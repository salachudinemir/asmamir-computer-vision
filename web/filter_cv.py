"""Webcam filters on the shared Asmamir camera. Does not open a camera or a second Hands instance.

Filter looks adapted from mishu006/Filters (MIT). Ideas only — not a clone.
Two hands (index + thumb) open a portal; pinch or peace cycles the look.
"""

import time

import cv2
import numpy as np

PINCH_ON = 0.38
PINCH_OFF = 0.58
CYCLE_COOLDOWN = 0.45

_index = 0
_pinched = False
_peace_was = False
_cycle_at = 0.0


def _grid(roi):
    out = roi.copy()
    h, w = out.shape[:2]
    overlay = out.copy()
    step = 22
    color = (235, 235, 235)
    for x in range(0, w, step):
        cv2.line(overlay, (x, 0), (x, h), color, 1)
    for y in range(0, h, step):
        cv2.line(overlay, (0, y), (w, y), color, 1)
    return cv2.addWeighted(overlay, 0.75, out, 0.25, 0)


def _duotone(roi):
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    out = np.zeros_like(roi)
    out[gray < 60] = (15, 8, 10)
    out[(gray >= 60) & (gray < 130)] = (118, 30, 214)
    out[(gray >= 130) & (gray < 195)] = (35, 140, 235)
    out[gray >= 195] = (235, 240, 240)
    return out


def _halftone(roi):
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    cell = 6
    yy, xx = np.meshgrid(np.arange(h), np.arange(w), indexing="ij")
    cx = (xx % cell) - cell / 2
    cy = (yy % cell) - cell / 2
    radius = (1 - gray / 255.0) * (cell / 1.4)
    dots = np.sqrt(cx ** 2 + cy ** 2) < radius
    out = np.full_like(roi, 245)
    out[dots] = (15, 15, 15)
    return out


def _chromatic(roi):
    shift = 6
    b, g, r = cv2.split(roi)
    out = cv2.merge([np.roll(b, shift, axis=1), g, np.roll(r, -shift, axis=1)])
    out[::3, :, :] = (out[::3, :, :] * 0.72).astype(np.uint8)
    return out


def _thermal(roi):
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    return cv2.applyColorMap(gray, cv2.COLORMAP_JET)


def _vintage(roi):
    h, w = roi.shape[:2]
    kernel = np.array(
        [
            [0.272, 0.534, 0.131],
            [0.349, 0.686, 0.168],
            [0.393, 0.769, 0.189],
        ]
    )
    sepia = np.clip(cv2.transform(roi, kernel), 0, 255).astype(np.uint8)
    yy, xx = np.meshgrid(np.arange(h), np.arange(w), indexing="ij")
    cy, cx = h / 2.0, w / 2.0
    dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    max_dist = np.sqrt(cx ** 2 + cy ** 2) or 1.0
    vignette = np.clip(1 - 0.5 * (dist / max_dist), 0, 1)[..., None]
    out = (sepia * vignette).astype(np.uint8)
    noise = np.random.randint(0, 25, out.shape, dtype=np.uint8)
    return cv2.add(out, noise)


def _frosted(roi):
    blurred = cv2.GaussianBlur(roi, (35, 35), 0)
    white = np.full_like(roi, 255)
    return cv2.addWeighted(blurred, 0.55, white, 0.45, 0)


def _pink_halftone(roi):
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    cell = 5
    yy, xx = np.meshgrid(np.arange(h), np.arange(w), indexing="ij")
    cx = (xx % cell) - cell / 2
    cy = (yy % cell) - cell / 2
    radius = (1 - gray / 255.0) * (cell / 1.3)
    dots = np.sqrt(cx ** 2 + cy ** 2) < radius
    out = np.full_like(roi, (215, 190, 245))
    out[dots] = (55, 20, 130)
    return out


FILTERS = [
    ("grid", _grid),
    ("duotone", _duotone),
    ("halftone", _halftone),
    ("chromatic", _chromatic),
    ("thermal", _thermal),
    ("vintage", _vintage),
    ("frosted", _frosted),
    ("pink", _pink_halftone),
]


def filter_name():
    return FILTERS[_index][0]


def cycle_filter():
    global _index, _cycle_at
    now = time.monotonic()
    if now - _cycle_at < CYCLE_COOLDOWN:
        return filter_name()
    _index = (_index + 1) % len(FILTERS)
    _cycle_at = now
    return filter_name()


