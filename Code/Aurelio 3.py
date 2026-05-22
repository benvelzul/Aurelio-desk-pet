from machine import Pin, I2C
import ssd1306
import time
import random

# ─────────────────────────────────────────
# HARDWARE
# ─────────────────────────────────────────
i2c = I2C(0, scl=Pin(1), sda=Pin(0))
oled = ssd1306.SSD1306_I2C(128, 64, i2c)

# touch sensor only
touch = Pin(16, Pin.IN)

# ─────────────────────────────────────────
# TIME HELPERS
# ─────────────────────────────────────────
def ms():
    return time.ticks_ms()

def elapsed(start):
    return time.ticks_diff(time.ticks_ms(), start)

def ticks_after(now, end):
    return time.ticks_diff(now, end) > 0

# ─────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────
BLINK_COOLDOWN   = 2000
BLINK_DURATION   = 100
AWAKE_TO_SLEEPY  = 45000
SLEEPY_TO_SLEEP  = 12000
LOOP_DELAY       = 50
ANNOY_DURATION   = 5000
ANNOY_TOUCHES    = 4
SCAN_DURATION    = 4000
MIN_TO_SAD       = 25000

# ─────────────────────────────────────────
# STATE
# ─────────────────────────────────────────
state = {
    "is_sleepy": False,
    "is_sleeping": False,
    "is_blinking": False,
    "is_scanning": False,
    "is_sad": False,
    "is_happy": False,

    "sleepy_start": ms(),
    "sleeping_start": ms(),

    "blink_end": 0,
    "last_blink": ms(),

    "offset_x": 0,
    "offset_y": 0,
    "last_offset": ms(),
    "time_for_next": random.randint(500, 3000),

    "last_interaction": ms(),

    "touch_count": 0,
    "last_touch": ms(),

    "anger_level": 0,
    "annoy_end": 0,

    "scan_end": 0,
    "scan_dir": 1,

    "sad_end": 0,

    "happy_end": 0,

    "pulse": 1,
    "pulse_dir": 0.5,

    "z_offset": 0,
    "z_dir": 1,
    "z_timer": ms(),

    "touching": False
}

# ─────────────────────────────────────────
# DRAW HELPERS
# ─────────────────────────────────────────
def fill_circle(x0, y0, r, color="white"):
    c = 0 if color == "black" else 1
    for dy in range(-r, r):
        for dx in range(-r, r):
            if dx*dx + dy*dy <= r*r:
                oled.pixel(x0 + dx, y0 + dy, c)

def draw_z(x, y, size):
    oled.line(x, y, x+size, y, 1)
    oled.line(x+size, y, x, y+size, 1)
    oled.line(x, y+size, x+size, y+size, 1)

def draw_thick_line(x1, y1, x2, y2, t=2):
    for i in range(t):
        oled.line(x1, y1+i, x2, y2+i, 1)

def angry_cross(x, y, size):
    arm = size // 4
    gap = arm * 2 + 2

    oled.line(x, y+arm, x, y, 1)
    oled.line(x, y+arm, x-arm, y+arm, 1)

    oled.line(x+gap, y+arm, x+gap, y, 1)
    oled.line(x+gap, y+arm, x+gap+arm, y+arm, 1)

    oled.line(x, y+gap, x, y+gap+arm, 1)
    oled.line(x, y+gap, x-arm, y+gap, 1)

    oled.line(x+gap, y+gap, x+gap, y+gap+arm, 1)
    oled.line(x+gap, y+gap, x+gap+arm, y+gap, 1)

# ─────────────────────────────────────────
# SHAKE EFFECT
# ─────────────────────────────────────────
shake_intensity = 0
shake_end = 0

def start_shake(intensity=3, duration=200):
    global shake_intensity, shake_end
    shake_intensity = intensity
    shake_end = ms() + duration

def get_shake():
    if time.ticks_diff(shake_end, ms()) > 0:
        return (
            random.randint(-shake_intensity, shake_intensity),
            random.randint(-shake_intensity, shake_intensity)
        )
    return 0, 0

