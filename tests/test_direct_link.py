"""No physical serial devices are opened: fake UARTs and local POSIX PTYs only."""
import json
import os
from pathlib import Path
import pty
import select
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'rpi4'))
from app.communication import PortResolver, create_link, validate_direct_config, transmission_authorized
from app.direct_link import DirectLink, Received, SerialWorker
from app.direct_protocol import FrameBuffer, command_frame, parse_frame
from app.state import SystemState
from app.telemetry import Telemetry

COV = b'<1,0,1,6,18.5,1,0,0>\r\n'
REG = b'<R1:52.12,1234,567,890,12345,2,54.20,49.10,26>\n'
HEAT = b'<HEAT:A,K,AUTO,17,42.50>\n'
PUMP = b'<PUMP:A,1>\n'


def config():
    return dict(mode='direct', tx_enabled=True, half_duplex_validated=True, log_path=None,
                ports={'cov': {'identity': {}}, 'slave': {'identity': {}}})


class Clock:
    now = 100.0
    def __call__(self):
        return self.now


class UART:
    def __init__(self, *args, **kwargs):
        self.data = b''
        self.sent = []
        self.closed = False
        self.kwargs = kwargs
    @property
    def in_waiting(self):
        if self.closed:
            raise OSError('USB removed')
        return len(self.data)
    def read(self, n):
        data, self.data = self.data[:n], self.data[n:]
        return data
    def write(self, data):
        self.sent.append(data)
        return len(data)
    def close(self):
        self.closed = True


class WireTests(unittest.TestCase):
    def test_actual_firmware_formats_and_master_difference(self):
        fixtures = [(COV, 'cov', 'cov'), (REG, 'slave', 'reg'),
                    (HEAT, 'slave', 'heating'), (PUMP, 'slave', 'pump'),
                    (b'<OUT:-12.25>\n', 'slave', 'outdoor')]
        for raw, role, kind in fixtures:
            parsed = parse_frame(role, raw.decode().strip())
            self.assertEqual(parsed[0], kind)
        self.assertIsNone(parse_frame('cov', '<1,0,1,6,18.5,1,0,0,12.2,0>'))
        self.assertIsNone(parse_frame('slave', 'H:A,K,AUTO,17,42.5'))
        self.assertIsNone(parse_frame('slave', COV.decode().strip()))
        self.assertIsNone(parse_frame('cov', HEAT.decode().strip()))

    def test_fragmented_joined_noise_non_ascii_and_recovery(self):
        buffer = FrameBuffer()
        output = []
        data = b'noise\xff<PUMP:M,\xff1>' + COV + REG + HEAT + b'<lost' + PUMP
        for byte in data:
            output += buffer.feed(bytes([byte]))
        self.assertEqual(output, [s.decode().strip() for s in (COV, REG, HEAT, PUMP)])
        self.assertEqual(buffer.errors, 2)
        self.assertEqual(buffer.feed(b'<' + b'x' * 5000 + COV), [COV.decode().strip()])
        self.assertLessEqual(len(buffer.buffer), 256)

    def test_invalid_messages_cannot_refresh_status(self):
        invalid = ['<HEAT:M,0,AUTO,17,40>', '<HEAT:A,1,AUTO,17,40>',
                   '<HEAT:A,K,AUTO,25,40>', '<HEAT:A,K,AUTO,17,nan>',
                   '<HEAT:A,K,AUTO,17,inf>', '<HEAT:A,K,AUTO,17,85>',
                   '<HEAT:A,0,NO_DATA,17,>',
                   '<PUMP:M,2>', '<PUMP:M>', '<OUT:nan>', '<OUT:85>',
                   '<R1:nan,1,1,1,1,1,1,1,1>', '<R2:1,1,1,1,1,1,1,1,1>']
        for frame in invalid:
            self.assertIsNone(parse_frame('slave', frame), frame)
        for frame in ('<1,0,1,16,18,1,0,0>', '<2,0,1,0,18,1,0,0>',
                      '<1,0,1,0,nan,1,0,0>', '<1,0,1,0,18,inf,0,0>'):
            self.assertIsNone(parse_frame('cov', frame), frame)

    def test_command_allowlist_and_unpadded_wire_format(self):
        for value in ('<TEMP:42>', '<PTEMP:66.500>', '<PTEMP:>', '<HEAT:K>', '<PUMP:M>'):
            self.assertEqual(command_frame(value)[1], value.encode())
        for value in ('<TEMP:85>', '<TEMP:126>', '<HEAT:X>', '<PTEMP:nan>',
                      '<TEMP:42>\n<PUMP:M>', '<PUMP:M>\n', '<R1:1>'):
            self.assertIsNone(command_frame(value))


class FreshnessTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.state = SystemState()
        self.telemetry = Telemetry(self.state, self.clock)
    def receive(self, raw, role='slave', stamp=None):
        kind, data = parse_frame(role, raw.decode().strip())
        return self.telemetry.accept(Received(kind, data, self.clock() if stamp is None else stamp, 1000))
    def test_independent_ages_and_unknown_not_off(self):
        self.receive(COV, 'cov')
        self.receive(HEAT)
        self.receive(PUMP)
        self.receive(b'<OUT:12>')
        self.clock.now += 3.01
        self.receive(REG)
        self.telemetry.expire()
        self.assertIsNone(self.state.heating['ACTIVE'])
        self.assertEqual(self.state.heating['REASON'], 'NO_DATA')
        self.assertIsNone(self.state.pump['ACTIVE'])
        self.assertIsNone(self.state.tank['TUV'])
        self.assertTrue(self.telemetry.fresh('reg'))
        self.assertAlmostEqual(self.telemetry.age('cov'), 3.01)
        self.clock.now = 191
        self.telemetry.expire()
        self.assertIsNone(self.state.cov['TO'])
        self.assertFalse(self.telemetry.fresh('cov'))
        self.assertFalse(self.telemetry.fresh('reg'))
    def test_cov_does_not_overwrite_outdoor_and_true_off_is_known(self):
        self.receive(b'<OUT:12>')
        self.receive(COV, 'cov')
        self.assertEqual(self.state.cov['TO'], 12)
        self.receive(b'<HEAT:0,0,OFF,17,>')
        self.assertEqual(self.state.heating['ACTIVE'], '0')
        self.assertIsNone(self.state.tank['TUV'])
    def test_age_uses_receipt_not_dequeue_time_and_boundary(self):
        self.assertFalse(self.receive(HEAT, stamp=90))
        self.telemetry.expire()
        self.assertIsNone(self.state.heating['ACTIVE'])
        self.receive(HEAT)
        self.clock.now += 3
        self.assertTrue(self.telemetry.fresh('heating'))
        self.clock.now += 0.001
        self.assertFalse(self.telemetry.fresh('heating'))


