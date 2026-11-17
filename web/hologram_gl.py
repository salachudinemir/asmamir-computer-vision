"""Draw the standby mesh with yaw and pitch. The OpenCV window stays the picture.

A hidden OpenGL window only rasterizes. Angles are not clamped.
"""

import ctypes
from ctypes import wintypes

import numpy as np

_user32 = ctypes.WinDLL("user32", use_last_error=True)
_gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_gl = ctypes.WinDLL("opengl32", use_last_error=True)

_WNDPROC = ctypes.WINFUNCTYPE(
    ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
)
_user32.DefWindowProcW.restype = ctypes.c_ssize_t
_user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]


@_WNDPROC
def _wndproc(hwnd, msg, wparam, lparam):
    return _user32.DefWindowProcW(hwnd, msg, wparam, lparam)


class _WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT),
        ("lpfnWndProc", _WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HANDLE),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
    ]


class _PFD(ctypes.Structure):
    _fields_ = [
        ("nSize", wintypes.WORD),
        ("nVersion", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("iPixelType", wintypes.BYTE),
        ("cColorBits", wintypes.BYTE),
        ("cRedBits", wintypes.BYTE),
        ("cRedShift", wintypes.BYTE),
        ("cGreenBits", wintypes.BYTE),
        ("cGreenShift", wintypes.BYTE),
        ("cBlueBits", wintypes.BYTE),
        ("cBlueShift", wintypes.BYTE),
        ("cAlphaBits", wintypes.BYTE),
        ("cAlphaShift", wintypes.BYTE),
        ("cAccumBits", wintypes.BYTE),
        ("cAccumRedBits", wintypes.BYTE),
        ("cAccumGreenBits", wintypes.BYTE),
        ("cAccumBlueBits", wintypes.BYTE),
        ("cAccumAlphaBits", wintypes.BYTE),
        ("cDepthBits", wintypes.BYTE),
        ("cStencilBits", wintypes.BYTE),
        ("cAuxBuffers", wintypes.BYTE),
        ("iLayerType", wintypes.BYTE),
        ("bReserved", wintypes.BYTE),
        ("dwLayerMask", wintypes.DWORD),
        ("dwVisibleMask", wintypes.DWORD),
        ("dwDamageMask", wintypes.DWORD),
    ]


class _MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt_x", wintypes.LONG),
        ("pt_y", wintypes.LONG),
    ]


_hwnd = None
_dc = None
_ctx = None
_size = (0, 0)
_class_name = ctypes.create_unicode_buffer("AsmamirHologramGL")
_buffers = None
_uploaded = 0
_gen_buffers = None
_bind_buffer = None
_buffer_data = None

_GL_DEPTH_TEST = 0x0B71
_GL_LESS = 0x0201
_GL_COLOR_BUFFER_BIT = 0x00004000
_GL_DEPTH_BUFFER_BIT = 0x00000100
_GL_PROJECTION = 0x1701
_GL_MODELVIEW = 0x1700
_GL_TRIANGLES = 0x0004
_GL_FLOAT = 0x1406
_GL_UNSIGNED_BYTE = 0x1401
_GL_VERTEX_ARRAY = 0x8074
_GL_COLOR_ARRAY = 0x8076
_GL_BGR = 0x80E0
_GL_PACK_ALIGNMENT = 0x0D05