def reset_gestures():
    global _pinched, _peace_was, _cycle_at
    _pinched = False
    _peace_was = False
    _cycle_at = 0.0


def _xy(lm, w, h):
    return (int(lm.x * w), int(lm.y * h))


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
    span = max(22.0, float(np.hypot((lms[5].x - lms[17].x) * w, (lms[5].y - lms[17].y) * h)))
    d = float(np.hypot((lms[4].x - lms[8].x) * w, (lms[4].y - lms[8].y) * h))
    return d / span


def _hands_ltr(results):
    lst = results.multi_hand_landmarks if results is not None else None
    if not lst:
        return []
    ranked = sorted(lst, key=lambda hand: hand.landmark[0].x)
    return [hand.landmark for hand in ranked]


def _paint_polygon(frame, pts, filtro):
    h, w = frame.shape[:2]
    poly = np.array(pts, dtype=np.int32)
    x, y, bw, bh = cv2.boundingRect(poly)
    x, y = max(x, 0), max(y, 0)
    bw = min(bw, w - x)
    bh = min(bh, h - y)
    if bw <= 2 or bh <= 2:
        return
    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.fillPoly(mask, [poly], 255)
    mask_roi = mask[y : y + bh, x : x + bw]
    roi = frame[y : y + bh, x : x + bw]
    filtered = filtro(roi)
    if filtered.shape[:2] != roi.shape[:2]:
        filtered = cv2.resize(filtered, (roi.shape[1], roi.shape[0]), interpolation=cv2.INTER_LINEAR)
    mix = cv2.cvtColor(mask_roi, cv2.COLOR_GRAY2BGR).astype(np.float32) / 255.0
    blended = (filtered.astype(np.float32) * mix + roi.astype(np.float32) * (1.0 - mix)).astype(np.uint8)
    frame[y : y + bh, x : x + bw] = blended


def _palm_poly(lms, w, h):
    ids = (0, 1, 2, 5, 9, 13, 17)
    pts = np.array([_xy(lms[i], w, h) for i in ids], dtype=np.float32)
    center = pts.mean(axis=0)
    scaled = (center + (pts - center) * 2.2).astype(np.int32)
    hull = cv2.convexHull(scaled)
    return [tuple(int(v) for v in pt[0]) for pt in hull]


def draw_filter_overlay(frame, results):
    """Paint the current look on the existing frame. Reuses app.py Hands."""
    global _pinched, _peace_was
    h, w = frame.shape[:2]
    hands = _hands_ltr(results)
    filtro = FILTERS[_index][1]
    status = "two hands open a portal · pinch or peace cycles"
    want_cycle = False
    any_pinch = False
    any_peace = False

    for lms in hands:
        if _peace(lms):
            any_peace = True
        ratio = _pinch_ratio(lms, w, h)
        if ratio < PINCH_ON:
            any_pinch = True

    if any_pinch:
        if not _pinched:
            want_cycle = True
        _pinched = True
    elif not any_pinch:
        still_held = False
        for lms in hands:
            if _pinch_ratio(lms, w, h) < PINCH_OFF:
                still_held = True
                break
        if not still_held:
            _pinched = False

    if any_peace and not _peace_was:
        want_cycle = True
    _peace_was = any_peace

    if not hands:
        _pinched = False
        _peace_was = False
        status = "show one or two hands"
    elif want_cycle:
        name = cycle_filter()
        status = f"next: {name}"
        filtro = FILTERS[_index][1]

    if len(hands) >= 2:
        left, right = hands[0], hands[1]
        p1 = _xy(left[8], w, h)
        p2 = _xy(left[4], w, h)
        p3 = _xy(right[8], w, h)
        p4 = _xy(right[4], w, h)
        poly = [p1, p3, p4, p2]
        _paint_polygon(frame, poly, filtro)
        cv2.polylines(frame, [np.array(poly, dtype=np.int32)], True, (255, 255, 255), 1, cv2.LINE_AA)
        status = f"{filter_name()} portal · pinch or peace cycles"
    elif len(hands) == 1:
        poly = _palm_poly(hands[0], w, h)
        _paint_polygon(frame, poly, filtro)
        cv2.polylines(frame, [np.array(poly, dtype=np.int32)], True, (255, 255, 255), 1, cv2.LINE_AA)
        if not want_cycle:
            status = f"{filter_name()} on hand · pinch or peace cycles"

    return frame
