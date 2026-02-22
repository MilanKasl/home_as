# power_logic.py
import time


class PowerLogic:
    IDLE = 0
    TEST = 1
    RUN  = 2

    def __init__(
        self,
        batt_on=13.7,
        batt_off=13.4,
        power_max=1000,
        load_power=200,     # výkon zátěže (W)
        delay_on=300,       # x min stabilní plná baterie
        delay_off=30,       # 30 s podmínka vypnutí
        test_time=20,       # 20 s test přebytku
        margin=0.1          # povolený pokles napětí během testu
    ):
        self.batt_on = batt_on
        self.batt_off = batt_off
        self.power_max = power_max
        self.load_power = load_power

        self.delay_on_ms = delay_on * 1000
        self.delay_off_ms = delay_off * 1000
        self.test_time_ms = test_time * 1000

        self.margin = margin

        self.state = self.IDLE
        self.timer = None
        self.test_start_voltage = None

    def update(self, batt_v, pv_power):
        now = time.ticks_ms()

        # ================= IDLE =================
        if self.state == self.IDLE:

            if batt_v >= self.batt_on:
                if self.timer is None:
                    self.timer = now
                elif time.ticks_diff(now, self.timer) >= self.delay_on_ms:
                    # přechod do TEST
                    self.state = self.TEST
                    self.timer = now
                    self.test_start_voltage = batt_v
            else:
                self.timer = None

            return False

        # ================= TEST =================
        if self.state == self.TEST:

            # pokud napětí během testu výrazně klesne → konec
            if batt_v < self.test_start_voltage - self.margin:
                self.state = self.IDLE
                self.timer = None
                return False

            # pokud test doběhl
            if time.ticks_diff(now, self.timer) >= self.test_time_ms:
                # potvrzení přebytku
                if pv_power > self.load_power:
                    self.state = self.RUN
                    self.timer = None
                    return True
                else:
                    self.state = self.IDLE
                    self.timer = None
                    return False

            return True  # během testu drž zátěž zapnutou

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