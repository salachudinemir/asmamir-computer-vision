import pygame
import cv2
import numpy as np
import os
import random

pygame.init()
W, H = 1000, 750
screen = pygame.display.set_mode((W, H))
pygame.display.set_caption("Monalisa - Stippling Particle Art")
clock = pygame.time.Clock()

# Classic stipple: light paper, black ink
BG_COLOR = (248, 246, 240)
DOT_COLOR = (12, 12, 12)
MAX_POINTS = 600000
MAX_HEIGHT = 750
# Grid step (finer than 3 → more candidates, sharper form)
STEP = 1
# Contrast >1 expands midtones; gamma >1 concentrates dots in dark regions
CONTRAST = 1.45
GAMMA = 1.75
JITTER = 0.45

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGE_PATH = os.path.join(BASE_DIR, "assets", "monalisa.jpg")
# Reveal order: "waterfall" = top-to-bottom (y then x); "shuffle" = random
FILL_MODE = "waterfall"


def load_and_prepare_image(path):
    """Load image and fit inside W×H without stretch (letterbox/pillarbox on paper BG)."""
    bg_gray = int(round(0.299 * BG_COLOR[0] + 0.587 * BG_COLOR[1] + 0.114 * BG_COLOR[2]))
    canvas = np.full((H, W), bg_gray, dtype=np.uint8)

    img = cv2.imread(path) if os.path.exists(path) else None
    if img is None:
        cv2.putText(
            canvas,
            "MONALISA",
            (W // 2 - 200, H // 2),
            cv2.FONT_HERSHEY_SIMPLEX,
            2,
            (255, 255, 255),
            3,
        )
        return canvas

    ih, iw = img.shape[:2]
    scale = min(W / iw, H / ih)
    nw = max(1, int(round(iw * scale)))
    nh = max(1, int(round(ih * scale)))
    resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)

    x0 = (W - nw) // 2
    y0 = (H - nh) // 2
    canvas[y0 : y0 + nh, x0 : x0 + nw] = gray
    return canvas


def prepare_darkness_map(gray):
    """Stretch contrast, then gamma-weight darkness so dark areas get denser dots."""
    g = gray.astype(np.float32) / 255.0
    g = np.clip((g - 0.5) * CONTRAST + 0.5, 0.0, 1.0)
    darkness = np.power(1.0 - g, GAMMA)
    return darkness


gray_img = load_and_prepare_image(IMAGE_PATH)
darkness = prepare_darkness_map(gray_img)

# Generate stippling points: rejection sampling weighted by darkness
points = []
print("Generating stippling points...")
h, w = gray_img.shape
for y in range(0, h, STEP):
    for x in range(0, w, STEP):
        if random.random() < float(darkness[y, x]):
            points.append(
                (
                    x + random.uniform(-JITTER, JITTER),
                    y + random.uniform(-JITTER, JITTER),
                )
            )

# Subsample first so density stays image-wide; then order the reveal.
if len(points) > MAX_POINTS:
    random.shuffle(points)
    points = points[:MAX_POINTS]

if FILL_MODE == "waterfall":
    points.sort(key=lambda p: (p[1], p[0]))
else:
    random.shuffle(points)

print(f"Ready: {len(points)} points (step={STEP}, gamma={GAMMA}, contrast={CONTRAST})")

current_count = 0
batch_size = 2500
running = True
font = pygame.font.SysFont("Arial", 16)

while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                running = False
            elif event.key == pygame.K_r:
                current_count = 0

    screen.fill(BG_COLOR)

    if current_count < len(points):
        current_count = min(len(points), current_count + batch_size)

    # Draw points (black ink on light paper)
    for i in range(current_count):
        pt = points[i]
        screen.set_at((int(pt[0]), int(pt[1])), DOT_COLOR)

    # UI overlay info
    txt = font.render(
        f"Points: {current_count} / {len(points)} | Press 'R' to restart, ESC to exit",
        True,
        (90, 90, 90),
    )
    screen.blit(txt, (20, H - 30))

    pygame.display.flip()
    clock.tick(60)

pygame.quit()
