
import os
import time
from datetime import date

LOG_INTERVAL = 300  # 5 minut


class RegulatorLogger:
    def __init__(self, base_dir="logs/regulators"):
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)

        self.last_log_ts = {
            1: 0,
            2: 0,
        }
        self.last_load_state = None

    def _logfile_path(self):
        today = date.today().isoformat()
        return os.path.join(self.base_dir, f"{today}.log")

    def _write(self, line):
        with open(self._logfile_path(), "a", encoding="utf-8") as f:
            f.write(line + "\n")

    def update(self, regulators: dict):

        """
        Volat opakovaně (např. z IO workeru).
        Loguje max. 1× za 10 min a jen při BOOST/FLOAT.
        """
        now = time.time()

        for idx, r in regulators.items():

            # logujeme jen při nabíjení
            if r.charge_state not in (1, 2):
                continue

            # hlídání intervalu
            if now - self.last_log_ts[idx] < LOG_INTERVAL:
                continue

            self.last_log_ts[idx] = now

            ts = time.strftime("%H:%M")
            mode = "FLOAT" if r.charge_state == 1 else "BOOST"

            line = (
                f"{ts} R{idx} MODE={mode} "
                f"U={r.batt:.2f}V "
                f"P={r.power:.0f}W "
                f"E={r.energy/1000:.2f}kWh "
                f"310E={r.r310e:.2f} "
                f"3304={r.r3304:.0f} "
                f"3111={r.r3111:.2f}"
            )

            self._write(line)


    def update_load(self, load: int):
        if self.last_load_state is None:
            self.last_load_state = load
            return

        if load == self.last_load_state:
            return

        self.last_load_state = load

        ts = time.strftime("%H:%M:%S")
        text = "ZAPNUTO" if load == 1 else "VYPNUTO"
        self._write(f"{ts} VYTĚŽOVÁNÍ: {text}")