"""Turns the generated World into source-shaped tables (lists of string rows), exactly as they are written to disk.

SAP tables are an ODP-style change feed: one row per change with `ODQ_CHANGEMODE` (C create, U update, D delete) and the
change date and time `AEDAT`/`AEZET`, which the connector uses as its incremental cursor. Dates use SAP's `YYYYMMDD` text
format, with `00000000` for an empty date. `TCURR.GDATU` is stored inverted, as SAP does.
"""
from __future__ import annotations

from datetime import date, datetime, time

from contextloop.datagen.world import STALE_CUTOFF, World

Table = tuple[list[str], list[dict[str, str]]]

SAP_KEYS = {
    "KNA1": ["MANDT", "KUNNR"], "VBAK": ["MANDT", "VBELN"], "VBAP": ["MANDT", "VBELN", "POSNR"],
    "LIKP": ["MANDT", "VBELN"], "LIPS": ["MANDT", "VBELN", "POSNR"], "VBRK": ["MANDT", "VBELN"],
    "VBRP": ["MANDT", "VBELN", "POSNR"], "TCURR": ["MANDT", "KURST", "FCURR", "TCURR", "GDATU"],
}
SAP_COLUMNS = {
    "KNA1": ["MANDT", "KUNNR", "NAME1", "LAND1", "ORT01", "TELF1", "KTOKD", "ERDAT"],
    "VBAK": ["MANDT", "VBELN", "ERDAT", "ERZET", "AUART", "VKORG", "KUNNR", "NETWR", "WAERK", "VDATU"],
    "VBAP": ["MANDT", "VBELN", "POSNR", "MATNR", "ARKTX", "KWMENG", "NETWR", "WAERK", "ERDAT"],
    "LIKP": ["MANDT", "VBELN", "KUNNR", "VSTEL", "ERDAT", "WADAT", "WADAT_IST", "LFDAT"],
    "LIPS": ["MANDT", "VBELN", "POSNR", "MATNR", "LFIMG", "VGBEL", "VGPOS", "ERDAT"],
    "VBRK": ["MANDT", "VBELN", "FKART", "FKDAT", "KUNAG", "NETWR", "WAERK", "ERDAT"],
    "VBRP": ["MANDT", "VBELN", "POSNR", "MATNR", "NETWR", "VGBEL", "AUBEL", "ERDAT"],
    "TCURR": ["MANDT", "KURST", "FCURR", "TCURR", "GDATU", "UKURS"],
}
CHANGE_COLS = ["AEDAT", "AEZET", "ODQ_CHANGEMODE"]
MANDT = "100"


def sap_date(d: date | None) -> str:
    return d.strftime("%Y%m%d") if d else "00000000"


def ts(dt: datetime | None) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ") if dt else ""


def money(x: float) -> str:
    return f"{x:.2f}"


def _change(row: dict, mode: str, when: date, hhmmss: str) -> dict:
    return row | {"AEDAT": sap_date(when), "AEZET": hhmmss, "ODQ_CHANGEMODE": mode}


def _am(n: int) -> str:  # creation rows in the morning, later changes in the afternoon, so order within a day is right
    return f"{8 + n % 4:02d}{(n * 7) % 60:02d}{(n * 13) % 60:02d}"


def _pm(n: int) -> str:
    return f"{13 + n % 5:02d}{(n * 11) % 60:02d}{(n * 17) % 60:02d}"


