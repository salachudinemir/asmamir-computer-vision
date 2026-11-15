"""Desert Eagle: GPU glTF viewer + MediaPipe WS; OpenCV Mark XIX if GPU fails."""

import json
import threading
import time
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import cv2
import numpy as np

COOLDOWN = 0.5
PULL_ON = 0.58
PULL_OFF = 0.38
CURL_ON = 0.52
CURL_OFF = 0.28
PINCH_ON = 0.4
PINCH_OFF = 0.58
DRAG_ON = 0.085
ROTATE_JUMP = 0.45

LEATHER = (28, 30, 34)
PAD = (14, 16, 18)
SLEEVE = (36, 38, 42)
HUD = (236, 236, 236)
FLASH = (80, 190, 255)
STEEL = (216, 220, 226)
STEEL_HI = (242, 244, 248)
STEEL_LO = (148, 152, 158)
STEEL_EDGE = (110, 114, 120)
RUBBER = (18, 20, 22)
BLACK = (10, 12, 14)

_last_primary = None
_pos = None
_fwd = None
_recoil = 0.0
_flash = 0.0
_pinched = False
_fist_was = False
_last_shot = 0.0
_prev_t = None
_mag = 1.0

WEB = Path(__file__).resolve().parent
HTTP_HOST = "127.0.0.1"
HTTP_PORT = 8765
WS_PORT = 8767
VIEW_URL = f"http://{HTTP_HOST}:{HTTP_PORT}/deagle/"

_http = None
_ws_thread = None
_ws_server = None
_ws_ok = False
_clients = set()
_clients_lock = threading.Lock()
_opened_browser = False
_pinch_on = [False, False]
_pinch_origin = [None, None]
_pinch_dragged = [False, False]
_dual_was = False
_peace_was = False
_rotate_prev = None


_MIME = {
    ".glb": "model/gltf-binary",
    ".gltf": "model/gltf+json",
    ".bin": "application/octet-stream",
    ".js": "text/javascript",
    ".mjs": "text/javascript",
}


class _Static(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB), **kwargs)

    def guess_type(self, path):
        ext = Path(path).suffix.lower()
        if ext in _MIME:
            return _MIME[ext]
        return super().guess_type(path)

    def log_message(self, fmt, *args):
        print(f"[deagle-http] {fmt % args}")


def _ensure_http():
    global _http
    if _http is not None:
        return True
    try:
        _http = ThreadingHTTPServer((HTTP_HOST, HTTP_PORT), _Static)
    except OSError:
        print(f"Deagle HTTP already on {HTTP_HOST}:{HTTP_PORT}")
        _http = True
        return True
    threading.Thread(target=_http.serve_forever, daemon=True, name="deagle-http").start()
    print(f"Deagle viewer {VIEW_URL}")
    return True


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
    http = _http
    if http is not None and http is not True:
        try:
            http.server_close()
        except Exception:
            pass


def _ws_loop():
    global _ws_ok, _ws_server
    try:
        from websockets.sync.server import serve

        with serve(_ws_handler, HTTP_HOST, WS_PORT) as server:
            _ws_server = server
            _ws_ok = True
            print(f"Deagle hands ws://{HTTP_HOST}:{WS_PORT}")
            server.serve_forever()
    except OSError as err:
        _ws_ok = False
        print(f"Deagle WS failed: {err}")
    finally:
        _ws_server = None


def _ensure_ws():
    global _ws_thread
    if _ws_thread is not None:
        return True
    try:
        from websockets.sync.server import serve as _serve  # noqa: F401
    except Exception as err:
        print(f"Deagle WS import failed: {err}")
        return False
    _ws_thread = threading.Thread(target=_ws_loop, daemon=True, name="deagle-ws")
    _ws_thread.start()
    return True


def ensure_deagle_viewer():
    """HTTP on 8765 (shared with Airbus/serve.py) + WS 8767 + browser."""
    global _opened_browser
    http_ok = _ensure_http()
    ws_ok = _ensure_ws()
    gpu = bool(http_ok and ws_ok)
    if gpu and not _opened_browser:
        _opened_browser = True
        webbrowser.open(VIEW_URL)
    return gpu


