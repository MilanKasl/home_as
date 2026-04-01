from machine import Pin  # type: ignore
import time
import ubinascii
import onewire
import ds18x20


class DS18B20Sensor:
    def __init__(self, pin_num, sensor_rom_hex=None):
        self.bus = ds18x20.DS18X20(onewire.OneWire(Pin(pin_num)))
        self.sensor_rom_hex = sensor_rom_hex
        self.rom = None

    def _scan_rom(self):
        roms = self.bus.scan()
        if not roms:
            self.rom = None
            return None

        if self.sensor_rom_hex:
            wanted = self.sensor_rom_hex.lower()
            for rom in roms:
                if ubinascii.hexlify(rom).decode().lower() == wanted:
                    self.rom = rom
                    return rom
            self.rom = None
            return None

        self.rom = roms[0]
        return self.rom

    def read_temp(self):
        rom = self.rom or self._scan_rom()
        if rom is None:
            return None

        try:
            self.bus.convert_temp()
            time.sleep_ms(750)
            return self.bus.read_temp(rom)
        except Exception:
            self.rom = None
            return None
