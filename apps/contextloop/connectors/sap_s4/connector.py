"""SAP S/4HANA connector for the ContextLoop demo, built with the Fivetran Connector SDK.

It reads an ODP-style change feed of SAP tables (one CSV per table per extraction batch) and replicates it incrementally:
  * schema()  declares each SAP table and its primary key; every other column is discovered from the data, so a column added at
              the source (LIKP.ZZ_CARRIER_ID in batch 2) appears in the destination with no code change.
  * update()  reads only the changes after the saved cursor, upserts creates and updates, emits deletes for cancelled documents
              (they land with _fivetran_deleted = TRUE and are never removed), and checkpoints its state so an interrupted
              sync resumes where it stopped.

Demo only: the extract is synthetic. A real deployment would use Fivetran's native SAP connectors or a hybrid deployment agent,
not this code.
"""
from __future__ import annotations

import csv
import glob
import os

from fivetran_connector_sdk import Connector
from fivetran_connector_sdk import Logging as log
from fivetran_connector_sdk import Operations as op

# SAP table -> primary key. MANDT (client) is part of every SAP key.
TABLES: dict[str, list[str]] = {
    "KNA1": ["MANDT", "KUNNR"],
    "VBAK": ["MANDT", "VBELN"],
    "VBAP": ["MANDT", "VBELN", "POSNR"],
    "LIKP": ["MANDT", "VBELN"],
    "LIPS": ["MANDT", "VBELN", "POSNR"],
    "VBRK": ["MANDT", "VBELN"],
    "VBRP": ["MANDT", "VBELN", "POSNR"],
    "TCURR": ["MANDT", "KURST", "FCURR", "TCURR", "GDATU"],
}
# Columns known when the connector was written. They are declared as text so SAP values keep their exact form (leading
# zeros, YYYYMMDD dates, 00000000 for an empty date). Columns that appear later are discovered from the data.
KNOWN_COLUMNS: dict[str, list[str]] = {
    "KNA1": ["NAME1", "LAND1", "ORT01", "TELF1", "KTOKD", "ERDAT"],
    "VBAK": ["ERDAT", "ERZET", "AUART", "VKORG", "KUNNR", "NETWR", "WAERK", "VDATU"],
    "VBAP": ["MATNR", "ARKTX", "KWMENG", "NETWR", "WAERK", "ERDAT"],
    "LIKP": ["KUNNR", "VSTEL", "ERDAT", "WADAT", "WADAT_IST", "LFDAT"],
    "LIPS": ["MATNR", "LFIMG", "VGBEL", "VGPOS", "ERDAT"],
    "VBRK": ["FKART", "FKDAT", "KUNAG", "NETWR", "WAERK", "ERDAT"],
    "VBRP": ["MATNR", "NETWR", "VGBEL", "AUBEL", "ERDAT"],
    "TCURR": ["UKURS"],
}
CHANGE_COLUMNS = ["AEDAT", "AEZET"]
CHECKPOINT_EVERY = 5000  # rows; a checkpoint also follows every table


def schema(configuration: dict) -> list[dict]:
    """Declares each SAP table, its primary key, and its known columns as text."""
    return [
        {"table": table, "primary_key": keys,
         "columns": {c: "STRING" for c in keys + KNOWN_COLUMNS[table] + CHANGE_COLUMNS}}
        for table, keys in TABLES.items()
    ]


def _cursor(row: dict, keys: list[str]) -> str:
    """Sortable position of a change: change date, change time, then the key (so ties are ordered too)."""
    return "|".join([row["AEDAT"] + row["AEZET"]] + [row[k] for k in keys])


def _changes(source_dir: str, table: str, after: str) -> list[dict]:
    """Every change to `table` after the cursor, across all extraction batches, in change order."""
    keys = TABLES[table]
    rows: list[dict] = []
    for path in sorted(glob.glob(os.path.join(source_dir, "batch=*", f"{table}.csv"))):
        with open(path, newline="", encoding="utf-8") as f:
            rows.extend(r for r in csv.DictReader(f) if _cursor(r, keys) > after)
    rows.sort(key=lambda r: _cursor(r, keys))
    return rows


def update(configuration: dict, state: dict):
    """Syncs every table incrementally from its saved cursor."""
    source_dir = configuration["source_dir"]
    fail_after = int(configuration.get("simulate_failure_after_checkpoints", "0") or 0)
    cursors: dict = dict(state.get("cursors", {}))
    checkpoints = 0
    for table, keys in TABLES.items():
        changes = _changes(source_dir, table, cursors.get(table, ""))
        log.info(f"{table}: {len(changes)} changes after cursor {cursors.get(table) or '(initial sync)'}")
        counts = {"C": 0, "U": 0, "D": 0}
        for n, row in enumerate(changes, start=1):
            mode = row.pop("ODQ_CHANGEMODE")
            counts[mode] += 1
            if mode == "D":
                op.delete(table=table, keys={k: row[k] for k in keys})
            else:
                op.upsert(table=table, data={k: v for k, v in row.items() if v != "" or k in keys})
            cursors[table] = _cursor(row, keys)
            if n % CHECKPOINT_EVERY == 0 or n == len(changes):
                op.checkpoint({"cursors": cursors})
                checkpoints += 1
                if fail_after and checkpoints >= fail_after:
                    raise RuntimeError(f"Simulated failure after {checkpoints} checkpoints (test of resume)")
        # One line per table that the sync job reads to build the sync log (CL-05).
        log.info(f"SYNC_RECORD table={table} inserted={counts['C']} updated={counts['U']} deleted={counts['D']}")


connector = Connector(update=update, schema=schema)

if __name__ == "__main__":
    import json

    with open("configuration.json", encoding="utf-8") as f:
        connector.debug(configuration=json.load(f))
