import os
import sys
import math
import random
import cv2
import numpy as np
import pygame

# --- Configuration ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGE = os.path.join(BASE_DIR, "assets", "sakura.jpg")
FALLBACK_IMAGE = os.path.join(BASE_DIR, "assets", "sakura.jpg")

THRESH = 10            # petals cut off? lower it
MOTION = "grow"        # "grow" | "gather"
WIND = 0               # 0 = flower · 1 = leaves
ROUGH = 0.7            # grain of the texture
EXACT_END = True       # settle cleanly into exact original photo pixels at completion

WIDTH, HEIGHT = 720, 1280
FPS = 60
TOTAL_FRAMES = 308
NUM_POINTS = 619053
NUM_HAIRS = 59500
NUM_STREAKS = 9000

BG_RGB = np.array([12, 12, 14], dtype=np.float32)


def has_checkerboard_bg(img_bgr):
    """Detect if the image actually has a fake transparency checkerboard background."""
    b = img_bgr[:, :, 0].astype(np.float32)
    g = img_bgr[:, :, 1].astype(np.float32)
    r = img_bgr[:, :, 2].astype(np.float32)
    max_c = np.maximum(np.maximum(r, g), b)
    min_c = np.minimum(np.minimum(r, g), b)
    chroma = max_c - min_c
    lum = 0.299 * r + 0.587 * g + 0.114 * b

    # Check border pixels first: real dark-background photos have near-black borders
    border_lum = np.concatenate([
        lum[0, :], lum[-1, :], lum[:, 0], lum[:, -1]
    ])
    if np.percentile(border_lum, 75) < 25.0:
        return False

    neutral_bright = (chroma < 18.0) & (lum > 155.0)
    return np.mean(neutral_bright) > 0.15


def clean_foreground_mask(img_bgr):
    """Extract foreground mask cleanly without punching holes inside petals or thin stamens."""
    b = img_bgr[:, :, 0].astype(np.float32)
    g = img_bgr[:, :, 1].astype(np.float32)
    r = img_bgr[:, :, 2].astype(np.float32)
    lum = 0.299 * r + 0.587 * g + 0.114 * b

    fg = lum > THRESH

    if has_checkerboard_bg(img_bgr):
        max_c = np.maximum(np.maximum(r, g), b)
        min_c = np.minimum(np.minimum(r, g), b)
        chroma = max_c - min_c
        checker_bg = (chroma < 18.0) & (lum > 155.0)
        fg = fg & (~checker_bg)

    # Close tiny 1-2px gaps inside petals/buds so there are no pinholes
    fg_u8 = (fg.astype(np.uint8)) * 255
    fg_u8 = cv2.morphologyEx(fg_u8, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8), iterations=1)
    clean_mask = fg_u8 > 0

    out = np.zeros_like(img_bgr)
    out[clean_mask] = img_bgr[clean_mask]
    return out, clean_mask