def _broadcast(payload):
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


def _pack_results(results):
    hands = []
    if results is None or not results.multi_hand_landmarks:
        return {"hands": []}
    for i, hand in enumerate(results.multi_hand_landmarks):
        lms = [[float(p.x), float(p.y), float(p.z)] for p in hand.landmark]
        hands.append({"label": _hand_label(results, i), "lms": lms})
    return {"hands": hands}


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


def reset_deagle_cad():
    """Clear pinch/rotate hysteresis. Used by tests."""
    global _dual_was, _peace_was, _rotate_prev
    for i in range(2):
        _reset_pinch_slot(i)
    _dual_was = False
    _peace_was = False
    _rotate_prev = None


def _cad_from_results(results, w, h):
    """Inspect/strip flags for the GPU viewer. Hands stay in the same payload."""
    global _dual_was, _peace_was
    hands = []
    if results is not None and results.multi_hand_landmarks:
        hands = [hand.landmark for hand in results.multi_hand_landmarks]
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
        if _peace(lms) or _index_point(lms):
            _reset_pinch_slot(i)
            continue
        if _fist(lms) and _pinch_ratio(lms, w, h) >= PINCH_ON:
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
        px, py = pinch_pts[0]["x"], pinch_pts[0]["y"]
    if two_pinch:
        pinch_on = False
        detach_edge = False
        drag_on = False

    measure = None
    if two_pinch:
        measure = {
            "on": True,
            "a": {"x": pinch_pts[0]["x"], "y": pinch_pts[0]["y"]},
            "b": {"x": pinch_pts[1]["x"], "y": pinch_pts[1]["y"]},
        }

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
    dual = len(fists) >= 2 and not rotating and not pointing and not two_pinch
    explode = bool(dual and not _dual_was)

    point = {"on": False, "x": 0.5, "y": 0.5}
    if not pinch_on and not two_pinch and not rotating and not dual and not peace_now and not fists:
        for lms in pointing:
            point = {"on": True, "x": float(lms[8].x), "y": float(lms[8].y)}
            break

    _dual_was = dual
    _peace_was = peace_now

    status = "viewer · show a pistol grip"
    if explode:
        status = "viewer · explode"
    elif reassemble:
        status = "viewer · reassemble"
    elif two_pinch:
        status = "viewer · measure"
    elif rotate["on"]:
        status = "viewer · orbit pinch+index"
    elif pinch_on and drag_on:
        status = "viewer · strip part"
    elif pinch_on:
        status = "viewer · pinch"
    elif dual:
        status = "viewer · two fists"
    elif fists:
        status = "viewer · reload mag"
    elif point["on"]:
        status = "viewer · part label"
    else:
        primary, support = (None, None)
        if results is not None and results.multi_hand_landmarks:
            primary, support = split_hands(results)
        if primary is not None:
            if _trigger_pull(primary, w, h) > PULL_ON:
                status = "viewer · trigger"
            elif support is not None:
                status = "viewer · two-hand grip · PIP fire"
            else:
                status = "viewer · yaw index · PIP fire"

    payload = {
        "pinch": {
            "on": pinch_on,
            "x": px,
            "y": py,
            "drag": bool(drag_on and pinch_on),
            "detach": bool(detach_edge and pinch_on),
        },
        "fists": len(fists),
        "explode": explode,
        "reassemble": reassemble,
        "point": point,
        "measure": measure,
        "rotate": rotate,
    }
    return payload, status


def _xy(lm, w, h):
    return np.array((lm.x * w, lm.y * h), dtype=np.float32)


def _palm_span(lms, w, h):
    a = _xy(lms[5], w, h)
    b = _xy(lms[17], w, h)
    return max(18.0, float(np.linalg.norm(a - b)))


