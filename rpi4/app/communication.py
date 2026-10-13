"""Select exactly one backend. USB identities must come from the actual machine."""
import json
import os
import subprocess
import threading
import time

from serial.tools import list_ports


IDENTITY_KEYS = {'ID_VENDOR_ID', 'ID_MODEL_ID', 'ID_SERIAL_SHORT',
                 'ID_USB_INTERFACE_NUM', 'ID_PATH'}


def transmission_authorized(config):
    """Operator authorization and measured validation are separate facts."""
    return (config.get('mode') == 'direct' and config.get('tx_enabled') is True
            and (config.get('half_duplex_validated') is True
                 or config.get('allow_unvalidated_half_duplex') is True))


def usb_inventory():
    result = []
    for port in list_ports.comports():
        if not port.device.startswith(('/dev/ttyACM', '/dev/ttyUSB')):
            continue
        try:
            output = subprocess.run(
                ['udevadm', 'info', '--query=property', '--name=' + port.device],
                capture_output=True, text=True, timeout=1, check=True).stdout
            props = dict(line.split('=', 1) for line in output.splitlines() if '=' in line)
            result.append((port.device, props))
        except (OSError, subprocess.SubprocessError):
            continue
    return result


def validate_direct_config(config):
    identifying = config.get('mode') == 'identify'
    expected = {'if00', 'if02', 'if04', 'if06'} if identifying else {'cov', 'slave'}
    if set(config['ports']) != expected:
        raise ValueError('Unexpected port roles for this communication mode')
    if identifying and (config.get('tx_enabled') is not False
                        or config.get('half_duplex_validated') is not False):
        raise ValueError('Identification requires TX and half-duplex validation both false')
    for role, port in config['ports'].items():
        if port.get('baudrate', 9600) != 9600:
            raise ValueError(role + ': existing firmware requires 9600 baud')
        if config.get('simulation', False):
            if not port.get('device', '').startswith('/dev/pts/'):
                raise ValueError('Simulation accepts only /dev/pts/ devices')
            continue
        identity = port.get('identity', {})
        if not set(identity) <= IDENTITY_KEYS:
            raise ValueError('Unsupported USB identity property')
        if identifying and not {'ID_VENDOR_ID', 'ID_MODEL_ID', 'ID_SERIAL_SHORT',
                                'ID_USB_INTERFACE_NUM'} <= identity.keys():
            raise ValueError('Identification requires a complete adapter/interface identity')
        if identifying and identity['ID_USB_INTERFACE_NUM'] != role[2:]:
            raise ValueError('Interface label does not match its USB identity')
        if identity and not (
            {'ID_VENDOR_ID', 'ID_MODEL_ID'} <= identity.keys()
            and ('ID_PATH' in identity or
                 {'ID_SERIAL_SHORT', 'ID_USB_INTERFACE_NUM'} <= identity.keys())
            and all(isinstance(v, str) and v for v in identity.values())
        ):
            raise ValueError(role + ': incomplete USB identity')
    for key in ('tx_enabled', 'half_duplex_validated', 'simulation',
                'allow_unvalidated_half_duplex'):
        if key in config and not isinstance(config[key], bool):
            raise ValueError(key + ' must be a JSON boolean')
    if config.get('allow_unvalidated_half_duplex'):
        if config.get('mode') != 'direct':
            raise ValueError('Unvalidated transmission is only available in direct mode')
        evidence = config.get('mapping_evidence', {})
        if evidence.get('physical_confirmed') != {'cov': 'CH1', 'slave': 'CH2'}:
            raise ValueError('Explicitly confirmed physical mapping required for unvalidated TX')
        for role, port in config['ports'].items():
            interface = port.get('identity', {}).get('ID_USB_INTERFACE_NUM')
            if not interface or evidence.get('interfaces', {}).get(role) != 'if' + interface:
                raise ValueError('TX mapping does not match its recorded confirmation')
        if not config.get('operational_authorization'):
            raise ValueError('Record the operator authorization before allowing unvalidated TX')


class PortResolver:
    def __init__(self, config, inventory=usb_inventory, clock=time.monotonic):
        validate_direct_config(config)
        self.config, self.inventory, self.clock = config, inventory, clock
        self.lock = threading.Lock()
        self.checked = -float('inf')
        self.mapping = {}

    def refresh(self):
        ports = self.config['ports']
        if self.config.get('simulation', False):
            mapping = {name: os.path.realpath(p['device']) for name, p in ports.items()}
        else:
            found = self.inventory()
            mapping = {}
            for name, p in ports.items():
                identity = p.get('identity', {})
                matches = [device for device, props in found if identity and
                           all(props.get(k) == v for k, v in identity.items())
                           and (not config_requires_modem_exclusion(self.config)
                                or (props.get('ID_MM_DEVICE_IGNORE') == '1'
                                    and props.get('ID_MM_PORT_IGNORE') == '1'))]
                mapping[name] = matches[0] if len(matches) == 1 else None
        duplicates = {device for device in mapping.values() if device is not None
                      and list(mapping.values()).count(device) > 1}
        mapping = {role: None if device in duplicates else device
                   for role, device in mapping.items()}
        with self.lock:
            self.mapping, self.checked = mapping, self.clock()

    def resolve(self, role):
        # Never run udev subprocesses in a serial reader: a slow discovery must
        # not stop reception on either link. Expired discovery disables TX/open.
        with self.lock:
            if self.clock() - self.checked > 10:
                return None
            return self.mapping.get(role)

    def start(self):
        self.stop = threading.Event()
        def discover():
            while not self.stop.is_set():
                try:
                    self.refresh()
                except Exception:
                    with self.lock:
                        self.mapping = {}
                self.stop.wait(0.5)
        self.thread = threading.Thread(target=discover, name='rs485-discovery', daemon=True)
        self.thread.start()

    def close(self):
        self.stop.set()
        self.thread.join(timeout=2)


def config_requires_modem_exclusion(config):
    return transmission_authorized(config) and config.get('allow_unvalidated_half_duplex') is True


def create_link(path=None):
    from app.config import PICO_LINK_DEVICE, PICO_LINK_BAUDRATE
    path = path or os.environ.get('HOME_AS_LINK_CONFIG')
    if path:
        with open(path, encoding='utf-8') as handle:
            config = json.load(handle)
    else:
        config = {'mode': 'legacy'}
    if config['mode'] == 'legacy':
        from app.link_receiver import PicoLinkReceiver
        return PicoLinkReceiver(config.get('device', PICO_LINK_DEVICE),
                                config.get('baudrate', PICO_LINK_BAUDRATE))
    if config['mode'] == 'identify':
        from app.identify_link import IdentifyLink
        return IdentifyLink(config, config_path=os.path.abspath(path))
    if config['mode'] == 'direct':
        from app.direct_link import DirectLink
        return DirectLink(config)
    raise ValueError('Communication mode must be legacy or direct')
