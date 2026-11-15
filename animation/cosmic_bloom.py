import math
import random
import sys
import numpy as np
import pygame

# ------------- CONFIGURATION -------------
W, H = 1000, 750
LW, LH = W // 2, H // 2  # half-resolution particle/trail layer

pygame.init()
screen = pygame.display.set_mode((W, H))
pygame.display.set_caption("Cosmic Bloom | Poornas Tech Talk")
clock = pygame.time.Clock()

# Palettes
PALETTES = ["CYAN ICE BLUE", "GOLDEN AMBER"]
NPAL = len(PALETTES)

class ParticleSystem:
    def __init__(self):
        self.particles = []
        for _ in range(800):
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(0.5, 3.0)
            self.particles.append({
                'x': W // 2,
                'y': H // 2,
                'vx': math.cos(angle) * speed,
                'vy': math.sin(angle) * speed,
                'radius': random.uniform(1.5, 3.5),
                'life': random.randint(100, 300)
            })

    def update(self):
        for p in self.particles:
            p['x'] += p['vx']
            p['y'] += p['vy']
            p['life'] -= 1
            if p['life'] <= 0:
                p['x'] = W // 2
                p['y'] = H // 2
                angle = random.uniform(0, 2 * math.pi)
                speed = random.uniform(0.5, 3.0)
                p['vx'] = math.cos(angle) * speed
                p['vy'] = math.sin(angle) * speed
                p['life'] = random.randint(100, 300)

    def draw(self, surface):
        for p in self.particles:
            pygame.draw.circle(surface, (173, 216, 230), (int(p['x']), int(p['y'])), int(p['radius']))

ps = ParticleSystem()

# Main Loop
running = True
while running:
    screen.fill((10, 10, 20))
    
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    ps.update()
    ps.draw(screen)

    pygame.display.flip()
    clock.tick(60)

pygame.quit()
sys.exit()