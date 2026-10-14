# Pico <-> Pi link: one JSON object per line over UART0 at 115200 baud.
#
# Pico -> Pi   {"t":"status", ...}           every 2 s while the Pi is powered
#              {"t":"button","action":"next_tab"}
#              {"t":"shutdown"}               please power off now
# Pi -> Pico   {"t":"hello"}                  Pi app started
#              {"t":"set","key":"reserve","value":30}
#              {"t":"time","value":[2026,10,13,21,40,0,2]}   set the clock (from GPS/NTP/mesh)
#              {"t":"sleep"}                  user asked the Pi to sleep from its own screen

import json

SETTABLE = {
    # key: (min, max) - anything else from the Pi is ignored
    "reserve": (10, 50),
    "dusk_on": (0.02, 0.6),
    "speed_cap": (5, 15),   # can only lower the cap, never raise it above 15
    "usb": (0, 1),
    "out_13v8": (0, 1),
}


class Link:
    def __init__(self, uart):
        self.uart = uart
        self.rx = b""

    def send(self, obj):
        try:
            self.uart.write(json.dumps(obj).encode() + b"\n")
        except Exception:
            pass

    def poll(self):
        msgs = []
        if self.uart.any():
            self.rx += self.uart.read()
            if len(self.rx) > 2048:          # junk on the line; start over
                self.rx = self.rx[-512:]
            while b"\n" in self.rx:
                line, self.rx = self.rx.split(b"\n", 1)
                try:
                    m = json.loads(line)
                    if isinstance(m, dict) and "t" in m:
                        msgs.append(m)
                except ValueError:
                    pass
        return msgs


def validate_set(key, value):
    if key not in SETTABLE:
        return None
    lo, hi = SETTABLE[key]
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return max(lo, min(hi, v))
