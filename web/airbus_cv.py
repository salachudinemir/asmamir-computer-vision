"""Airbus mode: MediaPipe on app.py camera, WebSocket to the Three.js viewer. No OpenCV fillPoly."""

import json
import mimetypes
import threading
import time
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import numpy as np

WEB = Path(__file__).resolve().parent
HTTP_HOST = "127.0.0.1"
HTTP_PORT = 8765
WS_PORT = 8766
VIEW_URL = f"http://{HTTP_HOST}:{HTTP_PORT}/airbus/"
PINCH_ON = 0.40
PINCH_OFF = 0.58
DRAG_ON = 0.085
FIST_ARM_S = 1.35
# 0 = fully extended, 1 = fully curled (3D tip reach + knuckle fold).
CURL_FIST = 0.60
CURL_FIST_MEAN = 0.66
CURL_INDEX_EXT = 0.42
CURL_OTHER_FOLD = 0.50
_FINGERS = (
    (5, 6, 8),
    (9, 10, 12),
    (13, 14, 16),
    (17, 18, 20),
)

mimetypes.add_type("model/gltf-binary", ".glb")
mimetypes.add_type("model/gltf+json", ".gltf")
mimetypes.add_type("application/octet-stream", ".bin")
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("text/javascript", ".mjs")
mimetypes.add_type("application/wasm", ".wasm")

_EXTRA_MIME = {
    ".glb": "model/gltf-binary",
    ".gltf": "model/gltf+json",
    ".bin": "application/octet-stream",
    ".js": "text/javascript",
    ".mjs": "text/javascript",
    ".css": "text/css",
    ".wasm": "application/wasm",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".html": "text/html",
}

_http = None
_ws_thread = None
_ws_server = None
_clients = set()
_clients_lock = threading.Lock()
_opened_browser = False
_pinch_on = [False, False]
_pinch_origin: list[tuple[float, float] | None] = [None, None]
_pinch_dragged = [False, False]
_dual_was = False
_peace_was = False
_fist_armed = False
_fist_held_t = 0.0
_throttle = 0.12
_prev_t = None
_rotate_prev = None
_last_payload = None
ROTATE_JUMP = 0.45


def _xyz(lm):
    return np.array((float(lm.x), float(lm.y), float(getattr(lm, "z", 0.0))), dtype=np.float64)


def _dist3(a, b):
    return float(np.linalg.norm(_xyz(a) - _xyz(b)))


def _palm_scale(lms):
    return max(_dist3(lms[5], lms[17]), _dist3(lms[0], lms[9]) * 0.55, 1e-4)


def _finger_curl(lms, mcp_i, pip_i, tip_i):
    """0 = extended, 1 = curled. Uses 3D reach so a camera-pointing index is not a fist."""
    palm = _palm_scale(lms)
    wrist, mcp, pip, tip = lms[0], lms[mcp_i], lms[pip_i], lms[tip_i]
    reach = _dist3(tip, wrist) / max(_dist3(mcp, wrist), 0.25 * palm)
    dist_curl = 1.0 - min(1.0, max(0.0, (reach - 1.05) / 0.95))
    a = _xyz(pip) - _xyz(mcp)
    b = _xyz(tip) - _xyz(pip)
    da, db = float(np.linalg.norm(a)), float(np.linalg.norm(b))
    if da < 1e-6 or db < 1e-6:
        ang_curl = dist_curl
    else:
        cos = float(np.clip(np.dot(a, b) / (da * db), -1.0, 1.0))
        ang_curl = 0.5 * (1.0 - cos)
    z_reach = abs(float(getattr(tip, "z", 0.0)) - float(getattr(mcp, "z", 0.0))) / palm
    xy_reach = float(np.hypot(tip.x - mcp.x, tip.y - mcp.y)) / palm
    if z_reach > 0.85 and z_reach > xy_reach * 1.15:
        dist_curl = min(dist_curl, 0.18)
        ang_curl = min(ang_curl, 0.22)
    return float(np.clip(0.62 * dist_curl + 0.38 * ang_curl, 0.0, 1.0))


def _finger_curls(lms):
    return [_finger_curl(lms, mcp, pip, tip) for mcp, pip, tip in _FINGERS]


