"""Reusable Qt visual effects: drop shadows and property animations.

Approximates the CSS `box-shadow` and `@keyframes pulse` patterns used in the
design handoff (see `_design_handoff_temp/project/styles.css`).
"""

from __future__ import annotations

from PyQt6.QtCore import QByteArray, QEasingCurve, QPropertyAnimation
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QGraphicsDropShadowEffect, QGraphicsOpacityEffect


def make_drop_shadow(widget, blur=30, x_offset=0, y_offset=12, color=None, alpha=170):
    """Attach a QGraphicsDropShadowEffect to `widget` and return it."""
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur)
    effect.setOffset(x_offset, y_offset)
    shadow_color = QColor(color) if color is not None else QColor(0, 0, 0)
    shadow_color.setAlpha(alpha)
    effect.setColor(shadow_color)
    widget.setGraphicsEffect(effect)
    return effect


def attach_pulse_animation(widget, prop_name="windowOpacity", period_ms=1400, lo=0.25, hi=0.8, loop=True):
    """Build a looping lo<->hi QPropertyAnimation on `widget`; caller must .start() it."""
    anim = QPropertyAnimation(widget, QByteArray(prop_name.encode("utf-8")))
    anim.setDuration(period_ms)
    anim.setKeyValueAt(0.0, lo)
    anim.setKeyValueAt(0.5, hi)
    anim.setKeyValueAt(1.0, lo)
    anim.setEasingCurve(QEasingCurve.Type.InOutSine)
    if loop:
        anim.setLoopCount(-1)
    return anim


def fade_in(widget, duration_ms=240):
    """Animate `widget` from transparent to opaque over `duration_ms` and start immediately."""
    meta = widget.metaObject()
    has_window_opacity = meta.indexOfProperty("windowOpacity") != -1 and widget.isWindow()
    if has_window_opacity:
        widget.setWindowOpacity(0.0)
        anim = QPropertyAnimation(widget, QByteArray(b"windowOpacity"), widget)
    else:
        effect = QGraphicsOpacityEffect(widget)
        effect.setOpacity(0.0)
        widget.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, QByteArray(b"opacity"), widget)
    anim.setDuration(duration_ms)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)
    anim.start()
    return anim
