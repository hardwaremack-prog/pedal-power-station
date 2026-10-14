"""Run the real Pico and Pi code on a PC with pretend sensors, and save pictures of both screens.

    python3 software/sim/simulate.py            # writes software/sim/out/*.png

Nothing here touches hardware. The Pico screen pictures are drawn by the same ui.py the Pico
runs (through a framebuf stand-in), and the Pi tabs by the same screens.py the Pi runs.
"""

import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)                                   # framebuf stand-in first
sys.path.insert(1, os.path.join(HERE, "..", "pico"))
sys.path.insert(2, os.path.join(HERE, "..", "pi"))

from PIL import Image  # noqa: E402

import config as cfg      # noqa: E402  (pico/config.py)
import energy as energy_mod  # noqa: E402
import framebuf  # noqa: E402
import rules  # noqa: E402
import status as status_mod  # noqa: E402
import ui  # noqa: E402

OUT = os.path.join(HERE, "out")


def readings(battery_v, battery_a, solar_w, motor_w, loads_w, speed=0.0):
    pv = 18.0
    return {
        "battery_v": battery_v, "battery_a": battery_a,
        "solar_v": battery_v, "solar_a": solar_w / battery_v,
        "motor_v": battery_v, "motor_a": motor_w / battery_v,
        "loads_v": battery_v, "loads_a": loads_w / battery_v,
        "speed_mph": speed, "_pv": pv,
    }


def lcd_png(fb_buf, path, scale=2):
    """Save the 1-bit frame looking like a reflective memory LCD (grey-green paper, dark ink)."""
    w, h = ui.W, ui.H
    img = Image.new("RGB", (w, h))
    px = img.load()
    stride = w // 8
    for y in range(h):
        for x in range(w):
            on = fb_buf[y * stride + (x >> 3)] & (0x80 >> (x & 7))
            px[x, y] = (34, 38, 36) if on else (196, 204, 192)
    img = img.resize((w * scale, h * scale), Image.NEAREST)
    frame = Image.new("RGB", (img.width + 24, img.height + 24), (40, 44, 52))
    frame.paste(img, (12, 12))
    frame.save(path)


