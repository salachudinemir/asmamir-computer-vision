"""
Standalone pygame pixel koi pond.

Dark-navy aquarium with nearest-neighbor pixel koi (Kohaku / Asagi / Yamabuki
and kin), slender ~5:1 silhouette with fan pectorals / pelvic fins / forked
V-tail, soft slow horizontal swim, lily pads, and pink lotus. Interactive:
click/tap calls fish, Space scatters, ripples on the surface. No HUD.

Look & swim ideas inspired by git-koi-aquarium
(https://github.com/reginaldalfret/git-koi-aquarium, MIT) — silhouette proportions,
fin layout, variety coats, fish under botanicals — rewritten as original
pygame code (not a port or wholesale copy of their Go or PNG/GIF assets).

Optional full-pond keyed MP4 overlay (`--overlay` / `O`) still available;
pixel interactive fish are the default.

Run:
    python animation/koi_fish.py
    python animation/koi_fish.py --fullscreen
    python animation/koi_fish.py --overlay
"""

from __future__ import annotations

import argparse
import math
import os
import random
import sys
from enum import Enum, auto
from pathlib import Path

import pygame

os.environ["SDL_VIDEO_CENTERED"] = "1"

pygame.init()
W, H = 1150, 720
screen: pygame.Surface | None = None
clock = pygame.time.Clock()
_ASSETS_DIR = Path(__file__).resolve().parent / "assets"
DEFAULT_MP4_PATH = _ASSETS_DIR / "koi_fish_swimming_animated_overlay.mp4"
OVERLAY_OPACITY = 1.0
OVERLAY_CACHE_MAX_MB = 700.0

# Pixel atlas: slender ~5:1 body (git-koi silhouette feel), nearest-neighbor upscale.
PIXEL_SCALE = 3
PIXEL_BODY_W = 72
PIXEL_BODY_H = 36
SWIM_FRAMES = 6
HEADING_SLEW = 1.55
HEADING_SLEW_FAST = 3.2
FACE_FLIP_COS = 0.42
FACE_FLIP_SIN_MAX = 0.55
FACE_FLIP_CD = 0.7
SEPARATION_RADIUS = 92.0
SEPARATION_GAIN = 48.0
HORIZONTAL_BIAS = 0.55
OUTLINE = (24, 20, 37)

# Palette inspired by classic Japanese morphs (original RGB; ramps echo aquarium coats).
PALETTES: dict[str, dict[str, tuple[int, int, int]]] = {
    "kohaku": {
        "ground": (244, 246, 250),
        "shade": (192, 203, 220),
        "edge": (90, 105, 136),
        "mark": (228, 59, 68),
        "mark2": (240, 96, 79),
        "fin": (236, 240, 248),
        "fin_tip": (246, 117, 122),
        "eye": (24, 20, 37),
    },
    "asagi": {
        "ground": (192, 203, 220),
        "shade": (90, 105, 136),
        "edge": (38, 43, 68),
        "mark": (247, 118, 34),
        "mark2": (254, 174, 52),
        "fin": (247, 118, 34),
        "fin_tip": (190, 74, 47),
        "eye": (24, 20, 37),
        "dorsal": (58, 68, 102),
        "net": (38, 43, 68),
    },
    "yamabuki": {
        "ground": (254, 174, 52),
        "shade": (215, 118, 67),
        "edge": (115, 62, 57),
        "mark": (254, 231, 97),
        "mark2": (255, 243, 176),
        "fin": (254, 210, 90),
        "fin_tip": (247, 118, 34),
        "eye": (28, 22, 18),
    },
    "ogon": {
        "ground": (244, 247, 251),
        "shade": (192, 203, 220),
        "edge": (90, 105, 136),
        "mark": (255, 255, 255),
        "mark2": (139, 155, 180),
        "fin": (236, 242, 250),
        "fin_tip": (254, 174, 52),
        "eye": (22, 24, 32),
    },
    "karasu": {
        "ground": (38, 43, 68),
        "shade": (24, 20, 37),
        "edge": (18, 16, 28),
        "mark": (58, 68, 102),
        "mark2": (90, 105, 136),
        "fin": (58, 68, 102),
        "fin_tip": (139, 155, 180),
        "eye": (200, 190, 170),
    },
    "chagoi": {
        "ground": (184, 111, 80),
        "shade": (115, 62, 57),
        "edge": (62, 39, 49),
        "mark": (228, 166, 114),
        "mark2": (160, 106, 58),
        "fin": (215, 118, 67),
        "fin_tip": (190, 74, 47),
        "eye": (24, 18, 16),
    },
}


def _try_import_cv2():
    try:
        import cv2  # type: ignore

        return cv2
    except ImportError:
        return None


def _create_display(fullscreen: bool) -> pygame.Surface:
    flags = pygame.SCALED | pygame.DOUBLEBUF
    if fullscreen:
        flags |= pygame.FULLSCREEN
    try:
        surf = pygame.display.set_mode((W, H), flags, vsync=1)
    except TypeError:
        surf = pygame.display.set_mode((W, H), flags)
    pygame.display.set_caption("Pixel Koi Pond")
    return surf


def _norm_pi(a: float) -> float:
    return (a + math.pi) % (2 * math.pi) - math.pi


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _body_half_width(along: float) -> float:
    """Slender adult silhouette: blunt nose → shoulder → thin peduncle (~5:1).

    along: 0 at snout, 1 at caudal peduncle (before flare).
    Returns half-width as fraction of max half-width.
    """
    head_slant = 0.18
    nose_w = 0.52
    shoulder = 0.30
    taper_end = 0.92
    tail_w = 0.26
    taper_exp = 1.8
    if along < head_slant:
        return nose_w + (1.0 - nose_w) * math.sin((along / head_slant) * (math.pi * 0.5))
    taper_len = taper_end - shoulder
    taper_prog = max(along - shoulder, 0.0) / max(1e-6, taper_len)
    return max(1.0 - taper_prog**taper_exp, tail_w)


