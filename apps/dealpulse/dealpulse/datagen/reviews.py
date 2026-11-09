"""Anonymised win/loss reviews written from closed deals' hidden drivers.

Reviews are shared guidance (no account or opportunity IDs, no company names), so the brief can
cite them for any deal without leaking one customer's details into another's.
"""
from __future__ import annotations

import random
from datetime import date


def quarter(d: date) -> str:
    return f"Q{(d.month - 1) // 3 + 1} {d.year}"


def review_markdown(number: int, truth: dict, opp: dict, account: dict, stage_reached: str) -> str:
    won = truth["won"]
    closed = date.fromisoformat(opp["CloseDate"])
    days = (closed - date.fromisoformat(opp["CreatedDate"])).days
    who = f"{truth['segment']} {account['Industry'].lower()} {'customer' if truth['deal_type'] == 'Expansion' else 'prospect'}"
    lines: list[str] = []
    lessons: list[str] = []
    if won:
        if truth["exec_engaged"]:
            lines.append("An executive sponsor joined early; after the executive alignment call the budget was approved quickly.")
            lessons.append("Playbook 2 (executive alignment)")
        if truth["champion"]:
            lines.append("Our champion presented the business case internally and kept the mutual action plan on track.")
            lessons.append("Playbook 3 (champion)")
        if truth["competitor"]:
            lines.append(f"{truth['competitor']} was also evaluated; we won on governance and lineage rather than price.")
            lessons.append("Playbook 5 (competitive deals)")
        if truth["pushes"] == 0:
            lines.append("The close date never moved: security and legal reviews started early.")
            lessons.append("Playbook 7 (security and legal)")
        if not lines:
            lines.append("Steady engagement and a clear compelling event carried the deal despite limited executive access.")
    else:
        if not truth["exec_engaged"]:
            lines.append("We never met the economic buyer; every meeting was with the analytics team, and finance decided without us.")
            lessons.append("Playbook 2 (executive alignment)")
        if not truth["champion"]:
            lines.append("No one inside the customer owned the decision; the evaluation team stayed lukewarm.")
            lessons.append("Playbook 3 (champion)")
        if truth["competitor"]:
            lines.append(f"{truth['competitor']} won after procurement turned the decision into a price comparison.")
            lessons.append("Playbook 5 (competitive deals)")
        if truth["pushes"] >= 2:
            lines.append(f"The close date slipped {truth['pushes']} times without a matching change in the action plan.")
            lessons.append("Playbook 4 (mutual action plan)")
        if truth["activity_level"] < 0.7:
            lines.append("The customer went quiet for several weeks before the decision; we kept sending check-in emails.")
            lessons.append("Playbook 6 (stalled deals)")
        if truth["severe_cases"]:
            lines.append("An open severe support case froze the expansion conversation and was never resolved in time.")
            lessons.append("Playbook 8 (expansion with support issues)")
        if truth["discount"] > 20:
            lines.append(f"A late {truth['discount']}% discount didn't change the outcome.")
            lessons.append("Pricing policy 1 (discount approval)")
        if not lines:
            lines.append("The customer chose to delay the project to next year after a budget review.")
    title = f"{'Win' if won else 'Loss'} review {number:02d} — {who}, {opp['Product_Line__c']} ({quarter(closed)})"
    outcome = (f"Won after {days} days." if won else f"Lost at {stage_reached} after {days} days.")
    body = [
        f"# {title}", "",
        "*Altura Analytics win/loss review · anonymised · fictional, for the DealPulse demo*", "",
        f"**Outcome:** {outcome} First-year value about ${round(opp['Amount'], -3):,.0f}.", "",
        "**What happened**", "",
        *[f"- {line}" for line in lines], "",
        f"**Lesson:** see {', '.join(dict.fromkeys(lessons)) or 'Playbook 1 (qualification checklist)'}.", "",
    ]
    return "\n".join(body)


def pick_reviews(ds_truth: list[dict], opps: dict, accounts: dict, history: dict, rng: random.Random,
                 per_outcome: int = 15) -> list[tuple[str, str]]:
    """Choose closed deals with a clear story and return (filename, markdown)."""
    from .vocab import OPEN_STAGES
    closed = [t for t in ds_truth if t["closed"]]
    won = [t for t in closed if t["won"]]
    lost = [t for t in closed if not t["won"]]
    chosen = rng.sample(won, min(per_outcome, len(won))) + rng.sample(lost, min(per_outcome, len(lost)))
    out = []
    for n, truth in enumerate(sorted(chosen, key=lambda t: t["OpportunityId"]), start=1):
        opp = opps[truth["OpportunityId"]]
        stage_reached = OPEN_STAGES[truth["stage_index"]]
        name = f"{'win' if truth['won'] else 'loss'}-review-{n:02d}.md"
        out.append((name, review_markdown(n, truth, opp, accounts[opp["AccountId"]], stage_reached)))
    return out
