"""Passive identification reuses production readers; all IO is fake or PTY."""
import json
import os
from pathlib import Path
import pty
import select
import tempfile
import time
import types
import unittest

from test_direct_link import config, Clock, UART, COV, PUMP, HEAT, REG
from app.communication import PortResolver, validate_direct_config
from app.identify_link import IdentifyLink, identify_candidates
from app.link_diagnostics import connection_summary, diagnostic_text


def identify_config():
    path = Path(__file__).resolve().parents[1] / 'rpi4/config/waveshare-BD63F2ABCD.identify.json'
    cfg = json.loads(path.read_text())
    cfg['log_path'] = None
    return cfg


class IdentificationTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.cfg = identify_config()
        self.uarts = {}
        def factory(device, *a, **k):
            uart = UART()
            self.uarts[device] = uart
            return uart
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'identify.json'
        self.link = IdentifyLink(self.cfg, str(self.path),
            resolver=types.SimpleNamespace(resolve=lambda role: role),
            factory=factory, clock=self.clock)
        for worker in self.link.workers.values():
            worker.step()

    def feed(self, interface, raw):
        self.uarts[interface].data += raw
        self.link.workers[interface].step()

    def recognize(self):
        # Deliberately reverse interface order: must not infer CH1=if00.
        self.feed('if06', COV * 2)
        self.feed('if02', (PUMP + HEAT) * 2)

    def test_repeated_messages_identify_without_assuming_interface_order(self):
        self.feed('if06', COV)
        self.feed('if02', PUMP + HEAT)
        self.assertEqual(self.link.candidates()[0], {})
        self.feed('if06', COV)
        self.feed('if02', PUMP + HEAT)
        self.assertEqual(self.link.candidates()[0], {'cov': 'if06', 'slave': 'if02'})
        self.assertEqual({event.source for event in self.link.read_events()}, {'if06', 'if02'})
        self.assertIn('TX VYPNUTO', connection_summary(self.link))
        self.assertIn('PORT OTEVŘEN', diagnostic_text(self.link))

    def test_never_transmits_even_with_mutated_flags_and_injected_pending(self):
        self.recognize()
        self.cfg.update(tx_enabled=True, half_duplex_validated=True)
        self.assertFalse(self.link.write_control_frame('<HEAT:K>'))
        self.assertFalse(self.link.write_temperature_frame('<TEMP:62>'))
        self.clock.now += .04
        for worker in self.link.workers.values():
            self.assertFalse(worker.submit('<PUMP:M>'))
            worker.pending['PUMP'] = (b'<PUMP:M>', self.clock())
            worker.step()
        self.assertFalse(any(uart.sent for uart in self.uarts.values()))

    def test_duplicates_mixed_protocols_and_outdated_evidence_block_save(self):
        self.recognize()
        self.feed('if00', COV)
        self.assertEqual(self.link.candidates()[0], {})
        with self.assertRaises(ValueError):
            self.link.save_mapping(True)
        self.link.workers['if00'].disconnect('removed')
        self.feed('if06', REG)
        self.assertEqual(self.link.candidates()[0], {})

    def test_requires_fresh_pair_and_physical_confirmation(self):
        self.recognize()
        with self.assertRaises(ValueError):
            self.link.save_mapping(False)
        self.clock.now += 3.01
        with self.assertRaises(ValueError):
            self.link.save_mapping(True)
        self.assertFalse((self.path.parent / 'direct.confirmed.json').exists())

    def test_atomic_saved_mapping_remains_read_only_and_preserves_previous_file(self):
        self.recognize()
        path = Path(self.link.save_mapping(True))
        data = json.loads(path.read_text())
        self.assertEqual(data['mode'], 'direct')
        self.assertFalse(data['tx_enabled'])
        self.assertFalse(data['half_duplex_validated'])
        self.assertEqual(data['ports']['cov']['identity']['ID_USB_INTERFACE_NUM'], '06')
        self.assertEqual(data['ports']['slave']['identity']['ID_USB_INTERFACE_NUM'], '02')
        self.assertEqual(data['mapping_evidence']['physical_confirmed']['cov'], 'CH1')
        validate_direct_config(data)
        old_content = path.read_text()
        self.link.save_mapping(True)
        backups = list(path.parent.glob('direct.confirmed.json.backup-*'))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(), old_content)
        self.assertFalse(self.link.transmit_enabled)

    def test_reconnect_clears_evidence_and_configuration_rejects_enabled_tx(self):
        self.recognize()
        self.link.workers['if06'].disconnect('USB unplugged')
        self.assertNotIn('cov', self.link.candidates()[0])
        self.assertEqual(self.link.workers['if06'].session_counts, {})
        for key in ('tx_enabled', 'half_duplex_validated'):
            cfg = identify_config()
            cfg[key] = True
            with self.assertRaises(ValueError):
                validate_direct_config(cfg)

    def test_complete_usb_identity_required_and_collision_never_opens(self):
        cfg = identify_config()
        cfg['ports']['if00']['identity']['ID_USB_INTERFACE_NUM'] = '02'
        with self.assertRaises(ValueError):
            validate_direct_config(cfg)
        cfg = identify_config()
        inventory = [('/dev/test-' + name, port['identity']) for name, port in cfg['ports'].items()]
        resolver = PortResolver(cfg, lambda: inventory)
        resolver.refresh()
        self.assertEqual(resolver.resolve('if06'), '/dev/test-if06')
        inventory.append(('/dev/duplicate', cfg['ports']['if06']['identity']))
        resolver.refresh()
        self.assertIsNone(resolver.resolve('if06'))
        self.assertEqual(resolver.resolve('if00'), '/dev/test-if00')

    def test_regulator_only_cannot_confirm_slave(self):
        self.feed('if02', REG * 10)
        self.feed('if06', COV * 2)
        self.assertEqual(self.link.candidates()[0], {'cov': 'if06'})


