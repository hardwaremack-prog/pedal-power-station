# Pedal Power Station - Pico 2 main loop (MicroPython).
#
# The Pico is always on. Every 100 ms it reads the sensors, applies the riding and safety rules,
# tells the motor controller what to do and switches the outputs. Once a second it redraws the
# status screen; every 2 s it sends a status line to the Pi if the Pi is awake.
#
# If anything in the loop throws, assist and regen are zeroed first, then the error is logged.
# A hardware watchdog resets the Pico if the loop ever stops running.

import time
from machine import Pin, I2C, SPI, UART, ADC, PWM, WDT

import config as cfg
import ina2xx
import ds3231
import sharp_lcd
import motor as motor_mod
import rules
import energy as energy_mod
import buttons as btn_mod
import link as link_mod
import pipower
import status
import store
import ui

# ------------------------------------------------------------------ hardware
i2c = I2C(0, sda=Pin(cfg.PIN_I2C_SDA), scl=Pin(cfg.PIN_I2C_SCL), freq=400_000)
sensors = {}
for name, (addr, chip, shunt, amax) in cfg.SENSORS.items():
    try:
        sensors[name] = ina2xx.make(i2c, addr, chip, shunt, amax)
    except OSError:
        print("sensor missing:", name, hex(addr))
rtc = ds3231.DS3231(i2c, cfg.RTC_ADDR)

spi = SPI(0, baudrate=2_000_000, sck=Pin(cfg.PIN_LCD_SCK), mosi=Pin(cfg.PIN_LCD_MOSI))
lcd = sharp_lcd.SharpLCD(spi, Pin(cfg.PIN_LCD_CS, Pin.OUT), Pin(cfg.PIN_LCD_DISP, Pin.OUT))
frontlight = PWM(Pin(cfg.PIN_FRONTLIGHT))
frontlight.freq(1000)

motor = motor_mod.Motor(UART(1, cfg.MOTOR_BAUD, tx=Pin(cfg.PIN_MOTOR_UART_TX),
                             rx=Pin(cfg.PIN_MOTOR_UART_RX)), cfg)
pi_link = link_mod.Link(UART(0, 115200, tx=Pin(cfg.PIN_PI_UART_TX), rx=Pin(cfg.PIN_PI_UART_RX)))

out_pins = {
    "usb": Pin(cfg.PIN_OUT_USB, Pin.OUT, value=0),
    "out_13v8": Pin(cfg.PIN_OUT_13V8, Pin.OUT, value=0),
    "pi": Pin(cfg.PIN_OUT_PI, Pin.OUT, value=0),
    "lights": Pin(cfg.PIN_OUT_LIGHTS, Pin.OUT, value=0),
}
dump_pin = Pin(cfg.PIN_DUMP_LOAD, Pin.OUT, value=0)
btn_pins = {
    "mode": Pin(cfg.PIN_BTN_MODE, Pin.IN, Pin.PULL_UP),
    "minus": Pin(cfg.PIN_BTN_MINUS, Pin.IN, Pin.PULL_UP),
    "plus": Pin(cfg.PIN_BTN_PLUS, Pin.IN, Pin.PULL_UP),
}
brake_pin = Pin(cfg.PIN_BRAKE, Pin.IN, Pin.PULL_UP)
wings_pin = Pin(cfg.PIN_WINGS_LOCKED, Pin.IN, Pin.PULL_UP)
pi_halted_pin = Pin(cfg.PIN_PI_HALTED, Pin.IN, Pin.PULL_DOWN)
light_adc = ADC(Pin(cfg.PIN_LIGHT_SENSOR))

# ------------------------------------------------------------------ state
saved = store.load()
energy = energy_mod.Energy(cfg)
energy.load_dict(saved.get("energy", {}))
for key, attr in (("reserve", "RESERVE_PCT"), ("speed_cap", "SPEED_CAP_MPH"),
                  ("dusk_on", "DUSK_ON")):
    if key in saved.get("settings", {}):
        setattr(cfg, attr, saved["settings"][key])
cfg.SPEED_FADE_START_MPH = cfg.SPEED_CAP_MPH - 1.0

st = {"mode": "neutral", "level": 0, "ride_mode": "neutral"}
user_outputs = {"usb": True, "out_13v8": False}   # what the rider asked for
outs = {"usb": False, "out_13v8": False, "lights": False}
outputs_ok = True
buttons = btn_mod.Buttons()
pip = pipower.PiPower(cfg)
last = {"screen": 0, "pi": 0, "save": 0}
decision = rules.Decision()


def read_all():
    r = {}
    for name in cfg.SENSORS:
        s = sensors.get(name)
        try:
            r[name + "_v"] = s.volts() if s else 0.0
            r[name + "_a"] = s.amps() if s else 0.0
        except OSError:
            r[name + "_v"] = r[name + "_a"] = 0.0
    r["speed_mph"] = motor.poll()
    return r


