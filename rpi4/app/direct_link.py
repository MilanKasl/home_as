"""Two independently reconnecting serial workers; no device IO on Tk's thread."""
from collections import deque
from dataclasses import dataclass
import logging
from logging.handlers import RotatingFileHandler
import os
import threading
import time

import serial

from app.communication import PortResolver, transmission_authorized
from app.direct_protocol import FrameBuffer, command_frame, parse_frame


@dataclass(frozen=True)
class Received:
    kind: str
    data: object
    received: float
    wall_time: float
    source: str = ""


class SerialWorker:
    RETRY = 1.0
    STATUS_TIMEOUT = 3.0
    QUIET = 0.030
    WINDOW = 0.150
    COMMAND_TTL = 2.0

    def __init__(self, role, config, resolver, deliver, audit,
                 factory=serial.Serial, clock=time.monotonic):
        self.role, self.config, self.resolver = role, config, resolver
        self.deliver, self.audit, self.factory, self.clock = deliver, audit, factory, clock
        self.ser = None
        self.device = None
        self.buffer = FrameBuffer()
        self.next_connect = 0
        self.connected_at = None
        self.last_rx = None
        self.last_valid_rx = None
        self.session_rx = {}
        self.session_counts = {}
        self.last_heat_window = None
        self.pending = {}
        self.commands = {}
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.thread = None
        self.diag = dict(connects=0, rx_bytes=0, valid=0, invalid=0, tx_bytes=0,
                         dropped=0, error=None)

    def start(self):
        if self.thread is None:
            self.thread = threading.Thread(target=self.run, name='rs485-' + self.role, daemon=True)
            self.thread.start()

    def run(self):
        try:
            while not self.stop.is_set():
                try:
                    self.step()
                except Exception as exc:
                    self.disconnect(str(exc))
                self.stop.wait(0.005)
        finally:
            self.disconnect('stopped')

    def disconnect(self, reason):
        handle, self.ser = self.ser, None
        if handle:
            try:
                handle.close()
            except (OSError, serial.SerialException):
                pass
            self.audit(self.role, 'disconnected: ' + reason)
        with self.lock:
            self.diag['dropped'] += len(self.pending)
            self.pending.clear()
            for command in self.commands.values():
                command['status'] = 'connection_lost'
        self.buffer = FrameBuffer()
        self.session_rx.clear()
        self.session_counts.clear()
        self.last_valid_rx = None
        self.last_heat_window = None
        self.diag['error'] = reason
        self.next_connect = self.clock() + self.RETRY

    def step(self):
        now = self.clock()
        # Discovery happens in worker threads, including after USB re-enumeration.
        if self.ser is None and now < self.next_connect:
            return
        device = self.resolver.resolve(self.role)
        if self.ser and device != self.device:
            self.disconnect('identity missing or ambiguous')
            return
        if self.ser is None:
            self.next_connect = now + self.RETRY
            if not device:
                self.diag['error'] = 'identity missing or ambiguous'
                return
            self.ser = self.factory(device, self.config['ports'][self.role].get('baudrate', 9600),
                                    timeout=0, write_timeout=0.05, bytesize=8,
                                    parity='N', stopbits=1, xonxoff=False,
                                    rtscts=False, dsrdtr=False, exclusive=True)
            self.device = device
            self.connected_at = now
            self.last_rx = None
            self.last_valid_rx = None
            self.diag['connects'] += 1
            self.diag['error'] = None
            self.audit(self.role, 'connected: ' + device)
        count = self.ser.in_waiting
        if count:
            chunk = self.ser.read(min(count, 4096))
            now = self.clock()
            if self.buffer.buffer and self.last_rx is not None and now - self.last_rx > 1:
                self.buffer = FrameBuffer()
                self.diag["invalid"] += 1
            self.last_rx = now
            self.diag['rx_bytes'] += len(chunk)
            errors = self.buffer.errors
            frames = self.buffer.feed(chunk)
            self.diag['invalid'] += self.buffer.errors - errors
            for frame in frames:
                parsed = self.parse(frame)
                if parsed is None:
                    self.diag['invalid'] += 1
                    continue
                kind, data = parsed
                self.last_valid_rx = now
                self.diag['valid'] += 1
                self.session_rx[kind] = now
                self.session_counts[kind] = self.session_counts.get(kind, 0) + 1
                self.deliver(Received(kind, data, now, time.time(), self.role))
                if kind in ('heating', 'pump'):
                    key = 'HEAT' if kind == 'heating' else 'PUMP'
                    with self.lock:
                        command = self.commands.get(key)
                        if (command and command.get('written') is not None
                                and now > command['written']
                                and command['payload'] == '<{}:{}>'.format(key, data['MODE'])):
                            command['status'] = 'state_observed'  # No protocol ACK exists.
                            command['observed'] = now
        if self.buffer.buffer and self.last_rx is not None and now - self.last_rx > 1:
            self.buffer = FrameBuffer()
            self.diag['invalid'] += 1
        if now - (self.last_rx if self.last_rx is not None else self.connected_at) > 30:
            self.disconnect('RX timeout')
            return
        # Noise (e.g. after another process changed the baud rate) must not
        # keep a broken connection alive indefinitely. Per-field freshness
        # remains independent: a valid R1 does not refresh HEAT/PUMP.
        if now - (self.last_valid_rx if self.last_valid_rx is not None else self.connected_at) > 30:
            self.disconnect('valid frame timeout')
            return
        self.transmit(now)

    def parse(self, frame):
        return parse_frame(self.role, frame)

    def submit(self, line):
        parsed = command_frame(line)
        now = self.clock()
        if (not parsed or self.role != 'slave' or not self.ser
                or not transmission_authorized(self.config)):
            return False
        # Never enqueue against a previous connection or an unresponsive peer.
        if any(now - self.session_rx.get(k, -float('inf')) > self.STATUS_TIMEOUT
               for k in ('heating', 'pump')):
            return False
        key, payload = parsed
        with self.lock:
            if (self.ser is None or self.stop.is_set()
                    or any(now - self.session_rx.get(k, -float("inf")) > self.STATUS_TIMEOUT
                           for k in ("heating", "pump"))):
                return False
            self.pending[key] = (payload, now)
            previous = self.commands.get(key, {})
            self.commands[key] = dict(payload=line, status='queued', requested=now,
                                      written=previous.get('written')
                                      if previous.get('payload') == line else None)
        return True  # Accepted, NOT sent or confirmed.

    def transmit(self, now):
        with self.lock:
            if not transmission_authorized(self.config):
                self.diag['dropped'] += len(self.pending)
                for key in self.pending:
                    self.commands[key]['status'] = 'disabled_unsent'
                self.pending.clear()
                return
            for key, (_, requested) in list(self.pending.items()):
                if now - requested > self.COMMAND_TTL:
                    del self.pending[key]
                    self.commands[key]['status'] = 'expired_unsent'
                    self.diag['dropped'] += 1
            if not self.pending or not self.ser:
                return
            heat = self.session_rx.get('heating')
            if (heat is None or heat == self.last_heat_window
                    or not self.QUIET <= now - heat <= self.WINDOW
                    or self.last_rx is None or now - self.last_rx < self.QUIET
                    or now - self.session_rx.get('pump', -float('inf')) > self.STATUS_TIMEOUT
                    or self.buffer.buffer or self.ser.in_waiting):
                return
            # One bounded burst per HEAT window. Existing Slave RX buffer is 128 B.
            payload = b''.join(value[0] for value in self.pending.values())
            if len(payload) > 64:
                raise ValueError('Command burst exceeds 64 bytes')
            written = self.ser.write(payload)
            if written != len(payload):
                raise OSError('partial serial write; outcome unknown')
            # No tcdrain/flush: bounded write plus wire time; no second burst in this window.
            self.last_heat_window = heat
            self.diag['tx_bytes'] += written
            for key in self.pending:
                self.commands[key].update(status='written_unconfirmed', written=now)
            self.pending.clear()
            self.audit(self.role, 'TX written, unconfirmed: ' + payload.decode('ascii'))

    def snapshot(self):
        now = self.clock()
        return dict(self.diag, device=self.device, connected=self.ser is not None,
                    buffer_len=len(self.buffer.buffer),
                    counts=self.session_counts.copy(),
                    seconds_since_rx=None if self.last_rx is None else now - self.last_rx,
                    seconds_since_valid_rx=None if self.last_valid_rx is None else now - self.last_valid_rx,
                    ages={key: now - stamp for key, stamp in self.session_rx.copy().items()},
                    commands={key: value.copy() for key, value in self.commands.copy().items()})


