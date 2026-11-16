from turtle import (
    Terminator,
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
import tkinter

speed(0)
bgcolor("black")
setpos(-4, -2)
color('aqua')
tracer(3, 0)
hideturtle()

try:
    for i in range(500):
        rt(i)
        circle(150, i)
        fd(70)
        right(210)
        fd(i)
        lt(1)

    done()
except (Terminator, tkinter.TclError):
    pass