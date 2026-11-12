"""Act 1: the naive agent. The same model and prompt as the governed agent, with one tool, `run_sql`, over the raw landed
tables only, and the list of those tables and columns, the way many teams first point an agent at their data.

It is not told to cut corners; it is asked to be accurate and state its assumptions. SQL runs on a read-only connection, so
any write fails (and the failure is logged in the trace).
"""
from __future__ import annotations

import re

import duckdb

from contextloop.agent import config as cfg
from contextloop.agent import runner
from contextloop.config import SERVING_PATH

RAW_SCHEMAS = ("sap_s4", "carrier_pg", "salesforce", "zendesk")
MAX_ROWS = 100
BLOCKED = re.compile(r"\b(marts|staging|intermediate|fivetran_log|main)\s*\.", re.I)

RUN_SQL_TOOL = {
    "name": "run_sql",
    "description": ("Run one read-only DuckDB SQL query against Northstar's raw data and get up to 100 rows back. Tables are "
                    "schema-qualified, e.g. sap_s4.vbak, carrier_pg.shipment_event, salesforce.account, zendesk.ticket. "
                    "DuckDB dialect: always write AS before a column alias (some words, such as matched, are keywords and "
                    "fail without it), and check each column's type in the table list before using it."),
    "input_schema": {"type": "object", "additionalProperties": False, "required": ["purpose", "sql"],
                     "properties": {"purpose": {"type": "string",
                                                "description": "One short sentence: what this query checks and why you need it"},
                                    "sql": {"type": "string", "description": "A single SELECT statement"}}},
}


TYPE_NAMES = {"VARCHAR": "text", "TIMESTAMP WITH TIME ZONE": "timestamptz", "BOOLEAN": "bool", "BIGINT": "int",
              "INTEGER": "int", "DOUBLE": "double", "DATE": "date"}
TABLE_REF = re.compile(r"\b(sap_s4|carrier_pg|salesforce|zendesk)\s*\.\s*([a-z_0-9]+)", re.I)


def _columns(con: duckdb.DuckDBPyConnection, where: str = "", params: list | None = None) -> list[tuple[str, str, str]]:
    """(schema, table, 'col type, col type, ...') for the raw tables."""
    return con.execute(
        "SELECT table_schema, table_name, string_agg(column_name || ' ' || data_type, ', ' ORDER BY ordinal_position) "
        f"FROM information_schema.columns WHERE table_schema IN {RAW_SCHEMAS} {where} GROUP BY 1, 2 ORDER BY 1, 2",
        params or []).fetchall()


def _short_types(cols: str) -> str:
    """'netwr VARCHAR, _fivetran_synced TIMESTAMP WITH TIME ZONE' -> 'netwr text, _fivetran_synced timestamptz'."""
    def short(col: str) -> str:
        name, _, dtype = col.partition(" ")
        return f"{name} {TYPE_NAMES.get(dtype, dtype.lower())}"
    return ", ".join(short(c) for c in cols.split(", "))


def schema_context() -> str:
    """The raw tables with each column's type, as a data team would hand them to an agent."""
    con = duckdb.connect(str(SERVING_PATH), read_only=True)
    try:
        rows = _columns(con)
    finally:
        con.close()
    return "\n".join(f"- {s}.{t}: {_short_types(cols)}" for s, t, cols in rows)


def system_prompt() -> str:
    return cfg.BASE_SYSTEM + f"""
## Your data and tools

You can query Northstar's raw data with the run_sql tool (DuckDB SQL). The data comes from four systems: SAP S/4HANA (ERP),
the carrier tracking database, Salesforce (CRM) and Zendesk (support). These are the tables available, with each column's
type. SAP fields land as text, the way SAP extracts arrive: amounts and quantities are decimal strings (CAST them to DECIMAL
before doing arithmetic) and dates are YYYYMMDD strings. An empty SAP date is '00000000', so parse dates with
try_strptime(col, '%Y%m%d'), which returns NULL for it instead of failing.

{schema_context()}
"""


