"""Pedal Power Station - Pi Zero 2 W app.

Wakes when you hold PLUS on the handlebar, shows four tabs on the e-paper screen (hold PLUS
again for the next tab), logs energy history, and handles the LoRa mesh. When you hold MINUS,
or nothing has happened for a while, it shuts Linux down cleanly and the Pico cuts its power.
"""

import argparse
import json
import logging
import os
import socket
import subprocess
import time
from datetime import datetime

from . import config as config_mod
from . import display as display_mod
from . import screens
from .energylog import EnergyLog
from .mesh import Mesh
from .pico_link import PicoLink

log = logging.getLogger("pps")


class App:
    def __init__(self, cfg, pico, mesh, display, energy_log, clock=time.time):
        self.cfg, self.pico, self.mesh, self.display = cfg, pico, mesh, display
        self.log = energy_log
        self.clock = clock
        self.status: dict | None = None
        self.tab = 0
        self.dirty = True
        self.last_draw = 0.0
        self.last_touch = clock()
        self.last_beacon = clock()
        self.seen_msgs = 0
        self.shutdown_requested = False
        self.ctl = None

    # ------------------------------------------------------------------ control socket
    def open_control(self) -> None:
        self.ctl = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.ctl.bind(("127.0.0.1", self.cfg.control_port))
        self.ctl.setblocking(False)

    def _control(self) -> None:
        if not self.ctl:
            return
        while True:
            try:
                data, addr = self.ctl.recvfrom(4096)
            except BlockingIOError:
                return
            try:
                reply = self.command(json.loads(data))
            except Exception as e:
                reply = {"ok": False, "error": str(e)}
            self.ctl.sendto(json.dumps(reply).encode(), addr)

    def command(self, c: dict) -> dict:
        cmd = c.get("cmd")
        self.last_touch = self.clock()
        if cmd == "status":
            return {"ok": True, "status": self.status}
        if cmd == "set":
            self.pico.send({"t": "set", "key": c["key"], "value": c["value"]})
            return {"ok": True}
        if cmd == "send":
            return {"ok": self.mesh.send(c["text"])}
        if cmd == "tab":
            self.tab = int(c["value"]) % len(screens.TABS)
            self.dirty = True
            return {"ok": True}
        if cmd == "time":
            n = datetime.now()
            self.pico.send({"t": "time", "value": [n.year, n.month, n.day, n.hour, n.minute,
                                                    n.second, n.isoweekday()]})
            return {"ok": True}
        if cmd == "sleep":
            self.pico.send({"t": "sleep"})
            return {"ok": True}
        return {"ok": False, "error": f"unknown command {cmd!r}"}

    # ------------------------------------------------------------------ main loop
    def handle_pico(self, m: dict) -> None:
        t = m.get("t")
        if t == "status":
            old = self.status
            self.status = m
            y, mo, d = m["time"][:3]
            self.log.record(f"{y:04d}-{mo:02d}-{d:02d}", m["today"])
            if old is None or old["mode"] != m["mode"] or old["level"] != m["level"]:
                self.dirty = True
        elif t == "button" and m.get("action") == "next_tab":
            self.tab = (self.tab + 1) % len(screens.TABS)
            self.last_touch = self.clock()
            self.dirty = True
        elif t == "shutdown":
            self.shutdown_requested = True

    def step(self) -> None:
        for m in self.pico.poll():
            self.handle_pico(m)
        self._control()

        n = len(self.mesh.messages)
        if n != self.seen_msgs:
            self.seen_msgs = n
            self.last_touch = self.clock()     # a new message keeps the screen awake
            if self.tab == 0:
                self.dirty = True

        now = self.clock()
        if self.dirty or now - self.last_draw >= self.cfg.refresh_seconds:
            img = screens.render(self.tab, self.status, self.mesh, self.log.last_days(7), self.cfg)
            self.display.show(img)
            self.last_draw, self.dirty = now, False

        if self.cfg.beacon_minutes and self.status and \
                now - self.last_beacon >= self.cfg.beacon_minutes * 60:
            s = self.status
            self.mesh.send(f"{self.cfg.node_name}: battery {s['soc']:.0f}%, "
                           f"USB {'on' if s['usb'] else 'off'}, 13.8V "
                           f"{'on' if s['out_13v8'] else 'off'} - power to share")
            self.last_beacon = now

        if self.cfg.idle_sleep_minutes and now - self.last_touch > self.cfg.idle_sleep_minutes * 60:
            log.info("idle - asking the Pico to power us down")
            self.pico.send({"t": "sleep"})
            self.last_touch = now   # don't spam while waiting

    def run(self) -> None:
        self.pico.send({"t": "hello"})
        while not self.shutdown_requested:
            try:
                self.step()
            except Exception:
                log.exception("step failed")
            time.sleep(0.2)
        log.info("Pico asked us to shut down")
        self.display.close()
        self.mesh.close()
        subprocess.run(["systemctl", "poweroff"], check=False)


def main() -> None:
    ap = argparse.ArgumentParser(description="Pedal Power Station Pi app")
    ap.add_argument("--config", default=None)
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    cfg = config_mod.load(args.config)
    mesh = Mesh(cfg.mesh_port)
    if cfg.mesh_enabled:
        mesh.start()
    app = App(cfg, PicoLink(cfg.pico_port, cfg.pico_baud), mesh, display_mod.make(cfg),
              EnergyLog(os.path.join(cfg.data_dir, "energy.db")))
    app.open_control()
    app.run()


if __name__ == "__main__":
    main()
