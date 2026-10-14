# Link to the regen-capable FOC motor controller (e.g. a Grin Phaserunner) over Modbus RTU.
#
# The controller does the real motor work and has its own 15 mph limit; the Pico only sets the
# assist ceiling and the regen current (which is the pedaling resistance) and double-checks speed.
#
# SAFE MODE: register numbers differ between controllers and firmware versions, so they are
# left blank in config.py. Until you fill them in from your controller's documentation and set
# MOTOR_REGISTERS_VERIFIED = True, this class never writes anything to the controller.

import time


def crc16(data):
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


def frame(slave, func, reg, value):
    body = bytes((slave, func, reg >> 8, reg & 0xFF, value >> 8, value & 0xFF))
    c = crc16(body)
    return body + bytes((c & 0xFF, c >> 8))


class Motor:
    def __init__(self, uart, cfg):
        self.uart, self.cfg = uart, cfg
        self.reg = cfg.MOTOR_REG
        self.writes_enabled = cfg.MOTOR_REGISTERS_VERIFIED and all(
            v is not None for v in self.reg.values())
        self.speed_mph = 0.0
        self.last_ok_ms = 0
        self._sent = {}
        if self.writes_enabled:
            self._write("speed_limit_x10_mph", int(cfg.SPEED_CAP_MPH * 10))

    @property
    def safe_mode(self):
        return not self.writes_enabled

    # ---------------------------------------------------------------- low level
    def _txrx(self, pkt, expect):
        while self.uart.any():
            self.uart.read()
        self.uart.write(pkt)
        deadline = time.ticks_add(time.ticks_ms(), 30)
        buf = b""
        while len(buf) < expect and time.ticks_diff(deadline, time.ticks_ms()) > 0:
            if self.uart.any():
                buf += self.uart.read()
        if len(buf) < expect or crc16(buf[:-2]) != (buf[-2] | (buf[-1] << 8)):
            return None
        return buf

    def _read(self, name):
        reg = self.reg.get(name)
        if reg is None:
            return None
        r = self._txrx(frame(self.cfg.MOTOR_SLAVE_ID, 0x03, reg, 1), 7)
        if r is None:
            return None
        self.last_ok_ms = time.ticks_ms()
        return (r[3] << 8) | r[4]

    def _write(self, name, value):
        if not self.writes_enabled:
            return False
        value = max(0, min(0xFFFF, int(value)))
        if self._sent.get(name) == value:
            return True
        r = self._txrx(frame(self.cfg.MOTOR_SLAVE_ID, 0x06, self.reg[name], value), 8)
        if r is not None:
            self._sent[name] = value
            self.last_ok_ms = time.ticks_ms()
        return r is not None

    # ---------------------------------------------------------------- used by main.py
    def poll(self):
        v = self._read("speed_x10_mph")
        if v is not None:
            self.speed_mph = v / 10.0
        return self.speed_mph

    def apply(self, assist_amps, regen_amps):
        # One of the two is always zero, so assist and regen never fight.
        if assist_amps > 0:
            regen_amps = 0
        self._write("assist_limit_amps", round(assist_amps * 10))
        self._write("regen_amps", round(regen_amps * 10))

    def stop(self):
        self._sent.clear()
        self.apply(0, 0)
