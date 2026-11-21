"""Line-at-a-time (or optional per-char) typing for coding time-lapse videos.

Uses tools/click_sound.py so ketik.mp3 plays reliably while pasting.
After typing, default behavior saves to tools/animasi.py, focuses the
VS Code terminal (Ctrl+`), runs `python tools/animasi.py`, and presses Enter.
Pass --no-run to skip save/terminal/run.
"""
from __future__ import annotations

import argparse
import sys
import time

import pyautogui
import pyperclip

from click_sound import prepare, play

# Typed into the focused editor, then saved here and executed in the terminal.
TARGET_REL = "tools/animasi.py"
RUN_CMD = f"python {TARGET_REL}"

kode_turtle = """from turtle import (
    Terminator,
    bgcolor,
    circle,
    color,
    done,
    fd,
    hideturtle,
    lt,
    right,
    rt,
    setpos,
    speed,
    tracer,
)
import tkinter

speed(0)
bgcolor("black")
setpos(-4, -2)
color('aqua')
tracer(3, 0)
hideturtle()

try:
    for i in range(500):
        rt(i)
        circle(150, i)
        fd(70)
        right(210)
        fd(i)
        lt(1)

    done()
except (Terminator, tkinter.TclError):
    pass
"""


def paste_text(text: str, click: bool = True) -> None:
    pyperclip.copy(text)
    pyautogui.hotkey("ctrl", "v")
    if click:
        play()


def type_lines(source: str, per_char: bool, pause: float) -> None:
    for baris in source.splitlines():
        teks = baris.lstrip()
        if teks == "done()":
            pyautogui.press("backspace")
        if teks:
            if per_char:
                for ch in teks:
                    paste_text(ch, click=True)
                    time.sleep(pause)
            else:
                # Line-paste: one click per line (after Enter), not paste+Enter spam.
                paste_text(teks, click=False)
                time.sleep(pause)
        pyautogui.press("esc")
        pyautogui.press("enter")
        if not per_char:
            play()


def type_command(command: str, per_char: bool, pause: float) -> None:
    if per_char:
        for ch in command:
            paste_text(ch, click=True)
            time.sleep(pause)
    else:
        paste_text(command, click=False)
        time.sleep(pause)
    pyautogui.press("enter")
    play()


def save_to_target() -> None:
    """Save As into TARGET_REL so untitled tabs do not block the run step."""
    # Ctrl+Shift+S always opens Save As (unlike Ctrl+S on a named buffer).
    pyautogui.hotkey("ctrl", "shift", "s")
    time.sleep(0.6)
    paste_text(TARGET_REL, click=False)
    time.sleep(0.15)
    pyautogui.press("enter")
    time.sleep(0.4)
    # Confirm overwrite when tools/animasi.py already exists.
    pyautogui.press("enter")
    time.sleep(0.35)


def run_in_terminal(per_char: bool, pause: float) -> None:
    """Focus VS Code terminal and run RUN_CMD."""
    pyautogui.hotkey("ctrl", "`")
    time.sleep(0.5)
    type_command(RUN_CMD, per_char=per_char, pause=pause)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Type demo code into the focused editor with click sounds, "
        "then save and run it in the VS Code terminal (unless --no-run)."
    )
    parser.add_argument(
        "--per-char",
        action="store_true",
        help="Paste one character at a time instead of whole lines (slower).",
    )
    parser.add_argument(
        "--pause",
        type=float,
        default=0.10,
        help="Sleep seconds after each paste (default 0.10; calm cadence).",
    )
    parser.add_argument(
        "--countdown",
        type=float,
        default=3.0,
        help="Seconds to switch focus to the editor tab that will receive code (default 3).",
    )
    parser.add_argument(
        "--no-run",
        action="store_true",
        help=f"Typing only: skip Save As / terminal / {RUN_CMD}.",
    )
    args = parser.parse_args()

    try:
        prepare()
    except Exception:
        return 1

    run_hint = "typing only (--no-run)" if args.no_run else f"then save+run {RUN_CMD}"
    print(
        f"Ready. Focus the editor tab in {args.countdown:.0f}s "
        f"(mode={'per-char' if args.per_char else 'line'}; {run_hint})."
    )
    time.sleep(args.countdown)

    type_lines(kode_turtle, per_char=args.per_char, pause=args.pause)

    if args.no_run:
        print("Done (typing only).")
        return 0

    time.sleep(0.05)
    save_to_target()
    run_in_terminal(per_char=args.per_char, pause=args.pause)
    print(f"Done. Ran: {RUN_CMD}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
