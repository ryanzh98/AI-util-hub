"""QSS stylesheets for the Claude Design dark/violet system.

Selector convention: dynamic-property `class` matching the CSS class name,
selected via `QWidget[class~="<name>"]`. Multi-class selectors stack the
attribute filters (e.g. `.tile.ai` -> `QWidget[class~="tile"][class~="ai"]`).
Set `widget.setProperty("class", "tile ai")` in Python to apply.

Where a widget is a singleton (whole window, footer, etc.) we use
`#objectName` selectors instead.

CSS features that have no QSS analogue are dropped silently. See the
spec/plan for the full mapping; notable omissions include `box-shadow`
(handled at runtime via QGraphicsDropShadowEffect), `backdrop-filter`
(substituted with higher-alpha solids), `transition`/`@keyframes`
(handled in Python via QPropertyAnimation), and `text-wrap: balance`.

Token mapping (CSS handoff -> Python tokens):
  --surf-0 -> COLOR.surface_1   (#0B0B10)
  --surf-1 -> COLOR.surface_2   (#14141C)
  --surf-2 -> COLOR.surface_3   (#1A1A24)
  --surf-3 -> COLOR.surface_4   (#22222E)
  --surf-4 -> COLOR.surface_5   (#2A2A38)
  --line   -> COLOR.line        (0.06)
  --line-2 -> COLOR.line_strong (0.10)
  --line-3 -> COLOR.line_3      (0.16)
  --line-soft -> COLOR.line_soft (0.04)

This stylesheet covers BOTH the current pre-redesign widgets (object names
like #popupCard, dynamic classes like `tile`, `mgr-row`, `rec-btn`) AND
the Wave-3 redesign classes (`win`, `tile-grid`, `rec-badge`, `ai-prompt`,
`adv-input`, ...). Selectors for both worlds coexist so windows render
correctly across the migration.
"""

from .tokens import COLOR, FONT, RADIUS


# ---------------------------------------------------------------------------
# Shared chrome: scrollbars, base font/color reset, buttons, kbd chips.
# ---------------------------------------------------------------------------

def shared_qss() -> str:
    return f"""
    /* base reset */
    QWidget {{
        background: transparent;
        color: {COLOR.text_1};
        font-family: {FONT.sans};
        font-size: {FONT.size_md}px;
        outline: 0;
    }}
    QToolTip {{
        background: {COLOR.surface_3};
        color: {COLOR.text_1};
        border: 1px solid {COLOR.line_strong};
        border-radius: {RADIUS.sm}px;
        padding: 4px 8px;
    }}
    QMenu {{
        background: {COLOR.surface_1};
        color: {COLOR.text_1};
        border: 1px solid {COLOR.line};
        border-radius: {RADIUS.md}px;
        padding: 4px;
    }}
    QMenu::item {{
        padding: 6px 12px;
        border-radius: {RADIUS.sm}px;
    }}
    QMenu::item:selected {{
        background: {COLOR.surface_3};
    }}
    QMenu::separator {{
        height: 1px;
        background: {COLOR.line};
        margin: 4px 0;
    }}

    /* scrollbars - thin, surface-3 colored */
    QScrollBar:vertical {{
        background: transparent;
        width: 8px;
        margin: 0;
    }}
    QScrollBar::handle:vertical {{
        background: {COLOR.surface_4};
        border-radius: 4px;
        min-height: 24px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {COLOR.surface_5};
    }}
    QScrollBar::add-line:vertical,
    QScrollBar::sub-line:vertical {{
        background: transparent;
        height: 0;
        border: 0;
    }}
    QScrollBar::add-page:vertical,
    QScrollBar::sub-page:vertical {{
        background: transparent;
    }}
    QScrollBar:horizontal {{
        background: transparent;
        height: 8px;
        margin: 0;
    }}
    QScrollBar::handle:horizontal {{
        background: {COLOR.surface_4};
        border-radius: 4px;
        min-width: 24px;
    }}
    QScrollBar::handle:horizontal:hover {{
        background: {COLOR.surface_5};
    }}
    QScrollBar::add-line:horizontal,
    QScrollBar::sub-line:horizontal {{
        background: transparent;
        width: 0;
        border: 0;
    }}

    /* ---------------------------------------------------------------- */
    /* Generic .btn — neutral pill button (Wave-3 style)                */
    /* ---------------------------------------------------------------- */
    QPushButton[class~="btn"] {{
        background: {COLOR.surface_3};
        color: {COLOR.text_1};
        border: 1px solid {COLOR.line_strong};
        border-radius: 9px;
        padding: 9px 16px;
        font-size: 13px;
        font-weight: {FONT.w_medium};
    }}
    QPushButton[class~="btn"]:hover {{
        background: {COLOR.surface_4};
        border-color: {COLOR.line_3};
    }}
    QPushButton[class~="btn"]:pressed {{
        background: {COLOR.surface_4};
    }}
    QPushButton[class~="btn"]:disabled,
    QPushButton[class~="btn"][class~="disabled"] {{
        color: {COLOR.text_4};
        background: {COLOR.surface_2};
        border-color: {COLOR.line};
    }}

    QPushButton[class~="btn"][class~="ghost"] {{
        background: transparent;
        border-color: transparent;
        color: {COLOR.text_2};
    }}
    QPushButton[class~="btn"][class~="ghost"]:hover {{
        background: rgba(255,255,255,0.04);
        border-color: transparent;
        color: {COLOR.text_1};
    }}

    QPushButton[class~="btn"][class~="primary"] {{
        background: {COLOR.violet};
        color: #0C0D15;
        border: 1px solid {COLOR.violet};
        font-weight: {FONT.w_semibold};
    }}
    QPushButton[class~="btn"][class~="primary"]:hover {{
        background: #9B90FF;
        border-color: #9B90FF;
    }}
    QPushButton[class~="btn"][class~="primary"]:pressed {{
        background: #7C6FFF;
    }}

    QPushButton[class~="btn"][class~="danger"] {{
        color: {COLOR.danger};
    }}
    QPushButton[class~="btn"][class~="danger"]:hover {{
        background: rgba(255,107,122,0.06);
        border-color: rgba(255,107,122,0.35);
        color: {COLOR.danger};
    }}

    /* coral filled action (e.g. recorder Stop) */
    QPushButton[class~="btn"][class~="coral"] {{
        background: qlineargradient(
            x1:0, y1:0, x2:0, y2:1,
            stop:0 {COLOR.coral},
            stop:1 #E85767
        );
        color: #1A0608;
        border: 1px solid rgba(255,255,255,0.08);
        font-weight: {FONT.w_semibold};
    }}
    QPushButton[class~="btn"][class~="coral"]:hover {{
        background: qlineargradient(
            x1:0, y1:0, x2:0, y2:1,
            stop:0 #FF8593,
            stop:1 #F26475
        );
    }}
    QPushButton[class~="btn"][class~="coral"]:pressed {{
        background: qlineargradient(
            x1:0, y1:0, x2:0, y2:1,
            stop:0 #E85767,
            stop:1 #C7475A
        );
    }}

    /* violet filled action */
    QPushButton[class~="btn"][class~="violet"] {{
        background: qlineargradient(
            x1:0, y1:0, x2:0, y2:1,
            stop:0 {COLOR.violet},
            stop:1 {COLOR.violet_2}
        );
        color: #14101A;
        border: 1px solid rgba(255,255,255,0.08);
        font-weight: {FONT.w_semibold};
    }}
    QPushButton[class~="btn"][class~="violet"]:hover {{
        background: qlineargradient(
            x1:0, y1:0, x2:0, y2:1,
            stop:0 #9B90FF,
            stop:1 #7B70F0
        );
    }}
    QPushButton[class~="btn"][class~="violet"]:pressed {{
        background: qlineargradient(
            x1:0, y1:0, x2:0, y2:1,
            stop:0 {COLOR.violet_2},
            stop:1 #5A4FCC
        );
    }}

    /* ---------------------------------------------------------------- */
    /* Text button (.btn-text) — fully chromeless                       */
    /* ---------------------------------------------------------------- */
    QPushButton[class~="btn-text"] {{
        background: transparent;
        border: 0;
        color: {COLOR.text_2};
        font-size: 12px;
        font-weight: {FONT.w_medium};
        padding: 6px 8px;
        border-radius: 6px;
    }}
    QPushButton[class~="btn-text"]:hover {{
        color: {COLOR.text_1};
        background: rgba(255,255,255,0.04);
    }}
    QPushButton[class~="btn-text"]:disabled,
    QPushButton[class~="btn-text"][class~="disabled"] {{
        color: {COLOR.text_4};
        background: transparent;
    }}

    /* ---------------------------------------------------------------- */
    /* Icon-only button (.icon-btn) — 26x26 square chip                 */
    /* ---------------------------------------------------------------- */
    QPushButton[class~="icon-btn"] {{
        background: transparent;
        border: 1px solid transparent;
        color: {COLOR.text_2};
        min-width: 26px;
        min-height: 26px;
        max-width: 26px;
        max-height: 26px;
        border-radius: 7px;
        padding: 0;
    }}
    QPushButton[class~="icon-btn"]:hover {{
        background: {COLOR.surface_3};
        color: {COLOR.text_1};
        border-color: {COLOR.line};
    }}
    QPushButton[class~="icon-btn"][class~="close"]:hover {{
        color: #FFB4BB;
        background: rgba(255,107,122,0.10);
        border-color: rgba(255,107,122,0.20);
    }}

    /* ---------------------------------------------------------------- */
    /* keyboard-cap chips (.kbd)                                        */
    /* ---------------------------------------------------------------- */
    QLabel[class~="kbd"], QWidget[class~="kbd"] {{
        font-family: {FONT.mono};
        font-size: 10px;
        font-weight: {FONT.w_medium};
        color: {COLOR.text_2};
        background: rgba(255,255,255,0.04);
        border: 1px solid {COLOR.line_strong};
        border-bottom: 2px solid {COLOR.line_strong};
        border-radius: 4px;
        padding: 1px 5px;
        min-width: 17px;
    }}
    QLabel[class~="kbd"][class~="sm"], QWidget[class~="kbd"][class~="sm"] {{
        font-size: 9px;
        padding: 1px 4px;
        min-width: 14px;
    }}
    QLabel[class~="kbd"][class~="lg"], QWidget[class~="kbd"][class~="lg"] {{
        font-size: 11px;
        padding: 3px 8px;
        min-width: 26px;
    }}

    /* ---------------------------------------------------------------- */
    /* Modal backdrop — backdrop-filter unavailable, use solid alpha    */
    /* ---------------------------------------------------------------- */
    QFrame#modalBack, QWidget#modalBack,
    QFrame[class~="modal-back"], QWidget[class~="modal-back"] {{
        background: rgba(2,3,6,0.7);
        border: 0;
    }}
    """


