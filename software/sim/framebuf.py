"""A small stand-in for MicroPython's `framebuf` module so the Pico screen code runs on a PC.

Only MONO_HLSB (what the Sharp LCD uses) is supported. Text uses MicroPython's own 8x8 font,
so the simulator's pictures match the real screen pixel for pixel.
"""

from font8x8 import FONT

MONO_HLSB = 3
MONO_HMSB = 4
MONO_VLSB = 0


class FrameBuffer:
    def __init__(self, buf, width, height, fmt, stride=None):
        if fmt != MONO_HLSB:
            raise NotImplementedError("simulator supports MONO_HLSB only")
        self.buf, self.width, self.height = buf, width, height
        self.stride = (width + 7) // 8

    def pixel(self, x, y, c=None):
        if not (0 <= x < self.width and 0 <= y < self.height):
            return None if c is not None else 0
        i = y * self.stride + (x >> 3)
        bit = 0x80 >> (x & 7)
        if c is None:
            return 1 if self.buf[i] & bit else 0
        if c:
            self.buf[i] |= bit
        else:
            self.buf[i] &= ~bit & 0xFF

    def fill(self, c):
        v = 0xFF if c else 0x00
        for i in range(len(self.buf)):
            self.buf[i] = v

    def fill_rect(self, x, y, w, h, c):
        for yy in range(max(0, y), min(self.height, y + h)):
            for xx in range(max(0, x), min(self.width, x + w)):
                self.pixel(xx, yy, c)

    def hline(self, x, y, w, c):
        self.fill_rect(x, y, w, 1, c)

    def vline(self, x, y, h, c):
        self.fill_rect(x, y, 1, h, c)

    def rect(self, x, y, w, h, c, f=False):
        if f:
            return self.fill_rect(x, y, w, h, c)
        self.hline(x, y, w, c)
        self.hline(x, y + h - 1, w, c)
        self.vline(x, y, h, c)
        self.vline(x + w - 1, y, h, c)

    def line(self, x0, y0, x1, y1, c):
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
        err = dx + dy
        while True:
            self.pixel(x0, y0, c)
            if x0 == x1 and y0 == y1:
                return
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def text(self, s, x, y, c=1):
        for ch in s:
            code = ord(ch)
            if code < 32 or code > 127:
                code = 127
            g = FONT[(code - 32) * 8:(code - 32) * 8 + 8]
            for col in range(8):
                bits = g[col]
                for row in range(8):
                    if bits & (1 << row):
                        self.pixel(x + col, y + row, c)
            x += 8
