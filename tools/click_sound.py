"""Reliable mechanical click for typing / scroll time-lapse scripts.

Resolves ketik.wav next to this file, generates it if missing, and plays via
winsound on a short-lived daemon thread so rapid clicks can overlap instead of
canceling each other (default SND_ASYNC stops the previous sound).
"""
from __future__ import annotations

import math
import random
import struct
import threading
import wave
from pathlib import Path

import winsound

FOLDER = Path(__file__).resolve().parent
WAV_PATH = FOLDER / "ketik.wav"

_SND_FLAGS = (
    winsound.SND_FILENAME
    | winsound.SND_NODEFAULT
)
_ready = False
_lock = threading.Lock()


def ensure_wav(path: Path = WAV_PATH) -> Path:
    """Create a sharp mono 44.1 kHz 16-bit mechanical click if missing."""
    if path.is_file() and path.stat().st_size > 0:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    sr = 44100
    dur = 0.045
    n = int(sr * dur)
    with wave.open(str(path), "w") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(sr)
        for i in range(n):
            t = i / sr
            click = math.sin(2 * math.pi * 2400 * t) * math.exp(-t * 180)
            body = math.sin(2 * math.pi * 380 * t) * math.exp(-t * 55)
            noise = random.uniform(-1, 1) * math.exp(-t * 120)
            sample = max(-1.0, min(1.0, 0.55 * click + 0.25 * body + 0.20 * noise))
            f.writeframes(struct.pack("<h", int(sample * 22000)))
    return path


def verify(path: Path | None = None) -> Path:
    """Ensure the wav exists and PlaySound can open it. Raises RuntimeError on failure."""
    global _ready
    wav = ensure_wav(path or WAV_PATH)
    if not wav.is_file():
        raise RuntimeError(f"Click sound missing and could not be created: {wav}")
    abs_path = str(wav.resolve())
    # Synchronous probe so a bad/unplayable file fails before typing starts.
    try:
        winsound.PlaySound(abs_path, _SND_FLAGS)
    except RuntimeError as exc:
        try:
            winsound.Beep(1000, 40)
        except Exception as beep_exc:
            raise RuntimeError(
                f"Click sound unplayable and Beep also failed: {abs_path} ({beep_exc})"
            ) from beep_exc
        raise RuntimeError(
            f"Click sound unplayable via PlaySound (SND_NODEFAULT): {abs_path} ({exc})"
        ) from exc
    with _lock:
        _ready = True
    return wav.resolve()


def play(path: Path | None = None) -> None:
    """Play one click asynchronously (overlapping-safe via daemon thread)."""
    wav = path or WAV_PATH
    abs_path = str(Path(wav).resolve())

    def _run() -> None:
        try:
            winsound.PlaySound(abs_path, _SND_FLAGS)
        except Exception:
            try:
                winsound.Beep(1200, 25)
            except Exception:
                pass

    threading.Thread(target=_run, daemon=True).start()


def prepare() -> Path:
    """Generate + verify before a typer starts. Prints a clear error and re-raises."""
    try:
        wav = verify()
        print(f"Click sound ready: {wav}")
        return wav
    except Exception as exc:
        print(f"ERROR: keyboard click sound not available: {exc}")
        print(f"Expected wav next to script: {WAV_PATH}")
        raise


if __name__ == "__main__":
    wav = prepare()
    play(wav)
    # Give the daemon thread time to finish the one-shot click.
    threading.Event().wait(0.2)
    print("PlaySound one-shot ok.")
    raise SystemExit(0)
