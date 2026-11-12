"""Builds the synthetic Northstar Industrial world: four linked source systems with planted traps.

Everything comes from one `random.Random(seed)`, so the same seed always gives the same records. The scenario (which accounts
are at risk and why) is engineered through account *roles*; the hidden truth is then computed from the generated records
alone (see truth.py), never from these intentions.
"""
from __future__ import annotations

import random
import string
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from contextloop.config import AS_OF

START = date(2025, 5, 1)
WINDOW_START = AS_OF - timedelta(days=89)  # 90 days, inclusive of the as-of date
TIER_CHANGE_AT = datetime(2026, 9, 22, 14, 30)  # mid-window promotions and the demotion (T5)
END_OF_TIME = datetime(9999, 12, 31, 23, 59, 59)
STALE_CUTOFF = datetime.combine(AS_OF - timedelta(days=2), time(0, 0))  # T6: Zendesk held two days behind
BATCH2_AT = datetime.combine(AS_OF + timedelta(days=1), time(6, 0))
N_ORDERS = 9000
CANCEL_RATE = 0.036

COUNTRIES = (
    [("US", "North America", 56), ("CA", "North America", 12), ("MX", "North America", 8)]
    + [("DE", "EMEA", 16), ("FR", "EMEA", 7), ("GB", "EMEA", 7), ("NL", "EMEA", 5), ("IT", "EMEA", 4), ("SE", "EMEA", 3), ("AT", "EMEA", 2)]
)
CITIES = {
    "US": ["Houston", "Cleveland", "Tulsa", "Baton Rouge", "Pittsburgh", "Milwaukee", "Charlotte", "Denver"],
    "CA": ["Calgary", "Hamilton", "Edmonton"], "MX": ["Monterrey", "Queretaro"],
    "DE": ["Duisburg", "Mannheim", "Hamburg", "Leverkusen"], "FR": ["Lyon", "Lille"], "GB": ["Leeds", "Aberdeen"],
    "NL": ["Rotterdam", "Eindhoven"], "IT": ["Turin", "Brescia"], "SE": ["Gothenburg"], "AT": ["Linz"],
}
LEGAL_SUFFIX = {"US": "Inc", "CA": "Ltd", "MX": "SA", "DE": "GmbH", "FR": "SA", "GB": "Ltd", "NL": "BV", "IT": "Srl", "SE": "AB", "AT": "GmbH"}
SYL_A = ["Bran", "Kel", "Mar", "Vel", "Dun", "Har", "Lin", "Osk", "Quen", "Ral", "Sev", "Tam", "Ulv", "Wes", "Yar", "Cor",
         "Fen", "Gal", "Ist", "Jor", "Pell", "Rov", "Stav", "Thal", "Vorn", "Ebb", "Ard", "Nesk", "Bryn", "Calt"]
SYL_B = ["mere", "stead", "holt", "wick", "ford", "ton", "vale", "bury", "land", "mark", "ridge", "more", "dale", "haven", "brook"]
INDUSTRY = ["Fluid Systems", "Process Equipment", "Energy", "Chemicals", "Water Works", "Mining", "Paper Mills",
            "Food Processing", "Marine", "Refining", "Utilities", "Steelworks", "HVAC", "Pipeline Services", "Pharma Plants"]
FIRST = ["Avery", "Jordan", "Riley", "Morgan", "Casey", "Quinn", "Rowan", "Sasha", "Elliot", "Noor", "Imani", "Tomas",
         "Lena", "Mateo", "Priya", "Jonas", "Ines", "Kofi", "Hana", "Arjun"]
LAST = ["Lindqvist", "Okoro", "Varga", "Beaumont", "Castell", "Moreau", "Albers", "Navarro", "Whitlock", "Ferrante",
        "Kowal", "Haddad", "Brandt", "Sato", "Delacroix", "Mbeki", "Orsini", "Halvorsen", "Quill", "Drummond"]

