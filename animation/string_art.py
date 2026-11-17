from turtle import Screen, Turtle, bye, done

screen = Screen()
screen.bgcolor("black")
screen.setup(800, 800)

t = [Turtle(), Turtle()]
for t_obj in t:
    t_obj.hideturtle()
    t_obj.speed(0)

colors = ["darkorange", "deepskyblue", "springgreen", "red"]

def start_animation():
    screen.tracer(20)
    for turtle_obj in t:
        turtle_obj.clear()
        turtle_obj.reset()
        turtle_obj.ht()
        turtle_obj.width(2)
        turtle_obj.up()

    for col in colors:
        t[0].color(col)
        t[1].color(col)
        
        for i in range(180):
            t[0].down()
            t[0].forward(5)
            t[0].left(2)
            t[1].down()
            t[1].forward(5)
            t[1].right(2)

    screen.tracer(True)

def restart():
    screen.clear()
    screen.bgcolor("black")
    global t
    t = [Turtle(), Turtle()]
    for t_obj in t:
        t_obj.hideturtle()
        t_obj.speed(0)
    start_animation()

screen.listen()
screen.onkey(restart, "r")
screen.onkey(bye, "Escape")

start_animation()
done()