KEYWORD_NEAR = re.compile(r'syntax error at or near "(\w+)"')


def tidy_sql(sql: str) -> tuple[str, list[str]]:
    """Removes quoting debris a model sometimes leaves at the end of a query (an unmatched trailing " or ;)."""
    fixes, s = [], sql.strip()
    if s.endswith('"') and s.count('"') % 2 == 1:
        s, _ = s[:-1].rstrip(), fixes.append("removed a stray trailing double quote")
    return s, fixes


def alias_keyword_fix(sql: str, message: str) -> str | None:
    """`count(x) matched` fails in DuckDB because MATCHED is a keyword; `count(x) AS matched` works. Returns the fixed SQL."""
    m = KEYWORD_NEAR.search(message)
    if not m:
        return None
    kw = m.group(1)
    fixed = re.sub(rf"(?<=[\w)])\s+({re.escape(kw)})(?=\s*(,|\bfrom\b|$))", r" AS \1", sql, flags=re.I)
    return fixed if fixed != sql else None


def run_sql(sql: str) -> dict:
    """Runs one read-only query. Dialect slips (not data mistakes) are repaired once and reported in `auto_fixed`."""
    if BLOCKED.search(sql):
        return {"error": "Only the raw schemas sap_s4, carrier_pg, salesforce and zendesk are available."}
    sql, fixes = tidy_sql(sql)
    try:
        out = _run(sql)
    except duckdb.ParserException as exc:
        fixed = alias_keyword_fix(sql, str(exc))
        if fixed is None:
            return {"error": f"{type(exc).__name__}: {exc}"} | ({"auto_fixed": fixes} if fixes else {})
        fixes.append(f"added AS before the alias {KEYWORD_NEAR.search(str(exc)).group(1)} (a DuckDB keyword)")
        try:
            out = _run(fixed)
        except duckdb.Error as exc2:
            out = _error(fixed, exc2)
        out["sql_run"] = fixed
    except duckdb.Error as exc:
        out = _error(sql, exc)
    return out | ({"auto_fixed": fixes} if fixes else {})


def _error(sql: str, exc: duckdb.Error) -> dict:
    out = {"error": f"{type(exc).__name__}: {exc}"}
    if isinstance(exc, duckdb.BinderException):
        # A column or type mistake: show the real columns of the tables the query used, as a SQL editor would.
        tables = sorted({(s.lower(), t.lower()) for s, t in TABLE_REF.findall(sql)})
        if tables:
            cond = " OR ".join("(table_schema = ? AND table_name = ?)" for _ in tables)
            con = duckdb.connect(str(SERVING_PATH), read_only=True)
            try:
                found = _columns(con, f"AND ({cond})", [x for pair in tables for x in pair])
            finally:
                con.close()
            out["columns_of_tables_used"] = {f"{s}.{t}": _short_types(cols) for s, t, cols in found}
    return out


def _run(sql: str) -> dict:
    con = duckdb.connect(str(SERVING_PATH), read_only=True)
    try:
        cur = con.execute(sql)
        if cur.description is None:
            return {"columns": [], "rows": [], "row_count": 0}
        cols = [d[0] for d in cur.description]
        rows = cur.fetchmany(MAX_ROWS + 1)
    finally:
        con.close()
    truncated = len(rows) > MAX_ROWS
    rows = rows[:MAX_ROWS]
    clean = [[v if v is None or isinstance(v, (int, float, str, bool)) else str(v) for v in r] for r in rows]
    return {"columns": cols, "rows": clean, "row_count": len(clean), "truncated": truncated}


def execute(name: str, args: dict) -> dict:
    if name == "run_sql":
        return run_sql(args.get("sql", ""))
    return {"error": f"Unknown tool {name}"}


def tools() -> list[dict]:
    return [RUN_SQL_TOOL]


def answer(question_id: str, question: str, **kw) -> runner.Trace:
    return runner.run("naive", question_id, question, system_prompt(), tools(), execute, **kw)