_kernel32.GetModuleHandleW.restype = wintypes.HINSTANCE
_kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
_user32.RegisterClassW.argtypes = [ctypes.POINTER(_WNDCLASSW)]
_user32.RegisterClassW.restype = wintypes.ATOM
_user32.CreateWindowExW.restype = wintypes.HWND
_user32.CreateWindowExW.argtypes = [
    wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, ctypes.c_void_p,
]
_user32.GetDC.restype = wintypes.HDC
_user32.GetDC.argtypes = [wintypes.HWND]
_gdi32.ChoosePixelFormat.argtypes = [wintypes.HDC, ctypes.POINTER(_PFD)]
_gdi32.ChoosePixelFormat.restype = ctypes.c_int
_gdi32.SetPixelFormat.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.POINTER(_PFD)]
_gdi32.SetPixelFormat.restype = wintypes.BOOL
_gl.wglCreateContext.restype = ctypes.c_void_p
_gl.wglCreateContext.argtypes = [wintypes.HDC]
_gl.wglMakeCurrent.restype = wintypes.BOOL
_gl.wglMakeCurrent.argtypes = [wintypes.HDC, ctypes.c_void_p]
_gl.glVertexPointer.argtypes = [ctypes.c_int, ctypes.c_uint, ctypes.c_int, ctypes.c_void_p]
_gl.glColorPointer.argtypes = [ctypes.c_int, ctypes.c_uint, ctypes.c_int, ctypes.c_void_p]
_gl.glDrawArrays.argtypes = [ctypes.c_uint, ctypes.c_int, ctypes.c_int]
_gl.glReadPixels.argtypes = [
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p,
]
_gl.glOrtho.argtypes = [ctypes.c_double] * 6
_gl.glRotatef.argtypes = [ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float]
_gl.glClearDepth.argtypes = [ctypes.c_double]
_gl.glClearColor.argtypes = [ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float]
_gl.glViewport.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int]


def _pump():
    msg = wintypes.MSG()
    while _user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
        _user32.TranslateMessage(ctypes.byref(msg))
        _user32.DispatchMessageW(ctypes.byref(msg))


def _context(width, height):
    global _hwnd, _dc, _ctx, _size
    if _user32 is None or _kernel32 is None or _gdi32 is None or _gl is None:
        raise RuntimeError("orbit window")
    if _ctx and _size == (width, height):
        return
    if _hwnd is None:
        instance = _kernel32.GetModuleHandleW(None)
        window = _WNDCLASSW()
        window.style = 0x0020
        window.lpfnWndProc = _wndproc
        window.hInstance = instance
        window.lpszClassName = ctypes.cast(_class_name, wintypes.LPCWSTR)
        if not _user32.RegisterClassW(ctypes.byref(window)) and ctypes.get_last_error() not in (0, 1410):
            raise RuntimeError("orbit window class")
        _hwnd = _user32.CreateWindowExW(
            0, _class_name, "asmamir-orbit", 0x80000000,
            -4000, -4000, int(width), int(height),
            None, None, instance, None,
        )
        if not _hwnd:
            raise RuntimeError("orbit window")
        _user32.ShowWindow(_hwnd, 8)
        _dc = _user32.GetDC(_hwnd)
        fmt = _PFD()
        fmt.nSize = ctypes.sizeof(_PFD)
        fmt.nVersion = 1
        fmt.dwFlags = 4 | 32 | 1
        fmt.iPixelType = 0
        fmt.cColorBits = 24
        fmt.cDepthBits = 24
        fmt.iLayerType = 0
        chosen = _gdi32.ChoosePixelFormat(_dc, ctypes.byref(fmt))
        if not chosen or not _gdi32.SetPixelFormat(_dc, chosen, ctypes.byref(fmt)):
            raise RuntimeError("orbit pixel format")
        _ctx = _gl.wglCreateContext(_dc)
        if not _ctx or not _gl.wglMakeCurrent(_dc, _ctx):
            raise RuntimeError("orbit context")
        _gl.glEnable(_GL_DEPTH_TEST)
        _gl.glDepthFunc(_GL_LESS)
        _gl.glDisable(0x0B44)  # GL_CULL_FACE, both sides of the shell
        _gl.glEnableClientState(_GL_VERTEX_ARRAY)
        _gl.glEnableClientState(_GL_COLOR_ARRAY)
        _gl.glPixelStorei(_GL_PACK_ALIGNMENT, 1)
    else:
        _user32.SetWindowPos(_hwnd, None, -4000, -4000, int(width), int(height), 0x0014)
        _gl.wglMakeCurrent(_dc, _ctx)
    _size = (width, height)
    _pump()


