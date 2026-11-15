"""Dragon on a black stage: green-keyed sprite sheet, chained body history."""

import math
import time
from pathlib import Path

import cv2
import numpy as np

SHEET = Path(__file__).resolve().parent / "dragon" / "sheet.png"
# Tight boxes from HSV-green keyed components on 1408x768 sheet.
CROPS = {
    "head": (46, 32, 166, 211),
    "body": (76, 278, 90, 180),
    "tail": (1212, 281, 145, 168),
    "head_side": (932, 562, 129, 116),
}
TRAIL = 14
SPACING = 38.0

_parts = None
_trail = []
_phase = 0.0
_prev_x = None
_prev_t = None
_fire = 0.0
_heading = np.array((1.0, 0.0), dtype=np.float32)
_peace_was = False
_pinched = False


def _xy(lm, w, h):
    return np.array((lm.x * w, lm.y * h), dtype=np.float32)


def _fist(lms):
    folded = 0
    for tip, pip in ((8, 6), (12, 10), (16, 14), (20, 18)):
        if lms[tip].y > lms[pip].y - 0.015:
            folded += 1
    thumb_in = abs(lms[4].x - lms[5].x) < 0.08
    return folded >= 4 and thumb_in


def _finger_up(lms, tip, pip):
    return lms[tip].y < lms[pip].y - 0.018


def _finger_down(lms, tip, pip):
    return lms[tip].y > lms[pip].y - 0.008


def _peace(lms):
    return (
        _finger_up(lms, 8, 6)
        and _finger_up(lms, 12, 10)
        and _finger_down(lms, 16, 14)
        and _finger_down(lms, 20, 18)
    )


def _pinch_ratio(lms, w, h):
    span = max(22.0, float(np.linalg.norm(_xy(lms[5], w, h) - _xy(lms[17], w, h))))
    d = float(np.linalg.norm(_xy(lms[4], w, h) - _xy(lms[8], w, h)))
    return d / span


def _pick_hand(results):
    lst = results.multi_hand_landmarks if results is not None else None
    if not lst:
        return None
    best = lst[0].landmark
    best_y = best[8].y
    for hand in lst[1:]:
        if hand.landmark[8].y < best_y:
            best = hand.landmark
            best_y = best[8].y
    return best


def _green_rgba(bgr):
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    green = cv2.inRange(hsv, np.array([35, 50, 40]), np.array([95, 255, 255]))
    alpha = cv2.bitwise_not(green)
    alpha = cv2.GaussianBlur(alpha, (3, 3), 0)
    return np.dstack([bgr, alpha])


def _load_parts():
    global _parts
    if _parts is not None:
        return _parts
    sheet = cv2.imread(str(SHEET))
    _parts = {}
    if sheet is None:
        return _parts
    for name, (x, y, w, h) in CROPS.items():
        crop = sheet[y : y + h, x : x + w]
        _parts[name] = _green_rgba(crop)
    return _parts


def _blend_patch(dst, sprite, cx, cy):
    if sprite is None or sprite.size == 0:
        return
    sh, sw = sprite.shape[:2]
    x0, y0 = int(cx - sw / 2), int(cy - sh / 2)
    x1, y1 = x0 + sw, y0 + sh
    dh, dw = dst.shape[:2]
    sx0 = 0 if x0 >= 0 else -x0
    sy0 = 0 if y0 >= 0 else -y0
    sx1 = sw if x1 <= dw else sw - (x1 - dw)
    sy1 = sh if y1 <= dh else sh - (y1 - dh)
    dx0, dy0 = max(0, x0), max(0, y0)
    dx1, dy1 = min(dw, x1), min(dh, y1)
    if sx1 <= sx0 or sy1 <= sy0:
        return
    patch = sprite[sy0:sy1, sx0:sx1]
    roi = dst[dy0:dy1, dx0:dx1]
    a = patch[:, :, 3:4].astype(np.float32) / 255.0
    roi[:] = (patch[:, :, :3] * a + roi * (1.0 - a)).astype(np.uint8)


def _rotate(sprite, angle_rad, scale):
    h, w = sprite.shape[:2]
    rot = -math.degrees(angle_rad)
    mat = cv2.getRotationMatrix2D((w / 2.0, h / 2.0), rot, scale)
    cos, sin = abs(mat[0, 0]), abs(mat[0, 1])
    nw, nh = int(h * sin + w * cos), int(h * cos + w * sin)
    mat[0, 2] += nw / 2.0 - w / 2.0
    mat[1, 2] += nh / 2.0 - h / 2.0
    return cv2.warpAffine(
        sprite,
        mat,
        (max(1, nw), max(1, nh)),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0, 0),
    )


