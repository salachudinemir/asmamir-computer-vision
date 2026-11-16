import cv2
import numpy as np
import math
import time

def main():
    WIDTH, HEIGHT = 900, 950
    fps = 30
    words = ["love", "passion", "bloom", "eternity", "grace", "beauty", "rose"]
    print("Menjalankan ASCII Rose Art (rose_art.py)...")
    start_time = time.time()
    while True:
        canvas = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
        elapsed = time.time() - start_time
        t = elapsed * 0.8
        center_x, center_y = WIDTH // 2, HEIGHT // 2 + 80
        
        np.random.seed(42)
        for i in range(120):
            sx = int((math.sin(i * 17.3 + t * 0.4) * 0.5 + 0.5) * WIDTH)
            sy = int((math.cos(i * 11.1 + t * 0.3) * 0.5 + 0.5) * HEIGHT)
            twinkle = int((math.sin(t * 5 + i) + 1) * 100 + 55)
            cv2.circle(canvas, (sx, sy), 1, (twinkle, twinkle, twinkle), -1)

        stem_height = 320.0
        growth_stem = min(1.0, max(0.0, t / 4.0))
        current_stem_h = stem_height * growth_stem
        
        for y_offset in range(0, int(current_stem_h), 12):
            cy_pos = center_y + 120 - y_offset
            sway_offset = int(math.sin(t * 2 + y_offset * 0.02) * 4 * (y_offset / stem_height))
            cx_pos = center_x + sway_offset
            char = "|" if y_offset % 24 == 0 else "/"
            cv2.putText(canvas, char, (cx_pos - 4, cy_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (50, 200, 50), 1)

        bloom_progress = min(1.0, max(0.0, (t - 3.0) / 4.0))
        scale_rose = 1.0 + bloom_progress * 1.5
        rose_center_y = center_y + 120 - int(current_stem_h) - 40
        
        num_layers = 7
        for layer in range(num_layers):
            radius = int((25 + layer * 18) * scale_rose)
            points_in_layer = 16 + layer * 8
            for p in range(points_in_layer):
                angle = p * (2 * math.pi / points_in_layer) + t * 0.2 + (layer * 0.3)
                r_var = radius * (1.0 + 0.15 * math.sin(angle * 4 + t))
                px = int(center_x + math.cos(angle) * r_var)
                py = int(rose_center_y + math.sin(angle) * r_var * 0.8)
                color = (50, 50, 230 + int(25 * math.sin(t + layer))) if layer > 1 else (40, 180, 40)
                char_to_draw = words[(p + layer) % len(words)] if layer > 2 else "#"
                if 0 <= px < WIDTH and 0 <= py < HEIGHT:
                    cv2.putText(canvas, char_to_draw[0], (px, py), cv2.FONT_HERSHEY_SIMPLEX, 0.35, color, 1)

        cv2.putText(canvas, "@jin_zime - 2026", (25, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180, 255, 180), 1)
        bloom_pct = int(bloom_progress * 100)
        cv2.putText(canvas, f"bloom {bloom_pct:02d}%  |  sway 000.00°", (25, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (120, 180, 120), 1)
        cv2.putText(canvas, "letters 1,351", (25, 85), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (120, 180, 120), 1)
        cv2.putText(canvas, "running - 30 fps", (WIDTH - 180, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (150, 150, 150), 1)

        cv2.imshow("ASCII Rose Growth - rose_art.py", canvas)
        if cv2.waitKey(1000 // fps) & 0xFF == 27:
            break
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
