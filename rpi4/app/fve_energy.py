"""Odhad energie spirály z teplot nádrže a skutečného stavu relé AKU."""

from datetime import datetime
import json
import math
import os
import time

from app.config import (
    FVE_HEATING_STATUS_GAP_S,
    FVE_ENERGY_SAVE_INTERVAL_S, FVE_ENERGY_STATE_PATH,
    FVE_MAX_SAMPLE_GAP_S, FVE_MAX_TEMPERATURE_STEP_C,
    FVE_MAX_ESTIMATED_POWER_W,
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
        self.previous = None
        self.active = None
        self.active_since = None
        self.heating_timestamp = None
        self.heating_status_known = False
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
        except FileNotFoundError:
            pass
        except (OSError, ValueError, KeyError, TypeError) as exc:
            print("FVE energy state could not be loaded:", exc)

    def _save(self, now, force=False):
        if not self.dirty or (not force and now - self.last_save < FVE_ENERGY_SAVE_INTERVAL_S):
            return
        temporary = self.path + ".tmp"
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(temporary, "w", encoding="utf-8") as handle:
                json.dump({"day": self.day,
                           "energy_today_kwh": self.energy_today_kwh,
                           "energy_total_kwh": self.energy_total_kwh}, handle)
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
            self.dirty = True
            self._save(now, force=True)
        else:
            self._save(now)

    def close(self):
        self._save(time.time(), force=True)

    def observe_heating(self, active, timestamp=None):
        now = time.time() if timestamp is None else timestamp
        if active is None:
            self.heating_status_known = False
            if (self.heating_timestamp is None
                    or now - self.heating_timestamp > FVE_HEATING_STATUS_GAP_S):
                self.previous = None
            return
        changed = active != self.active
        gap = (float("inf") if self.heating_timestamp is None
               else now - self.heating_timestamp)
        if changed or gap > FVE_HEATING_STATUS_GAP_S:
            self.active_since = now
            self.previous = None
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
            # Poslední platný vzorek pro FVE ponecháme pro návrat čidel.
            return

        average = TANK_TOP_WEIGHT * top + (1 - TANK_TOP_WEIGHT) * bottom
        self.tank_average_c = average
        if not self._valid_temperature(room):
            self.heat_loss_w = None
            # I výpadek pokojového čidla smí pouze odložit integraci.
            return
        self.heat_loss_w = TANK_UA_W_PER_K * (average - room)
        if (not self.heating_status_known or self.active != "K"
                or self.heating_timestamp is None
                or now - self.heating_timestamp > 10):
            if (self.active != "K" or self.heating_timestamp is None
                    or now - self.heating_timestamp > FVE_HEATING_STATUS_GAP_S):
                self.previous = None
            return
        current = (now, top, bottom, room, average)
        previous = self.previous
        if previous is None:
            self.previous = current
            return
        start, old_top, old_bottom, old_room, old_average = previous
        seconds = now - start
        if not 0 < seconds <= FVE_MAX_SAMPLE_GAP_S:
            self.previous = current
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
            return
        if self.active_since > start:
            self.previous = current
            return

        delta_aku = TANK_HEAT_CAPACITY_KWH_PER_K * (average - old_average)
        mean_loss_w = TANK_UA_W_PER_K * ((average + old_average - room - old_room) / 2)
        estimate_kwh = delta_aku + mean_loss_w * seconds / 3_600_000
        max_energy_kwh = FVE_MAX_ESTIMATED_POWER_W * seconds / 3_600_000
        if not math.isfinite(estimate_kwh) or abs(estimate_kwh) > max_energy_kwh:
            return
        self.previous = current
        # Záporný výsledek je možný vlivem šumu čidel; vyrobená energie nemůže být záporná.
        energy = max(0.0, estimate_kwh)
        self.energy_today_kwh += energy
        self.energy_total_kwh += energy
        self.dirty = self.dirty or energy > 0