# ─────────────────────────────────────────
# BLINK
# ─────────────────────────────────────────
def try_blink(now):
    if state["is_blinking"] or state["is_sleeping"]:
        return

    chance = 0.015 if state["is_sleepy"] else 0.04

    if elapsed(state["last_blink"]) > BLINK_COOLDOWN and random.random() < chance:
        state["is_blinking"] = True
        state["blink_end"] = now + BLINK_DURATION

def update_blink(now):
    if state["is_blinking"] and ticks_after(now, state["blink_end"]):
        state["is_blinking"] = False
        state["last_blink"] = now

# ─────────────────────────────────────────
# EYE MOVEMENT
# ─────────────────────────────────────────
def update_eye_offset(now):
    if state["is_sleeping"]:
        return

    if elapsed(state["last_offset"]) > state["time_for_next"]:
        state["last_offset"] = now
        state["time_for_next"] = random.randint(500, 1500)

        state["offset_x"] = max(-4, min(4,
            state["offset_x"] + random.choice([-1, 0, 1])))

        state["offset_y"] = max(-4, min(4,
            state["offset_y"] + random.choice([-1, 0, 1])))

# ─────────────────────────────────────────
# MOOD SYSTEM
# ─────────────────────────────────────────
def update_mood(now):
    if (
        not state["is_sleepy"]
        and not state["is_sleeping"]
        and not state["is_sad"]
        and state["anger_level"] == 0
    ):
        if elapsed(state["last_interaction"]) > AWAKE_TO_SLEEPY:
            state["is_sleepy"] = True
            state["sleepy_start"] = now

    if state["is_sleepy"]:
        if elapsed(state["sleepy_start"]) > SLEEPY_TO_SLEEP:
            state["is_sleepy"] = False
            state["is_sleeping"] = True
            state["sleeping_start"] = now

def wake_up(now):
    state["is_sleepy"] = False
    state["is_sleeping"] = False
    state["is_sad"] = False
    state["last_interaction"] = now
    state["last_blink"] = now

# ─────────────────────────────────────────
# ANGER
# ─────────────────────────────────────────
def trigger_annoy(now):
    state["anger_level"] = min(4, state["anger_level"] + 1)
    state["annoy_end"] = now + ANNOY_DURATION

    start_shake(3 + state["anger_level"], 250)

    for _ in range(state["anger_level"]):
        oled.invert(1)
        oled.show()
        time.sleep_ms(50)

        oled.invert(0)
        oled.show()
        time.sleep_ms(50)

def update_anger(now):
    if state["anger_level"] > 0 and ticks_after(now, state["annoy_end"]):
        state["anger_level"] -= 1

        if state["anger_level"] > 0:
            state["annoy_end"] = now + ANNOY_DURATION

# ─────────────────────────────────────────
# SADNESS
# ─────────────────────────────────────────
def update_sadness(now):
    if (
        not state["is_sad"]
        and not state["is_sleeping"]
        and not state["is_sleepy"]
        and state["anger_level"] == 0
        and elapsed(state["last_interaction"]) > MIN_TO_SAD
        and random.random() > 0.98
    ):
        state["is_sad"] = True
        state["sad_end"] = now + random.randint(6000, 15000)

    if state["is_sad"] and ticks_after(now, state["sad_end"]):
        state["is_sad"] = False

# ─────────────────────────────────────────
# HAPPINESS
# ─────────────────────────────────────────
def update_happiness(now):
    if (
        not state["is_happy"]
        and not state["is_sleeping"]
        and not state["is_sleepy"]
        and state["anger_level"] == 0
        and elapsed(state["last_interaction"]) < 3000
        and random.random() < 0.25
    ):
        state["is_happy"] = True
        state["happy_end"] = now + random.randint(3000, 6000)

    if state["is_happy"] and ticks_after(now, state["happy_end"]):
        state["is_happy"] = False

