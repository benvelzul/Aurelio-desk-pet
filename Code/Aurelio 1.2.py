from machine import Pin, I2C
import ssd1306
import time
import random

# ─────────────────────────────────────────
# HARDWARE
# ─────────────────────────────────────────
i2c    = I2C(0, scl=Pin(1), sda=Pin(0))
oled   = ssd1306.SSD1306_I2C(128, 64, i2c)
button = Pin(15, Pin.IN, Pin.PULL_UP)

# ─────────────────────────────────────────
# TIME HELPERS
# ─────────────────────────────────────────
def ms():
    return time.ticks_ms()

def elapsed(start):
    return time.ticks_diff(time.ticks_ms(), start)

def ticks_after(start, end):
    """True if 'now' is past 'end'."""
    return time.ticks_diff(start, end) > 0

# ─────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────
BLINK_COOLDOWN   = 2000   # ms between blinks
BLINK_DURATION   = 150    # ms eyes stay closed
AWAKE_TO_SLEEPY  = 30000  # ms idle before getting sleepy
SLEEPY_TO_SLEEP  = 10000  # ms in sleepy before sleeping
LOOP_DELAY       = 50     # ms per frame
ANNOY_DURATION   = 3000   # ms annoyed face shows
ANNOY_PRESSES    = 5      # presses to trigger annoyance
ANNOY_IDLE_MIN   = 60000  # ms idle before random annoyance can happen
ANNOY_IDLE_CHANCE = 0.001 # chance per frame of random annoyance

# ─────────────────────────────────────────
# STATE
# ─────────────────────────────────────────
state = {
    # mood
    "is_sleepy":   False,
    "is_sleeping": False,
    "sleepy_start": ms(),

    # blink
    "is_blinking":  False,
    "blink_end":    0,
    "last_blink":   ms(),

    # eyes
    "offset_x": 0,
    "offset_y": 0,
    "last_offset":   ms(),
    "time_for_next": random.randint(500, 3000),

    # button
    "press_count":     0,
    "last_press_time": ms(),
    "last_interaction": ms(),

    # shake
    "shake_intensity": 0,
    "shake_end":       0,

    # zzz animation
    "z_offset": 0,
    "z_dir":    1,
    "z_timer":  ms(),
    
    # annoyance
    "is_annoyed":    False,
    "annoy_end":     0,
    "annoy_trigger": "",   # "spam", "wake", or "idle"
}

# ─────────────────────────────────────────
# DRAW PRIMITIVES
# ─────────────────────────────────────────
def fill_circle(x0, y0, r, color="white"):
    c = 0 if color == "black" else 1
    for dy in range(-r, r):
        for dx in range(-r, r):
            if dx*dx + dy*dy <= r*r:
                oled.pixel(x0 + dx, y0 + dy, c)

def draw_z(x, y, size):
    oled.line(x,        y,        x+size, y,        1)
    oled.line(x+size,   y,        x,      y+size,   1)
    oled.line(x,        y+size,   x+size, y+size,   1)

# ─────────────────────────────────────────
# SHAKE
# ─────────────────────────────────────────
def start_shake(intensity=4, duration=200):
    state["shake_intensity"] = intensity
    state["shake_end"]       = ms() + duration

def get_shake_offset():
    """Returns (sx, sy) — nonzero only during active shake."""
    now = ms()
    if time.ticks_diff(state["shake_end"], now) > 0:
        i = state["shake_intensity"]
        return random.randint(-i, i), random.randint(-i, i)
    return 0, 0

# ─────────────────────────────────────────
# BLINK LOGIC
# ─────────────────────────────────────────
def try_blink(now):
    """Maybe start a blink if cooldown has passed."""
    if state["is_blinking"] or state["is_sleeping"]:
        return
    chance = 0.015 if state["is_sleepy"] else 0.04
    if elapsed(state["last_blink"]) > BLINK_COOLDOWN and random.random() < chance:
        state["is_blinking"] = True
        state["blink_end"]   = now + BLINK_DURATION
        print(f"BLINK START now={now}")