def _draw_fire(frame, pos, heading, scale, amount):
    n = float(np.linalg.norm(heading))
    d = heading / n if n > 1e-3 else np.array((1.0, 0.0), dtype=np.float32)
    perp = np.array((-d[1], d[0]), dtype=np.float32)
    glow = frame.copy()
    for i, color in enumerate(((0, 140, 255), (0, 200, 255), (80, 255, 255))):
        reach = scale * (3.2 - i * 0.6) * (0.5 + amount)
        wide = scale * (1.2 - i * 0.28) * (0.45 + amount)
        a = pos + d * (scale * 0.35)
        b = pos + d * reach + perp * wide
        c = pos + d * reach - perp * wide
        cv2.fillConvexPoly(glow, np.array([a, b, c], dtype=np.int32), color)
    cv2.addWeighted(glow, 0.7, frame, 0.3, 0, frame)


def _push_head(target):
    """History buffer: head is [0]; body/tail lag behind."""
    global _trail
    if not _trail:
        _trail = [target.copy()]
        return
    if float(np.linalg.norm(target - _trail[0])) < 8:
        _trail[0] = target.copy()
        return
    _trail.insert(0, target.copy())
    packed = [_trail[0]]
    dist = 0.0
    last = _trail[0]
    for p in _trail[1:]:
        step = float(np.linalg.norm(p - last))
        dist += step
        if dist >= SPACING:
            packed.append(p.copy())
            last = p
            dist = 0.0
        if len(packed) >= TRAIL:
            break
    _trail = packed


def draw_dragon_overlay(frame, results):
    """Black stage. Pinch drags the head; peace cuts the body; fist = fire."""
    global _phase, _prev_x, _prev_t, _fire, _heading, _trail, _peace_was, _pinched
    h, w = frame.shape[:2]
    frame[:] = 0
    now = time.time()
    dt = 0.016 if _prev_t is None else min(0.05, max(0.001, now - _prev_t))
    _prev_t = now
    _fire = max(0.0, _fire - dt * 1.8)
    parts = _load_parts()

    lms = _pick_hand(results)
    status = "pinch to drag the head · peace cuts the body · fist fire"
    if lms is not None:
        tip = _xy(lms[8], w, h)
        span = max(36.0, float(np.linalg.norm(_xy(lms[5], w, h) - _xy(lms[17], w, h))))
        pinch_r = _pinch_ratio(lms, w, h)
        dragging = pinch_r < 0.42
        if _pinched and pinch_r > 0.58:
            _pinched = False
        if dragging:
            _pinched = True
        peace = _peace(lms)
        if peace and not _peace_was:
            _trail = _trail[:1]
            status = "body cut"
        elif dragging:
            dx = 0.0 if _prev_x is None else float(tip[0] - _prev_x)
            _prev_x = float(tip[0])
            _phase += dt * 2.8 + dx * 0.05
            swirl = np.array(
                (math.sin(_phase) * span * 0.35, math.cos(_phase * 1.25) * span * 0.18),
                dtype=np.float32,
            )
            _push_head(tip + swirl)
            if len(_trail) >= 2:
                delta = _trail[0] - _trail[1]
                if float(np.linalg.norm(delta)) > 1.0:
                    _heading = delta.astype(np.float32)
            status = "dragging head"
        else:
            _prev_x = None
        if _fist(lms) and not peace:
            _fire = 1.0
            status = "fire breath"
        _peace_was = peace
    else:
        _prev_x = None
        _peace_was = False
        _pinched = False
        if _trail:
            _trail = _trail[1:]
        status = "pinch the head to drag · peace to cut"

    if _trail:
        scale = max(0.35, min(0.85, (h / 720.0) * 0.7))
        body = parts.get("body")
        tail = parts.get("tail")
        head_front = parts.get("head")
        head_side = parts.get("head_side")
        if _fire > 0.08:
            _draw_fire(frame, _trail[0], _heading, 48.0, _fire)
        n = len(_trail)
        for i in range(n - 1, -1, -1):
            p = _trail[i]
            if i + 1 < n:
                vec = _trail[i] - _trail[i + 1]
            elif i > 0:
                vec = _trail[i - 1] - _trail[i]
            else:
                vec = _heading
            ang = math.atan2(float(vec[1]), float(vec[0]))
            if i == 0:
                sprite = head_side if abs(vec[0]) > abs(vec[1]) * 0.6 else head_front
                if sprite is head_side:
                    rot = ang - math.pi
                else:
                    rot = ang * 0.15
                drawn = _rotate(sprite, rot, scale * 1.15) if sprite is not None else None
            elif i == n - 1 and n > 2:
                drawn = _rotate(tail, ang - math.pi / 2, scale * 0.95) if tail is not None else None
            else:
                drawn = _rotate(body, ang - math.pi / 2, scale * 0.72) if body is not None else None
            if drawn is not None:
                _blend_patch(frame, drawn, p[0], p[1])

    return frame