def build_sakura_canvas(w, h):
    """Load sakura_2.jpg (or sakura.jpg fallback) cleanly onto the vertical canvas."""
    chosen_path = None
    for candidate in (IMAGE, FALLBACK_IMAGE):
        if os.path.exists(candidate) and cv2.imread(candidate) is not None:
            chosen_path = candidate
            break

    if chosen_path is not None:
        loaded = cv2.imread(chosen_path)
        ih, iw, _ = loaded.shape
        # Leave space on the left for the sidebar so the branch sits cleanly in view
        avail_w = w - 185
        scale = min((avail_w * 0.96) / iw, (h * 0.94) / ih)
        nw, nh = max(1, int(iw * scale)), max(1, int(ih * scale))
        resized = cv2.resize(loaded, (nw, nh), interpolation=cv2.INTER_AREA)
        cleaned, mask = clean_foreground_mask(resized)

        canvas = np.zeros((h, w, 3), dtype=np.uint8)
        ox = 185 + max(0, (avail_w - nw) // 2)
        oy = max(0, (h - nh) // 2)
        canvas[oy:oy + nh, ox:ox + nw] = cleaned

        full_mask = np.zeros((h, w), dtype=bool)
        full_mask[oy:oy + nh, ox:ox + nw] = mask
        print(f"[INFO] Loaded sakura image: {chosen_path} ({nw}x{nh})")
        return canvas, full_mask, os.path.basename(chosen_path)

    print("[INFO] Using built-in sakura branch fallback.")
    canvas = np.zeros((h, w, 3), dtype=np.uint8)
    cx, cy = 440, h // 2 + 40
    stem_pts = [
        (cx - 25, cy + 360),
        (cx - 5, cy + 160),
        (cx + 20, cy - 30),
        (cx - 10, cy - 230),
        (cx + 15, cy - 360),
    ]
    for i in range(len(stem_pts) - 1):
        cv2.line(canvas, stem_pts[i], stem_pts[i + 1], (55, 45, 72), max(4, 14 - i * 2))

    rng = random.Random(12)
    blossoms = [
        (cx - 10, cy + 150, 52),
        (cx - 105, cy + 55, 58),
        (cx + 25, cy + 30, 62),
        (cx + 125, cy - 65, 55),
        (cx - 15, cy - 110, 64),
        (cx - 95, cy - 210, 52),
        (cx + 85, cy - 245, 56),
        (cx + 10, cy - 320, 50),
    ]
    for bx, by, rad in blossoms:
        for p in range(5):
            ang = p * (2 * math.pi / 5.0) - math.pi / 2.0
            px = int(bx + math.cos(ang) * rad * 0.45)
            py = int(by + math.sin(ang) * rad * 0.45)
            cv2.ellipse(canvas, (px, py), (int(rad * 0.46), int(rad * 0.30)), math.degrees(ang), 0, 360, (205, 165, 248), -1)
            cv2.ellipse(canvas, (px, py), (int(rad * 0.28), int(rad * 0.18)), math.degrees(ang), 0, 360, (240, 222, 254), -1)
        cv2.circle(canvas, (bx, by), max(3, rad // 9), (90, 55, 200), -1)

    gray = cv2.cvtColor(canvas, cv2.COLOR_BGR2GRAY)
    return canvas, gray > THRESH, "sakura_2.jpg"


def precompute_layers(img_bgr, mask):
    """Build dense sakura particle & hair layers covering the whole branch/petals without gaps."""
    ys, xs = np.where(mask)
    if len(xs) == 0:
        xs = np.array([WIDTH // 2])
        ys = np.array([HEIGHT // 2])

    rng = np.random.default_rng(42)
    total_fg = len(xs)

    # Sample up to 90,000 pixels across the entire branch/petals so nothing looks torn or missing
    n_anchors = min(total_fg, 90000)
    idx = rng.choice(total_fg, size=n_anchors, replace=total_fg < n_anchors)

    ax = xs[idx].astype(np.float32)
    ay = ys[idx].astype(np.float32)
    exact_rgb = img_bgr[ay.astype(int), ax.astype(int)][:, ::-1].astype(np.float32)

    # Bottom-to-top growth order
    y_norm = 1.0 - (ay / max(1, HEIGHT - 1))
    order = np.argsort(y_norm) if MOTION == "grow" else np.arange(n_anchors)

    ax = ax[order]
    ay = ay[order]
    exact_rgb = exact_rgb[order]
    y_norm = y_norm[order]

    t_start = np.clip(y_norm * 0.72 + rng.uniform(-0.04, 0.05, size=n_anchors), 0.0, 0.80).astype(np.float32)
    t_dur = rng.uniform(0.14, 0.22, size=n_anchors).astype(np.float32)

    # Keep offset subtle so petals stay cohesive and never tear apart
    fiber_dx = rng.normal(0.0, 1.3 * ROUGH, size=n_anchors).astype(np.float32)
    fiber_dy = rng.normal(0.0, 1.3 * ROUGH, size=n_anchors).astype(np.float32)
    hair_ang = rng.uniform(-math.pi * 0.85, -math.pi * 0.15, size=n_anchors).astype(np.float32)
    hair_len = rng.uniform(3.0, 8.5 * (0.5 + ROUGH), size=n_anchors).astype(np.float32)
    shade = rng.uniform(0.84, 1.12, size=(n_anchors, 1)).astype(np.float32)
    stipple_rgb = np.clip(exact_rgb * shade, 0, 255).astype(np.float32)

    return ax, ay, exact_rgb.astype(np.uint8), stipple_rgb, t_start, t_dur, fiber_dx, fiber_dy, hair_ang, hair_len


def draw_sidebar(screen, font_sm, font_md, img_label, frame_idx, elapsed_s):
    panel_w = 185
    pygame.draw.rect(screen, (14, 14, 17), (0, 0, panel_w, HEIGHT))
    pygame.draw.line(screen, (36, 36, 42), (panel_w, 0), (panel_w, HEIGHT), 1)

    done = frame_idx >= TOTAL_FRAMES
    badge_color = (65, 195, 125) if done else (235, 145, 55)
    badge_text = "● done" if done else "● running"
    screen.blit(font_md.render(badge_text, True, badge_color), (14, 14))

    rows = [
        ("IMAGE", img_label),
        ("SIZE", "0.62M"),
        ("MOTION", MOTION),
        ("POINTS", "60k"),
        ("WIND", str(WIND)),
        ("FRAME", f"{frame_idx} / {TOTAL_FRAMES}"),
        ("ROUGH", str(ROUGH)),
        ("TIME", f"{elapsed_s:.1f}s"),
        ("THRESH", str(THRESH)),
        ("TOTAL", "25.6"),
    ]
    y_pos = 48
    for label, val in rows:
        screen.blit(font_sm.render(label, True, (115, 120, 130)), (14, y_pos))
        screen.blit(font_md.render(val, True, (225, 228, 232)), (14, y_pos + 15))
        y_pos += 44


def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
    pygame.display.set_caption("particles - preview")
    clock = pygame.time.Clock()
    font_sm = pygame.font.SysFont("Consolas", 12)
    font_md = pygame.font.SysFont("Consolas", 15, bold=True)

    img_bgr, mask, img_label = build_sakura_canvas(WIDTH, HEIGHT)
    exact_rgb_full = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    ax, ay, exact_u8, stipple_rgb, t_start, t_dur, fdx, fdy, hang, hlen = precompute_layers(img_bgr, mask)

    frame_idx = 1
    running = True

    while running:
        win_w, win_h = screen.get_size()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_r:
                    frame_idx = 1

        progress = min(1.0, frame_idx / TOTAL_FRAMES)
        elapsed_s = (frame_idx - 1) / FPS

        local_p = np.clip((progress - t_start) / t_dur, 0.0, 1.0)
        ease = 1.0 - ((1.0 - local_p) ** 2.4)
        settle = np.clip((local_p - 0.25) / 0.75, 0.0, 1.0) ** 1.5

        active = local_p > 0.0
        px = ax[active]
        py = ay[active]
        pexact = exact_u8[active].astype(np.float32)
        pstipple = stipple_rgb[active]
        pease = ease[active]
        psettle = settle[active]
        plocal = local_p[active]
        cfdx = fdx[active]
        cfdy = fdy[active]
        chang = hang[active]
        chlen = hlen[active]

        scatter_scale = (1.0 - psettle) * (1.0 - 0.5 * pease)
        sprout_y = (1.0 - pease) * 20.0
        wind_x = (WIND * 10.0 * progress + np.sin(elapsed_s * 1.6 + py * 0.015) * 1.0 * ROUGH * plocal) * (1.0 - psettle)

        rx = np.clip((px + cfdx * scatter_scale + wind_x).astype(np.int32), 0, WIDTH - 1)
        ry = np.clip((py + cfdy * scatter_scale + sprout_y).astype(np.int32), 0, HEIGHT - 1)

        pcol = np.clip(pstipple * (1.0 - psettle[:, None]) + pexact * psettle[:, None], 0, 255).astype(np.uint8)

        canvas = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
        canvas[:, :] = BG_RGB.astype(np.uint8)

        # Fill settled regions from exact original image pixels so there are zero holes/tears
        if EXACT_END and progress > 0.15:
            max_y_reached = int(HEIGHT * (1.0 - min(1.0, progress * 1.18) * 0.92))
            if progress >= 0.992:
                canvas[mask] = exact_rgb_full[mask]
            else:
                wave_mask = mask.copy()
                wave_mask[:max_y_reached, :] = False
                blend_w = min(1.0, max(0.0, (progress - 0.20) / 0.78))
                canvas[wave_mask] = (
                    canvas[wave_mask].astype(np.float32) * (1.0 - blend_w)
                    + exact_rgb_full[wave_mask].astype(np.float32) * blend_w
                ).astype(np.uint8)

        canvas[ry, rx] = pcol
        rx1 = np.clip(rx + 1, 0, WIDTH - 1)
        ry1 = np.clip(ry + 1, 0, HEIGHT - 1)
        canvas[ry, rx1] = np.maximum(canvas[ry, rx1], (pcol.astype(np.float32) * 0.85).astype(np.uint8))
        canvas[ry1, rx] = np.maximum(canvas[ry1, rx], (pcol.astype(np.float32) * 0.85).astype(np.uint8))

        surf = pygame.surfarray.make_surface(np.transpose(canvas, (1, 0, 2)))

        # Subtle hairs/streaks only during active growth, fading away as it settles
        n_act = len(rx)
        if n_act > 20 and progress < 0.97:
            step = max(1, n_act // 1800)
            for k in range(0, n_act, step):
                s_k = float(psettle[k])
                if s_k > 0.8:
                    continue
                x0, y0 = int(rx[k]), int(ry[k])
                ang = float(chang[k]) + math.sin(elapsed_s * 2.0 + k) * 0.15
                ln = float(chlen[k]) * float(pease[k]) * (1.0 - s_k)
                if ln > 0.5:
                    x1 = int(max(0, min(WIDTH - 1, x0 + math.cos(ang) * ln)))
                    y1 = int(max(0, min(HEIGHT - 1, y0 + math.sin(ang) * ln)))
                    c = pcol[k]
                    pygame.draw.line(surf, (int(c[0]), int(c[1]), int(c[2])), (x0, y0), (x1, y1), 1)

        full_frame = pygame.Surface((WIDTH, HEIGHT))
        full_frame.fill((12, 12, 14))
        full_frame.blit(surf, (0, 0))
        draw_sidebar(full_frame, font_sm, font_md, img_label, frame_idx, elapsed_s)

        if (win_w, win_h) != (WIDTH, HEIGHT):
            scale = min(win_w / WIDTH, win_h / HEIGHT)
            dw, dh = max(1, int(WIDTH * scale)), max(1, int(HEIGHT * scale))
            scaled = pygame.transform.smoothscale(full_frame, (dw, dh))
            screen.fill((10, 10, 12))
            screen.blit(scaled, ((win_w - dw) // 2, (win_h - dh) // 2))
        else:
            screen.blit(full_frame, (0, 0))

        pygame.display.flip()

        if frame_idx < TOTAL_FRAMES:
            frame_idx += 1
        clock.tick(FPS)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()