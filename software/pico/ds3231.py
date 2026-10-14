# DS3231 battery-backed clock. Keeps the time while everything else is off.


def _bcd2(b):
    return (b >> 4) * 10 + (b & 0x0F)


def _2bcd(n):
    return ((n // 10) << 4) | (n % 10)


class DS3231:
    def __init__(self, i2c, addr=0x68):
        self.i2c, self.addr = i2c, addr

    def now(self):
        """(year, month, day, hour, minute, second, weekday 1-7)"""
        b = self.i2c.readfrom_mem(self.addr, 0x00, 7)
        return (2000 + _bcd2(b[6]), _bcd2(b[5] & 0x1F), _bcd2(b[4]),
                _bcd2(b[2] & 0x3F), _bcd2(b[1]), _bcd2(b[0] & 0x7F), b[3] & 0x07)

    def set(self, year, month, day, hour, minute, second, weekday=1):
        self.i2c.writeto_mem(self.addr, 0x00, bytes((
            _2bcd(second), _2bcd(minute), _2bcd(hour), weekday,
            _2bcd(day), _2bcd(month), _2bcd(year - 2000))))
