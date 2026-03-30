from machine import Pin, I2C
import ssd1306
import time
import random

# ─────────────────────────────────────────
# HARDWARE
# ─────────────────────────────────────────
i2c = I2C(0, scl=Pin(1), sda=Pin(0))
oled = ssd1306.SSD1306_I2C(128, 64, i2c)
button = Pin(15, Pin.IN, Pin.PULL_UP)

# helper — always use this for time comparisons
def ms():
    return time.ticks_ms()

def elapsed(start):
    return time.ticks_diff(time.ticks_ms(), start)

# ─────────────────────────────────────────
# BLINK
# ─────────────────────────────────────────
is_blinking       = False
blink_end         = 0
blink_start       = ms()
last_blink        = ms()
BLINK_COOLDOWN    = 2000   # ms
double_blink      = False
second_blink_time = 0

# ─────────────────────────────────────────
# EYES
# ─────────────────────────────────────────
offset_x      = 0
offset_y      = 0
last_offset   = ms()
time_for_next = random.randint(500, 3000)   # ms

# ─────────────────────────────────────────
# STATES
# ─────────────────────────────────────────
is_sleepy        = False
is_sleeping      = False
sleepy_start     = ms()
SLEEPY_TO_SLEEP  = 10000
AWAKE_TO_SLEEPY  = 30000
last_interaction = ms()
sleepy_z_offset  = 0
sleepy_z_dir     = 1
sleepy_z_timer   = ms()

# ─────────────────────────────────────────
# BUTTON
# ─────────────────────────────────────────
press_count     = 0
last_press_time = ms()

# ─────────────────────────────────────────
# SHAKE
# ─────────────────────────────────────────
shake_intensity = 0
shake_end       = 0

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
    oled.line(x,        y,        x + size, y,        1)
    oled.line(x + size, y,        x,        y + size, 1)
    oled.line(x,        y + size, x + size, y + size, 1)

def start_shake(intensity=4, duration=200):
    global shake_intensity, shake_end
    shake_intensity = intensity
    shake_end = ms() + duration

# ─────────────────────────────────────────
# FACES
# ─────────────────────────────────────────
def normal_face(sx=0, sy=0, blinking=False):
    oled.fill(0)
    if blinking:
        oled.fill_rect(25+sx, 25+sy, 30, 3, 1)
        oled.fill_rect(73+sx, 25+sy, 30, 3, 1)
    else:
        fill_circle(40+sx, 25+sy, 15)
        fill_circle(88+sx, 25+sy, 15)
        fill_circle(40+sx + offset_x, 25+sy + offset_y, 3, "black")
        fill_circle(88+sx + offset_x, 25+sy + offset_y, 3, "black")
    oled.fill_rect(60+sx, 50+sy, 10, 2, 1)
    oled.show()

def sleepy_face(sx=0, sy=0):
    oled.fill(0)
    if is_blinking:
        oled.fill_rect(25+sx, 25+sy, 30, 2, 1)
        oled.fill_rect(73+sx, 25+sy, 30, 2, 1)
    else:
        fill_circle(40+sx, 28+sy, 13)
        fill_circle(88+sx, 28+sy, 13)
        fill_circle(40+sx + offset_x, 30+sy + offset_y, 3, "black")
        fill_circle(88+sx + offset_x, 30+sy + offset_y, 3, "black")
        oled.fill_rect(25+sx, 16+sy, 32, 10, 0)
        oled.fill_rect(73+sx, 16+sy, 32, 10, 0)
        oled.fill_rect(25+sx, 16+sy, 32, 2, 1)
        oled.fill_rect(73+sx, 16+sy, 32, 2, 1)
    oled.fill_rect(60+sx, 50+sy, 10, 2, 1)
    oled.show()

def sleeping_face(sx=0, sy=0):
    global sleepy_z_offset, sleepy_z_timer, sleepy_z_dir
    oled.fill(0)
    oled.fill_rect(25+sx, 25+sy, 30, 2, 1)
    oled.fill_rect(73+sx, 25+sy, 30, 2, 1)
    oled.fill_rect(60+sx, 50+sy, 10, 2, 1)
    now = ms()
    if elapsed(sleepy_z_timer) > 100:
        sleepy_z_offset += sleepy_z_dir
        if sleepy_z_offset >= 8:
            sleepy_z_dir = -1
        elif sleepy_z_offset <= 3:
            sleepy_z_dir = 1
        sleepy_z_timer = now
    o = sleepy_z_offset
    draw_z(95+sx,  18-o+sy, 4)
    draw_z(103+sx, 10-o+sy, 6)
    draw_z(113+sx,  0-o+sy, 8)
    oled.show()

# ─────────────────────────────────────────
# MAIN LOOP
# ─────────────────────────────────────────
while True:
    now = ms()

    # ── Button ───────────────────────────
    if not button.value():
        last_interaction  = now
        is_sleepy         = False
        is_sleeping       = False
        is_blinking       = False
        double_blink      = False
        second_blink_time = 0
        blink_start       = now
        last_blink        = now

        if elapsed(last_press_time) < 500:
            press_count += 1
        else:
            press_count = 1
        last_press_time = now
        time.sleep_ms(200)

    now = ms()

    # ── State updates ────────────────────
    if not is_sleepy and not is_sleeping:
        if elapsed(last_interaction) > AWAKE_TO_SLEEPY:
            is_sleepy    = True
            sleepy_start = now

    if is_sleepy and elapsed(sleepy_start) > SLEEPY_TO_SLEEP:
        is_sleepy   = False
        is_sleeping = True
        start_shake(intensity=2, duration=200)

    # ── Blink ────────────────────────────
    blink_chance = 0.04 if not is_sleepy else 0.015

    if (not is_blinking and not is_sleeping
            and elapsed(last_blink) > BLINK_COOLDOWN
            and random.random() < blink_chance):
        is_blinking = True
        blink_end   = now + 100
        blink_start = now
        print(f"BLINK START now={now} end={blink_end}")

    if is_blinking and time.ticks_diff(now, blink_end) > 0:
        is_blinking = False
        last_blink  = now
        print(f"BLINK END now={now}")

    # ── Eye movement ─────────────────────
    if elapsed(last_offset) > time_for_next and not is_sleeping:
        last_offset   = now
        time_for_next = random.randint(500, 1500)
        offset_x = max(-4, min(4, offset_x + random.choice([-1, 0, 1])))
        offset_y = max(-4, min(4, offset_y + random.choice([-1, 0, 1])))

    # ── Shake ────────────────────────────
    if time.ticks_diff(now, shake_end) < 0:
        sx = random.randint(-shake_intensity, shake_intensity)
        sy = random.randint(-shake_intensity, shake_intensity)
    else:
        sx = 0
        sy = 0

    # ── Draw ─────────────────────────────
    if is_sleeping:
        sleeping_face(sx, sy)
    elif is_sleepy:
        sleepy_face(sx, sy)
    else:
        normal_face(sx, sy, is_blinking)

    time.sleep_ms(50)