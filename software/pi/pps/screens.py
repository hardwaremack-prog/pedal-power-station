"""Draws the four tabs of the handlebar e-paper screen (400 x 300, black and white)."""

import time
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont

W, H = 400, 300
TABS = ("Mesh", "Energy", "Map", "Setup")
INK, PAPER = 0, 255

_FONT_DIRS = ("/usr/share/fonts/truetype/dejavu/", "/usr/share/fonts/dejavu/",
              "/usr/share/fonts/TTF/")


def _font(size: int, bold: bool = False):
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    for d in _FONT_DIRS:
        try:
            return ImageFont.truetype(d + name, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


F = {"s": _font(12), "m": _font(15), "mb": _font(15, True), "l": _font(22, True),
     "xl": _font(34, True)}


def _header(d: ImageDraw.ImageDraw, tab: int) -> None:
    tw = W // len(TABS)
    for i, name in enumerate(TABS):
        x0 = i * tw
        if i == tab:
            d.rectangle([x0, 0, x0 + tw - 1, 26], fill=INK)
            d.text((x0 + tw // 2, 13), name, font=F["mb"], fill=PAPER, anchor="mm")
        else:
            d.rectangle([x0, 0, x0 + tw - 1, 26], outline=INK)
            d.text((x0 + tw // 2, 13), name, font=F["m"], fill=INK, anchor="mm")


def _footer(d, status: dict | None, mesh_online: bool) -> None:
    d.line([0, 276, W, 276], fill=INK)
    if not status:
        d.text((8, 288), "waiting for the Pico...", font=F["s"], fill=INK, anchor="lm")
        return
    mode = status["mode"].upper()
    if status["level"]:
        mode += f" {status['level']}"
    left = f"{status['soc']:.0f}%  {status['battery_v']:.1f}V  {mode}"
    d.text((8, 288), left, font=F["s"], fill=INK, anchor="lm")
    right = ("mesh ok" if mesh_online else "no mesh") + "  " + datetime.now().strftime("%H:%M")
    d.text((W - 8, 288), right, font=F["s"], fill=INK, anchor="rm")


def _wrap(d, text: str, font, width: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if d.textlength(trial, font=font) <= width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines or [""]


# ---------------------------------------------------------------------------- tabs
def draw_mesh(d, mesh) -> None:
    if not mesh.online:
        d.text((W // 2, 140), "Mesh node not connected", font=F["mb"], fill=INK, anchor="mm")
        d.text((W // 2, 164), mesh.error or "plug the LoRa node into the Pi's USB port",
               font=F["s"], fill=INK, anchor="mm")
        return
    y = 34
    msgs = list(mesh.messages)[-12:]
    if not msgs:
        d.text((W // 2, 140), "No messages yet", font=F["mb"], fill=INK, anchor="mm")
        d.text((W // 2, 162), "Your node is listening and relaying.", font=F["s"], fill=INK,
               anchor="mm")
        return
    blocks = []
    for m in reversed(msgs):          # newest first, fill downwards
        lines = _wrap(d, m.text, F["s"], W - 90)
        blocks.append((m, lines))
    for m, lines in blocks:
        h = 16 * len(lines) + 8
        if y + h > 272:
            break
        when = time.strftime("%H:%M", time.localtime(m.when))
        label = "me" if m.mine else m.sender[:8]
        d.text((8, y), label, font=F["mb"] if not m.mine else F["m"], fill=INK)
        d.text((8, y + 16), when, font=F["s"], fill=INK)
        for i, line in enumerate(lines):
            d.text((82, y + 1 + 16 * i), line, font=F["s"], fill=INK)
        y += max(h, 36)
        d.line([8, y - 4, W - 8, y - 4], fill=INK)


def draw_energy(d, status: dict | None, days: list[dict]) -> None:
    if not status:
        return
    t, life = status["today"], status["life"]
    made = t["solar"] + t["pedal"] + t["regen"]
    d.text((10, 34), "Made today", font=F["m"], fill=INK)
    d.text((10, 52), f"{made:.0f} Wh", font=F["xl"], fill=INK)
    rows = (("Sun", t["solar"]), ("Legs", t["pedal"]), ("Regen", t["regen"]),
            ("Assist used", t["assist"]), ("Devices used", t["used"]))
    for i, (k, v) in enumerate(rows):
        d.text((220, 36 + 17 * i), k, font=F["s"], fill=INK)
        d.text((392, 36 + 17 * i), f"{v:.0f} Wh", font=F["s"], fill=INK, anchor="ra")

    # Last 7 days: stacked bars, sun (outline) under legs+regen (solid).
    d.text((10, 128), "Last 7 days", font=F["mb"], fill=INK)
    x0, y0, bw, gap, hmax = 30, 248, 38, 14, 96
    top = max([d_["solar"] + d_["pedal"] + d_["regen"] for d_ in days] + [1.0])
    for i, day in enumerate(days[-7:]):
        x = x0 + i * (bw + gap)
        sun = day["solar"] / top * hmax
        legs = (day["pedal"] + day["regen"]) / top * hmax
        if sun >= 1:
            d.rectangle([x, y0 - sun, x + bw, y0], outline=INK, width=2)
        if legs >= 1:
            d.rectangle([x, y0 - sun - legs, x + bw, y0 - sun], fill=INK)
        d.text((x + bw // 2, y0 + 10), day["day"][5:], font=F["s"], fill=INK, anchor="mm")
    d.line([x0 - 6, y0, x0 + 7 * (bw + gap), y0], fill=INK)
    d.rectangle([250, 128, 262, 140], outline=INK, width=2)
    d.text((266, 134), "sun", font=F["s"], fill=INK, anchor="lm")
    d.rectangle([300, 128, 312, 140], fill=INK)
    d.text((316, 134), "legs", font=F["s"], fill=INK, anchor="lm")
    life_made = life["solar"] + life["pedal"] + life["regen"]
    d.text((10, 94), f"Lifetime: {life_made / 1000:.1f} kWh made", font=F["s"], fill=INK)
    d.text((10, 108), f"{life.get('assist_miles', 0):.0f} miles assisted", font=F["s"], fill=INK)


def draw_map(d, img: Image.Image, mesh, mapcfg) -> None:
    box = (8, 32, W - 8, 270)
    bw, bh = box[2] - box[0], box[3] - box[1]
    nodes = [n for n in mesh.nodes() if n.lat is not None]
    me = mesh.my_position()

    if mapcfg.image:
        try:
            base = Image.open(mapcfg.image).convert("L").resize((bw, bh))
            base = base.point(lambda v: 255 if v > 150 else 0, "1").convert("L")
            img.paste(base, box[:2])
            bounds = (mapcfg.north, mapcfg.south, mapcfg.west, mapcfg.east)
        except OSError:
            bounds = None
    else:
        bounds = None

    pts = [(n.lat, n.lon) for n in nodes] + ([me] if me else [])
    if bounds is None:
        if not pts:
            d.rectangle(box, outline=INK)
            d.text((W // 2, 140), "No positions yet", font=F["mb"], fill=INK, anchor="mm")
            d.text((W // 2, 162), "Nodes with GPS will appear here.", font=F["s"], fill=INK,
                   anchor="mm")
            return
        lats, lons = [p[0] for p in pts], [p[1] for p in pts]
        pad_lat = max(0.002, (max(lats) - min(lats)) * 0.15)
        pad_lon = max(0.002, (max(lons) - min(lons)) * 0.15)
        bounds = (max(lats) + pad_lat, min(lats) - pad_lat, min(lons) - pad_lon, max(lons) + pad_lon)
        # light grid so it still reads as a map
        for i in range(1, 6):
            gx = box[0] + bw * i // 6
            gy = box[1] + bh * i // 6
            for yy in range(box[1], box[3], 6):
                d.point((gx, yy), fill=INK)
            for xx in range(box[0], box[2], 6):
                d.point((xx, gy), fill=INK)
    d.rectangle(box, outline=INK, width=2)

    north, south, west, east = bounds

    def xy(lat, lon):
        x = box[0] + (lon - west) / ((east - west) or 1) * bw
        y = box[1] + (north - lat) / ((north - south) or 1) * bh
        return x, y

    for n in nodes:
        x, y = xy(n.lat, n.lon)
        if box[0] <= x <= box[2] and box[1] <= y <= box[3]:
            d.ellipse([x - 5, y - 5, x + 5, y + 5], fill=PAPER, outline=INK, width=2)
            d.text((x + 8, y), n.short, font=F["s"], fill=INK, anchor="lm")
    if me:
        x, y = xy(*me)
        d.polygon([(x, y - 9), (x + 8, y + 6), (x - 8, y + 6)], fill=INK)
        d.text((x + 10, y), "you", font=F["mb"], fill=INK, anchor="lm")
    d.text((box[2] - 6, box[3] - 6), f"{len(nodes)} nodes", font=F["s"], fill=INK, anchor="rd")


def draw_setup(d, status: dict | None, cfg) -> None:
    y = 36
    rows = [("Node name", cfg.node_name)]
    if status:
        rows += [
            ("Mode", f"{status['mode']} {status['level'] or ''}".strip()),
            ("Emergency reserve", f"{status['reserve']}%"),
            ("Speed cap", f"{status['speed_cap']} mph"),
            ("USB outputs", "on" if status["usb"] else "off"),
            ("13.8 V output", "on" if status["out_13v8"] else "off"),
            ("Lights", "on (dusk)" if status["lights"] else "off"),
            ("Sun Wings", "locked" if status["wings_locked"] else "UP - lock before riding"),
            ("Motor link", "SAFE MODE (registers not set)" if status["safe_mode"] else "active"),
        ]
    for k, v in rows:
        d.text((12, y), k, font=F["m"], fill=INK)
        d.text((W - 12, y), str(v), font=F["mb"], fill=INK, anchor="ra")
        y += 22
    d.text((12, 262), "Change with: pps-cli set reserve 30   (see README)", font=F["s"], fill=INK)


def render(tab: int, status, mesh, days, cfg) -> Image.Image:
    img = Image.new("L", (W, H), PAPER)
    d = ImageDraw.Draw(img)
    _header(d, tab)
    if tab == 0:
        draw_mesh(d, mesh)
    elif tab == 1:
        draw_energy(d, status, days)
    elif tab == 2:
        draw_map(d, img, mesh, cfg.map)
    else:
        draw_setup(d, status, cfg)
    _footer(d, status, mesh.online)
    return img.point(lambda v: 255 if v > 127 else 0).convert("1")
