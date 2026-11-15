"""Index fingertip moves the real Windows cursor. Pinch clicks. Two fingers scroll.

SetCursorPos places the OS cursor on the virtual desktop (every monitor, any app,
including YouTube and WeChat). The camera picture is not the cursor. While this
is armed the fullscreen overlay lets clicks through, so a pinch is a real left
click (YouTube play/pause when the cursor is on the player) and a two-finger
vertical drag is a real mouse-wheel scroll. Hands only. Does not type.
"""

import ctypes
import time
from ctypes import wintypes

PINCH_ON = 0.38
PINCH_OFF = 0.58
CLICK_COOLDOWN = 0.45
SCROLL_PIXELS = 28

_armed = False
_voice = False
_suppressed = False
_pinched = False
_smooth = None
_last_click = 0.0
_scroll_y = None
_scroll_acc = 0.0
_overlay_style = None
_cursor_forced = False
_scan_at = 0.0
_youtube_open = False

_user32 = ctypes.windll.user32
if ctypes.sizeof(ctypes.c_void_p) >= 8:
    _get_long = _user32.GetWindowLongPtrW
    _set_long = _user32.SetWindowLongPtrW
    _long = ctypes.c_ssize_t
else:
    _get_long = _user32.GetWindowLongW
    _set_long = _user32.SetWindowLongW
    _long = ctypes.c_long
_get_long.restype = _long
_get_long.argtypes = [wintypes.HWND, ctypes.c_int]
_set_long.restype = _long
_set_long.argtypes = [wintypes.HWND, ctypes.c_int, _long]
_user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
_user32.SetCursorPos.restype = wintypes.BOOL
_user32.ShowCursor.argtypes = [wintypes.BOOL]
_user32.ShowCursor.restype = ctypes.c_int
_user32.mouse_event.argtypes = [
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.DWORD,
    ctypes.c_ulonglong,
]


class _CURSORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("hCursor", wintypes.HANDLE),
        ("ptScreenPos", wintypes.POINT),
    ]


def arm():
    """Voice 'mouse' / 'kursor'. Stays on after YouTube closes until 'stop mouse'."""
    global _armed, _voice, _suppressed
    _voice = True
    _suppressed = False
    _armed = True
    _show_os_cursor()
    _set_overlay_clickthrough(True)


def disarm():
    """Drop the cursor. Does not block a later YouTube window from arming it."""
    global _armed, _pinched, _smooth, _scroll_y, _scroll_acc
    _armed = False
    _pinched = False
    _smooth = None
    _scroll_y = None
    _scroll_acc = 0.0
    _set_overlay_clickthrough(False)


def suppress():
    """Voice off. YouTube does not turn the cursor back on until 'mouse'."""
    global _voice, _suppressed
    _voice = False
    _suppressed = True
    disarm()


def armed():
    return _armed


def youtube_showing():
    """True after the last scan saw a visible YouTube window."""
    return _youtube_open


def wants_on(command):
    text = " ".join(command.replace("-", " ").lower().split())
    return text in {"mouse", "kursor", "hand mouse", "gerakkan mouse", "gerakkan kursor"}


def wants_off(command):
    text = " ".join(command.replace("-", " ").lower().split())
    return text in {
        "stop mouse",
        "stop kursor",
        "lepas mouse",
        "lepas kursor",
        "berhenti mouse",
        "berhenti kursor",
    }


def _pinch_ratio(lms, width, height):
    span = max(22.0, float(((lms[5].x - lms[17].x) * width) ** 2 + ((lms[5].y - lms[17].y) * height) ** 2) ** 0.5)
    dist = float(((lms[4].x - lms[8].x) * width) ** 2 + ((lms[4].y - lms[8].y) * height) ** 2) ** 0.5
    return dist / span


def _two_fingers(lms):
    """Index and middle up, ring down. The scroll pose, not a pinch."""
    index_up = lms[8].y < lms[6].y - 0.02
    middle_up = lms[12].y < lms[10].y - 0.02
    ring_down = lms[16].y > lms[14].y - 0.008
    return index_up and middle_up and ring_down


def _virtual_screen():
    left = int(_user32.GetSystemMetrics(76))
    top = int(_user32.GetSystemMetrics(77))
    width = int(_user32.GetSystemMetrics(78))
    height = int(_user32.GetSystemMetrics(79))
    if width <= 0 or height <= 0:
        left = top = 0
        width = int(_user32.GetSystemMetrics(0)) or 1
        height = int(_user32.GetSystemMetrics(1)) or 1
    return left, top, width, height


def map_point(nx, ny, screen):
    """Camera 0..1 (un-mirrored, x right) to a pixel on the virtual desktop."""
    left, top, width, height = screen
    ax = min(1.0, max(0.0, (float(nx) - 0.12) / 0.76))
    ay = min(1.0, max(0.0, (float(ny) - 0.12) / 0.76))
    x = int(left + ax * max(1, width - 1))
    y = int(top + ay * max(1, height - 1))
    return x, y


def _overlay_hwnd():
    found = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def visit(hwnd, _lparam):
        if not _user32.IsWindowVisible(hwnd):
            return True
        length = _user32.GetWindowTextLengthW(hwnd)
        buffer = ctypes.create_unicode_buffer(length + 1)
        _user32.GetWindowTextW(hwnd, buffer, length + 1)
        if buffer.value == "Asmamir Computer Vision AI Assistant":
            found.append(hwnd)
            return False
        return True

    _user32.EnumWindows(visit, 0)
    return found[0] if found else None


