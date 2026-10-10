"""Ověření čtyřicetiminutové tolerance výpadků."""
import ast
import types
import unittest
from test_pump_control import ROOT, Relay, load, ticks_diff


class ControlTimeoutTests(unittest.TestCase):
    def setUp(self):
        self.config = load('slave_config', 'pico_slave/config.py')
        self.control = load('heating_control_timeout', 'pico_slave/heating_control.py')
        self.control.time = types.SimpleNamespace(ticks_diff=ticks_diff,
                                                  ticks_add=lambda a, b: a + b)

    def test_all_control_timeouts_are_forty_minutes(self):
        for name in ('TEMPERATURE_TIMEOUT_MS', 'TUV_TEMP_TIMEOUT_MS',
                     'MANUAL_COMMAND_TIMEOUT_MS', 'PUMP_COMMAND_TIMEOUT_MS'):
            self.assertEqual(getattr(self.config, name), 2400000)

    def test_pump_survives_short_command_loss(self):
        pump = self.control.PumpController(Relay(), 66, 65,
                                           self.config.PUMP_COMMAND_TIMEOUT_MS)
        pump.set_mode('M', 0)
        for now in (10001, 300000, 2399999):
            self.assertTrue(pump.update(now, None, False))
        self.assertFalse(pump.update(2400000, None, False))
        self.assertEqual(pump.mode, 'A')

    def test_both_heaters_survive_short_loss_but_respect_maximum(self):
        for mode, maximum, reason in (('K', 75, 'MAX_AKU'), ('T', 50, 'MAX_TUV')):
            for reach_maximum in (False, True):
                heat = self.control.HeatingController(
                    Relay(), Relay(), 7, 17, 47, 50, 70, 75, 5000,
                    self.config.MANUAL_COMMAND_TIMEOUT_MS)
                heat.set_mode(mode, 0)
                for now in (10001, 300000, 2399999):
                    self.assertIsNotNone(heat.update(now, None, 40, 60))
                if reach_maximum:
                    heat.update(2400000, None,
                                maximum if mode == 'T' else 40,
                                maximum if mode == 'K' else 60)
                    self.assertEqual(heat.reason, reason)
                else:
                    heat.update(2400001, None, 40, 60)
                    self.assertEqual(heat.reason, 'TIMEOUT')
                self.assertIsNone(heat.active)

    def test_invalid_average_does_not_refresh_or_clear_last_valid(self):
        tree = ast.parse((ROOT / 'pico_slave/main.py').read_text())
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                        and n.name == 'handle_pump_temperature')
        clock = types.SimpleNamespace(ticks_ms=lambda: 123)
        namespace = dict(time=clock, pump_average_temp=None,
                         last_pump_temperature_received=None)
        exec(compile(ast.Module(body=[function], type_ignores=[]), '<temperature>', 'exec'), namespace)
        receive = namespace['handle_pump_temperature']
        receive(None)
        self.assertIsNone(namespace['last_pump_temperature_received'])
        receive(66.5)
        clock.ticks_ms = lambda: 100000
        receive(None)
        self.assertEqual(namespace['pump_average_temp'], 66.5)
        self.assertEqual(namespace['last_pump_temperature_received'], 123)
        receive(65)
        self.assertEqual(namespace['pump_average_temp'], 65)
        self.assertEqual(namespace['last_pump_temperature_received'], 100000)

    def test_host_keeps_requests_for_forty_minutes_without_feedback(self):
        tree = ast.parse((ROOT / 'rpi4/app/gui.py').read_text())
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef))
        function = next(n for n in cls.body if isinstance(n, ast.FunctionDef)
                        and n.name == 'expire_manual_requests')
        clock = types.SimpleNamespace(monotonic=lambda: 0)
        namespace = {'time': clock}
        exec(compile(ast.Module(body=[function], type_ignores=[]), '<expiry>', 'exec'), namespace)
        for heating_mode in ('T', 'K'):
            gui = types.SimpleNamespace(desired_pump_mode='M',
                desired_heating_mode=heating_mode, last_pump_contact_ts=0,
                last_heating_contact_ts=0, CONTROL_LOSS_TIMEOUT=2400)
            for now in (11, 31, 301, 2399):
                clock.monotonic = lambda: now
                namespace['expire_manual_requests'](gui)
                self.assertEqual(gui.desired_pump_mode, 'M')
                self.assertEqual(gui.desired_heating_mode, heating_mode)
            clock.monotonic = lambda: 2400
            namespace['expire_manual_requests'](gui)
            self.assertEqual(gui.desired_pump_mode, 'A')
            self.assertEqual(gui.desired_heating_mode, '0')


if __name__ == '__main__':
    unittest.main()
