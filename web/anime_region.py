"""Capture box for anime screen stipple. Not the whole monitor.

The box is a hollow always-on-top frame. The grab uses only that rectangle.
The Anime board is pinned above the camera with HWND_TOPMOST.
"""

import ctypes
from ctypes import wintypes

import numpy as np

# SetWindowPos: keep the current size and place, do not steal focus, show it.
_SWP_SHOW = 0x0001 | 0x0002 | 0x0010 | 0x0040
_HWND_TOPMOST = ctypes.c_void_p(-1)

_WS_EX = 0x00080000 | 0x00000008 | 0x00000080 | 0x08000000 | 0x00000020
_WS_POPUP = 0x80000000
_SW_HIDE = 0
_SW_SHOWNA = 8


def _pointing_index(lms):
    """Index up, the other three fingers down."""
    if lms is None or len(lms) < 21:
        return False
    index_up = lms[8].y < lms[6].y - 0.02
    others_down = (
        lms[12].y > lms[10].y - 0.01
        and lms[16].y > lms[14].y - 0.01
        and lms[20].y > lms[18].y - 0.01
    )
    return bool(index_up and others_down)


def index_tips(results):
    """Two pointing index tips as normalized (x, y), or None."""
    lst = None if results is None else getattr(results, "multi_hand_landmarks", None)
    if not lst or len(lst) != 2:
        return None
    tips = []
    for hand in lst:
        lms = hand.landmark if hasattr(hand, "landmark") else hand
        if not _pointing_index(lms):
            return None
        tips.append((float(lms[8].x), float(lms[8].y)))
    return tips


def rect_from_tips(tip_a, tip_b, frame_w, frame_h, origin_x, origin_y, screen_w, screen_h, min_norm=0.08):
    """Image rect and screen rect between two fingertips. None if the box is tiny or the whole monitor."""
    left_n, right_n = sorted((float(tip_a[0]), float(tip_b[0])))
    top_n, bottom_n = sorted((float(tip_a[1]), float(tip_b[1])))
    if right_n - left_n < min_norm or bottom_n - top_n < min_norm:
        return None, None
    frame_w = max(1, int(frame_w))
    frame_h = max(1, int(frame_h))
    screen_w = max(1, int(screen_w))
    screen_h = max(1, int(screen_h))
    image_rect = (
        int(left_n * frame_w),
        int(top_n * frame_h),
        max(2, int((right_n - left_n) * frame_w)),
        max(2, int((bottom_n - top_n) * frame_h)),
    )
    mon_right = int(origin_x) + screen_w
    mon_bottom = int(origin_y) + screen_h
    left = min(max(int(origin_x) + int(left_n * screen_w), int(origin_x)), mon_right - 2)
    top = min(max(int(origin_y) + int(top_n * screen_h), int(origin_y)), mon_bottom - 2)
    right = min(max(int(origin_x) + int(right_n * screen_w), left + 2), mon_right)
    bottom = min(max(int(origin_y) + int(bottom_n * screen_h), top + 2), mon_bottom)
    width = right - left
    height = bottom - top
    if width < 2 or height < 2 or (width >= screen_w and height >= screen_h):
        return None, None
    return image_rect, (left, top, width, height)


def _near(a, b, tol):
    return all(abs(int(a[i]) - int(b[i])) <= tol for i in range(4))


class Placement:
    """Live finger box. Capture once when the same rectangle holds still."""

    def __init__(self, hold=0.4, tol=24):
        self.hold = hold
        self.tol = tol
        self._last = None
        self._since = 0.0
        self._locked = None

    def reset(self):
        self._last = None
        self._since = 0.0
        self._locked = None

    def release(self):
        """A new placement may capture again."""
        self._locked = None
        self._last = None
        self._since = 0.0

    def update(self, rect, now):
        """Return the screen rect on the frame it locks. None while it is still moving."""
        if rect is None:
            self._last = None
            self._since = 0.0
            self._locked = None
            return None
        if self._locked is not None and _near(rect, self._locked, self.tol):
            return None
        if self._locked is not None:
            self._locked = None
        if self._last is not None and _near(rect, self._last, self.tol):
            if now - self._since >= self.hold:
                self._locked = tuple(int(v) for v in rect)
                return self._locked
            return None
        self._last = tuple(int(v) for v in rect)
        self._since = float(now)
        return None


