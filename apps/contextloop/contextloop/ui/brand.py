"""The ContextLoop brand: one palette, the mark, and a small set of line icons for HTML badges and cards.

Palette: bright but soft hues on a deep navy ink, chosen to stay readable when screen-shared and in both light and dark themes.
"""
from __future__ import annotations

# ---- palette -----------------------------------------------------------------------------------------------------------
INDIGO = "#4B5BDC"      # primary: actions, links, active navigation
INDIGO_SOFT = "#ECEEFD"
LAGOON = "#13B3A4"      # secondary: data, flow, success-adjacent highlights
LAGOON_SOFT = "#E3F7F4"
CORAL = "#FF7A5C"       # accent: the data point in the mark, dbt in diagrams
CORAL_SOFT = "#FFEFEA"
AMBER = "#E8A100"       # warnings (stale data)
AMBER_SOFT = "#FFF5DC"
MINT = "#1FAE7A"        # pass, correct, current
MINT_SOFT = "#E2F6EE"
ROSE = "#E5484D"        # fail, wrong
ROSE_SOFT = "#FDECEC"
INK = "#18203A"         # text
SLATE = "#5B6478"       # secondary text
MIST = "#F5F7FC"        # panels and sidebar
LINE = "#E3E7F0"        # borders

# ---- the mark (favicon and logo) ---------------------------------------------------------------------------------------
MARK_SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="64" height="64">
  <defs>
    <linearGradient id="cl-grad" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="{INDIGO}"/><stop offset="1" stop-color="{LAGOON}"/>
    </linearGradient>
  </defs>
  <rect width="64" height="64" rx="15" fill="url(#cl-grad)"/>
  <path d="M44.1 23.2 A15 15 0 1 0 44.1 40.8" fill="none" stroke="#FFFFFF" stroke-width="6.2" stroke-linecap="round"/>
  <circle cx="46.2" cy="32" r="4.6" fill="{CORAL}"/>
</svg>"""

LOGO_SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 262 64" width="262" height="64">
  <defs>
    <linearGradient id="cl-grad-l" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="{INDIGO}"/><stop offset="1" stop-color="{LAGOON}"/>
    </linearGradient>
  </defs>
  <rect x="2" y="6" width="52" height="52" rx="12.5" fill="url(#cl-grad-l)"/>
  <path d="M38.2 21.4 A12.2 12.2 0 1 0 38.2 42.6" fill="none" stroke="#FFFFFF" stroke-width="5" stroke-linecap="round"/>
  <circle cx="39.9" cy="32" r="3.8" fill="{CORAL}"/>
  <text x="68" y="42" font-family="Inter, -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif" font-size="30"
        font-weight="700" letter-spacing="-0.5"><tspan fill="{INK}">Context</tspan><tspan fill="{INDIGO}">Loop</tspan></text>
</svg>"""

# ---- line icons (24 x 24, stroke-based, drawn for ContextLoop) ---------------------------------------------------------
_PATHS = {
    "check": '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    "close": '<path d="M6.5 6.5l11 11M17.5 6.5l-11 11"/>',
    "warning": '<path d="M12 4l9 16H3z"/><path d="M12 10v4.5"/><circle cx="12" cy="17.4" r=".6" fill="currentColor"/>',
    "play": '<path d="M8 5.5v13l10.5-6.5z"/>',
    "pending": '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
    "info": '<circle cx="12" cy="12" r="8.5"/><path d="M12 11v5.5"/><circle cx="12" cy="7.8" r=".6" fill="currentColor"/>',
    "record": '<circle cx="12" cy="12" r="8.5"/><path d="M10 8.8v6.4l5.2-3.2z" fill="currentColor"/>',
    "bolt": '<path d="M13 3L5 13.5h6L10 21l8.5-10.5h-6z"/>',
}


def icon(name: str, size: int = 14, color: str = "currentColor") -> str:
    """An inline SVG icon for use inside HTML (badges, cards)."""
    return (f'<svg class="cl-ic" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2.2" '
            f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{_PATHS[name]}</svg>')


# Material Symbols names (shipped with Streamlit) for pages and buttons
PAGE_ICONS = {
    "home": ":material/factory:", "act1": ":material/report:", "act2": ":material/sync_alt:", "act3": ":material/verified:",
    "act4": ":material/hub:", "act5": ":material/send:", "compare": ":material/compare:", "scorecard": ":material/fact_check:",
    "architecture": ":material/schema:",
}
