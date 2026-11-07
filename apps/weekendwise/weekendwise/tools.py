"""The planner's only tool: check_local_conditions (MVP-06).

Read-only and deterministic. It returns simulated weather from the bundled fixture files in
data/seed/local_conditions/ and nothing else: no network, no booking, no payment, no writes.
Arguments are validated against an allowlist of seeded (city, date) pairs; anything else fails closed.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "data" / "seed" / "local_conditions"
TOOL_NAME = "check_local_conditions"
ALLOWED_TOOLS = (TOOL_NAME,)
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

OK = "ok"
REJECTED_INVALID_ARGS = "rejected_invalid_args"
REJECTED_UNSEEDED_DATE = "rejected_unseeded_date"


@dataclass(frozen=True)
class ToolResult:
    tool: str
    status: str  # ok | rejected_invalid_args | rejected_unseeded_date
    args: dict
    conditions: dict | None = None
    message: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def _city_id(city: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", city.strip().lower()).strip("-")


class ConditionsTool:
    """Allowlisted fixture lookup. `fixtures` maps '<cityId>__<date>' -> conditions dict."""

    def __init__(self, fixtures: dict[str, dict] | None = None, supported_city_ids: tuple[str, ...] = ()):
        self.fixtures = fixtures if fixtures is not None else load_fixtures()
        self.supported = set(supported_city_ids) or {k.split("__")[0] for k in self.fixtures}

    def seeded_dates(self, city_id: str) -> list[str]:
        return sorted(k.split("__")[1] for k in self.fixtures if k.startswith(f"{city_id}__"))

    def __call__(self, city: object, demo_date: object) -> ToolResult:
        args = {"city": city, "demo_date": demo_date}
        if not isinstance(city, str) or not isinstance(demo_date, str) or not city.strip():
            return ToolResult(TOOL_NAME, REJECTED_INVALID_ARGS, args, message="city and demo_date must be non-empty strings.")
        if len(city) > 60 or not _DATE.match(demo_date):
            return ToolResult(TOOL_NAME, REJECTED_INVALID_ARGS, args, message="demo_date must be YYYY-MM-DD.")
        cid = _city_id(city)
        if cid not in self.supported:
            return ToolResult(TOOL_NAME, REJECTED_INVALID_ARGS, args, message=f"'{city}' isn't a supported city.")
        record = self.fixtures.get(f"{cid}__{demo_date}")
        if record is None:
            return ToolResult(
                TOOL_NAME, REJECTED_UNSEEDED_DATE, args,
                message=f"No simulated conditions for {city} on {demo_date}. Seeded dates: {', '.join(self.seeded_dates(cid)) or 'none'}.",
            )
        keep = ("cityId", "city", "demoDate", "dayOfWeek", "condition", "icon", "tempHighF", "tempLowF",
                "precipitationChancePct", "windMph", "indoorRecommended", "summary", "simulated", "disclaimer")
        return ToolResult(TOOL_NAME, OK, args, conditions={k: record[k] for k in keep if k in record})


def load_fixtures(directory: Path = FIXTURE_DIR) -> dict[str, dict]:
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted(directory.glob("*.json"))}
