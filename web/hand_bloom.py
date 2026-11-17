"""Red roses on the camera frame Asmamir already captured. No second webcam."""

import math

import cv2


_TIPS = (4, 8, 12, 16, 20)
_STEM = (45, 120, 40)
_LEAF = (50, 150, 55)


def _clamp(value, low, high):
    return max(low, min(high, value))


def _rose(frame, x, y, radius):
    """Layered red petals. Not five dots around a circle."""
    for step in range(10):
        angle = step * 36
        spread = max(3, int(radius * (0.95 - step * 0.04)))
        axes = (max(4, spread // 2 + 2), max(7, int(spread * 0.9)))
        red = 150 + step * 8
        cv2.ellipse(frame, (x, y), axes, angle, 0, 360, (25, 25, min(255, red)), -1)
    for step in range(6):
        angle = 15 + step * 60
        offset = max(2, radius // 5)
        center = (
            int(x + math.cos(math.radians(angle)) * offset),
            int(y + math.sin(math.radians(angle)) * offset),
        )
        axes = (max(3, radius // 3), max(4, radius // 2))
        cv2.ellipse(frame, center, axes, angle, 0, 360, (20, 20, 200), -1)
    cv2.circle(frame, (x, y), max(2, radius // 6), (10, 10, 90), -1)


def _leaf(frame, x, y, radius):
    cv2.ellipse(frame, (x, y), (max(4, radius // 2), max(3, radius // 4)), -40, 0, 360, _LEAF, -1)
    cv2.ellipse(frame, (x, y), (max(4, radius // 2), max(3, radius // 4)), 40, 0, 360, _LEAF, -1)


def draw(frame, results):
    """Pinch distance grows a green stem and a red rose on each fingertip."""
    height, width = frame.shape[:2]
    hands = getattr(results, "multi_hand_landmarks", None) or []
    lines = []
    for hand in hands[:2]:
        landmarks = hand.landmark
        thumb = landmarks[4]
        index = landmarks[8]
        dist = math.hypot((thumb.x - index.x) * width, (thumb.y - index.y) * height)
        grow = _clamp(dist / 120.0, 0.0, 1.0)
        bloom = _clamp((200.0 - dist) / 150.0, 0.0, 1.0)
        lines.append((grow, bloom))
        for tip in _TIPS:
            x = int(landmarks[tip].x * width)
            y = int(landmarks[tip].y * height)
            stem = int(90 * grow)
            top = y - stem
            cv2.line(frame, (x, y), (x, top), _STEM, 3)
            if grow <= 0.15:
                continue
            radius = int(28 * bloom + 12)
            mid = (x, y - stem // 2)
            _leaf(frame, mid[0] + radius // 3, mid[1], radius)
            _rose(frame, x, top, radius)
    if not lines:
        lines.append((0.0, 0.0))
    for index, (grow, bloom) in enumerate(lines):
        cv2.putText(
            frame,
            f"Grow {grow:.2f}  Bloom {bloom:.2f}",
            (30, 40 + index * 28),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (230, 230, 230),
            2,
        )
