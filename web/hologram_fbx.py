"""Skinned Mixamo clips for the hologram.

ufbx evaluates the skeleton. Body, cloak, and skirt keep the embedded texture.
Weapons are left out. asmamir.glb is not this figure.
"""

import atexit
import gc
import os
import threading
from pathlib import Path

import cv2
import numpy as np
import ufbx

_SKIP = ("weapon",)
# Evaluated scenes and their mesh wrappers stay here for the process lifetime.
# Freeing them, or letting GC free them, access-violates inside ufbx.
_retain = []
_ufbx_lock = threading.Lock()


def _skip_skinner_gc():
    """Drop the hologram and the stipple browser before ufbx is torn down."""
    try:
        import sys
        app_mod = sys.modules.get("__main__") or sys.modules.get("app")
        closer = getattr(app_mod, "_close_p5_board", None) if app_mod is not None else None
        if closer is not None:
            closer()
        stopper = getattr(app_mod, "_stop_chat_companions", None) if app_mod is not None else None
        if stopper is not None:
            stopper()
    except Exception:
        pass
    try:
        cv2.destroyAllWindows()
        cv2.waitKey(1)
    except Exception:
        pass
    if _retain:
        os._exit(0)


atexit.register(_skip_skinner_gc)


def _vec3(values):
    return np.array([(item.x, item.y, item.z) for item in values], dtype=np.float32)


def _vec2(values):
    return np.array([(item.x, item.y) for item in values], dtype=np.float32)


def _ids(values):
    return np.fromiter(values, dtype=np.int32, count=len(values))


def _png_in(path):
    """The embedded Mixamo diffuse. Reading it through ufbx frees the scene."""
    data = Path(path).read_bytes()
    start = data.find(b"\x89PNG\r\n\x1a\n")
    if start < 0:
        return None
    end = data.find(b"IEND", start)
    if end < 0:
        return None
    blob = np.frombuffer(data[start:end + 8], dtype=np.uint8)
    image = cv2.imdecode(blob, cv2.IMREAD_COLOR)
    if image is None or image.size == 0:
        return None
    return image


def _texture(mesh, image):
    # Material objects after the first mesh crash ufbx. The PNG is the color.
    name = (mesh.name or "").lower()
    if "cloak" in name:
        color = np.array([70, 110, 170], dtype=np.float32)
    elif "skirt" in name:
        color = np.array([150, 70, 90], dtype=np.float32)
    else:
        color = np.array([190, 160, 140], dtype=np.float32)
    return image, color


def _part(mesh, image):
    """Corner map for one mesh. None when this piece is not drawn."""
    name = (mesh.name or "").lower()
    if any(word in name for word in _SKIP):
        return None
    if mesh.num_vertices <= 0 or mesh.num_triangles <= 0:
        return None
    corners = []
    for face in mesh.faces:
        count = int(face.num_indices)
        if count < 3:
            continue
        start = int(face.index_begin)
        for step in range(1, count - 1):
            corners.append((start, start + step, start + step + 1))
    if not corners:
        return None
    image, flat = _texture(mesh, image)
    uv = mesh.vertex_uv
    return {
        "name": mesh.name,
        "vix": _ids(mesh.vertex_position.indices),
        "corners": np.asarray(corners, dtype=np.int32),
        "uvix": _ids(uv.indices) if uv.exists else None,
        "uv": _vec2(uv.values) if uv.exists else None,
        "image": image,
        "flat": flat,
        "bind": _vec3(mesh.vertices),
    }


def _sample(image, uvs):
    height, width = image.shape[:2]
    x = np.clip(uvs[:, 0], 0.0, 1.0)
    y = np.clip(1.0 - uvs[:, 1], 0.0, 1.0)
    ix = np.clip((x * (width - 1)).astype(np.int32), 0, width - 1)
    iy = np.clip((y * (height - 1)).astype(np.int32), 0, height - 1)
    bgr = image[iy, ix]
    return bgr[:, ::-1].astype(np.float32)


def _shade(tri):
    edge_u = tri[:, 1] - tri[:, 0]
    edge_v = tri[:, 2] - tri[:, 0]
    normal = np.cross(edge_u, edge_v)
    length = np.linalg.norm(normal, axis=1, keepdims=True)
    length[length < 1e-8] = 1.0
    normal = normal / length
    light = np.array([0.25, 0.85, 0.45], dtype=np.float32)
    light = light / np.linalg.norm(light)
    facing = np.abs(normal @ light)
    return (0.42 + 0.58 * facing).astype(np.float32)