def _index_curl(lms):
    mcp, pip, tip = lms[5], lms[6], lms[8]
    ax, ay = pip.x - mcp.x, pip.y - mcp.y
    bx, by = tip.x - pip.x, tip.y - pip.y
    da, db = (ax * ax + ay * ay) ** 0.5, (bx * bx + by * by) ** 0.5
    if da < 1e-5 or db < 1e-5:
        return 0.0
    cos = (ax * bx + ay * by) / (da * db)
    return max(0.0, min(1.0, (1.0 - cos) * 0.5))


def _pinch_ratio(lms, w, h):
    span = _palm_span(lms, w, h)
    return float(np.linalg.norm(_xy(lms[4], w, h) - _xy(lms[8], w, h))) / span


def _fist(lms):
    folded = 0
    for tip, pip in ((8, 6), (12, 10), (16, 14), (20, 18)):
        if lms[tip].y > lms[pip].y - 0.015:
            folded += 1
    thumb_in = abs(lms[4].x - lms[5].x) < 0.08
    return folded >= 4 and thumb_in


def _finger_up(lms, tip, pip):
    return lms[tip].y < lms[pip].y - 0.018


def _finger_down(lms, tip, pip):
    return lms[tip].y > lms[pip].y - 0.008


def _peace(lms):
    return (
        _finger_up(lms, 8, 6)
        and _finger_up(lms, 12, 10)
        and _finger_down(lms, 16, 14)
        and _finger_down(lms, 20, 18)
    )


def _index_point(lms):
    thumb_away = abs(lms[4].x - lms[8].x) > 0.045
    return (
        _finger_up(lms, 8, 6)
        and _finger_down(lms, 12, 10)
        and _finger_down(lms, 16, 14)
        and _finger_down(lms, 20, 18)
        and thumb_away
    )


def _pinch_xy(lms):
    return float((lms[4].x + lms[8].x) * 0.5), float((lms[4].y + lms[8].y) * 0.5)


def _reset_pinch_slot(i):
    _pinch_on[i] = False
    _pinch_origin[i] = None
    _pinch_dragged[i] = False


def _trigger_pull(lms, w, h):
    curl = _index_curl(lms)
    pinch = 1.0 - min(1.0, _pinch_ratio(lms, w, h))
    return curl * 0.62 + pinch * 0.38


def _hand_label(results, i):
    if results.multi_handedness is None or i >= len(results.multi_handedness):
        return f"h{i}"
    return results.multi_handedness[i].classification[0].label


def split_hands(results):
    global _last_primary
    lst = results.multi_hand_landmarks
    if not lst:
        return None, None
    if len(lst) == 1:
        _last_primary = _hand_label(results, 0)
        return lst[0].landmark, None
    scored = []
    for i, hand in enumerate(lst):
        scored.append((hand.landmark[9].y, i, hand.landmark, _hand_label(results, i)))
    scored.sort(key=lambda row: row[0])
    grip, cup = scored[0], scored[1]
    # Higher in the frame (smaller y) = strong grip; lower = magwell.
    if _last_primary and cup[3] == _last_primary and cup[0] < grip[0] + 0.03:
        grip, cup = cup, grip
    _last_primary = grip[3]
    return grip[2], cup[2]


def _smooth(prev, now, alpha):
    if prev is None:
        return now.copy()
    return prev * (1.0 - alpha) + now * alpha


def _blend(frame, overlay_bgra):
    alpha = overlay_bgra[:, :, 3].astype(np.float32) / 255.0
    if float(alpha.max()) < 0.01:
        return
    a = alpha[:, :, None]
    frame[:] = (overlay_bgra[:, :, :3] * a + frame * (1.0 - a)).astype(np.uint8)


def _capsule(layer, p0, p1, radius, color):
    p0i = (int(p0[0]), int(p0[1]))
    p1i = (int(p1[0]), int(p1[1]))
    r = max(2, int(radius))
    cv2.line(layer, p0i, p1i, color, r * 2, cv2.LINE_AA)
    cv2.circle(layer, p0i, r, color, -1, cv2.LINE_AA)
    cv2.circle(layer, p1i, r, color, -1, cv2.LINE_AA)