# ---------------------------------------------------------------------------
# Window chrome shared between launcher / recorder / yt / tts / manager
# (.win, .win-hd, .win-body, .win-ft)
# ---------------------------------------------------------------------------

def _window_chrome_qss() -> str:
    return f"""
    /* generic frameless window (.win) */
    QFrame[class~="win"], QWidget[class~="win"] {{
        background: {COLOR.surface_1};
        border: 1px solid {COLOR.line};
        border-radius: {RADIUS.xxl}px;
        color: {COLOR.text_1};
    }}
    QWidget[class~="win-hd"], QFrame[class~="win-hd"] {{
        background: transparent;
    }}
    QWidget[class~="win-hd"][class~="bordered"],
    QFrame[class~="win-hd"][class~="bordered"] {{
        border-bottom: 1px solid {COLOR.line_soft};
    }}
    QWidget[class~="win-body"], QFrame[class~="win-body"] {{
        background: transparent;
    }}
    QWidget[class~="win-ft"], QFrame[class~="win-ft"] {{
        background: rgba(0,0,0,0.15);
        border-top: 1px solid {COLOR.line_soft};
    }}
    QLabel[class~="win-ft-hint"] {{
        font-size: 11px;
        color: {COLOR.text_3};
    }}

    /* brand mark (gradient circle / square containing app icon) */
    QLabel[class~="brand-mark"], QFrame[class~="brand-mark"] {{
        background: qlineargradient(
            x1:0, y1:0, x2:0.6, y2:1,
            stop:0 {COLOR.violet},
            stop:1 {COLOR.violet_2}
        );
        border-radius: 13px;
        min-width: 26px;
        min-height: 26px;
        max-width: 26px;
        max-height: 26px;
        color: #FFFFFF;
    }}
    QLabel[class~="brand-mark"][class~="sm"],
    QFrame[class~="brand-mark"][class~="sm"] {{
        border-radius: 12px;
        min-width: 24px;
        min-height: 24px;
        max-width: 24px;
        max-height: 24px;
    }}
    QLabel[class~="brand-mark"][class~="square"],
    QFrame[class~="brand-mark"][class~="square"] {{
        border-radius: 8px;
    }}

    /* brand title row (.brand-title) */
    QLabel[class~="brand"], QLabel[class~="brand-title"] {{
        color: {COLOR.text_1};
        font-size: 13px;
        font-weight: {FONT.w_semibold};
    }}
    QLabel[class~="brand-title-sub"] {{
        color: {COLOR.text_3};
        font-size: 12px;
        font-weight: {FONT.w_regular};
    }}
    QLabel[class~="brand-title-slash"] {{
        color: {COLOR.text_4};
        font-weight: {FONT.w_regular};
    }}
    QLabel[class~="brand-dot"] {{
        color: {COLOR.text_4};
        font-weight: {FONT.w_regular};
    }}
    QLabel[class~="brand-ctx"] {{
        color: {COLOR.text_2};
        font-weight: {FONT.w_medium};
    }}
    """


# ---------------------------------------------------------------------------
# Popup launcher window
# ---------------------------------------------------------------------------

