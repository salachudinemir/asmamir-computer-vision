import tkinter as tk
from datetime import datetime

DIGITS = {
    '0': ["#####", "#   #", "#   #", "#   #", "#####"],
    '1': ["  #  ", " ##  ", "  #  ", "  #  ", "#####"],
    '2': ["#####", "    #", "#####", "#    ", "#####"],
    '3': ["#####", "    #", "#####", "    #", "#####"],
    '4': ["#   #", "#   #", "#####", "    #", "    #"],
    '5': ["#####", "#    ", "#####", "    #", "#####"],
    '6': ["#####", "#    ", "#####", "#   #", "#####"],
    '7': ["#####", "    #", "  #  ", "  #  ", "  #  "],
    '8': ["#####", "#   #", "#####", "#   #", "#####"],
    '9': ["#####", "#   #", "#####", "    #", "#####"],
    ':': ["     ", "  #  ", "     ", "  #  ", "     "],
}


def generate_number_art(text):
    rows = [""] * 5
    for char in text:
        pattern = DIGITS.get(char, ["?????"] * 5)
        for i in range(5):
            rows[i] += pattern[i] + "  "
    return "\n".join(rows)


def update_clock():
    current_time = datetime.now().strftime("%H:%M:%S")
    ascii_art = generate_number_art(current_time)
    clock_label.config(text=ascii_art)
    # Perbarui otomatis setiap 1000 ms (1 detik) tanpa membekukan layar
    root.after(1000, update_clock)


# Pengaturan jendela (Box Screen)
root = tk.Tk()
root.title("Digital Clock ASCII")
root.configure(bg="#0d1117")
root.resizable(False, False)

# Bingkai kotak (Box) di dalam layar
box_frame = tk.Frame(
    root,
    bg="#161b22",
    highlightbackground="#00ff88",
    highlightthickness=2,
    padx=25,
    pady=20
)
box_frame.pack(padx=30, pady=30)

# Label teks ASCII (wajib font monospace seperti Courier agar sejajar)
clock_label = tk.Label(
    box_frame,
    text="",
    font=("Courier", 14, "bold"),
    fg="#00ff88",
    bg="#161b22",
    justify="left"
)
clock_label.pack()

update_clock()
root.mainloop()
