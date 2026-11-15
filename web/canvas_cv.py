"""Air-canvas on the webcam: index draws, fist erases, peace clears, gun = straight line."""

import cv2
import numpy as np

COLORS = [
    ("red", (40, 40, 255)),
    ("blue", (255, 90, 40)),
    ("green", (40, 220, 70)),
    ("yellow", (0, 240, 255)),
    ("cyan", (255, 220, 40)),
]
WIDTHS = [
    ("thin", 4),
    ("med", 8),
    ("thick", 14),
    ("bold", 22),
    ("mark", 32),
]
PINCH_ON = 0.38
PINCH_OFF = 0.58

_ink = None
_last = None
_color_i = 4  # cyan
_width_i = 1  # med
_pinched = False
_palm_was_open = False
_peace_was = False
_gun_was = False
_gun_a = None
_gun_b = None
_bar_pinched = False
_peace_hold = 0


def ink_color():
    return COLORS[_color_i][1]


def ink_name():
    return COLORS[_color_i][0]


def ink_px():
    return WIDTHS[_width_i][1]


def ink_width_name():
    return WIDTHS[_width_i][0]


def reset_canvas():
    global _ink, _last, _pinched, _palm_was_open, _peace_was, _gun_was, _gun_a, _gun_b, _bar_pinched, _peace_hold
    _ink = None
    _last = None
    _pinched = False
    _palm_was_open = False
    _peace_was = False
    _gun_was = False
    _gun_a = None
    _gun_b = None
    _bar_pinched = False
    _peace_hold = 0


def clear_ink():
    global _ink, _last
    if _ink is not None:
        _ink[:] = 0
    _last = None


def set_color(name):
    global _color_i
    key = name.strip().lower()
    aliases = {
        "red": 0, "merah": 0,
        "blue": 1, "biru": 1,
        "green": 2, "hijau": 2,
        "yellow": 3, "kuning": 3,
        "cyan": 4,
    }
    if key in aliases:
        _color_i = aliases[key]
        return ink_name()
    return None


def set_width(name):
    global _width_i
    key = str(name).strip().lower()
    aliases = {
        "thin": 0, "tipis": 0,
        "med": 1, "medium": 1, "sedang": 1,
        "thick": 2, "tebal": 2,
        "bold": 3,
        "mark": 4, "marker": 4, "tebal sekali": 4,
    }
    if key in aliases:
        _width_i = aliases[key]
        return ink_width_name()
    return None


def cycle_color():
    global _color_i
    _color_i = (_color_i + 1) % len(COLORS)
    return ink_name()


def _xy(lm, w, h):
    return (int(lm.x * w), int(lm.y * h))


def _reach(lms, a, b):
    return float(np.hypot(lms[a].x - lms[b].x, lms[a].y - lms[b].y))


def _extended(lms, tip, mcp):
    knuckle = max(0.035, _reach(lms, mcp, 0))
    return _reach(lms, tip, 0) > knuckle * 1.18


def _curled(lms, tip, mcp):
    knuckle = max(0.035, _reach(lms, mcp, 0))
    return _reach(lms, tip, 0) < knuckle * 1.08


def _fist(lms):
    folded = sum(_curled(lms, tip, mcp) for tip, mcp in ((8, 5), (12, 9), (16, 13), (20, 17)))
    thumb_in = _reach(lms, 4, 5) < 0.08
    return folded >= 4 and thumb_in


def _index_out(lms):
    return _extended(lms, 8, 5) and all(
        _curled(lms, tip, mcp) for tip, mcp in ((12, 9), (16, 13), (20, 17))
    )


def _peace(lms):
    """Index + middle out, ring + pinky curled. Measured from the wrist, not image up."""
    return (
        _extended(lms, 8, 5)
        and _extended(lms, 12, 9)
        and _curled(lms, 16, 13)
        and _curled(lms, 20, 17)
    )


def _gun(lms):
    """Index out, thumb away from the index knuckle, other fingers curled."""
    thumb_out = _reach(lms, 4, 5) > 0.07
    return (
        _extended(lms, 8, 5)
        and thumb_out
        and _curled(lms, 12, 9)
        and _curled(lms, 16, 13)
        and _curled(lms, 20, 17)
    )