def _put(raw: pygame.Surface, x: int, y: int, rgb: tuple[int, int, int], a: int = 255) -> None:
    bw, bh = raw.get_size()
    if 0 <= x < bw and 0 <= y < bh:
        raw.set_at((x, y), (*rgb, a))


def _paint_fin_lobe(
    raw: pygame.Surface,
    root_x: float,
    root_y: float,
    length: float,
    half_w: float,
    base_angle: float,
    flare: float,
    bend: float,
    col: tuple[int, int, int],
    tip: tuple[int, int, int],
    outline: bool = True,
) -> None:
    """Fan lobe grown backward from root (git-koi-like side/tail fins)."""
    segs = max(4, int(math.ceil(length)))
    seg_len = length / segs
    px, py = root_x, root_y
    for i in range(segs + 1):
        along = i / segs
        # Sin-envelope width: thin at root, fat mid, taper tip.
        width_prog = 0.12 + 0.88 * along
        hw = half_w * (math.sin(math.pi * min(1.0, width_prog)) ** 0.6) * (0.55 + 0.45 * flare)
        ang = base_angle + bend * along
        nx, ny = -math.sin(ang), math.cos(ang)
        c = tip if along > 0.62 else col
        for s in range(-int(hw) - 1, int(hw) + 2):
            if abs(s) > hw + 0.35:
                continue
            fx = int(round(px + nx * s))
            fy = int(round(py + ny * s))
            if outline and abs(abs(s) - hw) < 0.85:
                _put(raw, fx, fy, OUTLINE, 255)
            else:
                _put(raw, fx, fy, c, 235 if along > 0.15 else 210)
        px += math.cos(ang) * seg_len
        py += math.sin(ang) * seg_len


def _mark_color(
    variety: str,
    pal: dict[str, tuple[int, int, int]],
    along: float,
    lat: float,
    seed: int,
) -> tuple[int, int, int]:
    """Irregular koi plates/spots on a pale ground (original patterns)."""
    # along: 0 snout → 1 peduncle; lat: -1..1 across body.
    if abs(lat) > 0.82:
        return pal["edge"]
    c = pal["ground"]
    if lat > 0.35:
        c = pal.get("shade", pal["edge"])

    def plate(cx: float, cy: float, rx: float, ry: float) -> bool:
        return ((along - cx) / rx) ** 4 + ((lat - cy) / ry) ** 4 < 1.0

    if variety == "kohaku":
        leans = ((seed % 5) - 2) * 0.08
        if plate(0.18, leans * 0.4, 0.12, 0.72) or plate(0.42, leans, 0.14, 0.70) or plate(
            0.66, -leans * 0.6, 0.11, 0.65
        ):
            c = pal["mark"] if abs(lat) < 0.55 else pal["mark2"]
    elif variety == "asagi":
        if along < 0.12:
            c = (244, 246, 250)
        elif abs(lat) > 0.62:
            c = pal["mark"] if (int(along * 20) + seed) % 3 else pal["mark2"]
        else:
            # Dorsal net / saddle.
            row = int((lat + 1.0) * 6)
            col = int(along * 22 + (row % 2) * 0.5)
            if min(abs((lat + 1) * 6 - row), abs(along * 22 - col)) < 0.18:
                c = pal.get("net", pal["edge"])
            else:
                c = pal.get("dorsal", pal["shade"])
                if plate(0.35, 0.1, 0.1, 0.35) or plate(0.55, -0.15, 0.08, 0.3):
                    c = pal["mark2"]
    elif variety == "yamabuki":
        if plate(0.25, 0.05, 0.16, 0.55) or plate(0.55, -0.1, 0.14, 0.5):
            c = pal["mark"]
        elif abs(lat) < 0.25 and 0.3 < along < 0.5:
            c = pal["mark2"]
    elif variety == "ogon":
        if abs(lat) < 0.3 and 0.2 < along < 0.55 and (seed + int(along * 10)) % 3 == 0:
            c = pal["mark"]
        elif plate(0.4, 0.2, 0.12, 0.4):
            c = pal["mark2"]
    elif variety == "karasu":
        if (int(along * 16) ^ int(abs(lat) * 12) ^ seed) & 1:
            c = pal["mark"]
        if plate(0.5, 0.0, 0.2, 0.55):
            c = pal["mark2"]
    elif variety == "chagoi":
        if abs(lat) < 0.45 and (hash((seed, int(along * 14), int(lat * 10))) % 5) < 2:
            c = pal["mark"]
        elif plate(0.35, -0.15, 0.12, 0.4):
            c = pal["mark2"]

    # Soft highlight on upper flank.
    if lat < -0.12 and abs(lat) < 0.55 and along < 0.85:
        c = tuple(min(255, int(ch + 16)) for ch in c)
    return c