def update_blink(now):
    """Clear blink if duration has passed."""
    if state["is_blinking"] and ticks_after(now, state["blink_end"]):
        state["is_blinking"] = False
        state["last_blink"]  = now
        print(f"BLINK END now={now}")

# ─────────────────────────────────────────
# EYE MOVEMENT
# ─────────────────────────────────────────
def update_eye_offset(now):
    """Randomly drift pupils every so often."""
    if state["is_sleeping"]:
        return
    if elapsed(state["last_offset"]) > state["time_for_next"]:
        state["last_offset"]   = now
        state["time_for_next"] = random.randint(500, 1500)
        state["offset_x"] = max(-4, min(4, state["offset_x"] + random.choice([-1, 0, 1])))
        state["offset_y"] = max(-4, min(4, state["offset_y"] + random.choice([-1, 0, 1])))

# ─────────────────────────────────────────
# MOOD / STATE LOGIC
# ─────────────────────────────────────────
def update_mood(now):
    if not state["is_sleepy"] and not state["is_sleeping"] and not state["is_annoyed"]:
        if elapsed(state["last_interaction"]) > AWAKE_TO_SLEEPY:
            state["is_sleepy"]    = True
            state["sleepy_start"] = now
            print("MOOD -> sleepy")

    if state["is_sleepy"] and elapsed(state["sleepy_start"]) > SLEEPY_TO_SLEEP:
        state["is_sleepy"]   = False
        state["is_sleeping"] = True
        start_shake(intensity=2, duration=200)
        print("MOOD -> sleeping")

def wake_up(now):
    """Reset all sleep/blink state on button press."""
    state["last_interaction"] = now
    state["is_sleepy"]        = False
    state["is_sleeping"]      = False
    state["is_blinking"]      = False
    state["last_blink"]       = now
    print("MOOD -> awake")

# ─────────────────────────────────────────
# BUTTON HANDLING
# ─────────────────────────────────────────
def handle_button(now):
    if button.value():
        return

    was_sleeping = state["is_sleeping"]
    wake_up(now)

    # waking from sleep = annoyed
    if was_sleeping:
        trigger_annoy(now, "wake")

    if elapsed(state["last_press_time"]) < 500:
        state["press_count"] += 1
    else:
        state["press_count"] = 1
    state["last_press_time"] = now

    # button spam = annoyed
    if state["press_count"] >= ANNOY_PRESSES:
        trigger_annoy(now, "spam")
        state["press_count"] = 0

    print(f"BTN press_count={state['press_count']}")
    time.sleep_ms(200)
# ─────────────────────────────────────────
# ZZZ ANIMATION
# ─────────────────────────────────────────
def update_z_animation():
    if elapsed(state["z_timer"]) > 100:
        state["z_offset"] += state["z_dir"]
        if state["z_offset"] >= 8:
            state["z_dir"] = -1
        elif state["z_offset"] <= 3:
            state["z_dir"] = 1
        state["z_timer"] = ms()

def draw_zzz(sx, sy):
    o = state["z_offset"]
    draw_z(95+sx,  18-o+sy, 4)
    draw_z(103+sx, 10-o+sy, 6)
    draw_z(113+sx,  0-o+sy, 8)

# ─────────────────────────────────────────
# ANNOYANCE
# ─────────────────────────────────────────
def trigger_annoy(now, reason=""):
    if state["is_annoyed"]:
        return
    state["is_annoyed"]    = True
    state["annoy_end"]     = now + ANNOY_DURATION
    state["annoy_trigger"] = reason
    start_shake(intensity=5, duration=400)
    print(f"ANNOYED reason={reason}")

