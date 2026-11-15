"""Close one matching Chrome tab. Does not quit Chrome or change overlay mode.

Voice: close youtube / close you tube, close airbus, close desert eagle.
The small English model hears "youtube" as "you tube".
"""

import time

_COOLDOWN = 1.2
_LAST = 0.0
_CHROME = "Chrome_WidgetWin_1"

_PHRASES = {
    "close youtube": "youtube",
    "close you tube": "youtube",
    "close airbus": "airbus",
    "close desert eagle": "desert eagle",
}


def kind_from(command):
    """youtube, airbus, desert eagle, or empty. Exact phrase only."""
    if not command:
        return ""
    text = " ".join(command.replace("-", " ").lower().split())
    return _PHRASES.get(text, "")


def _matches(title, kind):
    low = (title or "").lower()
    if low in {"", "asmamir computer vision"}:
        return False
    if kind == "youtube":
        return "youtube" in low or "you tube" in low
    if kind == "airbus":
        return "airbus" in low
    if kind == "desert eagle":
        return "desert eagle" in low
    return False


def _title(hwnd, user32):
    length = user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ""
    buffer = __import__("ctypes").create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value or ""


def _class_name(hwnd, user32):
    import ctypes
    buffer = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buffer, 256)
    return buffer.value or ""


def _find(kind, user32):
    import ctypes
    from ctypes import wintypes

    found = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def visit(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        if _class_name(hwnd, user32) != _CHROME:
            return True
        title = _title(hwnd, user32)
        if _matches(title, kind):
            found.append(hwnd)
            return False
        return True

    user32.EnumWindows(visit, 0)
    return found[0] if found else None


def _focus(user32, hwnd):
    user32.ShowWindow(hwnd, 9)
    user32.keybd_event(0x12, 0, 0, 0)
    user32.SetForegroundWindow(hwnd)
    user32.keybd_event(0x12, 0, 2, 0)
    time.sleep(0.2)
    return user32.GetForegroundWindow() == hwnd


def _close_key(user32):
    """Ctrl+W closes the active Chrome tab. Nothing else is typed."""
    user32.keybd_event(0x11, 0, 0, 0)
    user32.keybd_event(0x57, 0, 0, 0)
    user32.keybd_event(0x57, 0, 2, 0)
    user32.keybd_event(0x11, 0, 2, 0)


def close_kind(kind, *, user32=None, sleeper=None):
    """Close one Chrome tab whose window title matches. False if none is open."""
    global _LAST
    if kind not in {"youtube", "airbus", "desert eagle"}:
        return False
    now = time.monotonic()
    if now - _LAST < _COOLDOWN:
        return True
    import ctypes
    win = user32 if user32 is not None else ctypes.windll.user32
    hwnd = _find(kind, win)
    if not hwnd:
        print(f"Close {kind}: no Chrome tab.")
        return False
    if not _focus(win, hwnd):
        print(f"Close {kind}: Chrome did not come forward.")
        return False
    if sleeper:
        sleeper(0.05)
    _close_key(win)
    _LAST = now
    print(f"Close {kind}: Chrome tab closed.")
    return True


def close_command(command, *, user32=None, sleeper=None):
    kind = kind_from(command)
    if not kind:
        return False
    return close_kind(kind, user32=user32, sleeper=sleeper)
