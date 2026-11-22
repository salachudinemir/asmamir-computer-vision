"""
Standalone pygame pixel koi pond.

Dark-navy aquarium with nearest-neighbor pixel koi (Kohaku / Asagi / Yamabuki
and kin), soft slow swim, lily pads, and pink lotus. Interactive: click/tap
calls fish, Space scatters, ripples on the surface.

Look & swim ideas inspired by git-koi-aquarium
(https://github.com/reginaldalfret/git-koi-aquarium, MIT) — stroke/glide beats,
variety coats, fish under botanicals, calm spacing — rewritten as original
pygame code (not a port or wholesale copy).

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

# Pixel atlas: paint at low res, scale with nearest-neighbor.
PIXEL_SCALE = 4
PIXEL_BODY_W = 40
PIXEL_BODY_H = 18
SWIM_FRAMES = 6
HEADING_SLEW = 1.55
HEADING_SLEW_FAST = 3.2
FACE_FLIP_COS = 0.42
FACE_FLIP_SIN_MAX = 0.55
FACE_FLIP_CD = 0.7
SEPARATION_RADIUS = 92.0
SEPARATION_GAIN = 48.0

# Palette inspired by classic Japanese morphs (original RGB choices).
PALETTES: dict[str, dict[str, tuple[int, int, int]]] = {
    "kohaku": {
        "ground": (244, 246, 250),
        "edge": (170, 180, 198),
        "mark": (228, 58, 52),
        "mark2": (242, 110, 48),
        "fin": (236, 240, 248),
        "eye": (18, 20, 28),
    },
    "asagi": {
        "ground": (78, 108, 148),
        "edge": (42, 58, 92),
        "mark": (248, 120, 52),
        "mark2": (220, 78, 48),
        "fin": (236, 132, 72),
        "eye": (16, 18, 26),
    },
    "yamabuki": {
        "ground": (252, 196, 64),
        "edge": (196, 118, 36),
        "mark": (255, 232, 120),
        "mark2": (255, 248, 200),
        "fin": (254, 210, 90),
        "eye": (28, 22, 18),
    },
    "ogon": {
        "ground": (220, 230, 240),
        "edge": (140, 156, 178),
        "mark": (250, 252, 255),
        "mark2": (190, 205, 220),
        "fin": (236, 242, 250),
        "eye": (22, 24, 32),
    },
    "karasu": {
        "ground": (32, 34, 48),
        "edge": (18, 20, 30),
        "mark": (58, 64, 88),
        "mark2": (90, 98, 120),
        "fin": (48, 52, 70),
        "eye": (200, 190, 170),
    },
    "chagoi": {
        "ground": (168, 108, 72),
        "edge": (96, 58, 42),
        "mark": (210, 150, 96),
        "mark2": (120, 72, 48),
        "fin": (184, 120, 80),
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


def _body_half_width(t: float) -> float:
    if t < 0.12:
        return 0.22 + 0.55 * (t / 0.12)
    if t < 0.55:
        return 0.78 + 0.22 * math.sin(((t - 0.12) / 0.43) * math.pi)
    u = (t - 0.55) / 0.45
    return max(0.12, 0.78 * (1.0 - u) ** 0.85)


def _paint_pixel_koi(variety: str, frame: int, seed: int) -> pygame.Surface:
    """Paint one low-res koi frame facing +X; nearest-neighbor scale up."""
    pal = PALETTES.get(variety, PALETTES["kohaku"])
    bw, bh = PIXEL_BODY_W, PIXEL_BODY_H
    raw = pygame.Surface((bw, bh), pygame.SRCALPHA)
    rng = random.Random(seed * 7919 + frame * 17)
    cy = bh // 2
    wag = math.sin((frame / max(1, SWIM_FRAMES - 1)) * math.pi * 2.0) * 1.15
    fin_flare = 0.55 + 0.45 * abs(math.sin((frame / max(1, SWIM_FRAMES - 1)) * math.pi))

    # Tail fork
    for k in range(7):
        u = k / 6.0
        spread = (u - 0.5) * 10.0 * fin_flare
        tx = int(2 + u * 5)
        ty = int(cy + spread + wag * (0.4 + u))
        col = pal["fin"] if k % 2 == 0 else pal["edge"]
        if 0 <= tx < bw and 0 <= ty < bh:
            raw.set_at((tx, ty), (*col, 230))
            if 0 <= ty + 1 < bh:
                raw.set_at((tx, ty + 1), (*pal["fin"], 160))

    # Body + markings
    for x in range(6, bw - 2):
        t = (x - 6) / float(bw - 8)
        half = _body_half_width(t) * (bh * 0.42)
        y_off = wag * (t ** 1.4) * 1.6
        y0 = int(cy - half + y_off)
        y1 = int(cy + half + y_off)
        for y in range(max(0, y0), min(bh, y1 + 1)):
            lat = (y - (cy + y_off)) / max(0.5, half)
            if abs(lat) > 0.78:
                c = pal["edge"]
            else:
                c = pal["ground"]
                if variety == "kohaku":
                    if 0.08 < t < 0.78 and abs(lat - ((seed % 5) - 2) * 0.08) < 0.55:
                        plate = math.sin(t * 9.0 + seed) * 0.35 + math.sin(lat * 5.0)
                        if plate > 0.15 and (hash((seed, int(t * 12), int(lat * 8))) % 7) != 0:
                            c = pal["mark"] if plate > 0.45 else pal["mark2"]
                elif variety == "asagi":
                    if abs(lat) < 0.55 and t > 0.1:
                        if (int(t * 18) + int((lat + 1) * 9)) % 3 == 0:
                            c = pal["edge"]
                        else:
                            c = pal["ground"]
                    if lat > 0.55:
                        c = pal["mark"]
                elif variety == "yamabuki":
                    if abs(lat) < 0.35 and 0.2 < t < 0.55:
                        c = pal["mark"]
                elif variety == "ogon":
                    if abs(lat) < 0.25 and 0.25 < t < 0.45:
                        c = pal["mark"]
                elif variety == "karasu":
                    if (int(t * 14) ^ int(abs(lat) * 10)) & 1:
                        c = pal["mark"]
                elif variety == "chagoi":
                    if abs(lat) < 0.4 and rng.random() < 0.35:
                        c = pal["mark"]
            if lat < -0.15 and abs(lat) < 0.55 and t < 0.85:
                c = tuple(min(255, int(ch + 18)) for ch in c)
            raw.set_at((x, y), (*c, 255))

    # Pectoral fins
    px = int(6 + 0.28 * (bw - 8))
    for side in (-1, 1):
        for i in range(5):
            fx = px + i // 2
            fy = int(cy + side * (3 + i * 0.9 * fin_flare) + wag * 0.3)
            if 0 <= fx < bw and 0 <= fy < bh:
                raw.set_at((fx, fy), (*pal["fin"], 210))

    # Eye
    ex = int(6 + 0.88 * (bw - 8))
    ey = cy - 2
    if 0 <= ex < bw and 0 <= ey < bh:
        raw.set_at((ex, ey), (*pal["eye"], 255))
        if ey + 1 < bh:
            raw.set_at((ex, ey + 1), (255, 255, 255, 200))

    # Barbel hint
    for i in range(3):
        wx = ex + 1 + i // 2
        wy = ey + 1 + i
        if 0 <= wx < bw and 0 <= wy < bh:
            raw.set_at((wx, wy), (*pal["edge"], 180))

    scaled = pygame.transform.scale(raw, (bw * PIXEL_SCALE, bh * PIXEL_SCALE))
    # convert_alpha needs a display mode; skip until main() creates one.
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
            self.turn_vel += random.uniform(-0.55, 0.55) * dt
            self.turn_vel *= 0.96
        elif self.state == SwimState.GLIDE:
            target_speed = self.base_speed * (0.38 + 0.2 * beat)
            self.turn_vel *= 0.9
        elif self.state == SwimState.REST:
            target_speed = self.base_speed * 0.1
            self.turn_vel += math.sin(self.phase * 0.9) * 0.35 * dt
            self.turn_vel *= 0.92
        elif self.state == SwimState.DART:
            target_speed = self.base_speed * (1.55 + 0.9 * beat)
            self.turn_vel *= 0.97
        else:
            target_speed = self.base_speed * (0.22 + 0.35 * beat)
            self.turn_vel *= 0.94

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
    circuits = [
        SoftCircuit(W * 0.5, H * 0.48, 380, 220, 0.00),
        SoftCircuit(W * 0.32, H * 0.32, 160, 70, 0.50),
        SoftCircuit(W * 0.68, H * 0.34, 160, 70, 0.50),
        SoftCircuit(W * 0.50, H * 0.52, 220, 70, 0.00),
        SoftCircuit(W * 0.30, H * 0.68, 150, 55, 0.50),
        SoftCircuit(W * 0.70, H * 0.68, 150, 55, 0.00),
        SoftCircuit(W * 0.48, H * 0.38, 280, 140, 0.25),
        SoftCircuit(W * 0.42, H * 0.60, 200, 90, 0.70),
        SoftCircuit(W * 0.58, H * 0.58, 190, 85, 0.15),
    ]
    # Speeds kept deliberately low for a calm pixel-pond glide.
    specs = [
        (circuits[0], "kohaku", 24, 1.05, 0.05),
        (circuits[0], "yamabuki", 22, 1.00, 0.55),
        (circuits[0], "asagi", 21, 0.96, 0.30),
        (circuits[1], "asagi", 20, 0.95, 0.10),
        (circuits[1], "kohaku", 19, 0.88, 0.65),
        (circuits[2], "kohaku", 20, 0.92, 0.20),
        (circuits[2], "yamabuki", 18, 0.86, 0.72),
        (circuits[3], "asagi", 19, 0.90, 0.40),
        (circuits[3], "karasu", 18, 0.85, 0.75),
        (circuits[4], "ogon", 20, 0.88, 0.15),
        (circuits[4], "chagoi", 17, 0.82, 0.80),
        (circuits[5], "chagoi", 19, 0.90, 0.60),
        (circuits[5], "ogon", 18, 0.84, 0.35),
        (circuits[6], "kohaku", 21, 0.98, 0.45),
        (circuits[6], "karasu", 17, 0.80, 0.88),
        (circuits[7], "yamabuki", 18, 0.87, 0.22),
        (circuits[8], "asagi", 19, 0.89, 0.58),
        (circuits[8], "chagoi", 16, 0.78, 0.05),
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