def _gpu(pos, col):
    """Upload the mesh once. Later frames only change yaw and pitch."""
    global _buffers, _uploaded, _gen_buffers, _bind_buffer, _buffer_data
    if _uploaded == len(pos) and _buffers is not None:
        return True
    if _gen_buffers is None:
        get_proc = _gl.wglGetProcAddress
        get_proc.restype = ctypes.c_void_p
        get_proc.argtypes = [ctypes.c_char_p]
        def load(name, restype, argtypes):
            address = get_proc(name)
            if not address:
                return None
            return ctypes.CFUNCTYPE(restype, *argtypes)(address)
        _gen_buffers = load(b"glGenBuffers", None, [ctypes.c_int, ctypes.POINTER(ctypes.c_uint)])
        _bind_buffer = load(b"glBindBuffer", None, [ctypes.c_uint, ctypes.c_uint])
        _buffer_data = load(
            b"glBufferData", None,
            [ctypes.c_uint, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_uint],
        )
        if not _gen_buffers or not _bind_buffer or not _buffer_data:
            return False
    gen_buffers = _gen_buffers
    bind_buffer = _bind_buffer
    buffer_data = _buffer_data
    if gen_buffers is None or bind_buffer is None or buffer_data is None:
        return False
    ids = (ctypes.c_uint * 2)()
    gen_buffers(2, ids)
    bind_buffer(0x8892, int(ids[0]))
    buffer_data(0x8892, pos.nbytes, pos.ctypes.data_as(ctypes.c_void_p), 0x88E4)
    bind_buffer(0x8892, int(ids[1]))
    buffer_data(0x8892, col.nbytes, col.ctypes.data_as(ctypes.c_void_p), 0x88E4)
    bind_buffer(0x8892, 0)
    _buffers = (int(ids[0]), int(ids[1]))
    _uploaded = len(pos)
    return True


def draw(pos, col, yaw, pitch, width, height, background):
    """BGR plate of `pos` (Nx3 float) and `col` (Nx3 RGB) after yaw then pitch."""
    width = int(width)
    height = int(height)
    _context(width, height)
    on_gpu = _gpu(pos, col)
    blue, green, red = (int(channel) for channel in background)
    _gl.glViewport(0, 0, width, height)
    _gl.glClearColor(red / 255.0, green / 255.0, blue / 255.0, 1.0)
    _gl.glClearDepth(1.0)
    _gl.glClear(_GL_COLOR_BUFFER_BIT | _GL_DEPTH_BUFFER_BIT)
    _gl.glMatrixMode(_GL_PROJECTION)
    _gl.glLoadIdentity()
    # Same fit as the standby plate: the unit box is one third of the window.
    span = height / 3.0
    half_x = width / (2.0 * span)
    half_y = height / (2.0 * span)
    _gl.glOrtho(-half_x, half_x, -half_y, half_y, -2.0, 2.0)
    _gl.glMatrixMode(_GL_MODELVIEW)
    _gl.glLoadIdentity()
    _gl.glRotatef(float(pitch), 1.0, 0.0, 0.0)
    _gl.glRotatef(float(yaw), 0.0, 1.0, 0.0)
    if on_gpu:
        _bind_buffer(0x8892, _buffers[0])
        _gl.glVertexPointer(3, _GL_FLOAT, 0, None)
        _bind_buffer(0x8892, _buffers[1])
        _gl.glColorPointer(3, _GL_UNSIGNED_BYTE, 0, None)
    else:
        _gl.glVertexPointer(3, _GL_FLOAT, 0, pos.ctypes.data_as(ctypes.c_void_p))
        _gl.glColorPointer(3, _GL_UNSIGNED_BYTE, 0, col.ctypes.data_as(ctypes.c_void_p))
    _gl.glDrawArrays(_GL_TRIANGLES, 0, int(len(pos)))
    _gl.glFinish()
    image = np.empty((height, width, 3), np.uint8)
    _gl.glReadPixels(
        0, 0, width, height, _GL_BGR, _GL_UNSIGNED_BYTE, image.ctypes.data_as(ctypes.c_void_p)
    )
    return np.ascontiguousarray(image[::-1])
