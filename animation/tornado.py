import colorsys
import math
import random
import time
import turtle

W, H = 1150, 720
HALF_W, HALF_H = W // 2, H // 2
GROUND, TOP = -260, 230

SPANS = [(0, 78), (78, 204), (204, 490), (490, 610)]
FLASHES = [
    (180, 0.6),
    (150, 0.5),
    (260, 0.8),
    (330, 0.6),
    (390, 0.9),
    (450, 0.6),
    (540, 0.4),
]

screen = turtle.Screen()
screen.setup(W, H)
screen.bgcolor("#03030a")
screen.colormode(1.0)
screen.title("Animasi - Tornado")
screen.tracer(0)

t = turtle.Turtle()
t.hideturtle()
t.speed(0)
t.penup()


def clamp(x):
    return max(0.0, min(1.0, x))


def ease(x):
    x = clamp(x)
    return x * x * (3 - 2 * x)


def mix(a, b, k):
    return tuple(p + (q - p) * k for p, q in zip(a, b))


def neon(h, s=0.85, v=1.0):
    return colorsys.hsv_to_rgb(h % 1, s, v)


def stroke(pts, color, width):
    t.pencolor(color)
    t.pensize(width)
    t.goto(*pts[0])
    t.pendown()
    for p in pts[1:]:
        t.goto(*p)
    t.penup()


def flash_at(i):
    fl = 0.0
    for f0, amp in FLASHES:
        age = (i - f0) / 30
        if age >= 0:
            fl = max(fl, amp * math.exp(-age * 8))
    return fl


def sky(fl):
    lit = (0.45, 0.52, 0.95)
    top = mix((0.02, 0.02, 0.07), lit, fl * 0.5)
    low = mix((0.28, 0.09, 0.25), (0.9, 0.85, 1.0), fl * 0.65)
    steps = 65
    step_h = (HALF_H - GROUND + 30) / steps
    for i in range(steps):
        y = HALF_H + 10 - i * step_h
        col = mix(top, low, (i / (steps - 1)) ** 1.6)
        stroke([(-HALF_W - 10, y), (HALF_W + 10, y)], col, int(step_h) + 4)


def ground(fl):
    steps = 12
    step_h = (HALF_H + GROUND + 20) / steps
    for i in range(steps):
        y = GROUND + 8 - i * step_h
        col = mix((0.18, 0.06, 0.13), (0.02, 0.02, 0.04), i / (steps - 1))
        col = mix(col, (0.45, 0.45, 0.65), fl * 0.35)
        stroke([(-HALF_W - 10, y), (HALF_W + 10, y)], col, int(step_h) + 4)


def lightning(cx, fl):
    if fl < 0.35:
        return
    rng = random.Random(int(fl * 1000))
    lx = cx + rng.randint(-260, 260)
    ly = TOP + 30
    pts = [(lx, ly)]
    while ly > GROUND + 20:
        lx += rng.randint(-28, 28)
        ly -= rng.randint(25, 45)
        pts.append((lx, ly))
    stroke(pts, (0.7, 0.8, 1.0), 4)
    stroke(pts, (1.0, 1.0, 1.0), 2)


def clouds(tm, cx, fl, power):
    rng = random.Random(3)
    for i in range(320):
        a = rng.uniform(0, 6.283) + tm * 0.15
        rr = rng.uniform(0, 720)
        x = cx + 0.75 * rr * math.cos(a)
        y = TOP + 125 + rr * 0.14 * math.sin(a) - rr * 0.04
        v = 0.11 * (1 - rr / 720)
        dark = (v * 0.85, v * 0.65, v * 1.5)
        t.goto(x, y)
        lit = mix(dark, (0.65, 0.68, 0.98), fl * 0.65)
        t.dot(rng.randint(70, 145), lit)


def center(u, tm, cx):
    sway = 55 * math.sin(tm * 1.4 + u * 5)
    return cx + sway * u ** 1.2


