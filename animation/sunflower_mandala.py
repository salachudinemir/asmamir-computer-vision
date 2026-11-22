import math
import time
import turtle

screen = turtle.Screen()
screen.setup(700, 700)
screen.bgcolor("black")
screen.title("Animasi - Sunflower Mandala")
screen.tracer(0)

t = turtle.Turtle()
t.hideturtle()
t.speed(0)

# --- (drawing code) ---
golden_angle = 137.50776405003785
num_petals = 180

for i in range(num_petals):
    angle = i * golden_angle
    radius = 12 + 1.15 * math.sqrt(i) * 10
    rad = math.radians(angle)

    x = radius * math.cos(rad)
    y = radius * math.sin(rad)

    # Gradasi warna emas hangat dari kuning terang ke jingga keemasan
    ratio = i / num_petals
    r = 1.0
    g = max(0.32, 0.88 - 0.50 * ratio)
    b = max(0.0, 0.18 * (1.0 - ratio))
    hex_color = f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"

    petal_size = 18 + 0.24 * i
    t.penup()
    t.goto(x, y)
    t.setheading(angle)
    t.pencolor(hex_color)
    t.pensize(1)  # <-- DIPERBAIKI: diubah dari 1.4 (float) menjadi 1 (int)
    t.pendown()

    # Menggambar kelopak/lingkaran berlapis yang membentuk pola mandala bunga matahari
    for _ in range(2):
        t.circle(petal_size, 180)
        t.left(60)

    if i % 1 == 0:
        screen.update()
        time.sleep(0.04)

screen.update()
turtle.done()
