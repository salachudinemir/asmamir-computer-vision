"""Standby figure is Mixamo Arissa from the sit-up clip.

The plate is her body, cloak, and skirt. It does not turn on its own.
A pinch plus the other index changes yaw and pitch with no stop.
asmamir.glb is not drawn. The webcam picture is not this plate.
"""

from pathlib import Path

import cv2
import numpy as np

_FOLDER = Path(__file__).resolve().parent / "hologram"
_BG = (14, 16, 12)

_cache_key = None
_plate = None
_yaw = 0.0
_pitch = 0.0
# Long side of the posed figure, as a fraction of the plate height.
# Was 0.58 of a 1280x720 plate that the fullscreen window then stretched.
_FIGURE = 1.0 / 3.0
_plate_log = None
_pos = None
_col = None
_orbit_ready = False
_orbit_key = None
_warm_started = False
_view = None
_view_key = None


def find_model():
    """The glTF to show. Prefer asmamir.glb, then asmamir.gltf, then any other."""
    _FOLDER.mkdir(parents=True, exist_ok=True)
    for name in ("asmamir.glb", "asmamir.gltf"):
        path = _FOLDER / name
        if path.is_file() and path.stat().st_size > 0:
            return path
    found = []
    for pattern in ("*.glb", "*.gltf", "*.GLB", "*.GLTF"):
        found.extend(path for path in _FOLDER.rglob(pattern) if path.is_file() and path.stat().st_size > 0)
    found.sort(key=lambda path: (path.parent != _FOLDER, -path.stat().st_mtime))
    return found[0] if found else None


def add_turn(dyaw, dpitch):
    """Yaw and pitch in degrees. Neither is clamped, so a drag can pass 360."""
    global _yaw, _pitch
    _yaw += float(dyaw)
    _pitch += float(dpitch)


def angles():
    return float(_yaw), float(_pitch)


def warm():
    """Load Arissa off the camera thread. The plate stays dark until she is ready."""
    global _warm_started
    if _warm_started:
        return
    _warm_started = True
    try:
        from web import hologram_dance
        hologram_dance.preload()
    except Exception as exc:
        print(f"Hologram figure did not load: {exc}")


def render(width, height, tick=0):
    """BGR plate of Arissa at the current yaw and pitch. Never the old glb.

    `width` and `height` are the window. The plate is that size, so the
    fullscreen window does not stretch a smaller buffer.
    """
    global _plate_log
    del tick
    width = max(640, int(width))
    height = max(360, int(height))
    if _plate_log != (width, height):
        _plate_log = (width, height)
        print(
            f"Hologram plate {width}x{height}. "
            f"Figure is one third of that height."
        )
    posed = None
    try:
        from web import hologram_dance
        posed = hologram_dance.frame()
    except Exception as exc:
        print(f"Hologram frame failed: {exc}")
    if posed is None:
        return np.full((height, width, 3), _BG, np.uint8)
    pos, col = posed
    return _paint_turn(pos, col, _yaw, _pitch, width, height)


def _resting(yaw, pitch):
    def near(angle):
        folded = abs(float(angle)) % 360.0
        return min(folded, 360.0 - folded) < 0.4
    return near(yaw) and near(pitch)


def _ensure(path):
    global _cache_key, _plate
    key = (str(path), path.stat().st_mtime_ns, path.stat().st_size)
    if _cache_key == key and _plate is not None:
        return True
    cache = path.with_name(path.stem + ".mesh.png")
    if cache.is_file() and cache.stat().st_mtime_ns >= path.stat().st_mtime_ns:
        image = cv2.imread(str(cache), cv2.IMREAD_COLOR)
        if image is not None and image.size:
            _plate = image
            _cache_key = key
            print(f"Hologram model {path.name} (still plate).")
            return True
    try:
        plate = _build_plate(path)
    except Exception as exc:
        print(f"Hologram model did not load ({path.name}): {exc}")
        _cache_key = key
        _plate = None
        return False
    _plate = plate
    _cache_key = key
    try:
        cv2.imwrite(str(cache), plate)
    except Exception as exc:
        print(f"Hologram plate not written ({exc}).")
    print(f"Hologram model {path.name} (solid, still).")
    return True