def _paint_pixel_koi(variety: str, frame: int, seed: int) -> pygame.Surface:
    """Paint one low-res koi frame facing +X; slender body + fan fins + V-tail."""
    pal = PALETTES.get(variety, PALETTES["kohaku"])
    bw, bh = PIXEL_BODY_W, PIXEL_BODY_H
    raw = pygame.Surface((bw, bh), pygame.SRCALPHA)
    cy = bh // 2
    phase = (frame / max(1, SWIM_FRAMES - 1)) * math.pi * 2.0
    wag = math.sin(phase) * 1.35
    fin_flare = 0.62 + 0.38 * abs(math.sin(phase * 0.5))

    # Body span: leave room for forked tail on the left, snout on the right.
    body_x0 = 18  # peduncle
    body_x1 = bw - 4  # snout
    body_len = body_x1 - body_x0
    max_half = body_len * 0.10  # ~5:1 length:width

    # --- Tail (two V lobes, grown backward from peduncle) ---
    ped_x = float(body_x0)
    ped_y = float(cy + wag * 0.9)
    ped_half = max_half * _body_half_width(0.98)
    tail_len = max_half * 2.0 * 1.75
    tail_hw = max_half * 1.15
    for side, ang_off, bend in (
        (-1, -0.62, -0.22 * fin_flare),
        (1, 0.48, 0.18 * fin_flare),
    ):
        _paint_fin_lobe(
            raw,
            ped_x,
            ped_y + side * ped_half * 0.2,
            tail_len,
            tail_hw,
            math.pi + ang_off,  # backward (−X)
            fin_flare,
            bend,
            pal["fin"],
            pal.get("fin_tip", pal["mark"]),
        )

    # --- Body + markings ---
    for xi in range(body_x0, body_x1 + 1):
        # along_from_snout: 0 at snout (right), 1 at peduncle (left)
        along = (body_x1 - xi) / float(body_len)
        # wave stronger toward tail
        y_off = wag * (along**1.35) * 1.7
        half = max(1.15, max_half * _body_half_width(along))
        y0 = int(cy - half + y_off)
        y1 = int(cy + half + y_off)
        for y in range(max(0, y0), min(bh, y1 + 1)):
            lat = (y - (cy + y_off)) / max(0.5, half)
            if abs(lat) > 1.0:
                continue
            c = _mark_color(variety, pal, along, lat, seed)
            # Inner rim shade near outline.
            if abs(lat) > 0.78:
                c = pal["edge"]
            _put(raw, xi, y, c, 255)

    # Dark outline around body (1px ring on transparent neighbors).
    for xi in range(body_x0 - 1, body_x1 + 2):
        for y in range(bh):
            pix = raw.get_at((xi, y)) if 0 <= xi < bw else (0, 0, 0, 0)
            if pix[3] != 0:
                continue
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                nx, ny = xi + dx, y + dy
                if 0 <= nx < bw and 0 <= ny < bh and raw.get_at((nx, ny))[3] != 0:
                    # Only outline body column neighborhood (fins already outlined).
                    if body_x0 - 1 <= nx <= body_x1 + 1:
                        _put(raw, xi, y, OUTLINE, 255)
                    break

    # --- Pectoral fins (large wing-like fans just behind shoulders) ---
    pec_along = 0.20
    pec_x = body_x1 - pec_along * body_len
    pec_y = cy + wag * (pec_along**1.3) * 1.2
    pec_len = max_half * 2.0 * 1.45
    pec_hw = max_half * 1.15
    for side in (-1, 1):
        root_y = pec_y + side * max_half * _body_half_width(pec_along) * 0.85
        # Angle more lateral/backward so fins read as wide fans, not stubs.
        _paint_fin_lobe(
            raw,
            pec_x,
            root_y,
            pec_len,
            pec_hw,
            math.pi + side * 0.85,
            fin_flare,
            side * 0.22 * fin_flare,
            pal["fin"],
            pal.get("fin_tip", pal["mark"]),
        )

    # --- Pelvic fins (smaller, mid-body) ---
    pel_along = 0.47
    pel_x = body_x1 - pel_along * body_len
    pel_y = cy + wag * (pel_along**1.3) * 1.4
    pel_len = max_half * 2.0 * 0.72
    pel_hw = max_half * 0.55
    for side in (-1, 1):
        root_y = pel_y + side * max_half * _body_half_width(pel_along) * 0.7
        _paint_fin_lobe(
            raw,
            pel_x,
            root_y,
            pel_len,
            pel_hw,
            math.pi + side * 0.55,
            fin_flare * 0.9,
            side * 0.12,
            pal["fin"],
            pal.get("fin_tip", pal["mark"]),
        )

    # Eyes (paired, near snout)
    eye_along = 0.07
    ex = int(body_x1 - eye_along * body_len)
    for side in (-1, 1):
        ey = int(cy + side * max_half * 0.55 + wag * 0.1)
        _put(raw, ex, ey, pal["eye"], 255)
        _put(raw, ex, ey + side, (255, 255, 255), 180)

    # Barbels from snout
    snx = body_x1
    for side in (-1, 1):
        for i in range(3):
            _put(
                raw,
                snx + 1 + i // 2,
                int(cy + side * (1 + i * 0.7) + wag * 0.05),
                pal.get("shade", pal["edge"]),
                200,
            )

    # Dorsal shade line (thin darker spine)
    for xi in range(body_x0 + 2, body_x1 - 4):
        along = (body_x1 - xi) / float(body_len)
        if 0.25 < along < 0.65:
            yy = int(cy + wag * (along**1.35) * 1.7)
            pix = raw.get_at((xi, yy))
            if pix[3]:
                dim = tuple(max(0, ch - 28) for ch in pix[:3])
                _put(raw, xi, yy, dim, 255)

    scaled = pygame.transform.scale(raw, (bw * PIXEL_SCALE, bh * PIXEL_SCALE))
    if pygame.display.get_surface() is not None:
        return scaled.convert_alpha()
    return scaled


class PixelKoiAtlas:
    def __init__(self):
        self._frames: dict[str, list[pygame.Surface]] = {}
        for name in PALETTES:
            seed = sum(ord(c) for c in name) * 13
            self._frames[name] = [
                _paint_pixel_koi(name, f, seed) for f in range(SWIM_FRAMES)
            ]

    def frame(self, variety: str, phase: float) -> pygame.Surface:
        frames = self._frames.get(variety) or self._frames["kohaku"]
        n = len(frames)
        t = (phase * 0.55) % (2.0 * (n - 1))
        idx = int(t) if t <= (n - 1) else int(2.0 * (n - 1) - t)
        return frames[max(0, min(n - 1, idx))]


