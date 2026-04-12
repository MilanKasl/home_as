from machine import Pin  # type: ignore
import time


class SSRBurstControl:
    def __init__(self, pin: Pin, period_ms=1000, active_high=True):
        self.pin = pin
        self.period_ms = max(100, int(period_ms))
        self.active_high = active_high
        self.duty = 0.0
        self.cycle_start_ms = time.ticks_ms()

        self.pin.init(Pin.OUT)
        self.off()

    def set_duty(self, duty):
        self.duty = max(0.0, min(1.0, duty))

    def off(self):
        self._write(False)

    def update(self, now_ms=None):
        if now_ms is None:
            now_ms = time.ticks_ms()

        elapsed = time.ticks_diff(now_ms, self.cycle_start_ms)
        if elapsed < 0 or elapsed >= self.period_ms:
            cycles = max(1, elapsed // self.period_ms) if elapsed >= 0 else 1
            self.cycle_start_ms = time.ticks_add(self.cycle_start_ms, cycles * self.period_ms)
            elapsed = time.ticks_diff(now_ms, self.cycle_start_ms)

        if self.duty <= 0.0:
            self._write(False)
            return

        if self.duty >= 1.0:
            self._write(True)
            return

        on_time_ms = int(self.period_ms * self.duty)
        self._write(elapsed < on_time_ms)

    def _write(self, enabled):
        level = 1 if enabled else 0
        if not self.active_high:
            level = 0 if enabled else 1
        self.pin.value(level)
