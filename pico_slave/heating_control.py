import time


class RelayOutput:
    def __init__(self, pin, active_high=True):
        self.pin = pin
        self.active_high = active_high
        self.is_on = False
        self.off()

    def on(self):
        self.pin.value(1 if self.active_high else 0)
        self.is_on = True

    def off(self):
        self.pin.value(0 if self.active_high else 1)
        self.is_on = False


class HysteresisRelay:
    """Jedno relé řízené teplotou s bezpečným vypnutím při chybě vstupu."""

    def __init__(self, relay, on_temperature_c, off_temperature_c):
        self.relay = relay
        self.on_temperature_c = on_temperature_c
        self.off_temperature_c = off_temperature_c

    def update(self, temperature_c):
        if temperature_c is None:
            self.relay.off()
        elif temperature_c >= self.on_temperature_c:
            self.relay.on()
        elif temperature_c <= self.off_temperature_c:
            self.relay.off()
        return self.relay.is_on


class HeatingController:
    """Vzájemně blokované relé TUV a akumulační nádrže s hysterezí."""

    TUV = "tuv"
    AKU = "aku"
    MODE_AUTO = "A"
    MODE_MANUAL_TUV = "T"
    MODE_MANUAL_AKU = "K"
    MODE_OFF = "0"

    def __init__(
        self,
        tuv_relay,
        aku_relay,
        start_hour,
        end_hour,
        tuv_on_c,
        tuv_off_c,
        aku_on_c,
        aku_off_c,
        switch_delay_ms,
        manual_command_timeout_ms,
    ):
        self.tuv_relay = tuv_relay
        self.aku_relay = aku_relay
        self.start_hour = start_hour
        self.end_hour = end_hour
        self.tuv_on_c = tuv_on_c
        self.tuv_off_c = tuv_off_c
        self.aku_on_c = aku_on_c
        self.aku_off_c = aku_off_c
        self.switch_delay_ms = switch_delay_ms
        self.manual_command_timeout_ms = manual_command_timeout_ms

        self.active = None
        self.pending = None
        self.switch_at = None
        self.mode = self.MODE_AUTO
        self.last_manual_command = None
        self.manual_blocked_reason = None
        self.reason = "START"
        self.window_active = False
        self.tuv_call = False
        self.aku_call = False
        self._all_off()

    def _all_off(self):
        self.tuv_relay.off()
        self.aku_relay.off()

    def _in_window(self, hour, minute):
        current = hour * 60 + minute
        return self.start_hour * 60 <= current < self.end_hour * 60

    def is_in_window(self, rtc_time):
        return rtc_time is not None and self._in_window(rtc_time[0], rtc_time[1])

    def _reset_calls(self):
        self.tuv_call = False
        self.aku_call = False

    def stop(self):
        self._all_off()
        self.active = None
        self.pending = None
        self.switch_at = None
        self.window_active = False
        self._reset_calls()

    def set_mode(self, mode, now_ms):
        mode = str(mode).upper()
        if mode not in (
            self.MODE_AUTO,
            self.MODE_MANUAL_TUV,
            self.MODE_MANUAL_AKU,
            self.MODE_OFF,
        ):
            return False

        if mode != self.mode:
            self.manual_blocked_reason = None
            self._reset_calls()
            self.window_active = False

        self.mode = mode
        if mode in (self.MODE_MANUAL_TUV, self.MODE_MANUAL_AKU):
            self.last_manual_command = now_ms
        else:
            self.last_manual_command = None
        return True

    def _update_calls(self, tuv_c, aku_c):
        if not self.window_active:
            # Na začátku denního okna se TUV dohřívá až k cílové teplotě.
            self.tuv_call = tuv_c < self.tuv_off_c
            self.aku_call = aku_c < self.aku_off_c
            self.window_active = True
            return

        if tuv_c >= self.tuv_off_c:
            self.tuv_call = False
        elif tuv_c <= self.tuv_on_c:
            self.tuv_call = True

        if aku_c >= self.aku_off_c:
            self.aku_call = False
        elif aku_c <= self.aku_on_c:
            self.aku_call = True

    def _desired_output(self):
        if self.tuv_call:
            return self.TUV
        if self.aku_call:
            return self.AKU
        return None

    def _activate(self, output):
        self._all_off()
        if output == self.TUV:
            self.tuv_relay.on()
        elif output == self.AKU:
            self.aku_relay.on()
        self.active = output

    def _manual_desired_output(self, now_ms, tuv_c, aku_c):
        if self.last_manual_command is None or time.ticks_diff(
            now_ms, self.last_manual_command
        ) > self.manual_command_timeout_ms:
            self.manual_blocked_reason = "TIMEOUT"
            self.reason = "TIMEOUT"
            return None

        output = self.TUV if self.mode == self.MODE_MANUAL_TUV else self.AKU
        temperature = tuv_c if output == self.TUV else aku_c
        maximum = self.tuv_off_c if output == self.TUV else self.aku_off_c
        maximum_reason = "MAX_TUV" if output == self.TUV else "MAX_AKU"

        if temperature is None:
            self.reason = "NO_TEMP"
            return None
        if self.manual_blocked_reason:
            self.reason = self.manual_blocked_reason
            return None
        if temperature >= maximum:
            self.manual_blocked_reason = maximum_reason
            self.reason = maximum_reason
            return None

        self.reason = "MANUAL"
        return output

    def _apply_desired(self, now_ms, desired):
        # Během ochranné prodlevy zůstávají obě relé vypnutá.
        if self.switch_at is not None:
            self.pending = desired
            if time.ticks_diff(now_ms, self.switch_at) < 0:
                return None
            self.switch_at = None
            self._activate(self.pending)
            self.pending = None
            return self.active

        if desired == self.active:
            return self.active

        if self.active is None:
            self._activate(desired)
            return self.active

        # Přepnutí mezi relé vždy provede vypnutí a ochrannou prodlevu.
        self._all_off()
        self.active = None
        self.pending = desired
        self.switch_at = time.ticks_add(now_ms, self.switch_delay_ms)
        return None

    def update(self, now_ms, rtc_time, tuv_c, aku_c):
        if self.mode == self.MODE_OFF:
            self.stop()
            if self.reason != "TIMEOUT":
                self.reason = "OFF"
            return None

        if self.mode in (self.MODE_MANUAL_TUV, self.MODE_MANUAL_AKU):
            desired = self._manual_desired_output(now_ms, tuv_c, aku_c)
            if desired is None:
                self.stop()
                return None
            return self._apply_desired(now_ms, desired)

        if rtc_time is None:
            self.reason = "NO_TIME"
            self.stop()
            return None
        if tuv_c is None or aku_c is None:
            self.reason = "NO_TEMP"
            self.stop()
            return None
        if not self.is_in_window(rtc_time):
            self.reason = "OUTSIDE"
            self.stop()
            return None

        self._update_calls(tuv_c, aku_c)
        self.reason = "AUTO"
        return self._apply_desired(now_ms, self._desired_output())

    def diagnostics(self, now_ms):
        remaining_ms = 0
        if self.switch_at is not None:
            remaining_ms = max(0, time.ticks_diff(self.switch_at, now_ms))
        return {
            "active": self.active or "vypnuto",
            "pending": self.pending or "nic",
            "remaining_ms": remaining_ms,
            "tuv_relay": self.tuv_relay.is_on,
            "aku_relay": self.aku_relay.is_on,
            "tuv_call": self.tuv_call,
            "aku_call": self.aku_call,
            "mode": self.mode,
            "reason": self.reason,
        }
