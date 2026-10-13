"""Wire protocol of the unchanged Uno and Pico Slave (9600, 8N1)."""
import math
import re

from app.parser import parse_cov_frame, parse_reg_frame, parse_heating_frame, parse_pump_frame


class FrameBuffer:
    """Bounded ASCII <...> stream; newline is optional, corruption is not ignored."""
    def __init__(self, limit=256):
        self.limit = limit
        self.buffer = bytearray()
        self.errors = 0

    def feed(self, chunk):
        frames = []
        for byte in chunk:
            if byte == ord('<'):
                if self.buffer:
                    self.errors += 1
                self.buffer = bytearray(b'<')
            elif self.buffer:
                if byte == ord('>'):
                    self.buffer.append(byte)
                    frames.append(self.buffer.decode('ascii'))
                    self.buffer.clear()
                elif not 32 <= byte <= 126 or len(self.buffer) >= self.limit:
                    self.errors += 1
                    self.buffer.clear()
                else:
                    self.buffer.append(byte)
        return frames


def valid_temperature(value):
    return math.isfinite(value) and -55 <= value <= 125 and value != 85


def parse_frame(role, frame):
    if not (frame.startswith('<') and frame.endswith('>')):
        return None
    body = frame[1:-1]
    if role == 'cov':
        fields = body.split(',')
        if len(fields) != 8 or any(fields[i] not in ('0', '1') for i in (0, 1, 2, 5, 6, 7)):
            return None
        data = parse_cov_frame(frame)
        if data is None or any(data[k] not in (0, 1) for k in
                               ('P1', 'P2', 'AIR', 'MODE', 'EP1', 'EP2')):
            return None
        if not 0 <= data['FLOATMASK'] <= 15 or not math.isfinite(data['TW']):
            return None
        return 'cov', data
    if role != 'slave':
        return None
    if body.startswith('R1:'):
        data = parse_reg_frame(body)
        if data and all(math.isfinite(v) for v in data.values()) and data['CH'] in range(4):
            return 'reg', data
    elif body.startswith('OUT:'):
        try:
            value = float(body[4:])
            if valid_temperature(value):
                return 'outdoor', value
        except ValueError:
            pass
    elif body.startswith('HEAT:'):
        fields = body[5:].split(',')
        if len(fields) != 5:
            return None
        try:
            if fields[4] and not valid_temperature(float(fields[4])):
                return None
        except ValueError:
            return None
        data = parse_heating_frame('H:' + body[5:])
        # Require the actual five-field firmware format, not an echoed command.
        if data and fields[2] in {
            'START', 'AUTO', 'MANUAL', 'OFF', 'MAX_TUV', 'MAX_AKU',
            'NO_TEMP', 'NO_TIME', 'OUTSIDE', 'TIMEOUT',
        }:
            return 'heating', data
    elif body.startswith('PUMP:'):
        data = parse_pump_frame('P:' + body[5:])
        if data:
            return 'pump', data
    return None


def command_frame(line):
    """Allowlist; never pass arbitrary bytes or PIO padding to an RS485 bus."""
    if re.fullmatch(r'<(?:HEAT:[ATK0]|PUMP:[AM])>', line):
        return line[1:].split(':')[0], line.encode('ascii')
    match = re.fullmatch(r'<TEMP:(-?\d+)>', line)
    if match and -55 <= int(match[1]) <= 125 and int(match[1]) != 85:
        return 'TEMP', line.encode('ascii')
    match = re.fullmatch(r'<PTEMP:(-?\d+(?:\.\d+)?)?>', line)
    if match and (match[1] is None or valid_temperature(float(match[1]))):
        return 'PTEMP', line.encode('ascii')
    return None