def _key_video_frame_bgr(
    frame_bgr,
    chroma_max: float = 20.0,
    gray_lo: float = 12.0,
    gray_hi: float = 105.0,
):
    import numpy as np

    b = frame_bgr[:, :, 0].astype(np.float32)
    g = frame_bgr[:, :, 1].astype(np.float32)
    r = frame_bgr[:, :, 2].astype(np.float32)
    mx = np.maximum(np.maximum(r, g), b)
    mn = np.minimum(np.minimum(r, g), b)
    chroma = mx - mn
    gray = (r + g + b) * (1.0 / 3.0)
    dark_bg = (chroma < chroma_max) & (gray < gray_hi) & (gray > gray_lo)
    pure_black_bg = gray <= gray_lo
    bg_mask = dark_bg | pure_black_bg
    hard_u8 = bg_mask.astype(np.uint8) * 255
    cv2 = _try_import_cv2()
    if cv2 is not None:
        hard_u8 = cv2.erode(hard_u8, np.ones((2, 2), np.uint8), iterations=1)
        alpha = 255 - hard_u8
        alpha = cv2.GaussianBlur(alpha, (5, 5), 0)
    else:
        alpha = np.where(bg_mask, np.uint8(0), np.uint8(255))
    return alpha


class KoiOverlayVideo:
    def __init__(
        self,
        path: Path,
        size: tuple[int, int],
        opacity: float = OVERLAY_OPACITY,
        max_cache_mb: float = OVERLAY_CACHE_MAX_MB,
    ):
        self.path = Path(path)
        self.size = size
        self.opacity = max(0.0, min(1.0, opacity))
        self.enabled = True
        self._cv2 = None
        self._fps = 30.0
        self._accum = 0.0
        self._index = 0
        self._frames: list[pygame.Surface] = []
        self._ok = False
        self._max_cache_mb = max_cache_mb
        self._open()

    @property
    def available(self) -> bool:
        return self._ok

    def _open(self) -> None:
        if not self.path.is_file():
            return
        self._cv2 = _try_import_cv2()
        if self._cv2 is None:
            print(f"[koi] OpenCV unavailable; skipping MP4 {self.path.name}", file=sys.stderr)
            return
        cap = self._cv2.VideoCapture(str(self.path))
        if not cap.isOpened():
            print(f"[koi] Could not open video: {self.path}", file=sys.stderr)
            return
        fps = float(cap.get(self._cv2.CAP_PROP_FPS) or 0.0)
        self._fps = fps if fps > 1.0 else 30.0
        reported = int(cap.get(self._cv2.CAP_PROP_FRAME_COUNT) or 0)
        tw, th = self.size
        bytes_per = tw * th * 4
        est_all_mb = (max(reported, 1) * bytes_per) / (1024.0 * 1024.0)
        stride = 1
        if est_all_mb > self._max_cache_mb and reported > 0:
            stride = max(1, int(math.ceil(est_all_mb / self._max_cache_mb)))
        frames: list[pygame.Surface] = []
        i = 0
        while True:
            ok, frame = cap.read()
            if not ok or frame is None:
                break
            if i % stride == 0:
                frames.append(self._bgr_to_surface(frame))
            i += 1
        cap.release()
        if not frames:
            return
        self._frames = frames
        if stride > 1:
            self._fps = max(1.0, self._fps / stride)
        self._ok = True
        cache_mb = (len(frames) * bytes_per) / (1024.0 * 1024.0)
        print(
            f"[koi] MP4 cached: {self.path.name} "
            f"({len(frames)} frames @ {self._fps:.1f} fps, ~{cache_mb:.0f} MiB)"
        )

    def close(self) -> None:
        self._frames.clear()
        self._ok = False

    def _bgr_to_surface(self, frame_bgr) -> pygame.Surface:
        import numpy as np

        cv2 = self._cv2
        assert cv2 is not None
        tw, th = self.size
        if frame_bgr.shape[1] != tw or frame_bgr.shape[0] != th:
            frame_bgr = cv2.resize(frame_bgr, (tw, th), interpolation=cv2.INTER_AREA)
        alpha = _key_video_frame_bgr(frame_bgr)
        if self.opacity < 1.0:
            alpha = (alpha.astype(np.float32) * self.opacity).astype(np.uint8)
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        rgba = np.dstack((rgb, alpha))
        surf = pygame.image.frombuffer(rgba.tobytes(), (tw, th), "RGBA").convert_alpha()
        return surf.copy()

    def update(self, dt: float) -> None:
        if not self._ok or not self.enabled or not self._frames:
            return
        self._accum += dt
        step = 1.0 / self._fps
        while self._accum >= step:
            self._accum -= step
            self._index = (self._index + 1) % len(self._frames)

    def draw(self, surf: pygame.Surface) -> None:
        if self._ok and self.enabled and self._frames:
            surf.blit(self._frames[self._index], (0, 0))


class SwimState(Enum):
    CRUISE = auto()
    GLIDE = auto()
    REST = auto()
    DART = auto()
    FEED = auto()


class SoftCircuit:
    def __init__(self, cx: float, cy: float, rx: float, ry: float, phase0: float = 0.0):
        self.cx = cx
        self.cy = cy
        self.rx = rx
        self.ry = ry
        self.u = phase0

    def advance(self, speed: float, dt: float) -> tuple[float, float, float]:
        peri = 2 * math.pi * math.sqrt((self.rx ** 2 + self.ry ** 2) * 0.5)
        self.u = (self.u + (speed * dt) / max(1.0, peri)) % 1.0
        ang = self.u * 2 * math.pi
        x = self.cx + math.cos(ang) * self.rx
        y = self.cy + math.sin(ang) * self.ry
        tx = -math.sin(ang) * self.rx
        ty = math.cos(ang) * self.ry
        return x, y, math.atan2(ty, tx)


