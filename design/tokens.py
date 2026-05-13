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
    bg: str = "#0A0B0F"
    surface_1: str = "#14151B"
    surface_2: str = "#1B1D26"
    surface_3: str = "#23262F"
    surface_4: str = "#2A2D38"

    # Lines
    line: str = "rgba(255,255,255,0.06)"
    line_strong: str = "rgba(255,255,255,0.10)"
    line_soft: str = "rgba(255,255,255,0.04)"

    # Text
    text_1: str = "#EEEFF2"
    text_2: str = "#9B9EA9"
    text_3: str = "#6A6D78"
    text_4: str = "#4A4D58"

    # Violet accent
    violet: str = "#8B7FFF"
    violet_soft: str = "rgba(139,127,255,0.14)"
    violet_line: str = "rgba(139,127,255,0.40)"
    violet_glow: str = "rgba(139,127,255,0.30)"

    # Mint accent
    mint: str = "#5EE0B8"
    mint_soft: str = "rgba(94,224,184,0.12)"
    mint_line: str = "rgba(94,224,184,0.35)"
    mint_glow: str = "rgba(94,224,184,0.28)"

    # Amber
    amber: str = "#F5B847"
    amber_soft: str = "rgba(245,184,71,0.12)"

    # Danger
    danger: str = "#FF6B7A"
    danger_soft: str = "rgba(255,107,122,0.12)"

    # URL accent
    url_blue: str = "#82B0FF"


@dataclass(frozen=True)
class Radius:
    sm: int = 6
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
    size_timer: int = 44

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
