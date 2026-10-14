"""Tests for the Pico firmware's pure-logic parts, run on a PC with:  python3 -m pytest software/tests"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "sim"))
sys.path.insert(1, os.path.join(HERE, "..", "pico"))

import importlib  # noqa: E402

import buttons  # noqa: E402
import config as cfg  # noqa: E402
import energy  # noqa: E402
import ina2xx  # noqa: E402
import link  # noqa: E402
import motor  # noqa: E402
import pipower  # noqa: E402
import rules  # noqa: E402


def decide(**kw):
    return rules.decide(rules.Inputs(**kw), cfg)


# ------------------------------------------------------------------ rules
def test_assist_full_power_below_fade():
    d = decide(mode="assist", level=3, speed_mph=10, soc_pct=80)
    assert d.assist_amps == cfg.ASSIST_AMPS[3] and d.regen_amps == 0


def test_assist_fades_between_14_and_15():
    d = decide(mode="assist", level=2, speed_mph=14.5, soc_pct=80)
    assert abs(d.assist_amps - cfg.ASSIST_AMPS[2] * 0.5) < 1e-9


def test_no_assist_at_or_above_cap():
    for v in (15.0, 15.1, 22.0):
        d = decide(mode="assist", level=3, speed_mph=v, soc_pct=80)
        assert d.assist_amps == 0 and "15 MPH CAP" in d.warnings


def test_reserve_blocks_assist():
    d = decide(mode="assist", level=3, speed_mph=5, soc_pct=cfg.RESERVE_PCT)
    assert d.assist_amps == 0 and d.warnings == ["RESERVE - PEDAL"]
    d = decide(mode="assist", level=3, speed_mph=5, soc_pct=cfg.RESERVE_PCT + 0.1)
    assert d.assist_amps > 0


def test_brake_cuts_assist_and_regens():
    d = decide(mode="assist", level=3, speed_mph=10, soc_pct=80, braking=True)
    assert d.assist_amps == 0 and d.regen_amps == cfg.BRAKE_REGEN_AMPS


def test_brake_no_regen_when_full():
    d = decide(mode="assist", level=3, speed_mph=10, soc_pct=100, braking=True, pack_full=True)
    assert d.assist_amps == 0 and d.regen_amps == 0


def test_wings_up_blocks_assist():
    d = decide(mode="assist", level=3, speed_mph=5, soc_pct=90, wings_locked=False)
    assert d.assist_amps == 0 and d.warnings[0] == "LOCK WINGS"


def test_harvest_and_full_pack():
    assert decide(mode="harvest", level=2, soc_pct=50).regen_amps == cfg.HARVEST_AMPS[2]
    d = decide(mode="harvest", level=2, soc_pct=100, pack_full=True)
    assert d.regen_amps == 0 and "PACK FULL" in d.warnings


def test_station_full_pack_uses_dump_load():
    d = decide(mode="station", level=4, soc_pct=100, pack_full=True)
    assert d.dump_load and d.regen_amps == cfg.STATION_AMPS[4]
    assert not decide(mode="station", level=4, soc_pct=60).dump_load


def test_station_ignores_wings_and_never_assists():
    d = decide(mode="station", level=5, soc_pct=90, wings_locked=False)
    assert d.assist_amps == 0 and d.warnings == []


def test_neutral_does_nothing():
    d = decide(mode="neutral", level=3, speed_mph=10, soc_pct=80)
    assert d.assist_amps == 0 and d.regen_amps == 0


def test_outputs_hysteresis():
    assert rules.outputs_allowed(4, True, cfg)
    assert not rules.outputs_allowed(2.9, True, cfg)
    assert not rules.outputs_allowed(5, False, cfg)
    assert rules.outputs_allowed(6, False, cfg)


def test_lights_hysteresis():
    assert rules.lights_wanted(0.1, False, cfg)
    assert not rules.lights_wanted(0.2, False, cfg)
    assert rules.lights_wanted(0.2, True, cfg)
    assert not rules.lights_wanted(0.3, True, cfg)


# ------------------------------------------------------------------ energy
def R(bv=40.0, ba=0.0, solar_w=0.0, motor_w=0.0, loads_w=0.0):
    return {"battery_v": bv, "battery_a": ba, "solar_v": bv, "solar_a": solar_w / bv,
            "motor_v": bv, "motor_a": motor_w / bv, "loads_v": bv, "loads_a": loads_w / bv}


def test_coulomb_counting():
    e = energy.Energy(cfg, soc_pct=50)
    for _ in range(3600):                       # 1 hour at +1.5 A = 1.5 Ah = 10 % of 15 Ah
        e.update(1.0, R(ba=1.5), "station")
    assert abs(e.soc_pct - 60.0) < 0.01


def test_resync_to_full():
    e = energy.Energy(cfg, soc_pct=80)
    e.update(1.0, R(bv=cfg.CELL_FULL_V * cfg.PACK_CELLS, ba=0.1), "neutral")
    assert e.soc_pct == 100.0 and e.pack_full


def test_full_flag_clears():
    e = energy.Energy(cfg, soc_pct=100)
    e.update(1.0, R(), "neutral")
    assert e.pack_full
    e.soc_pct = 96
    e.update(1.0, R(), "neutral")
    assert not e.pack_full


def test_counters_and_assist_miles():
    e = energy.Energy(cfg, soc_pct=50)
    e.new_day("2026-10-13")
    for _ in range(3600):
        e.update(1.0, R(solar_w=50, motor_w=72, loads_w=6), "station")
    assert abs(e.today["solar"] - 50) < 0.01
    assert abs(e.today["pedal"] - 72) < 0.01
    assert abs(e.today["used"] - 6) < 0.01
    assert abs(e.made_today_wh() - 122) < 0.01
    e.new_day("2026-10-14")
    assert e.today["solar"] == 0 and abs(e.life["solar"] - 50) < 0.01


def test_assist_budget_numbers_match_spec():
    e = energy.Energy(cfg, soc_pct=100)
    # 75 % above the reserve of a 540 Wh pack = 405 Wh -> 40.5 miles at 10 Wh/mile
    assert abs(e.assist_miles_left() - 40.5) < 1e-9
    e.soc_pct = 20
    assert e.assist_miles_left() == 0
    # 100 W at the pedals is about 72 W into the pack (spec section 7)
    assert abs(e.pedal_watts(72) - 100) < 1e-9


def test_hours_to_full():
    e = energy.Energy(cfg, soc_pct=50)
    assert abs(e.hours_to_full(54) - 5.0) < 1e-9
    assert e.hours_to_full(0) is None


def test_save_roundtrip():
    e = energy.Energy(cfg, soc_pct=42)
    e.today["solar"] = 5
    e.day = "2026-10-13"
    f = energy.Energy(cfg)
    f.load_dict(e.to_dict())
    assert f.soc_pct == 42 and f.today["solar"] == 5 and f.day == "2026-10-13"


# ------------------------------------------------------------------ buttons
def press(b, name, t0, ms):
    ev = b.update(t0, {"mode": False, "minus": False, "plus": False, name: True})
    ev += b.update(t0 + ms, {"mode": False, "minus": False, "plus": False, name: True})
    ev += b.update(t0 + ms + 1, {"mode": False, "minus": False, "plus": False})
    return ev


def test_short_and_long_press():
    b = buttons.Buttons()
    assert press(b, "mode", 1000, 100) == [("short", "mode")]
    assert press(b, "plus", 5000, 1200) == [("long", "plus")]


def test_mode_cycle_and_station():
    st = {"mode": "harvest", "level": 1}
    buttons.handle([("short", "mode")], st, rules.MAX_LEVEL)
    assert st["mode"] == "neutral" and st["level"] == 0
    buttons.handle([("short", "mode")], st, rules.MAX_LEVEL)
    assert st["mode"] == "assist" and st["level"] == 1
    buttons.handle([("short", "plus")] * 5, st, rules.MAX_LEVEL)
    assert st["level"] == 3
    buttons.handle([("long", "mode")], st, rules.MAX_LEVEL)
    assert st["mode"] == "station"
    buttons.handle([("short", "mode")], st, rules.MAX_LEVEL)   # ignored in station
    assert st["mode"] == "station"
    buttons.handle([("long", "mode")], st, rules.MAX_LEVEL)
    assert st["mode"] == "assist"
    acts = buttons.handle([("long", "plus"), ("long", "minus")], st, rules.MAX_LEVEL)
    assert acts == ["pi_wake_or_next", "pi_sleep"]


# ------------------------------------------------------------------ Pi power
def test_pi_power_clean_shutdown():
    p = pipower.PiPower(cfg)
    assert p.wake(0) and p.rail_on
    assert p.sleep(10) and p.rail_on          # still powered while Linux shuts down
    assert p.update(5000, False)
    p.update(6000, True)                       # Pi reports halted
    assert p.rail_on
    assert not p.update(6000 + cfg.PI_HALT_GRACE_MS, True)


def test_pi_power_timeout():
    p = pipower.PiPower(cfg)
    p.wake(0)
    p.sleep(0)
    assert not p.update(cfg.PI_SHUTDOWN_TIMEOUT_MS + 1, False)


# ------------------------------------------------------------------ link, motor, sensors
def test_link_validation():
    assert link.validate_set("reserve", 5) == 10
    assert link.validate_set("speed_cap", 20) == 15      # can never raise above 15
    assert link.validate_set("reserve", "x") is None
    assert link.validate_set("assist_amps", 99) is None  # not settable from the Pi


def test_modbus_crc():
    # Standard example: read 1 holding register at 0 from slave 1 -> CRC 84 0A
    assert motor.frame(1, 0x03, 0, 1) == bytes.fromhex("010300000001840a")


def test_motor_safe_mode_never_writes():
    class UartSpy:
        def __init__(self):
            self.written = []

        def any(self):
            return 0

        def write(self, b):
            self.written.append(b)

    u = UartSpy()
    m = motor.Motor(u, cfg)
    assert m.safe_mode
    m.apply(12, 0)
    m.apply(0, 6)
    assert u.written == []


class FakeI2C:
    def __init__(self, regs):
        self.regs, self.writes = regs, []

    def writeto_mem(self, addr, reg, data):
        self.writes.append((reg, bytes(data)))

    def readfrom_mem(self, addr, reg, n):
        return self.regs[reg][:n]


def test_ina228_scaling():
    # 40.0 V on the bus: 40 / 195.3125e-6 = 204800 counts, shifted left 4
    vbus = (204800 << 4).to_bytes(3, "big")
    # -10 A with 40 A full scale: lsb = 40/2^19 -> -131072 counts (20-bit two's complement)
    cur = (((1 << 20) - 131072) << 4).to_bytes(3, "big")
    s = ina2xx.INA228(FakeI2C({0x05: vbus, 0x07: cur}), 0x40, 0.002, 40.0)
    assert abs(s.volts() - 40.0) < 1e-6
    assert abs(s.amps() + 10.0) < 1e-6


def test_ina226_scaling():
    s = ina2xx.INA226(FakeI2C({0x02: (9600).to_bytes(2, "big"),
                               0x04: (65536 - 1000).to_bytes(2, "big")}), 0x45, 0.01, 10.0)
    assert abs(s.volts() - 12.0) < 1e-9
    assert abs(s.amps() + 1000 * 10.0 / 32768) < 1e-9


def test_ui_renders_every_mode():
    import framebuf
    import status
    import ui
    for mode, level in (("station", 3), ("assist", 2), ("harvest", 1), ("neutral", 0)):
        e = energy.Energy(cfg, soc_pct=55)
        r = dict(R(motor_w=-50), speed_mph=12.0)
        d = decide(mode=mode, level=level, speed_mph=12, soc_pct=55)
        s = status.build(cfg, {"mode": mode, "level": level}, r, e, d,
                         {"lights": False, "usb": True, "out_13v8": False}, False, True,
                         (2026, 10, 13, 9, 5, 0, 2))
        buf = bytearray(400 * 240 // 8)
        ui.render(framebuf.FrameBuffer(buf, 400, 240, framebuf.MONO_HLSB), s)
        assert any(buf)
