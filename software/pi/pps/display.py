"""Output for the rendered screen: the Waveshare 4.2" e-paper, or a PNG file for testing."""

import logging

log = logging.getLogger(__name__)


class EPaper:
    """Waveshare 4.2" (400x300). Needs Waveshare's `waveshare_epd` Python library."""

    def __init__(self):
        try:
            from waveshare_epd import epd4in2_V2 as drv
        except ImportError:
            from waveshare_epd import epd4in2 as drv
        self.epd = drv.EPD()
        self.awake = False

    def show(self, img) -> None:
        if not self.awake:
            self.epd.init()
            self.awake = True
        self.epd.display(self.epd.getbuffer(img))
        # E-paper keeps the picture with no power; sleep the controller between updates.
        self.epd.sleep()
        self.awake = False

    def close(self) -> None:
        # Leave the last picture on the panel - it stays readable with the Pi switched off.
        try:
            if self.awake:
                self.epd.sleep()
        except Exception as e:
            log.debug("epaper close: %s", e)


class PngDisplay:
    def __init__(self, path: str):
        self.path = path

    def show(self, img) -> None:
        img.save(self.path)

    def close(self) -> None:
        pass


def make(cfg):
    if cfg.display == "epaper":
        try:
            return EPaper()
        except Exception as e:
            log.error("e-paper not available (%s); writing %s instead", e, cfg.png_path)
    return PngDisplay(cfg.png_path)