def popup_qss() -> str:
    return _window_chrome_qss() + f"""
    /* legacy outer card */
    QWidget#popupCard, QFrame#popupCard {{
        background: {COLOR.surface_1};
        border-radius: {RADIUS.xxl}px;
        color: {COLOR.text_1};
    }}
    /* radial glow overlay - applied to a child QFrame#popupGlow */
    QFrame#popupGlow {{
        background: qradialgradient(
            cx:0.5, cy:-0.2, fx:0.5, fy:0.5, radius:1.0,
            stop:0 rgba(139,127,255,0.06),
            stop:0.55 transparent,
            stop:1 transparent
        );
        border: 0;
        border-radius: {RADIUS.xxl}px;
    }}

    /* legacy header / body / footer surfaces */
    QWidget#popupHeader {{
        background: transparent;
        border-bottom: 1px solid {COLOR.line_soft};
    }}
    QWidget#popupBody {{
        background: transparent;
    }}
    QWidget#popupFooter {{
        background: rgba(0,0,0,0.15);
        border-top: 1px solid {COLOR.line_soft};
    }}

    /* ---------------------------------------------------------------- */
    /* Search field (.search) — floating row above the body             */
    /* ---------------------------------------------------------------- */
    QWidget[class~="search-row"], QFrame[class~="search-row"] {{
        background: transparent;
    }}
    QLineEdit[class~="search"],
    QFrame[class~="search"], QWidget[class~="search"] {{
        background: {COLOR.surface_2};
        border: 1px solid {COLOR.line};
        border-radius: 9px;
        padding: 0 8px 0 36px;
        min-height: 36px;
        color: {COLOR.text_1};
        font-size: 12px;
        font-weight: {FONT.w_regular};
        selection-background-color: {COLOR.violet_soft};
        selection-color: {COLOR.text_1};
    }}
    QLineEdit[class~="search"]:focus,
    QFrame[class~="search"]:focus, QWidget[class~="search"]:focus {{
        border-color: {COLOR.violet_line};
    }}
    QLabel[class~="search-icon"] {{
        color: {COLOR.text_3};
    }}

    /* view toggle (grid / list) */
    QWidget[class~="view-toggle"], QFrame[class~="view-toggle"] {{
        background: transparent;
        border-left: 1px solid {COLOR.line};
    }}
    QPushButton[class~="view-toggle-btn"] {{
        background: transparent;
        border: 0;
        color: {COLOR.text_3};
        min-width: 22px;
        min-height: 22px;
        max-width: 22px;
        max-height: 22px;
        border-radius: 5px;
        padding: 0;
    }}
    QPushButton[class~="view-toggle-btn"]:hover {{
        color: {COLOR.text_1};
        background: rgba(255,255,255,0.04);
    }}
    QPushButton[class~="view-toggle-btn"][on="true"] {{
        color: {COLOR.violet};
        background: {COLOR.violet_soft};
    }}

    /* ---------------------------------------------------------------- */
    /* Section headers (.section / .section-hd)                          */
    /* ---------------------------------------------------------------- */
    QWidget[class~="section"], QFrame[class~="section"] {{
        background: transparent;
    }}
    QWidget[class~="section-hd"], QFrame[class~="section-hd"] {{
        background: transparent;
    }}
    QLabel[class~="section-hd-lbl"] {{
        font-family: {FONT.mono};
        font-size: 10px;
        font-weight: {FONT.w_semibold};
        color: {COLOR.text_2};
    }}
    QLabel[class~="section-hd-count"] {{
        font-family: {FONT.mono};
        font-size: 10px;
        color: {COLOR.text_4};
    }}
    QLabel[class~="section-empty"] {{
        font-size: 11px;
        color: {COLOR.text_3};
    }}
    QLabel[class~="chev"] {{
        color: {COLOR.text_3};
    }}
    QFrame[class~="rule"], QWidget[class~="rule"] {{
        background: {COLOR.line};
        max-height: 1px;
        min-height: 1px;
        border: 0;
    }}

    /* coloured dots (used in section headers + group labels) */
    QLabel[class~="dot"] {{
        background: {COLOR.violet};
        border-radius: 3px;
        min-width: 6px;
        min-height: 6px;
        max-width: 6px;
        max-height: 6px;
    }}
    QLabel[class~="dot"][class~="violet"] {{
        background: {COLOR.violet};
    }}
    QLabel[class~="dot"][class~="mint"] {{
        background: {COLOR.mint};
    }}
    QLabel[class~="ai-dot"] {{
        background: {COLOR.violet};
        border-radius: 3px;
        min-width: 6px;
        min-height: 6px;
        max-width: 6px;
        max-height: 6px;
    }}
    QLabel[class~="sn-dot"] {{
        background: {COLOR.mint};
        border-radius: 3px;
        min-width: 6px;
        min-height: 6px;
        max-width: 6px;
        max-height: 6px;
    }}
    QLabel[class~="url-dot"] {{
        background: {COLOR.url_blue};
        border-radius: 3px;
        min-width: 6px;
        min-height: 6px;
        max-width: 6px;
        max-height: 6px;
    }}

    /* ---------------------------------------------------------------- */
    /* Tile grid (.tile-grid / .tile)                                    */
    /* ---------------------------------------------------------------- */
    QWidget[class~="tile-grid"], QFrame[class~="tile-grid"] {{
        background: transparent;
    }}

    QWidget[class~="tile"], QPushButton[class~="tile"], QFrame[class~="tile"] {{
        background: {COLOR.surface_2};
        border: 1px solid {COLOR.line};
        border-radius: 10px;
        padding: 16px 12px 12px;
        min-height: 114px;
        color: {COLOR.text_1};
        text-align: left;
        font-size: 12px;
        font-weight: {FONT.w_medium};
    }}
    QWidget[class~="tile"]:hover,
    QPushButton[class~="tile"]:hover,
    QFrame[class~="tile"]:hover {{
        background: {COLOR.surface_3};
        border-color: {COLOR.line_strong};
    }}
    /* focused state — support BOTH legacy `focused="true"` AND new `is-focused` class */
    QWidget[class~="tile"][focused="true"],
    QPushButton[class~="tile"][focused="true"],
    QFrame[class~="tile"][focused="true"],
    QWidget[class~="tile"][class~="is-focused"],
    QPushButton[class~="tile"][class~="is-focused"],
    QFrame[class~="tile"][class~="is-focused"] {{
        background: {COLOR.surface_3};
        border-color: {COLOR.violet_line};
    }}

    /* tile variants (legacy `ai`/`snip`/`url` classes) */
    QWidget[class~="tile"][class~="ai"]:hover,
    QPushButton[class~="tile"][class~="ai"]:hover,
    QWidget[class~="tile"][class~="ai"][focused="true"],
    QPushButton[class~="tile"][class~="ai"][focused="true"],
    QWidget[class~="tile"][class~="ai"][class~="is-focused"],
    QPushButton[class~="tile"][class~="ai"][class~="is-focused"] {{
        border-color: {COLOR.violet_line};
    }}
    QWidget[class~="tile"][class~="snip"]:hover,
    QPushButton[class~="tile"][class~="snip"]:hover,
    QWidget[class~="tile"][class~="snip"][focused="true"],
    QPushButton[class~="tile"][class~="snip"][focused="true"],
    QWidget[class~="tile"][class~="snip"][class~="is-focused"],
    QPushButton[class~="tile"][class~="snip"][class~="is-focused"] {{
        border-color: {COLOR.mint_line};
    }}
    QWidget[class~="tile"][class~="url"]:hover,
    QPushButton[class~="tile"][class~="url"]:hover,
    QWidget[class~="tile"][class~="url"][focused="true"],
    QPushButton[class~="tile"][class~="url"][focused="true"],
    QWidget[class~="tile"][class~="url"][class~="is-focused"],
    QPushButton[class~="tile"][class~="url"][class~="is-focused"] {{
        border-color: rgba(120,170,255,0.35);
    }}

    /* tile running pulse */
    QWidget[class~="tile"][running="true"],
    QPushButton[class~="tile"][running="true"] {{
        border-color: {COLOR.violet_line};
    }}

    /* tile child labels */
    QLabel[class~="tile-name"] {{
        color: {COLOR.text_1};
        font-size: 12px;
        font-weight: {FONT.w_medium};
    }}
    QLabel[class~="tile-emoji"] {{
        font-size: 19px;
    }}
    QLabel[class~="tile-icon"] {{
        color: {COLOR.violet};
    }}
    QLabel[class~="tile-num"], QWidget[class~="tile-num"] {{
        font-family: {FONT.mono};
        font-size: 9px;
        font-weight: {FONT.w_medium};
        color: {COLOR.text_3};
        background: rgba(255,255,255,0.04);
        border: 1px solid {COLOR.line_strong};
        border-radius: 4px;
        padding: 1px 5px;
    }}
    QWidget[class~="tile"][class~="is-focused"] QLabel[class~="tile-num"],
    QWidget[class~="tile"][focused="true"] QLabel[class~="tile-num"] {{
        color: {COLOR.text_2};
        background: rgba(139,127,255,0.10);
        border-color: {COLOR.violet_line};
    }}
    QWidget[class~="tile-chord"], QFrame[class~="tile-chord"] {{
        background: transparent;
    }}

    /* legacy tile-kbd chip (sit at top-right of tiles) */
    QLabel[class~="tile-kbd"], QWidget[class~="tile-kbd"] {{
        font-family: {FONT.mono};
        font-size: 9px;
        font-weight: {FONT.w_semibold};
        color: {COLOR.text_4};
        background: rgba(255,255,255,0.03);
        border: 1px solid {COLOR.line_strong};
        border-radius: 4px;
        padding: 1px 4px;
        min-width: 16px;
    }}

    /* tile-type icon at bottom right (legacy) */
    QLabel[class~="tile-type"] {{
        color: {COLOR.text_3};
    }}
    QWidget[class~="tile"][class~="ai"] QLabel[class~="tile-type"] {{
        color: {COLOR.violet};
    }}
    QWidget[class~="tile"][class~="snip"] QLabel[class~="tile-type"] {{
        color: {COLOR.mint};
    }}
    QWidget[class~="tile"][class~="url"] QLabel[class~="tile-type"] {{
        color: {COLOR.url_blue};
    }}

    /* ---------------------------------------------------------------- */
    /* List view (.tile-list / .row)                                     */
    /* ---------------------------------------------------------------- */
    QWidget[class~="tile-list"], QFrame[class~="tile-list"] {{
        background: transparent;
    }}
    QWidget[class~="row"], QPushButton[class~="row"], QFrame[class~="row"] {{
        background: transparent;
        border: 1px solid transparent;
        border-radius: 8px;
        padding: 9px 12px;
        color: {COLOR.text_1};
        text-align: left;
        font-size: 12px;
    }}
    QWidget[class~="row"]:hover,
    QPushButton[class~="row"]:hover,
    QFrame[class~="row"]:hover {{
        background: {COLOR.surface_2};
    }}
    QWidget[class~="row"][class~="is-focused"],
    QPushButton[class~="row"][class~="is-focused"],
    QFrame[class~="row"][class~="is-focused"],
    QWidget[class~="row"][focused="true"],
    QPushButton[class~="row"][focused="true"],
    QFrame[class~="row"][focused="true"] {{
        background: rgba(139,127,255,0.06);
        border-color: {COLOR.violet_line};
    }}
    QLabel[class~="row-icon"] {{
        color: {COLOR.violet};
    }}
    QFrame[class~="row-divider"], QWidget[class~="row-divider"] {{
        background: {COLOR.line_strong};
        max-width: 1px;
        min-width: 1px;
        border: 0;
    }}
    QLabel[class~="row-name"] {{
        color: {COLOR.text_1};
        font-size: 12px;
        font-weight: {FONT.w_medium};
    }}
    QWidget[class~="row"][class~="is-focused"] QLabel[class~="row-name"],
    QWidget[class~="row"][focused="true"] QLabel[class~="row-name"] {{
        color: {COLOR.violet};
    }}
    QWidget[class~="row-chord"], QFrame[class~="row-chord"] {{
        background: transparent;
    }}

    /* ---------------------------------------------------------------- */
    /* Footer hint + manage button (legacy + new)                        */
    /* ---------------------------------------------------------------- */
    QLabel[class~="pop-ft-hint"] {{
        font-family: {FONT.sans};
        font-size: 11px;
        color: {COLOR.text_3};
    }}
    QPushButton[class~="manage"] {{
        background: transparent;
        border: 0;
        color: {COLOR.text_2};
        font-size: 12px;
        font-weight: {FONT.w_medium};
        padding: 6px 8px;
        border-radius: 6px;
    }}
    QPushButton[class~="manage"]:hover {{
        color: {COLOR.text_1};
        background: rgba(255,255,255,0.04);
    }}

    /* ---------------------------------------------------------------- */
    /* Empty state                                                        */
    /* ---------------------------------------------------------------- */
    QWidget#popupEmpty {{
        background: transparent;
    }}
    QLabel[class~="empty-glyph"] {{
        background: {COLOR.surface_2};
        border: 1px solid {COLOR.line_strong};
        border-radius: 16px;
        min-width: 56px;
        min-height: 56px;
        max-width: 56px;
        max-height: 56px;
        color: {COLOR.violet};
    }}
    QLabel[class~="empty-title"] {{
        font-size: 17px;
        font-weight: {FONT.w_semibold};
        color: {COLOR.text_1};
    }}
    QLabel[class~="empty-desc"] {{
        font-size: 13px;
        color: {COLOR.text_2};
    }}
    QPushButton[class~="cta"] {{
        background: {COLOR.violet};
        color: #0C0D15;
        font-weight: {FONT.w_semibold};
        font-size: 12px;
        border: 0;
        padding: 8px 14px;
        border-radius: 10px;
    }}
    QPushButton[class~="cta"]:hover {{
        background: #9B90FF;
    }}

    /* ---------------------------------------------------------------- */
    /* Toasts (.toast)                                                    */
    /* ---------------------------------------------------------------- */
    QWidget#toastStack {{
        background: transparent;
    }}
    QWidget[class~="toast"], QFrame[class~="toast"] {{
        background: rgba(20,21,27,0.97);
        border: 1px solid {COLOR.line_strong};
        border-radius: 12px;
        padding: 10px 12px;
        color: {COLOR.text_1};
    }}
    QLabel[class~="toast-title"] {{
        font-size: 12px;
        font-weight: {FONT.w_semibold};
        color: {COLOR.text_1};
    }}
    QLabel[class~="toast-desc"] {{
        font-size: 11px;
        color: {COLOR.text_2};
    }}
    QLabel[class~="toast-desc"][class~="mono"] {{
        font-family: {FONT.mono};
        font-size: 10px;
    }}
    QLabel[class~="toast-ic"] {{
        border-radius: 6px;
        min-width: 22px;
        min-height: 22px;
        max-width: 22px;
        max-height: 22px;
    }}
    QWidget[class~="toast"][class~="ok"] QLabel[class~="toast-ic"] {{
        background: {COLOR.mint_soft};
        color: {COLOR.mint};
    }}
    QWidget[class~="toast"][class~="run"] QLabel[class~="toast-ic"] {{
        background: {COLOR.violet_soft};
        color: {COLOR.violet};
    }}
    QWidget[class~="toast"][class~="warn"] QLabel[class~="toast-ic"] {{
        background: {COLOR.amber_soft};
        color: {COLOR.amber};
    }}
    QWidget[class~="toast"][class~="err"] QLabel[class~="toast-ic"] {{
        background: {COLOR.danger_soft};
        color: {COLOR.danger};
    }}
    """


