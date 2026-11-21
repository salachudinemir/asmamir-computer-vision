"""Reliable mechanical click for typing / scroll time-lapse scripts.

Plays tools/ketik.mp3 (absolute path next to this file) via pygame.mixer so
rapid clicks can overlap. winsound cannot play MP3; wav generation is not used.
"""
from __future__ import annotations

import threading
import time
from pathlib import Path

FOLDER = Path(__file__).resolve().parent
MP3_PATH = FOLDER / "ketik.mp3"

_ready = False
_lock = threading.Lock()
_mixer_ready = False
_sound = None


def _init_mixer() -> None:
    """Initialize pygame.mixer once (quiet import side-effects)."""
    global _mixer_ready
    if _mixer_ready:
        return
    import os

    # Avoid the pygame community hello banner in typer/smoke output.
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    import pygame

    if not pygame.mixer.get_init():
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
        pygame.mixer.set_num_channels(16)
    _mixer_ready = True


def require_mp3(path: Path | None = None) -> Path:
    """Resolve ketik.mp3 next to this module. Raises RuntimeError if missing."""
    mp3 = Path(path) if path is not None else MP3_PATH
    mp3 = mp3.resolve()
    if not mp3.is_file() or mp3.stat().st_size <= 0:
        raise RuntimeError(
            f"Click sound missing: {mp3}. Place ketik.mp3 in the tools folder."
        )
    if mp3.suffix.lower() != ".mp3":
        raise RuntimeError(f"Click sound must be an .mp3 file: {mp3}")
    return mp3


def verify(path: Path | None = None) -> Path:
    """Require the mp3 and load it into pygame.mixer. Raises RuntimeError on failure."""
    global _ready, _sound
    mp3 = require_mp3(path)
    abs_path = str(mp3)
    try:
        _init_mixer()
        import pygame

        sound = pygame.mixer.Sound(abs_path)
        # Synchronous probe so a bad/unplayable file fails before typing starts.
        channel = sound.play()
        if channel is None:
            raise RuntimeError("pygame.mixer returned no free channel")
        # Brief wait so a silent/broken load is more likely to surface.
        time.sleep(0.05)
        with _lock:
            _sound = sound
            _ready = True
    except Exception as exc:
        raise RuntimeError(f"Click sound unplayable via pygame.mixer: {abs_path} ({exc})") from exc
    return mp3


def play(path: Path | None = None) -> None:
    """Play one click asynchronously (overlapping-safe via mixer channels)."""
    global _sound

    def _run() -> None:
        global _sound
        try:
            _init_mixer()
            import pygame

            with _lock:
                sound = _sound
            if sound is None or path is not None:
                mp3 = require_mp3(path)
                sound = pygame.mixer.Sound(str(mp3))
                if path is None:
                    with _lock:
                        _sound = sound
            sound.play()
        except Exception:
            pass

    threading.Thread(target=_run, daemon=True).start()


def prepare() -> Path:
    """Verify mp3 before a typer starts. Prints a clear error and re-raises."""
    try:
        mp3 = verify()
        print(f"Click sound ready: {mp3}")
        return mp3
    except Exception as exc:
        print(f"ERROR: keyboard click sound not available: {exc}")
        print(f"Expected mp3 next to script: {MP3_PATH.resolve()}")
        raise


if __name__ == "__main__":
    mp3 = prepare()
    play(mp3)
    # Give the daemon thread / mixer time to finish the one-shot click.
    threading.Event().wait(0.4)
    print("pygame.mixer one-shot ok.")
    raise SystemExit(0)