def draw_glove(layer, lms, w, h, trigger_curl=0.0):
    """Black tactical leather along bones — not brown landmark blobs."""
    span = _palm_span(lms, w, h)
    r = max(3.0, span * 0.16)
    pts = [_xy(lms[i], w, h) for i in range(21)]
    palm = np.array([pts[i] for i in (0, 1, 5, 9, 13, 17)], dtype=np.int32)
    hull = cv2.convexHull(palm)
    cv2.fillConvexPoly(layer, hull, LEATHER)
    wrist, mid = pts[0], pts[9]
    sleeve = wrist + (wrist - mid) * 0.42
    _capsule(layer, wrist, sleeve, r * 1.15, SLEEVE)
    _capsule(layer, wrist, sleeve, r * 0.55, PAD)
    chains = ((1, 2, 3, 4), (5, 6, 7, 8), (9, 10, 11, 12), (13, 14, 15, 16), (17, 18, 19, 20))
    widths = (0.9, 0.78 + 0.12 * trigger_curl, 0.74, 0.7, 0.62)
    for chain, wf in zip(chains, widths):
        rad = r * wf
        for a, b in zip(chain, chain[1:]):
            _capsule(layer, pts[a], pts[b], rad, LEATHER)
        kn = pts[chain[0]]
        cv2.rectangle(
            layer,
            (int(kn[0] - rad), int(kn[1] - rad * 0.45)),
            (int(kn[0] + rad), int(kn[1] + rad * 0.45)),
            PAD,
            -1,
        )


def _uv(origin, fwd, down, scale, u, v):
    p = origin + fwd * (u * scale) + down * (v * scale)
    return (int(round(p[0])), int(round(p[1])))


def _shape(layer, origin, fwd, down, scale, uvs, fill, edge=None, width=1):
    pts = np.array([_uv(origin, fwd, down, scale, u, v) for u, v in uvs], dtype=np.int32)
    cv2.fillPoly(layer, [pts], fill, lineType=cv2.LINE_AA)
    cv2.polylines(layer, [pts], True, edge or STEEL_EDGE, max(1, width), cv2.LINE_AA)


