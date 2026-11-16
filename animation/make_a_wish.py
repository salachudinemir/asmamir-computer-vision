import math
import random
import numpy as np
import pygame

WIDTH = 800
HEIGHT = 900
FPS = 60

CW, CH = 500, 320
CAKE_X = 400
CAKE_Y = 560
U_CANDLES = 5

SPARK_COLORS = {
    "gold": (250, 200, 150),
    "champ": (255, 240, 220),
    "rose": (250, 170, 180),
    "white": (255, 255, 255),
    "blue": (100, 150, 255),
    "yellow": (255, 255, 100),
}
COL_NAMES = list(SPARK_COLORS.keys())

def clamp(v, a, b):
    return a if v < a else (b if v > b else b)

def lerp(a, b, t):
    return a + (b - a) * t

def smooth(t):
    return t * t * (3 - 2 * t)

class ParticleSystem:
    def __init__(self):
        self.particles = []
    def add(self, x, y, vx, vy, color, size, life, decay=0.02):
        self.particles.append([x, y, vx, vy, color, size, life, decay])
    def update(self):
        for p in self.particles:
            p[0] += p[2]
            p[1] += p[3]
            p[3] += 0.15
            p[6] -= p[7]
        self.particles = [p for p in self.particles if p[6] > 0]
    def draw(self, surface):
        for p in self.particles:
            alpha = int(clamp(p[6], 0, 1) * 255)
            surf = pygame.Surface((int(p[5]*2), int(p[5]*2)), pygame.SRCALPHA)
            pygame.draw.circle(surf, (*p[4], alpha), (int(p[5]), int(p[5])), int(p[5]))
            surface.blit(surf, (p[0] - p[5], p[1] - p[5]))