def now_tuple():
    try:
        return rtc.now()
    except OSError:
        return (2026, 1, 1, 0, 0, 0, 1)


def save_state():
    store.save({"energy": energy.to_dict(), "settings": {
        "reserve": cfg.RESERVE_PCT, "speed_cap": cfg.SPEED_CAP_MPH, "dusk_on": cfg.DUSK_ON}})


def handle_pi_messages(now):
    for m in pi_link.poll():
        t = m.get("t")
        if t == "set":
            v = link_mod.validate_set(m.get("key"), m.get("value"))
            if v is None:
                continue
            k = m["key"]
            if k == "reserve":
                cfg.RESERVE_PCT = v
            elif k == "speed_cap":
                cfg.SPEED_CAP_MPH = v
                cfg.SPEED_FADE_START_MPH = v - 1.0
            elif k == "dusk_on":
                cfg.DUSK_ON, cfg.DUSK_OFF = v, v + 0.08
            elif k in user_outputs:
                user_outputs[k] = bool(v)
            save_state()
        elif t == "time":
            try:
                rtc.set(*m["value"])
            except (KeyError, TypeError, OSError):
                pass
        elif t == "sleep":
            if pip.sleep(now):
                pi_link.send({"t": "shutdown"})


def loop_once(now, dt_s):
    global decision, outputs_ok
    r = read_all()
    st["braking"] = brake_pin.value() == 0
    st["wings_locked"] = wings_pin.value() == 0

    y, mo, d = now_tuple()[:3]
    energy.new_day("%04d-%02d-%02d" % (y, mo, d))
    energy.update(dt_s, r, st["mode"], r["speed_mph"])

    # Buttons -> mode/level and Pi power.
    pressed = {n: p.value() == 0 for n, p in btn_pins.items()}
    for action in btn_mod.handle(buttons.update(now, pressed), st, rules.MAX_LEVEL):
        if action == "pi_wake_or_next":
            if not pip.wake(now):
                pi_link.send({"t": "button", "action": "next_tab"})
        elif action == "pi_sleep" and pip.sleep(now):
            pi_link.send({"t": "shutdown"})

    # Rules -> motor + dump load.
    decision = rules.decide(rules.Inputs(
        st["mode"], st["level"], r["speed_mph"], energy.soc_pct,
        st["braking"], st["wings_locked"], energy.pack_full), cfg)
    motor.apply(decision.assist_amps, decision.regen_amps)
    dump_pin.value(1 if decision.dump_load else 0)

    # Outputs.
    outputs_ok = rules.outputs_allowed(energy.soc_pct, outputs_ok, cfg)
    outs["usb"] = outputs_ok and user_outputs["usb"]
    outs["out_13v8"] = outputs_ok and user_outputs["out_13v8"]
    outs["lights"] = rules.lights_wanted(light_adc.read_u16() / 65535, outs["lights"], cfg)
    out_pins["usb"].value(outs["usb"])
    out_pins["out_13v8"].value(outs["out_13v8"])
    out_pins["lights"].value(outs["lights"])
    frontlight.duty_u16(9000 if outs["lights"] else 0)

    if not outputs_ok and pip.sleep(now):
        pi_link.send({"t": "shutdown"})
    out_pins["pi"].value(1 if pip.update(now, pi_halted_pin.value()) else 0)

    handle_pi_messages(now)

    # Screen, Pi status, saving.
    if time.ticks_diff(now, last["screen"]) >= cfg.SCREEN_MS:
        s = status.build(cfg, st, r, energy, decision, outs, pip.rail_on, motor.safe_mode,
                         now_tuple())
        ui.render(lcd, s)
        lcd.show()       # also flips the panel's VCOM, which it needs about once a second
        last["screen"] = now
        if pip.running and time.ticks_diff(now, last["pi"]) >= cfg.PI_STATUS_MS:
            pi_link.send(s)
            last["pi"] = now
    if time.ticks_diff(now, last["save"]) >= cfg.SAVE_MS:
        save_state()
        last["save"] = now


def main():
    if motor.safe_mode:
        print("motor controller in SAFE MODE (registers not verified) - no assist/regen sent")
    wdt = WDT(timeout=4000)
    prev = time.ticks_ms()
    while True:
        now = time.ticks_ms()
        dt = time.ticks_diff(now, prev) / 1000
        prev = now
        try:
            loop_once(now, dt)
        except Exception as e:
            try:
                motor.stop()
            except Exception:
                pass
            print("loop error:", e)
        wdt.feed()
        spent = time.ticks_diff(time.ticks_ms(), now)
        time.sleep_ms(max(0, cfg.LOOP_MS - spent))


main()