def draw_mark_xix(frame, origin, fwd, down, scale, recoil, flash):
    """Stainless XIX: long slide, 6\" barrel, rubber grip. Drawn 2x then scaled."""
    origin = origin + down * (recoil * scale * 0.05) - fwd * (recoil * scale * 0.08)
    h, w = frame.shape[:2]
    hi, wi = h * 2, w * 2
    layer = np.zeros((hi, wi, 3), dtype=np.uint8)
    o2, s2 = origin * 2.0, scale * 2.0

    slide = [
        (-0.38, -0.06), (-0.48, -0.28), (-0.42, -0.48), (-0.18, -0.58),
        (0.55, -0.56), (1.35, -0.52), (1.72, -0.46), (1.78, -0.22),
        (1.72, -0.02), (1.15, 0.06), (0.15, 0.08), (-0.22, 0.04),
    ]
    _shape(layer, o2, fwd, down, s2, slide, STEEL, STEEL_LO, 2)
    hi_strip = [(-0.16, -0.54), (1.62, -0.48), (1.68, -0.36), (-0.12, -0.42)]
    _shape(layer, o2, fwd, down, s2, hi_strip, STEEL_HI, STEEL, 1)
    for i in range(8):
        u = -0.28 - i * 0.028
        _shape(
            layer, o2, fwd, down, s2,
            [(u, -0.46), (u + 0.012, -0.46), (u + 0.012, -0.16), (u, -0.16)],
            STEEL_LO, STEEL_LO, 1,
        )
    rear = [(-0.50, -0.22), (-0.58, -0.40), (-0.36, -0.50), (-0.28, -0.14)]
    _shape(layer, o2, fwd, down, s2, rear, STEEL, STEEL_LO, 2)
    hammer = [(-0.52, -0.36), (-0.62, -0.52), (-0.48, -0.56), (-0.40, -0.32)]
    _shape(layer, o2, fwd, down, s2, hammer, BLACK, BLACK, 1)
    _shape(
        layer, o2, fwd, down, s2,
        [(-0.20, -0.60), (-0.04, -0.60), (-0.06, -0.52), (-0.22, -0.52)],
        BLACK, BLACK, 1,
    )

    barrel = [(1.62, -0.34), (2.72, -0.30), (2.78, -0.12), (1.66, -0.04)]
    _shape(layer, o2, fwd, down, s2, barrel, STEEL, STEEL_LO, 2)
    brake = [(2.62, -0.36), (2.92, -0.34), (2.96, -0.10), (2.64, -0.06)]
    _shape(layer, o2, fwd, down, s2, brake, STEEL_HI, STEEL_LO, 2)
    _shape(
        layer, o2, fwd, down, s2,
        [(2.88, -0.28), (2.94, -0.28), (2.94, -0.16), (2.88, -0.16)],
        BLACK, BLACK, 1,
    )
    for i in range(7):
        u = 1.78 + i * 0.12
        p0 = _uv(o2, fwd, down, s2, u, -0.50)
        p1 = _uv(o2, fwd, down, s2, u, -0.40)
        cv2.line(layer, p0, p1, STEEL_LO, 2, cv2.LINE_AA)

    frame_body = [(-0.18, 0.02), (1.35, -0.02), (1.28, 0.18), (-0.10, 0.22)]
    _shape(layer, o2, fwd, down, s2, frame_body, STEEL_LO, STEEL_EDGE, 2)
    guard = [
        (0.38, 0.04), (0.98, 0.02), (1.08, 0.14), (1.02, 0.38),
        (0.70, 0.48), (0.42, 0.40), (0.36, 0.18),
    ]
    _shape(layer, o2, fwd, down, s2, guard, STEEL, STEEL_LO, 2)
    hole = [(0.50, 0.14), (0.88, 0.12), (0.90, 0.30), (0.54, 0.34)]
    _shape(layer, o2, fwd, down, s2, hole, BLACK, BLACK, 1)
    trig = [(0.58, 0.10), (0.70, 0.10), (0.68, 0.28), (0.54, 0.26)]
    _shape(layer, o2, fwd, down, s2, trig, BLACK, BLACK, 1)

    magwell = [(-0.06, 0.16), (0.52, 0.14), (0.48, 0.42), (-0.02, 0.46)]
    _shape(layer, o2, fwd, down, s2, magwell, STEEL_LO, STEEL_EDGE, 2)
    mag = [(0.04, 0.22), (0.40, 0.20), (0.36, 1.02), (0.02, 1.06)]
    _shape(layer, o2, fwd, down, s2, mag, RUBBER, BLACK, 1)
    grip = [
        (0.00, 0.18), (0.44, 0.16), (0.50, 0.28), (0.42, 1.08),
        (0.08, 1.14), (-0.04, 0.96), (-0.02, 0.40),
    ]
    _shape(layer, o2, fwd, down, s2, grip, RUBBER, BLACK, 2)
    badge = _uv(o2, fwd, down, s2, 0.46, 0.55)
    cv2.circle(layer, badge, max(3, int(0.07 * s2)), STEEL_LO, 2, cv2.LINE_AA)

    small = cv2.resize(layer, (w, h), interpolation=cv2.INTER_AREA)
    mask = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY) > 8
    overlay = np.zeros((h, w, 4), dtype=np.uint8)
    overlay[mask, :3] = small[mask]
    overlay[mask, 3] = 255
    _blend(frame, overlay)

    muzzle = origin + fwd * (2.96 * scale) + down * (-0.22 * scale)
    mx, my = int(muzzle[0]), int(muzzle[1])
    if flash > 0.05:
        glow = frame.copy()
        cv2.circle(glow, (mx, my), int(16 + flash * 36), FLASH, -1, cv2.LINE_AA)
        cv2.circle(glow, (mx, my), int(8 + flash * 12), (255, 255, 255), -1, cv2.LINE_AA)
        cv2.addWeighted(glow, min(0.7, flash), frame, 1.0 - min(0.7, flash), 0, frame)
    return mx, my


def _hud(frame, status):
    return frame


def _draw_gpu_hud(frame, results, status=None):
    if status is None:
        status = "viewer · show a pistol grip"
    return _hud(frame, status)