MATERIALS = [  # (MATNR, description, list price USD)
    ("VLV-1000", "Gate valve DN50 PN16", 420.0), ("VLV-1010", "Gate valve DN100 PN16", 910.0),
    ("VLV-1020", "Ball valve DN25 stainless", 185.0), ("VLV-1030", "Ball valve DN80 actuated", 1640.0),
    ("VLV-1040", "Butterfly valve DN200", 1320.0), ("VLV-1050", "Check valve DN65", 360.0),
    ("VLV-1060", "Control valve DN50 pneumatic", 2850.0), ("VLV-1070", "Safety relief valve 1in", 540.0),
    ("BRG-2000", "Deep groove ball bearing 6205", 18.5), ("BRG-2010", "Spherical roller bearing 22220", 265.0),
    ("BRG-2020", "Tapered roller bearing set", 74.0), ("BRG-2030", "Pillow block bearing UCP208", 58.0),
    ("BRG-2040", "Slewing ring bearing 600mm", 3900.0), ("BRG-2050", "Cylindrical roller bearing NU312", 142.0),
    ("PMP-3000", "Centrifugal pump 15kW", 6400.0), ("PMP-3010", "Centrifugal pump 45kW", 14800.0),
    ("PMP-3020", "Diaphragm metering pump", 2300.0), ("PMP-3030", "Progressive cavity pump", 9100.0),
    ("PMP-3040", "Submersible drainage pump", 1850.0), ("PMP-3050", "Pump mechanical seal kit", 410.0),
    ("SPR-4000", "Valve repair kit DN50", 95.0), ("SPR-4010", "Pump impeller 15kW", 780.0),
    ("SPR-4020", "Gasket set PN16", 22.0), ("SPR-4030", "Actuator positioner", 1250.0),
]

SHIP_SUBJECTS = ["Late delivery on order {order}", "Shipment {trk} delayed again", "Delivery for order {order} still missing",
                 "Tracking not updating for {trk}", "Order {order} arrived late", "Delay on bearings for line {n}"]
SHIP_SUBJECTS_NO_KEYWORD = ["Where is my order {order}?", "Order {order} not received yet", "Has {order} left your warehouse?"]
OTHER_SUBJECTS = ["Invoice {n} shows the wrong PO number", "Request for pump curve data sheet", "Bearing {m} running hot after install",
                  "Return authorization for valve kit", "Need certificate of conformity for {m}", "Credit note request for order {order}",
                  "Pricing question for next year", "Manual for {m} missing pages", "Seal kit compatibility question",
                  "Spare parts quote request", "Change of billing address", "Warranty claim for {m}"]
SHIP_TAG_CHOICES = [["shipping"]] * 7 + [["delivery"]] * 3 + [["late_delivery"]] * 2 + [["logistics"]] * 2 + [["shipping", "urgent"]] + [[]] * 5
OTHER_TAGS = {"Invoice": ["billing"], "Credit": ["billing"], "Pricing": ["sales"], "Change": ["billing"], "Return": ["returns"],
              "Warranty": ["returns", "warranty"]}
SHIPPING_TAGS = {"shipping", "delivery", "late_delivery", "logistics"}
SHIPPING_WORDS = ("late", "delay", "shipment", "delivery", "tracking")


def is_shipping_text(subject: str) -> bool:
    s = subject.lower()
    return any(w in s for w in SHIPPING_WORDS)


for _s in OTHER_SUBJECTS:  # non-shipping subjects must never match the shipping rule by accident
    assert not is_shipping_text(_s.format(n=1, m="VLV-1000", order="0010000001", trk="X")), _s
for _s in SHIP_SUBJECTS_NO_KEYWORD:
    assert not is_shipping_text(_s.format(order="0010000001")), _s

# Engineered roles. target = on-time rate in the 90-day window; tickets = open shipping-related tickets;
# renewal = days from the as-of date to the open renewal's close date.
ROLES: dict[str, dict] = {
    "R1": dict(tier="Strategic", target=0.62, tickets=3, renewal=(130, 330)),
    "R2": dict(tier="Strategic", target=0.70, tickets=2, renewal=(130, 330)),
    "R3": dict(tier="Strategic", target=0.74, tickets=4, renewal=(130, 330)),
    "R4": dict(tier="Strategic", target=0.78, tickets=2, renewal=(130, 330)),
    "R5": dict(tier="Strategic", target=0.80, tickets=3, renewal=(130, 330)),
    "R6": dict(tier="Strategic", target=0.72, tickets=1, renewal=30),
    "R7": dict(tier="Strategic", target=0.81, tickets=0, renewal=75),
    "P1": dict(tier="Strategic", before="Standard", target=0.76, tickets=1, renewal=45),
    "P2": dict(tier="Strategic", before="Standard", target=0.94, tickets=0),
    "P3": dict(tier="Strategic", before="Standard", target=0.97, tickets=1),
    "H": dict(tier="Strategic", target=0.75, tickets=1, dup_tickets=2, renewal=190),
    "C1": dict(tier="Strategic", target=0.93, tickets=0, renewal=60, cancel_window=0.30),
    "X1": dict(tier="Strategic", target=0.79, tickets=1, renewal=200, expansion=30),
    "X2": dict(tier="Strategic", target=0.95, tickets=3),
    "D1": dict(tier="Standard", before="Strategic", target=0.70, tickets=3, renewal=50),
    "N1": dict(tier="Standard", target=0.68, tickets=2, renewal=40),
}
N_HEALTHY_STRATEGIC = 11