def ring_pt(x0, y, r, ang):
    c, s = math.cos(ang), math.sin(ang)
    return x0 + r * c, y + r * 0.22 * s


def funnel(tm, extent, power, cx):
    wd = 0.38 + 0.68 * power
    layers = 62
    for k in range(layers):
        u = k / (layers - 1)
        if u < 1 - extent:
            continue
        y = GROUND + u * (TOP - GROUND)
        r = (8 + 115 * u ** 1.9) * wd
        x0 = center(u, tm, cx)
        hue = 0.06 + 0.03 * u
        shift = int(tm * 10 + k)
        for j in range(36):
            if (j + shift) % 3 == 0:
                continue
            ang = 6.283 * (j + 0.5) / 36
            dim = 1.0 if math.sin(ang) < 0 else 0.32
            p = ring_pt(x0, y, r, ang)
            q = ring_pt(x0, y, r, ang + 0.18)
            stroke([p, q], neon(hue, 0.78, dim), 4)


def debris(tm, extent, power, cx):
    if extent <= 0:
        return
    rng = random.Random(4)
    for i in range(int(220 * power)):
        a0 = rng.uniform(0, 6.283)
        u0, kf = rng.random(), rng.uniform(1.05, 1.85)
        spd = rng.uniform(0.12, 0.32)
        size = rng.randint(3, 6)
        hue = rng.choice([0.08, 0.55, 0.09, 0.12])
        u = 1 - extent + (u0 + tm * spd) % extent
        r = (8 + 115 * u ** 1.9) * kf * (0.38 + 0.68 * power)
        ang = a0 + tm * (5.5 + 4 * (1 - u))
        x = center(u, tm, cx) + r * math.cos(ang)
        y = GROUND + u * (TOP - GROUND) + r * 0.22 * math.sin(ang)
        t.goto(x, y)
        t.dot(size, neon(hue, 0.55))


def dust(tm, cx, power):
    rng = random.Random(6)
    for i in range(int(85 * power)):
        a = rng.uniform(0, 6.283) + tm * 5.5
        rad = 35 + 165 * rng.random()
        t.goto(
            cx + rad * math.cos(a),
            GROUND + 8 + rad * 0.18 * math.sin(a),
        )
        glow = neon(0.05, 0.68, 0.50 * power)
        t.dot(rng.randint(12, 24), glow)


def rain(tm, fl):
    col = mix((0.25, 0.25, 0.45), (0.85, 0.88, 1.0), fl)
    for i in range(130):
        x = (i * 73) % (W + 60) - (HALF_W + 30)
        y = HALF_H + 10 - (tm * 460 + i * 53) % (H + 40)
        stroke([(x, y), (x - 10, y - 22)], col, 1)


def frame(i, extent, power, cx):
    tm = i / 30
    fl = flash_at(i)
    t.clear()
    sky(fl)
    lightning(cx, fl)
    ground(fl)
    clouds(tm, cx, fl, power)
    dust(tm, cx, power)
    funnel(tm, extent, power, cx)
    debris(tm, extent, power, cx)
    rain(tm, fl)
    screen.update()


def play(k, motion):
    a, b = SPANS[k]
    for i in range(a, b):
        u = (i - a) / (b - a - 1)
        extent, power, cx = motion(u)
        frame(i, extent, power, cx)
        time.sleep(0.01)


def gather():
    play(0, lambda u: (0, 0.1 + 0.2 * u, -220))


def touchdown():
    play(1, lambda u: (ease(u), 0.3 + 0.5 * u, -220 + 30 * u))


def rage():
    play(2, lambda u: (1, 0.85 + 0.15 * math.sin(u * 9), -190 + 440 * u))


def dissipate():
    play(3, lambda u: (1 - 0.7 * u, 1 - u, 250 + 90 * u))


gather()
touchdown()
rage()
dissipate()
turtle.done()