class IdentityTests(unittest.TestCase):
    def test_operator_authorization_requires_mapping_and_modem_exclusion(self):
        cfg = config()
        cfg.update(half_duplex_validated=False, allow_unvalidated_half_duplex=True)
        with self.assertRaises(ValueError):
            validate_direct_config(cfg)
        cfg['mapping_evidence'] = dict(physical_confirmed={'cov': 'CH1', 'slave': 'CH2'},
                                       interfaces={'cov': 'if00', 'slave': 'if02'})
        found = []
        for role, interface in [('cov', '00'), ('slave', '02')]:
            identity = dict(ID_VENDOR_ID='test', ID_MODEL_ID='test',
                            ID_SERIAL_SHORT='test', ID_USB_INTERFACE_NUM=interface)
            cfg['ports'][role]['identity'] = identity
            found.append(('/fake/' + role, identity.copy()))
        with self.assertRaises(ValueError):
            validate_direct_config(cfg)
        cfg['operational_authorization'] = 'Explicit test operator authorization'
        resolver = PortResolver(cfg, lambda: found)
        resolver.refresh()
        self.assertIsNone(resolver.resolve('slave'))
        for _, properties in found:
            properties.update(ID_MM_DEVICE_IGNORE='1', ID_MM_PORT_IGNORE='1')
        resolver.refresh()
        self.assertEqual(resolver.resolve('slave'), '/fake/slave')
        self.assertTrue(transmission_authorized(cfg))
        self.assertFalse(cfg['half_duplex_validated'])
        cfg['mapping_evidence']['interfaces']['slave'] = 'if04'
        with self.assertRaises(ValueError):
            validate_direct_config(cfg)

    def test_no_guessed_ids_duplicates_and_renumbering(self):
        cfg = config()
        found = []
        resolver = PortResolver(cfg, lambda: found)
        resolver.refresh()
        self.assertIsNone(resolver.resolve('slave'))
        slave_id = dict(ID_VENDOR_ID='test-vid', ID_MODEL_ID='test-pid',
                        ID_SERIAL_SHORT='test-serial', ID_USB_INTERFACE_NUM='test-interface')
        cfg['ports']['slave']['identity'] = slave_id
        found.append(('/dev/ttyACM7', slave_id.copy()))
        resolver.refresh()
        self.assertEqual(resolver.resolve('slave'), '/dev/ttyACM7')
        found.append(('/dev/ttyACM8', slave_id.copy()))
        resolver.refresh()
        self.assertIsNone(resolver.resolve('slave'))
        found[:] = [('/dev/ttyACM3', slave_id.copy())]
        resolver.refresh()
        self.assertEqual(resolver.resolve('slave'), '/dev/ttyACM3')
        cfg['ports']['cov']['identity'] = slave_id
        resolver.refresh()
        self.assertIsNone(resolver.resolve('slave'))
        self.assertIsNone(resolver.resolve('cov'))
    def test_id_path_without_serial_and_missing_peer(self):
        cfg = config()
        props = dict(ID_VENDOR_ID='test', ID_MODEL_ID='test', ID_PATH='test-usb-port-interface')
        cfg['ports']['slave']['identity'] = props
        resolver = PortResolver(cfg, lambda: [('/dev/ttyACM4', props)])
        resolver.refresh()
        self.assertIsNone(resolver.resolve('cov'))
        self.assertEqual(resolver.resolve('slave'), '/dev/ttyACM4')
    def test_reject_tty_only_simulation_escape_and_invalid_flags(self):
        for change in ({'ID_VENDOR_ID': 'test', 'ID_MODEL_ID': 'test'},
                       {'device': '/dev/ttyUSB0'}):
            cfg = config()
            cfg['ports']['slave']['identity'] = change
            with self.assertRaises(ValueError):
                validate_direct_config(cfg)
        cfg = config()
        cfg['tx_enabled'] = 'false'
        with self.assertRaises(ValueError):
            validate_direct_config(cfg)
        cfg = config()
        cfg['simulation'] = True
        cfg['ports']['cov']['device'] = '/dev/ttyACM0'
        with self.assertRaises(ValueError):
            validate_direct_config(cfg)
    def test_factory_exclusive_backend(self):
        for mode, target in [('legacy', 'app.link_receiver.PicoLinkReceiver'),
                             ('direct', 'app.direct_link.DirectLink')]:
            with tempfile.NamedTemporaryFile(mode='w+', suffix='.json') as file:
                cfg = config()
                cfg['mode'] = mode
                json.dump(cfg, file)
                file.flush()
                with patch(target) as backend:
                    self.assertIs(create_link(file.name), backend.return_value)
                    backend.assert_called_once()


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.cfg = config()
        self.device = '/fake/slave'
        self.events = []
        self.uart = UART()
        self.worker = SerialWorker('slave', self.cfg,
            types.SimpleNamespace(resolve=lambda role: self.device), self.events.append,
            lambda *a: None, factory=lambda *a, **k: self.uart, clock=self.clock)
        self.worker.step()
    def feed(self, raw):
        self.uart.data += raw
        self.worker.step()
    def test_explicit_unvalidated_operation_keeps_receive_and_quiet_guards(self):
        self.cfg.update(half_duplex_validated=False, allow_unvalidated_half_duplex=True)
        self.assertFalse(self.worker.submit('<PUMP:A>'))
        self.feed(PUMP + HEAT)
        self.assertTrue(self.worker.submit('<PUMP:A>'))
        self.worker.step()
        self.assertFalse(self.uart.sent)
        self.clock.now += 0.04
        self.worker.step()
        self.assertEqual(self.uart.sent, [b'<PUMP:A>'])
        self.assertFalse(self.cfg['half_duplex_validated'])
        self.assertEqual(self.worker.commands['PUMP']['status'], 'written_unconfirmed')

    def test_disabling_transmission_also_blocks_already_queued_commands(self):
        self.feed(PUMP + HEAT)
        self.assertTrue(self.worker.submit('<PUMP:M>'))
        self.cfg['tx_enabled'] = False
        self.clock.now += 0.04
        self.worker.step()
        self.assertFalse(self.uart.sent)
        self.assertFalse(self.worker.pending)
        self.assertEqual(self.worker.commands['PUMP']['status'], 'disabled_unsent')

    def test_noise_cannot_keep_connection_alive_and_reopen_drops_old_intent(self):
        for initial in (b'', PUMP + HEAT):
            with self.subTest(initial=initial):
                self.setUp()
                self.feed(initial)
                if initial:
                    self.assertTrue(self.worker.submit('<PUMP:M>'))
                for _ in range(30):
                    self.clock.now += 1
                    self.feed(b'\xffgarbage<invalid>\r\n')
                self.assertIsNotNone(self.worker.ser)
                self.clock.now += 0.01
                self.feed(b'\xffgarbage')
                self.assertIsNone(self.worker.ser)
                self.assertEqual(self.worker.diag['error'], 'valid frame timeout')
                self.assertTrue(self.uart.closed)
                self.assertFalse(self.worker.session_rx)
                self.assertFalse(self.worker.pending)
                self.uart = UART()
                self.clock.now += self.worker.RETRY
                self.feed(PUMP + HEAT)
                self.assertIs(self.worker.ser, self.uart)
                self.assertEqual(self.worker.diag['connects'], 2)
                self.assertEqual(self.worker.snapshot()['seconds_since_valid_rx'], 0)
                self.clock.now += 0.04
                self.worker.step()
                self.assertEqual(self.uart.sent, [])

    def test_valid_reg_keeps_transport_alive_without_refreshing_heat_or_pump(self):
        self.feed(PUMP + HEAT)
        original_status = self.worker.session_rx.copy()
        for _ in range(4):
            self.clock.now += 20
            self.feed(REG)
        self.assertEqual(self.worker.diag['connects'], 1)
        self.assertIsNotNone(self.worker.ser)
        self.assertEqual(self.worker.session_rx['heating'], original_status['heating'])
        self.assertEqual(self.worker.session_rx['pump'], original_status['pump'])
        self.assertFalse(self.worker.submit('<PUMP:M>'))

    def test_routing_window_quiet_partial_and_observed_state(self):
        self.assertFalse(self.worker.submit('<PUMP:M>'))
        self.feed(PUMP + HEAT)
        self.assertTrue(self.worker.submit('<PUMP:M>'))
        self.assertTrue(self.worker.submit('<TEMP:42>'))
        self.worker.step()
        self.assertEqual(self.uart.sent, [])
        self.clock.now += 0.031
        self.worker.step()
        self.assertEqual(self.uart.sent, [b'<PUMP:M><TEMP:42>'])
        self.assertEqual(self.worker.commands['PUMP']['status'], 'written_unconfirmed')
        self.clock.now += 0.1
        self.feed(b'<PUMP:M,1>')
        self.assertEqual(self.worker.commands['PUMP']['status'], 'state_observed')
        self.assertEqual(self.worker.commands['TEMP']['status'], 'written_unconfirmed')
        self.worker.role = 'cov'
        self.assertFalse(self.worker.submit('<HEAT:K>'))
    def test_partial_receive_and_late_window_suppress_transmit(self):
        self.feed(PUMP + HEAT + b'<R1:')
        self.worker.submit('<HEAT:K>')
        self.clock.now += 0.04
        self.worker.step()
        self.assertEqual(self.uart.sent, [])
        self.clock.now += 0.2
        self.feed(REG)
        self.assertEqual(self.uart.sent, [])
    def test_busy_bus_delays_and_coalesces_current_intent(self):
        self.feed(PUMP + HEAT)
        self.worker.submit('<PUMP:M>')
        self.worker.submit('<PUMP:A>')
        self.clock.now += 0.02
        self.feed(b'<OUT:12>')
        self.clock.now += 0.02
        self.worker.step()
        self.assertEqual(self.uart.sent, [])
        self.clock.now += 0.02
        self.worker.step()
        self.assertEqual(self.uart.sent, [b'<PUMP:A>'])
    def test_pending_expiry_reconnect_no_replay_and_new_status_required(self):
        self.feed(PUMP + HEAT)
        self.worker.submit('<PUMP:M>')
        self.clock.now += 2.1
        self.worker.step()
        self.assertEqual(self.worker.commands['PUMP']['status'], 'expired_unsent')
        self.feed(PUMP + HEAT)
        self.worker.submit('<HEAT:T>')
        self.feed(b'<PUMP:')
        self.worker.disconnect('USB removed')
        self.assertFalse(self.worker.pending)
        self.assertFalse(self.worker.buffer.buffer)
        self.clock.now += 1.1
        self.uart = UART()
        self.worker.step()
        self.assertFalse(self.worker.submit('<HEAT:T>'))
        self.feed(REG)
        self.assertFalse(self.worker.submit('<HEAT:T>'))
        self.feed(PUMP + HEAT)
        self.clock.now += 0.04
        self.worker.step()
        self.assertEqual(self.uart.sent, [])
    def test_read_only_and_unvalidated_never_queue(self):
        self.feed(PUMP + HEAT)
        for key in ('tx_enabled', 'half_duplex_validated'):
            self.cfg[key] = False
            self.assertFalse(self.worker.submit('<HEAT:K>'))
            self.cfg[key] = True
    def test_invalid_frames_do_not_renew_freshness(self):
        self.feed(PUMP + HEAT)
        self.clock.now += 4
        self.feed(REG + b'<HEAT:K><PUMP:M>')
        self.assertFalse(self.worker.submit('<HEAT:K>'))
        self.assertEqual(self.worker.diag['invalid'], 2)
    def test_old_partial_cannot_be_completed_after_timeout(self):
        self.feed(b'<PUMP:M,')
        self.clock.now += 1.1
        self.feed(b'1>')
        self.assertEqual(self.events, [])
        self.feed(PUMP)
        self.assertEqual(self.events[0].kind, 'pump')
        self.assertEqual(self.worker.diag['invalid'], 1)

    def test_partial_write_is_failure_and_not_confirmation(self):
        self.feed(PUMP + HEAT)
        self.worker.submit('<HEAT:K>')
        self.uart.write = lambda data: 2
        self.clock.now += 0.04
        with self.assertRaises(OSError):
            self.worker.step()
        self.worker.disconnect('partial write')
        self.assertEqual(self.worker.commands['HEAT']['status'], 'connection_lost')
        self.assertFalse(self.worker.pending)


