"""Arissa on the hologram. Standby is the sit-up, played once, then held.

A finger snap or the word dance cycles rumba, salsa, then twerk.
The words rumba, salsa, and twerk play that clip.
Stop dance and standby start the sit-up again. Pinch plus the other index orbits.
asmamir.glb is not shown.
"""

import threading
import time
from pathlib import Path

_FOLDER = Path(__file__).resolve().parent / "hologram"
_SIT = "asmamir_situp_to_idle.fbx"
_ORDER = (
    "asmamir_rumba_dancing.fbx",
    "asmamir_salsa_dancing.fbx",
    "asmamir_dancing_twerk.fbx",
)

_mode = "sit"
_index = None
_sit = None
_dance = None
_dance_path = None
_started = 0.0
_loading = None
_lock = threading.Lock()
_snap_was = False
_snap_at = 0.0
_sit_started = False
_cache = None
_loaded = {}


def clip_paths():
    found = []
    for name in _ORDER:
        path = _FOLDER / name
        if path.is_file() and path.stat().st_size > 0:
            found.append(path)
    return found


def label_of(path):
    stem = path.stem.lower()
    if "situp" in stem or "sit" in stem:
        return "sit-up"
    if "rumba" in stem:
        return "rumba"
    if "salsa" in stem:
        return "salsa"
    if "twerk" in stem:
        return "twerk"
    return path.stem


def preload():
    """Load the sit-up in the background. The clock starts in begin_situp."""
    global _sit_started
    if _sit_started:
        return
    path = _FOLDER / _SIT
    if not path.is_file() or path.stat().st_size <= 0:
        print("Sit-up clip is missing.")
        return
    _sit_started = True

    def run():
        global _sit
        try:
            from web.hologram_fbx import Clip
            loaded = Clip(path)
            with _lock:
                _sit = loaded
                if _mode == "sit":
                    _started = time.time()
                    _cache = None
            print("Sit-up ready. It plays once, then holds.")
        except Exception as exc:
            print(f"Sit-up did not load ({path.name}): {exc}")

    threading.Thread(target=run, daemon=True).start()


def begin_situp():
    """Play the sit-up from the start. The last frame stays. Dance does not loop it."""
    global _mode, _started, _loading, _index, _cache
    with _lock:
        _mode = "sit"
        _started = time.time()
        _loading = None
        _index = None
        _cache = None
    print("Standby: sit-up once, then hold.")
    preload()


def leave():
    """Drop dance so another window can take the screen. The sit-up clock stays."""
    global _mode, _cache
    with _lock:
        if _mode != "dance":
            return
        _mode = "sit"
        _cache = None


def active():
    """True from the word dance or a snap until stop or standby."""
    with _lock:
        return _mode == "dance"


def _start(path):
    """Load one dance clip and loop it. The sit-up clock is not restarted here."""
    global _loading, _mode
    label = label_of(path)
    with _lock:
        _mode = "dance"
        _loading = path
    print(f"Dance: {label}")

    def run():
        global _dance, _dance_path, _started, _loading, _cache
        try:
            key = str(path)
            with _lock:
                loaded = _loaded.get(key)
            if loaded is None:
                from web.hologram_fbx import Clip
                loaded = Clip(path)
                with _lock:
                    loaded = _loaded.setdefault(key, loaded)
            with _lock:
                if _loading == path and _mode == "dance":
                    _dance = loaded
                    _dance_path = path
                    _started = time.time()
                    _cache = None
        except Exception as exc:
            print(f"Dance did not load ({path.name}): {exc}")
        finally:
            if _loading == path:
                _loading = None

    threading.Thread(target=run, daemon=True).start()
    return label


def cycle():
    """Advance rumba, salsa, twerk. Does not restart the sit-up clock while loading."""
    global _index
    items = clip_paths()
    if not items:
        print("Dance: no Arissa clips.")
        return ""
    _index = 0 if _index is None else (_index + 1) % len(items)
    return _start(items[_index])


def play(name):
    """Play rumba, salsa, or twerk. A longer sentence must not get here."""
    global _index
    wanted = (name or "").strip().lower()
    items = clip_paths()
    match = [(i, path) for i, path in enumerate(items) if label_of(path) == wanted]
    if not match:
        print(f"Dance: no {wanted} clip.")
        return ""
    _index, path = match[0]
    print(f"Dance file: {path.name}", flush=True)
    return _start(path)