# ---------------------------------------------------------------------------
# Manager window
# ---------------------------------------------------------------------------

def manager_qss() -> str:
    return f"""
    /* outer window (.mgr) — legacy + new */
    QWidget#managerCard, QFrame#managerCard,
    QWidget[class~="mgr"], QFrame[class~="mgr"] {{
        background: {COLOR.surface_1};
        border-radius: {RADIUS.xxl}px;
        color: {COLOR.text_1};
    }}

    /* titlebar (.mgr-titlebar) */
    QWidget#managerTitlebar {{
        background: rgba(0,0,0,0.15);
        border-bottom: 1px solid {COLOR.line_soft};
    }}
    QLabel[class~="mgr-title"] {{
        color: {COLOR.text_1};
        font-size: 12px;
        font-weight: {FONT.w_semibold};
    }}

    /* body (split rail + editor) */
    QWidget[class~="mgr-body"], QFrame[class~="mgr-body"] {{
        background: transparent;
    }}

    /* ---------------------------------------------------------------- */
    /* Left rail (.mgr-rail)                                              */
    /* ---------------------------------------------------------------- */
    QWidget#managerRail,
    QWidget[class~="mgr-rail"], QFrame[class~="mgr-rail"] {{
        background: rgba(0,0,0,0.18);
        border-right: 1px solid {COLOR.line_soft};
    }}
    QWidget#managerRailHead {{
        background: transparent;
        border-bottom: 1px solid {COLOR.line_soft};
    }}

    /* manager search */
    QLineEdit[class~="mgr-search"] {{
        background: {COLOR.surface_3};
        border: 1px solid {COLOR.line};
        border-radius: 8px;
        padding: 0 10px 0 30px;
        min-height: 32px;
        color: {COLOR.text_1};
        font-size: 12px;
    }}
    QLineEdit[class~="mgr-search"]:focus {{
        border-color: {COLOR.violet_line};
    }}

    /* tabs (.mgr-tabs / .mgr-tab) — legacy + new */
    QWidget#managerTabs,
    QWidget[class~="mgr-tabs"], QFrame[class~="mgr-tabs"] {{
        background: {COLOR.surface_2};
        border: 1px solid {COLOR.line};
        border-radius: 9px;
        padding: 3px;
    }}
    QPushButton[class~="mgr-tab"] {{
        background: transparent;
        color: {COLOR.text_3};
        border: 0;
        font-size: 12px;
        font-weight: {FONT.w_medium};
        padding: 6px 8px;
        border-radius: 6px;
    }}
    QPushButton[class~="mgr-tab"]:hover {{
        color: {COLOR.text_2};
    }}
    QPushButton[class~="mgr-tab"][on="true"] {{
        background: {COLOR.surface_4};
        color: {COLOR.text_1};
    }}

    /* list container */
    QWidget[class~="mgr-list"], QFrame[class~="mgr-list"] {{
        background: transparent;
    }}

    /* group label (.mgr-grp) */
    QLabel[class~="mgr-grp"], QWidget[class~="mgr-grp"], QFrame[class~="mgr-grp"] {{
        font-family: {FONT.mono};
        font-size: 10px;
        font-weight: {FONT.w_semibold};
        color: {COLOR.text_3};
        background: transparent;
    }}
    QPushButton[class~="mgr-add"] {{
        background: rgba(255,255,255,0.04);
        border: 1px solid {COLOR.line_strong};
        color: {COLOR.text_2};
        min-width: 18px;
        min-height: 18px;
        max-width: 18px;
        max-height: 18px;
        border-radius: 5px;
    }}
    QPushButton[class~="mgr-add"]:hover {{
        background: {COLOR.surface_3};
        color: {COLOR.text_1};
    }}

    /* ---------------------------------------------------------------- */
    /* List rows (.mgr-row)                                               */
    /* ---------------------------------------------------------------- */
    QWidget[class~="mgr-row"], QPushButton[class~="mgr-row"], QFrame[class~="mgr-row"] {{
        background: transparent;
        border: 1px solid transparent;
        border-radius: 8px;
        padding: 9px 10px;
        color: {COLOR.text_1};
        font-size: 12px;
        text-align: left;
    }}
    QWidget[class~="mgr-row"]:hover,
    QPushButton[class~="mgr-row"]:hover,
    QFrame[class~="mgr-row"]:hover {{
        background: rgba(255,255,255,0.03);
    }}
    QWidget[class~="mgr-row"][on="true"],
    QPushButton[class~="mgr-row"][on="true"],
    QFrame[class~="mgr-row"][on="true"] {{
        background: {COLOR.surface_3};
        border-color: {COLOR.violet_line};
    }}
    QLabel[class~="mgr-row-name"] {{
        color: {COLOR.text_1};
        font-size: 12px;
        font-weight: {FONT.w_medium};
    }}
    QLabel[class~="mgr-row-icon"] {{
        color: {COLOR.violet};
    }}
    QLabel[class~="mgr-row-num"], QWidget[class~="mgr-row-num"] {{
        font-family: {FONT.mono};
        font-size: 9px;
        color: {COLOR.text_3};
        background: rgba(255,255,255,0.04);
        border: 1px solid {COLOR.line};
        border-radius: 4px;
        padding: 1px 5px;
    }}
    QLabel[class~="mgr-row-spark"] {{
        color: {COLOR.violet};
    }}
    QLabel[class~="mgr-grip"] {{
        color: {COLOR.text_4};
        font-family: {FONT.mono};
        font-size: 9px;
    }}
    QLabel[class~="mgr-row-meta"] {{
        color: {COLOR.text_4};
    }}
    QWidget[class~="mgr-row"][on="true"] QLabel[class~="mgr-row-meta"] {{
        color: {COLOR.violet};
    }}

    /* ---------------------------------------------------------------- */
    /* Editor pane (.mgr-edit / .ed)                                      */
    /* ---------------------------------------------------------------- */
    QWidget#managerEdit,
    QWidget[class~="mgr-edit"], QFrame[class~="mgr-edit"] {{
        background: {COLOR.surface_1};
    }}
    QWidget#managerEditHead {{
        background: transparent;
        border-bottom: 1px solid {COLOR.line_soft};
    }}
    QWidget[class~="ed-body"], QFrame[class~="ed-body"] {{
        background: transparent;
    }}
    QWidget[class~="ed-explain"], QLabel[class~="ed-explain"] {{
        font-size: 13px;
        color: {COLOR.text_2};
    }}

    /* meta header (.ed-meta) — small icon + kind + h2 + p */
    QWidget[class~="ed-meta"], QFrame[class~="ed-meta"] {{
        background: transparent;
    }}
    QLabel[class~="ed-meta-ic"] {{
        background: {COLOR.surface_3};
        border: 1px solid {COLOR.line_strong};
        border-radius: 11px;
        min-width: 44px;
        min-height: 44px;
        max-width: 44px;
        max-height: 44px;
        color: {COLOR.violet};
    }}
    QLabel[class~="ed-meta-kind"] {{
        font-family: {FONT.mono};
        font-size: 10px;
        font-weight: {FONT.w_semibold};
        color: {COLOR.violet};
    }}
    QLabel[class~="ed-meta-h2"] {{
        font-size: 18px;
        font-weight: {FONT.w_semibold};
        color: {COLOR.text_1};
    }}
    QLabel[class~="ed-meta-p"] {{
        font-size: 13px;
        color: {COLOR.text_2};
    }}

    /* big emoji block (.ed-hd-emoji) — legacy */
    QLabel[class~="ed-hd-emoji"] {{
        background: {COLOR.surface_2};
        border: 1px solid {COLOR.line_strong};
        border-radius: 12px;
        min-width: 48px;
        min-height: 48px;
        max-width: 48px;
        max-height: 48px;
        font-size: 22px;
    }}
    QPushButton[class~="ed-emoji-edit"] {{
        font-family: {FONT.mono};
        font-size: 9px;
        color: {COLOR.text_2};
        background: {COLOR.surface_3};
        border: 1px solid {COLOR.line_strong};
        border-radius: 4px;
        padding: 2px 6px;
    }}
    QPushButton[class~="ed-emoji-edit"]:hover {{
        color: {COLOR.text_1};
    }}

    /* header kind label (.ed-hd-kind) — legacy */
    QLabel[class~="ed-hd-kind"] {{
        font-family: {FONT.mono};
        font-size: 10px;
        font-weight: {FONT.w_semibold};
        color: {COLOR.text_3};
    }}
    QLineEdit[class~="ed-hd-name"] {{
        background: transparent;
        border: 0;
        font-size: 18px;
        font-weight: {FONT.w_semibold};
        color: {COLOR.text_1};
        padding: 2px 0;
    }}
    QLabel[class~="ed-hd-sub"] {{
        font-size: 12px;
        color: {COLOR.text_2};
    }}

    /* fields (.ed-field) */
    QLabel[class~="ed-field-lbl"] {{
        font-family: {FONT.mono};
        font-size: 10px;
        font-weight: {FONT.w_semibold};
        color: {COLOR.text_3};
    }}
    QLabel[class~="ed-field-hint"] {{
        font-size: 12px;
        color: {COLOR.text_3};
    }}

    /* inputs (.ed-input / .ed-textarea) */
    QLineEdit[class~="ed-input"],
    QTextEdit[class~="ed-textarea"],
    QPlainTextEdit[class~="ed-textarea"],
    QComboBox[class~="ed-input"] {{
        background: {COLOR.surface_2};
        border: 1px solid {COLOR.line_strong};
        border-radius: 9px;
        padding: 10px 12px;
        color: {COLOR.text_1};
        font-size: 13px;
        selection-background-color: {COLOR.violet_soft};
        selection-color: {COLOR.text_1};
    }}
    QLineEdit[class~="ed-input"]:focus,
    QTextEdit[class~="ed-textarea"]:focus,
    QPlainTextEdit[class~="ed-textarea"]:focus,
    QComboBox[class~="ed-input"]:focus {{
        border-color: {COLOR.violet_line};
        background: {COLOR.surface_3};
    }}
    QLineEdit[class~="ed-input"][class~="mono"],
    QTextEdit[class~="ed-textarea"][class~="mono"],
    QPlainTextEdit[class~="ed-textarea"][class~="mono"] {{
        font-family: {FONT.mono};
        font-size: 12px;
    }}
    QComboBox[class~="ed-input"]::drop-down {{
        border: 0;
        width: 24px;
    }}
    QComboBox[class~="ed-input"] QAbstractItemView {{
        background: {COLOR.surface_2};
        color: {COLOR.text_1};
        border: 1px solid {COLOR.line_strong};
        border-radius: 8px;
        selection-background-color: {COLOR.surface_3};
        outline: 0;
    }}

    /* preview block (.ed-preview) */
    QWidget#editorPreview, QFrame[class~="ed-preview"], QWidget[class~="ed-preview"] {{
        background: rgba(0,0,0,0.18);
        border: 1px solid {COLOR.line};
        border-radius: 12px;
    }}
    QLabel[class~="ed-preview-lbl"] {{
        font-family: {FONT.mono};
        font-size: 10px;
        font-weight: {FONT.w_semibold};
        color: {COLOR.text_3};
    }}
    QLabel[class~="ed-preview-mute"] {{
        color: {COLOR.text_4};
        font-weight: {FONT.w_medium};
    }}
    QFrame[class~="ed-preview-cell"], QWidget[class~="ed-preview-cell"] {{
        background: {COLOR.surface_2};
        border: 1px solid {COLOR.line};
        border-radius: 9px;
        padding: 10px 12px;
    }}
    QLabel[class~="ed-preview-hdcell"] {{
        font-family: {FONT.mono};
        font-size: 9px;
        font-weight: {FONT.w_semibold};
        color: {COLOR.text_4};
    }}
    QLabel[class~="ed-preview-text"] {{
        font-size: 12px;
        color: {COLOR.text_1};
    }}
    QLabel[class~="ed-preview-arrow"] {{
        color: {COLOR.violet};
        font-size: 18px;
    }}
    QLabel[class~="ed-mono-block"],
    QTextEdit[class~="ed-mono-block"],
    QPlainTextEdit[class~="ed-mono-block"] {{
        font-family: {FONT.mono};
        font-size: 12px;
        color: {COLOR.text_1};
        background: {COLOR.surface_2};
        border: 1px solid {COLOR.line};
        border-radius: 9px;
        padding: 10px 12px;
    }}

    /* slider (.ed-slider) */
    QSlider[class~="ed-slider"]::groove:horizontal {{
        background: {COLOR.surface_4};
        height: 4px;
        border-radius: 2px;
    }}
    QSlider[class~="ed-slider"]::sub-page:horizontal {{
        background: {COLOR.violet};
        border-radius: 2px;
    }}
    QSlider[class~="ed-slider"]::handle:horizontal {{
        background: {COLOR.text_1};
        width: 14px;
        height: 14px;
        margin: -5px 0;
        border-radius: 7px;
    }}
    QSlider[class~="ed-slider"]::handle:horizontal:hover {{
        background: #FFFFFF;
    }}

    /* checkbox + radio (.ed-check / .ed-radio) */
    QCheckBox[class~="ed-check"], QRadioButton[class~="ed-radio"] {{
        color: {COLOR.text_1};
        font-size: 12px;
        spacing: 8px;
        padding: 6px 0;
        background: transparent;
    }}
    QCheckBox[class~="ed-check"]::indicator,
    QRadioButton[class~="ed-radio"]::indicator {{
        width: 14px;
        height: 14px;
        border: 1px solid {COLOR.line_strong};
        background: {COLOR.surface_2};
    }}
    QCheckBox[class~="ed-check"]::indicator {{
        border-radius: 4px;
    }}
    QRadioButton[class~="ed-radio"]::indicator {{
        border-radius: 7px;
    }}
    QCheckBox[class~="ed-check"]::indicator:checked,
    QRadioButton[class~="ed-radio"]::indicator:checked {{
        background: {COLOR.violet};
        border-color: {COLOR.violet};
    }}
    QCheckBox[class~="ed-check"]::indicator:hover,
    QRadioButton[class~="ed-radio"]::indicator:hover {{
        border-color: {COLOR.violet_line};
    }}

    /* segmented control (.ed-seg / .ed-seg-btn) */
    QWidget[class~="ed-seg"], QFrame[class~="ed-seg"] {{
        background: rgba(0,0,0,0.25);
        border-radius: 8px;
        padding: 3px;
    }}
    QPushButton[class~="ed-seg-btn"] {{
        background: transparent;
        color: {COLOR.text_2};
        border: 0;
        font-size: 12px;
        font-weight: {FONT.w_medium};
        padding: 6px 10px;
        border-radius: 6px;
    }}
    QPushButton[class~="ed-seg-btn"]:hover {{
        color: {COLOR.text_1};
    }}
    QPushButton[class~="ed-seg-btn"][on="true"] {{
        background: {COLOR.surface_2};
        color: {COLOR.text_1};
    }}

    /* editor footer (.ed-ft) */
    QWidget#editorFooter,
    QWidget[class~="ed-ft"], QFrame[class~="ed-ft"] {{
        background: rgba(0,0,0,0.15);
        border-top: 1px solid {COLOR.line_soft};
    }}
    QLabel[class~="ed-ft-lbl"] {{
        font-family: {FONT.mono};
        font-size: 10px;
        font-weight: {FONT.w_semibold};
        color: {COLOR.text_3};
    }}
    QLabel[class~="ed-ft-pos"] {{
        font-size: 11px;
        color: {COLOR.text_2};
    }}
    QLabel[class~="ed-ft-mute"] {{
        color: {COLOR.text_3};
    }}

    /* hotkey-row inside editor footer (.hotkey-row) */
    QWidget[class~="hotkey-row"], QFrame[class~="hotkey-row"] {{
        background: transparent;
    }}
    QLabel[class~="hotkey-row-lbl"] {{
        font-family: {FONT.mono};
        font-size: 12px;
        color: {COLOR.text_3};
    }}
    QPushButton[class~="hotkey-row-clear"] {{
        background: transparent;
        border: 0;
        color: {COLOR.text_3};
        font-size: 12px;
        padding: 4px 6px;
        border-radius: 6px;
    }}
    QPushButton[class~="hotkey-row-clear"]:hover {{
        color: {COLOR.text_2};
        background: rgba(255,255,255,0.03);
    }}

    /* ---------------------------------------------------------------- */
    /* AI Action editor (.ai-ed-hd / .ai-ed-cols / .ai-prompt / .ai-side) */
    /* ---------------------------------------------------------------- */
    QWidget[class~="ai-ed-hd"], QFrame[class~="ai-ed-hd"] {{
        background: transparent;
    }}
    QLabel[class~="ai-ed-hd-ic"] {{
        background: {COLOR.surface_3};
        border: 1px solid {COLOR.line_strong};
        border-radius: 13px;
        min-width: 56px;
        min-height: 56px;
        max-width: 56px;
        max-height: 56px;
        color: {COLOR.violet};
    }}
    QWidget[class~="ai-ed-hd-meta"], QFrame[class~="ai-ed-hd-meta"] {{
        background: transparent;
    }}
    QLabel[class~="ai-ed-hd-kind"] {{
        font-family: {FONT.mono};
        font-size: 10px;
        font-weight: {FONT.w_semibold};
        color: {COLOR.violet};
    }}
    QLabel[class~="ai-ed-hd-h2"] {{
        font-size: 22px;
        font-weight: {FONT.w_semibold};
        color: {COLOR.text_1};
    }}
    QLabel[class~="ai-ed-hd-p"] {{
        font-size: 13px;
        color: {COLOR.text_2};
    }}
    QWidget[class~="ai-ed-actions"], QFrame[class~="ai-ed-actions"] {{
        background: transparent;
    }}
    QPushButton[class~="ai-ed-action"] {{
        background: transparent;
        border: 0;
        color: {COLOR.text_2};
        font-size: 13px;
        font-weight: {FONT.w_medium};
        padding: 6px 8px;
        border-radius: 6px;
    }}
    QPushButton[class~="ai-ed-action"]:hover {{
        color: {COLOR.text_1};
        background: rgba(255,255,255,0.04);
    }}
    QPushButton[class~="ai-ed-action"][class~="danger"] {{
        color: {COLOR.coral};
    }}
    QPushButton[class~="ai-ed-action"][class~="danger"]:hover {{
        color: {COLOR.coral_2};
        background: rgba(255,107,122,0.08);
    }}

    QWidget[class~="ai-ed-cols"], QFrame[class~="ai-ed-cols"] {{
        background: transparent;
    }}

    /* prompt textarea */
    QTextEdit[class~="ai-prompt"], QPlainTextEdit[class~="ai-prompt"] {{
        background: {COLOR.surface_2};
        border: 1px solid {COLOR.line_strong};
        border-radius: 12px;
        padding: 16px 18px;
        color: {COLOR.text_1};
        font-family: {FONT.mono};
        font-size: 12px;
        min-height: 220px;
        selection-background-color: {COLOR.violet_soft};
        selection-color: {COLOR.text_1};
    }}
    QTextEdit[class~="ai-prompt"]:focus,
    QPlainTextEdit[class~="ai-prompt"]:focus {{
        border-color: {COLOR.violet_line};
    }}

    /* preview label / grid */
    QLabel[class~="preview-lbl"] {{
        font-family: {FONT.mono};
        font-size: 10px;
        font-weight: {FONT.w_semibold};
        color: {COLOR.text_3};
    }}
    QLabel[class~="preview-lbl-mute"] {{
        font-family: {FONT.sans};
        font-size: 11px;
        font-weight: {FONT.w_regular};
        color: {COLOR.text_3};
    }}
    QWidget[class~="preview-grid"], QFrame[class~="preview-grid"] {{
        background: transparent;
    }}
    QFrame[class~="preview-cell"], QWidget[class~="preview-cell"] {{
        background: {COLOR.surface_2};
        border: 1px solid {COLOR.line};
        border-radius: 10px;
        padding: 10px 12px;
        color: {COLOR.text_2};
        font-family: {FONT.mono};
        font-size: 11px;
    }}
    QLabel[class~="preview-cell-head"] {{
        font-family: {FONT.mono};
        font-size: 9px;
        font-weight: {FONT.w_semibold};
        color: {COLOR.text_4};
    }}

    /* AI side column (.ai-side / .select-field / .temp-row / .range / .behavior-check) */
    QWidget[class~="ai-side"], QFrame[class~="ai-side"] {{
        background: transparent;
    }}
    QFrame[class~="select-field"], QWidget[class~="select-field"],
    QComboBox[class~="select-field"] {{
        background: {COLOR.surface_2};
        border: 1px solid {COLOR.line_strong};
        border-radius: 10px;
        padding: 0 12px;
        min-height: 38px;
        color: {COLOR.text_1};
        font-size: 13px;
    }}
    QFrame[class~="select-field"]:hover, QWidget[class~="select-field"]:hover,
    QComboBox[class~="select-field"]:hover {{
        border-color: {COLOR.line_3};
    }}
    QComboBox[class~="select-field"]::drop-down {{
        border: 0;
        width: 24px;
    }}
    QComboBox[class~="select-field"] QAbstractItemView {{
        background: {COLOR.surface_2};
        color: {COLOR.text_1};
        border: 1px solid {COLOR.line_strong};
        border-radius: 8px;
        selection-background-color: {COLOR.surface_3};
        outline: 0;
    }}

    QWidget[class~="temp-row"], QFrame[class~="temp-row"] {{
        background: transparent;
    }}
    QLabel[class~="temp-row-lbl"] {{
        font-family: {FONT.mono};
        font-size: 10px;
        font-weight: {FONT.w_semibold};
        color: {COLOR.text_3};
    }}
    QLabel[class~="temp-row-val"] {{
        font-family: {FONT.mono};
        font-size: 10px;
        font-weight: {FONT.w_semibold};
        color: {COLOR.text_1};
    }}

    /* range slider (.range) */
    QSlider[class~="range"]::groove:horizontal {{
        background: {COLOR.surface_4};
        height: 4px;
        border-radius: 2px;
    }}
    QSlider[class~="range"]::sub-page:horizontal {{
        background: {COLOR.violet};
        border-radius: 2px;
    }}
    QSlider[class~="range"]::add-page:horizontal {{
        background: {COLOR.surface_4};
        border-radius: 2px;
    }}
    QSlider[class~="range"]::handle:horizontal {{
        background: #FFFFFF;
        border: 2px solid {COLOR.violet};
        width: 14px;
        height: 14px;
        margin: -5px 0;
        border-radius: 9px;
    }}
    QSlider[class~="range"]::handle:horizontal:hover {{
        background: #FFFFFF;
    }}
    QWidget[class~="range-marks"], QFrame[class~="range-marks"] {{
        background: transparent;
    }}
    QLabel[class~="range-marks"], QLabel[class~="range-mark"] {{
        font-family: {FONT.mono};
        font-size: 10px;
        color: {COLOR.text_4};
    }}

    /* behavior checkbox row (.behavior-check) */
    QCheckBox[class~="behavior-check"] {{
        color: {COLOR.text_1};
        font-size: 13px;
        spacing: 10px;
        padding: 4px 0;
        background: transparent;
    }}
    QCheckBox[class~="behavior-check"]::indicator {{
        width: 18px;
        height: 18px;
        border: 1px solid {COLOR.line_3};
        background: {COLOR.surface_3};
        border-radius: 5px;
    }}
    QCheckBox[class~="behavior-check"]::indicator:checked {{
        background: {COLOR.violet};
        border-color: {COLOR.violet};
        image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23191020' stroke-width='3.5' stroke-linecap='round' stroke-linejoin='round'><path d='M5 12l5 5L20 7'/></svg>");
    }}
    QCheckBox[class~="behavior-check"]::indicator:hover {{
        border-color: {COLOR.violet_line};
    }}

    /* ---------------------------------------------------------------- */
    /* Field row (.field-row / .field-input)                              */
    /* ---------------------------------------------------------------- */
    QWidget[class~="field-row"], QFrame[class~="field-row"] {{
        background: transparent;
    }}
    QLabel[class~="field-row-lbl"] {{
        font-size: 13px;
        color: {COLOR.text_2};
    }}
    QFrame[class~="field-input"], QWidget[class~="field-input"],
    QLineEdit[class~="field-input"] {{
        background: {COLOR.surface_2};
        border: 1px solid {COLOR.line_strong};
        border-radius: 10px;
        padding: 10px 14px;
        min-height: 38px;
        color: {COLOR.text_1};
        font-size: 13px;
        selection-background-color: {COLOR.violet_soft};
        selection-color: {COLOR.text_1};
    }}
    QFrame[class~="field-input"]:focus, QWidget[class~="field-input"]:focus,
    QLineEdit[class~="field-input"]:focus {{
        border-color: {COLOR.violet_line};
    }}
    QLabel[class~="field-input-caret"] {{
        color: {COLOR.text_3};
    }}

    /* ---------------------------------------------------------------- */
    /* Disclosure triangle button (.disclosure)                            */
    /* ---------------------------------------------------------------- */
    QPushButton[class~="disclosure"] {{
        background: transparent;
        border: 0;
        color: {COLOR.violet};
        font-size: 12px;
        font-weight: {FONT.w_medium};
        padding: 4px 4px;
        border-radius: 4px;
        text-align: left;
    }}
    QPushButton[class~="disclosure"]:hover {{
        color: #9B90FF;
    }}
    QLabel[class~="disclosure-tri"] {{
        color: {COLOR.violet};
    }}

    /* ---------------------------------------------------------------- */
    /* Advanced settings panel (.advanced / .adv-row / .adv-input)        */
    /* ---------------------------------------------------------------- */
    QWidget[class~="advanced"], QFrame[class~="advanced"] {{
        background: transparent;
    }}
    QWidget[class~="adv-row"], QFrame[class~="adv-row"] {{
        background: transparent;
    }}
    /* small ? help bubble */
    QPushButton[class~="adv-row-q"], QLabel[class~="adv-row-q"] {{
        background: {COLOR.surface_3};
        border: 1px solid {COLOR.line_strong};
        color: {COLOR.text_3};
        min-width: 18px;
        min-height: 18px;
        max-width: 18px;
        max-height: 18px;
        border-radius: 9px;
        font-family: {FONT.mono};
        font-size: 10px;
        font-weight: {FONT.w_semibold};
        padding: 0;
    }}
    QPushButton[class~="adv-row-q"]:hover {{
        color: {COLOR.text_1};
        border-color: {COLOR.line_3};
    }}
    QLabel[class~="adv-row-lbl"] {{
        font-size: 13px;
        color: {COLOR.text_2};
    }}

    /* the input chrome: container row + inner editor */
    QFrame[class~="adv-input"], QWidget[class~="adv-input"],
    QLineEdit[class~="adv-input"], QSpinBox[class~="adv-input"],
    QDoubleSpinBox[class~="adv-input"] {{
        background: {COLOR.surface_2};
        border: 1px solid {COLOR.line_strong};
        border-radius: 9px;
        padding: 0 4px 0 14px;
        min-height: 34px;
        color: {COLOR.text_1};
        font-size: 13px;
        selection-background-color: {COLOR.violet_soft};
        selection-color: {COLOR.text_1};
    }}
    QFrame[class~="adv-input"]:hover, QWidget[class~="adv-input"]:hover,
    QLineEdit[class~="adv-input"]:hover, QSpinBox[class~="adv-input"]:hover,
    QDoubleSpinBox[class~="adv-input"]:hover {{
        border-color: {COLOR.line_3};
    }}
    QFrame[class~="adv-input"]:focus, QWidget[class~="adv-input"]:focus,
    QLineEdit[class~="adv-input"]:focus, QSpinBox[class~="adv-input"]:focus,
    QDoubleSpinBox[class~="adv-input"]:focus {{
        border-color: {COLOR.violet_line};
    }}
    QLineEdit[class~="adv-input"][class~="mono"],
    QSpinBox[class~="adv-input"][class~="mono"],
    QDoubleSpinBox[class~="adv-input"][class~="mono"] {{
        font-family: {FONT.mono};
    }}

    /* spinner buttons inside the .adv-input row (Wave-3 widgets should
       set property "class"="adv-stepper-btn" on the inner up/down buttons) */
    QPushButton[class~="adv-stepper-btn"] {{
        background: rgba(255,255,255,0.04);
        border: 0;
        color: {COLOR.text_3};
        min-width: 18px;
        min-height: 12px;
        max-width: 18px;
        border-radius: 3px;
        padding: 0;
    }}
    QPushButton[class~="adv-stepper-btn"]:hover {{
        color: {COLOR.text_1};
        background: rgba(255,255,255,0.10);
    }}

    /* refresh icon inside an .adv-input (set "class"="adv-input-refresh") */
    QPushButton[class~="adv-input-refresh"] {{
        background: {COLOR.surface_3};
        border: 1px solid {COLOR.line_strong};
        color: {COLOR.text_2};
        min-width: 28px;
        min-height: 26px;
        max-width: 28px;
        max-height: 26px;
        border-radius: 6px;
        padding: 0;
    }}
    QPushButton[class~="adv-input-refresh"]:hover {{
        color: {COLOR.text_1};
        background: {COLOR.surface_4};
    }}

    /* Reset-defaults pill */
    QPushButton[class~="adv-reset"] {{
        background: transparent;
        border: 1px solid {COLOR.line_strong};
        color: {COLOR.text_2};
        font-size: 12px;
        padding: 6px 12px;
        border-radius: 7px;
    }}
    QPushButton[class~="adv-reset"]:hover {{
        color: {COLOR.text_1};
        border-color: {COLOR.line_3};
        background: {COLOR.surface_3};
    }}
    """


