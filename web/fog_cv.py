"""Fogged-glass mirror on the shared Asmamir camera.

Adapted from maherkhan-builds/fog-mirror (MIT). A blurred, cool-tinted copy of
the frame shows where the fog mask is thick. The glass starts clear. An open
mouth close to the camera lays thick fog across the whole glass in a frame
or two. One index finger wipes a small path. An open hand wipes a larger
patch. A fist does not refill the glass. The mask is not rebuilt while the
mode stays on.

OpenCV reimplementation. Does not copy that project's HTML. Does not open a
camera or a second Hands instance. Does not save the frame.
"""

import cv2
import numpy as np

_mask = None
_strokes = {"index": None, "palm": None}
_face = None


def reset():
    """Drop the mask so the next visit starts as clear glass. Mode enter and leave only."""
    global _mask
    _mask = None
    _strokes["index"] = None
    _strokes["palm"] = None


def _ensure(height, width):
    """Keep the existing glass. A size change scales it. A new mask is only the first frame."""
    global _mask
    if _mask is not None and _mask.shape == (height, width):
        return
    if _mask is not None:
        _mask = cv2.resize(_mask, (width, height), interpolation=cv2.INTER_LINEAR)
        return
    _mask = np.zeros((height, width), dtype=np.float32)


def _brush_radius(width, height):
    """Small eraser. About a fingertip, not a palm."""
    return max(6.0, min(width, height) * 0.008)


def _palm_radius(width, height):
    """Open hand. A wider wipe, still only the glass under the palm."""
    return max(28.0, min(width, height) * 0.055)


def _wipe(mask, x0, y0, x1, y1, radius):
    height, width = mask.shape
    steps = max(1, int(np.hypot(x1 - x0, y1 - y0) / max(1.0, radius * 0.35)))
    for step in range(steps + 1):
        blend = step / steps
        cx = x0 + (x1 - x0) * blend
        cy = y0 + (y1 - y0) * blend
        xa = max(0, int(cx - radius))
        xb = min(width, int(cx + radius) + 1)
        ya = max(0, int(cy - radius))
        yb = min(height, int(cy + radius) + 1)
        if xb <= xa or yb <= ya:
            continue
        yy, xx = np.ogrid[ya:yb, xa:xb]
        dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
        keep = 1.0 - np.clip(1.0 - dist / radius, 0, 1) * 0.92
        mask[ya:yb, xa:xb] *= keep.astype(np.float32)


def _span(lms, a, b):
    return float(np.hypot(lms[a].x - lms[b].x, lms[a].y - lms[b].y))


def _extended(lms, tip, mcp):
    """Tip is well past the knuckle, in any direction. A sideways wipe still counts."""
    tip_reach = _span(lms, tip, 0)
    knuckle = max(0.04, _span(lms, mcp, 0))
    return tip_reach > knuckle * 1.28 and tip_reach > 0.16


def _curled(lms, tip, mcp):
    """Tip has come back toward the wrist. Image-up is not required."""
    tip_reach = _span(lms, tip, 0)
    knuckle = max(0.04, _span(lms, mcp, 0))
    return tip_reach < knuckle * 1.12


def _index_only(lms):
    """One index finger out. The other fingers stay curled. That is the eraser."""
    return (
        _extended(lms, 8, 5)
        and _curled(lms, 12, 9)
        and _curled(lms, 16, 13)
        and _curled(lms, 20, 17)
    )


def _open_hand(lms):
    """Four fingers out and the thumb away from the palm."""
    fingers = all(_extended(lms, tip, mcp) for tip, mcp in ((8, 5), (12, 9), (16, 13), (20, 17)))
    thumb_out = _span(lms, 4, 5) > 0.06 or _extended(lms, 4, 2)
    return fingers and thumb_out


def _breath_gain(gap, mouth, cheek):
    """Fog added across the whole glass this frame. Shut or far mouths add none."""
    mouth = max(float(mouth), 1e-4)
    if float(gap) / mouth < 0.32:
        return 0.0
    if float(cheek) < 0.20 and mouth < 0.07:
        return 0.0
    closeness = min(1.0, max(float(cheek), mouth * 1.8) / 0.42)
    return float(0.85 + 0.15 * closeness)