# ─────────────────────────────────────────
# TOUCH SENSOR
# ─────────────────────────────────────────
def handle_touch(now):

    touched = touch.value()

    if touched and not state["touching"]:

        state["touching"] = True

        oled.invert(1)
        oled.show()
        time.sleep_ms(20)

        oled.invert(0)
        oled.show()

        was_sleeping = state["is_sleeping"]
        was_sleepy = state["is_sleepy"]

        if was_sleeping or was_sleepy:
            wake_up(now)

            if was_sleeping:
                if random.random() > 0.6:
                    trigger_annoy(now)
                else:
                    state["is_happy"] = True

        else:
            state["last_interaction"] = now

            if state["is_sad"]:
                state["is_sad"] = False
                state["is_happy"] = True

        if elapsed(state["last_touch"]) < 1000:
            state["touch_count"] += 1
        else:
            state["touch_count"] = 1

        state["last_touch"] = now

        if state["touch_count"] >= ANNOY_TOUCHES:
            trigger_annoy(now)
            state["touch_count"] = 0

    elif not touched:
        state["touching"] = False

# ─────────────────────────────────────────
# SCAN
# ─────────────────────────────────────────
def update_scan(now):

    if (
        not state["is_scanning"]
        and not state["is_sleeping"]
        and state["anger_level"] == 0
        and random.random() < 0.003
    ):
        state["is_scanning"] = True
        state["scan_end"] = now + SCAN_DURATION

    if state["is_scanning"]:
        state["offset_x"] += state["scan_dir"]

        if abs(state["offset_x"]) > 4:
            state["scan_dir"] *= -1

    if state["is_scanning"] and ticks_after(now, state["scan_end"]):
        state["is_scanning"] = False

# ─────────────────────────────────────────
# ZZZ
# ─────────────────────────────────────────
def update_z():
    if elapsed(state["z_timer"]) > 100:
        state["z_offset"] += state["z_dir"]

        if state["z_offset"] >= 8:
            state["z_dir"] = -1

        if state["z_offset"] <= 3:
            state["z_dir"] = 1

        state["z_timer"] = ms()

def draw_zzz(sx, sy):
    o = state["z_offset"]

    draw_z(95+sx, 18-o+sy, 4)
    draw_z(103+sx, 10-o+sy, 6)
    draw_z(113+sx, 0-o+sy, 8)

# ─────────────────────────────────────────
# FACES
# ─────────────────────────────────────────
def normal_face(sx=0, sy=0):

    ox, oy = state["offset_x"], state["offset_y"]

    oled.fill(0)

    if state["is_blinking"]:
        oled.fill_rect(25+sx, 25+sy, 30, 3, 1)
        oled.fill_rect(73+sx, 25+sy, 30, 3, 1)

    else:
        fill_circle(40+sx, 25+sy, 15)
        fill_circle(88+sx, 25+sy, 15)

        fill_circle(40+sx+ox, 25+sy+oy, 3, "black")
        fill_circle(88+sx+ox, 25+sy+oy, 3, "black")

    oled.fill_rect(60+sx, 50+sy, 10, 2, 1)

    oled.show()

def sleepy_face(sx=0, sy=0):

    oled.fill(0)

    oled.fill_rect(25+sx, 25+sy, 30, 2, 1)
    oled.fill_rect(73+sx, 25+sy, 30, 2, 1)

    oled.fill_rect(60+sx, 50+sy, 10, 2, 1)

    oled.show()

def sleeping_face(sx=0, sy=0):

    oled.fill(0)

    oled.fill_rect(25+sx, 25+sy, 30, 2, 1)
    oled.fill_rect(73+sx, 25+sy, 30, 2, 1)

    update_z()
    draw_zzz(sx, sy)

    oled.show()

def happy_face(sx=0, sy=0):

    ox, oy = state["offset_x"], state["offset_y"]

    oled.fill(0)

    fill_circle(40+sx, 25+sy, 15)
    fill_circle(88+sx, 25+sy, 15)

    fill_circle(40+sx+ox, 25+sy+oy, 3, "black")
    fill_circle(88+sx+ox, 25+sy+oy, 3, "black")

    for i in range(10):
        oled.pixel(59+sx+i, 54+sy + (2 if 1 < i < 8 else 0), 1)

    oled.show()

