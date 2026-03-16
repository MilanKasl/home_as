# power_logic.py
import time


class PowerLogic:
    IDLE = 0
    RUN  = 1

    def __init__(
        self,
        batt_on=13.50,
        batt_off=13.40,
        batt_protect=13.20,
        power_max=1000,
        load_power=200,     # výkon zátěže (W)
        delay_on=300,       # s stabilní plná baterie
        delay_off=60        # 60 s podmínka vypnutí
    ):
        self.batt_on = batt_on
        self.batt_off = batt_off
        self.batt_protect = batt_protect
        self.power_max = power_max
        self.load_power = load_power

        self.delay_on_ms = delay_on * 1000
        self.delay_off_ms = delay_off * 1000

        self.state = self.IDLE
        self.timer = None

    def reset(self):
        self.state = self.IDLE
        self.timer = None

    def update(self, batt_v, pv_power, sun_ok=True):
        now = time.ticks_ms()

        # Tvrdá ochrana baterie: okamžité vypnutí vytěžování pod ochraným prahem.
        if batt_v <= self.batt_protect:
            self.state = self.IDLE
            self.timer = None
            return False

        # ================= IDLE =================
        if self.state == self.IDLE:
            if sun_ok and batt_v >= self.batt_on:
                if self.timer is None:
                    self.timer = now
                elif time.ticks_diff(now, self.timer) >= self.delay_on_ms:
                    # přechod rovnou do RUN (test odstraněn)
                    self.state = self.RUN
                    self.timer = None
                    return True
            else:
                self.timer = None

            return False

        # ================= RUN =================
        if self.state == self.RUN:

            if batt_v <= self.batt_off and pv_power < self.load_power:
                if self.timer is None:
                    self.timer = now
                elif time.ticks_diff(now, self.timer) >= self.delay_off_ms:
                    self.state = self.IDLE
                    self.timer = None
                    return False
            else:
                self.timer = None

            return True

        return False

    def pwm_value(self, pv_power):
        if pv_power <= self.load_power:
            return 0
        if pv_power >= self.power_max:
            return 65535
        if self.power_max <= self.load_power:
            return 0

        return int(
            (pv_power - self.load_power) * 65535 /
            (self.power_max - self.load_power)
        )