class PixelKoi:
    def __init__(
        self,
        x: float,
        y: float,
        angle: float,
        base_speed: float,
        scale: float,
        variety: str,
        circuit: SoftCircuit,
    ):
        self.x = x
        self.y = y
        self.angle = angle
        self.base_speed = base_speed
        self.speed = base_speed
        self.scale = scale
        self.variety = variety
        self.circuit = circuit
        self.phase = random.uniform(0, 6.28)
        self.turn_vel = 0.0
        self.depth = random.uniform(0.2, 0.7)
        self.depth_vel = 0.0
        self.state = SwimState.CRUISE
        self.state_timer = random.uniform(2.5, 5.0)
        self.call_timer = 0.0
        self.call_target: tuple[float, float] | None = None
        self.scatter_timer = 0.0
        self.scatter_heading = angle
        self._visual_angle = float(angle)
        self._face_left = math.cos(angle) < 0.0
        self._face_flip_cd = 0.0
        self._stroke_t = random.uniform(0, 1)
        self._stroke_period = random.uniform(2.6, 3.8)

    def attract_to(self, tx: float, ty: float) -> None:
        self.call_target = (tx, ty)
        self.call_timer = random.uniform(2.8, 4.0)
        self.scatter_timer = 0.0
        desired = math.atan2(ty - self.y, tx - self.x)
        diff = _norm_pi(desired - self.angle)
        self.turn_vel = max(-1.4, min(1.4, diff * 1.8))
        dist = math.hypot(tx - self.x, ty - self.y)
        if dist > 280:
            self._enter(SwimState.DART, random.uniform(0.7, 1.1))
        else:
            self._enter(SwimState.FEED, random.uniform(1.4, 2.2))
        self.depth_vel -= 0.25

    def scatter(self) -> None:
        self.call_timer = 0.0
        self.call_target = None
        self.scatter_heading = self.angle + random.uniform(-2.2, 2.2)
        self.scatter_timer = random.uniform(1.2, 1.9)
        self._enter(SwimState.DART, random.uniform(0.8, 1.3))
        self.depth_vel += random.uniform(0.1, 0.35)

    def _enter(self, state: SwimState, duration: float) -> None:
        self.state = state
        self.state_timer = duration

    def _pick_idle(self) -> None:
        roll = random.random()
        if roll < 0.48:
            self._enter(SwimState.CRUISE, random.uniform(3.5, 7.0))
        elif roll < 0.78:
            self._enter(SwimState.GLIDE, random.uniform(2.0, 4.5))
        elif roll < 0.93:
            self._enter(SwimState.REST, random.uniform(1.5, 3.2))
        else:
            self._enter(SwimState.DART, random.uniform(0.45, 0.85))

    def _stroke_beat(self) -> float:
        share = 0.48 if self.state != SwimState.DART else 0.34
        frac = self._stroke_t % 1.0
        if frac < share:
            return math.sin(math.pi * frac / share)
        return 0.0

    def update(self, dt: float, neighbors: list["PixelKoi"]) -> None:
        self.state_timer -= dt
        if self.call_timer > 0:
            self.call_timer -= dt
        if self.scatter_timer > 0:
            self.scatter_timer -= dt

        self.depth_vel += random.uniform(-0.15, 0.15) * dt
        self.depth_vel *= 0.93
        self.depth = max(0.05, min(0.92, self.depth + self.depth_vel * dt))

        self._stroke_t += dt / self._stroke_period
        beat = self._stroke_beat()

        sep_x, sep_y = 0.0, 0.0
        for other in neighbors:
            if other is self:
                continue
            dx = self.x - other.x
            dy = self.y - other.y
            d2 = dx * dx + dy * dy
            if d2 < 1e-2 or d2 > SEPARATION_RADIUS * SEPARATION_RADIUS:
                continue
            d = math.sqrt(d2)
            push = (SEPARATION_RADIUS - d) / SEPARATION_RADIUS
            sep_x += (dx / d) * push
            sep_y += (dy / d) * push

        if self.scatter_timer > 0:
            diff = _norm_pi(self.scatter_heading - self.angle)
            self.turn_vel = max(-1.6, min(1.6, diff * 2.2))
            if self.state != SwimState.DART:
                self._enter(SwimState.DART, max(self.state_timer, 0.4))
        elif self.call_timer > 0 and self.call_target is not None:
            tx, ty = self.call_target
            desired = math.atan2(ty - self.y, tx - self.x)
            diff = _norm_pi(desired - self.angle)
            dist = math.hypot(tx - self.x, ty - self.y)
            self.turn_vel = max(-1.5, min(1.5, diff * 2.0))
            if dist < 48:
                self._enter(SwimState.FEED, random.uniform(0.8, 1.6))
        elif self.state_timer <= 0:
            self._pick_idle()

        if self.state == SwimState.CRUISE:
            target_speed = self.base_speed * (0.72 + 0.45 * beat)
            self.turn_vel += random.uniform(-0.45, 0.45) * dt
            self.turn_vel *= 0.96
        elif self.state == SwimState.GLIDE:
            target_speed = self.base_speed * (0.38 + 0.2 * beat)
            self.turn_vel *= 0.9
        elif self.state == SwimState.REST:
            target_speed = self.base_speed * 0.1
            self.turn_vel += math.sin(self.phase * 0.9) * 0.28 * dt
            self.turn_vel *= 0.92
        elif self.state == SwimState.DART:
            target_speed = self.base_speed * (1.55 + 0.9 * beat)
            self.turn_vel *= 0.97
        else:
            target_speed = self.base_speed * (0.22 + 0.35 * beat)
            self.turn_vel *= 0.94

        # Prefer near-horizontal headings (aquarium left/right swim feel).
        if self.call_timer <= 0 and self.scatter_timer <= 0 and self.state in (
            SwimState.CRUISE,
            SwimState.GLIDE,
            SwimState.FEED,
        ):
            horiz = math.pi if math.cos(self.angle) < 0.0 else 0.0
            self.turn_vel += _norm_pi(horiz - self.angle) * HORIZONTAL_BIAS * dt

        self.speed += (target_speed - self.speed) * min(1.0, 2.4 * dt)

        if self.call_timer <= 0 and self.scatter_timer <= 0 and self.state in (
            SwimState.CRUISE,
            SwimState.GLIDE,
        ):
            cx, cy, ch = self.circuit.advance(self.speed * 0.85, dt)
            seek = math.atan2(cy - self.y, cx - self.x)
            blend = 0.55
            desired = math.atan2(
                math.sin(ch) * (1 - blend) + math.sin(seek) * blend,
                math.cos(ch) * (1 - blend) + math.cos(seek) * blend,
            )
            self.turn_vel += _norm_pi(desired - self.angle) * 0.9 * dt

        if sep_x or sep_y:
            sep_ang = math.atan2(sep_y, sep_x)
            self.turn_vel += _norm_pi(sep_ang - self.angle) * 1.1 * dt
            self.x += sep_x * SEPARATION_GAIN * dt * 0.02
            self.y += sep_y * SEPARATION_GAIN * dt * 0.02

        margin = 140
        steer_x, steer_y = 0.0, 0.0
        if self.x < margin:
            steer_x += (margin - self.x) / margin
        elif self.x > W - margin:
            steer_x -= (self.x - (W - margin)) / margin
        if self.y < margin:
            steer_y += (margin - self.y) / margin
        elif self.y > H - margin:
            steer_y -= (self.y - (H - margin)) / margin
        if steer_x or steer_y:
            wall_ang = math.atan2(steer_y, steer_x)
            self.angle += _norm_pi(wall_ang - self.angle) * 1.1 * dt
        else:
            max_turn = 1.35 if self.state == SwimState.DART else 0.95
            self.angle += max(-max_turn, min(max_turn, self.turn_vel)) * dt

        self.x += math.cos(self.angle) * self.speed * dt
        self.y += math.sin(self.angle) * self.speed * dt

        wave = 0.75 + self.speed * 0.03
        if self.state == SwimState.DART:
            wave = 1.55 + self.speed * 0.04
        elif self.state == SwimState.REST:
            wave = 0.45
        self.phase += wave * dt

        vdiff = _norm_pi(self.angle - self._visual_angle)
        slew = (
            HEADING_SLEW_FAST
            if self.state == SwimState.DART or self.call_timer > 0 or self.scatter_timer > 0
            else HEADING_SLEW
        )
        step = slew * dt
        if abs(vdiff) <= step:
            self._visual_angle = self.angle
        else:
            self._visual_angle += math.copysign(step, vdiff)

        if self._face_flip_cd > 0:
            self._face_flip_cd = max(0.0, self._face_flip_cd - dt)
        vc = math.cos(self._visual_angle)
        vs = abs(math.sin(self._visual_angle))
        if self._face_flip_cd <= 0.0 and vs <= FACE_FLIP_SIN_MAX:
            if vc < -FACE_FLIP_COS and not self._face_left:
                self._face_left = True
                self._face_flip_cd = FACE_FLIP_CD
            elif vc > FACE_FLIP_COS and self._face_left:
                self._face_left = False
                self._face_flip_cd = FACE_FLIP_CD

    def draw(self, surf: pygame.Surface, atlas: PixelKoiAtlas) -> None:
        img = atlas.frame(self.variety, self.phase)
        depth_scale = 1.12 - self.depth * 0.28
        zoom = self.scale * depth_scale
        pose = pygame.transform.flip(img, True, False) if self._face_left else img
        if self._face_left:
            rot_deg = math.degrees(_norm_pi(self._visual_angle - math.pi))
        else:
            rot_deg = -math.degrees(self._visual_angle)
        try:
            if abs(zoom - 1.0) > 0.02:
                nw = max(8, int(pose.get_width() * zoom))
                nh = max(8, int(pose.get_height() * zoom))
                pose = pygame.transform.scale(pose, (nw, nh))
            drawn = pygame.transform.rotate(pose, rot_deg)
        except pygame.error:
            return

        opacity = max(0.4, min(1.0, 1.02 - self.depth * 0.5))
        if opacity < 0.98:
            drawn = drawn.copy()
            drawn.set_alpha(max(50, int(255 * opacity)))

        sw, sh = drawn.get_width(), drawn.get_height()
        shadow = pygame.Surface((sw, sh), pygame.SRCALPHA)
        pygame.draw.ellipse(
            shadow,
            (2, 8, 18, int(28 + (1.0 - self.depth) * 36)),
            shadow.get_rect().inflate(-int(sw * 0.2), -int(sh * 0.4)),
        )
        ox = 8 + (1.0 - self.depth) * 12
        oy = 10 + (1.0 - self.depth) * 14
        surf.blit(shadow, shadow.get_rect(center=(self.x + ox, self.y + oy)))
        surf.blit(drawn, drawn.get_rect(center=(self.x, self.y)))