# ---------------------------------------------------------------------------
# Recorder window
# ---------------------------------------------------------------------------

def recorder_qss() -> str:
    return f"""
    /* outer window (.rec) — legacy + new */
    QWidget#recorderCard, QFrame#recorderCard {{
        background: {COLOR.surface_1};
        border-radius: {RADIUS.xxl}px;
        color: {COLOR.text_1};
    }}
    /* danger-tinted glow overlay - child QFrame#recorderGlow */
    QFrame#recorderGlow {{
        background: qradialgradient(
            cx:0.5, cy:-0.1, fx:0.5, fy:0.5, radius:1.0,
            stop:0 rgba(255,107,122,0.08),
            stop:0.55 transparent,
            stop:1 transparent
        );
        border: 0;
        border-radius: {RADIUS.xxl}px;
    }}

    /* legacy header / body / footer surfaces */
    QWidget#recorderHead {{
        background: transparent;
    }}
    QWidget#recorderBody {{
        background: transparent;
    }}
    QWidget#recorderFooter {{
        background: rgba(0,0,0,0.18);
        border-top: 1px solid {COLOR.line_soft};
    }}
    QWidget#recorderWarning {{
        background: rgba(245,184,71,0.08);
        border: 1px solid rgba(245,184,71,0.25);
        border-radius: 8px;
        color: {COLOR.amber};
    }}
    QWidget#recorderVoiceRow {{
        background: transparent;
    }}

    /* header text */
    QLabel[class~="rec-title"] {{
        color: {COLOR.text_2};
        font-size: 12px;
        font-weight: {FONT.w_semibold};
    }}

    /* legacy LIVE pill (.rec-live) */
    QLabel[class~="rec-live"] {{
        font-family: {FONT.mono};
        font-size: 10px;
        font-weight: {FONT.w_semibold};
        color: {COLOR.danger};
        background: {COLOR.danger_soft};
        padding: 2px 6px;
        border-radius: 4px;
    }}
    QLabel[class~="rec-pulse-dot"] {{
        background: {COLOR.danger};
        border-radius: 3px;
        min-width: 6px;
        min-height: 6px;
        max-width: 6px;
        max-height: 6px;
    }}
    QWidget[class~="rec-live-wrap"], QFrame[class~="rec-live-wrap"] {{
        background: transparent;
    }}

    /* ---------------------------------------------------------------- */
    /* REC badge (Wave-3 .rec-badge with .pulse dot)                     */
    /* ---------------------------------------------------------------- */
    QFrame[class~="rec-badge"], QWidget[class~="rec-badge"] {{
        background: {COLOR.coral_soft};
        border: 1px solid {COLOR.coral_line};
        border-radius: 7px;
        padding: 6px 11px;
    }}
    QLabel[class~="rec-badge-lbl"] {{
        font-family: {FONT.mono};
        font-size: 11px;
        font-weight: {FONT.w_semibold};
        color: {COLOR.coral_2};
        background: transparent;
    }}
    QFrame[class~="rec-badge"][class~="paused"],
    QWidget[class~="rec-badge"][class~="paused"] {{
        background: rgba(255,255,255,0.04);
        border-color: {COLOR.line_strong};
    }}
    QFrame[class~="rec-badge"][class~="paused"] QLabel[class~="rec-badge-lbl"],
    QWidget[class~="rec-badge"][class~="paused"] QLabel[class~="rec-badge-lbl"] {{
        color: {COLOR.text_2};
    }}
    QLabel[class~="rec-badge-pulse"], QFrame[class~="rec-badge-pulse"] {{
        background: {COLOR.coral};
        border-radius: 3px;
        min-width: 7px;
        min-height: 7px;
        max-width: 7px;
        max-height: 7px;
    }}
    QFrame[class~="rec-badge"][class~="paused"] QLabel[class~="rec-badge-pulse"],
    QFrame[class~="rec-badge"][class~="paused"] QFrame[class~="rec-badge-pulse"] {{
        background: {COLOR.text_3};
    }}

    /* ---------------------------------------------------------------- */
    /* Timer (.rec-timer)                                                */
    /* ---------------------------------------------------------------- */
    QLabel[class~="rec-timer"] {{
        font-family: {FONT.mono};
        font-size: {FONT.size_timer}px;
        font-weight: {FONT.w_semibold};
        color: {COLOR.text_1};
    }}
    QLabel[class~="rec-timer-ms"] {{
        font-family: {FONT.mono};
        font-size: 26px;
        color: {COLOR.text_3};
        font-weight: {FONT.w_medium};
    }}

    /* ---------------------------------------------------------------- */
    /* Wave bars                                                          */
    /* ---------------------------------------------------------------- */
    QWidget#recorderWave {{
        background: transparent;
    }}
    /* legacy single-bar widget */
    QWidget[class~="rec-bar"] {{
        background: qlineargradient(
            x1:0, y1:0, x2:0, y2:1,
            stop:0 {COLOR.violet},
            stop:1 {COLOR.violet_2}
        );
        border-radius: 2px;
    }}
    /* Wave-3 .rec-wave container with child .bar widgets */
    QWidget[class~="rec-wave"], QFrame[class~="rec-wave"] {{
        background: transparent;
    }}
    QWidget[class~="rec-wave"] QWidget[class~="bar"],
    QFrame[class~="rec-wave"] QWidget[class~="bar"],
    QWidget[class~="rec-wave"] QFrame[class~="bar"],
    QFrame[class~="rec-wave"] QFrame[class~="bar"] {{
        background: qlineargradient(
            x1:0, y1:0, x2:0, y2:1,
            stop:0 {COLOR.violet},
            stop:1 {COLOR.violet_2}
        );
        border-radius: 2px;
        min-height: 6px;
    }}
    QWidget[class~="rec-wave"][class~="paused"] QWidget[class~="bar"],
    QFrame[class~="rec-wave"][class~="paused"] QWidget[class~="bar"],
    QWidget[class~="rec-wave"][class~="paused"] QFrame[class~="bar"],
    QFrame[class~="rec-wave"][class~="paused"] QFrame[class~="bar"] {{
        background: qlineargradient(
            x1:0, y1:0, x2:0, y2:1,
            stop:0 rgba(139,127,255,0.6),
            stop:1 rgba(110,99,230,0.6)
        );
    }}

    /* ---------------------------------------------------------------- */
    /* Mode + chip rows                                                   */
    /* ---------------------------------------------------------------- */
    QLabel[class~="rec-mode"] {{
        color: {COLOR.text_2};
        font-size: 12px;
    }}
    QWidget[class~="rec-chip"], QLabel[class~="rec-chip"], QFrame[class~="rec-chip"] {{
        background: {COLOR.surface_3};
        border: 1px solid {COLOR.line_strong};
        border-radius: 12px;
        padding: 8px 14px;
        font-size: 12px;
        font-weight: {FONT.w_medium};
        color: {COLOR.text_1};
    }}
    QLabel[class~="rec-chip-ic"] {{
        color: {COLOR.violet};
    }}

    /* secondary info row (.rec-row) */
    QWidget[class~="rec-row"], QFrame[class~="rec-row"] {{
        background: transparent;
    }}
    QLabel[class~="rec-row-lang"] {{
        color: {COLOR.text_3};
        font-family: {FONT.mono};
        font-size: 11px;
    }}

    /* ---------------------------------------------------------------- */
    /* Footer buttons (.rec-ft / .rec-btn / .rec-left-btn)               */
    /* ---------------------------------------------------------------- */
    QWidget[class~="rec-ft"], QFrame[class~="rec-ft"] {{
        background: rgba(0,0,0,0.18);
        border-top: 1px solid {COLOR.line_soft};
    }}
    QLabel[class~="rec-ft-left"] {{
        font-size: 13px;
        color: {COLOR.text_2};
        font-weight: {FONT.w_medium};
    }}
    QLabel[class~="rec-ft-spacer"], QFrame[class~="rec-ft-spacer"], QWidget[class~="rec-ft-spacer"] {{
        background: transparent;
    }}

    QPushButton[class~="rec-left-btn"] {{
        font-size: 13px;
        font-weight: {FONT.w_medium};
        color: {COLOR.text_2};
        background: transparent;
        border: 0;
        padding: 8px 4px;
        border-radius: 6px;
    }}
    QPushButton[class~="rec-left-btn"]:hover {{
        color: {COLOR.text_1};
    }}

    /* primary action buttons (.rec-btn) */
    QPushButton[class~="rec-btn"] {{
        font-size: 13px;
        font-weight: {FONT.w_medium};
        padding: 9px 16px;
        border-radius: 9px;
        border: 1px solid {COLOR.line_strong};
        background: {COLOR.surface_3};
        color: {COLOR.text_1};
    }}
    QPushButton[class~="rec-btn"]:hover {{
        background: {COLOR.surface_4};
        border-color: {COLOR.line_3};
    }}
    QPushButton[class~="rec-btn"]:disabled {{
        color: {COLOR.text_4};
        background: {COLOR.surface_2};
    }}
    QPushButton[class~="rec-btn"][class~="pause"] {{
        background: {COLOR.surface_3};
        color: {COLOR.text_1};
        border-color: {COLOR.line_strong};
    }}
    QPushButton[class~="rec-btn"][class~="pause"]:hover {{
        background: {COLOR.surface_4};
    }}
    QPushButton[class~="rec-btn"][class~="stop"] {{
        background: qlineargradient(
            x1:0, y1:0, x2:0, y2:1,
            stop:0 {COLOR.coral},
            stop:1 #E85767
        );
        color: #1A0608;
        border-color: rgba(255,255,255,0.08);
        font-weight: {FONT.w_semibold};
    }}
    QPushButton[class~="rec-btn"][class~="stop"]:hover {{
        background: qlineargradient(
            x1:0, y1:0, x2:0, y2:1,
            stop:0 #FF8593,
            stop:1 #F26475
        );
    }}
    QPushButton[class~="rec-btn"][class~="replay"] {{
        background: {COLOR.surface_3};
        color: {COLOR.text_1};
        border-color: {COLOR.line_strong};
    }}
    QPushButton[class~="rec-btn"][class~="replay"]:hover {{
        background: {COLOR.surface_4};
        border-color: {COLOR.violet_line};
        color: {COLOR.violet};
    }}
    QPushButton[class~="rec-btn"][class~="save"] {{
        background: qlineargradient(
            x1:0, y1:0, x2:0, y2:1,
            stop:0 {COLOR.violet},
            stop:1 {COLOR.violet_2}
        );
        color: #14101A;
        border-color: rgba(255,255,255,0.08);
        font-weight: {FONT.w_semibold};
    }}
    QPushButton[class~="rec-btn"][class~="save"]:hover {{
        background: qlineargradient(
            x1:0, y1:0, x2:0, y2:1,
            stop:0 #9B90FF,
            stop:1 #7B70F0
        );
    }}
    QPushButton[class~="rec-btn"][class~="close"] {{
        background: transparent;
        color: {COLOR.text_2};
        border-color: transparent;
    }}
    QPushButton[class~="rec-btn"][class~="close"]:hover {{
        color: {COLOR.text_1};
        background: rgba(255,255,255,0.04);
    }}

    /* ---------------------------------------------------------------- */
    /* Destination card (.rec-dest)                                      */
    /* ---------------------------------------------------------------- */
    QWidget[class~="rec-dest"], QFrame[class~="rec-dest"] {{
        background: rgba(139,127,255,0.05);
        border: 1px solid {COLOR.violet_line};
        border-radius: 12px;
        padding: 12px 16px;
        font-size: 12px;
        color: {COLOR.text_2};
    }}
    QLabel[class~="rec-dest-target"] {{
        color: {COLOR.text_1};
        font-weight: {FONT.w_medium};
        background: rgba(255,255,255,0.04);
        border: 1px solid {COLOR.line_strong};
        border-radius: 6px;
        padding: 1px 7px;
    }}
    """


