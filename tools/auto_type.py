"""Line-at-a-time (or optional per-char) typing for coding time-lapse videos.

Uses tools/click_sound.py so ketik.mp3 plays reliably while pasting.

After typing into the focused editor:
  1. SAVE — write the demo source to tools/animasi.py on disk (Python I/O).
     No VS Code Save As dialog, so the RUN command cannot leak into a filename.
  2. RUN  — focus the terminal (Ctrl+`), type only `python tools/animasi.py`, Enter.

Pass --no-run to skip save/terminal/run.
Pass --save-as to also drive the Save As dialog (filename = animasi.py only).
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pyautogui
import pyperclip

from click_sound import prepare, play

# SAVE target (disk + optional dialog). Never include the `python ` prefix here.
SAVE_BASENAME = "animasi.py"
TARGET_REL = f"tools/{SAVE_BASENAME}"
TARGET_PATH = Path(__file__).resolve().parent / SAVE_BASENAME

# RUN command — typed only into the terminal, never into a Save As filename field.
RUN_CMD = f"python {TARGET_REL}"

# Dialog / focus waits (seconds). Keep these longer than a typical Save As close.
WAIT_SAVE_AS_OPEN = 1.2
WAIT_SAVE_AS_AFTER_NAME = 0.35
WAIT_SAVE_AS_AFTER_ENTER = 1.0
WAIT_SAVE_AS_OVERWRITE = 0.6
WAIT_AFTER_DISK_WRITE = 0.4
WAIT_TERMINAL_FOCUS = 0.8
WAIT_BEFORE_RUN = 0.5

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
    """Type a shell command into the already-focused terminal. Never used for Save As."""
    if per_char:
        for ch in command:
            paste_text(ch, click=True)
            time.sleep(pause)
    else:
        paste_text(command, click=False)
        time.sleep(pause)
    pyautogui.press("enter")
    play()


def write_target_to_disk(source: str) -> Path:
    """SAVE step (primary): persist source to TARGET_PATH via Python I/O."""
    TARGET_PATH.parent.mkdir(parents=True, exist_ok=True)
    TARGET_PATH.write_text(source, encoding="utf-8", newline="\n")
    time.sleep(WAIT_AFTER_DISK_WRITE)
    return TARGET_PATH


def save_as_dialog(basename: str = SAVE_BASENAME) -> None:
    """Optional SAVE UX for video: Save As with ONLY the basename (no `python `).

    Clears the filename field before pasting so a leftover path/command cannot stick.
    Waits long enough for the dialog to close before the caller may open a terminal.
    """
    # Ctrl+Shift+S always opens Save As (unlike Ctrl+S on a named buffer).
    pyautogui.hotkey("ctrl", "shift", "s")
    time.sleep(WAIT_SAVE_AS_OPEN)

    # Clear whatever the dialog pre-filled (Untitled-1, previous path, etc.).
    pyautogui.hotkey("ctrl", "a")
    time.sleep(0.1)
    pyautogui.press("backspace")
    time.sleep(0.1)

    # Filename only — never RUN_CMD / never a `python ` prefix.
    paste_text(basename, click=False)
    time.sleep(WAIT_SAVE_AS_AFTER_NAME)
    pyautogui.press("enter")
    time.sleep(WAIT_SAVE_AS_AFTER_ENTER)

    # Confirm overwrite when tools/animasi.py (or basename) already exists.
    pyautogui.press("enter")
    time.sleep(WAIT_SAVE_AS_OVERWRITE)


def run_in_terminal(per_char: bool, pause: float) -> None:
    """RUN step: focus VS Code terminal and type ONLY RUN_CMD (after SAVE finished)."""
    time.sleep(WAIT_BEFORE_RUN)
    pyautogui.hotkey("ctrl", "`")
    time.sleep(WAIT_TERMINAL_FOCUS)
    type_command(RUN_CMD, per_char=per_char, pause=pause)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Type demo code into the focused editor with click sounds, "
        "then SAVE to disk and RUN in the VS Code terminal (unless --no-run)."
    )
    parser.add_argument(
        "--per-char",
        action="store_true",
        help="Paste one character at a time instead of whole lines (slower).",
    )
    parser.add_argument(
        "--pause",
        type=float,
        default=None,
        help=(
            "Sleep seconds after each paste. "
            "Default 0.05 with --per-char, else 0.12 (line mode)."
        ),
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
        help=f"Typing only: skip SAVE / terminal / {RUN_CMD}.",
    )
    parser.add_argument(
        "--save-as",
        action="store_true",
        help=(
            f"Also drive VS Code Save As after the disk write; "
            f"filename field is cleared then filled with only {SAVE_BASENAME}."
        ),
    )
    args = parser.parse_args()
    if args.pause is None:
        # Early slower per-char cadence (~0.05); line mode stays moderate.
        args.pause = 0.05 if args.per_char else 0.12

    try:
        prepare()
    except Exception:
        return 1

    if args.no_run:
        run_hint = "typing only (--no-run)"
    else:
        save_hint = "disk write"
        if args.save_as:
            save_hint += f" + Save As ({SAVE_BASENAME})"
        run_hint = f"then SAVE ({save_hint}) then RUN ({RUN_CMD})"

    print(
        f"Ready. Focus the editor tab in {args.countdown:.0f}s "
        f"(mode={'per-char' if args.per_char else 'line'}; {run_hint})."
    )
    time.sleep(args.countdown)

    type_lines(kode_turtle, per_char=args.per_char, pause=args.pause)

    if args.no_run:
        print("Done (typing only).")
        return 0

    # --- SAVE (must finish before any terminal typing) ---
    saved = write_target_to_disk(kode_turtle)
    print(f"Saved to disk: {saved}")

    if args.save_as:
        save_as_dialog(SAVE_BASENAME)
        print(f"Save As dialog: {SAVE_BASENAME}")

    # --- RUN (terminal only; never touches Save As) ---
    run_in_terminal(per_char=args.per_char, pause=args.pause)
    print(f"Done. Ran: {RUN_CMD}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
