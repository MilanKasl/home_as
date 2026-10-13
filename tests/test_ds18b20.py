"""1-Wire hotplug regression tests; no real sensors or serial ports accessed."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'rpi4'))
from app.ds18b20 import DS18B20


class SensorRecoveryTests(unittest.TestCase):
    SENSOR = '28-test-configured'

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.base = Path(directory.name)
        override = patch('app.ds18b20.BASE_DIR', str(self.base) + '/')
        override.start()
        self.addCleanup(override.stop)

    def sensor(self, sensor_id=None, temperature=42000, crc='YES'):
        directory = self.base / (sensor_id or self.SENSOR)
        directory.mkdir(exist_ok=True)
        file = directory / 'w1_slave'
        file.write_text('scratchpad crc=00 ' + crc + '\nscratchpad t=' + str(temperature) + '\n')
        return file

    def test_sensor_absent_at_start_recovers_without_recreating_reader(self):
        reader = DS18B20()
        self.assertIsNone(reader.read_temp(self.SENSOR))
        self.sensor(temperature=60312)
        self.assertEqual(reader.read_temp(self.SENSOR), 60.312)

    def test_disconnect_never_returns_cached_temperature_and_reconnect_recovers(self):
        file = self.sensor()
        reader = DS18B20()
        self.assertEqual(reader.read_temp(self.SENSOR), 42)
        file.unlink()
        file.parent.rmdir()
        self.assertIsNone(reader.read_temp(self.SENSOR))
        self.sensor(temperature=57812)
        self.assertEqual(reader.read_temp(self.SENSOR), 57.812)

    def test_other_sensor_cannot_replace_configured_id(self):
        reader = DS18B20()
        self.sensor(sensor_id='28-other', temperature=21000)
        self.assertIsNone(reader.read_temp(self.SENSOR))
        self.sensor(temperature=55000)
        self.assertEqual(reader.read_temp(self.SENSOR), 55)

    def test_returning_sensor_requires_valid_crc(self):
        reader = DS18B20()
        self.sensor(crc='NO')
        self.assertIsNone(reader.read_temp(self.SENSOR))
        self.sensor(temperature=25000)
        self.assertEqual(reader.read_temp(self.SENSOR), 25)


if __name__ == '__main__':
    unittest.main()
