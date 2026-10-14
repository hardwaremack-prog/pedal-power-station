# Save and load small JSON state on the Pico's flash (battery %, counters, settings).
# Writes go to a temp file first so a power cut mid-write can't corrupt the saved state.

import json
import os

PATH = "state.json"


def load():
    for p in (PATH, PATH + ".tmp"):
        try:
            with open(p) as f:
                return json.load(f)
        except (OSError, ValueError):
            pass
    return {}


def save(d):
    try:
        with open(PATH + ".tmp", "w") as f:
            json.dump(d, f)
        try:
            os.remove(PATH)
        except OSError:
            pass
        os.rename(PATH + ".tmp", PATH)
    except OSError:
        pass
