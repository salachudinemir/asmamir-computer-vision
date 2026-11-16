import pygame
import math
import random

pygame.init()
WIDTH, HEIGHT = 900, 900
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Spider-Man Particle Assembly - Python Pygame")
clock = pygame.time.Clock()

# Generate target points for Spider-Man silhouette (head shape + distinctive eyes + chest suit)
targets = []
colors = []

cx, cy = WIDTH // 2, HEIGHT // 2
num_particles = 8000

for i in range(num_particles):
    zone = random.choices(['head', 'eyes', 'chest', 'scatter'], weights=[50, 15, 25, 10])[0]
    
    if zone == 'head':
        u = random.uniform(0, 1)
        angle = random.uniform(0, 2 * math.pi)
        dist = 180 * math.sqrt(u)
        tx = cx + math.cos(angle) * dist
        ty = (cy - 30) + math.sin(angle) * dist * 1.25
        color = (255, 30, 50) if random.random() > 0.15 else (20, 20, 25)
    elif zone == 'eyes':
        side = random.choice([-1, 1])
        ex = cx + side * (60 + random.uniform(-30, 30))
        ey = (cy - 40) + random.uniform(-40, 30)
        tx = ex
        ty = ey
        color = (255, 255, 255)
    elif zone == 'chest':
        tx = cx + random.uniform(-180, 180)
        ty = cy + 180 + random.uniform(0, 160)
        color = (25, 30, 50) if random.random() > 0.4 else (30, 130, 255)
    else:
        tx = random.uniform(0, WIDTH)
        ty = random.uniform(0, HEIGHT)
        color = (200, 200, 200)

    targets.append((tx, ty))
    colors.append(color)

class Particle:
    def __init__(self, tx, ty, color):
        self.x = random.uniform(0, WIDTH)
        self.y = random.uniform(0, HEIGHT)
        self.target_x = tx
        self.target_y = ty
        self.vx = random.uniform(-3, 3)
        self.vy = random.uniform(-3, 3)
        self.color = color
        self.size = random.uniform(1.2, 2.5)

    def update(self, state, mouse_pos):
        if state == 'forming':
            dx = self.target_x - self.x
            dy = self.target_y - self.y
            self.x += dx * 0.1 + self.vx * 0.05
            self.y += dy * 0.1 + self.vy * 0.05
            self.vx *= 0.85
            self.vy *= 0.85
        else:
            self.x += self.vx
            self.y += self.vy
            if self.x < 0 or self.x > WIDTH: self.vx *= -1
            if self.y < 0 or self.y > HEIGHT: self.vy *= -1

        # Mouse repulsion
        mdx = mouse_pos[0] - self.x
        mdy = mouse_pos[1] - self.y
        mdist = math.hypot(mdx, mdy)
        if mdist < 100:
            angle = math.atan2(mdy, mdx)
            self.x -= math.cos(angle) * 6
            self.y -= math.sin(angle) * 6

    def draw(self, surface):
        pygame.draw.circle(surface, self.color, (int(self.x), int(self.y)), int(self.size))

particles = [Particle(targets[i][0], targets[i][1], colors[i]) for i in range(num_particles)]

state = 'forming'
running = True

while running:
    mouse_pos = pygame.mouse.get_pos()
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                running = False
            elif event.key == pygame.K_c or event.key == pygame.K_SPACE:
                state = 'scatter' if state == 'forming' else 'forming'
        elif event.type == pygame.MOUSEBUTTONDOWN:
            state = 'scatter' if state == 'forming' else 'forming'

    screen.fill((10, 11, 16))

    for p in particles:
        p.update(state, mouse_pos)
        p.draw(screen)

    font = pygame.font.SysFont("Arial", 16)
    txt = font.render("Click or Press SPACE to scatter/form. ESC to exit.", True, (150, 150, 180))
    screen.blit(txt, (20, HEIGHT - 30))

    pygame.display.flip()
    clock.tick(60)

pygame.quit()
