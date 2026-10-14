# INA228 (85 V) and INA226 (36 V) power monitors over I2C.
# Both give bus volts and signed shunt amps; the rest of the firmware doesn't care which.


class INA228:
    BUS_LSB = 195.3125e-6  # V per bit (20-bit value)

    def __init__(self, i2c, addr, shunt_ohms, max_amps):
        self.i2c, self.addr = i2c, addr
        self.current_lsb = max_amps / (1 << 19)
        shunt_cal = int(13107.2e6 * self.current_lsb * shunt_ohms)
        self._w16(0x00, 0x0000)                 # CONFIG: ADCRANGE = 0 (+-163.84 mV)
        self._w16(0x01, 0xFB6A)                 # ADC_CONFIG: continuous, 1052 us conversions, 16 avg
        self._w16(0x02, shunt_cal & 0x7FFF)     # SHUNT_CAL

    def _w16(self, reg, val):
        self.i2c.writeto_mem(self.addr, reg, bytes(((val >> 8) & 0xFF, val & 0xFF)))

    def _r24(self, reg):
        b = self.i2c.readfrom_mem(self.addr, reg, 3)
        return (b[0] << 16) | (b[1] << 8) | b[2]

    def volts(self):
        return (self._r24(0x05) >> 4) * self.BUS_LSB

    def amps(self):
        raw = self._r24(0x07) >> 4
        if raw & 0x80000:
            raw -= 1 << 20
        return raw * self.current_lsb


class INA226:
    BUS_LSB = 1.25e-3

    def __init__(self, i2c, addr, shunt_ohms, max_amps):
        self.i2c, self.addr = i2c, addr
        self.current_lsb = max_amps / 32768
        cal = int(0.00512 / (self.current_lsb * shunt_ohms))
        self._w16(0x00, 0x4527)   # 16 averages, 1.1 ms conversions, continuous shunt + bus
        self._w16(0x05, cal)

    def _w16(self, reg, val):
        self.i2c.writeto_mem(self.addr, reg, bytes(((val >> 8) & 0xFF, val & 0xFF)))

    def _r16s(self, reg):
        b = self.i2c.readfrom_mem(self.addr, reg, 2)
        v = (b[0] << 8) | b[1]
        return v - 65536 if v & 0x8000 else v

    def volts(self):
        return (self._r16s(0x02) & 0xFFFF) * self.BUS_LSB

    def amps(self):
        return self._r16s(0x04) * self.current_lsb


def make(i2c, addr, chip, shunt_ohms, max_amps):
    cls = INA228 if chip == "ina228" else INA226
    return cls(i2c, addr, shunt_ohms, max_amps)
