"""Generate a reproducible, Salesforce-shaped CRM for the fictional vendor Altura Analytics.

How it works:
1. Each deal gets hidden drivers (executive engagement, champion, competitor, discount, slips,
   activity level, support cases). For closed deals, the hidden rule turns them into a win
   probability and a coin flip decides the outcome.
2. A timeline is built from the drivers: creation, stage changes, close-date slips, contact roles,
   activities, support cases. Records are written from that timeline, with history objects
   (OpportunityHistory, OpportunityFieldHistory) so any past date can be reconstructed.
3. Open deals (this quarter) stop at the snapshot date and get readable activity notes.

Same seed → identical output.
"""
from __future__ import annotations

import math
import random
import unicodedata
from dataclasses import dataclass, field
from datetime import date, timedelta

from . import notes as notes_mod
from .vocab import (
    COMPETITORS, CONTACT_ROLES, EXECUTIVE_LEVELS, FIRST_NAMES, HISTORY_END, HISTORY_START, INDUSTRIES,
    LAST_NAMES, LEAD_SOURCES, NAME_HEADS, NAME_TAILS, ACCOUNT_SUFFIXES, OPEN_STAGES, PRODUCTS, PROPOSAL_INDEX,
    QUARTER_END, SEGMENTS, SNAPSHOT_DATE, STAGE_PROBABILITY, TEAMS, TITLES, employees_segment,
)

NEXT_STEP = {
    "Prospecting": "Schedule discovery call",
    "Qualification": "Book tailored demo",
    "Needs Analysis": "Agree proof-of-value success criteria",
    "Proposal/Price Quote": "Review proposal with stakeholders",
    "Negotiation/Review": "Close out legal redlines and procurement",
}


def sigmoid(x: float) -> float:
    return 1 / (1 + math.exp(-x))


def rule_logit(rule: dict, d: "Drivers") -> float:
    w = rule["weights"]
    return (
        rule["intercept"]
        + w["exec_engaged"] * d.exec_engaged
        + w["champion"] * d.champion
        + w["competitor"] * bool(d.competitor)
        + w["discount_points_over_15"] * max(0, d.discount - 15)
        + w["close_pushes"] * d.pushes
        + w["activity_level_minus_1"] * (d.activity_level - 1)
        + w["severe_cases"] * d.severe_cases
        + w["expansion"] * (d.deal_type == "Expansion")
        + w["enterprise"] * (d.segment == "Enterprise")
    )


def ascii_slug(text: str) -> str:
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return "".join(ch for ch in plain.lower() if ch.isalnum())


@dataclass
class Drivers:
    account_id: str
    owner_id: str
    segment: str
    industry: str
    product: str
    deal_type: str
    amount: int
    exec_engaged: bool
    champion: bool
    competitor: str | None
    discount: int
    pushes: int
    activity_level: float
    severe_cases: int
    lead_source: str
    stage_index: int = 4              # open: current stage; closed lost: furthest stage reached
    forecast: str | None = None       # open deals only
    won: bool | None = None           # closed deals only
    win_probability: float = 0.0      # from the hidden rule
    scenario: str | None = None
    max_notes: int | None = None
    injection: bool = False


@dataclass
class Dataset:
    objects: dict[str, list[dict]] = field(default_factory=dict)
    truth: list[dict] = field(default_factory=list)        # hidden drivers per deal (evaluation only)
    note_topics: list[dict] = field(default_factory=list)  # topic of each note (evaluation only)
    traps: dict = field(default_factory=dict)

    def add(self, obj: str, record: dict) -> dict:
        self.objects.setdefault(obj, []).append(record)
        return record


class Ids:
    """Salesforce-like IDs: object key prefix + 'DP' + a counter (15 characters)."""

    def __init__(self) -> None:
        self.counters: dict[str, int] = {}

    def new(self, prefix: str) -> str:
        self.counters[prefix] = self.counters.get(prefix, 0) + 1
        return f"{prefix}DP{self.counters[prefix]:010d}"


