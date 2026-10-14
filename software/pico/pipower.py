# Powers the Pi Zero 2 W up and down without ever pulling the plug on a running Linux system.
#
#   off --wake--> on --sleep--> stopping --Pi GPIO26 high--> halted --2 s--> off
#                                   \--60 s timeout (Pi hung)-----------------^
#
# The Pi drives GPIO26 high once it has fully shut down (dtoverlay=gpio-poweroff,gpiopin=26).
# Pure logic: main.py turns the result into the Pi rail pin and the "shutdown" message.

OFF, ON, STOPPING, HALTED = "off", "on", "stopping", "halted"


class PiPower:
    def __init__(self, cfg):
        self.cfg = cfg
        self.state = OFF
        self.since = 0

    def _go(self, state, now):
        self.state, self.since = state, now

    def wake(self, now):
        if self.state == OFF:
            self._go(ON, now)
            return True
        return False

    def sleep(self, now):
        """Returns True if a shutdown request should be sent to the Pi now."""
        if self.state == ON:
            self._go(STOPPING, now)
            return True
        return False

    def update(self, now, pi_halted_pin):
        if self.state == STOPPING:
            if pi_halted_pin:
                self._go(HALTED, now)
            elif now - self.since > self.cfg.PI_SHUTDOWN_TIMEOUT_MS:
                self._go(OFF, now)          # Pi never answered; cut power anyway
        elif self.state == HALTED and now - self.since >= self.cfg.PI_HALT_GRACE_MS:
            self._go(OFF, now)
        return self.rail_on

    @property
    def rail_on(self):
        return self.state in (ON, STOPPING, HALTED)

    @property
    def running(self):
        return self.state == ON
