#!/usr/bin/env python3
"""Self-contained PTY demonstration. Opens no physical devices and drives no GPIO."""
import argparse
import os
from pathlib import Path
import pty
import select
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'rpi4'))
from app.direct_link import DirectLink
from app.direct_protocol import FrameBuffer


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seconds', type=float, default=8)
    parser.add_argument('--tx', action='store_true', help='send demonstration commands to PTYs only')
    args = parser.parse_args()
    descriptors = []
    ports = {}
    masters = {}
    for role in ('cov', 'slave'):
        master, slave = pty.openpty()
        descriptors += [master, slave]
        ports[role] = {'device': os.ttyname(slave), 'baudrate': 9600}
        masters[role] = master
    config = dict(mode='direct', simulation=True, tx_enabled=args.tx,
                  half_duplex_validated=args.tx, log_path=None, ports=ports)
    link = DirectLink(config)
    buffer = FrameBuffer()
    started = time.monotonic()
    last_status = last_cov = last_reg = -100
    heat_mode, pump_mode = 'A', 'A'
    sent = False
    try:
        link.connect()
        while time.monotonic() - started < args.seconds:
            now = time.monotonic() - started
            if all(worker.ser for worker in link.workers.values()):
                if now - last_cov >= 10:
                    os.write(masters['cov'], b'<1,0,1,6,18.5,1,0,0>\r\n')
                    last_cov = now
                if now - last_status >= 1:
                    # Deliberately fragmented/concatenated messages.
                    os.write(masters['slave'], b'<PUMP:')
                    os.write(masters['slave'], (f'{pump_mode},1><HEAT:{heat_mode},K,AUTO,17,42.50>\n').encode())
                    last_status = now
                if now - last_reg >= 5:
                    os.write(masters['slave'], b'<R1:52.12,1234,567,890,12345,2,54.20,49.10,26><OUT:12.25>\n')
                    last_reg = now
                if args.tx and not sent:
                    sent = link.write_control_frame('<HEAT:K>')
                    if sent:
                        link.write_control_frame('<PUMP:M>')
                        link.write_temperature_frame('<TEMP:62>')
                        link.write_temperature_frame('<PTEMP:66.000>')
            for event in link.read_events():
                print('RX', event.kind, event.data)
            if select.select([masters['slave']], [], [], 0)[0]:
                for frame in buffer.feed(os.read(masters['slave'], 4096)):
                    print('SIMULATED DEVICE RECEIVED', frame)
                    if frame.startswith('<HEAT:'):
                        heat_mode = frame[6:-1]
                    elif frame.startswith('<PUMP:'):
                        pump_mode = frame[6:-1]
            time.sleep(0.01)
        print('DIAGNOSTICS', link.debug_snapshot())
    finally:
        link.disconnect()
        for descriptor in descriptors:
            os.close(descriptor)


if __name__ == '__main__':
    main()
