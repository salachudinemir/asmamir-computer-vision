"""Stipple on a black field. OpenCV + NumPy; no pygame.

Screen source is one capture-box still (mss, then PIL ImageGrab), not the whole monitor. Webcam is optional.
Density follows Rec.709 luminance (darker ink, near-white skipped), on a bounded
working image. Points are nudged toward local weight, jittered off the sample
grid, and revealed strongest-first. Ideas from prabinpebam/stipple-art (weighted
sampling, progressive marks, a small displacement). Not a copy of that repo.
"""

import time

import cv2
import numpy as np

GAMMA = 1.7
DENSITY = 0.4
WHITE_CUTOFF = 0.93
MAX_POINTS = 8500
BATCH = 85
RADIUS_START = 1
RADIUS_END = 5
SAMPLE_WIDTH = 640
JITTER = 0.42
REVEAL_S = 5.0

_points = None
_colors = None
_radii = None
_canvas = None
_drawn = 0
_size = None
_reveal_at = 0.0
_filled = False
_peace_was = False
_one_fist_was = False
_gesture_at = 0.0
GESTURE_COOLDOWN = 0.55


def _clear_picture():
    global _points, _colors, _radii, _canvas, _drawn, _size, _reveal_at, _filled
    _points = None
    _colors = None
    _radii = None
    _canvas = None
    _drawn = 0
    _size = None
    _reveal_at = 0.0
    _filled = False


def reset():
    """Drop the still and the gesture latch. Used when anime mode ends."""
    global _peace_was, _one_fist_was, _gesture_at
    _clear_picture()
    _peace_was = False
    _one_fist_was = False
    _gesture_at = 0.0


def _luma(bgr):
    """Rec.709 luminance in 0..1. Working image is already size-capped."""
    frame = bgr.astype(np.float32)
    return (0.2126 * frame[:, :, 2] + 0.7152 * frame[:, :, 1] + 0.0722 * frame[:, :, 0]) / 255.0


def _ink(luma):
    """Darker pixels weigh more. Letterbox black and near-white paper are dropped."""
    tone = np.clip(luma, 0.0, 1.0)
    ink = np.power(1.0 - tone, GAMMA)
    ink = np.where((tone >= 0.06) & (tone <= WHITE_CUTOFF), ink, 0.0)
    if ink.size:
        cutoff = float(np.quantile(ink, 1.0 - DENSITY))
        ink = np.where(ink >= cutoff, ink, 0.0)
    if float(ink.sum()) <= 1e-6:
        ink = np.where(tone >= 0.06, np.power(1.0 - tone, GAMMA), 0.0)
    return ink.astype(np.float32)


