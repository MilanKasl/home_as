"""Odhad energie spirály z teplot nádrže a skutečného stavu relé AKU."""

from collections import deque
from datetime import datetime, time as clock_time, timedelta
import json
import math
import os
import time

from app.config import (
    FVE_CHARGE_END_HOUR_FALLBACK, FVE_HEATING_STATUS_GAP_S,
    FVE_ENERGY_SAVE_INTERVAL_S, FVE_ENERGY_STATE_PATH,
    FVE_MAX_SAMPLE_GAP_S, FVE_MAX_TEMPERATURE_STEP_C,
    FVE_MAX_ESTIMATED_POWER_W, FVE_POWER_WINDOW_S,
    TANK_HEAT_CAPACITY_KWH_PER_K, TANK_TOP_WEIGHT, TANK_UA_W_PER_K,
)


class FveEnergy:
    def __init__(self, path=FVE_ENERGY_STATE_PATH):
        self.path = path
        self.day = datetime.now().date().isoformat()
        self.energy_today_kwh = 0.0
        self.energy_total_kwh = 0.0
        self.tank_average_c = None
        self.heat_loss_w = None
        self.power_fve_estimated_w = 0.0
        self.energy_since_last_charge_kwh = 0.0
        self.last_discharge_energy_kwh = 0.0
        self.discharge_start_c = None
        self.cycle_phase = "unknown"
        self.charge_end_hour = FVE_CHARGE_END_HOUR_FALLBACK
        self.last_schedule_start_day = None
        self.last_tank_sample = None
        self.last_off_sample = None
        self.previous = None
        self.active = None
        self.active_since = None
        self.heating_timestamp = None
        self.heating_status_known = False
        self.window = deque()
        self.dirty = False
        self.last_save = time.time()
        self._load()

    def _load(self):
        try:
            with open(self.path, encoding="utf-8") as handle:
                saved = json.load(handle)
            today = float(saved["energy_today_kwh"])
            total = float(saved["energy_total_kwh"])
            if not all(math.isfinite(x) and x >= 0 for x in (today, total)) or today > total:
                raise ValueError("invalid energy counters")
            self.energy_total_kwh = total
            if saved.get("day") == self.day:
                self.energy_today_kwh = today
            else:
                self.dirty = True
            self.energy_since_last_charge_kwh = self._stored_energy(
                saved.get("energy_since_last_charge_kwh", 0.0))
            self.last_discharge_energy_kwh = self._stored_energy(
                saved.get("last_discharge_energy_kwh", 0.0))
            phase = saved.get("cycle_phase", "unknown")
            self.cycle_phase = phase if phase in ("unknown", "charging", "discharging") else "unknown"
            start = saved.get("discharge_start_c")
            if start is not None and self._valid_temperature(start):
                self.discharge_start_c = float(start)
            if self.cycle_phase == "discharging" and self.discharge_start_c is None:
                self.cycle_phase = "unknown"
                self.energy_since_last_charge_kwh = 0.0
            end_hour = saved.get("charge_end_hour", FVE_CHARGE_END_HOUR_FALLBACK)
            if isinstance(end_hour, int) and 0 <= end_hour <= 24:
                self.charge_end_hour = end_hour
            start_day = saved.get("last_schedule_start_day")
            if isinstance(start_day, str):
                try:
                    datetime.strptime(start_day, "%Y-%m-%d")
                    self.last_schedule_start_day = start_day
                except ValueError:
                    pass
            self.last_off_sample = self._stored_sample(saved.get("last_off_sample"))
            if "last_schedule_start_day" not in saved and self.cycle_phase == "discharging":
                # Starší soubor mohl spustit cyklus uprostřed denního okna.
                self.cycle_phase = "unknown"
                self.discharge_start_c = None
                self.energy_since_last_charge_kwh = 0.0
                self.last_off_sample = None
                self.dirty = True
        except FileNotFoundError:
            pass
        except (OSError, ValueError, KeyError, TypeError) as exc:
            print("FVE energy state could not be loaded:", exc)

    @staticmethod
    def _stored_energy(value):
        value = float(value)
        if not math.isfinite(value) or value < 0:
            raise ValueError("invalid discharge energy")
        return value

    @classmethod
    def _stored_sample(cls, value):
        if (isinstance(value, list) and len(value) == 2
                and isinstance(value[0], (int, float))
                and math.isfinite(value[0]) and value[0] > 0
                and cls._valid_temperature(value[1])):
            return (float(value[0]), float(value[1]))
        return None

    def _save(self, now, force=False):
        if not self.dirty or (not force and now - self.last_save < FVE_ENERGY_SAVE_INTERVAL_S):
            return
        temporary = self.path + ".tmp"
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(temporary, "w", encoding="utf-8") as handle:
                json.dump({"day": self.day,
                           "energy_today_kwh": self.energy_today_kwh,
                           "energy_total_kwh": self.energy_total_kwh,
                           "energy_since_last_charge_kwh": self.energy_since_last_charge_kwh,
                           "last_discharge_energy_kwh": self.last_discharge_energy_kwh,
                           "discharge_start_c": self.discharge_start_c,
                           "cycle_phase": self.cycle_phase,
                           "charge_end_hour": self.charge_end_hour,
                           "last_schedule_start_day": self.last_schedule_start_day,
                           "last_off_sample": self.last_off_sample}, handle)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
            self.dirty = False
            self.last_save = now
        except OSError as exc:
            print("FVE energy state could not be saved:", exc)

    def tick(self, timestamp=None):
        now = time.time() if timestamp is None else timestamp
        day = datetime.fromtimestamp(now).date().isoformat()
        if day != self.day:
            self.day = day
            self.energy_today_kwh = 0.0
            self.previous = None  # interval přes půlnoc nepočítáme
            self.window.clear()
            self.power_fve_estimated_w = 0.0
            self.dirty = True
            self._save(now, force=True)
        else:
            self._save(now)

    def close(self):
        self._save(time.time(), force=True)

    def set_charge_end_hour(self, hour):
        if isinstance(hour, int) and 0 <= hour <= 24 and hour != self.charge_end_hour:
            self.charge_end_hour = hour
            self.dirty = True

    def _charge_end_timestamp(self, now):
        local_day = datetime.fromtimestamp(now).date()
        if self.charge_end_hour == 24:
            return datetime.combine(local_day, clock_time()).timestamp(), (local_day - timedelta(days=1)).isoformat()
        return (datetime.combine(local_day, clock_time(self.charge_end_hour)).timestamp(),
                local_day.isoformat())

    def observe_heating(self, active, timestamp=None):
        now = time.time() if timestamp is None else timestamp
        if active is None:
            self.heating_status_known = False
            if (self.heating_timestamp is None
                    or now - self.heating_timestamp > FVE_HEATING_STATUS_GAP_S):
                self.previous = None
            self.window.clear()
            self.power_fve_estimated_w = 0.0
            return
        changed = active != self.active
        if active == "K" and changed:
            if self.cycle_phase == "discharging":
                self.last_discharge_energy_kwh = self.energy_since_last_charge_kwh
                self.energy_since_last_charge_kwh = 0.0
                self.discharge_start_c = None
                self.last_off_sample = None
            self.cycle_phase = "charging"
            end_timestamp, schedule_day = self._charge_end_timestamp(now)
            if now >= end_timestamp:
                self.last_schedule_start_day = schedule_day
            self.dirty = True
            self._save(now, force=True)
        gap = (float("inf") if self.heating_timestamp is None
               else now - self.heating_timestamp)
        if changed or gap > FVE_HEATING_STATUS_GAP_S:
            self.active_since = now
            self.previous = None
        if changed or gap > 10:
            self.window.clear()
            self.power_fve_estimated_w = 0.0
        self.active = active
        self.heating_timestamp = now
        self.heating_status_known = True

    @staticmethod
    def _valid_temperature(value):
        return (isinstance(value, (int, float)) and not isinstance(value, bool)
                and math.isfinite(value) and -20 <= value <= 90 and value != 85)

    def sample(self, top, bottom, room, timestamp=None):
        now = time.time() if timestamp is None else timestamp
        self.tick(now)
        if not all(self._valid_temperature(x) for x in (top, bottom)):
            self.tank_average_c = None
            self.heat_loss_w = None
            self.last_tank_sample = None
            # Poslední platný vzorek pro FVE ponecháme pro návrat čidel.
            self.power_fve_estimated_w = 0.0
            return

        average = TANK_TOP_WEIGHT * top + (1 - TANK_TOP_WEIGHT) * bottom
        self.tank_average_c = average
        self._update_discharge(now, average)
        self.last_tank_sample = (now, average)
        if not self._valid_temperature(room):
            self.heat_loss_w = None
            # I výpadek pokojového čidla smí pouze odložit integraci.
            self.power_fve_estimated_w = 0.0
            return
        self.heat_loss_w = TANK_UA_W_PER_K * (average - room)
        if (not self.heating_status_known or self.active != "K"
                or self.heating_timestamp is None
                or now - self.heating_timestamp > 10):
            if (self.active != "K" or self.heating_timestamp is None
                    or now - self.heating_timestamp > FVE_HEATING_STATUS_GAP_S):
                self.previous = None
            self.power_fve_estimated_w = 0.0
            return
        current = (now, top, bottom, room, average)
        previous = self.previous
        self._trim_window(now)
        if previous is None:
            self.previous = current
            return
        start, old_top, old_bottom, old_room, old_average = previous
        seconds = now - start
        if not 0 < seconds <= FVE_MAX_SAMPLE_GAP_S:
            self.previous = current
            self.power_fve_estimated_w = 0.0
            return
        max_step = max(
            FVE_MAX_TEMPERATURE_STEP_C,
            FVE_MAX_ESTIMATED_POWER_W * seconds
            / (TANK_HEAT_CAPACITY_KWH_PER_K * 3_600_000),
        )
        max_room_step = max(FVE_MAX_TEMPERATURE_STEP_C, 10 * seconds / 3600)
        if (abs(top - old_top) > max_step
                or abs(bottom - old_bottom) > max_step
                or abs(room - old_room) > max_room_step):
            self.power_fve_estimated_w = 0.0
            return
        if self.active_since > start:
            self.previous = current
            self.power_fve_estimated_w = 0.0
            return

        delta_aku = TANK_HEAT_CAPACITY_KWH_PER_K * (average - old_average)
        mean_loss_w = TANK_UA_W_PER_K * ((average + old_average - room - old_room) / 2)
        estimate_kwh = delta_aku + mean_loss_w * seconds / 3_600_000
        estimate_w = estimate_kwh * 3_600_000 / seconds
        if not math.isfinite(estimate_w) or abs(estimate_w) > FVE_MAX_ESTIMATED_POWER_W:
            self.power_fve_estimated_w = 0.0
            return
        self.previous = current
        # Záporný výsledek je možný vlivem šumu čidel; vyrobená energie nemůže být záporná.
        energy = max(0.0, estimate_kwh)
        self.energy_today_kwh += energy
        self.energy_total_kwh += energy
        self.dirty = self.dirty or energy > 0
        self.window.append((now, energy, seconds))
        self._trim_window(now)
        duration = sum(item[2] for item in self.window)
        self.power_fve_estimated_w = (sum(item[1] for item in self.window)
                                      * 3_600_000 / duration if duration else 0.0)

    def _update_discharge(self, now, average):
        end_timestamp, schedule_day = self._charge_end_timestamp(now)
        relay_is_on = (self.heating_status_known and self.active == "K"
                       and self.heating_timestamp is not None
                       and now - self.heating_timestamp <= FVE_HEATING_STATUS_GAP_S)
        if self.cycle_phase != "discharging":
            if (now < end_timestamp or self.last_schedule_start_day == schedule_day
                    or relay_is_on):
                return
            previous = self.last_tank_sample
            if (previous is not None and previous[0] <= end_timestamp
                    and 0 < now - previous[0] <= FVE_MAX_SAMPLE_GAP_S):
                fraction = (end_timestamp - previous[0]) / (now - previous[0])
                self.discharge_start_c = previous[1] + (average - previous[1]) * fraction
            else:
                self.discharge_start_c = average
            self.last_schedule_start_day = schedule_day
            self.energy_since_last_charge_kwh = 0.0
            self.last_off_sample = (now, average)
            self.cycle_phase = "discharging"
            self.dirty = True
            self._save(now, force=True)
            return
        if relay_is_on:
            return
        prior = self.last_off_sample
        if prior is not None:
            seconds = now - prior[0]
            # Jednotlivý výpadek čidla nesmí vytvořit velký skok v záznamu.
            if seconds <= 0 or (seconds <= FVE_MAX_SAMPLE_GAP_S
                    and abs(average - prior[1]) > FVE_MAX_TEMPERATURE_STEP_C):
                return
            if seconds > 0 and abs(average - prior[1]) * TANK_HEAT_CAPACITY_KWH_PER_K * 3_600_000 / seconds > FVE_MAX_ESTIMATED_POWER_W:
                return
        energy = max(0.0, TANK_HEAT_CAPACITY_KWH_PER_K * (self.discharge_start_c - average))
        self.energy_since_last_charge_kwh = energy
        self.last_off_sample = (now, average)
        self.dirty = True

    def _trim_window(self, now):
        while self.window and self.window[0][0] <= now - FVE_POWER_WINDOW_S:
            self.window.popleft()