def youtube_hwnd():
    """Visible window whose title contains YouTube, or 0."""
    found = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def visit(hwnd, _lparam):
        if not _user32.IsWindowVisible(hwnd):
            return True
        length = _user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buffer = ctypes.create_unicode_buffer(length + 1)
        _user32.GetWindowTextW(hwnd, buffer, length + 1)
        title = buffer.value or ""
        if "youtube" in title.lower() and title != "Asmamir Computer Vision AI Assistant":
            found.append(hwnd)
            return False
        return True

    _user32.EnumWindows(visit, 0)
    return found[0] if found else 0


def youtube_window_open():
    """True when some visible window title contains YouTube. Not our overlay."""
    return bool(youtube_hwnd())


def watch_youtube_window(finder=None):
    """Arm while a YouTube window is visible. Close it and the cursor stops, unless voice armed it."""
    global _scan_at, _armed, _youtube_open
    if _suppressed:
        _youtube_open = False
        return False
    now = time.monotonic()
    if now - _scan_at >= 0.8:
        _scan_at = now
        _youtube_open = bool(youtube_window_open() if finder is None else finder())
    if _voice:
        if not _armed:
            _armed = True
            _show_os_cursor()
            _set_overlay_clickthrough(True)
        return True
    if _youtube_open:
        if not _armed:
            _armed = True
            _show_os_cursor()
            _set_overlay_clickthrough(True)
            print("Pointer armed: YouTube is open. Index moves the cursor. Pinch plays and pauses.")
        return True
    if _armed:
        disarm()
    return False


def needs_camera(finder=None):
    """The hand cursor needs the webcam: voice arm, or a visible YouTube window."""
    if _suppressed:
        return False
    if _voice:
        return True
    return watch_youtube_window(finder)


def _show_os_cursor():
    """Windows draw the arrow. The fullscreen view can hide it more than once."""
    info = _CURSORINFO()
    info.cbSize = ctypes.sizeof(_CURSORINFO)
    for _ in range(32):
        showing = False
        if _user32.GetCursorInfo(ctypes.byref(info)):
            showing = bool(info.flags & 0x1)
        if showing:
            return
        if _user32.ShowCursor(True) >= 0:
            return


def _set_overlay_clickthrough(enable, hwnd=None, getter=None, setter=None):
    """Fullscreen camera must not eat the OS click or the wheel."""
    global _overlay_style
    target = _overlay_hwnd() if hwnd is None else hwnd
    if not target:
        return
    read = _get_long if getter is None else getter
    write = _set_long if setter is None else setter
    style = int(read(target, -20))
    layered = 0x00080000
    transparent = 0x00000020
    if enable:
        if style & transparent:
            return
        _overlay_style = style
        write(target, -20, style | layered | transparent)
    elif _overlay_style is not None:
        write(target, -20, _overlay_style)
        _overlay_style = None


def _left_click(click=None):
    if click is not None:
        click()
        return
    _user32.mouse_event(0x0002, 0, 0, 0, 0)
    _user32.mouse_event(0x0004, 0, 0, 0, 0)


def _wheel(delta, scroll=None):
    if scroll is not None:
        scroll(int(delta))
        return
    _user32.mouse_event(0x0800, 0, 0, ctypes.c_uint(int(delta) & 0xFFFFFFFF).value, 0)


def drive(frame, results, *, move=None, click=None, scroll=None, screen=None):
    """Move the Windows cursor from the index tip. Pinch clicks. Two fingers scroll.

    Returns 'move', 'click', 'scroll', or None. No-op until arm(). Does not type.
    Does not draw a stand-in cursor on the frame.
    """
    global _pinched, _smooth, _last_click, _scroll_y, _scroll_acc
    if not _armed or frame is None:
        return None
    _show_os_cursor()
    _set_overlay_clickthrough(True)
    hands = getattr(results, "multi_hand_landmarks", None) if results is not None else None
    if not hands:
        _pinched = False
        _smooth = None
        _scroll_y = None
        _scroll_acc = 0.0
        return None
    height, width = frame.shape[:2]
    landmarks = hands[0].landmark
    tip = landmarks[8]
    ratio = _pinch_ratio(landmarks, width, height)
    desktop = screen if screen is not None else _virtual_screen()
    pinched = ratio < PINCH_ON
    if not pinched and ratio > PINCH_OFF:
        _pinched = False
    scrolling = _two_fingers(landmarks) and not pinched
    mover = _user32.SetCursorPos if move is None else move
    action = None
    if scrolling:
        mid_y = (landmarks[8].y + landmarks[12].y) * 0.5
        _sy = map_point(tip.x, mid_y, desktop)[1]
        if _scroll_y is not None:
            _scroll_acc += _scroll_y - _sy
            notches = int(_scroll_acc / SCROLL_PIXELS)
            if notches:
                _scroll_acc -= notches * SCROLL_PIXELS
                _wheel(notches * 120, scroll)
                action = "scroll"
                print(f"Pointer scroll {notches}.")
        _scroll_y = _sy
        return action or "move"
    _scroll_y = None
    _scroll_acc = 0.0
    point = map_point(tip.x, tip.y, desktop)
    if _smooth is None:
        _smooth = point
    else:
        _smooth = (
            int(_smooth[0] + 0.55 * (point[0] - _smooth[0])),
            int(_smooth[1] + 0.55 * (point[1] - _smooth[1])),
        )
    mover(int(_smooth[0]), int(_smooth[1]))
    action = "move"
    now = time.monotonic()
    if pinched and not _pinched and now - _last_click >= CLICK_COOLDOWN:
        _pinched = True
        _last_click = now
        _left_click(click)
        action = "click"
        print(f"Pointer click at {_smooth}.")
    elif pinched:
        _pinched = True
    return action
