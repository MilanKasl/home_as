#!/usr/bin/env python3
"""Package only RPi code, tests and migration instructions; never firmware."""
import hashlib
import io
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'deploy/output'


def main():
    OUTPUT.mkdir(exist_ok=True)
    files = list((ROOT / 'rpi4').rglob('*.py'))
    files += list((ROOT / 'rpi4/config').glob('*.example.json'))
    files += [ROOT / 'rpi4/config/waveshare-BD63F2ABCD.identify.json', ROOT / 'rpi4/requirements.txt']
    files += list((ROOT / 'tests').glob('*.py'))
    files += list((ROOT / 'deploy').glob('*.rules'))
    files += [ROOT / 'deploy/launch.py', ROOT / 'deploy/check_release.py', ROOT / 'docs/migrace-usb-rs485.md',
              ROOT / 'docs/nasazeni-rpi-2026-10-12.md']
    manifest = []
    package = OUTPUT / 'home-as-usb-rs485-rx1.tar.gz'
    with tarfile.open(package, 'w:gz') as archive:
        for path in sorted(set(files)):
            relative = path.relative_to(ROOT).as_posix()
            manifest.append(hashlib.sha256(path.read_bytes()).hexdigest() + '  ' + relative)
            archive.add(path, arcname=relative)
        payload = ('\n'.join(manifest) + '\n').encode()
        entry = tarfile.TarInfo('MANIFEST.sha256')
        entry.size = len(payload)
        archive.addfile(entry, io.BytesIO(payload))
    checksum = hashlib.sha256(package.read_bytes()).hexdigest()
    (OUTPUT / 'SHA256SUMS').write_text(checksum + '  ' + package.name + '\n')
    print(package)
    print(checksum)


if __name__ == '__main__':
    main()
