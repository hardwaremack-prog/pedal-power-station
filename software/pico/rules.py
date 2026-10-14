# Safety and riding rules. Pure logic, no hardware, so it runs (and is tested) on a PC too.
#
# Every 100 ms main.py hands decide() the latest readings and gets back what the motor
# controller and the dump load should do, plus any warnings for the screen.

MODES = ("harvest", "neutral", "assist", "station")
MAX_LEVEL = {"harvest": 3, "neutral": 0, "assist": 3, "station": 5}


class Inputs:
    def __init__(self, mode="neutral", level=0, speed_mph=0.0, soc_pct=50.0,
                 braking=False, wings_locked=True, pack_full=False):
        self.mode = mode
        self.level = level
        self.speed_mph = speed_mph
        self.soc_pct = soc_pct
        self.braking = braking
        self.wings_locked = wings_locked
        self.pack_full = pack_full


class Decision:
    def __init__(self):
        self.assist_amps = 0.0
        self.regen_amps = 0.0
        self.dump_load = False
        self.warnings = []   # short strings, most important first


def clamp_level(mode, level):
    top = MAX_LEVEL.get(mode, 0)
    return max(0 if top == 0 else 1, min(top, level)) if top else 0


def speed_fade(speed, fade_start, cap):
    """1.0 below fade_start, falling straight to 0.0 at the cap."""
    if speed <= fade_start:
        return 1.0
    if speed >= cap:
        return 0.0
    return (cap - speed) / (cap - fade_start)


def decide(i, cfg):
    d = Decision()
    level = clamp_level(i.mode, i.level)

    # --- Sun Wings up: never help the bike move.
    if not i.wings_locked and i.mode != "station":
        d.warnings.append("LOCK WINGS")

    # --- Braking always wins: no assist, some regen (unless the pack is full).
    if i.braking and i.mode != "station":
        if not i.pack_full:
            d.regen_amps = cfg.BRAKE_REGEN_AMPS
        return d

    if i.mode == "assist":
        if not i.wings_locked:
            pass
        elif i.soc_pct <= cfg.RESERVE_PCT:
            d.warnings.append("RESERVE - PEDAL")
        else:
            fade = speed_fade(i.speed_mph, cfg.SPEED_FADE_START_MPH, cfg.SPEED_CAP_MPH)
            d.assist_amps = cfg.ASSIST_AMPS[level] * fade
            if fade == 0.0:
                d.warnings.append("15 MPH CAP")

    elif i.mode == "harvest":
        if i.pack_full:
            d.warnings.append("PACK FULL")
        else:
            d.regen_amps = cfg.HARVEST_AMPS[level]

    elif i.mode == "station":
        amps = cfg.STATION_AMPS[level]
        if i.pack_full:
            # Keep the pedal feel without pushing more into a full pack.
            d.dump_load = True
            d.warnings.append("PACK FULL")
        d.regen_amps = amps

    return d


def outputs_allowed(soc_pct, currently_on, cfg):
    """Hysteresis so outputs don't flicker on and off around the cut-off."""
    if currently_on:
        return soc_pct > cfg.OUTPUT_CUTOFF_PCT
    return soc_pct >= cfg.OUTPUT_RESUME_PCT


def lights_wanted(light_level, currently_on, cfg):
    if currently_on:
        return light_level < cfg.DUSK_OFF
    return light_level < cfg.DUSK_ON
