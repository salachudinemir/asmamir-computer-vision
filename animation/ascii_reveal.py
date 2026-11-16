import cv2
import numpy as np
import time

def ascii_img(img, aspect):
    h, w = img.shape[:2]
    return cv2.resize(img, (w, h), interpolation=cv2.INTER_AREA)

def prepare(img, cols, rows):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
    return cv2.resize(gray, (cols, rows), interpolation=cv2.INTER_AREA)

def main():
    COLS = 100
    ROWS = 65
    ASCII_CHARS = "@%#*+=-:. "
    img_path = "jimin.jpg"
    img = cv2.imread(img_path)
    if img is None:
        img = np.zeros((500, 500, 3), dtype=np.uint8)
        cv2.putText(img, "JIMIN", (120, 280), cv2.FONT_HERSHEY_SIMPLEX, 3, (255, 255, 255), 5)
    target_gray = prepare(img, COLS, ROWS)
    normalized = target_gray / 255.0
    char_indices = (normalized * (len(ASCII_CHARS) - 1)).astype(int)
    drops = np.random.randint(0, ROWS, COLS)
    speeds = np.random.randint(1, 4, COLS)
    cell_w, cell_h = 10, 16
    canvas_w = COLS * cell_w
    canvas_h = ROWS * cell_h
    print("Menjalankan animasi ASCII Reveal... Tekan 'Esc' pada jendela untuk keluar.")
    while True:
        canvas = np.zeros((canvas_h, canvas_w, 3), dtype=np.uint8)
        for c in range(COLS):
            drops[c] = (drops[c] + speeds[c]) % ROWS
        for r in range(ROWS):
            for c in range(COLS):
                if r <= drops[c]:
                    char = ASCII_CHARS[np.random.randint(0, len(ASCII_CHARS))]
                    color = (0, 255, 0)
                else:
                    char = ASCII_CHARS[char_indices[r, c]]
                    intensity = int(target_gray[r, c])
                    color = (intensity, intensity, intensity)
                cv2.putText(canvas, char, (c * cell_w, (r + 1) * cell_h - 2), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)
        cv2.putText(canvas, "PARK JIMIN 💜", (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (230, 150, 255), 2)
        cv2.imshow("ASCII Reveal Animation", canvas)
        if cv2.waitKey(30) & 0xFF == 27:
            break
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
