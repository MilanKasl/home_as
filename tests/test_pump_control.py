"""Host tests: python3 -m unittest discover -s tests -v"""
import ast
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def ticks_diff(a, b):
    period = 1 << 30
    return (a - b + period // 2) % period - period // 2


class Relay:
    is_on = False

    def on(self):
        self.is_on = True

    def off(self):
        self.is_on = False


class PumpTests(unittest.TestCase):
    def setUp(self):
        self.control = load('pump_control', 'pico_slave/heating_control.py')
        self.control.time = types.SimpleNamespace(ticks_diff=ticks_diff)
        self.relay = Relay()
        self.pump = self.control.PumpController(self.relay, 66, 65, 10000)

    def test_automatic_hysteresis_and_missing_inputs(self):
        for temperature, allowed, expected in (
            (65.999, True, False), (66, True, True), (65.5, True, True),
            (65, True, False), (70, False, False), (70, True, True),
            (None, True, False), (65.5, True, False),
        ):
            self.assertEqual(self.pump.update(0, temperature, allowed), expected)

    def test_manual_bypasses_temperature_and_window_and_expires(self):
        self.assertTrue(self.pump.set_mode('M', 0))
        self.assertTrue(self.pump.update(9999, None, False))
        self.assertFalse(self.pump.update(10000, None, False))
        self.assertEqual(self.pump.mode, 'A')

    def test_refresh_and_tick_wrap(self):
        start = (1 << 30) - 5000
        self.pump.set_mode('M', start)
        self.assertTrue(self.pump.update(1000, 20, False))
        self.pump.set_mode('M', 1000)
        self.assertTrue(self.pump.update(10999, 20, False))
        self.assertFalse(self.pump.update(11000, 20, False))

    def test_return_to_auto_does_not_latch_manual_run(self):
        self.pump.set_mode('M', 0)
        self.assertTrue(self.pump.update(1, 65.5, True))
        self.pump.set_mode('A', 2)
        self.assertFalse(self.pump.update(2, 65.5, True))
        self.pump.update(3, 66, True)
        self.pump.set_mode('M', 4)
        self.pump.update(5, 65.5, True)
        self.pump.set_mode('A', 6)
        self.assertTrue(self.pump.update(6, 65.5, True))

    def test_timeout_returns_to_warm_tank_automatic_run(self):
        self.pump.set_mode('M', 0)
        self.assertTrue(self.pump.update(10000, 70, True))
        self.assertEqual(self.pump.mode, 'A')
        self.assertFalse(self.pump.set_mode('invalid', 10001))
        self.assertEqual(self.pump.mode, 'A')


class UART:
    def __init__(self, data=b''):
        self.data = data
        self.sent = []

    def read(self, count=None):
        data, self.data = self.data[:count], self.data[count:] if count else b''
        return data

    def any(self):
        return len(self.data)

    def write(self, data):
        self.sent.append(data)


class ProtocolTests(unittest.TestCase):
    def test_command_round_trip_with_fragmentation(self):
        tree = ast.parse((ROOT / 'pico_master/main.py').read_text())
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                        and n.name == 'forward_host_commands')
        incoming, outgoing = UART(), UART()
        namespace = dict(host_uart_rx=incoming, uart_fve=outgoing,
                         host_rx_buffer='', last_host_rx_debug=0,
                         time=types.SimpleNamespace(ticks_ms=lambda: 1),
                         print=lambda *args: None)
        exec(compile(ast.Module(body=[function], type_ignores=[]), '<forward>', 'exec'), namespace)
        for fragment in (b'<PU', b'MP:M>\n       ', b'<PUMP:X><HEAT:K><TEMP:42><PUMP:A>',
                         b'<PTEMP:66.000><PTEMP:65.500><PTEMP:65.000>',
                         b'<PTEMP:><PTEMP:nan><PTEMP:inf><PTEMP:126>'):
            incoming.data = fragment
            namespace['forward_host_commands']()
        self.assertEqual(outgoing.sent, ['<PUMP:M>', '<HEAT:K>', '<TEMP:42>', '<PUMP:A>',
                                         '<PTEMP:66.000>', '<PTEMP:65.500>', '<PTEMP:65.000>', '<PTEMP:>'])

        slave_uart = UART(''.join(outgoing.sent).encode() + b'<PUMP:X><PTEMP:nan><PTEMP:inf>')
        machine = types.SimpleNamespace(UART=lambda *a, **k: slave_uart, Pin=lambda n: n)
        with patch.dict(sys.modules, {'machine': machine}):
            protocol = load('pump_protocol', 'pico_slave/mega_protocol.py')
        pumps, heating, temperatures, averages = [], [], [], []
        protocol.poll_commands(temperatures.append, heating.append, pumps.append, averages.append)
        self.assertEqual(pumps, ['M', 'A'])
        self.assertEqual(heating, ['K'])
        self.assertEqual(temperatures, [42])
        self.assertEqual(averages, [66.0, 65.5, 65.0, None])

    def test_average_calculation_and_packet_size(self):
        host = load('pump_temperature', 'rpi4/app/pump_control.py')
        for top, bottom, expected in (
            (70, 62, '<PTEMP:66.000>'),
            (68, 62, '<PTEMP:65.000>'),
            (69, 62, '<PTEMP:65.500>'),
            (66, 65.9375, '<PTEMP:65.969>'),
            (125, 125, '<PTEMP:125.000>'),
            (-55, -55, '<PTEMP:-55.000>'),
            (None, 66, '<PTEMP:>'), (66, None, '<PTEMP:>'),
            (85, 65, '<PTEMP:>'), (66, float('nan'), '<PTEMP:>'),
        ):
            frame = host.pump_temperature_frame(top, bottom)
            self.assertEqual(frame, expected)
            self.assertLessEqual(len((frame + '\n').encode()), 16)

    def test_status_round_trip_and_invalid_frames(self):
        master = load('master_parser', 'pico_master/parser.py')
        host = load('host_parser', 'rpi4/app/parser.py')
        state = types.SimpleNamespace(pump=None)
        for mode in ('A', 'M'):
            for active in (0, 1):
                self.assertTrue(master.parse_pump(f'PUMP:{mode},{active}', state))
                line = 'P:{MODE},{ACTIVE}'.format(**state.pump)
                self.assertEqual(host.parse_pump_frame(line), state.pump)
        for body in ('M', 'X,1', 'M,2', 'M,1,extra', 'M,', ',1'):
            self.assertFalse(master.parse_pump('PUMP:' + body, state))
            self.assertIsNone(host.parse_pump_frame('P:' + body))
        self.assertEqual(host.parse_pump_frame('P:NO_DATA'), {'MODE': None, 'ACTIVE': None})

    def test_host_buttons_require_fresh_confirmation(self):
        tree = ast.parse((ROOT / 'rpi4/app/gui.py').read_text())
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef))
        functions = [n for n in cls.body if isinstance(n, ast.FunctionDef)
                     and n.name in ('pump_status_fresh', 'toggle_manual_pump')]
        namespace = {'time': types.SimpleNamespace(monotonic=lambda: 100)}
        exec(compile(ast.Module(body=functions, type_ignores=[]), '<gui>', 'exec'), namespace)
        gui = types.SimpleNamespace(
            last_pump_status_ts=99, PUMP_STATUS_TIMEOUT=3,
            state=types.SimpleNamespace(pump={'MODE': 'A', 'ACTIVE': 0}),
            link=types.SimpleNamespace(ser=object()), desired_pump_mode='A',
            log_link_debug=lambda text: None, update_fve_view=lambda: None)
        gui.pump_status_fresh = lambda: namespace['pump_status_fresh'](gui)
        toggle = lambda: namespace['toggle_manual_pump'](gui)
        toggle()
        self.assertEqual(gui.desired_pump_mode, 'M')
        toggle()
        self.assertEqual(gui.desired_pump_mode, 'A')
        gui.last_pump_status_ts = 96
        toggle()
        self.assertEqual(gui.desired_pump_mode, 'A')
        gui.last_pump_status_ts = 100
        gui.state.pump['MODE'] = None
        self.assertFalse(gui.pump_status_fresh())
        gui.state.pump['MODE'] = 'A'
        gui.link.ser = None
        self.assertFalse(gui.pump_status_fresh())


if __name__ == '__main__':
    unittest.main()
