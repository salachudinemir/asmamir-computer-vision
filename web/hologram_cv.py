"""Idle hologram for Asmamir. The webcam is not used.

Rings, a soft glow, and a shallow ellipse stack. Original drawing.
The plate does not print a status or a product subtitle.
"""

import cv2
import numpy as np

_BG = (10, 12, 14)
_CYAN = (248, 196, 72)
_CORE = (255, 236, 186)


def render(width=1280, height=720, tick=0):
    """BGR plate. A glTF in web/hologram replaces the rings. The webcam stays off."""
    from web import hologram_mesh

    plate = hologram_mesh.render(width, height, tick)
    if plate is not None:
        return plate
    width = max(640, int(width))
    height = max(360, int(height))
    frame = np.full((height, width, 3), _BG, np.uint8)
    cx = width // 2
    cy = height // 2 + 8
    glow = np.zeros_like(frame)
    _atmosphere(glow, cx, cy, tick)
    _rings(glow, cx, cy, tick, soft=True)
    _name(glow, cx, cy)
    soft = cv2.GaussianBlur(glow, (0, 0), 16)
    frame = cv2.add(frame, soft)
    veil = cv2.GaussianBlur(glow, (0, 0), 36)
    frame = cv2.addWeighted(frame, 1.0, veil, 0.45, 0)
    crisp = np.zeros_like(frame)
    _rings(crisp, cx, cy, tick, soft=False)
    _name(crisp, cx, cy)
    return cv2.add(frame, crisp)


def _atmosphere(layer, cx, cy, tick):
    pulse = 90 + int(18 * np.sin(tick * 0.08))
    cv2.circle(layer, (cx, cy - 10), pulse, (90, 70, 28), -1, cv2.LINE_AA)
    cv2.ellipse(layer, (cx, cy + 36), (220, 28), 0, 0, 360, (40, 32, 12), -1, cv2.LINE_AA)


def _rings(layer, cx, cy, tick, soft):
    turn = (tick * 4) % 360
    span = 150 if soft else 148
    rings = (
        (span + 70, 34, 0, _CYAN, 2),
        (span + 18, 46, turn, _CYAN, 2),
        (span - 16, 58, 360 - turn, _CORE, 2),
        (span - 52, 70, turn // 2, _CYAN, 1),
    )
    for rx, ry, angle, color, thick in rings:
        cv2.ellipse(layer, (cx, cy), (rx, ry), 0, angle, angle + (150 if soft else 300), color, thick + (2 if soft else 0), cv2.LINE_AA)
    cv2.ellipse(layer, (cx, cy + 48), (span + 24, 16), 0, 200, 340, _CYAN, 1, cv2.LINE_AA)
    for index, radius in enumerate((span + 18, span - 16)):
        angle = np.deg2rad(turn + index * 160)
        flat = 46 / 150
        dot = (int(cx + np.cos(angle) * radius), int(cy + np.sin(angle) * radius * flat))
        cv2.circle(layer, dot, 5 if soft else 3, _CORE, -1, cv2.LINE_AA)
    band = int((tick * 6) % 220) - 40
    if -8 <= band <= 80:
        y = cy - 40 + band
        cv2.line(layer, (cx - span, y), (cx + span, y), _CORE, 2 if soft else 1, cv2.LINE_AA)


def _name(layer, cx, cy):
    text = "ASMAMIR"
    scale = 1.15
    thickness = 2
    size, _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_DUPLEX, scale, thickness)
    origin = (cx - size[0] // 2, cy + 8)
    cv2.putText(layer, text, origin, cv2.FONT_HERSHEY_DUPLEX, scale, _CORE, thickness, cv2.LINE_AA)