def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Make a Wish - Interactive Birthday Experience")
    clock = pygame.time.Clock()

    stars = []
    for _ in range(120):
        stars.append({
            'x': random.randint(0, WIDTH),
            'y': random.randint(0, HEIGHT),
            'size': random.uniform(1, 3),
            'alpha': random.randint(100, 255),
            'twinkle_speed': random.uniform(0.02, 0.08)
        })

    ps = ParticleSystem()
    state = "intro"
    timer = 0
    wish_hold_time = 0
    fullscreen = False

    font_large = pygame.font.SysFont("Georgia", 54, bold=True)
    font_med = pygame.font.SysFont("Georgia", 24)
    font_small = pygame.font.SysFont("Arial", 16)

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        timer += dt

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_f:
                    fullscreen = not fullscreen
                    if fullscreen:
                        screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.FULLSCREEN)
                    else:
                        screen = pygame.display.set_mode((WIDTH, HEIGHT))
                elif event.key == pygame.K_r:
                    state = "intro"
                    timer = 0
                    wish_hold_time = 0
                    ps.particles.clear()
                elif event.key == pygame.K_RETURN and state == "intro":
                    state = "cake_enter"
                    timer = 0
                elif event.key == pygame.K_SPACE and state == "wishing":
                    wish_hold_time += 0.5

        keys = pygame.key.get_pressed()
        if state == "wishing" and keys[pygame.K_SPACE]:
            wish_hold_time += dt * 1.5
            if wish_hold_time >= 3.0:
                state = "celebration"
                timer = 0
                for _ in range(150):
                    ps.add(CAKE_X + random.randint(-200, 200), CAKE_Y - 200, 
                           random.uniform(-4, 4), random.uniform(-8, -2), 
                           SPARK_COLORS[random.choice(COL_NAMES)], random.uniform(2, 5), 1.0, 0.01)

        if state == "cake_enter" and timer > 3.0:
            state = "candles_on"
            timer = 0
        elif state == "candles_on" and timer > 2.5:
            state = "wishing"
            timer = 0

        ps.update()

        screen.fill((10, 12, 25))
        for y in range(0, HEIGHT, 4):
            factor = y / HEIGHT
            col = (int(10 + factor * 15), int(12 + factor * 20), int(25 + factor * 40))
            pygame.draw.line(screen, col, (0, y), (WIDTH, y))

        for star in stars:
            twinkle = (math.sin(timer * star['twinkle_speed'] * 20 + star['x']) + 1) / 2
            alpha = int(star['alpha'] * (0.5 + 0.5 * twinkle))
            surf = pygame.Surface((int(star['size']*2), int(star['size']*2)), pygame.SRCALPHA)
            pygame.draw.circle(surf, (255, 255, 255, alpha), (int(star['size']), int(star['size'])), star['size'])
            screen.blit(surf, (star['x'], star['y']))

        if state != "intro":
            cake_surface_y = CAKE_Y - int(smooth(clamp(timer/2.0 if state == "cake_enter" else 1.0, 0, 1)) * 100)
            pygame.draw.ellipse(screen, (218, 165, 32), (CAKE_X - 220, CAKE_Y + 40, 440, 40))
            pygame.draw.ellipse(screen, (255, 215, 0), (CAKE_X - 210, CAKE_Y + 45, 420, 30))
            pygame.draw.rect(screen, (245, 245, 250), (CAKE_X - 160, CAKE_Y - 20, 320, 70), border_radius=10)
            pygame.draw.ellipse(screen, (230, 230, 240), (CAKE_X - 160, CAKE_Y - 30, 320, 30))
            pygame.draw.ellipse(screen, (245, 245, 250), (CAKE_X - 160, CAKE_Y + 40, 320, 30))
            pygame.draw.rect(screen, (245, 245, 250), (CAKE_X - 100, CAKE_Y - 100, 200, 80), border_radius=8)
            pygame.draw.ellipse(screen, (220, 220, 230), (CAKE_X - 100, CAKE_Y - 110, 200, 30))
            pygame.draw.ellipse(screen, (245, 245, 250), (CAKE_X - 100, CAKE_Y - 20, 200, 30))

            if state in ["candles_on", "wishing", "celebration"]:
                for i in range(U_CANDLES):
                    cx = CAKE_X - 60 + i * 30
                    cy = CAKE_Y - 130
                    pygame.draw.rect(screen, (250, 250, 250), (cx - 4, cy, 8, 35))
                    if state != "celebration" or wish_hold_time < 3.0:
                        flame_h = random.randint(12, 18)
                        pygame.draw.ellipse(screen, (255, 165, 0), (cx - 5, cy - flame_h, 10, flame_h))
                        pygame.draw.ellipse(screen, (255, 255, 200), (cx - 2, cy - flame_h + 4, 4, flame_h - 6))

        if state == "intro":
            txt = font_large.render("MAKE A WISH", True, (255, 215, 0))
            sub = font_med.render("an interactive birthday surprise", True, (200, 200, 220))
            press = font_small.render("Press ENTER to begin", True, (180, 180, 180))
            screen.blit(txt, (WIDTH//2 - txt.get_width()//2, HEIGHT//2 - 60))
            screen.blit(sub, (WIDTH//2 - sub.get_width()//2, HEIGHT//2 + 5))
            screen.blit(press, (WIDTH//2 - press.get_width()//2, HEIGHT//2 + 90))
        elif state == "cake_enter":
            msg = font_med.render("Someone special is celebrating today...", True, (220, 220, 230))
            screen.blit(msg, (WIDTH//2 - msg.get_width()//2, 120))
        elif state == "candles_on":
            msg = font_med.render("Before we celebrate...", True, (220, 220, 230))
            sub2 = font_med.render("Close your eyes and make a wish.", True, (240, 240, 250))
            screen.blit(msg, (WIDTH//2 - msg.get_width()//2, 100))
            screen.blit(sub2, (WIDTH//2 - sub2.get_width()//2, 135))
        elif state == "wishing":
            msg = font_med.render("Press and hold SPACE to make your wish.", True, (240, 240, 250))
            screen.blit(msg, (WIDTH//2 - msg.get_width()//2, 120))
            if wish_hold_time > 0:
                prog = font_small.render("Keep holding...", True, (255, 215, 0))
                screen.blit(prog, (WIDTH//2 - prog.get_width()//2, 160))
        elif state == "celebration":
            wish_text = font_large.render("HAPPY BIRTHDAY!", True, (255, 215, 0))
            wish_sub = font_med.render("May every little wish find its way to you.", True, (230, 230, 240))
            screen.blit(wish_text, (WIDTH//2 - wish_text.get_width()//2, 700))
            screen.blit(wish_sub, (WIDTH//2 - wish_sub.get_width()//2, 765))
            restart_hint = font_small.render("Press R to replay", True, (150, 150, 150))
            screen.blit(restart_hint, (WIDTH//2 - restart_hint.get_width()//2, 830))

        ps.draw(screen)
        footer = font_small.render("R: restart    F: fullscreen    ESC: exit", True, (100, 100, 120))
        screen.blit(footer, (WIDTH//2 - footer.get_width()//2, HEIGHT - 30))

        pygame.display.flip()

    pygame.quit()

if __name__ == "__main__":
    main()
