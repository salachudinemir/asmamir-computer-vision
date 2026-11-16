import turtle as t
import math as m
import random as r
import time

# ------------- SCREEN SETUP -------------
s = t.Screen()
s.setup(900, 750)
s.bgcolor("black")
s.title("Beautiful Thread Heart | Poornas Tech Talk")
s.colormode(1)

t.tracer(0)
t.hideturtle()
t.speed(0)

# ------------- HEART SETTINGS -------------
SCALE = 16
THREADS = 420
SEGMENTS = 12

# Pink gradient color function
def pink_color(f):
    red = 1.0
    green = 0.12 + 0.55 * (1 - f)
    blue = 0.35 + 0.55 * (1 - f)
    return red, green, blue

# ------------- HEART DRAWING -------------
try:
    for i in range(THREADS):

        # Angle around the heart
        a = 2 * m.pi * i / THREADS

        # Mathematical heart outline
        xo = 16 * (m.sin(a) ** 3) * SCALE

        yo = (
            13 * m.cos(a)
            - 5 * m.cos(2 * a)
            - 2 * m.cos(3 * a)
            - m.cos(4 * a)
        ) * SCALE

        # Random thread length
        L = r.uniform(0.15, 0.58)

        # Inner endpoint
        xi = xo * (1 - L)
        yi = yo * (1 - L)

        # Draw each thread in small glowing-looking segments
        for j in range(SEGMENTS):
            f = j / SEGMENTS

            x1 = xo + (xi - xo) * f
            y1 = yo + (yi - yo) * f

            x2 = xo + (xi - xo) * (f + 1 / SEGMENTS)
            y2 = yo + (yi - yo) * (f + 1 / SEGMENTS)

            t.pencolor(pink_color(f))
            t.pensize(round(r.uniform(0.7, 1.5)))

            t.penup()
            t.goto(x1, y1)
            t.pendown()
            t.goto(x2, y2)

        # Show the drawing progressively
        if i % 4 == 0:
            t.update()
            time.sleep(0.1)

    # ------------- FINISH -------------
    t.update()
    t.done()
except t.Terminator:
    pass