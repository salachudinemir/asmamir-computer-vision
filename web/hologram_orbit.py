"""Standby orbit. One hand holds a pinch. The other hand's index drags.

Yaw and pitch keep going past 360. The figure does not turn on its own.
"""

import numpy as np

_prev = None
_held = False
_live = False
_drag_label = ""
_JUMP = 0.45


def reset():
    global _prev, _held, _live, _drag_label
    _prev = None
    _held = False
    _live = False
    _drag_label = ""


def _dist(a, b):
    return float(np.hypot(a.x - b.x, a.y - b.y) + abs(getattr(a, "z", 0.0) - getattr(b, "z", 0.0)) * 0.35)


def _pinch_ratio(lms):
    palm = max(_dist(lms[5], lms[17]), 0.04)
    return _dist(lms[4], lms[8]) / palm


def _pinching(lms, held):
    return _pinch_ratio(lms) < (0.72 if held else 0.55)


def _index_point(lms):
    """Index out, the other fingers curled. The pinch hand is not tested."""
    knuckle = max(0.04, _dist(lms[5], lms[0]))
    if _dist(lms[8], lms[0]) < knuckle * 1.15:
        return False
    for tip, mcp in ((12, 9), (16, 13), (20, 17)):
        if _dist(lms[tip], lms[0]) > max(0.04, _dist(lms[mcp], lms[0])) * 1.35:
            return False
    return True


def _hands(hand_landmarks):
    hands = []
    for item in hand_landmarks or []:
        hands.append(item.landmark if hasattr(item, "landmark") else item)
    return hands


def _labels(handedness):
    labels = []
    for item in handedness or []:
        klass = getattr(item, "classification", None)
        if klass:
            labels.append(str(klass[0].label))
        else:
            labels.append("")
    return labels


def engaged(hand_landmarks, handedness=None):
    """True while one hand pinches and the other index is the drag. A snap must wait."""
    hands = _hands(hand_landmarks)
    if len(hands) != 2:
        return False
    pinch_at = [i for i, lms in enumerate(hands) if _pinching(lms, _held)]
    if len(pinch_at) != 1:
        return False
    return _index_point(hands[1 - pinch_at[0]])


def apply(hand_landmarks, width, height, handedness=None):
    """Add yaw from horizontal drag and pitch from vertical drag. No clamp.

    The pinch hand is ignored as a pointer. The other hand's index is the drag,
    locked by Left/Right so a frame that swaps hand order does not jump.
    """
    global _prev, _held, _live, _drag_label
    from web import hologram_mesh

    hands = _hands(hand_landmarks)
    labels = _labels(handedness)
    if len(hands) != 2:
        _stop()
        return hologram_mesh.angles()
    pinch_at = [i for i, lms in enumerate(hands) if _pinching(lms, _held)]
    if len(pinch_at) != 1:
        _stop()
        return hologram_mesh.angles()
    drag_i = 1 - pinch_at[0]
    if not _index_point(hands[drag_i]):
        _stop()
        return hologram_mesh.angles()
    label = labels[drag_i] if drag_i < len(labels) else ""
    if _drag_label and label and label != _drag_label:
        _stop()
        return hologram_mesh.angles()
    _held = True
    _drag_label = label or _drag_label
    tip = hands[drag_i][8]
    point = (float(tip.x), float(tip.y))
    if _prev is None:
        _prev = point
        if not _live:
            _live = True
            print("Orbit on. Pinch held, index dragging.")
        return hologram_mesh.angles()
    dx = point[0] - _prev[0]
    dy = point[1] - _prev[1]
    _prev = point
    if abs(dx) > _JUMP or abs(dy) > _JUMP:
        return hologram_mesh.angles()
    height = max(1, int(height))
    dyaw = -dx * (float(width) / float(height)) * 360.0
    dpitch = -dy * 360.0
    hologram_mesh.add_turn(dyaw, dpitch)
    yaw, pitch = hologram_mesh.angles()
    if abs(dyaw) + abs(dpitch) >= 4.0:
        print(f"Orbit yaw {yaw:.0f} pitch {pitch:.0f}.")
    return yaw, pitch


def _stop():
    global _prev, _held, _live, _drag_label
    if _live:
        from web import hologram_mesh
        yaw, pitch = hologram_mesh.angles()
        print(f"Orbit held. yaw {yaw:.0f} pitch {pitch:.0f}.")
    _prev = None
    _held = False
    _live = False
    _drag_label = ""