def _draw_opencv_gun(frame, results):
    global _pos, _fwd, _recoil, _flash, _pinched, _fist_was, _last_shot, _prev_t, _mag
    h, w = frame.shape[:2]
    now = time.time()
    dt = 0.016 if _prev_t is None else min(0.05, max(0.001, now - _prev_t))
    _prev_t = now
    _recoil = max(0.0, _recoil - dt * 6.5)
    _flash = max(0.0, _flash - dt * 9.0)
    _mag = min(1.0, _mag + dt * 3.2)

    status = "show a pistol grip"
    primary, support = (None, None)
    if results is not None and results.multi_hand_landmarks:
        primary, support = split_hands(results)

    if primary is not None:
        wrist = _xy(primary[0], w, h)
        index_mcp = _xy(primary[5], w, h)
        index_pip = _xy(primary[6], w, h)
        middle = _xy(primary[9], w, h)
        palm = wrist * 0.55 + middle * 0.45
        if support is not None:
            cup = _xy(support[0], w, h) * 0.55 + _xy(support[9], w, h) * 0.45
            palm = palm * 0.72 + cup * 0.28
        fwd = index_pip - index_mcp
        n = float(np.linalg.norm(fwd))
        fwd = np.array((1.0, 0.0), dtype=np.float32) if n < 1e-3 else fwd / n
        _pos = _smooth(_pos, palm, 0.35)
        _fwd = _smooth(_fwd, fwd, 0.28)
        n = float(np.linalg.norm(_fwd))
        if n > 1e-6:
            _fwd = _fwd / n
        down = np.array((_fwd[1], -_fwd[0]), dtype=np.float32)
        if down[1] < 0:
            down = -down
        scale = _palm_span(primary, w, h) * 0.95
        gloves = np.zeros((h, w, 4), dtype=np.uint8)
        g_bgr = np.zeros((h, w, 3), dtype=np.uint8)
        if support is not None:
            draw_glove(g_bgr, support, w, h, 0.0)
        draw_glove(g_bgr, primary, w, h, _index_curl(primary))
        mask = cv2.cvtColor(g_bgr, cv2.COLOR_BGR2GRAY) > 0
        gloves[mask, :3] = g_bgr[mask]
        gloves[mask, 3] = 220
        _blend(frame, gloves)
        draw_mark_xix(frame, _pos, _fwd, down, scale, _recoil + (1.0 - _mag) * 0.35, _flash)
        pinch_r = _pinch_ratio(primary, w, h)
        pinch_close = pinch_r < PINCH_ON
        pinch_open = pinch_r > PINCH_OFF
        fist = _fist(primary)
        if fist and not _fist_was:
            _last_shot = 0.0
            _recoil = 0.45
            _mag = 0.0
            _pinched = False
            status = "reload"
        elif not fist and not _pinched and pinch_close:
            _pinched = True
            if now - _last_shot >= COOLDOWN:
                _last_shot = now
                _recoil = 1.0
                _flash = 1.0
            status = "trigger"
        elif _pinched and pinch_open:
            _pinched = False
            status = "two-hand grip · pinch to fire · fist reload" if support is not None else "pinch to fire · fist reload"
        elif support is not None:
            status = "reload" if _mag < 0.85 else "two-hand · pinch trigger · fist reload"
        else:
            status = "reload" if _mag < 0.85 else "pinch trigger · fist reload"
        _fist_was = fist
    else:
        _fist_was = False
        status = "show a pistol grip (pinch trigger · fist reload)"

    return _hud(frame, status)


def draw_deagle_overlay(frame, results):
    """GPU glTF viewer like Airbus; OpenCV Mark XIX if HTTP/WS cannot start."""
    gpu = ensure_deagle_viewer()
    if gpu:
        h, w = frame.shape[:2]
        packed = _pack_results(results)
        cad, status = _cad_from_results(results, w, h)
        packed.update(cad)
        _broadcast(packed)
        return _draw_gpu_hud(frame, results, status)
    return _draw_opencv_gun(frame, results)