class DeploymentProfileTests(unittest.TestCase):
    def test_installed_float_warning_display_can_be_preserved(self):
        from app.gui import DashboardGUI
        from app.state import SystemState
        from unittest.mock import Mock
        state = SystemState()
        state.cov['F1'] = 1
        gui = types.SimpleNamespace(state=state, direct=False, cov_levels_as_notices=False,
            last_cov_data_ts=time.time(), no_data=False, COV_WATCHDOG_TIMEOUT=30,
            status_label=Mock(), status_reason=Mock(), values={})
        DashboardGUI.update_system_status(gui)
        self.assertEqual(gui.status_label.config.call_args.kwargs['text'], 'STAV: ERROR')
        self.assertEqual(gui.status_reason.config.call_args.kwargs['text'], 'PLOVÁK 1 – PORUCHA')

    def test_read_only_buttons_do_not_change_desired_modes(self):
        from app.gui import DashboardGUI
        gui = types.SimpleNamespace(direct=True, link=types.SimpleNamespace(transmit_enabled=False),
                                    desired_heating_mode='A', desired_pump_mode='A')
        DashboardGUI.set_heating_mode(gui, 'K')
        DashboardGUI.toggle_manual_pump(gui)
        self.assertEqual(gui.desired_heating_mode, 'A')
        self.assertEqual(gui.desired_pump_mode, 'A')


class IdentificationPtyTests(unittest.TestCase):
    def test_four_streams_identify_passively_and_save(self):
        cfg = identify_config()
        cfg['simulation'] = True
        descriptors, masters = [], {}
        for role in cfg['ports']:
            master, slave = pty.openpty()
            descriptors.extend((master, slave))
            masters[role] = master
            cfg['ports'][role]['device'] = os.ttyname(slave)
        with tempfile.TemporaryDirectory() as directory:
            link = IdentifyLink(cfg, str(Path(directory) / 'identify.json'))
            try:
                link.connect()
                deadline = time.monotonic() + 4
                while time.monotonic() < deadline and not all(w.ser for w in link.workers.values()):
                    time.sleep(.01)
                self.assertTrue(all(w.ser for w in link.workers.values()))
                os.write(masters['if04'], COV * 2)
                os.write(masters['if00'], (PUMP + HEAT) * 2)
                deadline = time.monotonic() + 2
                while time.monotonic() < deadline and len(link.candidates()[0]) < 2:
                    time.sleep(.01)
                self.assertEqual(link.candidates()[0], {'cov': 'if04', 'slave': 'if00'})
                saved = json.loads(Path(link.save_mapping(True)).read_text())
                self.assertFalse(saved['tx_enabled'])
                self.assertFalse(saved['half_duplex_validated'])
                self.assertFalse(select.select(list(masters.values()), [], [], .1)[0])
            finally:
                link.disconnect()
                for fd in descriptors:
                    os.close(fd)


if __name__ == '__main__':
    unittest.main()
