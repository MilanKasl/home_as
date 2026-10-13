#!/usr/bin/env python3
"""Run host-only release tests; no firmware sources or physical IO needed.

The full repository suite additionally tests unchanged firmware locally.
"""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))

NAMES = [
    'test_ds18b20',
    'test_direct_link.WireTests',
    'test_direct_link.FreshnessTests',
    'test_direct_link.IdentityTests',
    'test_direct_link.WorkerTests',
    'test_direct_link.PtyTests',
    'test_identify_link',
    'test_direct_link.IntegrationTests.test_gui_adapter_keeps_logs_contacts_and_energy_independent',
    'test_direct_link.IntegrationTests.test_missing_cov_with_live_slave_has_status_without_crashing',
    'test_direct_link.IntegrationTests.test_legacy_keeps_pio_padding_and_normalized_parsers',
    'test_direct_link.IntegrationTests.test_expired_manual_intent_is_not_renewed_by_reconnection',
    'test_pump_control.ProtocolTests.test_average_calculation_and_packet_size',
    'test_pump_control.ProtocolTests.test_host_buttons_require_fresh_confirmation',
    'test_uno_levels.CovStatusTests',
]

if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromNames(NAMES)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