def _build_plate(path, width=1280, height=720):
    """Paint every source triangle. No voxel merge, so the shell stays closed."""
    import trimesh

    scene = trimesh.load(path, force="scene")
    geometries = getattr(scene, "geometry", None) or {}
    if not geometries and isinstance(scene, trimesh.Trimesh):
        geometries = {"mesh": scene}
    pieces = []
    low = np.full(3, np.inf, np.float32)
    high = np.full(3, -np.inf, np.float32)
    for name, geom in geometries.items():
        vertices = np.asarray(getattr(geom, "vertices", []), dtype=np.float32)
        faces = np.asarray(getattr(geom, "faces", []))
        if len(vertices) == 0 or len(faces) == 0:
            continue
        transform = np.eye(4, dtype=np.float32)
        graph = getattr(scene, "graph", None)
        if graph is not None:
            nodes = graph.geometry_nodes.get(name, [])
            if nodes:
                transform = np.asarray(graph.get(nodes[0])[0], dtype=np.float32)
        located = trimesh.transform_points(vertices, transform).astype(np.float32)
        low = np.minimum(low, located.min(axis=0))
        high = np.maximum(high, located.max(axis=0))
        pieces.append((located, faces, _face_colors(geom, faces)))
    if not pieces:
        raise RuntimeError("no triangles")
    center = (low + high) * 0.5
    span = float(np.max(high - low)) or 1.0
    span_px = height * 0.90
    screens = []
    depths = []
    paints = []
    for located, faces, face_colors in pieces:
        tri = ((located - center) / span)[faces]
        depth = tri[:, :, 2].mean(axis=1)
        sx = np.rint(width * 0.5 + tri[:, :, 0] * span_px).astype(np.int32)
        sy = np.rint(height * 0.50 - tri[:, :, 1] * span_px).astype(np.int32)
        min_x = sx.min(axis=1)
        max_x = sx.max(axis=1)
        min_y = sy.min(axis=1)
        max_y = sy.max(axis=1)
        keep = (max_x >= 0) & (min_x < width) & (max_y >= 0) & (min_y < height)
        keep &= (max_x - min_x) < 72
        keep &= (max_y - min_y) < 72
        keep &= (max_x > min_x) & (max_y > min_y)
        if not np.any(keep):
            continue
        screens.append(np.stack([sx[keep], sy[keep]], axis=-1))
        depths.append(depth[keep])
        paints.append(face_colors[keep])
    if not screens:
        raise RuntimeError("no visible triangles")
    points = np.concatenate(screens, axis=0)
    depth = np.concatenate(depths, axis=0)
    color = np.concatenate(paints, axis=0)
    order = np.argsort(depth, kind="mergesort")
    frame = np.full((height, width, 3), _BG, np.uint8)
    for index in order:
        cv2.fillConvexPoly(frame, points[index], color[index].tolist())
    return frame


