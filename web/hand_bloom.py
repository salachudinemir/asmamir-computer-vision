"""Flowers on the camera frame Asmamir already captured. No second webcam."""

import math

import cv2


_TIPS = (4, 8, 12, 16, 20)
_BLUE = (255, 100, 0)


def _clamp(value, low, high):
    return max(low, min(high, value))


def draw(frame, results):
    """Pinch distance grows a stem and a five-petal bloom on each fingertip."""
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
            cv2.line(frame, (x, y), (x, top), _BLUE, 2)
            if grow <= 0.15:
                continue
            radius = int(16 * bloom + 6)
            cv2.circle(frame, (x, top), radius, _BLUE, -1)
            cv2.circle(frame, (x, top), radius, (255, 180, 80), 1)
            petal = max(4, radius // 2)
            reach = radius + 10
            for step in range(5):
                angle = math.radians(step * 72)
                px = int(x + math.cos(angle) * reach)
                py = int(top + math.sin(angle) * reach)
                cv2.circle(frame, (px, py), petal, _BLUE, -1)
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
