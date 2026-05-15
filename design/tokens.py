"""Design tokens ported from the Claude Design handoff.

Canonical source: `_design_handoff_temp/project/styles.css` (`:root` block).
CSS variable names are translated to Python identifiers by replacing `-` with
`_`. Numeric prefixes (e.g. `--r-2xl`) are spelled out (`xxl`) since Python
identifiers cannot start with a digit.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Color:
    # Surfaces
    bg: str = "#000000"
    surface_1: str = "#0B0B10"  # window outer (CSS --surf-0)
    surface_2: str = "#14141C"  # window inner (CSS --surf-1)
    surface_3: str = "#1A1A24"  # card / input  (CSS --surf-2)
    surface_4: str = "#22222E"  # card hover    (CSS --surf-3)
    surface_5: str = "#2A2A38"  # divider strong (CSS --surf-4)

    # Lines
    line: str = "rgba(255,255,255,0.06)"
    line_strong: str = "rgba(255,255,255,0.10)"
    line_3: str = "rgba(255,255,255,0.16)"
    line_soft: str = "rgba(255,255,255,0.04)"

    # Text
    text_1: str = "#F4F4F8"
    text_2: str = "#9C9CA8"
    text_3: str = "#66666F"
    text_4: str = "#44444C"
    text_mute: str = "#2E2E36"

    # Violet accent
    violet: str = "#8B7FFF"
    violet_2: str = "#6E63E6"  # gradient endpoint
    violet_soft: str = "rgba(139,127,255,0.14)"
    violet_line: str = "rgba(139,127,255,0.45)"
    violet_glow: str = "rgba(139,127,255,0.35)"

    # Mint accent
    mint: str = "#5EE0B8"
    mint_soft: str = "rgba(94,224,184,0.14)"
    mint_line: str = "rgba(94,224,184,0.35)"
    mint_glow: str = "rgba(94,224,184,0.28)"

    # Amber
    amber: str = "#F5B847"
    amber_soft: str = "rgba(245,184,71,0.12)"

    # Danger / Coral (handoff renamed danger -> coral; both names exposed)
    danger: str = "#FF6B7A"
    danger_soft: str = "rgba(255,107,122,0.20)"
    coral: str = "#FF6B7A"
    coral_2: str = "#FF8593"
    coral_soft: str = "rgba(255,107,122,0.20)"
    coral_line: str = "rgba(255,107,122,0.55)"
    coral_glow: str = "rgba(255,107,122,0.40)"

    # URL accent
    url_blue: str = "#82B0FF"


@dataclass(frozen=True)
class Radius:
    xs: int = 5
    sm: int = 7
    md: int = 10
    lg: int = 14
    xl: int = 18
    xxl: int = 22  # CSS `--r-2xl`; Python identifiers can't lead with a digit.


@dataclass(frozen=True)
class Font:
    sans: str = '"Geist", "Segoe UI", system-ui, -apple-system, sans-serif'
    mono: str = '"Geist Mono", "Cascadia Mono", "JetBrains Mono", Consolas, monospace'

    # Sizes (px)
    size_xs: int = 11
    size_sm: int = 12
    size_md: int = 13
    size_lg: int = 16
    size_xl: int = 18
    size_timer: int = 64

    # Weights
    w_regular: int = 400
    w_medium: int = 500
    w_semibold: int = 600
    w_bold: int = 700


@dataclass(frozen=True)
class Motion:
    fast_ms: int = 120
    base_ms: int = 180
    slow_ms: int = 260
    pulse_ms: int = 1400


@dataclass(frozen=True)
class Spacing:
    xs: int = 4
    sm: int = 8
    md: int = 12
    lg: int = 16
    xl: int = 24


EASE: str = "cubic-bezier(0.2, 0.7, 0.3, 1)"

COLOR = Color()
RADIUS = Radius()
FONT = Font()
MOTION = Motion()
SPACING = Spacing()
