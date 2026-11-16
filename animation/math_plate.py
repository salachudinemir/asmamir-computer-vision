import turtle
import math
import tkinter
import time
import random

WIDTH = 950
EXTENT = 440
DELAY = 10
SCALE = 0.88
STEP = 1

PHI = (1 + math.sqrt(5)) / 2
PLATE_R = 372

def circle(r, steps=360):
    return [(r * math.cos(t * math.pi / 180), r * math.sin(t * math.pi / 180)) for t in range(steps + 1)]

def rose(n, d, k=1, amp: float = 300):
    pts = []
    turns = d * math.lcm(n, d) // n if hasattr(math, 'lcm') else d * (n * d // math.gcd(n, d)) // n
    for i in range(turns * n * 360 + 1):
        th = i * math.pi / 180
        r = amp * math.cos(n * th / d) * k
        x = r * math.cos(th)
        y = r * math.sin(th)
        pts.append((x, y))
    return pts

def hypotrochoid(r_fixed, r_moving, d_dist, turns=6):
    pts = []
    for i in range(turns * 360 + 1):
        th = i * math.pi / 180
        x = (r_fixed - r_moving) * math.cos(th) + d_dist * math.cos((r_fixed - r_moving) * th / r_moving)
        y = (r_fixed - r_moving) * math.sin(th) - d_dist * math.sin((r_fixed - r_moving) * th / r_moving)
        pts.append((x * SCALE, y * SCALE))
    return pts

def golden_spiral(r_scale=1.2, turns=8):
    pts = []
    for i in range(turns * 360 + 1):
        th = i * math.pi / 180
        rad = r_scale * th
        pts.append((rad * math.cos(th), rad * math.sin(th)))
    return pts

def phyllotaxis(count, radius):
    c = radius / math.sqrt(count)
    pts = []
    for i in range(count):
        th = i * 137.5 * math.pi / 180
        r = c * math.sqrt(i)
        pts.append((r * math.cos(th), r * math.sin(th)))
    return pts

def line(pts, color, width=1):
    return {"type": "line", "pts": pts, "color": color, "width": width}

def text(x, y, size, color, align="left", text_str=""):
    return {"type": "text", "x": x, "y": y, "color": color, "size": size, "align": align, "text": text_str}

def compose():
    items = []
    for f in (0.2, 0.4, 0.6, 0.8, 1.0):
        items.append(line(circle(PLATE_R * f, 180), (60, 60, 70), 1))
    for ang in range(0, 360, 30):
        th = ang * math.pi / 180
        items.append(line([(0, 0), (PLATE_R * math.cos(th), PLATE_R * math.sin(th))], (60, 60, 70), 1))
    items.append(line(circle(PLATE_R, 360), (180, 180, 200), 2))
    for ang in range(0, 360, 5):
        th = ang * math.pi / 180
        r_in = PLATE_R * (0.98 if ang % 30 == 0 else (0.99 if ang % 10 == 0 else 0.995))
        items.append(line([(r_in * math.cos(th), r_in * math.sin(th)), (PLATE_R * math.cos(th), PLATE_R * math.sin(th))], (180, 180, 200), 1))
        if ang % 30 == 0:
            items.append(text(PLATE_R * 1.04 * math.cos(th), PLATE_R * 1.04 * math.sin(th), 8, (200, 200, 200), "center", f"{ang}°"))
    rose_pts = rose(5, 3, amp=PLATE_R * 0.75)
    items.append(line(rose_pts, (220, 180, 100), 1))
    hypo_pts = hypotrochoid(200, 120, 80, turns=8)
    items.append(line(hypo_pts, (100, 200, 220), 1))
    spiral_pts = golden_spiral(r_scale=1.5, turns=6)
    items.append(line(spiral_pts, (220, 100, 150), 1))
    return items

class Painter:
    def __init__(self, screen):
        self.screen = screen
        self.t = turtle.Turtle()
        self.t.speed(0)
        self.t.hideturtle()
        self.screen.tracer(0)
        self.screen.colormode(255)
        self.items = compose()
        self.current_item = 0
        self.current_pt = 0
        self.paused = False

    def draw_step(self):
        if self.paused or self.current_item >= len(self.items):
            return
        item = self.items[self.current_item]
        if item["type"] == "line":
            pts = item["pts"]
            if self.current_pt == 0:
                self.t.penup()
                self.t.goto(pts[0])
                self.t.pendown()
                self.t.pencolor(item["color"])
                self.t.pensize(item["width"])
            batch_size = max(1, int(STEP))
            end_pt = min(self.current_pt + batch_size, len(pts))
            for i in range(self.current_pt, end_pt):
                self.t.goto(pts[i])
            self.current_pt = end_pt
            if self.current_pt >= len(pts):
                self.current_item += 1
                self.current_pt = 0
        elif item["type"] == "text":
            self.t.penup()
            self.t.goto(item["x"], item["y"] - item["size"])
            self.t.pencolor(item["color"])
            self.t.write(item["text"], align=item["align"], font=("Arial", item["size"], "normal"))
            self.current_item += 1
        self.screen.update()

def main():
    screen = turtle.Screen()
    screen.setup(WIDTH, WIDTH)
    screen.setworldcoordinates(-EXTENT, -EXTENT, EXTENT, EXTENT)
    screen.bgcolor("black")
    screen.title("Math Plate - Geometric Art")
    painter = Painter(screen)
    def toggle():
        painter.paused = not painter.paused
    def faster():
        global STEP
        STEP = min(50, STEP + 2)
    def slower():
        global STEP
        STEP = max(1, STEP - 2)
    def restart():
        screen.clear()
        screen.bgcolor("black")
        nonlocal painter
        painter = Painter(screen)
    screen.listen()
    screen.onkey(toggle, "space")
    screen.onkey(toggle, "t")
    screen.onkey(faster, "q")
    screen.onkey(slower, "w")
    screen.onkey(restart, "r")
    screen.onkey(turtle.bye, "Escape")
    def animate():
        try:
            painter.draw_step()
            screen.ontimer(animate, DELAY)
        except (turtle.Terminator, tkinter.TclError):
            pass
    screen.ontimer(animate, DELAY)
    screen.mainloop()

if __name__ == "__main__":
    main()
