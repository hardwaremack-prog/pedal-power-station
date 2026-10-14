# Three handlebar buttons: MODE, MINUS, PLUS. Short and long presses (pure logic).
#
#   MODE  short  Harvest -> Neutral -> Assist -> Harvest ...
#   MODE  long   Station mode on / off
#   - / + short  level down / up
#   PLUS  long   wake the big Pi screen, or next tab if it's already on
#   MINUS long   put the Pi to sleep (clean shutdown)

LONG_MS = 900
DEBOUNCE_MS = 30


class Buttons:
    NAMES = ("mode", "minus", "plus")

    def __init__(self):
        self.down_at = {n: None for n in self.NAMES}
        self.long_fired = {n: False for n in self.NAMES}
        self.last_change = {n: -10_000 for n in self.NAMES}
        self.state = {n: False for n in self.NAMES}

    def update(self, now_ms, pressed):
        """pressed: dict name -> bool. Returns a list of ('short'|'long', name) events."""
        events = []
        for n in self.NAMES:
            p = pressed[n]
            if p != self.state[n]:
                if now_ms - self.last_change[n] < DEBOUNCE_MS:
                    continue
                self.last_change[n] = now_ms
                self.state[n] = p
                if p:
                    self.down_at[n] = now_ms
                    self.long_fired[n] = False
                else:
                    if self.down_at[n] is not None and not self.long_fired[n]:
                        events.append(("short", n))
                    self.down_at[n] = None
            elif p and self.down_at[n] is not None and not self.long_fired[n]:
                if now_ms - self.down_at[n] >= LONG_MS:
                    self.long_fired[n] = True
                    events.append(("long", n))
        return events


RIDE_CYCLE = ("harvest", "neutral", "assist")


def handle(events, st, max_level):
    """Apply button events to st (a dict with mode, level, ride_mode). Returns Pi actions."""
    actions = []
    for kind, name in events:
        if name == "mode" and kind == "short":
            if st["mode"] == "station":
                continue
            i = RIDE_CYCLE.index(st["mode"]) if st["mode"] in RIDE_CYCLE else 0
            st["mode"] = RIDE_CYCLE[(i + 1) % len(RIDE_CYCLE)]
            st["level"] = 1 if max_level[st["mode"]] else 0
        elif name == "mode" and kind == "long":
            if st["mode"] == "station":
                st["mode"] = st.get("ride_mode", "neutral")
                st["level"] = 1 if max_level[st["mode"]] else 0
            else:
                st["ride_mode"] = st["mode"]
                st["mode"] = "station"
                st["level"] = 2
        elif name in ("minus", "plus") and kind == "short":
            top = max_level[st["mode"]]
            if top:
                step = 1 if name == "plus" else -1
                st["level"] = max(1, min(top, st["level"] + step))
        elif name == "plus" and kind == "long":
            actions.append("pi_wake_or_next")
        elif name == "minus" and kind == "long":
            actions.append("pi_sleep")
    return actions
