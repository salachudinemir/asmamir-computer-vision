import cv2
import numpy as np
import math
import time

def rot_y(pts, angle):
    c, s = math.cos(angle), math.sin(angle)
    R = np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
    return pts @ R.T

def generate_stem_tube(radius, height, segments=16, rings=20):
    pts = []
    for r in range(rings):
        v = r / (rings - 1)
        y = v * height - height / 2
        ring_pts = []
        for s in range(segments):
            u = s / segments
            theta = u * 2 * math.pi
            x = radius * math.cos(theta)
            z = radius * math.sin(theta)
            ring_pts.append((x, y, z))
        pts.append(ring_pts)
    return np.array(pts, dtype=np.float32)

def main():
    WIDTH, HEIGHT = 900, 950
    fps = 30
    print("Menjalankan 3D Lilium Orientalis Simulation (botanical_lily.py)...")
    angle = 0.0
    start_time = time.time()
    while True:
        canvas = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
        elapsed = time.time() - start_time
        angle += 0.015
        center_x, center_y = WIDTH // 2, HEIGHT // 2 + 100
        scale = 320.0
        np.random.seed(42)
        for i in range(40):
            px = int((math.sin(i * 12.3 + elapsed * 0.5) * 0.5 + 0.5) * WIDTH)
            py = int((math.cos(i * 7.1 + elapsed * 0.3) * 0.5 + 0.5) * HEIGHT)
            cv2.circle(canvas, (px, py), 1, (180, 140, 200), -1)

        stem_radius = 8.0
        stem_height = 450.0
        stem_mesh = generate_stem_tube(stem_radius, stem_height, segments=12, rings=25)
        flat_stem = stem_mesh.reshape(-1, 3)
        rotated_stem = rot_y(flat_stem, angle)
        perspective = 600 / (600 + rotated_stem[:, 2])
        proj_x = (center_x + rotated_stem[:, 0] * perspective * (scale / 100)).astype(int)
        proj_y = (center_y - rotated_stem[:, 1] * perspective * (scale / 100)).astype(int)
        rings, segs = stem_mesh.shape[0], stem_mesh.shape[1]
        proj_pts = np.column_stack((proj_x, proj_y)).reshape(rings, segs, 2)
        
        for r in range(rings):
            for s in range(segs):
                pt1 = tuple(proj_pts[r, s])
                pt2 = tuple(proj_pts[r, (s + 1) % segs])
                cv2.line(canvas, pt1, pt2, (40, 100, 60), 1)
                if r < rings - 1:
                    pt3 = tuple(proj_pts[r + 1, s])
                    cv2.line(canvas, pt1, pt3, (40, 100, 60), 1)

        flower_center_y = center_y - int(230 * (scale / 100))
        num_petals = 6
        for p in range(num_petals):
            petal_angle = angle + p * (2 * math.pi / num_petals)
            petal_len = 160.0
            tip_x = center_x + math.sin(petal_angle) * petal_len * 1.2
            tip_y = flower_center_y - math.cos(petal_angle) * petal_len * 0.8 - 40
            base_pt = (center_x, flower_center_y)
            tip_pt = (int(tip_x), int(tip_y))
            cv2.line(canvas, base_pt, tip_pt, (160, 100, 220), 1)
            cv2.ellipse(canvas, (int((base_pt[0]+tip_pt[0])/2), int((base_pt[1]+tip_pt[1])/2)), 
                        (int(petal_len*0.3), int(petal_len*0.5)), int(math.degrees(petal_angle)), 0, 360, (200, 150, 250), 1)

        cv2.putText(canvas, "LILIUM ORIENTALIS", (30, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (220, 220, 240), 2)
        cv2.putText(canvas, "00: BOTANICAL PROCEDURAL RECONSTRUCTION | SPECIMEN NO. 089", (30, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (140, 140, 170), 1)
        cv2.putText(canvas, "STAGE 05 // 3D FLORAL SPLINE BLUEPRINT", (30, HEIGHT - 30), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (160, 160, 190), 1)
        cv2.putText(canvas, "FPS: 30 | MODEL: LILY | RENDER: Wireframe", (WIDTH - 340, HEIGHT - 30), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (120, 120, 150), 1)

        cv2.imshow("Botanical Lily - Lilium Orientalis", canvas)
        if cv2.waitKey(int(1000 / fps)) & 0xFF == 27:
            break
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
