# The always-on status screen (400 x 240, 1-bit). Two layouts:
#   station - big pedal watts while you pedal on the stand
#   ride    - big speed and the assist you have left
# s is a plain dict (see main.py: build_status) so the simulator can feed the same thing.

import draw

W, H = 400, 240
DAYS = ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")
MONTHS = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC")


def _mode_label(s):
    m = s["mode"]
    if m == "station":
        return "STATION L%d" % s["level"]
    if m == "assist":
        return "ASSIST A%d  MAX %d" % (s["level"], s["speed_cap"])
    if m == "harvest":
        return "HARVEST H%d" % s["level"]
    return "NEUTRAL"


def _clock(s):
    y, mo, d, hh, mm, _, wd = s["time"]
    return "%02d:%02d %s %s %d" % (hh, mm, DAYS[(wd - 1) % 7], MONTHS[mo - 1], d)


def _hm(hours):
    if hours is None:
        return "--"
    total = int(hours * 60 + 0.5)
    if total >= 6000:
        return "99h+"
    return "%dh %02dm" % (total // 60, total % 60)


def render(fb, s):
    fb.fill(0)

    # ---- top bar (inverted)
    fb.fill_rect(0, 0, W, 22, 1)
    fb.text(_clock(s), 8, 7, 0)
    draw.text_right(fb, _mode_label(s), W - 8, 7, 1, 0)

    # ---- left panel: the big number
    fb.rect(6, 28, 214, 118, 1)
    if s["mode"] == "station":
        fb.text("PEDAL", 14, 34, 1)
        val = "%d" % round(s["pedal_w"])
        x = draw.seg_number(fb, val, 18, 52, 32, 58, 8, 9)
        draw.text(fb, "W", x + 2, 86, 3)
        fb.text("into pack %dW" % round(s["motor_w"]), 14, 122, 1)
        fb.text("you %dW" % round(s["pedal_w"]), 14, 133, 1)
    else:
        fb.text("SPEED", 14, 34, 1)
        val = "%.1f" % s["speed_mph"]
        x = draw.seg_number(fb, val, 18, 52, 32, 58, 8, 9)
        draw.text(fb, "mph", x + 2, 94, 2)
        motor = s["motor_w"]
        if motor <= -1:
            label = "motor %dW" % round(-motor)
        elif motor >= 1:
            label = "regen +%dW" % round(motor)
        else:
            label = "coasting"
        fb.text(label, 14, 122, 1)
        if s["pedal_w"] > 0:
            fb.text("you ~%dW" % round(s["pedal_w"]), 14, 133, 1)

    # ---- right panel: battery
    fb.rect(226, 28, 168, 118, 1)
    fb.text("BATTERY", 234, 34, 1)
    draw.text_right(fb, "%.1fV" % s["battery_v"], 386, 34)
    x = draw.seg_number(fb, "%d" % round(s["soc"]), 234, 50, 22, 40, 6, 6)
    draw.text(fb, "%", x, 66, 3)
    draw.bar(fb, 234, 100, 152, 14, s["soc"] / 100.0, s["reserve"] / 100.0)
    if s["mode"] == "station" or s["mode"] == "harvest":
        fb.text("full in " + _hm(s["hours_to_full"]) if not s["pack_full"] else "PACK FULL", 234, 124, 1)
    else:
        fb.text("assist left ~%d mi" % int(s["assist_miles"]), 234, 124, 1)
    fb.text("reserve %d%%" % s["reserve"], 234, 134, 1)

    # ---- bottom row: three small numbers
    cells = (("SOLAR", "%dW" % round(s["solar_w"])),
             ("MADE TODAY", "%dWh" % round(s["made_today_wh"])),
             ("OUT" if s["mode"] == "station" else "RESERVE",
              "%dW" % round(s["loads_w"]) if s["mode"] == "station" else "%d%%" % s["reserve"]))
    for i, (lab, val) in enumerate(cells):
        cx = 6 + i * 130
        fb.rect(cx, 152, 128, 58, 1)
        fb.text(lab, cx + 8, 158, 1)
        draw.text(fb, val, cx + 8, 174, 3)

    # ---- status chips (or the most important warning)
    if s["warnings"]:
        fb.fill_rect(0, 216, W, 24, 1)
        draw.text(fb, s["warnings"][0], 8, 220, 2, 0)
        return
    x = 6
    x = draw.chip(fb, "LIGHTS", x, 220, s["lights"])
    x = draw.chip(fb, "USB", x, 220, s["usb"])
    x = draw.chip(fb, "13.8V", x, 220, s["out_13v8"])
    x = draw.chip(fb, "PI", x, 220, s["pi_on"])
    if s["safe_mode"]:
        draw.chip(fb, "MOTOR SAFE", x, 220, True)