class Clip:
    """One skinned take. `mesh_at` returns orbit corners and RGB colors."""

    def __init__(self, path):
        # One bake at a time. A second evaluate while another clip is collected
        # access-violates inside ufbx, which is what killed her on Dance: twerk.
        with _ufbx_lock:
            enabled = gc.isenabled()
            gc.disable()
            try:
                self._load(path)
            finally:
                # The bake leaves ufbx wrappers that are not on _retain.
                # The next collection frees them and access-violates, with no
                # Python traceback. That collection is the one that runs when
                # the sit-up thread continues, while voice is still decoding
                # an unclear phrase. Freeze every object that exists now so
                # later collections never call those destructors.
                gc.freeze()
                if enabled:
                    gc.enable()

    def _load(self, path):
        self.path = Path(path)
        self.name = self.path.stem
        self._image = _png_in(self.path)
        self.scene = ufbx.load_file(str(self.path))
        _retain.append(self.scene)
        _retain.append(self)
        stack = self.scene.anim_stacks[0] if self.scene.anim_stacks else None
        self.duration = float(stack.time_end if stack is not None else 1.0) or 1.0
        self._parts = [_part(mesh, self._image) for mesh in self.scene.meshes]
        clouds = [part["bind"] for part in self._parts if part is not None]
        if not clouds:
            raise RuntimeError(f"no skinned mesh in {self.path.name}")
        cloud = np.concatenate(clouds, axis=0)
        low = cloud.min(axis=0)
        high = cloud.max(axis=0)
        self._center = ((low + high) * 0.5).astype(np.float32)
        self._span = float(np.max(high - low)) or 1.0
        self._frames = []
        self._bake()

    def _clock(self, seconds, loop):
        duration = self.duration
        if duration <= 0:
            return 0.0
        if loop:
            return float(seconds) % duration
        return min(max(float(seconds), 0.0), duration)

    def _skin(self, moment):
        state = ufbx.evaluate_scene(
            self.scene,
            self.scene.anim,
            moment,
            evaluate_skinning=True,
        )
        posed = {mesh.name: mesh for mesh in state.meshes}
        chunks = []
        paints = []
        for part in self._parts:
            if part is None:
                continue
            live = posed.get(part["name"])
            if live is None or not live.skinned_position.exists:
                continue
            points = _vec3(live.skinned_position.values)
            corners = part["corners"]
            tri = points[part["vix"][corners]]
            if part["image"] is not None and part["uv"] is not None:
                corner_uv = part["uv"][part["uvix"][corners]]
                sample = corner_uv.mean(axis=1)
                rgb = _sample(part["image"], sample)
            else:
                rgb = np.repeat(part["flat"][None, :], len(tri), axis=0)
            chunks.append(tri)
            paints.append(rgb)
        _retain.append(state)
        _retain.append(posed)
        if not chunks:
            raise RuntimeError("no posed triangles")
        tri = np.concatenate(chunks, axis=0).astype(np.float32)
        color = np.concatenate(paints, axis=0)
        flat = tri.reshape(-1, 3)
        low = flat.min(axis=0)
        high = flat.max(axis=0)
        center = (low + high) * 0.5
        span = float(np.max(high - low)) or 1.0
        tri = (tri - center) / span
        # The plate paints the larger Z in front. A yaw of 180 here put her
        # back on that side for the sit-up and every dance. Leave +Z facing
        # the camera. The fit above is unchanged.
        shade = _shade(tri)
        rgb = np.clip(color * shade[:, None], 0, 255).astype(np.uint8)
        pos = np.ascontiguousarray(tri.reshape(-1, 3))
        col = np.ascontiguousarray(np.repeat(rgb, 3, axis=0))
        return pos, col

    def _bake(self):
        """Sample the take once. Later frames only index this list."""
        step = 1.0 / 30.0
        moment = 0.0
        frames = []
        while True:
            frames.append(self._skin(moment))
            if moment >= self.duration - 1e-4:
                break
            moment = min(self.duration, moment + step)
        self._frames = frames

    def mesh_at(self, seconds, loop=True):
        frames = self._frames
        if not frames:
            raise RuntimeError("no posed triangles")
        last = len(frames) - 1
        if self.duration <= 0 or last == 0:
            return frames[0]
        moment = self._clock(seconds, loop)
        index = int(round(moment / self.duration * last))
        return frames[min(max(index, 0), last)]
