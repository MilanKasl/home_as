import os
import time
from datetime import date


class CovLogger:
    def __init__(self, base_dir="/home/milan/logs/home_as/cov"):
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)
        self.last_state = None

    def _logfile_path(self):
        today = date.today().isoformat()
        return os.path.join(self.base_dir, f"{today}.log")

    def _write(self, line):
        with open(self._logfile_path(), "a", encoding="utf-8") as f:
            f.write(line + "\n")

    def _write_line(self, m):
        ts = time.strftime("%H:%M:%S")
        line = (
            f"{ts} "
            f"P1={int(m.pump1)} P2={int(m.pump2)} AIR={int(m.air)} "
            f"F1={int(m.float1)} F2={int(m.float2)} "
            f"F3={int(m.float3)} F4={int(m.float4)} "
            f"EP1={int(m.error_pump1)} EP2={int(m.error_pump2)} "
            f"TW={m.temp_water:.1f} TA={m.temp_air:.1f}"
        )
        self._write(line)

    def update(self, m):
        if m is None:
            return

        state = (
            m.pump1, m.pump2, m.air,
            m.float1, m.float2, m.float3, m.float4,
            m.error_pump1, m.error_pump2,
        )

        if self.last_state is None:
            self.last_state = state
            self._write_line(m)
            return

        if self.last_state == state:
            return

        self.last_state = state
        self._write_line(m)
