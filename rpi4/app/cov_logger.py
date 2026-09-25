import os
import time
import re
import json
import math
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
        line = (
            f"{ts} "
            f"P1={int(m.pump1)} P2={int(m.pump2)} AIR={int(m.air)} "
            f"MODE={int(m.mode)} "
            f"F1={int(m.float1)} F2={int(m.float2)} "
            f"F3={int(m.float3)} F4={int(m.float4)} "
            f"EP1={int(m.error_pump1)} EP2={int(m.error_pump2)}"
        )
        self._write(line)

    def update(self, m, cov_fresh=True):
        if m is None or not cov_fresh:
            return

        state = (
            m.pump1, m.pump2, m.air,
            m.mode,
            m.float1, m.float2, m.float3, m.float4,
            m.error_pump1, m.error_pump2,
        )

        if self.last_state == state:
            return

        self.last_state = state
        self._write_line(m)


class CovHistoryStore:
    TO_PATTERN = re.compile(r"\bTO=(-?\d+(?:\.\d+)?)")
    TA_PATTERN = re.compile(r"\bTA=(-?\d+(?:\.\d+)?)")

    def __init__(self, base_dir="/home/milan/logs/home_as/cov",
                 temperature_dir="/home/milan/logs/home_as/outdoor_temperature"):
        self.base_dir = base_dir
        self.temperature_dir = temperature_dir

    def record_air_temperature(self, temp, day=None):
        """Uloží pouze změnu denního minima/maxima, mimo stavový log ČOV."""
        if temp is None or not math.isfinite(temp):
            return

        day = day or date.today()
        value = round(temp, 1)
        path = os.path.join(self.temperature_dir, f"{day.isoformat()}.json")
        bucket = self._read_temperature_file(path)
        if bucket is None:
            new_min = new_max = value
        else:
            new_min = min(bucket["min"], value)
            new_max = max(bucket["max"], value)
            if new_min == bucket["min"] and new_max == bucket["max"]:
                return

        os.makedirs(self.temperature_dir, exist_ok=True)
        temporary_path = path + ".tmp"
        try:
            with open(temporary_path, "w", encoding="utf-8") as handle:
                json.dump({"min": new_min, "max": new_max}, handle)
                handle.write("\n")
            os.replace(temporary_path, path)
        finally:
            if os.path.exists(temporary_path):
                os.unlink(temporary_path)

    def _read_temperature_file(self, path):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            minimum = float(data["min"])
            maximum = float(data["max"])
            if math.isfinite(minimum) and math.isfinite(maximum) and minimum <= maximum:
                return {"min": minimum, "max": maximum}
        except (OSError, ValueError, TypeError, KeyError):
            pass
        return None

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

        if os.path.isdir(self.temperature_dir):
            for name in sorted(os.listdir(self.temperature_dir)):
                if not name.endswith(".json"):
                    continue
                try:
                    file_day = datetime.strptime(name[:-5], "%Y-%m-%d").date()
                except ValueError:
                    continue
                if file_day.year != today.year:
                    continue
                bucket = self._read_temperature_file(os.path.join(self.temperature_dir, name))
                if bucket is not None:
                    for temp in (bucket["min"], bucket["max"]):
                        self._update_for_day(summary, temp, file_day, today)

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
                    self._update_for_day(summary, temp, file_day, today)
        except OSError:
            return

    def _update_for_day(self, summary, temp, file_day, today):
        self._update(summary["year"], temp)
        self._update(summary["months"][file_day.month], temp)
        if file_day.month == today.month:
            self._update(summary["month"], temp)
        if file_day == today:
            self._update(summary["day"], temp)

    def _update(self, bucket, temp):
        if bucket["min"] is None or temp < bucket["min"]:
            bucket["min"] = temp
        if bucket["max"] is None or temp > bucket["max"]:
            bucket["max"] = temp


class CovPumpCycleStore:
    STATE_PATTERN = re.compile(r"\bP1=(\d+)\s+P2=(\d+)")

    def __init__(self, base_dir="/home/milan/logs/home_as/cov"):
        self.base_dir = base_dir

    def get_last_cycles(self, limit=10, max_files=14):
        if not os.path.isdir(self.base_dir):
            return []

        log_files = []
        for name in sorted(os.listdir(self.base_dir), reverse=True):
            if not name.endswith(".log"):
                continue

            try:
                file_day = datetime.strptime(name[:-4], "%Y-%m-%d").date()
            except ValueError:
                continue

            log_files.append((file_day, os.path.join(self.base_dir, name)))
            if len(log_files) >= max_files:
                break

        cycles = []
        active_cycle = None
        pump_starts = {1: None, 2: None}
        last_state = {1: 0, 2: 0}

        for file_day, path in sorted(log_files):
            active_cycle = self._consume_file(
                path,
                file_day,
                cycles,
                active_cycle,
                pump_starts,
                last_state,
            )

        return cycles[-limit:][::-1]

    def _consume_file(self, path, file_day, cycles, active_cycle, pump_starts, last_state):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                for line in handle:
                    if len(line) < 8:
                        continue

                    match = self.STATE_PATTERN.search(line)
                    if not match:
                        continue

                    try:
                        timestamp = datetime.combine(
                            file_day,
                            datetime.strptime(line[:8], "%H:%M:%S").time(),
                        )
                    except ValueError:
                        continue

                    states = {
                        1: int(match.group(1)),
                        2: int(match.group(2)),
                    }

                    if active_cycle is None and (states[1] or states[2]):
                        active_cycle = {
                            "started_at": timestamp,
                            "ended_at": None,
                            "pump1_seconds": None,
                            "pump2_seconds": None,
                        }

                    for pump_no in (1, 2):
                        previous = last_state[pump_no]
                        current = states[pump_no]

                        if previous == 0 and current == 1:
                            if active_cycle is None:
                                active_cycle = {
                                    "started_at": timestamp,
                                    "ended_at": None,
                                    "pump1_seconds": None,
                                    "pump2_seconds": None,
                                }
                            pump_starts[pump_no] = timestamp

                        elif previous == 1 and current == 0 and pump_starts[pump_no] is not None:
                            elapsed = (timestamp - pump_starts[pump_no]).total_seconds()
                            key = f"pump{pump_no}_seconds"
                            if elapsed >= 0 and active_cycle is not None:
                                active_cycle[key] = int(elapsed)
                                active_cycle["ended_at"] = timestamp
                            pump_starts[pump_no] = None

                    if (
                        active_cycle is not None
                        and states[1] == 0
                        and states[2] == 0
                        and (
                            active_cycle["pump1_seconds"] is not None
                            or active_cycle["pump2_seconds"] is not None
                        )
                    ):
                        cycles.append(active_cycle)
                        active_cycle = None

                    last_state.update(states)
        except OSError:
            return active_cycle

        return active_cycle
