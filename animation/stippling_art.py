import pygame
import cv2
import numpy as np
import os
import random

pygame.init()
W, H = 1000, 750
screen = pygame.display.set_mode((W, H))
pygame.display.set_caption("Stippling Particle Art Generator")
clock = pygame.time.Clock()

BG_COLOR = (0, 0, 0)
MAX_POINTS = 150000
IMAGE_NAME = "monalisa.jpg"
# Reveal order: "waterfall" = top-to-bottom (y then x); "shuffle" = random
FILL_MODE = "waterfall"

def load_and_prepare_image(path):
    if os.path.exists(path):
        img = cv2.imread(path)
        img = cv2.resize(img, (W, H))
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return gray
    else:
        # Fallback placeholder if image not found
        gray = np.zeros((H, W), dtype=np.uint8)
        cv2.putText(gray, "MONALISA", (W//2 - 200, H//2), cv2.FONT_HERSHEY_SIMPLEX, 2, (255, 255, 255), 3)
        return gray

gray_img = load_and_prepare_image(IMAGE_NAME)

# Generate stippling points based on pixel darkness (rejection sampling / weighted distribution)
points = []
print("Generating stippling points...")
h, w = gray_img.shape
for y in range(0, h, 3):
    for x in range(0, w, 3):
        # Darkness probability (inverted gray)
        val = 255 - gray_img[y, x]
        if random.randint(0, 255) < val:
            points.append((x + random.uniform(-1.5, 1.5), y + random.uniform(-1.5, 1.5)))

# Subsample first so density stays image-wide; then order the reveal.
if len(points) > MAX_POINTS:
    random.shuffle(points)
    points = points[:MAX_POINTS]

if FILL_MODE == "waterfall":
    points.sort(key=lambda p: (p[1], p[0]))
else:
    random.shuffle(points)

current_count = 0
batch_size = 2000
running = True

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

    # Draw points
    for i in range(current_count):
        pt = points[i]
        screen.set_at((int(pt[0]), int(pt[1])), (220, 220, 220))

    # UI overlay info
    font = pygame.font.SysFont("Arial", 16)
    txt = font.render(f"Points: {current_count} / {len(points)} | Press 'R' to restart, ESC to exit", True, (150, 150, 150))
    screen.blit(txt, (20, H - 30))

    pygame.display.flip()
    clock.tick(60)

pygame.quit()