def _open_palm(lms):
    stretched = sum(_extended(lms, tip, mcp) for tip, mcp in ((8, 5), (12, 9), (16, 13), (20, 17)))
    return stretched >= 4


def _pinch_ratio(lms, w, h):
    span = max(22.0, float(np.hypot((lms[5].x - lms[17].x) * w, (lms[5].y - lms[17].y) * h)))
    d = float(np.hypot((lms[4].x - lms[8].x) * w, (lms[4].y - lms[8].y) * h))
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


def _blend(frame, ink):
    mask = cv2.cvtColor(ink, cv2.COLOR_BGR2GRAY) > 8
    if not np.any(mask):
        return
    a = 0.72
    mixed = (frame[mask].astype(np.float32) * (1.0 - a) + ink[mask].astype(np.float32) * a)
    frame[mask] = mixed.astype(np.uint8)


def _palette_rects(w, h):
    n = len(COLORS)
    pad = 16
    bar_h = max(52, int(h * 0.1))
    y0 = h - bar_h - 18
    gap = 10
    inner = w - pad * 2 - gap * (n - 1)
    slot = max(40, inner // n)
    rects = []
    x = pad
    for _ in range(n):
        rects.append((x, y0, x + slot, y0 + bar_h))
        x += slot + gap
    return rects


def _hit_swatch(tip, rects):
    x, y = tip
    for i, (x0, y0, x1, y1) in enumerate(rects):
        if x0 <= x <= x1 and y0 <= y <= y1:
            return i
    return None


def _pinch_hit(pinch_pt, tip, thumb, rects):
    hit = _hit_swatch(pinch_pt, rects)
    if hit is None:
        hit = _hit_swatch(tip, rects) if _hit_swatch(thumb, rects) is not None else None
    return hit


def _width_rects(w, h):
    color_rects = _palette_rects(w, h)
    bar_h = color_rects[0][3] - color_rects[0][1]
    y1 = color_rects[0][1] - 10
    y0 = y1 - max(44, int(bar_h * 0.82))
    n = len(WIDTHS)
    pad = 16
    gap = 10
    inner = w - pad * 2 - gap * (n - 1)
    slot = max(40, inner // n)
    rects = []
    x = pad
    for _ in range(n):
        rects.append((x, y0, x + slot, y1))
        x += slot + gap
    return rects


def _label(frame, text, x, y, scale=0.45):
    cv2.putText(frame, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale, (255, 255, 255), 1, cv2.LINE_AA)


def _draw_widths(frame, rects):
    color = ink_color()
    for i, (x0, y0, x1, y1) in enumerate(rects):
        cv2.rectangle(frame, (x0, y0), (x1, y1), (36, 38, 42), -1)
        selected = i == _width_i
        border = (230, 230, 230) if selected else (30, 30, 30)
        cv2.rectangle(frame, (x0, y0), (x1, y1), border, 4 if selected else 2)
        mid_y = (y0 + y1) // 2
        px = min(WIDTHS[i][1], max(2, (y1 - y0) // 3))
        cv2.line(frame, (x0 + 12, mid_y - 6), (x1 - 12, mid_y - 6), color, px, cv2.LINE_AA)


def _draw_palette(frame, rects):
    for i, (x0, y0, x1, y1) in enumerate(rects):
        cv2.rectangle(frame, (x0, y0), (x1, y1), COLORS[i][1], -1)
        border = (230, 230, 230) if i == _color_i else (30, 30, 30)
        cv2.rectangle(frame, (x0, y0), (x1, y1), border, 4 if i == _color_i else 2)
        _label(frame, COLORS[i][0].title(), x0 + 8, y0 + 22)


def _draw_hud(frame, status, color_rects, width_rects):
    """Color chips with their names, and the thickness bars. No red frames."""
    _draw_widths(frame, width_rects)
    _draw_palette(frame, color_rects)
    if status:
        _label(frame, status, 28, 48, 0.65)


def draw_canvas_overlay(frame, results):
    """Keep the camera; paint/erase on a separate ink layer."""
    global _ink, _last, _pinched, _palm_was_open, _color_i, _width_i
    global _peace_was, _gun_was, _gun_a, _gun_b, _bar_pinched, _peace_hold
    h, w = frame.shape[:2]
    if _ink is None:
        _ink = np.zeros((h, w, 3), dtype=np.uint8)
        _last = None
    elif _ink.shape[:2] != (h, w):
        _ink = cv2.resize(_ink, (w, h), interpolation=cv2.INTER_NEAREST)
        _last = None

    color = ink_color()
    px = ink_px()
    color_rects = _palette_rects(w, h)
    width_rects = _width_rects(w, h)
    lms = _pick_hand(results)
    status = f"{ink_name().title()} · index draws · peace clears · gun line"
    if lms is None:
        if _gun_was and _gun_a is not None and _gun_b is not None:
            cv2.line(_ink, _gun_a, _gun_b, color, px, cv2.LINE_AA)
        _last = None
        _pinched = False
        _palm_was_open = False
        _peace_was = False
        _peace_hold = 0
        _gun_was = False
        _gun_a = None
        _gun_b = None
        _bar_pinched = False
        status = ""
    else:
        tip = _xy(lms[8], w, h)
        thumb = _xy(lms[4], w, h)
        pinch_pt = ((tip[0] + thumb[0]) // 2, (tip[1] + thumb[1]) // 2)
        peace = _peace(lms)
        gun = _gun(lms) and not peace
        span = max(22.0, float(np.hypot((lms[5].x - lms[17].x) * w, (lms[5].y - lms[17].y) * h)))
        pinch = _pinch_ratio(lms, w, h)
        color_hit = _pinch_hit(pinch_pt, tip, thumb, color_rects)
        width_hit = _pinch_hit(pinch_pt, tip, thumb, width_rects)
        hovering_color = _hit_swatch(tip, color_rects)
        hovering_width = _hit_swatch(tip, width_rects)
        if pinch < PINCH_ON and color_hit is not None:
            if not _bar_pinched:
                _color_i = color_hit
                color = ink_color()
                _bar_pinched = True
                _last = None
            status = f"color {ink_name().title()}"
            _pinched = True
        elif pinch < PINCH_ON and width_hit is not None:
            if not _bar_pinched:
                _width_i = width_hit
                px = ink_px()
                _bar_pinched = True
                _last = None
            status = "width"
            _pinched = True
        else:
            if pinch > PINCH_OFF:
                _bar_pinched = False
                _pinched = False
            palm = _open_palm(lms)
            if hovering_color is not None and pinch >= PINCH_ON:
                _last = None
                status = "pinch the swatch to pick a color"
            elif hovering_width is not None and pinch >= PINCH_ON:
                _last = None
                status = "pinch the swatch to pick thickness"
            elif peace:
                _peace_hold += 1
                _last = None
                if _peace_hold == 8:
                    clear_ink()
                    _gun_a = None
                    _gun_b = None
                    status = "cleared"
                else:
                    status = "hold peace to clear"
            elif gun:
                if not _gun_was:
                    _gun_a = tip
                _gun_b = tip
                status = "straight line"
                _last = None
            elif _gun_was and _gun_a is not None and _gun_b is not None:
                cv2.line(_ink, _gun_a, _gun_b, color, px, cv2.LINE_AA)
                _gun_a = None
                _gun_b = None
                status = f"line {ink_name().title()}"
            elif palm:
                _last = None
                status = f"{ink_name().title()} · ink stays"
            elif _fist(lms) and not palm:
                rad = max(18, int(span * 0.55))
                cv2.circle(_ink, tip, rad, (0, 0, 0), -1, cv2.LINE_AA)
                _last = None
                status = "erasing"
            elif _index_out(lms) and not palm and not _bar_pinched and not peace:
                if _last is not None:
                    cv2.line(_ink, _last, tip, color, px, cv2.LINE_AA)
                cv2.circle(_ink, tip, max(2, px // 2), color, -1, cv2.LINE_AA)
                _last = tip
                status = f"drawing {ink_name().title()}"
            else:
                _last = None
                if not palm and not peace:
                    status = f"{ink_name().title()} · pinch a swatch"
            if not peace:
                _peace_hold = 0
            _palm_was_open = palm
            _peace_was = peace
            _gun_was = gun
        cv2.circle(frame, tip, max(5, px // 2), color, 2, cv2.LINE_AA)
        if _gun_a is not None and _gun_b is not None:
            cv2.line(frame, _gun_a, _gun_b, color, max(2, min(px, 10)), cv2.LINE_AA)

    _blend(frame, _ink)
    _draw_hud(frame, status, color_rects, width_rects)
    return frame