def scene(name, st, r, soc, seconds, outs, pi_on=False, wings=True, braking=False,
          made=None, clock=(2026, 10, 13, 19, 8, 0, 2)):
    e = energy_mod.Energy(cfg, soc_pct=soc)
    e.new_day("2026-10-13")
    if made:
        for k, v in made.items():
            e.today[k] = v
    # Run the real update a few seconds so derived numbers come from the real code.
    for _ in range(int(seconds * 10)):
        e.update(0.1, r, st["mode"], r["speed_mph"])
    d = rules.decide(rules.Inputs(st["mode"], st["level"], r["speed_mph"], e.soc_pct,
                                  braking, wings, e.pack_full), cfg)
    st = dict(st, wings_locked=wings, braking=braking)
    s = status_mod.build(cfg, st, r, e, d, outs, pi_on, False, clock)
    buf = bytearray(ui.W * ui.H // 8)
    fb = framebuf.FrameBuffer(buf, ui.W, ui.H, framebuf.MONO_HLSB)
    ui.render(fb, s)
    lcd_png(buf, os.path.join(OUT, name + ".png"))
    return s, d


def pico_screens():
    on = {"lights": True, "usb": True, "out_13v8": False}
    day = {"lights": False, "usb": True, "out_13v8": False}
    made = {"solar": 41.0, "pedal": 23.0, "regen": 0.0}

    s1, _ = scene("status_station", {"mode": "station", "level": 3},
                  readings(40.1, 2.4, 18, 102, 6), 78, 3, on, pi_on=True, made=made)
    s2, d2 = scene("status_ride_assist", {"mode": "assist", "level": 2},
                   readings(39.6, -2.2, 22, -85, 3, speed=12.4), 78, 3, day, made=made)
    s3, d3 = scene("status_ride_harvest", {"mode": "harvest", "level": 2},
                   readings(40.3, 1.6, 20, 58, 3, speed=13.1), 64, 3, day, made=made)
    s4, d4 = scene("status_reserve", {"mode": "assist", "level": 2},
                   readings(39.0, -0.1, 0, 0, 3, speed=9.0), 24.5, 1, on, made=made)
    s5, d5 = scene("status_wings_up", {"mode": "assist", "level": 1},
                   readings(40.0, 0.5, 60, 0, 3), 70, 1, day, wings=False, made=made)
    return [s1, s2, s3, s4, s5], [d2, d3, d4, d5]


def pi_screens(status):
    from pps import config as pcfg, screens
    from pps.energylog import EnergyLog
    from pps.mesh import FakeMesh, Message, Node
    from pps.app import App
    from pps.display import PngDisplay
    from pps.pico_link import FakePico

    now = time.time()
    mesh = FakeMesh(
        messages=[
            Message(now - 3600, "RAY", "Power's out on Oak St. Anyone have a charger?"),
            Message(now - 3300, "me", "Have power to share at the corner of Oak & 5th. "
                                      "USB and 13.8V for radios.", mine=True),
            Message(now - 1800, "DANA", "Thanks! Coming by with two phones."),
            Message(now - 600, "KIDS", "Block party moved to the church lot, they have lights."),
        ],
        nodes=[Node("Ray's house", "RAY", 42.3820, -83.0590, now),
               Node("Dana", "DANA", 42.3801, -83.0552, now),
               Node("Church lot", "KIDS", 42.3842, -83.0531, now),
               Node("Rooftop relay", "RLY1", 42.3866, -83.0611, now)],
        me=(42.3812, -83.0575))
    tmp = tempfile.mkdtemp()
    log = EnergyLog(os.path.join(tmp, "energy.db"))
    week = [(22, 30, 4), (55, 12, 2), (8, 41, 0), (61, 25, 6), (47, 0, 3), (12, 60, 1)]
    for i, (sun, legs, regen) in enumerate(week):
        log.record(f"2026-10-{7 + i:02d}", {"solar": sun, "pedal": legs, "regen": regen,
                                            "used": 20, "assist": 30})
    c = pcfg.Config(display="png", idle_sleep_minutes=0)
    pico = FakePico([status])
    app = App(c, pico, mesh, PngDisplay(os.path.join(tmp, "x.png")), log)
    app.step()                                 # takes the status + logs today
    for tab, name in enumerate(("mesh", "energy", "map", "setup")):
        img = screens.render(tab, app.status, mesh, log.last_days(7), c)
        frame = Image.new("RGB", (img.width * 2 + 24, img.height * 2 + 24), (40, 44, 52))
        frame.paste(img.convert("RGB").resize((img.width * 2, img.height * 2), Image.NEAREST),
                    (12, 12))
        frame.save(os.path.join(OUT, f"pi_{tab + 1}_{name}.png"))
    # Button press from the Pico moves to the next tab.
    pico.queue.append({"t": "button", "action": "next_tab"})
    app.step()
    assert app.tab == 1
    # A "set" from pps-cli is forwarded to the Pico.
    app.command({"cmd": "set", "key": "reserve", "value": 30})
    assert pico.sent[-1] == {"t": "set", "key": "reserve", "value": 30}


def main():
    os.makedirs(OUT, exist_ok=True)
    statuses, decisions = pico_screens()
    print("assist 12.4 mph A2 ->", round(decisions[0].assist_amps, 1), "A")
    print("harvest H2         ->", decisions[1].regen_amps, "A regen")
    print("below reserve      ->", decisions[2].assist_amps, "A,", decisions[2].warnings)
    print("wings up           ->", decisions[3].assist_amps, "A,", decisions[3].warnings)
    pi_screens(statuses[0])
    print("pictures in", OUT)
    for f in sorted(os.listdir(OUT)):
        print("  ", f)


if __name__ == "__main__":
    main()
