"""Settings for the Pi app, read from /etc/pps/config.toml (or a path given on the command line)."""

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class MapConfig:
    image: str = ""            # a PNG of your neighborhood (e.g. exported from OpenStreetMap)
    north: float = 0.0         # latitude of the image's top edge
    south: float = 0.0
    west: float = 0.0          # longitude of the image's left edge
    east: float = 0.0


@dataclass
class Config:
    pico_port: str = "/dev/serial0"
    pico_baud: int = 115200
    mesh_port: str = ""        # "" = auto-detect the Meshtastic node on USB
    mesh_enabled: bool = True
    beacon_minutes: int = 0    # 0 = off; otherwise broadcast "PPS: 78% ..." on the mesh this often
    node_name: str = "Pedal Power Station"
    data_dir: str = "/var/lib/pps"
    display: str = "epaper"    # "epaper" or "png" (writes screen.png - for testing)
    png_path: str = "screen.png"
    refresh_seconds: int = 60  # e-paper redraw interval when nothing changed
    idle_sleep_minutes: int = 10  # ask the Pico to power the Pi down after this long untouched (0 = never)
    control_port: int = 7341   # localhost UDP port for pps-cli
    map: MapConfig = field(default_factory=MapConfig)


def load(path: str | None = None) -> Config:
    cfg = Config()
    p = Path(path or "/etc/pps/config.toml")
    if not p.exists():
        return cfg
    data = tomllib.loads(p.read_text())
    for k, v in data.items():
        if k == "map" and isinstance(v, dict):
            cfg.map = MapConfig(**v)
        elif hasattr(cfg, k):
            setattr(cfg, k, v)
    return cfg