def _nudge(xs, ys, ink):
    """A few short steps toward higher local weight. Not a Voronoi solve."""
    height, width = ink.shape
    field = cv2.GaussianBlur(ink, (0, 0), 1.2)
    gx = cv2.Sobel(field, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(field, cv2.CV_32F, 0, 1, ksize=3)
    peak = float(max(np.max(np.abs(gx)), np.max(np.abs(gy)), 1e-6))
    gx = gx / peak
    gy = gy / peak
    for _ in range(3):
        xi = np.clip(np.rint(xs).astype(np.int32), 0, width - 1)
        yi = np.clip(np.rint(ys).astype(np.int32), 0, height - 1)
        xs = np.clip(xs + gx[yi, xi] * 0.85, 0, width - 1)
        ys = np.clip(ys + gy[yi, xi] * 0.85, 0, height - 1)
    return xs, ys


def _as_bgr(raw):
    if raw is None or getattr(raw, "size", 0) == 0:
        return None
    image = np.asarray(raw)
    if image.ndim == 2:
        return np.ascontiguousarray(cv2.cvtColor(image, cv2.COLOR_GRAY2BGR))
    if image.shape[2] == 4:
        return np.ascontiguousarray(image[:, :, :3])
    if image.shape[2] == 3:
        return np.ascontiguousarray(image)
    return None


def grab_region(left, top, width, height, grab=None):
    """BGR still of one rectangle. mss first, then PIL ImageGrab. None on failure.

    `grab`, when set, is `grab(left, top, width, height) -> array` and skips the desktop.
    """
    left, top, width, height = int(left), int(top), int(width), int(height)
    if width < 2 or height < 2:
        print("Anime screen: capture box is empty.")
        return None
    if grab is not None:
        image = _as_bgr(grab(left, top, width, height))
        if image is None or image.shape[1] > width + 2 or image.shape[0] > height + 2:
            print("Anime screen: grab was larger than the box, dropped.")
            return None
        return image
    try:
        import mss
        with mss.mss() as sct:
            raw = np.array(sct.grab({
                "left": left, "top": top, "width": width, "height": height,
            }), dtype=np.uint8)
        bgr = _as_bgr(raw)
        if bgr is None or bgr.shape[1] > width + 2 or bgr.shape[0] > height + 2:
            raise RuntimeError("mss region was larger than the box")
        print(f"Anime screen: box {width}x{height} at {left},{top}")
        return bgr
    except Exception as exc:
        print(f"Anime screen: mss skipped ({exc})")
    try:
        from PIL import ImageGrab
        shot = ImageGrab.grab(bbox=(left, top, left + width, top + height))
        rgb = np.array(shot)
        if rgb.ndim == 2:
            bgr = cv2.cvtColor(rgb, cv2.COLOR_GRAY2BGR)
        else:
            bgr = cv2.cvtColor(rgb[:, :, :3], cv2.COLOR_RGB2BGR)
        if bgr.shape[1] > width + 2 or bgr.shape[0] > height + 2:
            raise RuntimeError("ImageGrab region was larger than the box")
        print(f"Anime screen: box {width}x{height} at {left},{top}")
        return np.ascontiguousarray(bgr)
    except Exception as exc:
        print(f"Anime screen: ImageGrab failed ({exc})")
        return None


def _photo_box(luma):
    """Box of the picture under the toolbar, inside the dark letterbox."""
    height, width = luma.shape
    margin = max(2, int(width * 0.05))
    left_mean = luma[:, :margin].mean(axis=1)
    right_mean = luma[:, -margin:].mean(axis=1)
    side = (left_mean < 0.28) & (right_mean < 0.28)
    row = 0
    while row < height and side[row]:
        row += 1
    while row < height and not side[row]:
        row += 1
    if row >= int(height * 0.55) or row >= height - 8:
        row = 0
    stage = luma[row:]
    stage_h, stage_w = stage.shape
    if stage_h < 8 or stage_w < 8:
        return None
    corners = np.concatenate([
        stage[:6, :6].ravel(),
        stage[:6, -6:].ravel(),
        stage[-6:, :6].ravel(),
        stage[-6:, -6:].ravel(),
    ])
    level = float(np.median(corners))
    if level > 0.45:
        return None
    bar = np.abs(stage - level) <= 0.07
    content = np.where(bar, 0, 1).astype(np.uint8)
    count, _labels, stats, _centroids = cv2.connectedComponentsWithStats(content, 8)
    best = None
    for index in range(1, count):
        x, y, box_w, box_h, area = (int(v) for v in stats[index])
        if area < max(80, int(stage.size * 0.02)):
            continue
        if box_w > int(stage_w * 0.96) and box_h < int(stage_h * 0.08):
            continue
        if best is None or area > best[0]:
            best = (area, x, y, box_w, box_h)
    if best is None:
        return None
    _area, x, y, box_w, box_h = best
    return row + y, row + y + box_h, x, x + box_w


def crop_page_photo(bgr):
    """Browser chrome and the black letterbox come off. The photo remains."""
    image = _as_bgr(bgr)
    if image is None:
        return bgr
    height, width = image.shape[:2]
    if height < 60 or width < 60:
        return image
    sample_w = min(360, width)
    sample_h = max(1, int(round(height * (sample_w / float(width)))))
    small = cv2.resize(image, (sample_w, sample_h), interpolation=cv2.INTER_AREA)
    box = _photo_box(_luma(small))
    if box is None:
        return image
    top, bottom, left, right = box
    y0 = int(round(top * height / float(sample_h)))
    y1 = int(round(bottom * height / float(sample_h)))
    x0 = int(round(left * width / float(sample_w)))
    x1 = int(round(right * width / float(sample_w)))
    y0 = max(0, min(y0, height - 2))
    y1 = max(y0 + 2, min(height, y1))
    x0 = max(0, min(x0, width - 2))
    x1 = max(x0 + 2, min(width, x1))
    if (y1 - y0) < height * 0.15 or (x1 - x0) < width * 0.15:
        return image
    if y0 <= 2 and y1 >= height - 2 and x0 <= 2 and x1 >= width - 2:
        return image
    cropped = np.ascontiguousarray(image[y0:y1, x0:x1])
    print(f"Anime page {cropped.shape[1]}x{cropped.shape[0]} from {width}x{height}")
    return cropped


def begin(frame):
    """Freeze one still (screen or webcam) and pick stipple sites.

    Does not clear the peace/fist latch, so a held pose does not recapture
    again on the next frame.
    """
    _clear_picture()
    if frame is None or getattr(frame, "size", 0) == 0:
        return False
    src = frame
    if src.ndim == 2:
        src = cv2.cvtColor(src, cv2.COLOR_GRAY2BGR)
    h, w = src.shape[:2]
    scale = SAMPLE_WIDTH / w if w > SAMPLE_WIDTH else 1.0
    work = cv2.resize(src, (max(1, int(w * scale)), max(1, int(h * scale))), interpolation=cv2.INTER_AREA)
    luma = _luma(work)
    ink = _ink(luma)
    total = float(ink.sum())
    if total <= 1e-6:
        return False
    prob = ink / total
    n = int(prob.size)
    rng = np.random.default_rng()
    flat = prob.ravel()
    positive = int(np.count_nonzero(flat))
    k = min(MAX_POINTS, n, positive)
    if k <= 0:
        return False
    chosen = rng.choice(n, size=k, replace=False, p=flat)
    ys, xs = np.divmod(chosen, work.shape[1])
    xs = xs.astype(np.float32)
    ys = ys.astype(np.float32)
    weight = ink[ys.astype(np.int32), xs.astype(np.int32)].copy()
    xs, ys = _nudge(xs, ys, ink)
    xs = xs + rng.uniform(-JITTER, JITTER, size=k)
    ys = ys + rng.uniform(-JITTER, JITTER, size=k)
    wh, ww = work.shape[:2]
    xs = np.clip(xs, 0, ww - 1)
    ys = np.clip(ys, 0, wh - 1)
    order = np.lexsort((xs, ys))
    xs, ys, weight = xs[order], ys[order], weight[order]
    sx = w / ww
    sy = h / wh
    global _points, _colors, _radii, _canvas, _drawn, _size, _reveal_at, _filled
    _points = np.column_stack((xs * sx, ys * sy)).astype(np.float32)
    yi = np.clip(np.rint(ys).astype(np.int32), 0, wh - 1)
    xi = np.clip(np.rint(xs).astype(np.int32), 0, ww - 1)
    sampled = work[yi, xi]
    _colors = np.clip(sampled.astype(np.int16) + 18, 0, 255).astype(np.uint8)
    peak = float(weight.max()) + 1e-6
    span = weight / peak
    _radii = np.clip(np.rint(RADIUS_START + span * (RADIUS_END - RADIUS_START)), 1, RADIUS_END).astype(np.int32)
    _canvas = np.zeros((h, w, 3), dtype=np.uint8)
    _drawn = 0
    _size = (h, w)
    _reveal_at = time.time()
    _filled = False
    return True


def _finger_up(lms, tip, pip):
    return lms[tip].y < lms[pip].y - 0.018


def _finger_down(lms, tip, pip):
    return lms[tip].y > lms[pip].y - 0.008


def _peace(lms):
    """Index + middle up, ring + pinky down. Not a fist."""
    return (
        _finger_up(lms, 8, 6)
        and _finger_up(lms, 12, 10)
        and _finger_down(lms, 16, 14)
        and _finger_down(lms, 20, 18)
    )


def _fist(lms):
    """Four fingers curled. Peace and pointing hands are not fists."""
    if _peace(lms):
        return False
    folded = 0
    for tip, pip in ((8, 6), (12, 10), (16, 14), (20, 18)):
        if lms[tip].y > lms[pip].y - 0.015:
            folded += 1
    thumb_in = abs(lms[4].x - lms[5].x) < 0.08
    return folded >= 4 and thumb_in


def has_picture():
    return _canvas is not None


def poll_gestures(results):
    """Peace places the held desktop box. A fist does not. Two fists do nothing.

    The box itself is the two index fingertips. Airbus never sees these:
    app.py only calls this while anime_active.
    """
    global _peace_was, _one_fist_was, _gesture_at
    hands = []
    lst = results.multi_hand_landmarks if results is not None else None
    if lst:
        hands = [hand.landmark for hand in lst]
    any_peace = any(_peace(lms) for lms in hands)
    fist_n = sum(1 for lms in hands if _fist(lms))
    now = time.time()
    fired = None
    peace_edge = any_peace and not _peace_was
    if fist_n >= 2 and not any_peace:
        _peace_was = False
        _one_fist_was = False
        return None
    if peace_edge and now - _gesture_at >= GESTURE_COOLDOWN:
        fired = "place"
        _gesture_at = now
        print("Anime gesture: peace → place the box")
    _peace_was = any_peace
    _one_fist_was = fist_n == 1
    return fired


def _letterbox(canvas, frame):
    """Center the photo on black. The photo's aspect stays. Bars fill the rest."""
    frame_h, frame_w = frame.shape[:2]
    photo_h, photo_w = canvas.shape[:2]
    if photo_h == frame_h and photo_w == frame_w:
        frame[:] = canvas
        return frame
    scale = min(frame_w / photo_w, frame_h / photo_h)
    fitted_w = max(1, int(photo_w * scale))
    fitted_h = max(1, int(photo_h * scale))
    fitted = cv2.resize(canvas, (fitted_w, fitted_h), interpolation=cv2.INTER_NEAREST)
    frame[:] = 0
    x = (frame_w - fitted_w) // 2
    y = (frame_h - fitted_h) // 2
    frame[y:y + fitted_h, x:x + fitted_w] = fitted
    return frame


def draw_anime_overlay(frame, _results=None):
    """Fill the photo with dots from top to bottom, done in about five seconds."""
    global _canvas, _drawn, _filled
    if frame is None or getattr(frame, "size", 0) == 0:
        return frame
    if _points is None or _canvas is None:
        frame[:] = 0
        return frame
    elapsed = time.time() - _reveal_at
    target = len(_points) if elapsed >= REVEAL_S else int(len(_points) * elapsed / REVEAL_S)
    target = min(len(_points), max(_drawn, target))
    for i in range(_drawn, target):
        x = int(round(float(_points[i, 0])))
        y = int(round(float(_points[i, 1])))
        x = min(max(0, x), _canvas.shape[1] - 1)
        y = min(max(0, y), _canvas.shape[0] - 1)
        radius = int(_radii[i]) if _radii is not None else RADIUS_START
        color = tuple(int(c) for c in _colors[i])
        cv2.circle(_canvas, (x, y), radius, color, -1, lineType=cv2.LINE_8)
    _drawn = target
    if _drawn >= len(_points) and not _filled:
        _filled = True
        print("Anime stipple filled.")
    return _letterbox(_canvas, frame)