def update_annoy(now):
    if state["is_annoyed"] and ticks_after(now, state["annoy_end"]):
        state["is_annoyed"] = False
        print("ANNOY -> calm")
    # random idle annoyance
    if (not state["is_annoyed"] and not state["is_sleeping"]
            and elapsed(state["last_interaction"]) > ANNOY_IDLE_MIN
            and random.random() < ANNOY_IDLE_CHANCE):
        trigger_annoy(now, "idle")

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
        fill_circle(40+sx,      25+sy, 15)
        fill_circle(88+sx,      25+sy, 15)
        fill_circle(40+sx + ox, 25+sy + oy, 3, "black")
        fill_circle(88+sx + ox, 25+sy + oy, 3, "black")
    oled.fill_rect(60+sx, 50+sy, 10, 2, 1)
    oled.show()

def sleepy_face(sx=0, sy=0):
    ox, oy = state["offset_x"], state["offset_y"]
    oled.fill(0)
    if state["is_blinking"]:
        oled.fill_rect(25+sx, 25+sy, 30, 2, 1)
        oled.fill_rect(73+sx, 25+sy, 30, 2, 1)
    else:
        fill_circle(40+sx,      28+sy, 13)
        fill_circle(88+sx,      28+sy, 13)
        fill_circle(40+sx + ox, 30+sy + oy, 3, "black")
        fill_circle(88+sx + ox, 30+sy + oy, 3, "black")
        # heavy eyelids
        oled.fill_rect(25+sx, 16+sy, 32, 10, 0)
        oled.fill_rect(73+sx, 16+sy, 32, 10, 0)
        oled.fill_rect(25+sx, 16+sy, 32,  2, 1)
        oled.fill_rect(73+sx, 16+sy, 32,  2, 1)
    oled.fill_rect(60+sx, 50+sy, 10, 2, 1)
    oled.show()

def sleeping_face(sx=0, sy=0):
    oled.fill(0)
    oled.fill_rect(25+sx, 25+sy, 30, 2, 1)
    oled.fill_rect(73+sx, 25+sy, 30, 2, 1)
    oled.fill_rect(60+sx, 50+sy, 10, 2, 1)
    update_z_animation()
    draw_zzz(sx, sy)
    oled.show()
    
def annoyed_face(sx=0, sy=0):
    ox, oy = state["offset_x"], state["offset_y"]
    oled.fill(0)
    # angry brows angled inward
    oled.line(25+sx, 18+sy, 45+sx, 26+sy, 1)
    oled.line(26+sx, 18+sy, 46+sx, 26+sy, 1)  # thicker
    oled.line(83+sx, 26+sy, 103+sx, 18+sy, 1)
    oled.line(84+sx, 26+sy, 104+sx, 18+sy, 1)  # thicker
    # normal eye circles
    fill_circle(40+sx,      30+sy, 13)
    fill_circle(88+sx,      30+sy, 13)
    # small pupils (looking slightly down-center = more menacing)
    fill_circle(40+sx + ox, 32+sy + oy, 4, "black")
    fill_circle(88+sx + ox, 32+sy + oy, 4, "black")
    # flat mouth
    oled.fill_rect(55+sx, 52+sy, 18, 2, 1)
    oled.show()

# ─────────────────────────────────────────
# RENDER
# ─────────────────────────────────────────
def render(sx=0, sy=0):
    if state["is_annoyed"]:
        annoyed_face(sx, sy)
    elif state["is_sleeping"]:
        sleeping_face(sx, sy)
    elif state["is_sleepy"]:
        sleepy_face(sx, sy)
    else:
        normal_face(sx, sy)

# ─────────────────────────────────────────
# MAIN LOOP
# ─────────────────────────────────────────
while True:
    now = ms()

    handle_button(now)
    now = ms()

    update_mood(now)
    update_annoy(now)     # ← add this
    try_blink(now)
    update_blink(now)
    update_eye_offset(now)

    sx, sy = get_shake_offset()
    render(sx, sy)

    time.sleep_ms(LOOP_DELAY)