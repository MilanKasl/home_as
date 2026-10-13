"""Receive-time freshness; regulator traffic cannot renew actuator status."""
import time


class Telemetry:
    LIMITS = {'cov': 30, 'reg': 30, 'outdoor': 90, 'heating': 3, 'pump': 3, 'tuv': 3}

    def __init__(self, state, clock=time.monotonic):
        self.state, self.clock = state, clock
        self.received = {}

    def age(self, kind):
        stamp = self.received.get(kind)
        return None if stamp is None else max(0, self.clock() - stamp)

    def fresh(self, kind):
        age = self.age(kind)
        return age is not None and age <= self.LIMITS[kind]

    def accept(self, event):
        kind, data = event.kind, event.data
        # Queued old events are never made fresh at GUI consumption time.
        if event.received < self.received.get(kind, -float('inf')):
            return False
        self.received[kind] = event.received
        if kind == 'cov':
            data = dict(data, TO=self.state.cov['TO'], COV_AGE=self.age('cov'))
            self.state.update_from_cov(data)
        elif kind == 'reg':
            self.state.update_from_reg(data)
        elif kind == 'outdoor':
            self.state.cov['TO'] = data
        elif kind == 'heating':
            self.state.update_from_heating(data)
            if data.get('TUV_TEMP') is not None:
                self.received['tuv'] = event.received
            else:
                self.received.pop('tuv', None)
        elif kind == 'pump':
            self.state.pump = data.copy()
        return self.fresh(kind)

    def expire(self):
        self.state.cov['COV_AGE'] = self.age('cov')
        if not self.fresh('heating'):
            self.state.heating.update(MODE=None, ACTIVE=None, REASON='NO_DATA')
        if not self.fresh('pump'):
            self.state.pump = {'MODE': None, 'ACTIVE': None}
        if not self.fresh('tuv'):
            self.state.tank['TUV'] = None
        if not self.fresh('outdoor'):
            self.state.cov['TO'] = None