def sad_face(sx=0, sy=0):

    ox, oy = state["offset_x"], state["offset_y"]

    oled.fill(0)

    fill_circle(40+sx, 25+sy, 15)
    fill_circle(88+sx, 25+sy, 15)

    fill_circle(40+sx+ox, 25+sy+oy, 3, "black")
    fill_circle(88+sx+ox, 25+sy+oy, 3, "black")

    draw_thick_line(25+sx, 10+sy, 50+sx, 7+sy, 2)
    draw_thick_line(76+sx, 7+sy, 101+sx, 10+sy, 2)

    for i in range(10):
        oled.pixel(59+sx+i, 54+sy + (0 if 1 < i < 8 else 2), 1)

    oled.show()

def annoyed_face(sx=0, sy=0):

    ox, oy = state["offset_x"], state["offset_y"]
    lvl = state["anger_level"]

    oled.fill(0)

    draw_thick_line(25+sx, 5+sy, 50+sx, 10+sy, 1+lvl)
    draw_thick_line(75+sx, 10+sy, 100+sx, 4+sy, 1+lvl)

    fill_circle(40+sx, 30+sy, 15)
    fill_circle(88+sx, 30+sy, 15)

    state["pulse"] += state["pulse_dir"]

    if state["pulse"] >= 4:
        state["pulse_dir"] = -0.5

    if state["pulse"] <= 1:
        state["pulse_dir"] = 0.5

    p = int(state["pulse"])

    fill_circle(40+sx+ox, 30+sy+oy, p, "black")
    fill_circle(88+sx+ox, 30+sy+oy, p, "black")

    if lvl > 3:
        angry_cross(110, 4, 12)

    oled.fill_rect(55+sx, 52+sy, 18, 1+lvl, 1)

    oled.show()

def scan_face(sx=0, sy=0):

    ox, oy = state["offset_x"], state["offset_y"]

    oled.fill(0)

    fill_circle(40+sx, 25+sy, 15)
    fill_circle(88+sx, 25+sy, 15)

    fill_circle(40+sx+ox, 25+sy+oy, 3, "black")
    fill_circle(88+sx+ox, 25+sy+oy, 3, "black")

    squint = 6 + int(abs(ox))

    oled.fill_rect(25+sx, 10+sy, 30, squint, 0)
    oled.fill_rect(73+sx, 10+sy, 30, squint, 0)

    oled.line(25+sx, 7+sy+squint, 55+sx, 7+sy+squint, 1)
    oled.line(74+sx, 7+sy+squint, 104+sx, 7+sy+squint, 1)

    oled.fill_rect(60+sx, 50+sy, 10, 2, 1)

    oled.show()

# ─────────────────────────────────────────
# RENDER
# ─────────────────────────────────────────
def render(sx=0, sy=0):

    if state["anger_level"] > 0:
        annoyed_face(sx, sy)

    elif state["is_happy"]:
        happy_face(sx, sy)

    elif state["is_sad"]:
        sad_face(sx, sy)

    elif state["is_sleeping"]:
        sleeping_face(sx, sy)

    elif state["is_sleepy"]:
        sleepy_face(sx, sy)

    elif state["is_scanning"]:
        scan_face(sx, sy)

    else:
        normal_face(sx, sy)

# ─────────────────────────────────────────
# STARTUP
# ─────────────────────────────────────────
def startup():

    oled.fill(0)
    oled.show()

    for _ in range(3):
        oled.invert(1)
        oled.show()
        time.sleep_ms(100)

        oled.invert(0)
        oled.show()
        time.sleep_ms(100)

    sizes = [2, 5, 8, 11, 15]

    for r in sizes:

        oled.fill(0)

        fill_circle(40, 25, r)
        fill_circle(88, 25, r)

        if r >= 8:
            fill_circle(40, 25, max(1, r-10), "black")
            fill_circle(88, 25, max(1, r-10), "black")

        oled.fill_rect(60, 50, 10, 2, 1)

        oled.show()

        time.sleep_ms(100)

# ─────────────────────────────────────────
# MAIN LOOP
# ─────────────────────────────────────────
startup()

while True:

    now = ms()

    handle_touch(now)

    update_mood(now)
    update_anger(now)
    update_sadness(now)
    update_happiness(now)

    try_blink(now)
    update_blink(now)
    update_eye_offset(now)
    update_scan(now)

    sx, sy = get_shake()

    render(sx, sy)

    time.sleep_ms(LOOP_DELAY)