"""Line-at-a-time (or optional per-char) typing for coding time-lapse videos.

Uses tools/click_sound.py so ketik.wav plays reliably while pasting.
Focus an empty editor tab within the countdown before input starts.
"""
from __future__ import annotations

import argparse
import sys
import time

import pyautogui
import pyperclip

from click_sound import prepare, play

kode_turtle = """from turtle import *

speed(0)
bgcolor("black")
setpos(-4, -2)
color('aqua')
tracer(3, 0)
hideturtle()

for i in range(500):
    rt(i)
    circle(150, i)
    fd(70)
    right(210)
    fd(i)
    lt(1)

done()
"""


def paste_text(text: str) -> None:
    pyperclip.copy(text)
    pyautogui.hotkey("ctrl", "v")
    play()


def type_lines(source: str, per_char: bool, pause: float) -> None:
    for baris in source.splitlines():
        teks = baris.lstrip()
        if teks == "done()":
            pyautogui.press("backspace")
        if teks:
            if per_char:
                for ch in teks:
                    paste_text(ch)
                    time.sleep(pause)
            else:
                paste_text(teks)
                time.sleep(pause)
        pyautogui.press("esc")
        pyautogui.press("enter")
        play()


def type_command(command: str, per_char: bool, pause: float) -> None:
    if per_char:
        for ch in command:
            paste_text(ch)
            time.sleep(pause)
    else:
        paste_text(command)
        time.sleep(pause)
    pyautogui.press("enter")
    play()


def main() -> int:
    parser = argparse.ArgumentParser(description="Type demo code into the focused editor with click sounds.")
    parser.add_argument(
        "--per-char",
        action="store_true",
        help="Paste one character at a time instead of whole lines (slower).",
    )
    parser.add_argument(
        "--pause",
        type=float,
        default=0.01,
        help="Sleep seconds after each paste (default 0.01).",
    )
    parser.add_argument(
        "--countdown",
        type=float,
        default=3.0,
        help="Seconds to switch focus to an empty editor tab (default 3).",
    )
    parser.add_argument(
        "--no-run",
        action="store_true",
        help="Skip Ctrl+S / terminal / python tools/animasi.py after typing.",
    )
    args = parser.parse_args()

    try:
        prepare()
    except Exception:
        return 1

    print(
        f"Ready. Focus an empty editor tab in {args.countdown:.0f}s "
        f"(mode={'per-char' if args.per_char else 'line'})."
    )
    time.sleep(args.countdown)

    type_lines(kode_turtle, per_char=args.per_char, pause=args.pause)

    if args.no_run:
        print("Done (typing only).")
        return 0

    time.sleep(0.02)
    pyautogui.hotkey("ctrl", "s")
    time.sleep(0.02)
    pyautogui.hotkey("ctrl", "`")
    time.sleep(0.5)
    type_command("python tools/animasi.py", per_char=args.per_char, pause=args.pause)
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