def sap_batch1(w: World) -> dict[str, Table]:
    feeds: dict[str, list[dict]] = {t: [] for t in SAP_COLUMNS}
    for n, c in enumerate(w.customers):
        row = {"MANDT": MANDT, "KUNNR": c.kunnr, "NAME1": c.name, "LAND1": c.land1, "ORT01": c.city,
               "TELF1": c.phone, "KTOKD": "0001", "ERDAT": sap_date(c.since)}
        feeds["KNA1"].append(_change(row, "C", c.since, _am(n)))
    for n, o in enumerate(w.orders):
        c = o.customer
        head = {"MANDT": MANDT, "VBELN": o.vbeln, "ERDAT": sap_date(o.erdat), "ERZET": o.erzet, "AUART": "ZOR", "VKORG": c.vkorg,
                "KUNNR": c.kunnr, "NETWR": money(o.netwr), "WAERK": c.currency, "VDATU": sap_date(o.vdatu)}
        feeds["VBAK"].append(_change(head, "C", o.erdat, _am(n)))
        items = [{"MANDT": MANDT, "VBELN": o.vbeln, "POSNR": i["posnr"], "MATNR": i["matnr"], "ARKTX": i["arktx"],
                  "KWMENG": str(i["qty"]), "NETWR": money(i["netwr"]), "WAERK": c.currency, "ERDAT": sap_date(o.erdat)} for i in o.items]
        feeds["VBAP"] += [_change(r, "C", o.erdat, _am(n)) for r in items]
        if o.cancelled_on:
            feeds["VBAK"].append(_change(head, "D", o.cancelled_on, _pm(n)))
            feeds["VBAP"] += [_change(r, "D", o.cancelled_on, _pm(n)) for r in items]
        qty = {i["posnr"]: i["qty"] for i in o.items}
        mat = {i["posnr"]: i["matnr"] for i in o.items}
        for k, d in enumerate(o.deliveries):
            m = n * 3 + k
            hdr = {"MANDT": MANDT, "VBELN": d.vbeln, "KUNNR": c.kunnr, "VSTEL": "1000" if c.vkorg == "1000" else "2000",
                   "ERDAT": sap_date(d.erdat), "WADAT": sap_date(d.wadat), "WADAT_IST": "00000000", "LFDAT": sap_date(d.lfdat)}
            feeds["LIKP"].append(_change(hdr, "C", d.erdat, _am(m)))
            lips = [{"MANDT": MANDT, "VBELN": d.vbeln, "POSNR": p, "MATNR": mat[p], "LFIMG": str(qty[p]), "VGBEL": o.vbeln,
                     "VGPOS": p, "ERDAT": sap_date(d.erdat)} for p in d.posnrs]
            feeds["LIPS"] += [_change(r, "C", d.erdat, _am(m)) for r in lips]
            if d.cancelled_on:
                feeds["LIKP"].append(_change(hdr, "D", d.cancelled_on, _pm(m)))
                feeds["LIPS"] += [_change(r, "D", d.cancelled_on, _pm(m)) for r in lips]
            elif d.wadat_ist:
                feeds["LIKP"].append(_change(hdr | {"WADAT_IST": sap_date(d.wadat_ist)}, "U", d.wadat_ist, _pm(m)))
    for n, inv in enumerate(w.invoices):
        hdr = {"MANDT": MANDT, "VBELN": inv["vbeln"], "FKART": inv["fkart"], "FKDAT": sap_date(inv["fkdat"]), "KUNAG": inv["kunag"],
               "NETWR": money(inv["netwr"]), "WAERK": inv["waerk"], "ERDAT": sap_date(inv["fkdat"])}
        feeds["VBRK"].append(_change(hdr, "C", inv["fkdat"], _pm(n)))
        for ln in inv["lines"]:
            feeds["VBRP"].append(_change({"MANDT": MANDT, "VBELN": inv["vbeln"], "POSNR": ln["posnr"], "MATNR": ln["matnr"],
                                          "NETWR": money(ln["netwr"]), "VGBEL": ln["vgbel"], "AUBEL": ln["aubel"],
                                          "ERDAT": sap_date(inv["fkdat"])}, "C", inv["fkdat"], _pm(n)))
    for n, (month, rate) in enumerate(sorted(w.rates.items())):
        first = date(int(month[:4]), int(month[5:]), 1)
        row = {"MANDT": MANDT, "KURST": "M", "FCURR": "EUR", "TCURR": "USD", "GDATU": str(99999999 - int(sap_date(first))),
               "UKURS": f"{rate:.5f}"}
        feeds["TCURR"].append(_change(row, "C", first, _am(n)))
    return {t: (SAP_COLUMNS[t] + CHANGE_COLS, _sorted(t, rows)) for t, rows in feeds.items()}


def sap_batch2(w: World) -> dict[str, Table]:
    """New deliveries and updates after the as-of date, with the new column ZZ_CARRIER_ID (schema change)."""
    likp, lips = [], []
    when = w.batch2_deliveries[0].erdat if w.batch2_deliveries else None
    for n, d in enumerate(w.batch2_deliveries + w.batch2_updates):
        c, o = d.order.customer, d.order
        hdr = {"MANDT": MANDT, "VBELN": d.vbeln, "KUNNR": c.kunnr, "VSTEL": "1000" if c.vkorg == "1000" else "2000",
               "ERDAT": sap_date(d.erdat), "WADAT": sap_date(d.wadat), "WADAT_IST": "00000000", "LFDAT": sap_date(d.lfdat),
               "ZZ_CARRIER_ID": d.carrier_id}
        is_new = n < len(w.batch2_deliveries)
        likp.append(_change(hdr, "C" if is_new else "U", when, _am(n) if is_new else _pm(n)))
        if is_new:
            items = {i["posnr"]: i for i in o.items}
            lips += [_change({"MANDT": MANDT, "VBELN": d.vbeln, "POSNR": p, "MATNR": items[p]["matnr"], "LFIMG": str(items[p]["qty"]),
                              "VGBEL": o.vbeln, "VGPOS": p, "ERDAT": sap_date(d.erdat)}, "C", when, _am(n)) for p in d.posnrs]
    return {"LIKP": (SAP_COLUMNS["LIKP"] + ["ZZ_CARRIER_ID"] + CHANGE_COLS, _sorted("LIKP", likp)),
            "LIPS": (SAP_COLUMNS["LIPS"] + CHANGE_COLS, _sorted("LIPS", lips))}


