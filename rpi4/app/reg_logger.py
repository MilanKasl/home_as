
import os
import time
from datetime import date

LOG_INTERVAL = 300  # 5 minut


class RegulatorLogger:
    def __init__(self, base_dir="/home/milan/logs/home_as/regulators"):
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)

        self.last_log_ts = {
            1: 0,
        }
        self.last_load_state = None

    def _logfile_path(self):
        today = date.today().isoformat()
        return os.path.join(self.base_dir, f"{today}.log")

    def _write(self, line):
        with open(self._logfile_path(), "a", encoding="utf-8") as f:
            f.write(line + "\n")

    def _reg_snapshot(self, regulators: dict):
        r = regulators.get(1) if regulators else None
        if not r:
            return ""

        mode = "FLOAT" if r.charge_state == 1 else "BOOST" if r.charge_state == 2 else "OFF"
        return (
            f"R1 MODE={mode} "
            f"U={r.batt:.2f}V "
            f"P={r.power:.0f}W "
            f"E_DAY={r.energy_today:.0f}W "
            f"3111={r.r3111:.2f}"
        )

    def update(self, regulators: dict):

        """
        Volat opakovaně (např. z IO workeru).
        Loguje max. 1× za 10 min a jen při BOOST/FLOAT.
        """
        now = time.time()

        for idx, r in regulators.items():
            if idx != 1:
                continue

            # logujeme jen při nabíjení
            if r.charge_state not in (1, 2):
                continue

            # hlídání intervalu
            last_ts = self.last_log_ts.get(idx, 0)
            if now - last_ts < LOG_INTERVAL:
                continue

            self.last_log_ts[idx] = now

            ts = time.strftime("%H:%M")
            line = f"{ts} {self._reg_snapshot(regulators)}"

            self._write(line)


    def update_load(self, load: int, regulators: dict = None):
        if self.last_load_state is None:
            self.last_load_state = load
            return

        if load == self.last_load_state:
            return

        self.last_load_state = load

        ts = time.strftime("%H:%M:%S")
        text = "ZAPNUTO" if load == 1 else "VYPNUTO"
        snapshot = self._reg_snapshot(regulators)
        suffix = f" {snapshot}" if snapshot else ""
        self._write(f"{ts} VYTĚŽOVÁNÍ: {text}{suffix}")
