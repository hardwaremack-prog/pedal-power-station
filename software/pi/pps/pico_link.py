"""Serial link to the always-on Pico. One JSON object per line (see pico/link.py)."""

import json
import logging

log = logging.getLogger(__name__)


class PicoLink:
    def __init__(self, port: str, baud: int):
        import serial  # pyserial
        self.ser = serial.Serial(port, baud, timeout=0)
        self.buf = b""

    def send(self, obj: dict) -> None:
        self.ser.write(json.dumps(obj).encode() + b"\n")

    def poll(self) -> list[dict]:
        data = self.ser.read(4096)
        if not data:
            return []
        self.buf += data
        out = []
        while b"\n" in self.buf:
            line, self.buf = self.buf.split(b"\n", 1)
            try:
                m = json.loads(line)
            except ValueError:
                log.debug("bad line from pico: %r", line[:80])
                continue
            if isinstance(m, dict):
                out.append(m)
        if len(self.buf) > 65536:
            self.buf = b""
        return out


class FakePico:
    """Stand-in used by the simulator and tests."""

    def __init__(self, statuses: list[dict] | None = None):
        self.sent: list[dict] = []
        self.queue = list(statuses or [])

    def send(self, obj: dict) -> None:
        self.sent.append(obj)

    def poll(self) -> list[dict]:
        out, self.queue = self.queue, []
        return out