def _finger_extended(lms, mcp_i, pip_i, tip_i):
    if _finger_curl(lms, mcp_i, pip_i, tip_i) <= CURL_INDEX_EXT:
        return True
    palm = _palm_scale(lms)
    tip, mcp = lms[tip_i], lms[mcp_i]
    z_reach = abs(float(getattr(tip, "z", 0.0)) - float(getattr(mcp, "z", 0.0))) / palm
    xy_reach = float(np.hypot(tip.x - mcp.x, tip.y - mcp.y)) / palm
    return z_reach > 0.85 and z_reach > xy_reach * 1.15


def _thumb_index_span(lms):
    return _dist3(lms[4], lms[8]) / _palm_scale(lms)


def _is_pinch_pose(lms):
    return _thumb_index_span(lms) < 0.45


def _fist(lms):
    """True only when all four fingers are actually curled. Open/pointing hands are not fists."""
    if _finger_extended(lms, 5, 6, 8):
        return False
    curls = _finger_curls(lms)
    if min(curls) < CURL_FIST:
        return False
    if sum(curls) / 4.0 < CURL_FIST_MEAN:
        return False
    if any(_finger_extended(lms, mcp, pip, tip) for mcp, pip, tip in _FINGERS):
        return False
    return True


def _finger_up(lms, tip, pip):
    return lms[tip].y < lms[pip].y - 0.018


def _finger_down(lms, tip, pip):
    return lms[tip].y > lms[pip].y - 0.008


def _peace(lms):
    """Index + middle up, ring + pinky down."""
    return (
        _finger_up(lms, 8, 6)
        and _finger_up(lms, 12, 10)
        and _finger_down(lms, 16, 14)
        and _finger_down(lms, 20, 18)
    )


def _open_palm(lms):
    curls = _finger_curls(lms)
    stretched = sum(1 for c in curls if c < 0.38)
    thumb_out = _dist3(lms[4], lms[5]) / _palm_scale(lms) > 0.45
    return stretched >= 4 and thumb_out


def _index_point(lms):
    """Index extended (any direction, including at camera). Other fingers folded. Not a fist/pinch."""
    if _fist(lms) or _open_palm(lms) or _is_pinch_pose(lms):
        return False
    if not _finger_extended(lms, 5, 6, 8):
        return False
    curls = _finger_curls(lms)
    others = curls[1:]
    if min(others) < 0.38 or sum(others) / 3.0 < CURL_OTHER_FOLD:
        return False
    return True


def _orbit_from_tip(pose):
    """Raw index-tip deltas. No EMA, no pitch/yaw clamp. Viewer does spherical 360."""
    global _rotate_prev
    if pose is None:
        _rotate_prev = None
        return {"on": False, "dx": 0.0, "dy": 0.0}
    dmx = dmy = 0.0
    if _rotate_prev is not None:
        dmx = float(pose["x"] - _rotate_prev["x"])
        dmy = float(pose["y"] - _rotate_prev["y"])
        if abs(dmx) > ROTATE_JUMP or abs(dmy) > ROTATE_JUMP:
            dmx = dmy = 0.0
    _rotate_prev = pose
    return {
        "on": True,
        "dx": round(dmx, 5),
        "dy": round(dmy, 5),
        "x": round(pose["x"], 5),
        "y": round(pose["y"], 5),
    }


def reset_airbus_gestures():
    """Clear pinch/fist/rotate hysteresis. Used by tests."""
    global _dual_was, _peace_was, _fist_armed, _fist_held_t, _throttle, _prev_t, _rotate_prev
    for i in range(2):
        _reset_pinch_slot(i)
    _dual_was = False
    _peace_was = False
    _fist_armed = False
    _fist_held_t = 0.0
    _throttle = 0.12
    _prev_t = None
    _rotate_prev = None


def _pinch_ratio(lms, w, h):
    span = max(18.0, float(np.hypot((lms[5].x - lms[17].x) * w, (lms[5].y - lms[17].y) * h)))
    d = float(np.hypot((lms[4].x - lms[8].x) * w, (lms[4].y - lms[8].y) * h))
    return d / span


def _pinch_xy(lms):
    return float((lms[4].x + lms[8].x) * 0.5), float((lms[4].y + lms[8].y) * 0.5)


class _Static(SimpleHTTPRequestHandler):
    extensions_map = {
        **getattr(SimpleHTTPRequestHandler, "extensions_map", {}),
        **_EXTRA_MIME,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB), **kwargs)

    def guess_type(self, path):
        ext = Path(path).suffix.lower()
        if ext in _EXTRA_MIME:
            return _EXTRA_MIME[ext]
        return super().guess_type(path)

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def log_message(self, format, *args):
        print(f"[airbus-http] {fmt % args}")


