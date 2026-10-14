"""Tests for the Pi app (no hardware needed)."""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "pi"))

from pps import cli, config, screens  # noqa: E402
from pps.app import App  # noqa: E402
from pps.display import PngDisplay  # noqa: E402
from pps.energylog import EnergyLog  # noqa: E402
from pps.mesh import FakeMesh, Message, Node  # noqa: E402
from pps.pico_link import FakePico  # noqa: E402

STATUS = {
    "t": "status", "time": [2026, 10, 13, 19, 8, 0, 2], "mode": "station", "level": 3,
    "speed_cap": 15, "speed_mph": 0, "pedal_w": 140, "motor_w": 101, "solar_w": 18,
    "loads_w": 6, "net_w": 95, "battery_v": 40.1, "soc": 78.0, "reserve": 25,
    "pack_full": False, "hours_to_full": 1.2, "assist_miles": 28.0, "made_today_wh": 64,
    "today": {"solar": 41, "pedal": 23, "regen": 0, "used": 5, "assist": 0},
    "life": {"solar": 900, "pedal": 400, "regen": 50, "used": 300, "assist": 600,
             "assist_miles": 60},
    "lights": True, "usb": True, "out_13v8": False, "pi_on": True, "wings_locked": True,
    "braking": False, "safe_mode": True, "warnings": [],
}


class Clock:
    def __init__(self):
        self.t = 1_000_000.0

    def __call__(self):
        return self.t


def make_app(tmp_path, **cfg_kw):
    clock = Clock()
    cfg = config.Config(display="png", **cfg_kw)
    pico = FakePico([dict(STATUS)])
    mesh = FakeMesh([Message(clock.t, "RAY", "hello")], [Node("Ray", "RAY", 42.38, -83.05, 0)],
                    me=(42.381, -83.051))
    app = App(cfg, pico, mesh, PngDisplay(str(tmp_path / "s.png")),
              EnergyLog(str(tmp_path / "e.db")), clock=clock)
    return app, pico, mesh, clock


def test_status_logged_and_drawn(tmp_path):
    app, pico, mesh, clock = make_app(tmp_path)
    app.step()
    assert app.status["soc"] == 78
    assert (tmp_path / "s.png").exists()
    days = app.log.last_days()
    assert days[-1]["day"] == "2026-10-13" and days[-1]["solar"] == 41


def test_energy_log_keeps_max(tmp_path):
    log = EnergyLog(str(tmp_path / "e.db"))
    log.record("2026-10-13", {"solar": 10})
    log.record("2026-10-13", {"solar": 30})
    log.record("2026-10-13", {"solar": 5})      # e.g. after a Pico restart mid-day
    assert log.last_days()[0]["solar"] == 30


def test_next_tab_and_shutdown(tmp_path):
    app, pico, mesh, clock = make_app(tmp_path)
    app.step()
    pico.queue.append({"t": "button", "action": "next_tab"})
    app.step()
    assert app.tab == 1
    pico.queue.append({"t": "shutdown"})
    app.step()
    assert app.shutdown_requested


def test_commands(tmp_path):
    app, pico, mesh, clock = make_app(tmp_path)
    app.step()
    assert app.command({"cmd": "status"})["status"]["soc"] == 78
    app.command({"cmd": "set", "key": "reserve", "value": 30})
    assert pico.sent[-1] == {"t": "set", "key": "reserve", "value": 30}
    assert app.command({"cmd": "send", "text": "hi"})["ok"]
    assert mesh.messages[-1].mine
    app.command({"cmd": "time"})
    assert pico.sent[-1]["t"] == "time" and len(pico.sent[-1]["value"]) == 7
    assert not app.command({"cmd": "bogus"})["ok"]


def test_idle_sleep(tmp_path):
    app, pico, mesh, clock = make_app(tmp_path, idle_sleep_minutes=10)
    app.step()
    clock.t += 9 * 60
    app.step()
    assert {"t": "sleep"} not in pico.sent
    clock.t += 2 * 60
    app.step()
    assert {"t": "sleep"} in pico.sent


def test_beacon(tmp_path):
    app, pico, mesh, clock = make_app(tmp_path, beacon_minutes=60, idle_sleep_minutes=0)
    app.step()
    clock.t += 3601
    app.step()
    assert mesh.messages[-1].text.startswith("Pedal Power Station: battery 78%")


def test_all_tabs_render_with_and_without_data():
    mesh = FakeMesh()
    cfg = config.Config()
    for tab in range(4):
        for st in (None, STATUS):
            img = screens.render(tab, st, mesh, [], cfg)
            assert img.size == (400, 300) and img.mode == "1"


def test_config_file(tmp_path):
    p = tmp_path / "c.toml"
    p.write_text('node_name = "Oak St bike"\nbeacon_minutes = 30\n[map]\nnorth = 42.4\n')
    c = config.load(str(p))
    assert c.node_name == "Oak St bike" and c.beacon_minutes == 30 and c.map.north == 42.4


def test_cli_usage():
    assert cli.main([]) == 0
    assert cli.main(["set", "reserve"]) == 2
