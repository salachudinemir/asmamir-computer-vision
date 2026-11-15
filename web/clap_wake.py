"""Two claps wake Asmamir. The microphone she already uses is enough.

A clap is a short loud spike. Two of them, a little apart, count. A held
voice does not. Nothing here opens a browser, a song, or another app.
"""

import numpy as np

_BLOCK_S = 0.012
_SPIKE = 4.5
_MIN_RMS = 0.012
_GAP_MIN = 0.05
_GAP_MAX = 0.45
_RETRIGGER = 0.55
_FLOOR_ALPHA = 0.992
_QUIET = 2.2
_COOLDOWN = 1.6
_SPEECH_SHARE = 0.35


class ClapWatch:
    """Feed mono float samples in [-1, 1]. `feed` is true once per double clap."""

    def __init__(self):
        self._floor = 1e-4
        self._armed = True
        self._first = None
        self._last = -1e9
        self._clock = 0.0

    def feed(self, samples, rate):
        samples = np.asarray(samples, dtype=np.float32).reshape(-1)
        rate = int(rate)
        if samples.size == 0 or rate <= 0:
            return False
        block = max(1, int(rate * _BLOCK_S))
        levels = []
        for start in range(0, samples.size - block + 1, block):
            chunk = samples[start:start + block].astype(np.float64)
            levels.append(float(np.sqrt(np.mean(chunk * chunk))))
        if not levels:
            return False
        loudest = max(levels)
        floor_now = max(self._floor, 1e-7)
        if loudest < max(floor_now * _SPIKE, _MIN_RMS):
            self._advance_floor(levels)
            self._clock += len(levels) * _BLOCK_S
            return False
        threshold = max(floor_now * _SPIKE, _MIN_RMS)
        if sum(level >= threshold * 0.5 for level in levels) / len(levels) > _SPEECH_SHARE:
            self._first = None
            self._armed = True
            self._advance_floor(levels)
            self._clock += len(levels) * _BLOCK_S
            return False
        hit = False
        for level in levels:
            if self._step(level):
                hit = True
        return hit

    def _advance_floor(self, levels):
        for level in levels:
            if level < self._floor * _QUIET:
                self._floor = _FLOOR_ALPHA * self._floor + (1.0 - _FLOOR_ALPHA) * level
                self._floor = max(self._floor, 1e-7)

    def _step(self, level):
        now = self._clock
        self._clock += _BLOCK_S
        if level < self._floor * _QUIET:
            self._floor = _FLOOR_ALPHA * self._floor + (1.0 - _FLOOR_ALPHA) * level
            self._floor = max(self._floor, 1e-7)
        threshold = max(self._floor * _SPIKE, _MIN_RMS)
        if level < threshold * _RETRIGGER:
            self._armed = True
        if self._first is not None and now - self._first > _GAP_MAX:
            self._first = None
        if not self._armed or level < threshold or now - self._last < _COOLDOWN:
            return False
        self._armed = False
        if self._first is None:
            self._first = now
            return False
        gap = now - self._first
        self._first = None
        if gap < _GAP_MIN:
            self._first = now
            return False
        self._last = now
        return True
