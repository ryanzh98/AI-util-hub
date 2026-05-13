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
        background: {COLOR.surface_3};
        border-radius: 4px;
        min-height: 24px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {COLOR.surface_4};
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
        background: {COLOR.surface_3};
        border-radius: 4px;
        min-width: 24px;
    }}
    QScrollBar::handle:horizontal:hover {{
        background: {COLOR.surface_4};
    }}
    QScrollBar::add-line:horizontal,
    QScrollBar::sub-line:horizontal {{
        background: transparent;
        width: 0;
        border: 0;
    }}

    /* generic .btn pattern */
    QPushButton[class~="btn"] {{
        background: {COLOR.surface_2};
        color: {COLOR.text_1};
        border: 1px solid {COLOR.line};
        border-radius: 8px;
        padding: 7px 12px;
        font-size: 12px;
        font-weight: {FONT.w_medium};
    }}
    QPushButton[class~="btn"]:hover {{
        background: {COLOR.surface_3};
        border-color: {COLOR.line_strong};
    }}
    QPushButton[class~="btn"]:pressed {{
        background: {COLOR.surface_3};
    }}
    QPushButton[class~="btn"]:disabled {{
        color: {COLOR.text_3};
        background: {COLOR.surface_1};
        border-color: {COLOR.line};
    }}

    QPushButton[class~="btn"][class~="ghost"] {{
        background: transparent;
        border-color: transparent;
    }}
    QPushButton[class~="btn"][class~="ghost"]:hover {{
        background: {COLOR.surface_3};
        border-color: transparent;
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

    /* icon-only button */
    QPushButton[class~="icon-btn"] {{
        background: transparent;
        border: 1px solid transparent;
        color: {COLOR.text_2};
        min-width: 28px;
        min-height: 28px;
        max-width: 28px;
        max-height: 28px;
        border-radius: 8px;
        padding: 0;
    }}
    QPushButton[class~="icon-btn"]:hover {{
        background: {COLOR.surface_3};
        color: {COLOR.text_1};
        border-color: {COLOR.line};
    }}

    /* keyboard-cap chips: .kbd is QLabel-like */
    QLabel[class~="kbd"], QWidget[class~="kbd"] {{
        font-family: {FONT.mono};
        font-size: 10px;
        font-weight: {FONT.w_medium};
        color: {COLOR.text_3};
        background: rgba(255,255,255,0.04);
        border: 1px solid {COLOR.line};
        border-bottom: 2px solid {COLOR.line};
        border-radius: 4px;
        padding: 1px 5px;
        min-width: 17px;
    }}
    """


# ---------------------------------------------------------------------------
# Popup launcher window
# ---------------------------------------------------------------------------

def popup_qss() -> str:
    return f"""
    /* frameless window chrome (.win) */
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

    /* header row (.pop-hd) */
    QWidget#popupHeader {{
        background: transparent;
        border-bottom: 1px solid {COLOR.line_soft};
    }}

    /* brand block (.brand) */
    QLabel[class~="brand"] {{
        color: {COLOR.text_1};
        font-size: 13px;
        font-weight: {FONT.w_semibold};
    }}
    QLabel[class~="brand-mark"] {{
        background: qlineargradient(
            x1:0, y1:0, x2:1, y2:1,
            stop:0 {COLOR.violet},
            stop:1 #6B5BF0
        );
        border-radius: 6px;
        min-width: 22px;
        min-height: 22px;
        max-width: 22px;
        max-height: 22px;
        color: #FFFFFF;
    }}
    QLabel[class~="brand-dot"] {{
        color: {COLOR.text_4};
        font-weight: {FONT.w_regular};
    }}
    QLabel[class~="brand-ctx"] {{
        color: {COLOR.text_2};
        font-weight: {FONT.w_medium};
    }}

    /* search field (.search) */
    QLineEdit[class~="search"] {{
        background: {COLOR.surface_3};
        border: 1px solid {COLOR.line};
        border-radius: 9px;
        padding: 0 10px 0 30px;
        min-height: 30px;
        color: {COLOR.text_1};
        font-size: 13px;
        selection-background-color: {COLOR.violet_soft};
        selection-color: {COLOR.text_1};
    }}
    QLineEdit[class~="search"]:focus {{
        border-color: {COLOR.violet_line};
        background: #262934;
    }}

    /* section headers (.section-hd) */
    QLabel[class~="section-hd-lbl"] {{
        font-family: {FONT.mono};
        font-size: 10px;
        font-weight: {FONT.w_semibold};
        letter-spacing: 1px;
        color: {COLOR.text_3};
    }}
    QLabel[class~="section-hd-count"] {{
        font-family: {FONT.mono};
        font-size: 10px;
        color: {COLOR.text_4};
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

    /* tile (.tile) - default */
    QWidget[class~="tile"], QPushButton[class~="tile"] {{
        background: {COLOR.surface_2};
        border: 1px solid {COLOR.line};
        border-radius: 12px;
        padding: 10px 11px;
        min-height: 78px;
        max-height: 78px;
        color: {COLOR.text_1};
        text-align: left;
        font-size: 11px;
        font-weight: {FONT.w_medium};
    }}
    QWidget[class~="tile"]:hover, QPushButton[class~="tile"]:hover {{
        background: {COLOR.surface_3};
        border-color: {COLOR.line_strong};
    }}
    QWidget[class~="tile"][focused="true"],
    QPushButton[class~="tile"][focused="true"] {{
        background: {COLOR.surface_3};
        border-color: {COLOR.violet_line};
    }}

    /* tile variants */
    QWidget[class~="tile"][class~="ai"]:hover,
    QPushButton[class~="tile"][class~="ai"]:hover,
    QWidget[class~="tile"][class~="ai"][focused="true"],
    QPushButton[class~="tile"][class~="ai"][focused="true"] {{
        border-color: {COLOR.violet_line};
    }}
    QWidget[class~="tile"][class~="snip"]:hover,
    QPushButton[class~="tile"][class~="snip"]:hover,
    QWidget[class~="tile"][class~="snip"][focused="true"],
    QPushButton[class~="tile"][class~="snip"][focused="true"] {{
        border-color: {COLOR.mint_line};
    }}
    QWidget[class~="tile"][class~="url"]:hover,
    QPushButton[class~="tile"][class~="url"]:hover,
    QWidget[class~="tile"][class~="url"][focused="true"],
    QPushButton[class~="tile"][class~="url"][focused="true"] {{
        border-color: rgba(120,170,255,0.35);
    }}

    /* tile running pulse - set property running=true */
    QWidget[class~="tile"][running="true"],
    QPushButton[class~="tile"][running="true"] {{
        border-color: {COLOR.violet_line};
    }}

    /* tile-name label inside tile */
    QLabel[class~="tile-name"] {{
        color: {COLOR.text_1};
        font-size: 11px;
        font-weight: {FONT.w_medium};
    }}
    QLabel[class~="tile-emoji"] {{
        font-size: 19px;
    }}

    /* tile-kbd chip (top-right of each tile) */
    QLabel[class~="tile-kbd"], QWidget[class~="tile-kbd"] {{
        font-family: {FONT.mono};
        font-size: 9px;
        font-weight: {FONT.w_semibold};
        color: {COLOR.text_4};
        background: rgba(255,255,255,0.03);
        border: 1px solid {COLOR.line};
        border-radius: 4px;
        padding: 1px 4px;
        min-width: 16px;
    }}

    /* tile-type icon at bottom right */
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

    /* popup footer (.pop-ft) */
    QWidget#popupFooter {{
        background: rgba(0,0,0,0.15);
        border-top: 1px solid {COLOR.line_soft};
    }}
    QLabel[class~="pop-ft-hint"] {{
        font-family: {FONT.mono};
        font-size: 11px;
        color: {COLOR.text_3};
    }}
    QPushButton[class~="manage"] {{
        background: transparent;
        border: 0;
        color: {COLOR.text_2};
        font-size: 11px;
        font-weight: {FONT.w_medium};
        padding: 4px 8px;
        border-radius: 6px;
    }}
    QPushButton[class~="manage"]:hover {{
        color: {COLOR.text_1};
        background: rgba(255,255,255,0.04);
    }}

    /* empty state */
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

    /* toast (.toast) - backdrop-filter omitted, alpha bumped */
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
    /* toast icon chip variants */
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
    /* outer window (.mgr) */
    QWidget#managerCard, QFrame#managerCard {{
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

    /* left rail (.mgr-rail) */
    QWidget#managerRail {{
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
        min-height: 30px;
        color: {COLOR.text_1};
        font-size: 12px;
    }}
    QLineEdit[class~="mgr-search"]:focus {{
        border-color: {COLOR.violet_line};
    }}

    /* tabs (.mgr-tabs / .mgr-tab) */
    QWidget#managerTabs {{
        background: rgba(0,0,0,0.25);
        border-radius: 8px;
        padding: 3px;
    }}
    QPushButton[class~="mgr-tab"] {{
        background: transparent;
        color: {COLOR.text_2};
        border: 0;
        font-size: 11px;
        font-weight: {FONT.w_medium};
        padding: 5px 8px;
        border-radius: 6px;
    }}
    QPushButton[class~="mgr-tab"]:hover {{
        color: {COLOR.text_1};
    }}
    QPushButton[class~="mgr-tab"][on="true"] {{
        background: {COLOR.surface_2};
        color: {COLOR.text_1};
    }}

    /* group label (.mgr-grp) */
    QLabel[class~="mgr-grp"] {{
        font-family: {FONT.mono};
        font-size: 10px;
        font-weight: {FONT.w_semibold};
        letter-spacing: 1px;
        color: {COLOR.text_3};
    }}
    QPushButton[class~="mgr-add"] {{
        background: transparent;
        border: 0;
        color: {COLOR.text_3};
        min-width: 18px;
        min-height: 18px;
        max-width: 18px;
        max-height: 18px;
        border-radius: 4px;
    }}
    QPushButton[class~="mgr-add"]:hover {{
        background: {COLOR.surface_3};
        color: {COLOR.text_1};
    }}

    /* list rows (.mgr-row) */
    QWidget[class~="mgr-row"], QPushButton[class~="mgr-row"] {{
        background: transparent;
        border: 1px solid transparent;
        border-radius: 7px;
        padding: 7px 8px;
        color: {COLOR.text_1};
        font-size: 12px;
        text-align: left;
    }}
    QWidget[class~="mgr-row"]:hover, QPushButton[class~="mgr-row"]:hover {{
        background: rgba(255,255,255,0.03);
    }}
    QWidget[class~="mgr-row"][on="true"],
    QPushButton[class~="mgr-row"][on="true"] {{
        background: rgba(139,127,255,0.10);
        border-color: {COLOR.violet_line};
    }}
    QLabel[class~="mgr-row-name"] {{
        color: {COLOR.text_1};
        font-weight: {FONT.w_regular};
    }}
    QLabel[class~="mgr-grip"] {{
        color: {COLOR.text_4};
        font-size: 10px;
    }}
    QLabel[class~="mgr-row-meta"] {{
        color: {COLOR.text_4};
    }}
    QWidget[class~="mgr-row"][on="true"] QLabel[class~="mgr-row-meta"] {{
        color: {COLOR.violet};
    }}

    /* editor pane (.mgr-edit / .ed) */
    QWidget#managerEdit {{
        background: {COLOR.surface_1};
    }}
    QWidget#managerEditHead {{
        background: transparent;
        border-bottom: 1px solid {COLOR.line_soft};
    }}

    /* big emoji block (.ed-hd-emoji) */
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

    /* header kind label (.ed-hd-kind) */
    QLabel[class~="ed-hd-kind"] {{
        font-family: {FONT.mono};
        font-size: 10px;
        font-weight: {FONT.w_semibold};
        letter-spacing: 1px;
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
        letter-spacing: 1px;
        color: {COLOR.text_3};
    }}
    QLabel[class~="ed-field-hint"] {{
        font-size: 11px;
        color: {COLOR.text_3};
    }}

    /* inputs (.ed-input / .ed-textarea) */
    QLineEdit[class~="ed-input"],
    QTextEdit[class~="ed-textarea"],
    QPlainTextEdit[class~="ed-textarea"],
    QComboBox[class~="ed-input"] {{
        background: {COLOR.surface_2};
        border: 1px solid {COLOR.line};
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
    QWidget#editorPreview, QFrame[class~="ed-preview"] {{
        background: rgba(0,0,0,0.18);
        border: 1px solid {COLOR.line};
        border-radius: 12px;
    }}
    QLabel[class~="ed-preview-lbl"] {{
        font-family: {FONT.mono};
        font-size: 10px;
        font-weight: {FONT.w_semibold};
        letter-spacing: 1px;
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
        letter-spacing: 1px;
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
        background: {COLOR.surface_3};
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
    QWidget#editorFooter {{
        background: rgba(0,0,0,0.15);
        border-top: 1px solid {COLOR.line_soft};
    }}
    QLabel[class~="ed-ft-lbl"] {{
        font-family: {FONT.mono};
        font-size: 10px;
        font-weight: {FONT.w_semibold};
        letter-spacing: 1px;
        color: {COLOR.text_3};
    }}
    QLabel[class~="ed-ft-pos"] {{
        font-size: 11px;
        color: {COLOR.text_2};
    }}
    QLabel[class~="ed-ft-mute"] {{
        color: {COLOR.text_3};
    }}
    """


# ---------------------------------------------------------------------------
# Recorder window
# ---------------------------------------------------------------------------

def recorder_qss() -> str:
    return f"""
    /* outer window (.rec) */
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

    /* header (.rec-hd) */
    QWidget#recorderHead {{
        background: transparent;
    }}
    QLabel[class~="rec-title"] {{
        color: {COLOR.text_2};
        font-size: 12px;
        font-weight: {FONT.w_semibold};
    }}
    /* LIVE pill (.rec-hd .live) */
    QLabel[class~="rec-live"] {{
        font-family: {FONT.mono};
        font-size: 10px;
        font-weight: {FONT.w_semibold};
        letter-spacing: 1px;
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

    /* timer (.rec-timer) */
    QLabel[class~="rec-timer"] {{
        font-family: {FONT.mono};
        font-size: {FONT.size_timer}px;
        font-weight: {FONT.w_semibold};
        color: {COLOR.text_1};
    }}
    QLabel[class~="rec-timer-ms"] {{
        font-family: {FONT.mono};
        font-size: 22px;
        color: {COLOR.text_3};
        font-weight: {FONT.w_medium};
    }}

    /* waveform container (bars are individual QWidgets drawn in Python) */
    QWidget#recorderWave {{
        background: transparent;
    }}
    QWidget[class~="rec-bar"] {{
        background: qlineargradient(
            x1:0, y1:0, x2:0, y2:1,
            stop:0 {COLOR.violet},
            stop:1 #6557E0
        );
        border-radius: 2px;
    }}

    /* mode row (.rec-mode .chip) */
    QLabel[class~="rec-mode"] {{
        color: {COLOR.text_2};
        font-size: 12px;
    }}
    QWidget[class~="rec-chip"], QLabel[class~="rec-chip"] {{
        background: {COLOR.surface_2};
        border: 1px solid {COLOR.line};
        border-radius: 12px;
        padding: 4px 9px;
        font-size: 11px;
        color: {COLOR.text_2};
    }}

    /* footer (.rec-ft) */
    QWidget#recorderFooter {{
        background: rgba(0,0,0,0.15);
        border-top: 1px solid {COLOR.line_soft};
    }}
    QPushButton[class~="rec-left-btn"] {{
        font-size: 12px;
        font-weight: {FONT.w_medium};
        color: {COLOR.text_2};
        background: transparent;
        border: 0;
        padding: 8px 12px;
        border-radius: 8px;
    }}
    QPushButton[class~="rec-left-btn"]:hover {{
        color: {COLOR.text_1};
        background: rgba(255,255,255,0.04);
    }}

    /* primary action buttons (.rec-btn) */
    QPushButton[class~="rec-btn"] {{
        font-size: 12px;
        font-weight: {FONT.w_semibold};
        padding: 9px 14px;
        border-radius: 9px;
        border: 1px solid {COLOR.line_strong};
        background: {COLOR.surface_3};
        color: {COLOR.text_1};
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
        background: {COLOR.danger};
        color: #0C0D15;
        border-color: {COLOR.danger};
    }}
    QPushButton[class~="rec-btn"][class~="stop"]:hover {{
        background: #FF7E8C;
    }}

    /* destination hint (.rec-dest) */
    QWidget[class~="rec-dest"], QFrame[class~="rec-dest"] {{
        background: rgba(139,127,255,0.06);
        border: 1px solid rgba(139,127,255,0.16);
        border-radius: 9px;
        padding: 8px 12px;
        font-size: 11px;
        color: {COLOR.text_2};
    }}
    QLabel[class~="rec-dest-target"] {{
        color: {COLOR.text_1};
        font-weight: {FONT.w_medium};
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
    QLabel[class~="yt-title"] {{
        font-size: 13px;
        font-weight: {FONT.w_semibold};
        color: {COLOR.text_1};
    }}
    QLabel[class~="yt-hint"] {{
        font-size: 12px;
        color: {COLOR.text_3};
    }}
    QWidget#youtubeFooter {{
        background: rgba(0,0,0,0.15);
        border-top: 1px solid {COLOR.line_soft};
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
    QLabel[class~="tts-title"] {{
        font-size: 13px;
        font-weight: {FONT.w_semibold};
        color: {COLOR.text_1};
    }}
    QLabel[class~="tts-hint"] {{
        font-size: 12px;
        color: {COLOR.text_3};
    }}
    QWidget#ttsFooter {{
        background: rgba(0,0,0,0.15);
        border-top: 1px solid {COLOR.line_soft};
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
