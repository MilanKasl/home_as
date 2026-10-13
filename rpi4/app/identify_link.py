"""Receive-only port identification inside Home AS using the existing workers."""
import copy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import tempfile

from app.direct_link import DirectLink, SerialWorker
from app.direct_protocol import parse_frame


class ProbeWorker(SerialWorker):
    def parse(self, frame):
        return parse_frame('cov', frame) or parse_frame('slave', frame)

    def submit(self, line):
        return False

    def transmit(self, now):
        # Defense in depth: even a mutated config/pending buffer cannot enable TX.
        return


def identify_candidates(snapshots):
    """Unique repeated, fresh evidence, never USB interface order or a single frame."""
    seen = {'cov': [], 'slave': []}
    for interface, snap in snapshots.items():
        if not snap['connected']:
            continue
        counts = snap['counts']
        cov_seen = counts.get('cov', 0) > 0
        slave_seen = any(counts.get(k, 0) for k in ('heating', 'pump', 'reg', 'outdoor'))
        # Mixed protocols on one physical bus must be investigated, not guessed.
        if cov_seen and slave_seen:
            return {}, 'Smíšené zprávy ČOV a Slave na ' + interface + '; zkontrolujte kabeláž.'
        if cov_seen:
            seen['cov'].append(interface)
        if slave_seen:
            seen['slave'].append(interface)
    if any(len(items) > 1 for items in seen.values()):
        return {}, 'Stejný typ zařízení na více rozhraních; přiřazení je nejednoznačné.'
    result = {}
    for role, interfaces in seen.items():
        if len(interfaces) != 1:
            continue
        interface = interfaces[0]
        snap = snapshots[interface]
        required = {'cov': 30} if role == 'cov' else {'heating': 3, 'pump': 3}
        if all(snap['counts'].get(kind, 0) >= 2 and snap['ages'].get(kind, float('inf')) <= limit
               for kind, limit in required.items()):
            result[role] = interface
    if len(result) < 2:
        return result, 'Čekám na alespoň 2 zprávy ČOV a 2 zprávy HEAT i PUMP (ČOV po 10 s).'
    return result, 'Rozpoznáno podle příjmu. Potvrďte fyzické CH1=ČOV, CH2=Slave.'


class IdentifyLink(DirectLink):
    identifying = True

    def __init__(self, config, config_path, **kwargs):
        self.config_path = Path(config_path)
        self.saved_path = None
        super().__init__(config, **kwargs)

    def make_workers(self, config, resolver, factory, clock):
        return {role: ProbeWorker(role, config, resolver, self.deliver, self.audit,
                                  factory, clock) for role in config['ports']}

    @property
    def ser(self):
        return None

    @property
    def transmit_enabled(self):
        return False

    def write_control_frame(self, line):
        return False

    write_temperature_frame = write_control_frame

    def candidates(self):
        return identify_candidates({key: worker.snapshot() for key, worker in self.workers.items()})

    def read_events(self):
        candidates, _ = self.candidates()
        return [event for event in super().read_events()
                if event.source == candidates.get('cov' if event.kind == 'cov' else 'slave')]

    def save_mapping(self, physical_confirmed=False):
        if not physical_confirmed:
            raise ValueError('Nejprve potvrďte fyzické zapojení CH1=ČOV, CH2=Slave a odpojený Master.')
        candidates, reason = self.candidates()
        if set(candidates) != {'cov', 'slave'}:
            raise ValueError(reason)
        # Refresh in-memory identity agreement; no udev subprocesses on Tk thread.
        for role, interface in candidates.items():
            worker = self.workers[interface]
            if not worker.ser or self.resolver.resolve(interface) != worker.device:
                raise ValueError('USB přiřazení se změnilo. Počkejte na nové platné zprávy.')
        output = {
            'mode': 'direct', 'tx_enabled': False, 'half_duplex_validated': False,
            'simulation': self.config.get('simulation', False),
            'log_path': self.config.get('log_path'),
            'ports': {role: copy.deepcopy(self.config['ports'][interface])
                      for role, interface in candidates.items()},
            'mapping_evidence': {
                'confirmed_at': datetime.now(timezone.utc).isoformat(),
                'physical_confirmed': {'cov': 'CH1', 'slave': 'CH2'},
                'interfaces': candidates,
                'basis': 'operator wiring confirmation and repeated received COV/HEAT/PUMP frames',
                'half_duplex_test': 'not performed',
            },
        }
        destination = self.config_path.with_name('direct.confirmed.json')
        if destination.exists():
            # Preserve any older mapping/config, including its flags, before replacement.
            with tempfile.NamedTemporaryFile(prefix=destination.name + '.backup-',
                                             dir=destination.parent, delete=False) as backup:
                backup_path = backup.name
            shutil.copy2(destination, backup_path)
        fd, temporary = tempfile.mkstemp(prefix='.mapping-', dir=destination.parent)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as handle:
                json.dump(output, handle, ensure_ascii=False, indent=2)
                handle.write('\n')
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, destination)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        self.saved_path = str(destination)
        self.audit('identify', 'Mapping saved; TX remains disabled: ' + self.saved_path)
        return self.saved_path
