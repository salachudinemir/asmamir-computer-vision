"""Line-at-a-time (or optional per-char) typing for coding time-lapse videos.

Uses tools/click_sound.py so ketik.mp3 plays reliably while pasting.

Indent rule: paste each source line verbatim (leading spaces kept). Never lstrip.
After Enter, Shift+Tab outdent N times (N matches expected auto-indent) so the next
paste is not shifted right. Never Home / Shift+Home / clear-line — those wipe upward.

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
# Brief settle after Shift+Tab outdent before the next clipboard paste.
WAIT_AFTER_DEDENT = 0.03
# VS Code / Python editor tab width used to convert leading spaces → Shift+Tab count.
TAB_SIZE = 4

kode_turtle = """import pygame
import cv2
import numpy as np
import os
import random

pygame.init()
MAX_WIDTH = 1000
MAX_HEIGHT = 750
MAX_POINTS = 600000
STEP = 1
CONTRAST = 1.45
GAMMA = 1.75
JITTER = 0.45
BG_COLOR = (248, 246, 240)
DOT_COLOR = (12, 12, 12)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGE_PATH = os.path.join(BASE_DIR, "monalisa.jpg")
# Reveal order: "waterfall" = top-to-bottom (y then x); "shuffle" = random
FILL_MODE = "shuffle"

def load_and_prepare_image(path):
    img = cv2.imread(path) if os.path.exists(path) else None
    if img is None:
        w, h = MAX_WIDTH, MAX_HEIGHT
        canvas = np.full((h, w), 200, dtype=np.uint8)
        cv2.putText(
            canvas,
            "MONALISA",
            (w // 2 - 200, h // 2),
            cv2.FONT_HERSHEY_SIMPLEX,
            2,
            (255, 255, 255),
            3,
        )
        return canvas, w, h

    ih, iw = img.shape[:2]
    scale = min(MAX_WIDTH / iw, MAX_HEIGHT / ih)
    nw = max(1, int(round(iw * scale)))
    nh = max(1, int(round(ih * scale)))
    resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
    return gray, nw, nh

def prepare_darkness_map(gray):
    g = gray.astype(np.float32) / 255.0
    g = np.clip((g - 0.5) * CONTRAST + 0.5, 0.0, 1.0)
    darkness = np.power(1.0 - g, GAMMA)
    return darkness

gray_img, W, H = load_and_prepare_image(IMAGE_PATH)
screen = pygame.display.set_mode((W, H))
pygame.display.set_caption("Monalisa - Stippling Particle Art")
clock = pygame.time.Clock()

darkness = prepare_darkness_map(gray_img)

points = []
print("Generating stippling points...")
h, w = gray_img.shape
for y in range(0, h, STEP):
    for x in range(0, w, STEP):
        if random.random() < float(darkness[y, x]):
            points.append(
                (
                    x + random.uniform(-JITTER, JITTER),
                    y + random.uniform(-JITTER, JITTER),
                )
            )

if len(points) > MAX_POINTS:
    random.shuffle(points)
    points = points[:MAX_POINTS]

if FILL_MODE == "waterfall":
    points.sort(key=lambda p: (p[1], p[0]))
else:
    random.shuffle(points)

print(f"Ready: {len(points)} points (step={STEP}, gamma={GAMMA}, contrast={CONTRAST}, size={W}x{H})")

current_count = 0
batch_size = 1000
running = True

while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                running = False
            elif event.key == pygame.K_r:
                current_count = 0

    screen.fill(BG_COLOR)

    if current_count < len(points):
        current_count = min(len(points), current_count + batch_size)

    # Draw points (black ink on light paper)
    for i in range(current_count):
        pt = points[i]
        screen.set_at((int(pt[0]), int(pt[1])), DOT_COLOR)

    pygame.display.flip()
    clock.tick(45)

pygame.quit()
"""


def paste_text(text: str, click: bool = True) -> None:
    pyperclip.copy(text)
    pyautogui.hotkey("ctrl", "v")
    if click:
        play()


def leading_indent_levels(line: str, tab_size: int = TAB_SIZE) -> int:
    """Count leading indent as whole tab-stop levels (spaces and tabs)."""
    width = 0
    for ch in line:
        if ch == " ":
            width += 1
        elif ch == "\t":
            width = (width // tab_size + 1) * tab_size
        else:
            break
    if width <= 0:
        return 0
    return (width + tab_size - 1) // tab_size


def clear_editor_auto_indent(levels: int) -> None:
    """Cancel VS Code auto-indent via Shift+Tab only so the next paste keeps source spaces.

    After Enter, the editor inserts leading whitespace. Without outdenting it, pasting a
    line that already has its own indent stacks and drifts right every def/block.

    Do NOT use Home / Shift+End / Shift+Home / Backspace: from column 0, Shift+Home
    selects the previous line and Backspace deletes code upward.
    Extra Shift+Tab at column 0 is a no-op in VS Code.
    """
    if levels > 0:
        pyautogui.press("esc")
        for _ in range(levels):
            pyautogui.hotkey("shift", "tab")
    time.sleep(WAIT_AFTER_DEDENT)


def type_lines(source: str, per_char: bool, pause: float, chunk_size: int = 32) -> None:
    import textwrap

    clean_source = textwrap.dedent(source).lstrip("\n")
    for baris in clean_source.splitlines():
        raw_lstrip = baris.lstrip(" ")
        is_top_level = len(baris) == len(raw_lstrip)
        teks = raw_lstrip

        if teks == "done()":
            pyautogui.press("backspace")

        if is_top_level:
            pyautogui.press("home")

        if teks:
            if per_char:
                step = max(1, chunk_size)
                for i in range(0, len(teks), step):
                    pyperclip.copy(teks[i : i + step])
                    pyautogui.hotkey("ctrl", "v")
                    if pause > 0:
                        time.sleep(pause)
            else:
                pyperclip.copy(teks)
                pyautogui.hotkey("ctrl", "v")
                if pause > 0:
                    time.sleep(pause)
            play()

        pyautogui.press("enter")

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
        help="Paste characters incrementally instead of whole lines.",
    )
    parser.add_argument(
        "--chunk",
        type=int,
        default=32,
        help="Characters pasted per step in --per-char mode (larger = faster).",
    )
    parser.add_argument(
        "--pause",
        type=float,
        default=None,
        help="Sleep seconds after each paste (default 0).",
    )
    parser.add_argument(
        "--countdown",
        type=float,
        default=5.0,
        help="Seconds to switch focus to the editor tab that will receive code (default 5.0).",
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
        args.pause = 0.0
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