class IntegrationTests(unittest.TestCase):
    def test_gui_adapter_keeps_logs_contacts_and_energy_independent(self):
        from app.gui import DashboardGUI
        from unittest.mock import Mock
        state = SystemState()
        state.fve_energy = Mock()
        clock = Clock()
        events = []
        for role, raw in [('cov', COV), ('slave', HEAT), ('slave', PUMP),
                          ('slave', REG), ('slave', b'<OUT:12>')]:
            kind, data = parse_frame(role, raw.decode().strip())
            events.append(Received(kind, data, 100, 1000))
        gui = types.SimpleNamespace(state=state, telemetry=Telemetry(state, clock),
                                    link=Mock(), cov_logger=Mock(), reg_logger=Mock(),
                                    cov_history=Mock())
        gui.link.read_events.return_value = events
        DashboardGUI.receive_direct(gui)
        gui.cov_logger.update.assert_called_once()
        gui.reg_logger.update.assert_called_once()
        gui.cov_history.record_air_temperature.assert_called_once_with(12)
        state.fve_energy.observe_heating.assert_called_once_with('K', 1000)
        self.assertEqual(gui.last_heating_contact_ts, 100)
        self.assertEqual(gui.last_pump_contact_ts, 100)
        clock.now = 104
        kind, data = parse_frame('slave', REG.decode().strip())
        gui.link.read_events.return_value = [Received(kind, data, 104, 1004)]
        DashboardGUI.receive_direct(gui)
        self.assertEqual(gui.last_heating_contact_ts, 100)
        self.assertEqual(gui.last_pump_contact_ts, 100)
        self.assertIsNone(state.heating['ACTIVE'])
        self.assertIsNone(state.pump['ACTIVE'])
        self.assertIsNone(state.fve_energy.observe_heating.call_args[0][0])

    def test_missing_cov_with_live_slave_has_status_without_crashing(self):
        from app.gui import DashboardGUI
        from unittest.mock import Mock
        gui = types.SimpleNamespace(state=SystemState(), direct=True,
            last_cov_data_ts=0, no_data=False, telemetry=Mock(),
            COV_WATCHDOG_TIMEOUT=30, status_label=Mock(), status_reason=Mock(), values={})
        gui.telemetry.age.return_value = None
        gui.format_duration = lambda value: DashboardGUI.format_duration(gui, value)
        DashboardGUI.update_system_status(gui)
        self.assertEqual(gui.status_label.config.call_args.kwargs['text'], 'STAV: COV NO DATA')
        self.assertIn('dosud nepřijata', gui.status_reason.config.call_args.kwargs['text'])

    def test_legacy_keeps_pio_padding_and_normalized_parsers(self):
        from app.link_receiver import PicoLinkReceiver
        from app.parser import parse_cov_frame, parse_heating_frame
        link = PicoLinkReceiver.__new__(PicoLinkReceiver)
        sent = []
        link._write_payload = lambda payload, **kwargs: sent.append(payload) or True
        link.write_control_frame('<PUMP:M>')
        link.write_temperature_frame('<TEMP:42>')
        self.assertEqual(sent, [b'<PUMP:M>\n       ', b'<TEMP:42>\n      '])
        self.assertEqual(parse_cov_frame('<1,0,1,6,18.5,1,0,0,12.2,7>')['COV_AGE'], 7)
        self.assertEqual(parse_heating_frame('H:A,K,AUTO,17,42.50')['ACTIVE'], 'K')

    def test_expired_manual_intent_is_not_renewed_by_reconnection(self):
        from app.gui import DashboardGUI
        gui = types.SimpleNamespace(desired_heating_mode='K', desired_pump_mode='M',
                                    last_heating_contact_ts=100, last_pump_contact_ts=100,
                                    CONTROL_LOSS_TIMEOUT=2400)
        with patch('app.gui.time.monotonic', return_value=2500):
            DashboardGUI.expire_manual_requests(gui)
        self.assertEqual(gui.desired_heating_mode, '0')
        self.assertEqual(gui.desired_pump_mode, 'A')

    def test_unchanged_slave_accepts_direct_command_bytes(self):
        from test_pump_control import load, UART as SlaveUART
        uart = SlaveUART(b'<TEMP:62><PTEMP:66.000><HEAT:K><PUMP:M>')
        machine = types.SimpleNamespace(UART=lambda *a, **k: uart, Pin=lambda n: n)
        with patch.dict(sys.modules, {'machine': machine}):
            protocol = load('direct_slave_protocol', 'pico_slave/mega_protocol.py')
        temps, heats, pumps, averages = [], [], [], []
        protocol.poll_commands(temps.append, heats.append, pumps.append, averages.append)
        self.assertEqual((temps, heats, pumps, averages), ([62], ['K'], ['M'], [66.0]))

    def test_heating_interlock_and_local_missing_input_protection_unchanged(self):
        from test_pump_control import load, Relay, ticks_diff
        control = load('direct_heating_protection', 'pico_slave/heating_control.py')
        control.time = types.SimpleNamespace(ticks_diff=ticks_diff, ticks_add=lambda a, b: a+b)
        tuv, aku = Relay(), Relay()
        heat = control.HeatingController(tuv, aku, 7, 17, 47, 50, 70, 75, 5000, 2400000)
        heat.update(0, (12, 0, 0), 40, 60)
        self.assertTrue(tuv.is_on)
        heat.update(1, (12, 0, 0), 51, 60)
        self.assertFalse(tuv.is_on or aku.is_on)
        heat.update(5000, (12, 0, 0), 51, 60)
        self.assertFalse(tuv.is_on or aku.is_on)
        heat.update(5001, (12, 0, 0), 51, 60)
        self.assertTrue(aku.is_on)
        heat.update(5002, None, 51, 60)
        self.assertFalse(tuv.is_on or aku.is_on)
        self.assertEqual(heat.reason, 'NO_TIME')
        heat.update(5003, (12, 0, 0), 51, None)
        self.assertFalse(tuv.is_on or aku.is_on)
        self.assertEqual(heat.reason, 'NO_TEMP')


