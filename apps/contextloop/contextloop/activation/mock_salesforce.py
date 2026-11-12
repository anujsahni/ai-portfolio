"""Mock Salesforce REST API (a stand-in CRM for Act 5; it is NOT Salesforce and holds only synthetic data).

Accounts are seeded from the landed Salesforce data the first time they are needed. Four custom fields carry the delivery-risk
signal that the reverse ETL sync writes:
  Delivery_Risk__c, Delivery_Risk_Drivers__c, Next_Step__c (+ Next_Step_Source__c), Risk_Updated_At__c
Every write is recorded in the audit log with a timestamp, the fields changed and the model the values came from.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from contextloop.config import SERVING_PATH, WAREHOUSE_PATH

DB = WAREHOUSE_PATH.parent / "crm" / "mock_salesforce.db"
RISK_FIELDS = ["Delivery_Risk__c", "Delivery_Risk_Drivers__c", "Next_Step__c", "Next_Step_Source__c", "Risk_Updated_At__c"]
_lock = threading.Lock()

app = FastAPI(title="Mock Salesforce (synthetic, local only)",
              description="A stand-in CRM for the ContextLoop demo. Not Salesforce. Synthetic data only.")


class AccountPatch(BaseModel):
    Delivery_Risk__c: str | None = None
    Delivery_Risk_Drivers__c: str | None = None
    Next_Step__c: str | None = None
    Next_Step_Source__c: str | None = None
    Risk_Updated_At__c: str | None = None


def _db(path: Path = DB) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.execute("CREATE TABLE IF NOT EXISTS account (Id TEXT PRIMARY KEY, Name TEXT, Tier__c TEXT, OwnerName TEXT, "
                + ", ".join(f"{f} TEXT" for f in RISK_FIELDS) + ")")
    con.execute("CREATE TABLE IF NOT EXISTS audit (seq INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT, account_id TEXT, account_name TEXT, "
                "changes TEXT, source_model TEXT, sync_id TEXT)")
    return con


def seed(con: sqlite3.Connection) -> int:
    """Loads the account list from the landed Salesforce data, once."""
    if con.execute("SELECT count(*) FROM account").fetchone()[0] or not SERVING_PATH.exists():
        return 0
    import duckdb

    wh = duckdb.connect(str(SERVING_PATH), read_only=True)
    try:
        rows = wh.execute("SELECT a.id, a.name, a.tier_c, u.name FROM salesforce.account a LEFT JOIN salesforce.user u ON u.id = a.owner_id "
                          "WHERE a._fivetran_active AND a.sap_customer_number_c IS NOT NULL").fetchall()
    finally:
        wh.close()
    con.executemany("INSERT INTO account (Id, Name, Tier__c, OwnerName) VALUES (?, ?, ?, ?)", rows)
    con.commit()
    return len(rows)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "mock-salesforce"}


@app.get("/accounts")
def list_accounts(flagged_only: bool = False) -> list[dict]:
    with _lock, closing(_db()) as con:
        seed(con)
        sql = "SELECT * FROM account" + (" WHERE Delivery_Risk__c IS NOT NULL" if flagged_only else "") + " ORDER BY Name"
        return [dict(r) for r in con.execute(sql)]


@app.get("/accounts/{account_id}")
def get_account(account_id: str) -> dict:
    with _lock, closing(_db()) as con:
        seed(con)
        row = con.execute("SELECT * FROM account WHERE Id = ?", [account_id]).fetchone()
    if not row:
        raise HTTPException(404, "No such account in the mock CRM")
    return dict(row)


@app.patch("/accounts/{account_id}")
def patch_account(account_id: str, patch: AccountPatch, x_source_model: str = Header("unknown"),
                  x_sync_id: str = Header("manual")) -> dict:
    fields = patch.model_dump(exclude_unset=True)
    with _lock, closing(_db()) as con:
        seed(con)
        row = con.execute("SELECT * FROM account WHERE Id = ?", [account_id]).fetchone()
        if not row:
            raise HTTPException(404, "No such account in the mock CRM")
        changes = {k: {"from": row[k], "to": v} for k, v in fields.items() if row[k] != v}
        if changes:
            con.execute(f"UPDATE account SET {', '.join(f'{k} = ?' for k in changes)} WHERE Id = ?",
                        [c["to"] for c in changes.values()] + [account_id])
            con.execute("INSERT INTO audit (at, account_id, account_name, changes, source_model, sync_id) VALUES (?, ?, ?, ?, ?, ?)",
                        [datetime.now(timezone.utc).isoformat(timespec="seconds"), account_id, row["Name"], json.dumps(changes),
                         x_source_model, x_sync_id])
            con.commit()
        out = dict(con.execute("SELECT * FROM account WHERE Id = ?", [account_id]).fetchone())
    return out | {"changed_fields": sorted(changes)}


@app.get("/audit")
def audit(limit: int = 200) -> list[dict]:
    with _lock, closing(_db()) as con:
        rows = con.execute("SELECT * FROM audit ORDER BY seq DESC LIMIT ?", [limit]).fetchall()
    return [dict(r) | {"changes": json.loads(r["changes"])} for r in rows]


@app.post("/reset")
def reset() -> dict:
    """Clears every risk field and the audit log (for rehearsals)."""
    with _lock, closing(_db()) as con:
        con.execute("DELETE FROM audit")
        con.execute(f"UPDATE account SET {', '.join(f'{f} = NULL' for f in RISK_FIELDS)}")
        con.commit()
    return {"status": "reset"}