def _posed(clip, seconds, loop):
    global _cache
    if loop:
        moment = round(float(seconds) % clip.duration, 2) if clip.duration else 0.0
    else:
        moment = round(min(max(float(seconds), 0.0), clip.duration), 2)
    key = (id(clip), loop, moment)
    if _cache is not None and _cache[0] == key:
        return _cache[1], _cache[2]
    pos, col = clip.mesh_at(seconds, loop=loop)
    _cache = (key, pos, col)
    return pos, col


def frame():
    """Orbit corners for the figure on screen. None until the sit-up has loaded."""
    with _lock:
        mode = _mode
        dance = _dance
        sit = _sit
        started = _started
    try:
        if mode == "dance":
            if dance is None:
                return None
            return _posed(dance, time.time() - started, True)
        if sit is None:
            return None
        return _posed(sit, time.time() - started, False)
    except Exception as exc:
        print(f"Hologram pose failed: {exc}")
        return None


def playing():
    with _lock:
        return _mode == "dance" and _dance is not None


def arrays():
    return frame()


def _dist(a, b):
    return float(((a.x - b.x) ** 2 + (a.y - b.y) ** 2) ** 0.5)


def _hands(hand_landmarks):
    hands = []
    for item in hand_landmarks or []:
        hands.append(item.landmark if hasattr(item, "landmark") else item)
    return hands


def _thumb_middle(lms):
    """Thumb tip on the middle finger, and not the thumb-index pinch orbit uses."""
    middle, index, _ring = _snap_ratios(lms)
    return middle < 0.42 and index > 0.55


def _snap_ratios(lms):
    """Thumb-tip distances divided by the palm width. Middle, index, then ring."""
    palm = max(_dist(lms[5], lms[17]), 0.04)
    return (
        _dist(lms[4], lms[12]) / palm,
        _dist(lms[4], lms[8]) / palm,
        _dist(lms[4], lms[16]) / palm,
    )


# Held preview uses the same thumb-to-middle test as wake. The pose already
# in frame when the rectangle is released is not a new snap.
_preview_was = False
_preview_at = 0.0
_preview_arm_at = 0.0
_preview_hist = []


def reset_preview_snap():
    """Call when the still is shown. The release pose must not start the heart."""
    global _preview_was, _preview_at, _preview_arm_at, _preview_hist, _motion_ring, _motion_was
    _preview_was = False
    _preview_at = 0.0
    _preview_hist = []
    _preview_arm_at = time.time() + 0.6
    _motion_ring = []
    _motion_was = False


def _preview_ratios(lms):
    """Thumb tip against the middle finger shaft, then the index tip."""
    palm = max(_dist(lms[5], lms[17]), 0.04)
    middle = min(_dist(lms[4], lms[joint]) for joint in (10, 11, 12)) / palm
    return middle, _dist(lms[4], lms[8]) / palm


def preview_snap(hand_landmarks):
    """A new thumb-to-middle close after the photo is held. Not the release pose."""
    global _preview_was, _preview_at, _preview_hist
    closest = None
    for lms in _hands(hand_landmarks):
        ratios = _preview_ratios(lms)
        if closest is None or ratios[0] < closest[0]:
            closest = ratios
    now = time.time()
    if closest is None:
        if now >= _preview_arm_at:
            _preview_was = False
        return False
    middle, index = closest
    _preview_hist.append((now, middle))
    _preview_hist = [item for item in _preview_hist if now - item[0] <= 0.35]
    earlier = [item[1] for item in _preview_hist if now - item[0] >= 0.05]
    drop = (max(earlier) - middle) if earlier else 0.0
    pinch = index + 0.10 < middle
    closed = (not pinch) and (middle < 0.55 or (middle < 0.90 and drop >= 0.20))
    if now < _preview_arm_at:
        _preview_was = closed
        return False
    edge = closed and not _preview_was and now - _preview_at >= 0.7
    _preview_was = closed
    if not edge:
        return False
    _preview_at = now
    print(
        f"Anime camera snap. thumb-middle {middle:.2f}, closed {drop:.2f}.",
        flush=True,
    )
    return True


_motion_ring = []
_motion_saved = None
_motion_was = False
_motion_at = 0.0


def note_motion(hand_landmarks):
    """Remember the latest thumb-to-middle distance for a recorded snap."""
    now = time.time()
    middle = None
    for lms in _hands(hand_landmarks):
        distance, _index = _preview_ratios(lms)
        if middle is None or distance < middle:
            middle = distance
    _motion_ring.append((now, 1.5 if middle is None else middle))
    cutoff = now - 1.2
    while _motion_ring and _motion_ring[0][0] < cutoff:
        del _motion_ring[0]


