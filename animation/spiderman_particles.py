"""
Spider-Man particle assembly from a reference image.

Particles scatter, then form the Spider-Man silhouette sampled from
animation/assets/spiderman-ref.png. Click / SPACE toggles form vs scatter.

Run:
    python animation/spiderman_particles.py
"""

import math
import os
import random
import sys

import pygame

os.environ.setdefault("SDL_VIDEO_CENTERED", "1")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGE_PATH = os.path.join(BASE_DIR, "assets", "spiderman-ref.png")

MAX_WIDTH = 900
MAX_HEIGHT = 900
NUM_PARTICLES = 20000
# Higher density → finer grid step when collecting stipple candidates.
SAMPLE_DENSITY = 12
# Skip near-black / near-white noise; keep suit + speed-line colors.
MIN_LUMA = 28
MAX_LUMA = 245
BG_COLOR = (10, 11, 16)
# Small radii for fine detail (drawn as at least 1px).
PARTICLE_SIZE_MIN = 0.6
PARTICLE_SIZE_MAX = 1.25

pygame.init()


def load_target_image(path):
    """Load and fit IMAGE_PATH inside MAX_WIDTH×MAX_HEIGHT (aspect preserved)."""
    if not os.path.isfile(path):
        raise FileNotFoundError(
            f"Spider-Man reference missing: {path}\n"
            "Place spiderman-ref.png under animation/assets/."
        )
    raw = pygame.image.load(path)
    iw, ih = raw.get_size()
    scale = min(MAX_WIDTH / iw, MAX_HEIGHT / ih)
    nw = max(1, int(round(iw * scale)))
    nh = max(1, int(round(ih * scale)))
    return pygame.transform.smoothscale(raw, (nw, nh))


def sample_targets(surf, count):
    """Sample colored pixels as particle targets (skip near-empty luma)."""
    w, h = surf.get_size()
    candidates = []
    step = max(1, int(math.sqrt((w * h) / (count * SAMPLE_DENSITY))))
    for y in range(0, h, step):
        for x in range(0, w, step):
            r, g, b, *_ = surf.get_at((x, y))
            luma = 0.2126 * r + 0.7152 * g + 0.0722 * b
            if MIN_LUMA <= luma <= MAX_LUMA:
                candidates.append(
                    (x + random.uniform(-0.4, 0.4), y + random.uniform(-0.4, 0.4), (r, g, b))
                )

    if not candidates:
        raise RuntimeError(f"No sampleable pixels in {IMAGE_PATH}")

    if len(candidates) > count:
        random.shuffle(candidates)
        candidates = candidates[:count]
    else:
        # Upsample with jitter if the grid was sparse.
        while len(candidates) < count:
            x, y, color = random.choice(candidates)
            candidates.append(
                (x + random.uniform(-1.5, 1.5), y + random.uniform(-1.5, 1.5), color)
            )
        candidates = candidates[:count]

    targets = [(c[0], c[1]) for c in candidates]
    colors = [c[2] for c in candidates]
    return targets, colors, w, h


try:
    image = load_target_image(IMAGE_PATH)
except FileNotFoundError as exc:
    print(exc, file=sys.stderr)
    pygame.quit()
    sys.exit(1)

targets, colors, WIDTH, HEIGHT = sample_targets(image, NUM_PARTICLES)
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Spider-Man Particle Assembly - Python Pygame")
clock = pygame.time.Clock()


class Particle:
    def __init__(self, tx, ty, color):
        self.x = random.uniform(0, WIDTH)
        self.y = random.uniform(0, HEIGHT)
        self.target_x = tx
        self.target_y = ty
        self.vx = random.uniform(-3, 3)
        self.vy = random.uniform(-3, 3)
        self.color = color
        self.size = random.uniform(PARTICLE_SIZE_MIN, PARTICLE_SIZE_MAX)

    def update(self, state, mouse_pos):
        if state == "forming":
            dx = self.target_x - self.x
            dy = self.target_y - self.y
            self.x += dx * 0.1 + self.vx * 0.05
            self.y += dy * 0.1 + self.vy * 0.05
            self.vx *= 0.85
            self.vy *= 0.85
        else:
            self.x += self.vx
            self.y += self.vy
            if self.x < 0 or self.x > WIDTH:
                self.vx *= -1
            if self.y < 0 or self.y > HEIGHT:
                self.vy *= -1

        mdx = mouse_pos[0] - self.x
        mdy = mouse_pos[1] - self.y
        mdist = math.hypot(mdx, mdy)
        if mdist < 100:
            angle = math.atan2(mdy, mdx)
            self.x -= math.cos(angle) * 6
            self.y -= math.sin(angle) * 6

    def draw(self, surface):
        radius = max(1, int(round(self.size)))
        pygame.draw.circle(surface, self.color, (int(self.x), int(self.y)), radius)


particles = [Particle(targets[i][0], targets[i][1], colors[i]) for i in range(NUM_PARTICLES)]

state = "forming"
running = True

while running:
    mouse_pos = pygame.mouse.get_pos()
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                running = False
            elif event.key in (pygame.K_c, pygame.K_SPACE):
                state = "scatter" if state == "forming" else "forming"
        elif event.type == pygame.MOUSEBUTTONDOWN:
            state = "scatter" if state == "forming" else "forming"

    screen.fill(BG_COLOR)

    for p in particles:
        p.update(state, mouse_pos)
        p.draw(screen)

    font = pygame.font.SysFont("Arial", 16)
    txt = font.render("Click or Press SPACE to scatter/form. ESC to exit.", True, (150, 150, 180))
    screen.blit(txt, (20, HEIGHT - 30))

    pygame.display.flip()
    clock.tick(60)

pygame.quit()
