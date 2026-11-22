import sys
import math
import random
import pygame

WIDTH, HEIGHT = 720, 1280
FPS = 60
BG_COLOR = (0, 0, 0)

NUM_LINES = 160
TOTAL_TIME = 32
SCALE = 18.0

BLUE_COLOR = (0, 180, 255)
GLOW_COLOR = (0, 90, 220)
CORE_COLOR = (180, 235, 255)


def heart_point(t, scale=SCALE):
    x = 16 * (math.sin(t) ** 3)
    y = -(
        13 * math.cos(t)
        - 5 * math.cos(2 * t)
        - 2 * math.cos(3 * t)
        - math.cos(4 * t)
    )
    return x * scale, y * scale


class Sparkle:
    """Very fine, delicate glowing blue embers."""

    def __init__(self, cx, cy):
        self.cx = cx
        self.cy = cy
        self.reset()

    def reset(self):
        t = random.uniform(0, 2 * math.pi)
        hx, hy = heart_point(t, SCALE * random.uniform(0.35, 1.05))
        self.x = self.cx + hx + random.uniform(-14, 14)
        self.y = self.cy + hy + random.uniform(-14, 14)
        self.vx = random.uniform(-0.35, 0.35)
        self.vy = random.uniform(-0.8, -0.15)
        self.radius = random.uniform(1.0, 2.6)
        self.life = random.uniform(0.4, 1.0)
        self.decay = random.uniform(0.008, 0.022)
        self.phase = random.uniform(0, 2 * math.pi)

    def update(self, elapsed):
        self.x += self.vx + math.sin(elapsed * 2.0 + self.phase) * 0.25
        self.y += self.vy
        self.life -= self.decay
        if self.life <= 0:
            self.reset()

    def draw(self, surface):
        if self.life <= 0:
            return
        twinkle = 0.65 + 0.35 * math.sin(pygame.time.get_ticks() * 0.01 + self.phase)
        alpha = max(0, min(255, int(255 * self.life * twinkle)))

        r_glow = max(2, int(self.radius * 3))
        glow_surf = pygame.Surface((r_glow * 2, r_glow * 2), pygame.SRCALPHA)
        pygame.draw.circle(
            glow_surf,
            (*GLOW_COLOR, max(0, min(255, int(alpha * 0.35)))),
            (r_glow, r_glow),
            r_glow,
        )
        surface.blit(glow_surf, (int(self.x - r_glow), int(self.y - r_glow)), special_flags=pygame.BLEND_RGBA_ADD)

        core_surf = pygame.Surface((int(self.radius * 4) + 2, int(self.radius * 4) + 2), pygame.SRCALPHA)
        cr = core_surf.get_width() // 2
        pygame.draw.circle(core_surf, (*CORE_COLOR, alpha), (cr, cr), max(1, int(self.radius)))
        surface.blit(core_surf, (int(self.x - cr), int(self.y - cr)), special_flags=pygame.BLEND_RGBA_ADD)


def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Blue Animated Heart - Pygame")
    clock = pygame.time.Clock()

    cx, cy = WIDTH // 2, HEIGHT // 2 - 40
    sparkles = [Sparkle(cx, cy) for _ in range(95)]
    start_ticks = pygame.time.get_ticks()

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_r:
                    start_ticks = pygame.time.get_ticks()

        elapsed = ((pygame.time.get_ticks() - start_ticks) / 1000.0) % TOTAL_TIME
        progress = min(1.0, elapsed / (TOTAL_TIME * 0.75))
        pulse = 1.0 + 0.04 * math.sin(elapsed * 3.0)

        screen.fill(BG_COLOR)

        layer_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        active_lines = max(1, int(NUM_LINES * progress))

        for i in range(active_lines):
            ratio = i / max(1, NUM_LINES - 1)
            t1 = ratio * 2 * math.pi
            t2 = ((i + 1) / max(1, NUM_LINES - 1)) * 2 * math.pi

            for ring_scale in (0.55, 0.8, 1.0):
                s = SCALE * ring_scale * pulse
                x1, y1 = heart_point(t1, s)
                x2, y2 = heart_point(t2, s)
                p1 = (cx + x1, cy + y1)
                p2 = (cx + x2, cy + y2)

                alpha = int(60 + 175 * (1.0 - abs(ring_scale - 0.85)))
                pygame.draw.line(layer_surf, (*GLOW_COLOR, max(20, min(180, alpha // 2))), p1, p2, 5)
                pygame.draw.line(layer_surf, (*BLUE_COLOR, max(40, min(255, alpha))), p1, p2, 2)

        # Outer core contour
        core_pts = []
        steps = max(2, int(240 * progress))
        for k in range(steps):
            tk = (k / 240.0) * 2 * math.pi
            kx, ky = heart_point(tk, SCALE * pulse)
            core_pts.append((cx + kx, cy + ky))
        if len(core_pts) > 1:
            pygame.draw.lines(layer_surf, (*CORE_COLOR, 230), False, core_pts, 2)

        screen.blit(layer_surf, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)

        for sp in sparkles:
            sp.update(elapsed)
            sp.draw(screen)

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
