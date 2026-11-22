import turtle
import colorsys

# Setup screen
screen = turtle.Screen()
screen.bgcolor("black")
screen.title("Rainbow Spiral Art")

# Setup turtle
t = turtle.Turtle()
t.speed(0)
t.width(2)
t.hideturtle()

# Initial hue value
h = 0
# Number of outer loops
num_iterations = 120

# Main loop
for i in range(num_iterations):
    # Calculate color from HSV value
    color = colorsys.hsv_to_rgb(h, 1, 1)
    t.pencolor(color)
    
    # Inner loop to draw a petal-like shape
    for _ in range(5):
        t.forward(i * 2)
        t.right(144)
        
    # Turn for the next petal
    t.right(8)
    # Increment hue for gradient effect
    h += 1 / num_iterations

# Finish up
turtle.done()
