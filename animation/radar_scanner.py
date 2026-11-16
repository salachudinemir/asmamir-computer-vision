import pygame
import math
import random

# Initialize Pygame
pygame.init()

WIDTH, HEIGHT = 800, 800
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Radar Scanner")
clock = pygame.time.Clock()

CENTER = (WIDTH // 2, HEIGHT // 2)
RADIUS = 320

DARK_GREEN = (0, 60, 0)
BLACK = (0, 0, 0)

# Generate random target/enemy blips on the radar
enemies = []
for _ in range(5):
    angle = random.uniform(0, 360)
    dist = random.uniform(70, RADIUS - 20)
    x = CENTER[0] + math.cos(math.radians(angle)) * dist
    y = CENTER[1] + math.sin(math.radians(angle)) * dist
    enemies.append((x, y))

enemy_memory = [0] * len(enemies)
radar_angle = 0

running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                running = False

    screen.fill(BLACK)

    # Draw radar concentric circles and crosshairs
    pygame.draw.circle(screen, DARK_GREEN, CENTER, RADIUS, 2)
    pygame.draw.circle(screen, DARK_GREEN, CENTER, RADIUS * 0.75, 1)
    pygame.draw.circle(screen, DARK_GREEN, CENTER, RADIUS * 0.5, 1)
    pygame.draw.circle(screen, DARK_GREEN, CENTER, RADIUS * 0.25, 1)

    pygame.draw.line(screen, DARK_GREEN, (CENTER[0] - RADIUS, CENTER[1]), (CENTER[0] + RADIUS, CENTER[1]), 1)
    pygame.draw.line(screen, DARK_GREEN, (CENTER[0], CENTER[1] - RADIUS), (CENTER[0], CENTER[1] + RADIUS), 1)

    # Draw radar sweep trail (semi-transparent sector)
    sweep_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    for angle_offset in range(45):
        alpha = int((45 - angle_offset) * (120 / 45))
        a1 = math.radians(radar_angle - angle_offset)
        a2 = math.radians(radar_angle - angle_offset - 1)
        
        p1 = CENTER
        p2 = (CENTER[0] + math.cos(a1) * RADIUS, CENTER[1] + math.sin(a1) * RADIUS)
        p3 = (CENTER[0] + math.cos(a2) * RADIUS, CENTER[1] + math.sin(a2) * RADIUS)
        
        pygame.draw.polygon(sweep_surf, (0, 255, 70, alpha), [p1, p2, p3])

    screen.blit(sweep_surf, (0, 0))

    # Outer border circle
    pygame.draw.circle(screen, (0, 255, 70), CENTER, RADIUS, 2)

    # Check for enemy sweep detection
    for i, (ex, ey) in enumerate(enemies):
        enemy_angle = math.degrees(math.atan2(ey - CENTER[1], ex - CENTER[0]))
        if enemy_angle < 0:
            enemy_angle += 360

        diff = abs(radar_angle - enemy_angle)
        if diff < 3:
            enemy_memory[i] = 40  # fade frames

        if enemy_memory[i] > 0:
            # Draw glowing blip
            glow = pygame.Surface((40, 40), pygame.SRCALPHA)
            pygame.draw.circle(glow, (0, 255, 70, int(255 * (enemy_memory[i] / 40))), (20, 20), 8)
            screen.blit(glow, (ex - 20, ey - 20))
            pygame.draw.circle(screen, (255, 255, 255), (int(ex), int(ey)), 4)
            enemy_memory[i] -= 1

    radar_angle = (radar_angle + 2) % 360

    pygame.display.flip()
    clock.tick(60)

pygame.quit()