def _paint_turn(pos, col, yaw, pitch, width, height):
    """Solid triangles at this yaw and pitch when the GL plate is unavailable."""
    tri = np.ascontiguousarray(pos).reshape(-1, 3, 3)
    rgb = np.ascontiguousarray(col).reshape(-1, 3, 3)[:, 0, ::-1]
    step = max(1, len(tri) // 70000)
    tri = tri[::step]
    rgb = rgb[::step]
    yr = np.deg2rad(float(yaw))
    pr = np.deg2rad(float(pitch))
    cy, sy = np.cos(yr), np.sin(yr)
    cp, sp = np.cos(pr), np.sin(pr)
    x, y, z = tri[:, :, 0], tri[:, :, 1], tri[:, :, 2]
    xz = cy * x + sy * z
    zz = -sy * x + cy * z
    y2 = cp * y - sp * zz
    z2 = sp * y + cp * zz
    span_px = height * _FIGURE
    sx = np.rint(width * 0.5 + xz * span_px).astype(np.int32)
    sy = np.rint(height * 0.50 - y2 * span_px).astype(np.int32)
    min_x = sx.min(axis=1)
    max_x = sx.max(axis=1)
    min_y = sy.min(axis=1)
    max_y = sy.max(axis=1)
    keep = (max_x >= 0) & (min_x < width) & (max_y >= 0) & (min_y < height)
    limit = int(min(width, height) * 0.72)
    keep &= (max_x - min_x) < limit
    keep &= (max_y - min_y) < limit
    keep &= (max_x > min_x) & (max_y > min_y)
    frame = np.full((height, width, 3), _BG, np.uint8)
    if not np.any(keep):
        return frame
    points = np.stack([sx[keep], sy[keep]], axis=-1)
    depth = z2[keep].mean(axis=1)
    paint = rgb[keep]
    for index in np.argsort(depth, kind="mergesort"):
        cv2.fillConvexPoly(frame, points[index], paint[index].tolist())
    return frame


def _render_turned(path, width, height, yaw, pitch):
    """Rasterize the solid mesh at this yaw and pitch. None until the mesh is loaded."""
    global _view, _view_key
    if not _orbit_ready or _pos is None or _col is None:
        warm()
        return None
    key = (width, height, round(float(yaw), 2), round(float(pitch), 2))
    if _view_key == key and _view is not None:
        return _view.copy()
    from web import hologram_gl

    try:
        image = hologram_gl.draw(_pos, _col, yaw, pitch, width, height, _BG)
    except Exception as exc:
        print(f"Hologram orbit draw failed: {exc}")
        image = _paint_turn(_pos, _col, yaw, pitch, width, height)
    _view = image
    _view_key = key
    return image.copy()


def _load_orbit(path):
    global _pos, _col, _orbit_key, _orbit_ready
    key = (str(path), path.stat().st_mtime_ns, path.stat().st_size)
    if _orbit_ready and _orbit_key == key and _pos is not None:
        return
    cache = path.with_name(path.stem + ".orbit.npz")
    if cache.is_file() and cache.stat().st_mtime_ns >= path.stat().st_mtime_ns:
        data = np.load(cache)
        col = np.ascontiguousarray(data["col"])
        pos = np.ascontiguousarray(data["pos"])
        _col = col
        _pos = pos
        _orbit_key = key
        _orbit_ready = True
        print(f"Hologram orbit mesh {path.name} ({len(pos)} verts).")
        return
    pos, col = _orbit_arrays(path)
    try:
        np.savez(cache, pos=pos, col=col)
    except Exception as exc:
        print(f"Orbit cache not written ({exc}).")
    _col = col
    _pos = pos
    _orbit_key = key
    _orbit_ready = True
    print(f"Hologram orbit mesh {path.name} ({len(pos)} verts).")


def _orbit_arrays(path):
    """One vertex per triangle corner, in model space, ready to yaw and pitch."""
    import trimesh

    scene = trimesh.load(path, force="scene")
    geometries = getattr(scene, "geometry", None) or {}
    if not geometries and isinstance(scene, trimesh.Trimesh):
        geometries = {"mesh": scene}
    chunks = []
    paints = []
    low = np.full(3, np.inf, np.float32)
    high = np.full(3, -np.inf, np.float32)
    for name, geom in geometries.items():
        vertices = np.asarray(getattr(geom, "vertices", []), dtype=np.float32)
        faces = np.asarray(getattr(geom, "faces", []))
        if len(vertices) == 0 or len(faces) == 0:
            continue
        transform = np.eye(4, dtype=np.float32)
        graph = getattr(scene, "graph", None)
        if graph is not None:
            nodes = graph.geometry_nodes.get(name, [])
            if nodes:
                transform = np.asarray(graph.get(nodes[0])[0], dtype=np.float32)
        located = trimesh.transform_points(vertices, transform).astype(np.float32)
        low = np.minimum(low, located.min(axis=0))
        high = np.maximum(high, located.max(axis=0))
        chunks.append(located[faces])
        paints.append(_face_colors(geom, faces))
    if not chunks:
        raise RuntimeError("no triangles")
    center = (low + high) * 0.5
    span = float(np.max(high - low)) or 1.0
    tri = np.concatenate(chunks, axis=0)
    color = np.concatenate(paints, axis=0)
    tri = (tri - center) / span
    extent = tri.max(axis=1) - tri.min(axis=1)
    keep = np.max(extent, axis=1) < 0.11
    if int(keep.sum()) < max(1, int(len(keep) * 0.05)):
        keep = np.ones(len(keep), dtype=bool)
    tri = tri[keep]
    color = color[keep]
    tri = np.ascontiguousarray(tri.reshape(-1, 3))
    tri[:, 2] *= -1.0
    rgb = np.ascontiguousarray(color[:, ::-1])
    return tri, np.ascontiguousarray(np.repeat(rgb, 3, axis=0))


def _face_colors(geom, faces):
    visual = getattr(geom, "visual", None)
    uv = np.asarray(getattr(visual, "uv", [])) if visual is not None else np.empty((0, 2))
    image = _texture(visual)
    if image is not None and len(uv) > int(faces.max()):
        sample = uv[faces].mean(axis=1)
        height, width = image.shape[:2]
        x = np.clip((sample[:, 0] * (width - 1)).astype(np.int32), 0, width - 1)
        y = np.clip(((1.0 - sample[:, 1]) * (height - 1)).astype(np.int32), 0, height - 1)
        rgb = image[y, x]
        return np.ascontiguousarray(rgb[:, ::-1])
    return np.full((len(faces), 3), (186, 196, 248), np.uint8)


def _texture(visual):
    if visual is None:
        return None
    material = getattr(visual, "material", None)
    if material is None:
        return None
    image = getattr(material, "baseColorTexture", None) or getattr(material, "image", None)
    if image is None:
        return None
    rgb = image.convert("RGB") if hasattr(image, "convert") else image
    return np.asarray(rgb)

