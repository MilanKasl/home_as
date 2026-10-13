#!/usr/bin/env python3
"""Launch the staged Home AS GUI, defaulting to passive identification."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys


class LaunchParser(argparse.ArgumentParser):
    def error(self, message):
        if os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY'):
            try:
                import tkinter as tk
                from tkinter import messagebox
                root = tk.Tk()
                root.withdraw()
                messagebox.showerror('Home AS — spuštění', message, parent=root)
                root.destroy()
            except tk.TclError:
                pass
        super().error(message)


def main():
    parser = LaunchParser(description=__doc__)
    parser.add_argument('mode', choices=('identify', 'receive', 'operate', 'legacy'))
    args = parser.parse_args()
    release = Path(__file__).resolve().parents[1]
    rpi = release / 'rpi4'
    configs = {'identify': 'waveshare-BD63F2ABCD.identify.json',
               'receive': 'direct.confirmed.json', 'operate': 'direct.operational.json',
               'legacy': 'legacy.example.json'}
    config = rpi / 'config' / configs[args.mode]
    if not config.exists():
        parser.error('Konfigurace ještě neexistuje: ' + str(config))
    data = json.loads(config.read_text())
    if args.mode in ('identify', 'receive') and (data.get('tx_enabled') is not False
                                  or data.get('half_duplex_validated') is not False):
        parser.error('Tento spouštěč dovoluje pouze příjem; TX a half_duplex_validated musí být false.')
    if args.mode == 'operate':
        sys.path.insert(0, str(rpi))
        from app.communication import validate_direct_config, transmission_authorized
        try:
            validate_direct_config(data)
        except (ValueError, KeyError) as exc:
            parser.error(str(exc))
        if not transmission_authorized(data):
            parser.error('Provozní konfigurace nemá povolené vysílání.')
    # Prevent parallel use with the old desktop shortcut, which has no lock support.
    original = '/home/milan/home_as/rpi4/main.py'
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit() or int(entry.name) == os.getpid():
            continue
        try:
            argv = (entry / 'cmdline').read_bytes().split(b'\0')
            relative_original = (b'main.py' in argv and
                                 (entry / 'cwd').resolve() == Path(original).parent)
            if original.encode() in argv or relative_original:
                parser.error('Původní Home AS je spuštěný; nejprve jej zavřete, PID ' + entry.name)
        except (OSError, PermissionError):
            continue
    runtime = Path(os.environ.get('XDG_RUNTIME_DIR', '/tmp'))
    with open(runtime / ('home-as-' + str(os.getuid()) + '.lock'), 'a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            parser.error('Jiná instance nové aplikace už běží. Nejprve ji zavřete.')
        env = dict(os.environ, HOME_AS_LINK_CONFIG=str(config))
        return subprocess.call([sys.executable, str(rpi / 'main.py')], cwd=rpi, env=env)


if __name__ == '__main__':
    sys.exit(main())
