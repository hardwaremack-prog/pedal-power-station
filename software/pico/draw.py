# Drawing helpers that work on any MicroPython-style FrameBuffer (color 1 = ink).
# Big numbers are drawn as chunky seven-segment digits: crisp on a 1-bit reflective screen
# and readable at a glance while riding.

import framebuf

#           a  b  c  d  e  f  g
_SEGS = {
    "0": (1, 1, 1, 1, 1, 1, 0), "1": (0, 1, 1, 0, 0, 0, 0), "2": (1, 1, 0, 1, 1, 0, 1),
    "3": (1, 1, 1, 1, 0, 0, 1), "4": (0, 1, 1, 0, 0, 1, 1), "5": (1, 0, 1, 1, 0, 1, 1),
    "6": (1, 0, 1, 1, 1, 1, 1), "7": (1, 1, 1, 0, 0, 0, 0), "8": (1, 1, 1, 1, 1, 1, 1),
    "9": (1, 1, 1, 1, 0, 1, 1), "-": (0, 0, 0, 0, 0, 0, 1), " ": (0, 0, 0, 0, 0, 0, 0),
}


def seg_digit(fb, ch, x, y, w, h, t, c=1):
    s = _SEGS.get(ch)
    if s is None:
        return
    m = h // 2
    if s[0]: fb.fill_rect(x, y, w, t, c)                      # a
    if s[1]: fb.fill_rect(x + w - t, y + t, t, m - t, c)                   # b
    if s[2]: fb.fill_rect(x + w - t, y + m, t, h - m - t, c)               # c
    if s[3]: fb.fill_rect(x, y + h - t, w, t, c)               # d
    if s[4]: fb.fill_rect(x, y + m, t, h - m - t, c)                       # e
    if s[5]: fb.fill_rect(x, y + t, t, m - t, c)                           # f
    if s[6]: fb.fill_rect(x, y + m - t // 2, w, t, c)          # g


def seg_number(fb, text, x, y, w=30, h=54, t=7, gap=8, c=1):
    """Draw digits, '-', ' ' and '.'; returns the x just past the last character."""
    for ch in text:
        if ch == ".":
            fb.fill_rect(x, y + h - t, t, t, c)
            x += t + gap
        else:
            seg_digit(fb, ch, x, y, w, h, t, c)
            x += w + gap
    return x


_glyph_buf = bytearray(8)
_glyph = framebuf.FrameBuffer(_glyph_buf, 8, 8, framebuf.MONO_HLSB)


def text(fb, s, x, y, scale=1, c=1):
    """The built-in 8x8 font, optionally scaled up. Returns the x after the text."""
    if scale == 1:
        fb.text(s, x, y, c)
        return x + 8 * len(s)
    for ch in s:
        _glyph.fill(0)
        _glyph.text(ch, 0, 0, 1)
        for gy in range(8):
            row = _glyph_buf[gy]
            if not row:
                continue
            for gx in range(8):
                if row & (0x80 >> gx):
                    fb.fill_rect(x + gx * scale, y + gy * scale, scale, scale, c)
        x += 8 * scale
    return x


def text_right(fb, s, right_x, y, scale=1, c=1):
    text(fb, s, right_x - 8 * scale * len(s), y, scale, c)


def bar(fb, x, y, w, h, frac, tick_frac=None):
    fb.rect(x, y, w, h, 1)
    fill = int((w - 4) * max(0.0, min(1.0, frac)))
    fb.fill_rect(x + 2, y + 2, fill, h - 4, 1)
    if tick_frac is not None:
        tx = x + 2 + int((w - 4) * tick_frac)
        fb.fill_rect(tx - 1, y - 4, 3, h + 8, 1)
        fb.fill_rect(tx, y + 2, 1, h - 4, 0)


def chip(fb, s, x, y, on):
    w = 8 * len(s) + 10
    if on:
        fb.fill_rect(x, y, w, 15, 1)
        fb.text(s, x + 5, y + 4, 0)
    else:
        fb.rect(x, y, w, 15, 1)
        fb.text(s, x + 5, y + 4, 1)
    return x + w + 5