def _ensure_http():
    global _http
    if _http is not None:
        return
    try:
        _http = ThreadingHTTPServer((HTTP_HOST, HTTP_PORT), _Static)
    except OSError:
        print(f"Airbus HTTP already on {HTTP_HOST}:{HTTP_PORT}")
        return
    threading.Thread(target=_http.serve_forever, daemon=True, name="airbus-http").start()
    print(f"Airbus viewer {VIEW_URL}")


def _ws_handler(connection):
    with _clients_lock:
        _clients.add(connection)
    try:
        for _ in connection:
            pass
    except Exception:
        pass
    finally:
        with _clients_lock:
            _clients.discard(connection)


def _close_socket(obj):
    sock = getattr(obj, "socket", None)
    if sock is None:
        return
    try:
        sock.close()
    except Exception:
        pass


def stop_servers():
    """Close listening sockets and clients. Do not wait on Server.shutdown."""
    with _clients_lock:
        clients = list(_clients)
        _clients.clear()
    for client in clients:
        _close_socket(client)
    if _ws_server is not None:
        _close_socket(_ws_server)
    if _http is not None:
        try:
            _http.server_close()
        except Exception:
            pass


def _ws_loop():
    global _ws_server
    from websockets.sync.server import serve

    try:
        with serve(_ws_handler, HTTP_HOST, WS_PORT) as server:
            _ws_server = server
            print(f"Airbus hands ws://{HTTP_HOST}:{WS_PORT}")
            server.serve_forever()
    finally:
        _ws_server = None


def _ensure_ws():
    global _ws_thread
    if _ws_thread is not None:
        return
    _ws_thread = threading.Thread(target=_ws_loop, daemon=True, name="airbus-ws")
    _ws_thread.start()


def ensure_airbus_viewer():
    global _opened_browser
    _ensure_http()
    _ensure_ws()
    if not _opened_browser:
        _opened_browser = True
        webbrowser.open(VIEW_URL)


def _broadcast(payload):
    global _last_payload
    _last_payload = payload
    blob = json.dumps(payload)
    dead = []
    with _clients_lock:
        for client in list(_clients):
            try:
                client.send(blob)
            except Exception:
                dead.append(client)
        for client in dead:
            _clients.discard(client)


def _reset_pinch_slot(i):
    _pinch_on[i] = False
    _pinch_origin[i] = None
    _pinch_dragged[i] = False


