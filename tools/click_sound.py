"""Reliable mechanical click for typing / scroll time-lapse scripts.

Plays tools/ketik.mp3 (absolute path next to this file) via pygame.mixer.
Volume is kept low and plays are throttled so rapid callers stay calm.
"""
from __future__ import annotations

import threading
import time
from pathlib import Path

FOLDER = Path(__file__).resolve().parent
MP3_PATH = FOLDER / "ketik.mp3"

# Calm defaults: soft volume, no overlapping burst.
CLICK_VOLUME = 0.32
MIN_PLAY_INTERVAL_S = 0.10

_ready = False
_lock = threading.Lock()
_mixer_ready = False
_sound = None
_last_play_mono = 0.0


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
        # Few channels: throttle already limits rate; avoid stacked chaos.
        pygame.mixer.set_num_channels(4)
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


def _load_sound(abs_path: str):
    """Load mp3 and apply the calm volume."""
    import pygame

    sound = pygame.mixer.Sound(abs_path)
    sound.set_volume(CLICK_VOLUME)
    return sound


def verify(path: Path | None = None) -> Path:
    """Require the mp3 and load it into pygame.mixer. Raises RuntimeError on failure."""
    global _ready, _sound
    mp3 = require_mp3(path)
    abs_path = str(mp3)
    try:
        _init_mixer()
        sound = _load_sound(abs_path)
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
    """Play one click asynchronously, throttled to MIN_PLAY_INTERVAL_S."""
    global _sound, _last_play_mono

    def _run() -> None:
        global _sound, _last_play_mono
        try:
            _init_mixer()

            with _lock:
                now = time.monotonic()
                if now - _last_play_mono < MIN_PLAY_INTERVAL_S:
                    return
                sound = _sound
                if sound is None or path is not None:
                    mp3 = require_mp3(path)
                    sound = _load_sound(str(mp3))
                    if path is None:
                        _sound = sound
                else:
                    sound.set_volume(CLICK_VOLUME)
                _last_play_mono = now
                sound.play()
        except Exception:
            pass

    threading.Thread(target=_run, daemon=True).start()


def prepare() -> Path:
    """Verify mp3 before a typer starts. Prints a clear error and re-raises."""
    try:
        mp3 = verify()
        print(
            f"Click sound ready: {mp3} "
            f"(volume={CLICK_VOLUME}, min_interval={MIN_PLAY_INTERVAL_S}s)"
        )
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
