# relay_control.py
from machine import Pin

class RelayControl:
    def __init__(self, pin: Pin, active_high=True):
        """
        pin          - instance Pin(...)
        active_high  - True  = log.1 sepne relé
                       False = log.0 sepne relé (invertované moduly)
        """
        self.pin = pin
        self.active_high = active_high
        self.state = False

        # nastav pin jako výstup
        self.pin.init(Pin.OUT)

        # bezpečný start = relé vypnuto
        self.off()

    def on(self):
        if not self.state:
            self.state = True
            if self.active_high:
                self.pin.value(1)
            else:
                self.pin.value(0)

    def off(self):
        if self.state:
            self.state = False
            if self.active_high:
                self.pin.value(0)
            else:
                self.pin.value(1)

    def is_on(self):
        return self.state