class PtyTests(unittest.TestCase):
    def test_two_real_serial_streams_reconnect_and_no_cross_routing(self):
        descriptors = []
        def pair():
            master, slave = pty.openpty()
            descriptors.extend([master, slave])
            return master, os.ttyname(slave)
        cov, cov_path = pair()
        slave, slave_path = pair()
        mapping = {'cov': cov_path, 'slave': slave_path}
        link = DirectLink(config(), resolver=types.SimpleNamespace(resolve=lambda role: mapping[role]))
        def wait_for(predicate, seconds=3):
            until = time.monotonic() + seconds
            while time.monotonic() < until:
                if predicate():
                    return
                time.sleep(0.01)
            self.fail('Timed out waiting for serial worker')
        try:
            link.connect()
            wait_for(lambda: all(w.ser for w in link.workers.values()))
            os.write(cov, COV[:7])
            os.write(slave, REG + PUMP + HEAT)
            os.write(cov, COV[7:])
            wait_for(lambda: len(link.events) >= 4)
            self.assertEqual({e.kind for e in link.read_events()}, {'cov', 'reg', 'pump', 'heating'})
            self.assertTrue(link.write_control_frame('<PUMP:M>'))
            wait_for(lambda: select.select([slave], [], [], 0)[0])
            self.assertEqual(os.read(slave, 100), b'<PUMP:M>')
            self.assertFalse(select.select([cov], [], [], 0)[0])
            # Remove one endpoint, the other still receives.
            os.close(cov)
            descriptors.remove(cov)
            wait_for(lambda: link.workers['cov'].ser is None)
            os.write(slave, PUMP + HEAT)
            wait_for(lambda: any(e.kind == 'pump' for e in link.events))
            link.read_events()
            cov, mapping['cov'] = pair()
            wait_for(lambda: link.workers['cov'].ser is not None)
            os.write(cov, COV)
            wait_for(lambda: any(e.kind == 'cov' for e in link.events))
            # Whole adapter removal/re-enumeration; no pending command replay.
            os.close(cov)
            descriptors.remove(cov)
            os.close(slave)
            descriptors.remove(slave)
            wait_for(lambda: all(w.ser is None for w in link.workers.values()))
            cov, mapping['cov'] = pair()
            slave, mapping['slave'] = pair()
            wait_for(lambda: all(w.ser for w in link.workers.values()))
            self.assertFalse(link.write_control_frame('<PUMP:M>'))
            os.write(cov, COV)
            os.write(slave, PUMP + HEAT)
            time.sleep(0.2)
            self.assertFalse(select.select([slave], [], [], 0)[0])
        finally:
            link.disconnect()
            for fd in descriptors:
                os.close(fd)


if __name__ == '__main__':
    unittest.main()