# ---------------------------------------------------------------------------
# YouTube URL input window
# ---------------------------------------------------------------------------

def youtube_qss() -> str:
    return f"""
    /* outer window chrome - reuses .win pattern */
    QWidget#youtubeCard, QFrame#youtubeCard {{
        background: {COLOR.surface_1};
        border-radius: {RADIUS.xxl}px;
        color: {COLOR.text_1};
    }}
    QFrame#youtubeGlow {{
        background: qradialgradient(
            cx:0.5, cy:-0.2, fx:0.5, fy:0.5, radius:1.0,
            stop:0 rgba(139,127,255,0.06),
            stop:0.55 transparent,
            stop:1 transparent
        );
        border: 0;
        border-radius: {RADIUS.xxl}px;
    }}
    QWidget#youtubeHeader {{
        background: transparent;
        border-bottom: 1px solid {COLOR.line_soft};
    }}
    QWidget#youtubeFooter {{
        background: rgba(0,0,0,0.15);
        border-top: 1px solid {COLOR.line_soft};
    }}
    QLabel[class~="yt-title"] {{
        font-size: 13px;
        font-weight: {FONT.w_semibold};
        color: {COLOR.text_1};
    }}
    QLabel[class~="yt-hint"] {{
        font-size: 12px;
        color: {COLOR.text_3};
    }}

    /* URL input body + the big violet-bordered field */
    QWidget[class~="url-body"], QFrame[class~="url-body"] {{
        background: transparent;
    }}
    QLineEdit[class~="url-input"] {{
        background: {COLOR.surface_2};
        border: 1px solid {COLOR.violet_line};
        border-radius: 12px;
        padding: 16px 18px;
        color: {COLOR.text_1};
        font-size: 14px;
        selection-background-color: {COLOR.violet_soft};
        selection-color: {COLOR.text_1};
    }}
    QLineEdit[class~="url-input"]:focus {{
        border-color: {COLOR.violet};
    }}
    """


