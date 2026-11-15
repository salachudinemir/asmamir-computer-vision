import argparse
import sys
import cv2
import numpy as np

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--image", required=True, help="Path to input image")
    p.add_argument("--crop", type=int, nargs=4, metavar=("X", "Y", "W", "H"))
    p.add_argument("--seconds", type=float, default=9.0)
    p.add_argument("--out", default="output_reveal.mp4")
    a = p.parse_args()

    img = cv2.imread(a.image)
    if img is None:
        sys.exit(f"Could not open '{a.image}'")

    if a.crop:
        x, y, w, h = a.crop
        img = img[y:y+h, x:x+w]

    # Video Settings
    FPS = 30
    CELL_H, CELL_W = 14, 14
    HEIGHT_PX, COLS = img.shape[:2]
    rows = HEIGHT_PX // CELL_H
    cols = COLS // CELL_W

    n_frames = int(a.seconds * FPS)
    fourcc = cv2.VideoWriter.fourcc(*"mp4v")
    writer = cv2.VideoWriter(a.out, fourcc, FPS, (COLS, HEIGHT_PX))

    # Random per-cell values for the animation simulation
    rng = np.random.default_rng(7)
    yy, xx = np.mgrid[0:rows, 0:cols].astype(np.float32)
    
    REVEAL_START = 1.0
    REVEAL_DUR = 4.0
    base = REVEAL_DUR + rng.random((rows, cols)) * 0.7
    T_REVEAL = REVEAL_START + base
    speed = rng.uniform(14, 34, (rows, cols))
    trail = rng.integers(10, 28, (rows, cols)).astype(np.float32)
    off = rng.uniform(0, rows + 30, (rows, cols))

    grid_h, grid_w = rows * CELL_H, cols * CELL_W
    src = img[:grid_h, :grid_w]
    period = rows + trail

    for f in range(n_frames):
        t = f / FPS
        frame = np.zeros((HEIGHT_PX, COLS, 3), dtype=np.uint8)
        head = (t * speed + off) % period
        revealed = t >= T_REVEAL
        # Green trail above each head until that cell's reveal time.
        dist = (head - yy) % period
        raining = (~revealed) & (dist < trail)
        rain = np.repeat(np.repeat(raining, CELL_H, axis=0), CELL_W, axis=1)
        glow = (1.0 - dist / np.maximum(trail, 1.0)).clip(0, 1)
        green = np.repeat(np.repeat((40 + 180 * glow).astype(np.uint8), CELL_H, axis=0), CELL_W, axis=1)
        view = frame[:grid_h, :grid_w]
        view[rain, 1] = green[rain]
        shown = np.repeat(np.repeat(revealed, CELL_H, axis=0), CELL_W, axis=1)
        view[shown] = src[shown]
        writer.write(frame)

    writer.release()
    print(f"Video berhasil disimpan ke {a.out}")

if __name__ == "__main__":
    main()