def _fog_layer(frame):
    height, width = frame.shape[:2]
    small = cv2.resize(frame, (max(1, width // 4), max(1, height // 4)), interpolation=cv2.INTER_AREA)
    small = cv2.GaussianBlur(small, (0, 0), 3)
    blurred = cv2.resize(small, (width, height), interpolation=cv2.INTER_LINEAR)
    blurred = cv2.convertScaleAbs(blurred, alpha=1.05, beta=6)
    tint = np.empty_like(blurred)
    tint[:] = (228, 218, 205)
    return cv2.addWeighted(blurred, 0.62, tint, 0.38, 0)


def _one_hand(results):
    """The gesture needs exactly one hand. Two hands do nothing."""
    hands = results.multi_hand_landmarks if results is not None else None
    if not hands or len(hands) != 1:
        return None
    return hands[0].landmark


def _classify(landmarks):
    """index, open, or None. None keeps every existing mark."""
    if landmarks is None:
        return None
    if _index_only(landmarks):
        return "index"
    if _open_hand(landmarks):
        return "open"
    return None


def _face_mesh():
    global _face
    if _face is not None:
        return _face
    try:
        from mediapipe.python.solutions.face_mesh import FaceMesh
        _face = FaceMesh(
            static_image_mode=False,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
    except Exception as exc:
        print(f"Fog mouth unavailable: {exc}")
        _face = False
    return _face


def _mouth_breath(frame, mask):
    """Open mouth close to the lens fogs the whole glass quickly."""
    mesh = _face_mesh()
    if mesh is None or mesh is False or mask is None:
        return
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    rgb.flags.writeable = False
    found = mesh.process(rgb)
    faces = getattr(found, "multi_face_landmarks", None)
    if not faces:
        return
    landmarks = faces[0].landmark
    upper, lower = landmarks[13], landmarks[14]
    left, right = landmarks[78], landmarks[308]
    gap = abs(lower.y - upper.y)
    mouth = float(np.hypot(left.x - right.x, left.y - right.y))
    cheek = float(np.hypot(landmarks[234].x - landmarks[454].x, landmarks[234].y - landmarks[454].y))
    gain = _breath_gain(gap, mouth, cheek)
    if gain <= 0.0:
        return
    mask += np.float32(gain)
    np.clip(mask, 0.0, 1.0, out=mask)


def _palm_point(landmarks, width, height):
    ids = (0, 5, 9, 13, 17)
    x = sum(landmarks[i].x for i in ids) / len(ids)
    y = sum(landmarks[i].y for i in ids) / len(ids)
    return x * width, y * height


def _follow(kind, point, radius, mask):
    """Continue one wipe path. A jump starts a new patch and does not refill fog."""
    previous = _strokes.get(kind)
    if previous is None or np.hypot(point[0] - previous[0], point[1] - previous[1]) > radius * 6:
        origin = point
    else:
        origin = previous
        point = (
            previous[0] + 0.45 * (point[0] - previous[0]),
            previous[1] + 0.45 * (point[1] - previous[1]),
        )
    _strokes[kind] = point
    _wipe(mask, origin[0], origin[1], point[0], point[1], radius)
    return point


def draw_fog_overlay(frame, results):
    """Composite fog onto frame. Index wipes small. Open hand wipes wide.

    The mask is created once. A close open mouth adds thick fog across the
    whole glass. A fist does not refill a wipe.
    """
    if frame is None or frame.size == 0:
        return frame
    height, width = frame.shape[:2]
    _ensure(height, width)
    fog = _fog_layer(frame)
    mask = _mask
    if mask is None:
        return frame
    _mouth_breath(frame, mask)
    hand = _one_hand(results)
    pose = _classify(hand)
    if pose == "index":
        _strokes["palm"] = None
        tip = (float(hand[8].x * width), float(hand[8].y * height))
        brush = _brush_radius(width, height)
        point = _follow("index", tip, brush, mask)
        cv2.circle(frame, (int(point[0]), int(point[1])), max(3, int(round(brush))), (255, 255, 255), 1)
    elif pose == "open":
        _strokes["index"] = None
        palm = _palm_point(hand, width, height)
        brush = _palm_radius(width, height)
        point = _follow("palm", palm, brush, mask)
        cv2.circle(frame, (int(point[0]), int(point[1])), max(8, int(round(brush * 0.35))), (255, 255, 255), 1)
    else:
        _strokes["index"] = None
        _strokes["palm"] = None
    np.clip(mask, 0, 1, out=mask)
    weight = mask[..., None]
    mixed = fog.astype(np.float32) * weight + frame.astype(np.float32) * (1.0 - weight)
    frame[:] = mixed.astype(np.uint8)
    return frame
