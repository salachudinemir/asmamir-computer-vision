import tkinter as tk
from math import sin

# Pengaturan jendela (Screen Box)
root = tk.Tk()
root.title("Animasi - Saturn")
root.configure(bg="#05050a")
root.resizable(False, False)

box_frame = tk.Frame(
    root,
    bg="#05050a",
    highlightbackground="#333344",
    highlightthickness=2,
    padx=15,
    pady=15
)
box_frame.pack(padx=20, pady=20)

W_CHARS = 220
H_CHARS = 68

canvas_text = tk.Text(
    box_frame,
    width=W_CHARS,
    height=H_CHARS,
    bg="#05050a",
    fg="white",
    font=("Consolas", 7, "bold"),
    borderwidth=0,
    highlightthickness=0
)
canvas_text.pack()

CHARS = " .:-=+*#%@"
created_tags = set()

# Kecepatan animasi dalam milidetik per baris (semakin besar = semakin lambat)
DELAY_MS = 45

def render_row(y):
    if y >= H_CHARS // 2:
        canvas_text.configure(state="disabled")
        return

    canvas_text.configure(state="normal")
    for x in range(-W_CHARS // 2, W_CHARS // 2):
        a, b = x / 46.0, y / 23.0
        d = 1 - a * a - b * b
        v = (0.97 * b - 0.24 * a) / 0.24
        r = ((0.97 * a + 0.24 * b) ** 2 + v * v) ** 0.5

        ring = (1.32 < r < 2.25) and (abs(r - 1.82) > 0.045)
        light = 0.0

        if ring and (d < 0 or v > 0):
            light = 0.65 + 0.30 * sin(r * 16)
        elif d >= 0:
            band = sin(v * 6.5) * 0.06
            light = 0.25 + 0.72 * (d ** 0.55) - a / 3.5 + band

        if light <= 0.02:
            canvas_text.insert(tk.END, " ")
        else:
            q = int(min(max(light, 0.1), 0.99) * 256)
            i = q * len(CHARS) // 256
            ch = CHARS[i]

            r_col = q
            g_col = int(q * 0.82)
            b_col = int(q * 0.52)
            hex_color = f"#{r_col:02x}{g_col:02x}{b_col:02x}"

            if hex_color not in created_tags:
                canvas_text.tag_configure(hex_color, foreground=hex_color)
                created_tags.add(hex_color)

            canvas_text.insert(tk.END, ch, hex_color)

    canvas_text.insert(tk.END, "\n")
    canvas_text.configure(state="disabled")

    # Lanjut menggambar baris berikutnya setelah jeda DELAY_MS
    root.after(DELAY_MS, lambda: render_row(y + 1))

def start_animation(event=None):
    canvas_text.configure(state="normal")
    canvas_text.delete("1.0", tk.END)
    canvas_text.configure(state="disabled")
    render_row(-H_CHARS // 2)

# Tekan tombol 'R' di keyboard untuk mengulang animasi
root.bind("<r>", start_animation)
root.bind("<R>", start_animation)

start_animation()
root.mainloop()
