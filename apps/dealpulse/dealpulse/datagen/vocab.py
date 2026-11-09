"""Fixed vocabularies and constants for the synthetic CRM. All names are invented."""
from __future__ import annotations

from datetime import date

VENDOR = "Altura Analytics"
SNAPSHOT_DATE = date(2026, 11, 2)            # "today" in the data (a Monday); fixed for reproducibility
QUARTER_START = date(2026, 10, 1)            # current quarter: Q4 2026
QUARTER_END = date(2026, 12, 31)
HISTORY_START = date(2024, 10, 1)            # 8 closed quarters: Q4 2024 .. Q3 2026
HISTORY_END = date(2026, 9, 30)

# Salesforce's default sales process (open stages, in order) and default probabilities.
OPEN_STAGES = ["Prospecting", "Qualification", "Needs Analysis", "Proposal/Price Quote", "Negotiation/Review"]
STAGE_PROBABILITY = {
    "Prospecting": 10, "Qualification": 20, "Needs Analysis": 40,
    "Proposal/Price Quote": 60, "Negotiation/Review": 75, "Closed Won": 100, "Closed Lost": 0,
}
PROPOSAL_INDEX = OPEN_STAGES.index("Proposal/Price Quote")

SEGMENTS = {  # employees range, amount range (USD), planned sales cycle (days)
    "SMB": {"employees": (50, 400), "amount": (18_000, 60_000), "cycle": (30, 60)},
    "Mid-Market": {"employees": (400, 3_000), "amount": (60_000, 180_000), "cycle": (50, 100)},
    "Enterprise": {"employees": (3_000, 40_000), "amount": (150_000, 450_000), "cycle": (80, 150)},
}
PRODUCTS = {"Core": 1.0, "Governance add-on": 0.55, "AI add-on": 0.75}  # relative price
INDUSTRIES = ["Logistics", "Healthcare", "Retail", "Manufacturing", "Financial Services", "Energy", "Media", "Public Sector"]
LEAD_SOURCES = ["Web", "Partner", "Outbound", "Event", "Customer Referral"]
COMPETITORS = ["Quantrix Data", "Lumora Analytics", "Stackwell", "Brightgrid BI"]

TEAMS = {
    "West": {"manager": "Priya Raman", "reps": ["Marcus Bell", "Elena Ortiz", "Sam Whitaker"]},
    "East": {"manager": "Daniel Okafor", "reps": ["Grace Lin", "Tomás Rivera", "Aisha Karim"]},
}

# Account names are built from invented syllables to avoid real company names.
NAME_HEADS = ["Bel", "Cor", "Dal", "Fen", "Gal", "Hal", "Kel", "Lor", "Mar", "Nor", "Ost", "Pel", "Quin", "Ros",
              "Sel", "Tal", "Ver", "Wyn", "Ash", "Bram", "Cal", "Dun", "Elm", "Har", "Ivo", "Kip", "Lun", "Mor"]
NAME_TAILS = ["vale", "wick", "mere", "stead", "holt", "gate", "brook", "ley", "crest", "ridge", "haven", "field"]
ACCOUNT_SUFFIXES = {
    "Logistics": ["Freight", "Logistics", "Transit", "Shipping Co."],
    "Healthcare": ["Health Partners", "Medical Group", "Care Network", "Clinics"],
    "Retail": ["Retail Group", "Outfitters", "Markets", "Home Goods"],
    "Manufacturing": ["Manufacturing", "Industries", "Fabrication", "Components"],
    "Financial Services": ["Credit Union", "Capital", "Insurance", "Bancorp"],
    "Energy": ["Energy Cooperative", "Power", "Renewables", "Utilities"],
    "Media": ["Media", "Studios", "Publishing", "Broadcasting"],
    "Public Sector": ["County Services", "Transit Authority", "Water District", "City Services"],
}

FIRST_NAMES = [
    "Avery", "Jordan", "Riley", "Morgan", "Casey", "Taylor", "Quinn", "Rowan", "Harper", "Emerson", "Parker",
    "Sasha", "Devon", "Reese", "Hayden", "Kendall", "Logan", "Jamie", "Noor", "Mateo", "Ines", "Kenji", "Leila",
    "Omar", "Priya", "Tobias", "Yara", "Wen", "Felix", "Amara", "Nikhil", "Sofia", "Lucas", "Mina", "Andre",
]
LAST_NAMES = [
    "Ashworth", "Brennan", "Castillo", "Delacroix", "Eriksen", "Fairbanks", "Galloway", "Hollis", "Ivers",
    "Jansen", "Kowalski", "Lindqvist", "Mercer", "Nakamura", "Okonkwo", "Pemberton", "Quintero", "Rosales",
    "Sundberg", "Thackeray", "Underhill", "Vasquez", "Whitlock", "Yamamoto", "Zielinski", "Abernathy", "Bose",
]

# Customer-side titles by seniority. Executives (C-level, VP) count for executive engagement.
TITLES = {
    "C-level": ["Chief Financial Officer", "Chief Information Officer", "Chief Operating Officer", "Chief Data Officer"],
    "VP": ["VP of Finance", "VP of Operations", "VP of Data & Analytics", "VP of IT"],
    "Director": ["Director of Analytics", "Director of IT", "Director of Finance Systems", "Director of Operations"],
    "Manager": ["Analytics Manager", "Data Platform Manager", "BI Manager", "Procurement Manager"],
    "Analyst": ["Senior Data Analyst", "Data Engineer", "Financial Analyst", "Solutions Architect"],
}
EXECUTIVE_LEVELS = {"C-level", "VP"}

CONTACT_ROLES = ["Economic Buyer", "Champion", "Technical Evaluator", "Influencer", "Decision Maker"]


def employees_segment(employees: int) -> str:
    for name, spec in SEGMENTS.items():
        low, high = spec["employees"]
        if low <= employees < high:
            return name
    return "Enterprise"
