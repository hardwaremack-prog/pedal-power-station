# Sharp Memory LCD (LS027B7DH01, 2.7" 400x240) driver for MicroPython.
#
# The panel is reflective with no backlight and keeps its image on microwatts. It expects
# LSB-first SPI; the RP2 SPI only does MSB-first, so we pre-reverse the command and line
# address bits and keep the frame in MONO_HLSB (leftmost pixel in bit 7), which comes out of
# an MSB-first SPI in exactly the order the panel wants.

import framebuf

WIDTH, HEIGHT = 400, 240
CMD_WRITE = 0x80
CMD_VCOM = 0x40
CMD_CLEAR = 0x20


def _rev8(b):
    b = ((b & 0xF0) >> 4) | ((b & 0x0F) << 4)
    b = ((b & 0xCC) >> 2) | ((b & 0x33) << 2)
    return ((b & 0xAA) >> 1) | ((b & 0x55) << 1)


_REV_ADDR = bytes(_rev8(n) for n in range(256))


class SharpLCD(framebuf.FrameBuffer):
    """Draw with color 1 = black ink, 0 = white paper (inverted on the way out)."""

    def __init__(self, spi, cs, disp):
        self.spi, self.cs, self.disp = spi, cs, disp
        self.buf = bytearray(WIDTH * HEIGHT // 8)
        super().__init__(self.buf, WIDTH, HEIGHT, framebuf.MONO_HLSB)
        self.vcom = 0
        self.line = bytearray(2 + WIDTH // 8)
        self.cs.value(0)
        self.disp.value(1)
        self.clear_panel()

    def _toggle_vcom(self):
        # The panel needs its VCOM flipped about once a second or the image slowly burns in.
        self.vcom ^= CMD_VCOM
        return self.vcom

    def clear_panel(self):
        self.cs.value(1)
        self.spi.write(bytes((CMD_CLEAR | self._toggle_vcom(), 0x00)))
        self.cs.value(0)

    def show(self):
        bpl = WIDTH // 8
        line = self.line
        mv = memoryview(self.buf)
        self.cs.value(1)
        self.spi.write(bytes((CMD_WRITE | self._toggle_vcom(),)))
        for y in range(HEIGHT):
            line[0] = _REV_ADDR[y + 1]
            row = mv[y * bpl:(y + 1) * bpl]
            for x in range(bpl):
                line[1 + x] = row[x] ^ 0xFF     # 1 = ink -> 0 = black on the panel
            line[-1] = 0
            self.spi.write(line)
        self.spi.write(b"\x00")
        self.cs.value(0)