def _sorted(table: str, rows: list[dict]) -> list[dict]:
    keys = SAP_KEYS[table]
    return sorted(rows, key=lambda r: (r["AEDAT"], r["AEZET"], *[r[k] for k in keys]))


def saas(w: World) -> dict[str, Table]:
    acct_cols = ["id", "name", "sap_customer_number_c", "tier_c", "region_c", "billing_country", "owner_id", "industry",
                 "is_deleted", "created_date", "last_modified_date", "valid_from", "valid_to"]
    accounts = [{"id": a["id"], "name": a["name"], "sap_customer_number_c": a["sap_customer_number_c"] or "", "tier_c": a["tier_c"],
                 "region_c": a["region_c"], "billing_country": a["billing_country"], "owner_id": a["owner_id"], "industry": a["industry"],
                 "is_deleted": "false", "created_date": ts(a["created_date"]), "last_modified_date": ts(a["last_modified_date"]),
                 "valid_from": ts(a["valid_from"]), "valid_to": ts(a["valid_to"])} for a in w.sf_accounts]
    opp_cols = ["id", "account_id", "name", "type", "stage_name", "close_date", "amount", "is_closed", "is_won", "owner_id",
                "is_deleted", "created_date", "last_modified_date"]
    opps = [{"id": o["id"], "account_id": o["account_id"], "name": o["name"], "type": o["type"], "stage_name": o["stage_name"],
             "close_date": o["close_date"].isoformat(), "amount": money(o["amount"]), "is_closed": str(o["is_closed"]).lower(),
             "is_won": str(o["is_won"]).lower(), "owner_id": o["owner_id"], "is_deleted": "false",
             "created_date": ts(o["created_date"]), "last_modified_date": ts(o["last_modified_date"])} for o in w.sf_opportunities]
    user_cols = ["id", "name", "email", "title", "is_active"]
    users = [{k: (str(v).lower() if isinstance(v, bool) else v) for k, v in u.items()} for u in w.sf_users]
    org_cols = ["id", "name", "external_id", "created_at"]
    orgs = [{"id": str(o["id"]), "name": o["name"], "external_id": o["external_id"], "created_at": ts(o["created_at"])} for o in w.zd_organizations]
    t_cols = ["id", "created_at", "updated_at", "subject", "status", "priority", "type", "organization_id", "requester_id"]
    tickets = [{k: (ts(v) if isinstance(v, datetime) else str(v)) for k, v in t.items()} for t in w.zd_tickets]
    tag_cols = ["ticket_id", "tag"]
    tags = [{"ticket_id": str(t["ticket_id"]), "tag": t["tag"]} for t in w.zd_tags]
    return {
        "salesforce/account_history": (acct_cols, accounts), "salesforce/opportunity": (opp_cols, opps),
        "salesforce/user": (user_cols, users), "zendesk/organization": (org_cols, orgs),
        "zendesk/ticket": (t_cols, tickets), "zendesk/ticket_tag": (tag_cols, tags),
    }


def carrier(w: World) -> dict[str, Table]:
    s_cols = ["shipment_id", "delivery_number", "carrier_code", "tracking_number", "status", "created_at", "updated_at"]
    e_cols = ["event_id", "shipment_id", "event_type", "event_at", "location", "updated_at"]
    ships = [{k: (ts(v) if isinstance(v, datetime) else str(v)) for k, v in s.items()} for s in w.shipments]
    evs = [{k: (ts(v) if isinstance(v, datetime) else str(v)) for k, v in e.items()} for e in w.events]
    return {"shipment": (s_cols, ships), "shipment_event": (e_cols, evs)}


def stale_cutoff_iso() -> str:
    return ts(STALE_CUTOFF)


__all__ = ["sap_batch1", "sap_batch2", "saas", "carrier", "SAP_KEYS", "stale_cutoff_iso", "time"]
