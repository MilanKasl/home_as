from machine import PWM

class PWMControl:
    def __init__(self, pin, freq=1500):
        self.pwm = PWM(pin)
        self.pwm.freq(freq)
        self.pwm.duty_u16(0)

    def set(self, duty):  # duty: 0–65535
        duty = max(0, min(65535, duty))
        self.pwm.duty_u16(duty)

    def off(self):
        self.pwm.duty_u16(0)
