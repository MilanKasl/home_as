from machine import I2C, Pin  # type: ignore


class DS3231:
    ADDRESS = 0x68
    STATUS_REGISTER = 0x0F
    OSF_MASK = 0x80

    def __init__(self, i2c_id, sda_pin, scl_pin, frequency=400000):
        self.i2c = I2C(
            i2c_id,
            sda=Pin(sda_pin),
            scl=Pin(scl_pin),
            freq=frequency,
        )

    @staticmethod
    def _bcd_to_int(value):
        return ((value >> 4) * 10) + (value & 0x0F)

    @staticmethod
    def _int_to_bcd(value):
        return ((value // 10) << 4) | (value % 10)

    def set_datetime(self, year, month, day, weekday, hour, minute, second=0):
        """Nastaví DS3231; weekday je 1–7, rok musí být v rozsahu 2000–2099."""
        if not (
            2000 <= year <= 2099
            and 1 <= month <= 12
            and 1 <= day <= 31
            and 1 <= weekday <= 7
            and 0 <= hour <= 23
            and 0 <= minute <= 59
            and 0 <= second <= 59
        ):
            raise ValueError("Neplatné datum nebo čas pro DS3231")

        values = bytes((
            self._int_to_bcd(second),
            self._int_to_bcd(minute),
            self._int_to_bcd(hour),
            self._int_to_bcd(weekday),
            self._int_to_bcd(day),
            self._int_to_bcd(month),
            self._int_to_bcd(year - 2000),
        ))
        self.i2c.writeto_mem(self.ADDRESS, 0x00, values)
        self.i2c.writeto_mem(self.ADDRESS, self.STATUS_REGISTER, b"\x00")

    def read_time(self):
        """Vrátí (hodina, minuta, sekunda), nebo None při chybě/neplatném čase."""
        try:
            status = self.i2c.readfrom_mem(self.ADDRESS, self.STATUS_REGISTER, 1)[0]
            if status & self.OSF_MASK:
                return None

            raw = self.i2c.readfrom_mem(self.ADDRESS, 0x00, 3)
            second = self._bcd_to_int(raw[0] & 0x7F)
            minute = self._bcd_to_int(raw[1] & 0x7F)

            hour_raw = raw[2]
            if hour_raw & 0x40:  # 12hodinový režim
                hour = self._bcd_to_int(hour_raw & 0x1F) % 12
                if hour_raw & 0x20:
                    hour += 12
            else:
                hour = self._bcd_to_int(hour_raw & 0x3F)

            if hour > 23 or minute > 59 or second > 59:
                return None
            return hour, minute, second
        except OSError:
            return None