class DirectLink:
    direct = True

    def __init__(self, config, resolver=None, factory=serial.Serial, clock=time.monotonic):
        self.config = config
        self.events = deque(maxlen=512)
        self.event_lock = threading.Lock()
        self.event_drops = 0
        self.logger = logging.getLogger('home_as.rs485.' + str(id(self)))
        self.logger.setLevel(logging.INFO)
        path = config.get('log_path', '/home/milan/logs/home_as/link_debug.log')
        if path:
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            handler = RotatingFileHandler(path, maxBytes=2000000, backupCount=2)
            handler.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
            self.logger.addHandler(handler)
        resolver = resolver or PortResolver(config)
        self.resolver = resolver
        self.workers = self.make_workers(config, resolver, factory, clock)

    def make_workers(self, config, resolver, factory, clock):
        return {role: SerialWorker(role, config, resolver, self.deliver, self.audit,
                                   factory, clock) for role in ('cov', 'slave')}

    @property
    def transmit_enabled(self):
        return transmission_authorized(self.config)

    @property
    def ser(self):
        # Compatibility for the existing pump button's connection check.
        return self.workers['slave'].ser

    def audit(self, role, message):
        self.logger.info('[RS485 %s] %s', role, message)

    def deliver(self, event):
        with self.event_lock:
            if len(self.events) == self.events.maxlen:
                self.event_drops += 1
            self.events.append(event)

    def read_events(self):
        with self.event_lock:
            events = list(self.events)
            self.events.clear()
        return events

    def connect(self):
        if hasattr(self.resolver, "start"):
            self.resolver.start()
        for worker in self.workers.values():
            worker.start()
        return True

    def write_control_frame(self, line):
        return self.workers['slave'].submit(line)

    write_temperature_frame = write_control_frame

    def debug_snapshot(self):
        return dict(links={key: worker.snapshot() for key, worker in self.workers.items()},
                    event_drops=self.event_drops, tx_enabled=self.transmit_enabled,
                    half_duplex_validated=self.config.get('half_duplex_validated', False),
                    allow_unvalidated_half_duplex=self.config.get('allow_unvalidated_half_duplex', False))

    def disconnect(self):
        for worker in self.workers.values():
            worker.stop.set()
        for worker in self.workers.values():
            if worker.thread:
                worker.thread.join(timeout=2)
        if hasattr(self.resolver, "close"):
            self.resolver.close()
        for handler in list(self.logger.handlers):
            handler.close()
            self.logger.removeHandler(handler)
