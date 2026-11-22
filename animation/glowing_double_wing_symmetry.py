import turtle

t = turtle.Turtle()
s = turtle.Screen()
s.bgcolor("black")
t.speed(0)
t.width(2)
t.hideturtle()

colors = ["spring green", "cyan", "turquoise", "lime"]

for angle in range(0, 360, 10):
    t.color(colors[(angle // 10) % len(colors)])
    t.penup()
    t.goto(0, 0)
    t.setheading(angle)
    t.pendown()
    for step in range(18):
        t.forward(12)
        t.left(12)

turtle.done()