class Generator:
    def __init__(self, seed: int, rule: dict, scenarios: list[dict], scale: float = 1.0) -> None:
        self.rng = random.Random(seed)
        self.rule = rule
        self.scenarios = scenarios
        self.n_accounts = max(60, int(400 * scale))
        self.n_closed = max(100, int(2400 * scale))
        self.n_open = max(len(scenarios) + 5, int(60 * scale))
        self.n_open_accounts = max(len(scenarios) + 3, int(40 * scale))
        self.ids = Ids()
        self.ds = Dataset()
        self.users: dict[str, dict] = {}
        self.accounts: list[dict] = []
        self.contacts_by_account: dict[str, list[dict]] = {}
        self.used_templates: dict[str, set[str]] = {}

    # ------------------------------------------------------------ helpers
    def poisson(self, lam: float) -> int:
        limit, k, p = math.exp(-lam), 0, 1.0
        while True:
            p *= self.rng.random()
            if p <= limit:
                return k
            k += 1

    def day_between(self, start: date, end: date) -> date:
        span = max(0, (end - start).days)
        return start + timedelta(days=self.rng.randint(0, span))

    def person(self) -> tuple[str, str]:
        return self.rng.choice(FIRST_NAMES), self.rng.choice(LAST_NAMES)

    # ------------------------------------------------------------ users, accounts, contacts
    def make_users(self) -> None:
        for team, spec in TEAMS.items():
            manager = self.ds.add("User", {
                "Id": self.ids.new("005"), "Name": spec["manager"], "Title": "Regional Sales Manager",
                "Team__c": team, "ManagerId": None, "IsManager__c": True,
            })
            self.users[spec["manager"]] = manager
            for rep in spec["reps"]:
                self.users[rep] = self.ds.add("User", {
                    "Id": self.ids.new("005"), "Name": rep, "Title": "Account Executive",
                    "Team__c": team, "ManagerId": manager["Id"], "IsManager__c": False,
                })

    def make_account(self, name: str, industry: str, segment: str | None = None, customer: bool | None = None) -> dict:
        seg = segment or self.rng.choices(list(SEGMENTS), weights=[0.4, 0.4, 0.2])[0]
        employees = self.rng.randint(*SEGMENTS[seg]["employees"])
        account = self.ds.add("Account", {
            "Id": self.ids.new("001"), "Name": name, "Industry": industry,
            "NumberOfEmployees": employees, "Segment__c": employees_segment(employees) if segment is None else seg,
            "BillingCountry": "United States",
            "Type": ("Customer" if customer else "Prospect") if customer is not None
                    else ("Customer" if self.rng.random() < 0.35 else "Prospect"),
        })
        self.accounts.append(account)
        self.make_contacts(account)
        return account

    def make_accounts(self) -> None:
        reserved = {s["account"] for s in self.scenarios}
        names: set[str] = set()
        while len(self.accounts) < self.n_accounts - len(self.scenarios):
            industry = self.rng.choice(INDUSTRIES)
            name = f"{self.rng.choice(NAME_HEADS)}{self.rng.choice(NAME_TAILS)} {self.rng.choice(ACCOUNT_SUFFIXES[industry])}"
            if name in names or name in reserved:
                continue
            names.add(name)
            self.make_account(name, industry)

    def make_contacts(self, account: dict) -> None:
        slug = ascii_slug(account["Name"])[:24]
        levels = ["C-level", "VP", "Director", "Manager", "Analyst"]
        chosen = [self.rng.choice(["C-level", "VP"]), "Manager", "Analyst"]
        chosen += self.rng.sample(levels, k=self.rng.randint(0, 2))
        contacts = []
        used: set[tuple[str, str]] = set()
        for level in chosen:
            first, last = self.person()
            while (first, last) in used:
                first, last = self.person()
            used.add((first, last))
            contacts.append(self.ds.add("Contact", {
                "Id": self.ids.new("003"), "AccountId": account["Id"], "FirstName": first, "LastName": last,
                "Title": self.rng.choice(TITLES[level]), "Seniority__c": level,
                "Email": f"{ascii_slug(first)}.{ascii_slug(last)}@{slug}.example.com",
                "Phone": f"+1-202-555-01{self.rng.randint(0, 99):02d}",
            }))
        self.contacts_by_account[account["Id"]] = contacts

    # ------------------------------------------------------------ drivers
    def random_drivers(self, account: dict, owner: dict) -> Drivers:
        rng = self.rng
        seg = account["Segment__c"]
        expansion = account["Type"] == "Customer" and rng.random() < 0.55
        product = rng.choices(list(PRODUCTS), weights=[0.5, 0.25, 0.25])[0]
        low, high = SEGMENTS[seg]["amount"]
        amount = int(round(rng.uniform(low, high) * PRODUCTS[product] / 500) * 500)
        discount = 0 if rng.random() < 0.3 else int(min(40, max(3, rng.gauss(14, 7))))
        return Drivers(
            account_id=account["Id"], owner_id=owner["Id"], segment=seg, industry=account["Industry"],
            product=product, deal_type="Expansion" if expansion else "New Business", amount=amount,
            exec_engaged=rng.random() < (0.6 if expansion else 0.45),
            champion=rng.random() < 0.55,
            competitor=rng.choice(COMPETITORS) if rng.random() < 0.4 else None,
            discount=discount, pushes=min(5, self.poisson(0.9)),
            activity_level=round(min(1.8, max(0.3, rng.lognormvariate(0, 0.35))), 2),
            severe_cases=min(3, self.poisson(0.5)) if expansion else 0,
            lead_source="Customer Referral" if expansion and rng.random() < 0.5 else rng.choice(LEAD_SOURCES),
        )

    def scenario_drivers(self, spec: dict) -> Drivers:
        account = self.make_account(spec["account"], spec["industry"], segment=spec["segment"],
                                    customer=spec["deal_type"] == "Expansion")
        return Drivers(
            account_id=account["Id"], owner_id=self.users[spec["owner"]]["Id"], segment=spec["segment"],
            industry=spec["industry"], product=spec["product"], deal_type=spec["deal_type"], amount=spec["amount"],
            exec_engaged=spec["exec_engaged"], champion=spec["champion"],
            competitor=COMPETITORS[len(spec["key"]) % len(COMPETITORS)] if spec["competitor"] else None,
            discount=spec["discount"], pushes=spec["pushes"], activity_level=spec["activity_level"],
            severe_cases=spec["severe_cases"], lead_source="Outbound",
            stage_index=OPEN_STAGES.index(spec["stage"]), forecast=spec["forecast"], scenario=spec["key"],
            max_notes=spec.get("max_notes"), injection=spec.get("injection", False),
        )

    # ------------------------------------------------------------ one deal
    def build_deal(self, d: Drivers, *, closed: bool) -> dict:
        rng = self.rng
        d.win_probability = round(sigmoid(rule_logit(self.rule, d) + rng.gauss(0, self.rule["noise_sd"])), 4)
        planned = rng.randint(*SEGMENTS[d.segment]["cycle"])
        push_days = [rng.randint(14, 40) for _ in range(d.pushes)]

        if closed:
            d.won = rng.random() < d.win_probability
            if not d.won:
                d.stage_index = rng.choices(range(5), weights=[0.15, 0.25, 0.25, 0.2, 0.15])[0]
            else:
                d.stage_index = 4
            if d.stage_index < PROPOSAL_INDEX:
                d.discount = 0  # never reached a proposal, so no discount was ever recorded
            end = self.day_between(HISTORY_START, HISTORY_END)
            created = end - timedelta(days=planned + sum(push_days))
            initial_close = created + timedelta(days=planned)
        else:
            current_close = self.day_between(SNAPSHOT_DATE + timedelta(days=7), QUARTER_END)
            initial_close = current_close - timedelta(days=sum(push_days))
            created = initial_close - timedelta(days=planned)
            latest_created = SNAPSHOT_DATE - timedelta(days=rng.randint(21, 45))
            if created > latest_created:
                created = latest_created
            if (initial_close - created).days < 20:
                initial_close = created + timedelta(days=20)
                current_close = initial_close + timedelta(days=sum(push_days))
            end = SNAPSHOT_DATE
            if d.stage_index < PROPOSAL_INDEX:
                d.discount = 0

        # Close-date slips: each happens before the close date it replaces.
        pushes, close = [], initial_close
        horizon = end if closed else SNAPSHOT_DATE - timedelta(days=1)
        cursor = created + timedelta(days=max(5, int(0.3 * planned)))
        for days in push_days:
            latest = min(close - timedelta(days=1), horizon)
            when = self.day_between(min(cursor, latest), latest)
            close = close + timedelta(days=days)
            pushes.append((when, close))
            cursor = when + timedelta(days=1)
        final_close = close if not closed else end

        # Stage changes.
        stage_dates = [created]
        last_change = (end - timedelta(days=rng.randint(3, 20))) if not closed else end - timedelta(days=rng.randint(2, 10))
        last_change = max(last_change, created + timedelta(days=d.stage_index))
        for k in range(1, d.stage_index + 1):
            frac = k / (d.stage_index + (1 if closed else 0))
            proposed = created + timedelta(days=int((last_change - created).days * frac * rng.uniform(0.85, 1.0)))
            stage_dates.append(max(proposed, stage_dates[-1] + timedelta(days=1)))

        account = next(a for a in self.accounts if a["Id"] == d.account_id)
        opp_id = self.ids.new("006")
        stage_now = (("Closed Won" if d.won else "Closed Lost") if closed else OPEN_STAGES[d.stage_index])
        opp = self.ds.add("Opportunity", {
            "Id": opp_id, "AccountId": d.account_id, "OwnerId": d.owner_id,
            "Name": f"{account['Name']} - {d.product} {'Expansion' if d.deal_type == 'Expansion' else 'Platform'}",
            "Amount": d.amount, "StageName": stage_now, "Probability": STAGE_PROBABILITY[stage_now],
            "ForecastCategoryName": ("Closed" if d.won else "Omitted") if closed else d.forecast,
            "CloseDate": final_close.isoformat(), "CreatedDate": created.isoformat(),
            "Type": d.deal_type, "LeadSource": d.lead_source, "Product_Line__c": d.product,
            "Discount_Pct__c": d.discount, "Competitor__c": d.competitor,
            "NextStep": None if closed else NEXT_STEP[stage_now], "IsClosed": closed, "IsWon": bool(d.won),
        })

        # OpportunityHistory: creation, stage changes, slips, closure.
        events = [(stage_dates[0], "stage", 0)] + [(dt, "stage", k) for k, dt in enumerate(stage_dates) if k > 0]
        events += [(when, "push", new_close) for when, new_close in pushes]
        events += [(when, "forecast", category) for when, category in self.forecast_changes(d, closed, stage_dates, end)]
        order = {"stage": 0, "push": 1, "forecast": 2}
        events.sort(key=lambda e: (e[0], order[e[1]]))
        stage, close, forecast = 0, initial_close, "Pipeline"
        for when, kind, value in events:
            if kind == "stage":
                stage = value
            elif kind == "push":
                close = value
            else:
                forecast = value
            self.history_row(opp_id, when, OPEN_STAGES[stage], d.amount, close, forecast)
        if closed:
            self.history_row(opp_id, end, stage_now, d.amount, end, "Closed" if d.won else "Omitted")

        # OpportunityFieldHistory: discount (set at proposal) and competitor (first seen).
        if d.discount and d.stage_index >= PROPOSAL_INDEX:
            self.ds.add("OpportunityFieldHistory", {
                "Id": self.ids.new("017"), "OpportunityId": opp_id, "Field": "Discount_Pct__c",
                "OldValue": 0, "NewValue": d.discount, "CreatedDate": stage_dates[PROPOSAL_INDEX].isoformat(),
            })
        competitor_from = None
        if d.competitor:
            competitor_from = created + timedelta(days=int((end - created).days * rng.uniform(0.1, 0.6)))
            self.ds.add("OpportunityFieldHistory", {
                "Id": self.ids.new("017"), "OpportunityId": opp_id, "Field": "Competitor__c",
                "OldValue": None, "NewValue": d.competitor, "CreatedDate": competitor_from.isoformat(),
            })

        # Contact roles.
        contacts = self.contacts_by_account[d.account_id]
        execs = [c for c in contacts if c["Seniority__c"] in EXECUTIVE_LEVELS]
        others = [c for c in contacts if c["Seniority__c"] not in EXECUTIVE_LEVELS]
        span = max(1, (end - created).days)
        exec_from = created + timedelta(days=int(span * rng.uniform(0.2, 0.5)))
        roles = [("Technical Evaluator", rng.choice(others), created + timedelta(days=int(span * 0.05)))]
        champion_contact = None
        if d.champion:
            champion_contact = rng.choice(others)
            roles.append(("Champion", champion_contact, created + timedelta(days=int(span * rng.uniform(0.1, 0.4)))))
        if d.exec_engaged and rng.random() < 0.9:
            roles.append(("Economic Buyer", execs[0], exec_from))
        elif not d.exec_engaged and rng.random() < 0.25:
            roles.append(("Economic Buyer", execs[0], created + timedelta(days=int(span * rng.uniform(0.3, 0.8)))))
        if rng.random() < 0.5:
            roles.append(("Influencer", rng.choice(contacts), created + timedelta(days=int(span * rng.uniform(0.1, 0.7)))))
        for role, contact, when in roles:
            self.ds.add("OpportunityContactRole", {
                "Id": self.ids.new("00K"), "OpportunityId": opp_id, "ContactId": contact["Id"],
                "Role": role, "IsPrimary": role == "Champion", "CreatedDate": min(when, end).isoformat(),
            })

        # Severe support cases on the account during the deal.
        severe = []
        for _ in range(d.severe_cases):
            opened = self.day_between(created, max(created, end - timedelta(days=5)))
            closed_on = opened + timedelta(days=rng.randint(10, 45))
            case = self.ds.add("Case", {
                "Id": self.ids.new("500"), "AccountId": d.account_id, "CaseNumber": f"{len(self.ds.objects.get('Case', [])) + 10001}",
                "Priority": rng.choice(["Critical", "High"]), "Subject": rng.choice(
                    ["Dashboard refresh failures", "SSO login errors", "Slow queries on finance model", "Data sync delays"]),
                "CreatedDate": opened.isoformat(),
                "ClosedDate": closed_on.isoformat() if closed_on <= SNAPSHOT_DATE else None,
                "Status": "Closed" if closed_on <= SNAPSHOT_DATE else "Open",
            })
            severe.append(case)

        self.activities(d, opp, closed, created, end, exec_from, execs[0], others, champion_contact,
                        pushes, competitor_from, stage_dates, severe)

        self.ds.truth.append({
            "OpportunityId": opp_id, "scenario": d.scenario, "closed": closed, "won": d.won,
            "win_probability": d.win_probability, "exec_engaged": d.exec_engaged, "champion": d.champion,
            "competitor": d.competitor, "discount": d.discount, "pushes": d.pushes,
            "activity_level": d.activity_level, "severe_cases": d.severe_cases, "deal_type": d.deal_type,
            "segment": d.segment, "stage_index": d.stage_index,
        })
        return opp

    def history_row(self, opp_id: str, when: date, stage: str, amount: int, close: date, forecast: str) -> None:
        self.ds.add("OpportunityHistory", {
            "Id": self.ids.new("008"), "OpportunityId": opp_id, "CreatedDate": when.isoformat(),
            "StageName": stage, "Amount": amount, "CloseDate": close.isoformat(),
            "Probability": STAGE_PROBABILITY[stage], "ForecastCategory": forecast,
        })

    def forecast_changes(self, d: Drivers, closed: bool, stage_dates: list[date], end: date) -> list[tuple[date, str]]:
        """When the rep moved the forecast category (Salesforce logs these in OpportunityHistory)."""
        changes = []
        def after(k: int) -> date:
            return min(stage_dates[k] + timedelta(days=self.rng.randint(1, 4)), end - timedelta(days=1))
        if closed:
            if d.stage_index >= PROPOSAL_INDEX:
                changes.append((after(PROPOSAL_INDEX), "Best Case"))
            if d.stage_index == 4 and (d.won or self.rng.random() < 0.5):
                changes.append((after(4), "Commit"))
        elif d.forecast in ("Best Case", "Commit"):
            last = len(stage_dates) - 1
            if d.forecast == "Commit" and last > PROPOSAL_INDEX:
                changes.append((after(PROPOSAL_INDEX), "Best Case"))
            changes.append((after(last), d.forecast))
        return changes

    # ------------------------------------------------------------ activities and notes
    def activities(self, d: Drivers, opp: dict, closed: bool, created: date, end: date, exec_from: date,
                   exec_contact: dict, others: list[dict], champion: dict | None, pushes: list,
                   competitor_from: date | None, stage_dates: list[date], severe: list[dict]) -> None:
        rng = self.rng
        items: list[tuple[date, str, dict | None, str | None]] = []  # (date, type, contact, forced topic)
        week = created
        while week < end:
            for _ in range(self.poisson(0.95 * d.activity_level)):
                when = week + timedelta(days=rng.randint(0, 6))
                if when < end:
                    items.append((when, rng.choices(["Call", "Email", "Meeting"], weights=[0.35, 0.45, 0.2])[0], None, None))
            week += timedelta(days=7)
        if d.exec_engaged:
            when = exec_from
            while when < end:
                items.append((when, "Meeting", exec_contact, "exec_meeting"))
                when += timedelta(days=rng.randint(24, 38))
        if not closed:
            for when, _ in pushes:  # each slip is mentioned in the next note
                items.append((when, "Call", None, "close_push"))
            if d.injection:
                items.append((created + timedelta(days=int((end - created).days * 0.7)), "Email", None, "injection"))
        items.sort(key=lambda item: (item[0], item[3] or ""))
        if not closed and d.max_notes is not None:
            items = items[: d.max_notes]

        push_iter = iter(new_close for _, new_close in pushes)
        # How far through the deal each note falls: towards the close date (open) or the close (closed).
        span = max(1, (date.fromisoformat(opp["CloseDate"]) - created).days)
        for when, kind, contact, forced in items:
            contact = contact or rng.choice(others)
            obj = "Event" if kind == "Meeting" else "Task"
            record = {
                "Id": self.ids.new("00U" if obj == "Event" else "00T"), "WhatId": opp["Id"], "WhoId": contact["Id"],
                "OwnerId": d.owner_id, "ActivityDate": when.isoformat(), "Type": kind,
                "Subject": {"Call": "Call", "Email": "Email", "Meeting": "Meeting"}[kind],
            }
            if not closed:
                topic, text = self.note(d, when, contact, champion, exec_contact, forced, push_iter,
                                        competitor_from, stage_dates, severe, (when - created).days / span, kind)
                record["Description"] = text
                record["Author_Role__c"] = notes_mod.AUTHOR_ROLE.get(topic, "Account Executive")
                self.ds.note_topics.append({"ActivityId": record["Id"], "OpportunityId": opp["Id"], "topic": topic})
                if topic == "injection":
                    self.ds.traps.setdefault("injection", {}).update({"OpportunityId": opp["Id"], "ActivityId": record["Id"]})
            self.ds.add(obj, record)

    def note(self, d: Drivers, when: date, contact: dict, champion: dict | None, exec_contact: dict, forced: str | None,
             push_iter, competitor_from: date | None, stage_dates: list[date], severe: list[dict],
             fraction: float, kind: str) -> tuple[str, str]:
        rng = self.rng
        used = self.used_templates.setdefault(d.account_id + d.product, set())  # per deal
        open_case = next((c for c in severe if date.fromisoformat(c["CreatedDate"]) <= when
                          and (c["ClosedDate"] is None or date.fromisoformat(c["ClosedDate"]) > when)), None)
        ctx = {
            "contact": f"{contact['FirstName']} {contact['LastName']}", "contact_title": contact["Title"],
            "exec_name": f"{exec_contact['FirstName']} {exec_contact['LastName']}", "exec_title": exec_contact["Title"],
            "champion": f"{champion['FirstName']} {champion['LastName']}" if champion else "",
            "competitor": d.competitor or "", "discount": d.discount, "product": d.product, "new_close": "",
            "severity": "", "case_number": "",
        }
        if forced == "injection":
            return "injection", notes_mod.INJECTION_TEXT.format(**ctx)
        if forced == "exec_meeting":
            return "exec_meeting", notes_mod.render("exec_meeting", ctx, rng, used)
        if forced == "close_push":
            ctx["new_close"] = next(push_iter).strftime("%B %-d")
            return "close_push", notes_mod.render("close_push", ctx, rng, used)

        reached_proposal = d.stage_index >= PROPOSAL_INDEX and when >= stage_dates[PROPOSAL_INDEX]
        options = [(notes_mod.phase_topic(fraction, rng), 3.0)]
        if not d.exec_engaged:
            options.append(("exec_gap", 1.2))
        options.append(("champion_positive", 1.0) if champion else ("champion_gap", 0.8))
        if d.competitor and competitor_from and when >= competitor_from:
            options.append(("competitor", 1.0))
        if d.discount and reached_proposal:
            options.append(("discount_ask", 1.0))
        if reached_proposal:
            options.append(("pricing", 0.6))
        if d.activity_level < 0.75 and kind == "Email":
            options.append(("no_response", 1.5))
        if open_case:
            options.append(("support_issue", 1.5))
            ctx.update(severity="Sev-1" if open_case["Priority"] == "Critical" else "Sev-2",
                       case_number=open_case["CaseNumber"])
        topic = rng.choices([t for t, _ in options], weights=[w for _, w in options])[0]
        return topic, notes_mod.render(topic, ctx, rng, used)

    # ------------------------------------------------------------ whole dataset
    def generate(self) -> Dataset:
        self.make_users()
        reps = [u for u in self.users.values() if not u["IsManager__c"]]
        self.make_accounts()

        # Open pipeline: scripted scenarios first, then random deals on ~40 accounts.
        for spec in self.scenarios:
            opp = self.build_deal(self.scenario_drivers(spec), closed=False)
            self.ds.traps.setdefault("scenarios", {})[spec["key"]] = opp["Id"]
        open_accounts = self.rng.sample(self.accounts[: self.n_accounts - len(self.scenarios)],
                                        self.n_open_accounts - len(self.scenarios))
        stage_weights = [0.05, 0.15, 0.25, 0.3, 0.25]
        queue = list(open_accounts)  # every chosen account gets at least one open deal
        while len(self.ds.objects["Opportunity"]) < self.n_open:
            account = queue.pop() if queue else self.rng.choice(open_accounts)
            d = self.random_drivers(account, self.rng.choice(reps))
            d.stage_index = self.rng.choices(range(5), weights=stage_weights)[0]
            d.forecast = self.forecast_for(d.stage_index)
            self.build_deal(d, closed=False)

        for _ in range(self.n_closed):
            self.build_deal(self.random_drivers(self.rng.choice(self.accounts), self.rng.choice(reps)), closed=True)

        self.background_cases()
        self.resolve_traps()
        return self.ds

    def forecast_for(self, stage_index: int) -> str:
        """Reps' forecast calls follow the stage, not the evidence, which is what DealPulse flags."""
        if stage_index >= PROPOSAL_INDEX:
            return self.rng.choices(["Commit", "Best Case", "Pipeline"], weights=[0.55, 0.35, 0.10])[0]
        if stage_index == 2:
            return self.rng.choices(["Best Case", "Pipeline"], weights=[0.4, 0.6])[0]
        return "Pipeline"

    def background_cases(self) -> None:
        """Low-priority cases so severe cases aren't the only ones (about 300 cases in total)."""
        customers = [a for a in self.accounts if a["Type"] == "Customer"]
        target = max(30, int(300 * self.n_accounts / 400))
        while len(self.ds.objects.get("Case", [])) < target:
            account = self.rng.choice(customers)
            opened = self.day_between(HISTORY_START, SNAPSHOT_DATE - timedelta(days=1))
            closed_on = opened + timedelta(days=self.rng.randint(1, 20))
            self.ds.add("Case", {
                "Id": self.ids.new("500"), "AccountId": account["Id"],
                "CaseNumber": f"{len(self.ds.objects['Case']) + 10001}",
                "Priority": self.rng.choice(["Medium", "Low"]),
                "Subject": self.rng.choice(["How-to question", "Feature request", "Report formatting", "License change"]),
                "CreatedDate": opened.isoformat(),
                "ClosedDate": closed_on.isoformat() if closed_on <= SNAPSHOT_DATE else None,
                "Status": "Closed" if closed_on <= SNAPSHOT_DATE else "Open",
            })

    def resolve_traps(self) -> None:
        sc = self.ds.traps.get("scenarios", {})
        opps = {o["Id"]: o for o in self.ds.objects["Opportunity"]}
        self.ds.traps.update({
            "discount_35": sc.get("S3_discount_35"),
            "thin_notes": sc.get("S4_thin_notes"),
            "lookalike": {
                "approved": {"OpportunityId": sc.get("S6a_lookalike_northbeam"),
                             "AccountId": opps.get(sc.get("S6a_lookalike_northbeam"), {}).get("AccountId")},
                "not_approved": {"OpportunityId": sc.get("S6b_lookalike_northbeam_group"),
                                 "AccountId": opps.get(sc.get("S6b_lookalike_northbeam_group"), {}).get("AccountId")},
            },
        })