def create_pond_bed() -> pygame.Surface:
    bed = pygame.Surface((W, H))
    cx, cy = W * 0.5, H * 0.45
    max_d = math.hypot(cx, cy)
    for y in range(0, H, 2):
        for x in range(0, W, 2):
            d = math.hypot(x - cx, y - cy) / max_d
            r = int(_lerp(8, 14, 1 - d) * (1 - d * 0.55) + 2)
            g = int(_lerp(16, 40, 1 - d) * (1 - d * 0.5) + 4)
            b = int(_lerp(24, 72, 1 - d) * (1 - d * 0.4) + 10)
            pygame.draw.rect(bed, (r, g, b), (x, y, 2, 2))
    rng = random.Random(7)
    gravel = pygame.Surface((W, H), pygame.SRCALPHA)
    for _ in range(90):
        gx = rng.randint(20, W - 20)
        gy = rng.randint(int(H * 0.55), H - 12)
        gr = rng.randint(1, 3)
        pygame.draw.circle(gravel, (30, 55, 90, rng.randint(40, 90)), (gx, gy), gr)
    bed.blit(gravel, (0, 0))
    return bed


def draw_botanicals(surf: pygame.Surface, t: float) -> None:
    pads = [
        (110, 95, 70, 0.4, True, 1.0),
        (175, 145, 48, 2.1, False, 0.85),
        (70, 160, 36, 1.2, False, 0.7),
        (1040, 560, 78, 3.5, True, 1.1),
        (980, 620, 52, 0.8, False, 0.9),
        (1085, 500, 40, 2.4, False, 0.75),
        (1000, 80, 44, 1.5, False, 0.7),
        (90, 600, 38, 0.3, False, 0.65),
    ]
    for px, py, rad, notch, has_flower, scale in pads:
        sway_x = math.sin(t * 0.55 + px * 0.01) * 2.2
        sway_y = math.cos(t * 0.48 + py * 0.01) * 1.8
        x, y = px + sway_x, py + sway_y
        r = int(rad * scale)
        ps = pygame.Surface((r * 2 + 36, r * 2 + 36), pygame.SRCALPHA)
        c = r + 14
        pygame.draw.circle(ps, (0, 10, 20, 90), (c + 10, c + 14), r)
        pygame.draw.circle(ps, (26, 78, 48), (c, c), r)
        pygame.draw.circle(ps, (40, 110, 62), (c - 2, c - 2), int(r * 0.86))
        for k in range(7):
            va = notch + 0.4 + k * 0.75
            pygame.draw.line(
                ps,
                (56, 130, 78, 130),
                (c, c),
                (c + math.cos(va) * r * 0.82, c + math.sin(va) * r * 0.82),
                1,
            )
        cut = [
            (c, c),
            (c + math.cos(notch - 0.22) * (r + 3), c + math.sin(notch - 0.22) * (r + 3)),
            (c + math.cos(notch + 0.22) * (r + 3), c + math.sin(notch + 0.22) * (r + 3)),
        ]
        pygame.draw.polygon(ps, (0, 0, 0, 0), cut)
        if has_flower:
            fx, fy = c - 4, c - 6
            for layer_r, col in [
                (15, (250, 170, 200)),
                (11, (252, 200, 220)),
                (6, (255, 236, 140)),
            ]:
                for p_ang in range(0, 360, 45):
                    ra = math.radians(p_ang + t * 3)
                    pygame.draw.circle(
                        ps,
                        col,
                        (
                            int(fx + math.cos(ra) * layer_r * 0.5),
                            int(fy + math.sin(ra) * layer_r * 0.5),
                        ),
                        max(2, layer_r // 2),
                    )
            pygame.draw.circle(ps, (255, 220, 80), (int(fx), int(fy)), 4)
        surf.blit(ps, (int(x - c), int(y - c)))


def draw_caustics(surf: pygame.Surface, t: float) -> None:
    layer = pygame.Surface((W, H), pygame.SRCALPHA)
    for i in range(5):
        cx = W * 0.5 + math.cos(t * 0.22 + i * 1.3) * 260
        cy = H * 0.48 + math.sin(t * 0.18 + i * 1.1) * 160
        rad = int(120 + 30 * math.sin(t * 0.4 + i))
        pygame.draw.circle(layer, (90, 170, 220, 7), (int(cx), int(cy)), rad)
    surf.blit(layer, (0, 0))


class Ripple:
    def __init__(self, x, y, max_r=95, strength=1.0):
        self.x = x
        self.y = y
        self.r = 4.0
        self.max_r = max_r
        self.strength = strength
        self.alpha = 100.0 * strength

    def update(self, dt):
        self.r += 36.0 * dt
        self.alpha = max(0.0, 100.0 * self.strength * (1.0 - self.r / self.max_r))

    def draw(self, surf):
        if self.alpha > 2:
            size = int(self.r * 2 + 6)
            rs = pygame.Surface((size, size), pygame.SRCALPHA)
            c = size // 2
            pygame.draw.circle(rs, (160, 210, 240, int(self.alpha)), (c, c), int(self.r), 1)
            if self.r > 16:
                pygame.draw.circle(
                    rs, (160, 210, 240, int(self.alpha * 0.45)), (c, c), int(self.r - 10), 1
                )
            surf.blit(rs, (int(self.x - c), int(self.y - c)))


def _parse_args(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(description="Standalone pygame pixel koi pond")
    parser.add_argument(
        "--mp4",
        type=Path,
        default=DEFAULT_MP4_PATH,
        help="Path to optional MP4 for overlay mode.",
    )
    parser.add_argument(
        "--overlay",
        nargs="?",
        const=None,
        default=None,
        type=Path,
        help="Start with full-pond keyed MP4 animation (toggle with O).",
    )
    parser.add_argument(
        "--fullscreen",
        action="store_true",
        help="Start fullscreen (F11 toggles; SCALED logical 1150x720).",
    )
    return parser.parse_args(argv)


def _load_overlay(path: Path) -> KoiOverlayVideo | None:
    candidate = Path(path)
    if not candidate.is_file():
        print(f"[koi] MP4 file missing ({candidate}).", file=sys.stderr)
        return None
    print("[koi] Caching keyed MP4 frames (one-time)…", file=sys.stderr)
    overlay = KoiOverlayVideo(candidate, (W, H), opacity=OVERLAY_OPACITY)
    if not overlay.available:
        return None
    return overlay


def _spawn_koi() -> list[PixelKoi]:
    # Flattened ellipses → more horizontal lap feel (like git-koi lap courses).
    circuits = [
        SoftCircuit(W * 0.5, H * 0.48, 400, 140, 0.00),
        SoftCircuit(W * 0.32, H * 0.32, 180, 48, 0.50),
        SoftCircuit(W * 0.68, H * 0.34, 180, 48, 0.50),
        SoftCircuit(W * 0.50, H * 0.52, 260, 52, 0.00),
        SoftCircuit(W * 0.30, H * 0.68, 170, 42, 0.50),
        SoftCircuit(W * 0.70, H * 0.68, 170, 42, 0.00),
        SoftCircuit(W * 0.48, H * 0.38, 300, 90, 0.25),
        SoftCircuit(W * 0.42, H * 0.60, 220, 58, 0.70),
        SoftCircuit(W * 0.58, H * 0.58, 210, 55, 0.15),
    ]
    # Speeds kept deliberately low; ~18 fish; scale down a bit for longer sprites.
    specs = [
        (circuits[0], "kohaku", 24, 0.92, 0.05),
        (circuits[0], "yamabuki", 22, 0.88, 0.55),
        (circuits[0], "asagi", 21, 0.86, 0.30),
        (circuits[1], "asagi", 20, 0.84, 0.10),
        (circuits[1], "kohaku", 19, 0.78, 0.65),
        (circuits[2], "kohaku", 20, 0.82, 0.20),
        (circuits[2], "yamabuki", 18, 0.76, 0.72),
        (circuits[3], "asagi", 19, 0.80, 0.40),
        (circuits[3], "karasu", 18, 0.74, 0.75),
        (circuits[4], "ogon", 20, 0.78, 0.15),
        (circuits[4], "chagoi", 17, 0.72, 0.80),
        (circuits[5], "chagoi", 19, 0.80, 0.60),
        (circuits[5], "ogon", 18, 0.74, 0.35),
        (circuits[6], "kohaku", 21, 0.86, 0.45),
        (circuits[6], "karasu", 17, 0.70, 0.88),
        (circuits[7], "yamabuki", 18, 0.76, 0.22),
        (circuits[8], "asagi", 19, 0.78, 0.58),
        (circuits[8], "chagoi", 16, 0.68, 0.05),
    ]
    fish: list[PixelKoi] = []
    for circ, variety, speed, scale, phase in specs:
        own = SoftCircuit(circ.cx, circ.cy, circ.rx, circ.ry, phase)
        x, y, heading = own.advance(0.0, 0.0)
        x += random.uniform(-12, 12)
        y += random.uniform(-8, 8)
        fish.append(PixelKoi(x, y, heading, speed, scale, variety, own))
    return fish


def main(argv: list[str] | None = None):
    global screen

    args = _parse_args(argv)
    fullscreen = bool(args.fullscreen)
    screen = _create_display(fullscreen)
    pond_bed = create_pond_bed()
    atlas = PixelKoiAtlas()
    kois = _spawn_koi()

    source_mp4 = Path(args.overlay) if isinstance(args.overlay, Path) else Path(args.mp4)
    want_overlay = args.overlay is not None or isinstance(args.overlay, Path)
    overlay: KoiOverlayVideo | None = None
    if want_overlay:
        overlay = _load_overlay(source_mp4)
        if overlay is not None:
            overlay.enabled = True

    ripples: list[Ripple] = []
    ripple_timer = 0.0
    surface_ripple_timer = 0.0
    sim_time = 0.0

    running = True
    try:
        while running:
            dt = clock.tick(60) / 1000.0
            sim_time += dt
            assert screen is not None

            overlay_active = (
                overlay is not None and overlay.available and overlay.enabled
            )

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_F11:
                        fullscreen = not fullscreen
                        screen = _create_display(fullscreen)
                    elif event.key == pygame.K_SPACE and not overlay_active and kois:
                        for k in kois:
                            k.scatter()
                        for k in kois:
                            ripples.append(Ripple(k.x, k.y, max_r=90, strength=0.7))
                    elif event.key == pygame.K_o:
                        if overlay is None:
                            overlay = _load_overlay(source_mp4)
                            if overlay is not None:
                                overlay.enabled = True
                        elif overlay.available:
                            overlay.enabled = not overlay.enabled
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    mx, my = event.pos
                    ripples.append(Ripple(mx, my, max_r=140, strength=1.15))
                    if not overlay_active:
                        for k in kois:
                            k.attract_to(mx, my)

            screen.blit(pond_bed, (0, 0))
            draw_caustics(screen, sim_time)

            if overlay_active:
                assert overlay is not None
                overlay.update(dt)
                overlay.draw(screen)
            else:
                for k in sorted(kois, key=lambda f: f.depth, reverse=True):
                    k.update(dt, kois)
                    k.draw(screen, atlas)

                ripple_timer += dt
                if ripple_timer > 1.1:
                    ripple_timer = 0.0
                    candidates = [k for k in kois if k.depth < 0.55] or kois
                    chosen = random.choice(candidates)
                    ripples.append(
                        Ripple(
                            chosen.x,
                            chosen.y,
                            max_r=80,
                            strength=0.45 + (1.0 - chosen.depth) * 0.3,
                        )
                    )

            surface_ripple_timer += dt
            if surface_ripple_timer > 3.2:
                surface_ripple_timer = random.uniform(0.0, 0.5)
                ripples.append(
                    Ripple(
                        random.uniform(80, W - 80),
                        random.uniform(80, H - 80),
                        max_r=random.uniform(45, 85),
                        strength=0.3,
                    )
                )

            for r in ripples[:]:
                r.update(dt)
                r.draw(screen)
                if r.alpha <= 2:
                    ripples.remove(r)

            draw_botanicals(screen, sim_time)
            pygame.display.flip()
    finally:
        if overlay is not None:
            overlay.close()
        pygame.quit()


if __name__ == "__main__":
    main()
