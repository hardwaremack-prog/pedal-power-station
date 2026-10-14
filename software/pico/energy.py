# Battery state of charge and energy counters. Pure logic (runs on a PC too).
#
# LiFePO4 voltage is almost flat in the middle, so voltage alone can't give a percentage.
# Instead we count amp-hours in and out (coulomb counting) and re-sync to 100 % whenever the
# pack is clearly full: high voltage with only a trickle of charge current.


class Energy:
    def __init__(self, cfg, soc_pct=50.0):
        self.cfg = cfg
        self.soc_pct = soc_pct
        self.pack_full = False
        # Counters in Wh. "today" resets at midnight; "life" never does.
        self.today = {"solar": 0.0, "pedal": 0.0, "regen": 0.0, "used": 0.0, "assist": 0.0}
        self.life = {"solar": 0.0, "pedal": 0.0, "regen": 0.0, "used": 0.0, "assist": 0.0,
                     "assist_miles": 0.0}
        self.day = None

    # ------------------------------------------------------------ update every loop
    def update(self, dt_s, r, mode, speed_mph=0.0):
        """r = readings dict with *_v and *_a for battery/solar/motor/loads (amps signed)."""
        cfg = self.cfg
        hours = dt_s / 3600.0

        # Coulomb count on the battery sensor (+ = charging).
        self.soc_pct += r["battery_a"] * hours / cfg.PACK_AH * 100.0
        self.soc_pct = max(0.0, min(100.0, self.soc_pct))

        cell_v = r["battery_v"] / cfg.PACK_CELLS
        charging_trickle = 0 <= r["battery_a"] < cfg.FULL_SYNC_AMPS
        if cell_v >= cfg.CELL_FULL_V and charging_trickle:
            self.soc_pct = 100.0
        if cell_v <= cfg.CELL_EMPTY_V:
            self.soc_pct = min(self.soc_pct, 1.0)
        # Full flag with a little hysteresis so regen doesn't chatter.
        if self.soc_pct >= 99.5 or cell_v >= cfg.CELL_FULL_V + 0.02:
            self.pack_full = True
        elif self.soc_pct < 97.0:
            self.pack_full = False

        # Energy counters.
        solar_w = max(0.0, r["solar_v"] * r["solar_a"])
        motor_w = r["motor_v"] * r["motor_a"]
        loads_w = max(0.0, r["loads_v"] * r["loads_a"])
        self._add("solar", solar_w * hours)
        self._add("used", loads_w * hours)
        if motor_w > 0:
            self._add("pedal" if mode in ("harvest", "station") else "regen", motor_w * hours)
        else:
            self._add("assist", -motor_w * hours)
            if speed_mph > 0:
                self.life["assist_miles"] += speed_mph * hours

    def _add(self, key, wh):
        self.today[key] += wh
        self.life[key] += wh

    def new_day(self, day):
        if self.day is not None and day != self.day:
            for k in self.today:
                self.today[k] = 0.0
        self.day = day

    # ------------------------------------------------------------ derived numbers
    def made_today_wh(self):
        t = self.today
        return t["solar"] + t["pedal"] + t["regen"]

    def assist_wh_left(self):
        return max(0.0, (self.soc_pct - self.cfg.RESERVE_PCT) / 100.0 * self.cfg.PACK_WH)

    def assist_miles_left(self):
        return self.assist_wh_left() / self.cfg.WH_PER_MILE

    def hours_to_full(self, net_w):
        if net_w <= 1.0 or self.pack_full:
            return None
        return (100.0 - self.soc_pct) / 100.0 * self.cfg.PACK_WH / net_w

    def pedal_watts(self, motor_w):
        """Estimate of what your legs are putting in, from what reaches the pack."""
        return max(0.0, motor_w) / self.cfg.PEDAL_TO_PACK_EFF

    # ------------------------------------------------------------ saving
    def to_dict(self):
        return {"soc": self.soc_pct, "today": self.today, "life": self.life, "day": self.day}

    def load_dict(self, d):
        self.soc_pct = d.get("soc", self.soc_pct)
        self.today.update(d.get("today", {}))
        self.life.update(d.get("life", {}))
        self.day = d.get("day")
