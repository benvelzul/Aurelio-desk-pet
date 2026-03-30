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

def ticks_after(now, end):
    return time.ticks_diff(now, end) > 0

# ─────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────
BLINK_COOLDOWN   = 2000
BLINK_DURATION   = 150
AWAKE_TO_SLEEPY  = 100000
SLEEPY_TO_SLEEP  = 10000
LOOP_DELAY       = 50
ANNOY_DURATION   = 5000
ANNOY_PRESSES    = 5

# ─────────────────────────────────────────
# STATE
# ─────────────────────────────────────────
state = {
    # mood
    "is_sleepy":    False,
    "is_sleeping":  False,
    "sleepy_start": ms(),

    # blink
    "is_blinking": False,
    "blink_end":   0,
    "last_blink":  ms(),

    # eyes
    "offset_x":      0,
    "offset_y":      0,
    "last_offset":   ms(),
    "time_for_next": random.randint(500, 3000),

    # button
    "press_count":      0,
    "last_press_time":  ms(),
    "last_interaction": ms(),

    # shake
    "shake_intensity": 0,
    "shake_end":       0,

    # zzz animation
    "z_offset": 0,
    "z_dir":    1,
    "z_timer":  ms(),

    # anger (levels 0-3, decays over time)
    "anger_level":   0,
    "annoy_end":     0,
    "annoy_trigger": "",

    # annoyed face pupils
    "pulse":     1.0,
    "pulse_dir": 0.5,

    # scan system
    "is_scanning": False,
    "scan_end":    0,
    "scan_dir":    1,
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
    oled.line(x,      y,      x+size, y,      1)
    oled.line(x+size, y,      x,      y+size, 1)
    oled.line(x,      y+size, x+size, y+size, 1)

def draw_thick_line(x1, y1, x2, y2, t=2):
    for i in range(t):
        oled.line(x1+i, y1+i, x2+i, y2+i, 1)

# ─────────────────────────────────────────
# SHAKE
# ─────────────────────────────────────────
def start_shake(intensity=4, duration=200):
    state["shake_intensity"] = intensity
    state["shake_end"]       = ms() + duration

def get_shake_offset():
    if time.ticks_diff(state["shake_end"], ms()) > 0:
        i = state["shake_intensity"]
        return random.randint(-i, i), random.randint(-i, i)
    return 0, 0

# ─────────────────────────────────────────
# BLINK
# ─────────────────────────────────────────
def try_blink(now):
    if state["is_blinking"] or state["is_sleeping"] or state["anger_level"] > 0:
        return
    chance = 0.015 if state["is_sleepy"] else 0.04
    if elapsed(state["last_blink"]) > BLINK_COOLDOWN and random.random() < chance:
        state["is_blinking"] = True
        state["blink_end"]   = now + BLINK_DURATION
        print("[BLINK] start")

def update_blink(now):
    if state["is_blinking"] and ticks_after(now, state["blink_end"]):
        state["is_blinking"] = False
        state["last_blink"]  = now
        print("[BLINK] end")

# ─────────────────────────────────────────
# EYE MOVEMENT
# ─────────────────────────────────────────
def update_eye_offset(now):
    if state["is_sleeping"]:
        return
    if elapsed(state["last_offset"]) > state["time_for_next"]:
        state["last_offset"]   = now
        state["time_for_next"] = random.randint(500, 1500)
        state["offset_x"] = max(-4, min(4, state["offset_x"] + random.choice([-1, 0, 1])))
        state["offset_y"] = max(-4, min(4, state["offset_y"] + random.choice([-1, 0, 1])))

# ─────────────────────────────────────────
# SCAN
# ─────────────────────────────────────────
def update_scan(now):
    if (not state["is_scanning"]
            and not state["is_sleeping"]
            and state["anger_level"] == 0
            and random.random() < 0.003):
        state["is_scanning"] = True
        state["scan_end"]    = now + 2000
        print("[SCAN] start")

    if state["is_scanning"]:
        state["offset_x"] += state["scan_dir"]
        if abs(state["offset_x"]) > 4:
            state["scan_dir"] *= -1

    if state["is_scanning"] and ticks_after(now, state["scan_end"]):
        state["is_scanning"] = False
        print("[SCAN] end")

# ─────────────────────────────────────────
# MOOD
# ─────────────────────────────────────────
def update_mood(now):
    # don't go sleepy while angry
    if not state["is_sleepy"] and not state["is_sleeping"] and state["anger_level"] == 0:
        if elapsed(state["last_interaction"]) > AWAKE_TO_SLEEPY:
            state["is_sleepy"]    = True
            state["sleepy_start"] = now
            print("[MOOD] sleepy")

    if state["is_sleepy"] and elapsed(state["sleepy_start"]) > SLEEPY_TO_SLEEP:
        state["is_sleepy"]   = False
        state["is_sleeping"] = True
        start_shake(intensity=2, duration=200)
        print("[MOOD] sleeping")

def wake_up(now):
    state["last_interaction"] = now
    state["is_sleepy"]        = False
    state["is_sleeping"]      = False
    state["is_blinking"]      = False
    state["last_blink"]       = now
    print("[MOOD] awake")

# ─────────────────────────────────────────
# ANGER
# ─────────────────────────────────────────
def trigger_annoy(now, reason=""):
    # each trigger bumps anger up, max level 3
    state["anger_level"]   = min(3, state["anger_level"] + 1)
    state["annoy_end"]     = now + ANNOY_DURATION
    state["annoy_trigger"] = reason
    start_shake(intensity=3 + state["anger_level"], duration=300)
    # flash screen
    for _ in range(state["anger_level"]):
        oled.invert(1); oled.show()
        time.sleep_ms(60)
        oled.invert(0); oled.show()
        time.sleep_ms(60)
    print(f"[ANGER] level={state['anger_level']} reason={reason}")

def update_anger(now):
    # decay one level when timer expires
    if state["anger_level"] > 0 and ticks_after(now, state["annoy_end"]):
        state["anger_level"] -= 1
        if state["anger_level"] > 0:
            # still angry, reset timer for next decay
            state["annoy_end"] = now + ANNOY_DURATION
        print(f"[ANGER] decay -> {state['anger_level']}")

# ─────────────────────────────────────────
# BUTTON
# ─────────────────────────────────────────
def handle_button(now):
    if button.value():
        return

    was_sleeping = state["is_sleeping"]
    wake_up(now)

    # waking from sleep = annoyed (70% chance)
    if was_sleeping and random.random() > 0.1:
        trigger_annoy(now, "wake")

    if elapsed(state["last_press_time"]) < 1000:
        state["press_count"] += 1
    else:
        state["press_count"] = 1
    state["last_press_time"] = now

    # spam = annoyed, anger can stack up to level 3
    if state["press_count"] >= ANNOY_PRESSES:
        trigger_annoy(now, "spam")
        state["press_count"] = 0

    print(f"[BTN] count={state['press_count']} anger={state['anger_level']}")
    time.sleep_ms(200)

# ─────────────────────────────────────────
# ZZZ ANIMATION
# ─────────────────────────────────────────
def update_z_animation():
    if elapsed(state["z_timer"]) > 100:
        state["z_offset"] += state["z_dir"]
        if state["z_offset"] >= 8: state["z_dir"] = -1
        if state["z_offset"] <= 3: state["z_dir"] =  1
        state["z_timer"] = ms()

def draw_zzz(sx, sy):
    o = state["z_offset"]
    draw_z(95+sx, 18-o+sy, 4)
    draw_z(103+sx, 10-o+sy, 6)
    draw_z(113+sx,  0-o+sy, 8)

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
    lvl    = state["anger_level"]
    oled.fill(0)

    # brows get thicker and more angled with anger level
    brow_thickness = 1 + lvl
    brow_slant     = 2 * lvl
    draw_thick_line(25+sx, 5-brow_slant+sy, 50+sx, 10+sy,     brow_thickness)
    draw_thick_line(75+sx, 10+sy,     104+sx, 5-brow_slant+sy, brow_thickness)

    # eyes
    fill_circle(40+sx,      30+sy, 15)
    fill_circle(88+sx,      30+sy, 15)

    # pulsing pupils
    state["pulse"] += state["pulse_dir"]
    if state["pulse"] >= 4:   state["pulse_dir"] = -0.5
    if state["pulse"] <= 1:   state["pulse_dir"] =  0.5
    p = int(state["pulse"])
    fill_circle(40+sx + ox, 30+sy + oy, p, "black")
    fill_circle(88+sx + ox, 30+sy + oy, p, "black")

    # mouth gets wider/thicker with anger level
    oled.fill_rect(55+sx, 52+sy, 18, 1 + lvl, 1)

    oled.show()

# ─────────────────────────────────────────
# RENDER
# ─────────────────────────────────────────
def render(sx=0, sy=0):
    if state["anger_level"] > 0:
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
    update_anger(now)
    try_blink(now)
    update_blink(now)
    update_eye_offset(now)
    update_scan(now)

    sx, sy = get_shake_offset()
    render(sx, sy)

    time.sleep_ms(LOOP_DELAY)
    