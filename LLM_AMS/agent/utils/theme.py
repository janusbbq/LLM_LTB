"""Central UI theme — single source of truth for colors / symbols.

All "green" in the project resolves to RGB(51, 118, 31) — the CURENT brand
green. Edit ``BRAND_GREEN`` here to recolor the whole CLI.
"""

from rich.style import Style
from rich.theme import Theme


BRAND_GREEN = "rgb(51,118,31)"
ACCENT_BLUE = "rgb(58,134,255)"
MUTED       = "grey50"
WARN        = "yellow"
ERROR       = "red"

# Symbols (kept ASCII-friendly so they render in any terminal)
SYM_PROMPT  = "❯"
SYM_CHOICE  = "[?]"
SYM_INFO    = "[i]"
SYM_OK      = "[✓]"
SYM_FAIL    = "[✗]"
SYM_WAIT    = "…"


# rich Theme used by Console — names map to inline tags like [brand], [choice]
THEME = Theme({
    "brand":      Style(color=BRAND_GREEN, bold=True),
    "brand_dim":  Style(color=BRAND_GREEN),
    "accent":     Style(color=ACCENT_BLUE, bold=True),
    "muted":      Style(color=MUTED),
    "ok":         Style(color=BRAND_GREEN, bold=True),
    "fail":       Style(color=ERROR, bold=True),
    "warn":       Style(color=WARN),
    "prompt":     Style(color=BRAND_GREEN, bold=True),
    "choice":     Style(color=ACCENT_BLUE, bold=True),
    "default":    Style(color=BRAND_GREEN, italic=True),
    "kbd":        Style(color="white", bgcolor="grey23"),
    "value":      Style(color="white", bold=True),
    "label":      Style(color=MUTED),
})
