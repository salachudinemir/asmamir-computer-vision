from turtle import Screen, Turtle, clear, color, done, goto, ht, pd, pu

screen = Screen()
screen.bgcolor("black")
screen.setup(800, 800)

t = [Turtle(), Turtle()]
c = [1, 2]

colors = ["darkorange", "#256003", "#00FF80", "red"]


def start_animation():
    screen.tracer(20)

    for turtle_obj in t:
        turtle_obj.clear()
        turtle_obj.reset()
        turtle_obj.ht()
        turtle_obj.width(3)
        turtle_obj.up()
        turtle_obj.goto(30, 0)
        turtle_obj.seth(120 * c[t.index(turtle_obj)])
        turtle_obj.seth(0)

    clear()
    ht()

    for col in colors:
        t[0].color(col)
        t[1].color(col)
        color(col)

        for i in range(361):
            for j in range(2):
                t[j].fd(1)
                t[j].lt(1)

            pu()
            goto(t[1].pos())
            t[1].lt(c[1] * 2)
            t[1].lt(1)
            t[1].lt(1)
            pd()
            goto(t[1].pos())

    screen.tracer(True)


def restart():
    screen.clear()
    screen.bgcolor("black")

    global t
    t = [Turtle(), Turtle()]

    start_animation()


screen.listen()
screen.onkey(restart, "r")
screen.onkey(restart, "R")

start_animation()
done()
