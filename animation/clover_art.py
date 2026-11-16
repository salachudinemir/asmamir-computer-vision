import cv2
import numpy as np
import math
import time

def main():
    WIDTH, HEIGHT = 900, 900
    fps = 30
    phrases = [
        "Good Luck", "Fortune", "Success", "Prosperity", "Lucky", 
        "Blessing", "Joy", "Hope", "Believe", "Magic", "Dream", "Harmony"
    ]
    print("Menjalankan 3D Clover Art (clover_art.py)...")
    angle = 0.0
    while True:
        canvas = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
        t = time.time()
        angle += 0.025
        num_points = 350
        theta = np.linspace(0, 2 * np.pi, num_points)
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)
        center_x, center_y = WIDTH // 2, HEIGHT // 2
        scale = 220.0
        for i, th in enumerate(theta):
            r = math.cos(2 * th)
            if r < 0:
                continue
            x_local = r * math.cos(th) * scale
            y_local = r * math.sin(th) * scale
            z_local = math.sin(th * 4) * 40.0
            x_rot = x_local * cos_a - z_local * sin_a
            z_rot = x_local * sin_a + z_local * cos_a
            y_rot = y_local
            perspective = 500 / (500 + z_rot)
            screen_x = int(center_x + x_rot * perspective)
            screen_y = int(center_y + y_rot * perspective)
            phrase = phrases[i % len(phrases)]
            intensity = int(160 + 95 * (z_rot / 50.0))
            intensity = max(60, min(255, intensity))
            color = (50, intensity, 50)
            if 0 <= screen_x < WIDTH - 50 and 0 <= screen_y < HEIGHT:
                cv2.putText(canvas, phrase, (screen_x, screen_y), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.32, color, 1)
        sweep_y = int((math.sin(t * 2.5) + 1) / 2 * HEIGHT)
        cv2.line(canvas, (0, sweep_y), (WIDTH, sweep_y), (30, 80, 30), 2)
        cv2.putText(canvas, "Code by @jin_zime - 2026", (25, 35), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180, 255, 180), 1)
        cv2.putText(canvas, "languages 37  |  phrases 360  |  letters 6,338", (25, 60), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (120, 180, 120), 1)
        cv2.putText(canvas, "running - 30 fps", (WIDTH - 180, 35), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (150, 150, 150), 1)
        cv2.imshow("3D Clover Art - clover_art.py", canvas)
        if cv2.waitKey(int(1000 / fps)) & 0xFF == 27:
            break
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
