"""
Standalone pygame koi pond.

Default: interactive RealisticKoi (click-call, Space scatter, ripples, swim states,
depth) drawn with keyed fish sprites extracted from the local overlay MP4 when present.
Procedural vector draw is the fallback if the asset or OpenCV is missing, or when
sprites are toggled off (`--procedural` / `P`).

Optional full-pond MP4 overlay (`--overlay` or `O`) still hides interactive fish while
active. Smooth 60 FPS with SCALED + vsync when available.

Run:
    python animation/koi_fish.py
    python animation/koi_fish.py --fullscreen
    python animation/koi_fish.py --procedural
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

# Center the window on the laptop display.
os.environ["SDL_VIDEO_CENTERED"] = "1"

pygame.init()
W, H = 1150, 720
# Display is created in main() so --fullscreen / F11 can recreate it with SCALED+vsync.
screen: pygame.Surface | None = None
clock = pygame.time.Clock()
HINT_FONT = pygame.font.SysFont("segoeui", 16)
HINT_FADE_S = 12.0

_ASSETS_DIR = Path(__file__).resolve().parent / "assets"
DEFAULT_OVERLAY_MP4 = _ASSETS_DIR / "koi_fish_swimming_animated_overlay.mp4"
# Full opacity when optional overlay mode is active (procedural fish hidden).
OVERLAY_OPACITY = 1.0
# Soft cap for the keyed Surface cache (~474 MiB for 150 frames @ 1150x720 RGBA).
OVERLAY_CACHE_MAX_MB = 700.0
# Sprite bank: fish crops from the same MP4 (default look for RealisticKoi).
SPRITE_MAX_COUNT = 28
SPRITE_FRAME_STRIDE = 8
SPRITE_MIN_AREA = 28_000
SPRITE_MAX_AREA = 185_000
SPRITE_TARGET_LENGTH = 220.0  # normalize crops before per-fish scaling
# After canonicalize, every surface faces +X (nose right). Draw uses flip L/R + pitch.
SPRITE_CANON_HEADING = 0.0  # radians; nose along +X
SPRITE_CYCLE_LEN = 4  # light swim-pose cycle per fish (stable base + nearby frames)
SPRITE_CYCLE_RATE = 0.22  # phase → cycle index (slow; avoids tumble)


def _try_import_cv2():
    try:
        import cv2  # type: ignore

        return cv2
    except ImportError:
        return None


def _create_display(fullscreen: bool) -> pygame.Surface:
    """Logical (W, H) buffer; SDL SCALED letterboxes/covers the real desktop."""
    flags = pygame.SCALED | pygame.DOUBLEBUF
    if fullscreen:
        flags |= pygame.FULLSCREEN
    try:
        surf = pygame.display.set_mode((W, H), flags, vsync=1)
    except TypeError:
        surf = pygame.display.set_mode((W, H), flags)
    pygame.display.set_caption("Realistic Living Koi Pond")
    return surf


def _key_checkerboard_bgr(frame_bgr, chroma_max: float = 18.0, gray_lo: float = 15.0, gray_hi: float = 95.0):
    """Build a soft alpha mask that removes a dark gray/black checkerboard plate.

    The overlay MP4 has no real alpha channel; transparency is encoded as a
    checkerboard (near-achromatic mid-dark grays). Colored / bright fish pixels
    and soft shadows outside that band are kept.
    """
    import numpy as np

    b = frame_bgr[:, :, 0].astype(np.float32)
    g = frame_bgr[:, :, 1].astype(np.float32)
    r = frame_bgr[:, :, 2].astype(np.float32)
    mx = np.maximum(np.maximum(r, g), b)
    mn = np.minimum(np.minimum(r, g), b)
    chroma = mx - mn
    gray = (r + g + b) * (1.0 / 3.0)
    hard = (chroma < chroma_max) & (gray > gray_lo) & (gray < gray_hi)
    hard_u8 = (hard.astype(np.uint8) * 255)
    cv2 = _try_import_cv2()
    if cv2 is not None:
        hard_u8 = cv2.dilate(hard_u8, np.ones((3, 3), np.uint8), iterations=1)
        alpha = 255 - hard_u8
        alpha = cv2.GaussianBlur(alpha, (5, 5), 0)
    else:
        alpha = np.where(hard, np.uint8(0), np.uint8(255))
    return alpha


class KoiSpriteBank:
    """Keyed fish crops from the overlay MP4 for blitting onto RealisticKoi.

    Every stored surface is canonicalized so the nose faces +X (right). Draw-time
    code then flips for left swim and applies a small pitch rotation — no full
    360 tumble from mismatched per-crop headings.
    """

    def __init__(
        self,
        path: Path,
        max_sprites: int = SPRITE_MAX_COUNT,
        frame_stride: int = SPRITE_FRAME_STRIDE,
    ):
        self.path = Path(path)
        # (surface facing +X, body_length_px)
        self._sprites: list[tuple[pygame.Surface, float]] = []
        self._ok = False
        self._open(max_sprites=max_sprites, frame_stride=frame_stride)

    @property
    def available(self) -> bool:
        return self._ok and bool(self._sprites)

    def __len__(self) -> int:
        return len(self._sprites)

    def close(self) -> None:
        self._sprites.clear()
        self._ok = False

    def pick(self, fish_index: int, phase: float) -> tuple[pygame.Surface, float] | None:
        """Return (surface facing +X, body_length_px) with a stable per-fish cycle."""
        if not self.available:
            return None
        n = len(self._sprites)
        cycle_len = min(SPRITE_CYCLE_LEN, n)
        # Stable base per fish; light nearby-frame cycle for swim pose (not bank scramble).
        base = (fish_index * cycle_len) % n
        step = int(phase * SPRITE_CYCLE_RATE) % cycle_len
        idx = (base + step) % n
        return self._sprites[idx]

    def _open(self, max_sprites: int, frame_stride: int) -> None:
        if not self.path.is_file():
            return
        cv2 = _try_import_cv2()
        if cv2 is None:
            print(f"[koi] OpenCV unavailable; sprite bank skipped ({self.path.name}).", file=sys.stderr)
            return
        import numpy as np

        print(f"[koi] Extracting fish sprites from {self.path.name}…", file=sys.stderr)
        cap = cv2.VideoCapture(str(self.path))
        if not cap.isOpened():
            print(f"[koi] Could not open sprite source: {self.path}", file=sys.stderr)
            return

        sprites: list[tuple[pygame.Surface, float]] = []
        frame_i = 0
        while len(sprites) < max_sprites:
            ok, frame = cap.read()
            if not ok or frame is None:
                break
            if frame_i % max(1, frame_stride) != 0:
                frame_i += 1
                continue
            frame_i += 1
            alpha = _key_checkerboard_bgr(frame)
            binm = (alpha > 128).astype(np.uint8)
            binm = cv2.morphologyEx(binm, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8), iterations=1)
            num, labels, stats, _centroids = cv2.connectedComponentsWithStats(binm, 8)
            # Largest fish first so we keep the best crops when capping.
            order = sorted(
                range(1, num),
                key=lambda i: int(stats[i, cv2.CC_STAT_AREA]),
                reverse=True,
            )
            for i in order:
                if len(sprites) >= max_sprites:
                    break
                area = int(stats[i, cv2.CC_STAT_AREA])
                bw = int(stats[i, cv2.CC_STAT_WIDTH])
                bh = int(stats[i, cv2.CC_STAT_HEIGHT])
                if area < SPRITE_MIN_AREA or area > SPRITE_MAX_AREA:
                    continue
                if max(bw, bh) < 140:
                    continue
                aspect = max(bw, bh) / max(1, min(bw, bh))
                # Merged two-fish blobs are near-square and huge — skip.
                if aspect < 1.18 and area > 150_000:
                    continue
                cropped = self._crop_component(frame, alpha, labels, stats, i, cv2, np)
                if cropped is None:
                    continue
                rgba, heading, _length = cropped
                surf = self._rgba_to_surface(rgba, target_length=SPRITE_TARGET_LENGTH)
                if surf is None:
                    continue
                canon = self._canonicalize_facing(surf, heading)
                if canon is None:
                    continue
                # Length after normalize ≈ SPRITE_TARGET_LENGTH; nose faces +X.
                sprites.append((canon, float(SPRITE_TARGET_LENGTH)))

        cap.release()
        if not sprites:
            print(f"[koi] No fish sprites extracted from {self.path.name}.", file=sys.stderr)
            return
        self._sprites = sprites
        self._ok = True
        print(
            f"[koi] Sprite bank ready: {len(sprites)} keyed crops "
            f"(canonical +X facing, cycle {min(SPRITE_CYCLE_LEN, len(sprites))}).",
            file=sys.stderr,
        )

    @staticmethod
    def _canonicalize_facing(surf: pygame.Surface, heading: float) -> pygame.Surface | None:
        """Rotate so the nose points along +X (SPRITE_CANON_HEADING)."""
        # pygame.rotozoom: positive degrees = CCW. Image coords share atan2 (Y down).
        rot_deg = -math.degrees(heading - SPRITE_CANON_HEADING)
        try:
            out = pygame.transform.rotozoom(surf, rot_deg, 1.0)
        except pygame.error:
            return None
        return out.convert_alpha()

    @staticmethod
    def _crop_component(frame_bgr, alpha, labels, stats, comp_i, cv2, np):
        x = int(stats[comp_i, cv2.CC_STAT_LEFT])
        y = int(stats[comp_i, cv2.CC_STAT_TOP])
        w = int(stats[comp_i, cv2.CC_STAT_WIDTH])
        h = int(stats[comp_i, cv2.CC_STAT_HEIGHT])
        pad = 10
        x0 = max(0, x - pad)
        y0 = max(0, y - pad)
        x1 = min(frame_bgr.shape[1], x + w + pad)
        y1 = min(frame_bgr.shape[0], y + h + pad)
        rgb = cv2.cvtColor(frame_bgr[y0:y1, x0:x1], cv2.COLOR_BGR2RGB)
        a = alpha[y0:y1, x0:x1].copy()
        lab = labels[y0:y1, x0:x1]
        a = np.where(lab == comp_i, a, 0).astype(np.uint8)
        ys, xs = np.where(a > 128)
        if len(xs) < 80:
            return None
        pts = np.column_stack((xs.astype(np.float64), ys.astype(np.float64)))
        mean = pts.mean(axis=0)
        centered = pts - mean
        cov = np.cov(centered, rowvar=False)
        if not np.isfinite(cov).all():
            return None
        eigvals, eigvecs = np.linalg.eigh(cov)
        axis = eigvecs[:, int(np.argmax(eigvals))]
        proj = centered @ axis
        lo = proj < np.percentile(proj, 12)
        hi = proj > np.percentile(proj, 88)
        # Head cue: brighter tip (orange/white) and/or narrower cross-section.
        bright = rgb.astype(np.float32).mean(axis=2)
        lo_b = float(bright[ys[lo], xs[lo]].mean()) if lo.any() else 0.0
        hi_b = float(bright[ys[hi], xs[hi]].mean()) if hi.any() else 0.0
        # Cross-section width near each tip (perpendicular spread).
        perp = np.array([-axis[1], axis[0]], dtype=np.float64)
        lat = centered @ perp
        lo_w = float(np.std(lat[lo])) if lo.any() else 1.0
        hi_w = float(np.std(lat[hi])) if hi.any() else 1.0
        heading = math.atan2(float(axis[1]), float(axis[0]))
        # Score: prefer bright + tapered tip as head.
        hi_score = hi_b / 255.0 - 0.35 * (hi_w / max(lo_w, hi_w, 1e-3))
        lo_score = lo_b / 255.0 - 0.35 * (lo_w / max(lo_w, hi_w, 1e-3))
        if hi_score < lo_score:
            heading += math.pi
        length = float(np.percentile(proj, 95) - np.percentile(proj, 5))
        length = max(length, float(max(w, h)) * 0.55)
        rgba = np.dstack((rgb, a))
        return rgba, heading, length

    @staticmethod
    def _rgba_to_surface(rgba, target_length: float) -> pygame.Surface | None:
        import numpy as np

        h, w = rgba.shape[:2]
        if w < 8 or h < 8:
            return None
        # Scale so the long side ≈ target_length (keeps rotozoom cheap).
        long_side = max(w, h)
        scale = target_length / float(long_side)
        if abs(scale - 1.0) > 0.02:
            nw = max(8, int(round(w * scale)))
            nh = max(8, int(round(h * scale)))
            cv2 = _try_import_cv2()
            if cv2 is not None:
                rgba = cv2.resize(rgba, (nw, nh), interpolation=cv2.INTER_AREA)
            else:
                tmp = pygame.image.frombuffer(
                    np.ascontiguousarray(rgba).tobytes(), (w, h), "RGBA"
                )
                return pygame.transform.smoothscale(tmp.copy(), (nw, nh)).convert_alpha()
        h, w = rgba.shape[:2]
        buf = np.ascontiguousarray(rgba)
        surf = pygame.image.frombuffer(buf.tobytes(), (w, h), "RGBA").convert_alpha()
        return surf.copy()


class KoiOverlayVideo:
    """Loop a pre-keyed MP4 overlay; OpenCV work happens only at load time."""

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
        self._frame_count = 0
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
            print(f"[koi] OpenCV unavailable; skipping overlay {self.path.name}", file=sys.stderr)
            return
        cap = self._cv2.VideoCapture(str(self.path))
        if not cap.isOpened():
            print(f"[koi] Could not open overlay video: {self.path}", file=sys.stderr)
            return
        fps = float(cap.get(self._cv2.CAP_PROP_FPS) or 0.0)
        self._fps = fps if fps > 1.0 else 30.0
        reported = int(cap.get(self._cv2.CAP_PROP_FRAME_COUNT) or 0)
        tw, th = self.size
        # Estimate RAM; if over budget, cache every Nth frame (still clock-synced).
        bytes_per = tw * th * 4
        est_all_mb = (max(reported, 1) * bytes_per) / (1024.0 * 1024.0)
        stride = 1
        if est_all_mb > self._max_cache_mb and reported > 0:
            stride = max(1, int(math.ceil(est_all_mb / self._max_cache_mb)))
            print(
                f"[koi] Overlay cache budget {self._max_cache_mb:.0f} MiB; "
                f"keeping every {stride} frame(s) (~{est_all_mb / stride:.0f} MiB).",
                file=sys.stderr,
            )

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
            print(f"[koi] Overlay decode produced no frames: {self.path}", file=sys.stderr)
            return

        self._frames = frames
        self._frame_count = len(frames)
        # Stride slows presentation FPS so wall-clock loop duration matches the source.
        if stride > 1:
            self._fps = max(1.0, self._fps / stride)
        self._ok = True
        cache_mb = (self._frame_count * bytes_per) / (1024.0 * 1024.0)
        print(
            f"[koi] Overlay cached: {self.path.name} "
            f"({self._frame_count} keyed surfaces @ {self._fps:.1f} fps, ~{cache_mb:.0f} MiB)"
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
        alpha = _key_checkerboard_bgr(frame_bgr)
        if self.opacity < 1.0:
            alpha = (alpha.astype(np.float32) * self.opacity).astype(np.uint8)
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        rgba = np.dstack((rgb, alpha))
        surf = pygame.image.frombuffer(rgba.tobytes(), (tw, th), "RGBA").convert_alpha()
        # frombuffer aliases the buffer; copy so the next decode cannot mutate the blit.
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
    GLIDE = auto()
    COAST = auto()
    HOVER = auto()
    BURST = auto()
    PIVOT = auto()


def create_pond_bed():
    """Natural pond bed: depth gradient plus soft river stones."""
    bed = pygame.Surface((W, H))
    cx, cy = W // 2, H // 2
    max_d = math.hypot(cx, cy)

    for y in range(0, H, 2):
        for x in range(0, W, 2):
            d = math.hypot(x - cx, y - cy) / max_d
            r = int(max(5, 16 * (1 - d * 0.75)))
            g = int(max(18, 54 * (1 - d * 0.65)))
            b = int(max(24, 68 * (1 - d * 0.55)))
            pygame.draw.rect(bed, (r, g, b), (x, y, 2, 2))

    rng = random.Random(42)
    stone_surf = pygame.Surface((W, H), pygame.SRCALPHA)
    for _ in range(55):
        sx = rng.randint(40, W - 40)
        sy = rng.randint(40, H - 40)
        rx = rng.randint(18, 48)
        ry = int(rx * rng.uniform(0.65, 0.9))
        ang = rng.uniform(0, 180)
        shade = rng.randint(18, 38)

        s_tmp = pygame.Surface((rx * 2 + 10, ry * 2 + 10), pygame.SRCALPHA)
        pygame.draw.ellipse(s_tmp, (shade, shade + 12, shade + 16, 65), (5, 5, rx * 2, ry * 2))
        pygame.draw.ellipse(
            s_tmp, (shade + 10, shade + 22, shade + 25, 45), (7, 6, int(rx * 1.6), int(ry * 1.5))
        )
        rot_s = pygame.transform.rotate(s_tmp, ang)
        stone_surf.blit(rot_s, rot_s.get_rect(center=(sx, sy)))

    bed.blit(stone_surf, (0, 0))
    return bed


def _tint_alpha(color, alpha):
    """Apply a 0..1 opacity factor to an RGB or RGBA color."""
    a = max(0, min(255, int(round(alpha * (color[3] if len(color) > 3 else 255)))))
    return (color[0], color[1], color[2], a)


class RealisticKoi:
    def __init__(self, x, y, angle, base_speed, scale, variety, sprite_index: int = 0):
        self.x = x
        self.y = y
        self.angle = angle
        self.base_speed = base_speed
        self.speed = base_speed
        self.base_scale = scale
        self.scale = scale
        self.variety = variety
        self.sprite_index = sprite_index

        self.phase = random.uniform(0, 6.28)
        self.turn_vel = 0.0

        # Depth: 0 = near surface (larger, clearer), 1 = deep (smaller, dimmer).
        self.depth = random.uniform(0.25, 0.75)
        self.depth_vel = 0.0

        self.state = SwimState.GLIDE
        self.state_timer = random.uniform(1.5, 3.5)
        self.call_timer = 0.0
        self.call_target = None
        self.scatter_timer = 0.0
        self.scatter_heading = angle
        # Sprite L/R facing with hysteresis (avoids flicker when swimming vertical).
        self._face_left = math.cos(angle) < 0.0

        # Follow-the-leader spine (32 joints).
        self.num_joints = 32
        self.joint_dist = 4.6 * scale
        self.joints = [
            [x - math.cos(angle) * i * self.joint_dist, y - math.sin(angle) * i * self.joint_dist]
            for i in range(self.num_joints)
        ]

        self.spots = self._generate_organic_spots()

    def _generate_organic_spots(self):
        rng = random.Random(hash((self.variety, round(self.base_scale, 2), round(self.phase, 2))))
        spots = []
        if self.variety in ("kohaku", "sanke", "showa"):
            for _ in range(rng.randint(3, 5)):
                spots.append(
                    {
                        "t_center": rng.uniform(0.08, 0.78),
                        "t_radius": rng.uniform(0.08, 0.16),
                        "side_offset": rng.uniform(-0.35, 0.35),
                        "color": (228, 62, 22) if rng.random() > 0.3 else (242, 85, 28),
                    }
                )
        if self.variety in ("sanke", "showa"):
            for _ in range(rng.randint(3, 6)):
                spots.append(
                    {
                        "t_center": rng.uniform(0.15, 0.82),
                        "t_radius": rng.uniform(0.04, 0.09),
                        "side_offset": rng.uniform(-0.45, 0.45),
                        "color": (24, 26, 32),
                    }
                )
        return spots

    def attract_to(self, tx, ty):
        """Swim toward a click / tap (feeding call)."""
        self.call_target = (tx, ty)
        self.call_timer = random.uniform(2.4, 3.6)
        self.scatter_timer = 0.0
        desired = math.atan2(ty - self.y, tx - self.x)
        diff = (desired - self.angle + math.pi) % (2 * math.pi) - math.pi
        self.turn_vel = max(-2.0, min(2.0, diff * 2.8))
        dist = math.hypot(tx - self.x, ty - self.y)
        if dist > 220:
            self._enter(SwimState.BURST, random.uniform(0.55, 0.95))
        elif abs(diff) > 1.1:
            self._enter(SwimState.PIVOT, random.uniform(0.35, 0.7))
        else:
            self._enter(SwimState.GLIDE, random.uniform(1.2, 2.0))
        # Drift slightly toward the surface when called.
        self.depth_vel -= 0.35

    def scatter(self):
        """Dash away from the current heading cluster (Space)."""
        self.call_timer = 0.0
        self.call_target = None
        self.scatter_heading = self.angle + random.uniform(-2.4, 2.4)
        self.scatter_timer = random.uniform(1.1, 1.8)
        self._enter(SwimState.BURST, random.uniform(0.7, 1.2))
        self.depth_vel += random.uniform(0.15, 0.45)

    def _enter(self, state, duration):
        self.state = state
        self.state_timer = duration

    def _pick_idle_state(self):
        roll = random.random()
        if roll < 0.38:
            self._enter(SwimState.GLIDE, random.uniform(2.0, 4.5))
        elif roll < 0.62:
            self._enter(SwimState.COAST, random.uniform(1.2, 2.8))
        elif roll < 0.78:
            self._enter(SwimState.HOVER, random.uniform(0.9, 2.2))
        elif roll < 0.92:
            self._enter(SwimState.BURST, random.uniform(0.45, 0.9))
        else:
            self._enter(SwimState.PIVOT, random.uniform(0.4, 0.85))

    def _smooth_spine(self):
        """Light Laplacian pass so the body curve stays soft without losing IK length."""
        if self.num_joints < 3:
            return
        smoothed = [self.joints[0][:]]
        for i in range(1, self.num_joints - 1):
            px, py = self.joints[i - 1]
            cx, cy = self.joints[i]
            nx, ny = self.joints[i + 1]
            sx = cx * 0.62 + (px + nx) * 0.19
            sy = cy * 0.62 + (py + ny) * 0.19
            smoothed.append([sx, sy])
        smoothed.append(self.joints[-1][:])

        self.joints[0] = smoothed[0]
        for i in range(1, self.num_joints):
            px, py = self.joints[i - 1]
            cx, cy = smoothed[i]
            ang = math.atan2(py - cy, px - cx)
            self.joints[i][0] = px - math.cos(ang) * self.joint_dist
            self.joints[i][1] = py - math.sin(ang) * self.joint_dist

    def update(self, dt):
        self.state_timer -= dt
        if self.call_timer > 0:
            self.call_timer -= dt
        if self.scatter_timer > 0:
            self.scatter_timer -= dt

        # Gentle depth wander (and call / scatter bias).
        self.depth_vel += random.uniform(-0.25, 0.25) * dt
        self.depth_vel *= 0.92
        self.depth = max(0.05, min(0.95, self.depth + self.depth_vel * dt))
        # Visual scale from depth: near surface larger, deep smaller.
        depth_scale = 1.18 - self.depth * 0.42
        self.scale = self.base_scale * depth_scale
        self.joint_dist = 4.6 * self.scale

        # Call / scatter steering overrides idle wander.
        if self.scatter_timer > 0:
            diff = (self.scatter_heading - self.angle + math.pi) % (2 * math.pi) - math.pi
            self.turn_vel = max(-2.2, min(2.2, diff * 3.0))
            if self.state != SwimState.BURST:
                self._enter(SwimState.BURST, max(self.state_timer, 0.4))
        elif self.call_timer > 0 and self.call_target is not None:
            tx, ty = self.call_target
            desired = math.atan2(ty - self.y, tx - self.x)
            diff = (desired - self.angle + math.pi) % (2 * math.pi) - math.pi
            dist = math.hypot(tx - self.x, ty - self.y)
            self.turn_vel = max(-2.0, min(2.0, diff * 2.6))
            if dist < 55:
                if self.state != SwimState.HOVER:
                    self._enter(SwimState.HOVER, random.uniform(0.6, 1.4))
            elif abs(diff) > 1.25 and self.state not in (SwimState.PIVOT, SwimState.BURST):
                self._enter(SwimState.PIVOT, random.uniform(0.3, 0.6))

        if self.state_timer <= 0 and self.call_timer <= 0 and self.scatter_timer <= 0:
            self._pick_idle_state()

        # State → speed / turn character.
        if self.state == SwimState.GLIDE:
            target_speed = self.base_speed * (1.0 + 0.08 * math.sin(self.phase * 0.35))
            self.turn_vel += random.uniform(-1.1, 1.1) * dt
            self.turn_vel *= 0.94
        elif self.state == SwimState.COAST:
            target_speed = self.base_speed * 0.42
            self.turn_vel *= 0.88
            self.turn_vel += random.uniform(-0.5, 0.5) * dt
        elif self.state == SwimState.HOVER:
            target_speed = self.base_speed * 0.12
            self.turn_vel += math.sin(self.phase * 1.6) * 0.9 * dt
            self.turn_vel *= 0.9
        elif self.state == SwimState.BURST:
            target_speed = self.base_speed * 2.15
            self.turn_vel *= 0.96
        else:  # PIVOT
            target_speed = self.base_speed * 0.28
            self.turn_vel += random.choice((-1, 1)) * 3.4 * dt
            self.turn_vel = max(-2.8, min(2.8, self.turn_vel))

        self.speed += (target_speed - self.speed) * min(1.0, 3.2 * dt)

        # Soft wall avoidance.
        margin = 160
        steer_x, steer_y = 0.0, 0.0
        if self.x < margin:
            steer_x += (margin - self.x) / margin
        elif self.x > W - margin:
            steer_x -= (self.x - (W - margin)) / margin
        if self.y < margin:
            steer_y += (margin - self.y) / margin
        elif self.y > H - margin:
            steer_y -= (self.y - (H - margin)) / margin

        if steer_x != 0.0 or steer_y != 0.0:
            wall_ang = math.atan2(steer_y, steer_x)
            diff = (wall_ang - self.angle + math.pi) % (2 * math.pi) - math.pi
            self.angle += diff * 2.2 * dt
        else:
            self.angle += self.turn_vel * dt

        self.x += math.cos(self.angle) * self.speed * dt
        self.y += math.sin(self.angle) * self.speed * dt
        wave_rate = 1.4 if self.state == SwimState.HOVER else (self.speed * 0.075 + 2.2)
        if self.state == SwimState.BURST:
            wave_rate = self.speed * 0.09 + 3.4
        self.phase += wave_rate * dt

        # Inverse kinematics chain + swim wave, then a light smooth pass.
        self.joints[0] = [self.x, self.y]
        wave_amp = 0.14
        if self.state == SwimState.BURST:
            wave_amp = 0.2
        elif self.state == SwimState.HOVER:
            wave_amp = 0.08
        elif self.state == SwimState.COAST:
            wave_amp = 0.1

        for i in range(1, self.num_joints):
            t = i / (self.num_joints - 1)
            px, py = self.joints[i - 1]
            cx, cy = self.joints[i]
            ang = math.atan2(py - cy, px - cx)
            swim_wave = math.sin(self.phase - t * 5.2) * (wave_amp * (t ** 1.35))
            target_ang = ang + swim_wave
            self.joints[i][0] = px - math.cos(target_ang) * self.joint_dist
            self.joints[i][1] = py - math.sin(target_ang) * self.joint_dist

        self._smooth_spine()

    def _body_radius(self, t):
        """Body thickness profile from snout to tail root."""
        if t < 0.26:
            return (0.28 + 0.72 * math.sin((t / 0.26) * (math.pi / 2))) * 22.0 * self.scale
        u = (t - 0.26) / 0.74
        return (math.cos(u * (math.pi / 2)) ** 0.85) * 22.0 * self.scale

    def _opacity(self):
        # Deeper fish look softer / more submerged.
        return max(0.35, min(1.0, 1.05 - self.depth * 0.55))

    def draw(self, surf, sprites: KoiSpriteBank | None = None):
        """Blit MP4 sprite when bank available; else procedural vector body."""
        if sprites is not None and sprites.available:
            if self._draw_sprite(surf, sprites):
                return
        self._draw_procedural(surf)

    @staticmethod
    def _norm_pi(a: float) -> float:
        return (a + math.pi) % (2 * math.pi) - math.pi

    def _draw_sprite(self, surf: pygame.Surface, sprites: KoiSpriteBank) -> bool:
        picked = sprites.pick(self.sprite_index, self.phase)
        if picked is None:
            return False
        base, body_len = picked
        # Match procedural body length (~147 * scale) to the keyed crop.
        target_len = max(48.0, 147.0 * self.scale)
        zoom = target_len / max(1.0, body_len)

        # Bank surfaces are canonical nose-+X. Prefer stable facing:
        # flip horizontally when swimming left, then pitch about that axis
        # (avoids head/tail tumble from mismatched per-frame headings).
        c = math.cos(self.angle)
        if c < -0.15:
            self._face_left = True
        elif c > 0.15:
            self._face_left = False
        facing_left = self._face_left
        pose = pygame.transform.flip(base, True, False) if facing_left else base
        if facing_left:
            # Flip mirrors rotation sense; pitch relative to -X (π).
            pitch = self._norm_pi(self.angle - math.pi)
            rot_deg = math.degrees(pitch)
        else:
            pitch = self._norm_pi(self.angle)
            rot_deg = -math.degrees(pitch)
        try:
            img = pygame.transform.rotozoom(pose, rot_deg, zoom)
        except pygame.error:
            return False
        opacity = self._opacity()
        if opacity < 0.99:
            img = img.copy()
            img.set_alpha(max(40, min(255, int(255 * opacity))))

        # Soft elliptical shadow under the fish (depth cue).
        shadow_ox = 10 + (1.0 - self.depth) * 14
        shadow_oy = 12 + (1.0 - self.depth) * 16
        sw, sh = img.get_width(), img.get_height()
        shadow = pygame.Surface((sw, sh), pygame.SRCALPHA)
        pygame.draw.ellipse(
            shadow,
            (2, 10, 14, int(22 + (1.0 - self.depth) * 34)),
            shadow.get_rect().inflate(-int(sw * 0.18), -int(sh * 0.35)),
        )
        # Anchor near mid-body (slightly behind the head joint).
        mid_i = min(6, self.num_joints - 1)
        cx = self.joints[mid_i][0]
        cy = self.joints[mid_i][1]
        surf.blit(shadow, shadow.get_rect(center=(cx + shadow_ox, cy + shadow_oy)))
        surf.blit(img, img.get_rect(center=(cx, cy)))
        return True

    def _draw_procedural(self, surf):
        opacity = self._opacity()
        shadow_strength = int(28 + (1.0 - self.depth) * 36)
        shadow_ox = 14 + (1.0 - self.depth) * 18
        shadow_oy = 18 + (1.0 - self.depth) * 22

        angles = []
        for i in range(self.num_joints):
            if i == 0:
                ang = self.angle
            else:
                dx = self.joints[i - 1][0] - self.joints[i][0]
                dy = self.joints[i - 1][1] - self.joints[i][1]
                ang = math.atan2(dy, dx)
            angles.append(ang)

        xs = [p[0] for p in self.joints]
        ys = [p[1] for p in self.joints]
        pad = int(75 * self.scale + shadow_ox + 8)
        min_x = max(0, int(min(xs)) - pad)
        min_y = max(0, int(min(ys)) - pad)
        max_x = min(W, int(max(xs)) + pad + 35)
        max_y = min(H, int(max(ys)) + pad + 35)
        bw, bh = max_x - min_x, max_y - min_y
        if bw <= 0 or bh <= 0:
            return

        local_surf = pygame.Surface((bw, bh), pygame.SRCALPHA)

        def to_loc(px, py):
            return px - min_x, py - min_y

        # Soft bed shadow — stronger when closer to the surface.
        for i in range(self.num_joints):
            t = i / (self.num_joints - 1)
            r = int(self._body_radius(t) * 0.95)
            if r > 1:
                lx, ly = to_loc(self.joints[i][0] + shadow_ox, self.joints[i][1] + shadow_oy)
                pygame.draw.circle(local_surf, (2, 10, 14, shadow_strength), (int(lx), int(ly)), r)

        # Barbels
        hx, hy = to_loc(*self.joints[0])
        hang = angles[0]
        for side in (-1, 1):
            b_ang = hang + side * 0.55 + math.sin(self.phase) * 0.08
            bx1 = hx + math.cos(hang + side * 0.35) * 4 * self.scale
            by1 = hy + math.sin(hang + side * 0.35) * 4 * self.scale
            bx2 = bx1 + math.cos(b_ang) * 12 * self.scale
            by2 = by1 + math.sin(b_ang) * 12 * self.scale
            pygame.draw.line(
                local_surf,
                _tint_alpha((235, 225, 215, 190), opacity),
                (bx1, by1),
                (bx2, by2),
                max(1, int(1.6 * self.scale)),
            )

        # Pectoral fins
        px_base, py_base = to_loc(*self.joints[5])
        pang = angles[5]
        flap = math.sin(self.phase * 0.85) * 0.26
        for side in (-1, 1):
            f_ang = pang + side * (1.12 + flap)
            p1 = (px_base, py_base)
            p2 = (
                px_base + math.cos(f_ang - 0.28 * side) * 38 * self.scale,
                py_base + math.sin(f_ang - 0.28 * side) * 38 * self.scale,
            )
            p3 = (
                px_base + math.cos(f_ang + 0.12 * side) * 42 * self.scale,
                py_base + math.sin(f_ang + 0.12 * side) * 42 * self.scale,
            )
            p4 = (
                px_base + math.cos(f_ang + 0.42 * side) * 26 * self.scale,
                py_base + math.sin(f_ang + 0.42 * side) * 26 * self.scale,
            )
            pygame.draw.polygon(local_surf, _tint_alpha((245, 248, 252, 115), opacity), [p1, p2, p3, p4])
            for ray_pt in (p2, p3, p4):
                pygame.draw.line(local_surf, _tint_alpha((255, 255, 255, 145), opacity), p1, ray_pt, 1)

        # Caudal fin
        tx, ty = to_loc(*self.joints[-1])
        tang = angles[-1] + math.pi
        tail_poly = [(tx, ty)]
        num_rays = 11
        for k in range(num_rays):
            u = (k / (num_rays - 1)) * 2.0 - 1.0
            spread = u * 0.62
            fork = 1.0 - 0.18 * math.exp(-(u * 3.0) ** 2)
            length = (46.0 * fork * (1.0 - 0.18 * (u ** 2))) * self.scale
            wave_tail = math.sin(self.phase - 5.5 + u * 0.8) * 0.18
            ang = tang + spread + wave_tail
            tail_poly.append((tx + math.cos(ang) * length, ty + math.sin(ang) * length))

        pygame.draw.polygon(local_surf, _tint_alpha((248, 246, 242, 135), opacity), tail_poly)
        for pt in tail_poly[1::2]:
            pygame.draw.line(local_surf, _tint_alpha((255, 255, 255, 160), opacity), (tx, ty), pt, 1)

        # Main body (tail → head)
        base_col = (242, 242, 245) if self.variety != "ogon" else (245, 195, 45)
        edge_col = (195, 200, 210) if self.variety != "ogon" else (190, 140, 20)
        base_a = _tint_alpha((*base_col, 255), opacity)
        edge_a = _tint_alpha((*edge_col, 255), opacity)

        for i in range(self.num_joints - 1, -1, -1):
            t = i / (self.num_joints - 1)
            lx, ly = to_loc(*self.joints[i])
            ang = angles[i]
            r = max(1, int(self._body_radius(t)))

            pygame.draw.circle(local_surf, edge_a, (int(lx), int(ly)), r)
            if r > 2:
                pygame.draw.circle(local_surf, base_a, (int(lx - 1), int(ly - 1)), int(r * 0.88))

            for spot in self.spots:
                dist_t = abs(t - spot["t_center"])
                if dist_t < spot["t_radius"]:
                    factor = math.cos((dist_t / spot["t_radius"]) * (math.pi / 2))
                    sr = int(r * 0.86 * factor)
                    if sr > 1:
                        perp_ang = ang + math.pi / 2
                        sx = lx + math.cos(perp_ang) * (r * spot["side_offset"])
                        sy = ly + math.sin(perp_ang) * (r * spot["side_offset"])
                        pygame.draw.circle(
                            local_surf,
                            _tint_alpha((*spot["color"], 255), opacity),
                            (int(sx), int(sy)),
                            sr,
                        )

            if r > 4 and 0.08 < t < 0.72:
                pygame.draw.circle(
                    local_surf,
                    _tint_alpha((255, 255, 255, 95), opacity),
                    (int(lx - 2), int(ly - 2)),
                    int(r * 0.42),
                )

        # Dorsal fin
        dorsal_pts = []
        for i in range(8, 22):
            t = i / (self.num_joints - 1)
            lx, ly = to_loc(*self.joints[i])
            ang = angles[i]
            wave_d = math.sin(self.phase - t * 5.0) * 4.5 * self.scale
            dx = lx + math.cos(ang + math.pi / 2) * wave_d
            dy = ly + math.sin(ang + math.pi / 2) * wave_d
            dorsal_pts.append((dx, dy))
        if len(dorsal_pts) >= 2:
            pygame.draw.lines(
                local_surf,
                _tint_alpha((255, 255, 255, 165), opacity),
                False,
                dorsal_pts,
                max(2, int(3.2 * self.scale)),
            )

        # Eyes
        ex_base, ey_base = to_loc(*self.joints[2])
        eang = angles[2]
        for side in (-1, 1):
            perp = eang + side * 1.48
            ex = ex_base + math.cos(perp) * 11.5 * self.scale
            ey = ey_base + math.sin(perp) * 11.5 * self.scale
            er = max(2, int(2.8 * self.scale))
            pygame.draw.circle(local_surf, _tint_alpha((220, 215, 200, 255), opacity), (int(ex), int(ey)), er + 1)
            pygame.draw.circle(local_surf, _tint_alpha((12, 14, 18, 255), opacity), (int(ex), int(ey)), er)
            pygame.draw.circle(local_surf, _tint_alpha((255, 255, 255, 255), opacity), (int(ex - 1), int(ey - 1)), 1)

        surf.blit(local_surf, (min_x, min_y))


class Ripple:
    def __init__(self, x, y, max_r=95, strength=1.0):
        self.x = x
        self.y = y
        self.r = 5.0
        self.max_r = max_r
        self.strength = strength
        self.alpha = 110.0 * strength

    def update(self, dt):
        self.r += 42.0 * dt
        self.alpha = max(0.0, 110.0 * self.strength * (1.0 - self.r / self.max_r))

    def draw(self, surf):
        if self.alpha > 2:
            size = int(self.r * 2 + 6)
            rs = pygame.Surface((size, size), pygame.SRCALPHA)
            c = size // 2
            pygame.draw.circle(rs, (175, 225, 245, int(self.alpha)), (c, c), int(self.r), 1)
            if self.r > 18:
                pygame.draw.circle(
                    rs, (175, 225, 245, int(self.alpha * 0.5)), (c, c), int(self.r - 12), 1
                )
            if self.r > 36:
                pygame.draw.circle(
                    rs, (190, 235, 250, int(self.alpha * 0.28)), (c, c), int(self.r - 24), 1
                )
            surf.blit(rs, (int(self.x - c), int(self.y - c)))


def draw_water_surface(surf, t):
    """Sun caustics on the water surface plus floating lotus pads."""
    caustic_surf = pygame.Surface((W, H), pygame.SRCALPHA)
    for i in range(7):
        cx = W * 0.5 + math.cos(t * 0.35 + i * 1.1) * 280
        cy = H * 0.5 + math.sin(t * 0.28 + i * 1.4) * 180
        rad = int(130 + 35 * math.sin(t * 0.6 + i))
        pygame.draw.circle(caustic_surf, (120, 210, 235, 8), (int(cx), int(cy)), rad)
    surf.blit(caustic_surf, (0, 0))

    pads = [
        (135, 125, 62, 0.45, True),
        (205, 178, 44, 2.2, False),
        (1025, 595, 68, 3.7, True),
        (955, 635, 48, 1.1, False),
    ]
    for px, py, rad, notch, has_flower in pads:
        sway_x = math.sin(t * 0.8 + px * 0.01) * 3.0
        sway_y = math.cos(t * 0.7 + py * 0.01) * 2.5
        x, y = px + sway_x, py + sway_y

        ps = pygame.Surface((rad * 2 + 40, rad * 2 + 40), pygame.SRCALPHA)
        c = rad + 15
        pygame.draw.circle(ps, (2, 10, 14, 80), (c + 14, c + 18), rad)
        pygame.draw.circle(ps, (26, 76, 40), (c, c), rad)
        pygame.draw.circle(ps, (38, 102, 54), (c - 2, c - 2), int(rad * 0.86))
        for k in range(8):
            va = notch + 0.5 + k * 0.68
            pygame.draw.line(
                ps,
                (52, 122, 68, 120),
                (c, c),
                (c + math.cos(va) * (rad * 0.85), c + math.sin(va) * (rad * 0.85)),
                1,
            )
        cut_pts = [
            (c, c),
            (c + math.cos(notch - 0.24) * (rad + 4), c + math.sin(notch - 0.24) * (rad + 4)),
            (c + math.cos(notch + 0.24) * (rad + 4), c + math.sin(notch + 0.24) * (rad + 4)),
        ]
        pygame.draw.polygon(ps, (0, 0, 0, 0), cut_pts)

        if has_flower:
            fx, fy = c - 6, c - 4
            for layer_r, col in [(16, (235, 140, 165)), (11, (250, 185, 200)), (6, (255, 235, 130))]:
                for p_ang in range(0, 360, 45):
                    ra = math.radians(p_ang + t * 4)
                    px_f = fx + math.cos(ra) * (layer_r * 0.55)
                    py_f = fy + math.sin(ra) * (layer_r * 0.55)
                    pygame.draw.circle(ps, col, (int(px_f), int(py_f)), layer_r // 2)

        surf.blit(ps, (int(x - c), int(y - c)))


def draw_hint(
    surf,
    elapsed,
    overlay_active: bool = False,
    sprites_active: bool = False,
):
    """Brief on-screen control hint that fades after a few seconds."""
    if elapsed > HINT_FADE_S:
        return
    fade = 1.0 if elapsed < HINT_FADE_S - 3.0 else max(0.0, (HINT_FADE_S - elapsed) / 3.0)
    alpha = int(210 * fade)
    if alpha < 8:
        return
    if overlay_active:
        lines = [
            "Overlay on — interactive fish hidden",
            "Click / tap — ripples",
            "O — interactive    F11 — fullscreen    Esc — quit",
        ]
    else:
        look = "sprites" if sprites_active else "procedural"
        lines = [
            f"Click / tap — call the koi ({look})",
            "Space — scatter    P — sprites/procedural    O — overlay",
            "F11 — fullscreen    Esc — quit",
        ]
    pad_x, pad_y = 14, 10
    rendered = [HINT_FONT.render(line, True, (220, 240, 250)) for line in lines]
    box_w = max(r.get_width() for r in rendered) + pad_x * 2
    box_h = sum(r.get_height() for r in rendered) + pad_y * 2 + 4
    box = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
    pygame.draw.rect(box, (8, 22, 30, int(160 * fade)), (0, 0, box_w, box_h), border_radius=8)
    pygame.draw.rect(box, (120, 190, 220, alpha), (0, 0, box_w, box_h), 1, border_radius=8)
    y = pad_y
    for r in rendered:
        r.set_alpha(alpha)
        box.blit(r, (pad_x, y))
        y += r.get_height() + 2
    surf.blit(box, (18, 16))


def _parse_args(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(description="Standalone pygame koi pond")
    parser.add_argument(
        "--procedural",
        action="store_true",
        help="Force procedural vector draw (skip MP4 fish sprites).",
    )
    parser.add_argument(
        "--overlay",
        nargs="?",
        const=DEFAULT_OVERLAY_MP4,
        default=None,
        type=Path,
        help=(
            "Optional full-pond keyed MP4 overlay (path optional; default asset). "
            "Off by default. When on, interactive RealisticKoi are hidden (O toggles)."
        ),
    )
    parser.add_argument(
        "--fullscreen",
        action="store_true",
        help="Start fullscreen (F11 toggles; SCALED logical 1150x720)",
    )
    return parser.parse_args(argv)


def _load_overlay(path: Path) -> KoiOverlayVideo | None:
    """Decode/key MP4 once into Surfaces. Returns None if unavailable."""
    candidate = Path(path)
    if not candidate.is_file():
        print(f"[koi] Overlay file missing ({candidate}).", file=sys.stderr)
        return None
    print("[koi] Caching keyed overlay frames (one-time)…", file=sys.stderr)
    overlay = KoiOverlayVideo(candidate, (W, H), opacity=OVERLAY_OPACITY)
    if not overlay.available:
        return None
    return overlay


def _load_sprite_bank(path: Path) -> KoiSpriteBank | None:
    """Extract keyed fish crops from MP4. Returns None if unavailable."""
    candidate = Path(path)
    if not candidate.is_file():
        print(f"[koi] Sprite source missing ({candidate}); procedural draw.", file=sys.stderr)
        return None
    bank = KoiSpriteBank(candidate)
    if not bank.available:
        return None
    return bank


def _spawn_procedural_koi() -> list[RealisticKoi]:
    return [
        RealisticKoi(420, 310, 0.3, 105, 1.18, "kohaku", sprite_index=0),
        RealisticKoi(740, 450, 3.4, 95, 1.12, "sanke", sprite_index=1),
        RealisticKoi(580, 520, -1.2, 88, 1.00, "showa", sprite_index=2),
        RealisticKoi(320, 500, -0.5, 92, 0.92, "ogon", sprite_index=3),
    ]


def main(argv: list[str] | None = None):
    global screen

    args = _parse_args(argv)
    fullscreen = bool(args.fullscreen)
    screen = _create_display(fullscreen)
    pond_bed = create_pond_bed()

    # Interactive RealisticKoi always spawn; look = MP4 sprites when available.
    kois: list[RealisticKoi] = _spawn_procedural_koi()
    overlay_path = Path(args.overlay) if args.overlay is not None else DEFAULT_OVERLAY_MP4
    sprite_path = DEFAULT_OVERLAY_MP4
    want_overlay = args.overlay is not None
    use_sprites = not bool(args.procedural)
    sprites: KoiSpriteBank | None = None
    if use_sprites:
        sprites = _load_sprite_bank(sprite_path)
        if sprites is None:
            use_sprites = False
            print("[koi] Falling back to procedural draw.", file=sys.stderr)
        else:
            print(
                "[koi] Interactive pond with MP4 fish sprites (P toggles procedural).",
                file=sys.stderr,
            )
    else:
        print("[koi] Procedural draw (--procedural). P loads sprites if available.", file=sys.stderr)

    overlay: KoiOverlayVideo | None = None
    if want_overlay:
        overlay = _load_overlay(overlay_path)
        if overlay is not None:
            overlay.enabled = True
            print("[koi] Overlay mode (interactive fish hidden). Press O to return.", file=sys.stderr)
        else:
            print("[koi] Staying on interactive pond.", file=sys.stderr)

    ripples = []
    ripple_timer = 0.0
    surface_ripple_timer = 0.0
    sim_time = 0.0

    running = True
    try:
        while running:
            # Cap display rate; overlay advances on its own FPS accumulator.
            dt = clock.tick(60) / 1000.0
            sim_time += dt
            assert screen is not None

            overlay_active = (
                overlay is not None and overlay.available and overlay.enabled
            )
            sprites_active = bool(
                use_sprites and sprites is not None and sprites.available
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
                    elif event.key == pygame.K_p and not overlay_active:
                        if use_sprites and sprites is not None and sprites.available:
                            use_sprites = False
                            print("[koi] Procedural vector draw.", file=sys.stderr)
                        else:
                            if sprites is None:
                                sprites = _load_sprite_bank(sprite_path)
                            if sprites is not None and sprites.available:
                                use_sprites = True
                                print("[koi] MP4 fish sprites on.", file=sys.stderr)
                            else:
                                use_sprites = False
                                print("[koi] Sprites unavailable; staying procedural.", file=sys.stderr)
                        sprites_active = bool(
                            use_sprites and sprites is not None and sprites.available
                        )
                    elif event.key == pygame.K_o:
                        if overlay is None:
                            overlay = _load_overlay(overlay_path)
                            if overlay is not None:
                                overlay.enabled = True
                                print(
                                    "[koi] Overlay on (interactive fish hidden).",
                                    file=sys.stderr,
                                )
                        elif overlay.available:
                            overlay.enabled = not overlay.enabled
                            if overlay.enabled:
                                print(
                                    "[koi] Overlay on (interactive fish hidden).",
                                    file=sys.stderr,
                                )
                            else:
                                print(
                                    "[koi] Overlay off — interactive pond.",
                                    file=sys.stderr,
                                )
                        overlay_active = (
                            overlay is not None
                            and overlay.available
                            and overlay.enabled
                        )
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    mx, my = event.pos
                    ripples.append(Ripple(mx, my, max_r=140, strength=1.15))
                    if not overlay_active:
                        for k in kois:
                            k.attract_to(mx, my)

            screen.blit(pond_bed, (0, 0))

            if overlay_active:
                assert overlay is not None
                overlay.update(dt)
                overlay.draw(screen)
            else:
                bank = sprites if sprites_active else None
                for k in sorted(kois, key=lambda fish: fish.depth, reverse=True):
                    k.update(dt)
                    k.draw(screen, sprites=bank)

                # Occasional ripples from near-surface fish motion.
                ripple_timer += dt
                if ripple_timer > 0.75:
                    ripple_timer = 0.0
                    candidates = [k for k in kois if k.depth < 0.55] or kois
                    chosen = random.choice(candidates)
                    ripples.append(
                        Ripple(
                            chosen.x,
                            chosen.y,
                            max_r=85,
                            strength=0.55 + (1.0 - chosen.depth) * 0.35,
                        )
                    )

            # Soft ambient surface ripples (wind / drip feel).
            surface_ripple_timer += dt
            if surface_ripple_timer > 2.8:
                surface_ripple_timer = random.uniform(0.0, 0.6)
                ripples.append(
                    Ripple(
                        random.uniform(80, W - 80),
                        random.uniform(80, H - 80),
                        max_r=random.uniform(50, 90),
                        strength=0.35,
                    )
                )

            for r in ripples[:]:
                r.update(dt)
                r.draw(screen)
                if r.alpha <= 2:
                    ripples.remove(r)

            draw_water_surface(screen, sim_time)
            draw_hint(
                screen,
                sim_time,
                overlay_active=overlay_active,
                sprites_active=sprites_active,
            )

            pygame.display.flip()
    finally:
        if overlay is not None:
            overlay.close()
        if sprites is not None:
            sprites.close()
        pygame.quit()


if __name__ == "__main__":
    main()
