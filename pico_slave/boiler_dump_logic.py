import time


class BoilerDumpLogic:
    STATE_BLOCKED = 0
    STATE_PROBING = 1
    STATE_HOLDING = 2
    STATE_BACKOFF = 3

    def __init__(
        self,
        heater_power_w=500,
        power_reserve_w=30,
        v_min=13.55,
        v_limit=13.70,
        v_critical=13.45,
        duty_step_up=0.05,
        duty_step_down=0.05,
        duty_step_fast_down=0.15,
        step_up_interval_ms=15000,
        step_down_interval_ms=5000,
        good_cycles_to_step_up=3,
        bad_cycles_to_step_down=1,
        battery_avg_alpha=0.2,
        battery_trend_epsilon=0.01,
    ):
        self.heater_power_w = heater_power_w
        self.power_reserve_w = power_reserve_w
        self.v_min = v_min
        self.v_limit = v_limit
        self.v_critical = v_critical
        self.duty_step_up = duty_step_up
        self.duty_step_down = duty_step_down
        self.duty_step_fast_down = duty_step_fast_down
        self.step_up_interval_ms = step_up_interval_ms
        self.step_down_interval_ms = step_down_interval_ms
        self.good_cycles_to_step_up = good_cycles_to_step_up
        self.bad_cycles_to_step_down = bad_cycles_to_step_down
        self.battery_avg_alpha = battery_avg_alpha
        self.battery_trend_epsilon = battery_trend_epsilon

        self.state = self.STATE_BLOCKED
        self.duty_current = 0.0
        self.battery_voltage_avg = None
        self.previous_voltage_avg = None
        self.good_cycles = 0
        self.bad_cycles = 0
        self.last_step_up_ms = None
        self.last_step_down_ms = None

    def reset(self):
        self.state = self.STATE_BLOCKED
        self.duty_current = 0.0
        self.good_cycles = 0
        self.bad_cycles = 0
        self.last_step_up_ms = None
        self.last_step_down_ms = None

    def update(self, now_ms, enabled, batt_v, pv_power):
        if self.battery_voltage_avg is None and batt_v is not None:
            self.battery_voltage_avg = batt_v
            self.previous_voltage_avg = batt_v
        elif batt_v is not None:
            self.previous_voltage_avg = self.battery_voltage_avg
            self.battery_voltage_avg = self.battery_voltage_avg + self.battery_avg_alpha * (
                batt_v - self.battery_voltage_avg
            )

        if not enabled or batt_v is None or pv_power is None:
            self.reset()
            return 0.0

        if self.battery_voltage_avg is not None and self.battery_voltage_avg < self.v_critical:
            self.reset()
            return 0.0

        battery_falling = False
        if self.battery_voltage_avg is not None and self.previous_voltage_avg is not None:
            battery_falling = (
                self.battery_voltage_avg
                < self.previous_voltage_avg - self.battery_trend_epsilon
            )

        dump_power = self.duty_current * self.heater_power_w
        pv_support_ok = pv_power >= (dump_power + self.power_reserve_w)

        if self.battery_voltage_avg is not None and self.battery_voltage_avg < self.v_min:
            self.state = self.STATE_BACKOFF
            self.good_cycles = 0
            self.bad_cycles = 0
            self.last_step_down_ms = now_ms
            self.duty_current = max(0.0, self.duty_current - self.duty_step_fast_down)
            return self.duty_current

        if battery_falling or not pv_support_ok:
            self.state = self.STATE_BACKOFF
            self.good_cycles = 0
            self.bad_cycles += 1
            if (
                self.bad_cycles >= self.bad_cycles_to_step_down
                and self._timer_elapsed(now_ms, self.last_step_down_ms, self.step_down_interval_ms)
            ):
                self.bad_cycles = 0
                self.last_step_down_ms = now_ms
                self.duty_current = max(0.0, self.duty_current - self.duty_step_down)
            return self.duty_current

        self.bad_cycles = 0
        self.good_cycles += 1

        if self.battery_voltage_avg is not None and self.battery_voltage_avg >= self.v_limit:
            self.good_cycles = max(self.good_cycles, self.good_cycles_to_step_up)

        if (
            self.good_cycles >= self.good_cycles_to_step_up
            and self._timer_elapsed(now_ms, self.last_step_up_ms, self.step_up_interval_ms)
        ):
            self.state = self.STATE_PROBING
            self.good_cycles = 0
            self.last_step_up_ms = now_ms
            self.duty_current = min(1.0, self.duty_current + self.duty_step_up)
            return self.duty_current

        self.state = self.STATE_HOLDING
        return self.duty_current

    @staticmethod
    def _timer_elapsed(now_ms, last_ms, interval_ms):
        if last_ms is None:
            return True
        return time.ticks_diff(now_ms, last_ms) >= interval_ms
