from turtle import (
    bgcolor,
    circle,
    color,
    done,
    fd,
    hideturtle,
    lt,
    right,
    rt,
    setpos,
    speed,
    tracer,
)

speed(0)
bgcolor("black")
setpos(-4, -2)
color('aqua')
tracer(3, 0)
hideturtle()

for i in range(500):
    rt(i)
    circle(150, i)
    fd(70)
    right(210)
    fd(i)
    lt(1)

done()