from machine import Pin, I2C
import ssd1306
import time
import random

# I2C setup
i2c = I2C(0, scl=Pin(1), sda=Pin(0))
oled = ssd1306.SSD1306_I2C(128, 64, i2c)

# Button
button = Pin(15, Pin.IN, Pin.PULL_UP)

face = 0
last_offset = time.time()
time_for_next = random.uniform(0.5, 3)
offset_x = 0
offset_y = 0
is_blinking = False
blink_end = 0

def draw_circle(x0, y0, r, color="white"):
    x = r
    y = 0
    err = 0
    if color == "white":
        cc = 1
    else:
        cc = 0

    while x >= y:
        oled.pixel(x0 + x, y0 + y, cc)
        oled.pixel(x0 + y, y0 + x, cc)
        oled.pixel(x0 - y, y0 + x, cc)
        oled.pixel(x0 - x, y0 + y, cc)
        oled.pixel(x0 - x, y0 - y, cc)
        oled.pixel(x0 - y, y0 - x, cc)
        oled.pixel(x0 + y, y0 - x, cc)
        oled.pixel(x0 + x, y0 - y, cc)

        y += 1
        if err <= 0:
            err += 2*y + 1
        if err > 0:
            x -= 1
            err -= 2*x + 1
            
def fill_circle(x0, y0, r, color="white"):
    for y in range(-r, r):
        for x in range(-r, r):
            if x*x + y*y <= r*r:
                if color == "black":
                    oled.pixel(x0 + x, y0 + y, 0)
                else:
                    oled.pixel(x0 + x, y0 + y, 1)

def normal_face():
    global offset_x, offset_y
    
    oled.fill(0)

    
    if is_blinking:
        oled.fill_rect(25, 25, 30, 3, 1)
        oled.fill_rect(73, 25, 30, 3, 1)
    else:
        fill_circle(40, 25, 15)
        fill_circle(88, 25, 15)

        fill_circle(40 + offset_x, 25 + offset_y, 3, "black")
        fill_circle(88 + offset_x, 25 + offset_y, 3, "black")

    oled.fill_rect(60, 50, 10, 2, 1)

    oled.show()

while True:
    if not button.value():
        face = (face + 1) % 4
        time.sleep(0.2)
    
    elapsed_time = time.time() - last_offset
    now = time.time()
    is_blinking = False
    blink_end = 0
    last_blink = 0
    BLINK_COOLDOWN = 2.0  # seconds before next blink can happen

    # In your loop, replace the blink trigger with:
    if not is_blinking and (now - last_blink) > BLINK_COOLDOWN and random.random() < 0.015:
        is_blinking = True
        blink_end = now + 0.15
        print("blink", now)
    if is_blinking and now > blink_end:
        is_blinking = False
        last_blink = now   # <-- record when blink ended
        print("no blink")
    
    if elapsed_time >= time_for_next:
        time_for_next = random.uniform(0.5, 1.5)
        last_offset = time.time()
        offset_x += random.choice([-2, -1, 0, 1, 2])
        offset_y += random.choice([-2,-1, 0, 1])

        offset_x = max(-4, min(4, offset_x))
        offset_y = max(-4, min(4, offset_y))

    normal_face()
    time.sleep(0.05)