@dataclass
class Customer:
    kunnr: str
    name: str
    land1: str
    city: str
    region: str
    currency: str
    vkorg: str
    since: date
    role: str
    tier_now: str
    tier_before: str
    target: float
    weight: float
    phone: str
    sf_id: str = ""
    owner_id: str = ""


@dataclass
class Delivery:
    vbeln: str
    order: "Order"
    posnrs: list[str]
    erdat: date
    wadat: date
    lfdat: date
    wadat_ist: date | None = None
    delivered_at: datetime | None = None
    picked_up_at: datetime | None = None
    late: bool | None = None
    late_kind: str | None = None
    cancelled_on: date | None = None
    carrier_id: str | None = None  # appears only in batch 2 (schema change)


@dataclass
class Order:
    vbeln: str
    customer: Customer
    erdat: date
    erzet: str
    vdatu: date
    items: list[dict]
    deliveries: list[Delivery] = field(default_factory=list)
    cancelled_on: date | None = None

    @property
    def netwr(self) -> float:
        return round(sum(i["netwr"] for i in self.items), 2)


@dataclass
class World:
    seed: int
    customers: list[Customer]
    orders: list[Order]
    rates: dict[str, float]  # 'YYYY-MM' -> EUR to USD monthly average
    invoices: list[dict]
    sf_users: list[dict]
    sf_accounts: list[dict]  # history-mode versions
    sf_opportunities: list[dict]
    zd_organizations: list[dict]
    zd_tickets: list[dict]
    zd_tags: list[dict]
    shipments: list[dict]
    events: list[dict]
    batch2_deliveries: list[Delivery]
    batch2_updates: list[Delivery]


def _rand_dt(rng: random.Random, d: date, h0: int = 7, h1: int = 18) -> datetime:
    return datetime.combine(d, time(rng.randint(h0, h1 - 1), rng.randint(0, 59), rng.randint(0, 59)))


def _sf_id(rng: random.Random, prefix: str) -> str:
    return prefix + "".join(rng.choice(string.ascii_letters + string.digits) for _ in range(15))


def _norm(name: str) -> str:
    import re

    s = re.sub(r"[^a-z0-9 ]", " ", name.lower())
    return " ".join(w for w in s.split() if w not in {"gmbh", "ag", "inc", "llc", "ltd", "corp", "bv", "sa", "srl", "ab"})


def build_world(seed: int) -> World:
    rng = random.Random(seed)
    customers = _customers(rng)
    users = _users(rng)
    for c in customers:
        c.owner_id = rng.choice(users)["id"]
    rates = _rates(rng)
    orders = _orders(rng, customers)
    _cancellations(rng, orders, customers)
    _assign_lateness(rng, orders, customers)
    invoices = _billing(rng, orders, rates)
    shipments, events = _carrier(rng, orders)
    accounts = _sf_accounts(rng, customers, users)
    opps = _sf_opportunities(rng, customers, accounts)
    orgs, tickets, tags = _zendesk(rng, customers, accounts, orders)
    b2_new, b2_upd = _batch2(rng, orders)
    return World(seed, customers, orders, rates, invoices, users, accounts, opps, orgs, tickets, tags, shipments, events, b2_new, b2_upd)


