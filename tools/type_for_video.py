"""Paste a source file into Visual Studio Code, then scroll it.

The editor must be an empty untitled file. This script refuses to start
unless you pass --empty-untitled after that file is focused. It copies the
whole source once and pastes it with one Ctrl+V. It does not type characters
and it does not press Enter per line. Then it goes to the top and moves down
one line at a time until the end. It stops if the foreground window is not
Visual Studio Code. The paste waits until the 3 second countdown finishes.

Each paste and each scroll step plays tools/ketik.wav via click_sound.
"""
import ctypes
import sys
import time
from pathlib import Path

import pyautogui
import pyperclip

from click_sound import prepare, play

DEFAULT = Path(__file__).resolve().parent.parent / "animation" / "test_capture.py"
SCROLL_PAUSE = 0.18
EMPTY_FLAG = "--empty-untitled"

pyautogui.PAUSE = 0
pyautogui.FAILSAFE = True


def foreground_title():
    user32 = ctypes.windll.user32
    hwnd = user32.GetForegroundWindow()
    length = user32.GetWindowTextLengthW(hwnd)
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value


def code_is_focused():
    return "Visual Studio Code" in foreground_title()


def set_clipboard(text):
    last_error = None
    for _ in range(8):
        try:
            pyperclip.copy(text)
            return
        except Exception as exc:
            last_error = exc
            time.sleep(0.05)
    raise RuntimeError(f"Clipboard stayed busy: {last_error}")


def require_code(where):
    if code_is_focused():
        return
    print(f"Stopped. Focus left Visual Studio Code {where}.")
    sys.exit(1)


def main():
    args = sys.argv[1:]
    if EMPTY_FLAG not in args:
        print(
            "Refusing to start. The editor must be an empty untitled file. "
            f"Focus Visual Studio Code, then run again with {EMPTY_FLAG}."
        )
        sys.exit(1)
    try:
        prepare()
    except Exception:
        sys.exit(1)
    paths = [arg for arg in args if arg != EMPTY_FLAG]
    source = Path(paths[0]) if paths else DEFAULT
    if not source.is_file():
        print(f"Missing file: {source}")
        sys.exit(1)
    text = source.read_text(encoding="utf-8")
    line_count = len(text.splitlines())
    print("The editor must be an empty untitled file inside Visual Studio Code.")
    for left in range(3, 0, -1):
        print(f"Pasting starts in {left}...")
        time.sleep(1)
    require_code("before the paste")
    set_clipboard(text)
    time.sleep(0.12)
    require_code("before the paste")
    pyautogui.hotkey("ctrl", "v")
    play()
    time.sleep(0.3)
    require_code("before scrolling")
    pyautogui.hotkey("ctrl", "home")
    time.sleep(0.2)
    print(f"Scrolling {source} ({line_count} lines).")
    for index in range(1, line_count):
        require_code(f"at line {index}")
        pyautogui.hotkey("ctrl", "down")
        play()
        time.sleep(SCROLL_PAUSE)
    print("Done.")


if __name__ == "__main__":
    main()
