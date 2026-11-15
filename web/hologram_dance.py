"""Arissa on the hologram. Standby is the sit-up, played once, then held.

A finger snap or the word dance cycles rumba, salsa, then twerk.
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


def cycle():
    """Advance rumba, salsa, twerk. Does not restart the sit-up clock while loading."""
    global _index, _loading, _mode
    items = clip_paths()
    if not items:
        print("Dance: no Arissa clips.")
        return ""
    _index = 0 if _index is None else (_index + 1) % len(items)
    path = items[_index]
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
    palm = max(_dist(lms[5], lms[17]), 0.04)
    middle = _dist(lms[4], lms[12]) / palm
    index = _dist(lms[4], lms[8]) / palm
    return middle < 0.42 and index > 0.55


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