def capture_box(origin_x, origin_y, screen_w, screen_h):
    """A centered rectangle strictly inside the monitor. Never the full screen."""
    screen_w = int(screen_w)
    screen_h = int(screen_h)
    if screen_w < 2 or screen_h < 2:
        return int(origin_x), int(origin_y), 1, 1
    width = min(960, max(240, (screen_w * 50) // 100))
    height = min(540, max(180, (screen_h * 45) // 100))
    max_w = max(1, screen_w - max(2, (screen_w * 16) // 100))
    max_h = max(1, screen_h - max(2, (screen_h * 16) // 100))
    width = min(width, max_w)
    height = min(height, max_h)
    left = int(origin_x) + max(0, (screen_w - width) // 2)
    top = int(origin_y) + max(0, (screen_h - height) // 2)
    return left, top, int(width), int(height)


def primary_bounds():
    """Primary monitor origin and size, matching the grab coordinates."""
    try:
        import mss
        with mss.mss() as sct:
            mon = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
            width = int(mon["width"])
            height = int(mon["height"])
            if width > 1 and height > 1:
                return int(mon["left"]), int(mon["top"]), width, height
    except Exception as exc:
        print(f"Anime box: monitor list skipped ({exc})")
    user32 = ctypes.windll.user32
    return 0, 0, int(user32.GetSystemMetrics(0)), int(user32.GetSystemMetrics(1))


def border_bgra(width, height, thickness=10):
    """Hollow sky-blue frame. The middle is transparent so the desktop shows through."""
    width = max(2, int(width))
    height = max(2, int(height))
    thickness = max(2, min(int(thickness), width // 2, height // 2))
    image = np.zeros((height, width, 4), dtype=np.uint8)
    # Premultiplied BGRA. #38bdf8 at full alpha.
    image[:thickness, :, :] = (248, 189, 56, 255)
    image[-thickness:, :, :] = (248, 189, 56, 255)
    image[:, :thickness, :] = (248, 189, 56, 255)
    image[:, -thickness:, :] = (248, 189, 56, 255)
    return image


def raise_topmost(user32, hwnd):
    """HWND_TOPMOST without moving, resizing, or activating. False if there is no window."""
    if not hwnd:
        return False
    setpos = user32.SetWindowPos
    setpos.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        ctypes.c_uint,
    ]
    setpos.restype = ctypes.c_int
    return bool(setpos(ctypes.c_void_p(hwnd), _HWND_TOPMOST, 0, 0, 0, 0, _SWP_SHOW))


def hwnd_by_title(user32, title):
    find = user32.FindWindowW
    find.restype = ctypes.c_void_p
    find.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
    return find(None, title) or 0


def _user32_dll(existing=None):
    return existing or ctypes.WinDLL("user32", use_last_error=True)


def _gdi32_dll(existing=None):
    return existing or ctypes.WinDLL("gdi32", use_last_error=True)


def _bind_handles(user32, gdi32):
    """HDC, HWND, and HBITMAP are pointer-sized. A bare int becomes a 32-bit c_int and overflows."""
    user32.GetDC.argtypes = [ctypes.c_void_p]
    user32.GetDC.restype = ctypes.c_void_p
    user32.ReleaseDC.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    user32.ReleaseDC.restype = ctypes.c_int
    user32.ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
    user32.ShowWindow.restype = ctypes.c_int
    user32.DestroyWindow.argtypes = [ctypes.c_void_p]
    user32.DestroyWindow.restype = ctypes.c_int
    gdi32.CreateCompatibleDC.argtypes = [ctypes.c_void_p]
    gdi32.CreateCompatibleDC.restype = ctypes.c_void_p
    gdi32.DeleteDC.argtypes = [ctypes.c_void_p]
    gdi32.DeleteDC.restype = ctypes.c_int
    gdi32.SelectObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    gdi32.SelectObject.restype = ctypes.c_void_p
    gdi32.DeleteObject.argtypes = [ctypes.c_void_p]
    gdi32.DeleteObject.restype = ctypes.c_int


class RegionFrame:
    """Always-on-top hollow rectangle. Camera thread only."""

    def __init__(self):
        self.hwnd = 0
        self.rect = None
        self.visible = False
        self._hdc_screen = None
        self._hdc_mem = None
        self._bitmap = None
        self._old = None
        self._user32 = None
        self._gdi32 = None

    def show(self, rect, user32=None, gdi32=None):
        left, top, width, height = (int(v) for v in rect)
        self._user32 = _user32_dll(user32)
        self._gdi32 = _gdi32_dll(gdi32)
        _bind_handles(self._user32, self._gdi32)
        if not self.hwnd:
            self.hwnd = self._create(left, top, width, height)
        if not self.hwnd:
            return False
        if self.rect != (left, top, width, height) or self._bitmap is None:
            self._paint(left, top, width, height)
        else:
            self._place(left, top, width, height)
        self._user32.ShowWindow(ctypes.c_void_p(self.hwnd), _SW_SHOWNA)
        raise_topmost(self._user32, self.hwnd)
        self.rect = (left, top, width, height)
        self.visible = True
        return True

    def hide(self):
        self.visible = False
        if self.hwnd and self._user32 is not None:
            _bind_handles(self._user32, _gdi32_dll(self._gdi32))
            self._user32.ShowWindow(ctypes.c_void_p(self.hwnd), _SW_HIDE)

    def raise_topmost(self):
        if self.visible and self.hwnd and self._user32 is not None:
            raise_topmost(self._user32, self.hwnd)

    def close(self):
        user32 = self._user32
        gdi32 = self._gdi32
        if user32 is None or gdi32 is None:
            self.hwnd = 0
            self.visible = False
            return
        _bind_handles(user32, gdi32)
        if self._hdc_mem and self._old:
            gdi32.SelectObject(self._hdc_mem, self._old)
        if self._bitmap:
            gdi32.DeleteObject(self._bitmap)
        if self._hdc_mem:
            gdi32.DeleteDC(self._hdc_mem)
        if self._hdc_screen:
            user32.ReleaseDC(0, self._hdc_screen)
        if self.hwnd:
            user32.DestroyWindow(ctypes.c_void_p(self.hwnd))
        self.hwnd = 0
        self.rect = None
        self.visible = False
        self._hdc_screen = None
        self._hdc_mem = None
        self._bitmap = None
        self._old = None

    def _create(self, left, top, width, height):
        user32 = self._user32
        if user32 is None:
            return 0
        create = user32.CreateWindowExW
        create.restype = ctypes.c_void_p
        create.argtypes = [
            ctypes.c_uint, wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.c_uint,
            ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
        ]
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.GetModuleHandleW.restype = ctypes.c_void_p
        kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
        hwnd = create(
            _WS_EX, "Static", "Anime capture",
            _WS_POPUP,
            left, top, width, height,
            None, None, kernel32.GetModuleHandleW(None), None,
        )
        if not hwnd:
            print("Anime box: could not open the capture frame.")
        return hwnd or 0

    def _paint(self, left, top, width, height):
        user32 = self._user32
        gdi32 = self._gdi32
        if user32 is None or gdi32 is None:
            return
        _bind_handles(user32, gdi32)
        pixels = np.ascontiguousarray(border_bgra(width, height))
        if self._hdc_mem and self._old:
            gdi32.SelectObject(self._hdc_mem, self._old)
            self._old = None
        if self._bitmap:
            gdi32.DeleteObject(self._bitmap)
            self._bitmap = None
        if self._hdc_screen is None:
            self._hdc_screen = user32.GetDC(0)
        if self._hdc_mem is None:
            self._hdc_mem = gdi32.CreateCompatibleDC(self._hdc_screen)

        class BITMAPINFOHEADER(ctypes.Structure):
            _fields_ = [
                ("biSize", wintypes.DWORD),
                ("biWidth", ctypes.c_long),
                ("biHeight", ctypes.c_long),
                ("biPlanes", wintypes.WORD),
                ("biBitCount", wintypes.WORD),
                ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD),
                ("biXPelsPerMeter", ctypes.c_long),
                ("biYPelsPerMeter", ctypes.c_long),
                ("biClrUsed", wintypes.DWORD),
                ("biClrImportant", wintypes.DWORD),
            ]

        info = BITMAPINFOHEADER()
        info.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        info.biWidth = width
        info.biHeight = -height
        info.biPlanes = 1
        info.biBitCount = 32
        info.biCompression = 0
        bits = ctypes.c_void_p()
        gdi32.CreateDIBSection.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(BITMAPINFOHEADER),
            ctypes.c_uint,
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.c_void_p,
            ctypes.c_uint,
        ]
        gdi32.CreateDIBSection.restype = ctypes.c_void_p
        self._bitmap = gdi32.CreateDIBSection(
            self._hdc_screen, ctypes.byref(info), 0, ctypes.byref(bits), None, 0,
        )
        self._old = gdi32.SelectObject(self._hdc_mem, self._bitmap)
        ctypes.memmove(bits, pixels.ctypes.data, pixels.nbytes)

        class POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

        class SIZE(ctypes.Structure):
            _fields_ = [("cx", ctypes.c_long), ("cy", ctypes.c_long)]

        class BLENDFUNCTION(ctypes.Structure):
            _fields_ = [
                ("BlendOp", ctypes.c_byte),
                ("BlendFlags", ctypes.c_byte),
                ("SourceConstantAlpha", ctypes.c_byte),
                ("AlphaFormat", ctypes.c_byte),
            ]

        dst = POINT(left, top)
        size = SIZE(width, height)
        src = POINT(0, 0)
        blend = BLENDFUNCTION(0, 0, 255, 1)
        user32.UpdateLayeredWindow.argtypes = [
            ctypes.c_void_p, ctypes.c_void_p,
            ctypes.POINTER(POINT), ctypes.POINTER(SIZE),
            ctypes.c_void_p, ctypes.POINTER(POINT),
            ctypes.c_uint, ctypes.POINTER(BLENDFUNCTION), ctypes.c_uint,
        ]
        user32.UpdateLayeredWindow.restype = ctypes.c_int
        user32.UpdateLayeredWindow(
            ctypes.c_void_p(self.hwnd), self._hdc_screen,
            ctypes.byref(dst), ctypes.byref(size),
            self._hdc_mem, ctypes.byref(src),
            0, ctypes.byref(blend), 0x02,
        )
        self.rect = (left, top, width, height)

    def _place(self, left, top, width, height):
        user32 = self._user32
        if user32 is None:
            return
        setpos = user32.SetWindowPos
        setpos.argtypes = [
            ctypes.c_void_p, ctypes.c_void_p,
            ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
            ctypes.c_uint,
        ]
        setpos.restype = ctypes.c_int
        setpos(ctypes.c_void_p(self.hwnd), _HWND_TOPMOST, left, top, width, height, 0x0040)