# ---------------------------------------------------------------------------
# TTS window (Ctrl+Alt+6) — same chrome shape as YouTube, multi-line input
# ---------------------------------------------------------------------------

def tts_qss() -> str:
    return f"""
    QWidget#ttsCard, QFrame#ttsCard {{
        background: {COLOR.surface_1};
        border-radius: {RADIUS.xxl}px;
        color: {COLOR.text_1};
    }}
    QFrame#ttsGlow {{
        background: qradialgradient(
            cx:0.5, cy:-0.2, fx:0.5, fy:0.5, radius:1.0,
            stop:0 rgba(139,127,255,0.06),
            stop:0.55 transparent,
            stop:1 transparent
        );
        border: 0;
        border-radius: {RADIUS.xxl}px;
    }}
    QWidget#ttsHeader {{
        background: transparent;
        border-bottom: 1px solid {COLOR.line_soft};
    }}
    QWidget#ttsBody {{
        background: transparent;
    }}
    QWidget#ttsFooter {{
        background: rgba(0,0,0,0.15);
        border-top: 1px solid {COLOR.line_soft};
    }}
    QWidget#ttsVoiceRow {{
        background: transparent;
    }}
    QWidget#ttsSettingsWrap {{
        background: transparent;
    }}
    QLabel#ttsStatus {{
        color: {COLOR.text_3};
        font-size: 11px;
    }}
    QLabel[class~="tts-title"] {{
        font-size: 13px;
        font-weight: {FONT.w_semibold};
        color: {COLOR.text_1};
    }}
    QLabel[class~="tts-hint"] {{
        font-size: 12px;
        color: {COLOR.text_3};
    }}

    /* Big multi-line text area (.tts-area) */
    QTextEdit[class~="tts-area"], QPlainTextEdit[class~="tts-area"],
    QTextEdit#ttsTextInput, QPlainTextEdit#ttsTextInput {{
        background: {COLOR.surface_2};
        border: 1px solid {COLOR.violet_line};
        border-radius: 14px;
        padding: 16px 18px;
        color: {COLOR.text_1};
        font-size: 14px;
        min-height: 200px;
        selection-background-color: {COLOR.violet_soft};
        selection-color: {COLOR.text_1};
    }}
    QTextEdit[class~="tts-area"]:focus, QPlainTextEdit[class~="tts-area"]:focus,
    QTextEdit#ttsTextInput:focus, QPlainTextEdit#ttsTextInput:focus {{
        border-color: {COLOR.violet};
    }}
    """


# ---------------------------------------------------------------------------
# Concatenated default - kept for backwards compatibility.
# ---------------------------------------------------------------------------

def build_qss() -> str:
    return (
        shared_qss()
        + popup_qss()
        + manager_qss()
        + recorder_qss()
        + youtube_qss()
        + tts_qss()
    )


__all__ = [
    "shared_qss",
    "popup_qss",
    "manager_qss",
    "recorder_qss",
    "youtube_qss",
    "tts_qss",
    "build_qss",
]
