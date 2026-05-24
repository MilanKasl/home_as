import os
import time
import re
from datetime import date, datetime


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
        outdoor_temp = m.temp_outdoor
        if outdoor_temp is None:
            return
        line = (
            f"{ts} "
            f"P1={int(m.pump1)} P2={int(m.pump2)} AIR={int(m.air)} "
            f"MODE={int(m.mode)} "
            f"F1={int(m.float1)} F2={int(m.float2)} "
            f"F3={int(m.float3)} F4={int(m.float4)} "
            f"EP1={int(m.error_pump1)} EP2={int(m.error_pump2)} "
            f"TW={m.temp_water:.1f} TO={outdoor_temp:.1f}"
        )
        self._write(line)

    def update(self, m):
        if m is None:
            return

        state = (
            m.pump1, m.pump2, m.air,
            m.mode,
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


class CovHistoryStore:
    TO_PATTERN = re.compile(r"\bTO=(-?\d+(?:\.\d+)?)")
    TA_PATTERN = re.compile(r"\bTA=(-?\d+(?:\.\d+)?)")

    def __init__(self, base_dir="/home/milan/logs/home_as/cov"):
        self.base_dir = base_dir

    def get_air_temperature_history(self, today=None, live_temp=None):
        today = today or date.today()

        summary = {
            "day": {"min": None, "max": None},
            "month": {"min": None, "max": None},
            "year": {"min": None, "max": None},
            "months": {
                month: {"min": None, "max": None}
                for month in range(1, 13)
            },
        }

        if os.path.isdir(self.base_dir):
            for name in sorted(os.listdir(self.base_dir)):
                if not name.endswith(".log"):
                    continue

                try:
                    file_day = datetime.strptime(name[:-4], "%Y-%m-%d").date()
                except ValueError:
                    continue

                if file_day.year != today.year:
                    continue

                path = os.path.join(self.base_dir, name)
                self._consume_file(path, summary, file_day, today)

        if live_temp is not None:
            self._update(summary["day"], live_temp)
            self._update(summary["month"], live_temp)
            self._update(summary["year"], live_temp)
            self._update(summary["months"][today.month], live_temp)

        return summary

    def _consume_file(self, path, summary, file_day, today):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                for line in handle:
                    match = self.TO_PATTERN.search(line)
                    if not match:
                        match = self.TA_PATTERN.search(line)
                    if not match:
                        continue

                    temp = float(match.group(1))
                    self._update(summary["year"], temp)
                    self._update(summary["months"][file_day.month], temp)

                    if file_day.month == today.month:
                        self._update(summary["month"], temp)

                    if file_day == today:
                        self._update(summary["day"], temp)
        except OSError:
            return

    def _update(self, bucket, temp):
        if bucket["min"] is None or temp < bucket["min"]:
            bucket["min"] = temp
        if bucket["max"] is None or temp > bucket["max"]:
            bucket["max"] = temp