def _customers(rng: random.Random) -> list[Customer]:
    slots = [(cc, region) for cc, region, n in COUNTRIES for _ in range(n)]
    rng.shuffle(slots)
    names: set[str] = {"northstar"}
    roles = list(ROLES) + ["S"] * N_HEALTHY_STRATEGIC
    roles += ["-"] * (len(slots) - len(roles))
    # Halbrook (T4) must be German; put the role on a DE slot.
    de_idx = next(i for i, (cc, _) in enumerate(slots) if cc == "DE")
    roles.remove("H")
    roles.insert(de_idx, "H")
    out = []
    for i, ((cc, region), role) in enumerate(zip(slots, roles, strict=True)):
        if role == "H":
            base = "Halbrook Fluid Systems"
        else:
            while True:
                base = f"{rng.choice(SYL_A)}{rng.choice(SYL_B)} {rng.choice(INDUSTRY)}"
                if _norm(base) not in names and not base.lower().startswith("halbrook"):
                    break
        names.add(_norm(base))
        spec = ROLES.get(role, {})
        tier_now = spec.get("tier", "Strategic" if role == "S" else "Standard")
        target = spec.get("target") or (round(rng.uniform(0.89, 0.99), 3) if role == "S" else round(rng.uniform(0.83, 0.99), 3))
        out.append(Customer(
            kunnr=f"{100001 + i:010d}", name=f"{base} {LEGAL_SUFFIX[cc]}", land1=cc, city=rng.choice(CITIES[cc]),
            region=region, currency="USD" if region == "North America" else "EUR", vkorg="1000" if region == "North America" else "2000",
            since=date(2019, 1, 1) + timedelta(days=rng.randint(0, 2000)), role=role, tier_now=tier_now,
            tier_before=spec.get("before", tier_now), target=target, weight=3.0 if tier_now == "Strategic" or role == "D1" else 1.0,
            phone=f"555-01{rng.randint(0, 99):02d}",
        ))
    return out


def _users(rng: random.Random) -> list[dict]:
    users = []
    for i in range(10):
        first, last = FIRST[i * 2 % len(FIRST)], LAST[(i * 3 + 1) % len(LAST)]
        users.append({"id": _sf_id(rng, "005"), "name": f"{first} {last}", "email": f"{first.lower()}.{last.lower()}@example.com",
                      "title": "Account Executive" if i < 7 else "Customer Success Manager", "is_active": True})
    return users


def _rates(rng: random.Random) -> dict[str, float]:
    rates, r = {}, 1.0850
    d = START.replace(day=1)
    while d <= AS_OF:
        r = min(1.15, max(1.03, r + rng.gauss(0, 0.008)))
        rates[d.strftime("%Y-%m")] = round(r, 5)
        d = (d + timedelta(days=32)).replace(day=1)
    return rates