def take_motion():
    """The last 0.45 s of thumb-to-middle distances."""
    now = time.time()
    return [distance for stamp, distance in _motion_ring if now - stamp <= 0.45]


def _load_motions():
    global _motion_saved
    if _motion_saved is not None:
        return _motion_saved
    folder = Path(__file__).resolve().parent.parent / "models" / "snaps"
    loaded = []
    if folder.is_dir():
        for path in sorted(folder.glob("snap-*.motion")):
            try:
                values = [float(part) for part in path.read_text(encoding="utf-8").split() if part]
            except Exception:
                continue
            if len(values) >= 4:
                loaded.append(values)
    _motion_saved = loaded
    return loaded


def remember_motion_file():
    global _motion_saved
    _motion_saved = None


def matches_saved_motion():
    """True once when the thumb starts open and closes quickly, like snap-1.motion.

    A finger that is already on the middle finger when it enters does not count.
    The correlation score is logged, but a clear open-then-close still starts the fill.
    """
    global _motion_was, _motion_at
    now = time.time()
    if now < _preview_arm_at:
        _motion_was = False
        return False
    recent = [distance for stamp, distance in _motion_ring if now - stamp <= 0.45 and distance < 1.45]
    if len(recent) < 2:
        _motion_was = False
        return False
    closing = recent[0] - recent[-1]
    quick = max((recent[i] - recent[i + 1] for i in range(len(recent) - 1)), default=0.0)
    # snap-1.motion is open near 1.3, then one step down to 0.86.
    like_saved = recent[0] >= 0.95 and closing >= 0.25 and quick >= 0.18 and recent[-1] < recent[0]
    best = _motion_score(recent)
    hit = like_saved and not _motion_was and now - _motion_at >= 0.7
    _motion_was = like_saved
    if not hit:
        return False
    _motion_at = now
    print(
        f"Anime motion match {best:.2f}. Thumb {recent[0]:.2f} to {recent[-1]:.2f}.",
        flush=True,
    )
    return True


def latest_thumb_middle():
    """Newest thumb-middle distance, or None when no hand is in the recent ring."""
    for _stamp, distance in reversed(_motion_ring):
        if distance < 1.45:
            return distance
    return None


def hand_matches_snap1():
    """Whether the last half-second looks like snap-1.motion. Does not arm the fill."""
    now = time.time()
    recent = [distance for stamp, distance in _motion_ring if now - stamp <= 0.45 and distance < 1.45]
    if len(recent) < 2:
        return False
    closing = recent[0] - recent[-1]
    quick = max((recent[i] - recent[i + 1] for i in range(len(recent) - 1)), default=0.0)
    return recent[0] >= 0.95 and closing >= 0.25 and quick >= 0.18 and recent[-1] < recent[0]


def motion_score_now():
    now = time.time()
    recent = [distance for stamp, distance in _motion_ring if now - stamp <= 0.45 and distance < 1.45]
    if len(recent) < 2:
        return 0.0
    return _motion_score(recent)


def _motion_score(recent):
    best = 0.0
    live_mean = sum(recent) / len(recent)
    live = [value - live_mean for value in recent]
    live_norm = sum(value * value for value in live) ** 0.5 or 1.0
    for saved in _load_motions():
        sample = [value for value in saved if value < 1.45]
        if len(sample) < 3:
            continue
        sample_mean = sum(sample) / len(sample)
        centered = [value - sample_mean for value in sample]
        width = min(len(live), len(centered))
        score = abs(sum(live[i] * centered[i] for i in range(width)))
        sample_norm = sum(centered[i] * centered[i] for i in range(width)) ** 0.5 or 1.0
        best = max(best, score / (live_norm * sample_norm))
    return best


def feed_snap(hand_landmarks):
    """True on the frame a snap closes. Orbit's pinch-plus-index does not count."""
    global _snap_was, _snap_at
    from web import hologram_orbit

    hands = _hands(hand_landmarks)
    if hologram_orbit.engaged(hand_landmarks):
        _snap_was = any(_thumb_middle(lms) for lms in hands)
        return False
    closed = any(_thumb_middle(lms) for lms in hands)
    now = time.time()
    edge = closed and not _snap_was and now - _snap_at >= 0.7
    _snap_was = closed
    if not edge:
        return False
    _snap_at = now
    return True


preload()