def hands_payload(hands, w, h, now=None):
    """Classify Airbus CAD gestures. Pinch+index orbit; two pinch measure; two fists explode."""
    global _dual_was, _peace_was, _fist_armed, _fist_held_t, _throttle, _prev_t
    if now is None:
        now = time.time()
    dt = 0.016 if _prev_t is None else min(0.05, max(0.001, now - _prev_t))
    _prev_t = now
    hands = sorted(hands, key=lambda lms: lms[0].x)[:2]

    peaces = [lms for lms in hands if _peace(lms)]
    pointing = [lms for lms in hands if _index_point(lms)]
    peace_now = bool(peaces)
    reassemble = bool(peace_now and not _peace_was)

    for i in range(len(hands), 2):
        _reset_pinch_slot(i)

    pinch_pts = []
    detach_edge = False
    drag_on = False
    for i, lms in enumerate(hands):
        if _peace(lms) or _index_point(lms) or _open_palm(lms):
            _reset_pinch_slot(i)
            continue
        if _fist(lms) and not _is_pinch_pose(lms):
            _reset_pinch_slot(i)
            continue
        ratio = _pinch_ratio(lms, w, h)
        px, py = _pinch_xy(lms)
        if ratio < PINCH_ON:
            if not _pinch_on[i]:
                _pinch_on[i] = True
                _pinch_origin[i] = (px, py)
                _pinch_dragged[i] = False
        elif ratio > PINCH_OFF:
            _reset_pinch_slot(i)
            continue
        if not _pinch_on[i]:
            continue
        origin = _pinch_origin[i]
        dist = 0.0
        if origin is not None:
            dist = float(np.hypot(px - origin[0], py - origin[1]))
        if dist >= DRAG_ON:
            if not _pinch_dragged[i]:
                detach_edge = True
            _pinch_dragged[i] = True
        if _pinch_dragged[i]:
            drag_on = True
        pinch_pts.append({"x": px, "y": py, "drag": _pinch_dragged[i]})

    two_pinch = len(pinch_pts) >= 2 and not peace_now
    pinch_on = len(pinch_pts) == 1 and not peace_now
    px = py = 0.5
    if pinch_pts:
        px = pinch_pts[0]["x"]
        py = pinch_pts[0]["y"]
    if two_pinch:
        pinch_on = False
        detach_edge = False
        drag_on = False

    measure = None
    if two_pinch:
        measure = {"on": True, "a": {"x": pinch_pts[0]["x"], "y": pinch_pts[0]["y"]}, "b": {"x": pinch_pts[1]["x"], "y": pinch_pts[1]["y"]}}

    orbit_ok = (
        len(pinch_pts) == 1
        and len(pointing) == 1
        and not two_pinch
        and not peace_now
        and len(hands) == 2
    )
    pose = None
    if orbit_ok:
        tip = pointing[0][8]
        pose = {"x": float(tip.x), "y": float(tip.y)}
    rotate = _orbit_from_tip(pose)
    rotating = bool(rotate["on"])
    if rotating:
        pinch_on = False
        detach_edge = False
        drag_on = False
        if pinch_pts:
            hold = (pinch_pts[0]["x"], pinch_pts[0]["y"])
            for i in range(len(hands)):
                if _pinch_on[i]:
                    _pinch_origin[i] = hold
                    _pinch_dragged[i] = False

    fists = [] if rotating or pointing else [lms for lms in hands if _fist(lms)]
    pinch_busy = bool(pinch_on or two_pinch or rotating)
    dual = len(fists) >= 2 and not rotating and not pointing and not pinch_busy
    explode = bool(dual and not _dual_was)

    if len(fists) == 1 and not dual and not rotating:
        _throttle = min(1.0, _throttle + dt * 0.85)
        _fist_armed = True
        _fist_held_t = now
    else:
        _throttle = max(0.08, _throttle - dt * 0.32)
    if dual or rotating:
        _fist_armed = False
    elif not fists and _fist_armed and (now - _fist_held_t) > FIST_ARM_S:
        _fist_armed = False

    pause_toggle = False
    if (
        _fist_armed
        and not fists
        and not dual
        and not peace_now
        and not rotating
        and any(_open_palm(lms) for lms in hands)
    ):
        pause_toggle = True
        _fist_armed = False

    point = {"on": False, "x": 0.5, "y": 0.5}
    if not pinch_on and not two_pinch and not rotating and not dual and not peace_now and not fists:
        for lms in hands:
            if _index_point(lms):
                point = {"on": True, "x": float(lms[8].x), "y": float(lms[8].y)}
                break

    _dual_was = dual
    _peace_was = peace_now

    status = "3D in browser"
    if pause_toggle:
        status = "pause/resume · 3D in browser"
    elif explode:
        status = "explode · 3D in browser"
    elif reassemble:
        status = "reassemble · 3D in browser"
    elif two_pinch:
        status = "measure · 3D in browser"
    elif rotate["on"]:
        status = "orbit · pinch+index · 3D in browser"
    elif pinch_on and drag_on:
        status = "tray · 3D in browser"
    elif pinch_on:
        status = "pinch · 3D in browser"
    elif point["on"]:
        status = "spare · 3D in browser"
    elif len(fists) == 1:
        status = f"fans {int(_throttle * 100)} · 3D in browser"

    payload = {
        "pinch": {"on": pinch_on, "x": px, "y": py, "drag": bool(drag_on and pinch_on), "detach": bool(detach_edge and pinch_on)},
        "fists": len(fists),
        "throttle": round(_throttle, 3),
        "explode": explode,
        "reassemble": reassemble,
        "pauseToggle": pause_toggle,
        "point": point,
        "measure": measure,
        "rotate": rotate,
    }
    return payload, status


def draw_airbus_overlay(frame, results):
    """Keep the webcam HUD; send CAD gestures over WebSocket. Do not draw the glTF here."""
    ensure_airbus_viewer()
    h, w = frame.shape[:2]
    hands = []
    if results is not None and results.multi_hand_landmarks:
        hands = [hand.landmark for hand in results.multi_hand_landmarks]
    payload, status = hands_payload(hands, w, h)
    _broadcast(payload)
    return frame