def _orders(rng: random.Random, customers: list[Customer]) -> list[Order]:
    total_w = sum(c.weight for c in customers)
    span = (AS_OF - START).days
    raw = []
    for c in customers:
        n = round(N_ORDERS * c.weight / total_w)
        for _ in range(n):
            raw.append((START + timedelta(days=rng.randint(0, span)), c))
    raw.sort(key=lambda x: (x[0], x[1].kunnr))
    orders = []
    for i, (erdat, c) in enumerate(raw):
        items = []
        for p in range(rng.choice([1, 2, 2, 3, 3, 3, 4, 4, 5])):
            matnr, desc, usd = rng.choice(MATERIALS)
            qty = rng.choice([1, 1, 2, 2, 4, 5, 10, 20]) if usd < 500 else rng.choice([1, 1, 1, 2, 3])
            price = usd if c.currency == "USD" else round(usd / 1.08, 2)
            items.append({"posnr": f"{(p + 1) * 10:06d}", "matnr": matnr, "arktx": desc, "qty": qty, "price": price,
                          "netwr": round(qty * price, 2)})
        o = Order(vbeln=f"{10000001 + i:010d}", customer=c, erdat=erdat, erzet=f"{rng.randint(7, 18):02d}{rng.randint(0, 59):02d}00",
                  vdatu=erdat + timedelta(days=rng.randint(12, 30)), items=items)
        orders.append(o)
    # Deliveries: created two days before the planned goods issue; ~5% of orders ship in two deliveries.
    seq = 0
    for o in orders:
        pt = 3 if o.customer.region == "North America" else 4
        wadat = o.vdatu - timedelta(days=pt)
        created = wadat - timedelta(days=2)
        if created > AS_OF:
            continue  # open order, no delivery yet (batch 2 creates some)
        groups = [o.items] if len(o.items) < 2 or rng.random() > 0.05 else [o.items[: len(o.items) // 2], o.items[len(o.items) // 2:]]
        for g in groups:
            seq += 1
            o.deliveries.append(Delivery(vbeln=f"{80000000 + seq:010d}", order=o, posnrs=[i["posnr"] for i in g],
                                         erdat=created, wadat=wadat, lfdat=o.vdatu))
    return orders


def _cancellations(rng: random.Random, orders: list[Order], customers: list[Customer]) -> None:
    c1 = next(c for c in customers if c.role == "C1")
    for o in orders:
        if not o.deliveries:
            continue
        d0 = o.deliveries[0]
        latest_cancel = min(d0.wadat - timedelta(days=1), AS_OF)
        if latest_cancel < d0.erdat:
            continue
        in_window = WINDOW_START <= o.vdatu <= AS_OF
        p = ROLES["C1"]["cancel_window"] if (o.customer is c1 and in_window) else CANCEL_RATE
        if rng.random() < p:
            o.cancelled_on = d0.erdat + timedelta(days=rng.randint(0, (latest_cancel - d0.erdat).days))
            for d in o.deliveries:
                d.cancelled_on = o.cancelled_on


def _assign_lateness(rng: random.Random, orders: list[Order], customers: list[Customer]) -> None:
    window: dict[str, list[Delivery]] = {c.kunnr: [] for c in customers}
    others: list[Delivery] = []
    for o in orders:
        for d in o.deliveries:
            if d.cancelled_on:
                continue
            (window[o.customer.kunnr] if WINDOW_START <= o.vdatu <= AS_OF else others).append(d)
    for c in customers:
        ds = window[c.kunnr]
        k = round(len(ds) * (1 - c.target))
        late = set(id(d) for d in rng.sample(ds, k)) if k else set()
        for d in ds:
            d.late = id(d) in late
    for d in others:
        d.late = rng.random() < 0.07
    for o in orders:
        pt = 3 if o.customer.region == "North America" else 4
        for d in o.deliveries:
            if d.cancelled_on:
                continue
            if d.late:
                d.late_kind = rng.choice(["transit", "goods_issue"])
                if d.late_kind == "transit":
                    gi, transit = d.wadat, pt + rng.randint(1, 6)
                else:
                    gi, transit = d.wadat + timedelta(days=rng.randint(1, 6)), pt
            else:
                gi = d.wadat - timedelta(days=rng.choice([0, 0, 0, 1]))
                transit = max(1, pt - rng.choice([0, 0, 1]))
            if gi > AS_OF:
                continue  # not shipped yet
            d.wadat_ist = gi
            d.picked_up_at = _rand_dt(rng, gi, 7, 11)
            arrival = gi + timedelta(days=transit)
            if arrival <= AS_OF:
                d.delivered_at = _rand_dt(rng, arrival, 9, 17)


def _billing(rng: random.Random, orders: list[Order], rates: dict[str, float]) -> list[dict]:
    invoices, seq = [], 0
    for o in orders:
        items = {i["posnr"]: i for i in o.items}
        for d in o.deliveries:
            if d.cancelled_on or not d.wadat_ist:
                continue
            seq += 1
            lines = [items[p] for p in d.posnrs]
            inv = {"vbeln": f"{90000000 + seq:010d}", "fkart": "F2", "fkdat": d.wadat_ist, "kunag": o.customer.kunnr,
                   "waerk": o.customer.currency, "netwr": round(sum(i["netwr"] for i in lines), 2), "delivery": d, "order": o,
                   "lines": [{"posnr": i["posnr"], "matnr": i["matnr"], "netwr": i["netwr"], "vgbel": d.vbeln, "aubel": o.vbeln} for i in lines]}
            invoices.append(inv)
    memos = []
    for inv in invoices:
        if rng.random() < 0.03:
            fkdat = inv["fkdat"] + timedelta(days=rng.randint(5, 30))
            if fkdat > AS_OF:
                continue
            seq += 1
            amt = round(inv["netwr"] * rng.uniform(0.05, 0.25), 2)
            memos.append({"vbeln": f"{90000000 + seq:010d}", "fkart": "G2", "fkdat": fkdat, "kunag": inv["kunag"], "waerk": inv["waerk"],
                          "netwr": amt, "delivery": None, "order": inv["order"],
                          "lines": [{"posnr": "000010", "matnr": inv["lines"][0]["matnr"], "netwr": amt, "vgbel": inv["vbeln"],
                                     "aubel": inv["order"].vbeln}]})
    return invoices + memos


def _carrier(rng: random.Random, orders: list[Order]) -> tuple[list[dict], list[dict]]:
    shipments, events = [], []
    carriers = ["NRTH", "VELX", "KSTL", "ORBF"]
    sid = 500000
    eid = 7000000
    end_of_asof = datetime.combine(AS_OF, time(23, 59, 59))
    for o in orders:
        for d in o.deliveries:
            sid += 1
            evs = [("label_created", _rand_dt(rng, d.erdat, 8, 16), None)]
            if d.cancelled_on:
                evs.append(("cancelled", _rand_dt(rng, d.cancelled_on, 9, 17), None))
            elif d.wadat_ist:
                evs.append(("picked_up", d.picked_up_at, o.customer.city if rng.random() < 0 else "Northstar DC"))
                if d.delivered_at:
                    mid = d.picked_up_at + (d.delivered_at - d.picked_up_at) / 2
                    evs.append(("in_transit", mid, "Hub"))
                    evs.append(("out_for_delivery", d.delivered_at - timedelta(hours=rng.randint(2, 5)), o.customer.city))
                    evs.append(("delivered", d.delivered_at, o.customer.city))
                else:
                    t = d.picked_up_at + timedelta(days=1)
                    if t <= end_of_asof:
                        evs.append(("in_transit", t, "Hub"))
            evs = [e for e in evs if e[1] <= end_of_asof]
            created, last = evs[0][1], evs[-1][1]
            shipments.append({"shipment_id": sid, "delivery_number": d.vbeln, "carrier_code": rng.choice(carriers),
                              "tracking_number": f"TRK{rng.randint(10**9, 10**10 - 1)}", "status": evs[-1][0],
                              "created_at": created, "updated_at": last})
            for etype, at, loc in evs:
                eid += 1
                events.append({"event_id": eid, "shipment_id": sid, "event_type": etype, "event_at": at,
                               "location": loc or "Northstar DC", "updated_at": at})
    return shipments, events


def _sf_accounts(rng: random.Random, customers: list[Customer], users: list[dict]) -> list[dict]:
    rows = []
    change_end = TIER_CHANGE_AT - timedelta(milliseconds=1)

    def version(acct_id, name, sap, tier, c, start, end, owner, country, region):
        return {"id": acct_id, "name": name, "sap_customer_number_c": sap, "tier_c": tier, "region_c": region,
                "billing_country": country, "owner_id": owner, "industry": "Industrial Manufacturing",
                "created_date": c, "last_modified_date": start, "valid_from": start, "valid_to": end}

    for c in customers:
        c.sf_id = _sf_id(rng, "001")
        created = datetime.combine(c.since, time(10, 0))
        name = "Halbrook Fluid Systems" if c.role == "H" else c.name
        if c.tier_before != c.tier_now:
            rows.append(version(c.sf_id, name, c.kunnr, c.tier_before, created, created, change_end, c.owner_id, c.land1, c.region))
            rows.append(version(c.sf_id, name, c.kunnr, c.tier_now, created, TIER_CHANGE_AT, END_OF_TIME, c.owner_id, c.land1, c.region))
        else:
            rows.append(version(c.sf_id, name, c.kunnr, c.tier_now, created, created, END_OF_TIME, c.owner_id, c.land1, c.region))
    h = next(c for c in customers if c.role == "H")
    dup_created = datetime(2025, 2, 10, 9, 15)
    other_owner = next(u["id"] for u in users if u["id"] != h.owner_id)
    rows.append(version(_sf_id(rng, "001"), "Halbrook Fluid Systems GmbH", None, "Strategic", dup_created, dup_created, END_OF_TIME,
                        other_owner, "DE", "EMEA") | {"is_duplicate_of": h.sf_id})
    taken = {_norm(c.name) for c in customers}
    for _ in range(13):  # prospects: no SAP customer
        while True:
            base = f"{rng.choice(SYL_A)}{rng.choice(SYL_B)} {rng.choice(INDUSTRY)}"
            if _norm(base) not in taken and not base.lower().startswith("halbrook"):
                break
        taken.add(_norm(base))
        cc = rng.choice(["US", "DE", "CA", "FR"])
        created = datetime(2026, rng.randint(1, 9), rng.randint(1, 28), 11, 0)
        rows.append(version(_sf_id(rng, "001"), f"{base} {LEGAL_SUFFIX[cc]}", None, "Prospect", created, created, END_OF_TIME,
                            rng.choice(users)["id"], cc, "North America" if cc in ("US", "CA") else "EMEA"))
    return rows


def _sf_opportunities(rng: random.Random, customers: list[Customer], accounts: list[dict]) -> list[dict]:
    opps = []
    for c in customers:
        spec = ROLES.get(c.role, {})
        r = spec.get("renewal")
        if isinstance(r, tuple):
            offset = rng.randint(*r)
        elif isinstance(r, int):
            offset = r
        elif c.tier_now == "Strategic" and c.role not in ROLES:
            offset = rng.randint(1, 365)
        else:
            offset = rng.randint(1, 365)
        annual = round(rng.uniform(40, 400) * (3 if c.tier_now == "Strategic" else 1)) * 1000.0
        nxt = AS_OF + timedelta(days=offset)
        for k in (2, 1):  # past renewals, closed
            close = nxt - timedelta(days=365 * k)
            if close < START - timedelta(days=200):
                continue
            won = rng.random() < 0.92
            opps.append(_opp(rng, c, "Renewal", close, "Closed Won" if won else "Closed Lost", True, won, annual))
        stage = "Negotiation" if offset <= 60 else ("Proposal" if offset <= 150 else "Qualification")
        opps.append(_opp(rng, c, "Renewal", nxt, stage, False, False, annual))
        if "expansion" in spec:
            opps.append(_opp(rng, c, "Expansion", AS_OF + timedelta(days=spec["expansion"]), "Proposal", False, False, annual * 0.3))
        elif rng.random() < 0.3:
            opps.append(_opp(rng, c, "Expansion", AS_OF + timedelta(days=rng.randint(10, 200)), "Qualification", False, False, annual * 0.2))
    return opps


def _opp(rng, c, otype, close, stage, closed, won, amount):
    return {"id": _sf_id(rng, "006"), "account_id": c.sf_id, "name": f"{c.name.split(' ')[0]} {otype} {close.year}",
            "type": otype, "stage_name": stage, "close_date": close, "amount": round(amount, 2), "is_closed": closed,
            "is_won": won, "owner_id": c.owner_id, "created_date": datetime.combine(close - timedelta(days=150), time(9, 0)),
            "last_modified_date": datetime.combine(min(close - timedelta(days=20), AS_OF - timedelta(days=3)), time(9, 0))}


def _zendesk(rng: random.Random, customers: list[Customer], accounts: list[dict], orders: list[Order]):
    orgs, org_by_sf = [], {}
    for i, a in enumerate(a for a in accounts if a["tier_c"] != "Prospect" and a["valid_to"] == END_OF_TIME):
        org = {"id": 360000000001 + i, "name": a["name"], "external_id": a["id"], "created_at": a["created_date"]}
        orgs.append(org)
        org_by_sf[a["id"]] = org
    dup = next(a for a in accounts if a.get("is_duplicate_of"))
    orders_by_c: dict[str, list[Order]] = {}
    for o in orders:
        orders_by_c.setdefault(o.customer.kunnr, []).append(o)
    tickets, tags = [], []

    def add(org_id, created, updated, subject, status, tag_list, c_orders):
        tickets.append({"id": 0, "created_at": created, "updated_at": updated, "subject": subject, "status": status,
                        "priority": rng.choice(["low", "normal", "normal", "high", "urgent"]),
                        "type": rng.choice(["question", "problem", "incident"]),
                        "organization_id": org_id, "requester_id": rng.randint(9000000, 9999999), "_tags": tag_list})

    def subj(templates, c):
        os_ = orders_by_c.get(c.kunnr) or [None]
        o = rng.choice(os_)
        return rng.choice(templates).format(order=o.vbeln if o else "0010000001", trk=f"TRK{rng.randint(10**9, 10**10 - 1)}",
                                            n=rng.randint(1000, 9999), m=rng.choice(MATERIALS)[0])

    def ship_ticket(c):
        if rng.random() < 0.25:
            return subj(SHIP_SUBJECTS_NO_KEYWORD, c), [["shipping"], ["delivery"], ["logistics"]][rng.randint(0, 2)]
        return subj(SHIP_SUBJECTS, c), list(rng.choice(SHIP_TAG_CHOICES))

    total_w = sum(c.weight for c in customers)
    bg_end = AS_OF - timedelta(days=3)
    span = (bg_end - START).days
    for c in customers:
        org_id = org_by_sf[c.sf_id]["id"]
        for _ in range(round(2950 * c.weight / total_w)):
            created = _rand_dt(rng, START + timedelta(days=rng.randint(0, span)))
            if rng.random() < 0.33:
                s, t = ship_ticket(c)
                status = rng.choice(["solved", "closed"])
            else:
                s = subj(OTHER_SUBJECTS, c)
                t = list(OTHER_TAGS.get(s.split(" ")[0], ["product_question"]))
                recent = (bg_end - created.date()).days < 20
                status = rng.choice(["open", "pending", "solved"]) if recent else rng.choice(["solved", "closed"])
            updated = min(created + timedelta(days=rng.randint(0, 15), hours=rng.randint(0, 8)), datetime.combine(bg_end, time(18, 0)))
            add(org_id, created, max(updated, created), s, status, t, None)
        spec = ROLES.get(c.role, {})
        n_open = spec.get("tickets", rng.choice([0, 0, 1]) if c.tier_now == "Strategic" else rng.choice([0, 0, 0, 1]))
        for target_org, n in ((org_id, n_open), (org_by_sf[dup["id"]]["id"] if c.role == "H" else None, spec.get("dup_tickets", 0))):
            for _ in range(n or 0):
                created = _rand_dt(rng, AS_OF - timedelta(days=rng.randint(4, 25)))
                updated = min(created + timedelta(days=rng.randint(0, 2)), datetime.combine(bg_end, time(18, 0)))
                s, t = ship_ticket(c)
                add(target_org, created, max(created, updated), s, rng.choice(["open", "open", "pending", "new", "hold"]), t, None)
    # T6: the most recent tickets (last two days) are non-shipping; a stale Zendesk sync misses them.
    for _ in range(12):
        c = rng.choice(customers)
        created = _rand_dt(rng, AS_OF - timedelta(days=rng.randint(0, 1)))
        add(org_by_sf[c.sf_id]["id"], created, created, subj(OTHER_SUBJECTS, c), "new", ["product_question"], None)
    tickets.sort(key=lambda t: (t["created_at"], t["organization_id"], t["subject"]))
    for i, t in enumerate(tickets):
        t["id"] = 100001 + i
        for tag in t.pop("_tags"):
            tags.append({"ticket_id": t["id"], "tag": tag})
    return orgs, tickets, tags


def _batch2(rng: random.Random, orders: list[Order]) -> tuple[list[Delivery], list[Delivery]]:
    """Schema-change batch: new deliveries and updates that carry the new LIKP column ZZ_CARRIER_ID."""
    carriers = ["NRTH", "VELX", "KSTL", "ORBF"]
    open_orders = [o for o in orders if not o.deliveries and not o.cancelled_on]
    open_orders.sort(key=lambda o: o.vbeln)
    new = []
    last_seq = max(int(d.vbeln) for o in orders for d in o.deliveries) - 80000000
    for o in open_orders[:40]:
        last_seq += 1
        pt = 3 if o.customer.region == "North America" else 4
        d = Delivery(vbeln=f"{80000000 + last_seq:010d}", order=o, posnrs=[i["posnr"] for i in o.items],
                     erdat=BATCH2_AT.date(), wadat=o.vdatu - timedelta(days=pt), lfdat=o.vdatu, carrier_id=rng.choice(carriers))
        new.append(d)
    unshipped = sorted((d for o in orders for d in o.deliveries if not d.cancelled_on and not d.wadat_ist), key=lambda d: d.vbeln)
    for d in unshipped[:30]:
        d.carrier_id = rng.choice(carriers)
    return new, unshipped[:30]
