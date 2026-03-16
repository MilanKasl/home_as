#gui.py
import tkinter as tk
import time
from datetime import date
from app.gui_style import *
import threading
from app.parser import parse_fve_load_frame

from app.gui_layout import DashboardLayout

from app.cov_logger import CovLogger, CovHistoryStore
from app.reg_logger import RegulatorLogger
from app.parser import parse_cov_frame, parse_reg_frame
from app.ds18b20 import DS18B20
from app.config import (
    TANK_TOP_SENSOR,
    TANK_BOTTOM_SENSOR,
    IN_SIDE_TEMP,
    TUV_TEMP,
)

DEBUG = False

BATT_OFFSET = {
    1: -0.1,   # regulátor 1
}


class DashboardGUI:
    def __init__(self, root: tk.Tk, state, usb):
        # --- ZÁKLAD ---
        self.root = root
        self.state = state
        self.usb = usb
        self.fullscreen = False

        # --- STAVY / TIMING ---
        self.last_data_ts = 0
        self.no_data = True
        self.usb_dead_since = None
        self.USB_WATCHDOG_TIMEOUT = 30
        self.last_temp_read = 0.0

        # --- DATA KONTEJNERY ---
        self._last_values = {}
        self.indicators = {}
        self.cov_history_data = None
        self.last_cov_history_refresh = 0.0
        self.COV_HISTORY_REFRESH_INTERVAL = 60

        # --- HARDWARE ---
        self.ds = DS18B20()

        # --- GUI ---
        self.layout = DashboardLayout(root)
        self.values = self.layout.values

        self.status_label = self.layout.status_label
        self.status_reason = self.layout.status_reason
        self.time_label = self.layout.time_label

        # --- INPUT / FULLSCREEN ---
        self._press_job = None
        self._long_press_time = 1200
        self.root.bind("<ButtonPress-1>", self._on_press)
        self.root.bind("<ButtonRelease-1>", self._on_release)
        self.root.bind("<Escape>", lambda e: self.shutdown())

        
        self.root.protocol("WM_DELETE_WINDOW", self.shutdown)

        # --- LOGGERS ---
        self.reg_logger = RegulatorLogger()
        self.cov_logger = CovLogger()
        self.cov_history = CovHistoryStore()

        # --- IO ---
        self.io_running = True
        self.start_io()        # ⬅️ IO AŽ TADY

        # --- GUI LOOP ---
        self.poll_gui()        # ⬅️ GUI POSLEDNÍ
        self.root.after(400, self.start_fullscreen)








    # =====================================================
    # LOGIKA / AKTUALIZACE
    def poll_gui(self):
        now = time.time()

        # WATCHDOG
        if now - self.last_data_ts > self.USB_WATCHDOG_TIMEOUT:
            if not self.no_data:
                print("USB WATCHDOG: no data")
            self.no_data = True
        else:
            self.no_data = False

        # GUI
        self.update_time()
        self.update_main_view()

        if self.layout.view_cov.winfo_ismapped():
            self.update_cov_view()

        if self.layout.view_fve.winfo_ismapped():
            self.update_fve_view()

        self.update_system_status()

        self.root.after(500, self.poll_gui)


    def io_worker(self):
        while self.io_running:
            try:
                if self.usb.ser is None:
                    self.usb.connect()
                    time.sleep(1)
                    continue

                rx_silence = self.usb.seconds_since_rx()
                conn_age = self.usb.seconds_since_connect()
                if (
                    rx_silence is not None
                    and conn_age is not None
                    and conn_age > self.USB_WATCHDOG_TIMEOUT
                    and rx_silence > self.USB_WATCHDOG_TIMEOUT
                ):
                    print(
                        f"[USB] RX timeout after {rx_silence:.1f}s, reconnecting {self.usb.device}"
                    )
                    self.usb.disconnect()
                    time.sleep(1)
                    continue

                block = self.usb.read_block()
                if block:
                    last_cov = None
                    last_reg = {}

                    last_load = None

                    for line in block:
                        if line.startswith("<"):
                            last_cov = line
                        elif line.startswith("R"):
                            last_reg[line[1]] = line
                        elif line.startswith("FVE:"):
                            last_load = line

                    if last_cov:
                        data = parse_cov_frame(last_cov)
                        if data:
                            self.state.update_from_cov(data)
                            self.last_data_ts = time.time()
                            self.cov_logger.update(self.state.monitoring)

                    for line in last_reg.values():
                        data = parse_reg_frame(line)
                        if data:
                            self.state.update_from_reg(data)
                            self.reg_logger.update(self.state.regulators)
                            self.last_data_ts = time.time()

                    if last_load:
                        data = parse_fve_load_frame(last_load)
                        if data:
                            self.state.update_fve_load(data)
                            self.last_data_ts = time.time() 
                            self.reg_logger.update_load(self.state.fve_load, self.state.regulators)

                # DS18B20
                now = time.time()
                if now - self.last_temp_read > 60:
                    self.last_temp_read = now
                    self.state.tank["TOP"] = self.ds.read_temp(TANK_TOP_SENSOR)
                    self.state.tank["BOTTOM"] = self.ds.read_temp(TANK_BOTTOM_SENSOR)
                    self.state.tank["IN"] = self.ds.read_temp(IN_SIDE_TEMP)
                    self.state.tank["TUV"] = self.ds.read_temp(TUV_TEMP)

            except Exception as e:
                print("IO ERROR:", e)
                try:
                    self.usb.disconnect()
                except:
                    pass
                self.usb.ser = None

            time.sleep(0.1)



    def start_io(self):
        self.io_running = True
        self.io_thread = threading.Thread(
            target=self.io_worker,
            daemon=True
        )
        self.io_thread.start()


    def update_time(self):
        self.time_label.config(text=time.strftime("%H:%M:%S"))


    def update_left_panel(self):
        m = self.state.monitoring

        for k in ["pump1", "pump2", "air",
                "float1", "float2", "float3", "float4"]:
            self.set_indicator(k, getattr(m, k))

        # === TEPLOTY ČOV ===
        if hasattr(m, "temp_water") and m.temp_water is not None:
            self.set_value("temp_water", f"{m.temp_water:.1f} °C")

        if hasattr(m, "temp_air") and m.temp_air is not None:
            self.set_value("temp_air", f"{m.temp_air:.1f} °C")

    def update_main_view(self):
        m = self.state.monitoring
        tank = self.state.tank

        # === ČOV ===
        active_items = []
        has_tech = False
        has_float = False
        for key, label in [
            ("pump1", "Pumpa 1"),
            ("pump2", "Pumpa 2"),
            ("air", "Vzduchování"),
            ("float4", "Plovák 4"),
            ("float3", "Plovák 3"),
            ("float2", "Plovák 2"),
            ("float1", "Plovák 1"),
        ]:
            if getattr(m, key):
                active_items.append(label)
                if key in ("pump1", "pump2", "air"):
                    has_tech = True
                else:
                    has_float = True

        if active_items:
            active_text = "\n".join(f"• {item}" for item in active_items)
        else:
            active_text = "• Žádný"
        self.set_value("main_cov_active", active_text)
        cov_lbl = self.values.get("main_cov_active")
        if cov_lbl:
            color = "#ff9800" if has_float else GREEN_OK if has_tech else FG_MUTED
            cov_lbl.config(fg=color)

        if m.temp_water is not None:
            self.set_value(
                "main_temp_water",
                f"Voda: {m.temp_water:.1f} °C"
            )

        if m.temp_air is not None:
            self.set_value(
                "main_temp_air",
                f"Vzduch: {m.temp_air:.1f} °C"
            )

        self.refresh_cov_history(force=self.cov_history_data is None)
        self.render_main_cov_history(live_temp=m.temp_air)


        # === FVE – souhrn ===
        for rid in (1,):
            r = self.state.regulators.get(rid)
            if not r:
                continue

            self.set_value(
                f"main_r{rid}_batt",
                f"{self.batt_display(rid, r.batt):.2f} V"
            )

            self.set_value(f"main_r{rid}_power", f"{r.power:.0f} W")
            self.set_value(f"main_r{rid}_energy_day", f"{r.energy_today:.0f} W")
            self.set_value(f"main_r{rid}_temp", f"{r.r3111:.0f} °C")
            self.set_charge_state(f"main_r{rid}_state", self.charge_text(r.charge_state))

        load = self.state.fve_load
        self.set_value("main_fve_load", "⇧ ZAPNUTO" if load == 1 else "VYPNUTO")
        load_lbl = self.values.get("main_fve_load")
        if load_lbl:
            load_lbl.config(fg="#ff9800" if load == 1 else FG_MUTED)

        # === TEPLOTY NÁDRŽE ===
        if tank.get("TOP") is not None:
            self.set_value("tank_top", f"{tank['TOP']:.0f} °C")

        if tank.get("BOTTOM") is not None:
            self.set_value("tank_bottom", f"{tank['BOTTOM']:.0f} °C")

        if tank.get("TUV") is not None:
            self.set_value("tank_tuv", f"{tank['TUV']:.0f} °C")

        if tank.get("IN") is not None:
            self.set_value("tank_in", f"{tank['IN']:.1f} °C")



    def update_right_panel(self):
        for rid in (1,):
            r = self.state.regulators[rid]
            self.set_value(f"r{rid}_batt", f"{r.batt:.2f}")
            self.set_value(f"r{rid}_power", f"{r.power:.0f}")
            self.set_value(f"r{rid}_energy_day", f"{r.energy_today:.0f}")
            self.set_value(f"r{rid}_energy_month", f"{r.energy_month:.0f}")
            self.set_value(f"r{rid}_energy_year", f"{r.energy_year:.0f}")
            self.set_value(f"r{rid}_vmax", f"{r.vbat_max_day:.2f}")
            self.set_value(f"r{rid}_vmin", f"{r.vbat_min_day:.2f}")
            self.set_value(f"r{rid}_3111", f"{r.r3111:.0f}")
            self.set_charge_state(f"r{rid}_state", self.charge_text(r.charge_state))

        # === TEPLOTY NÁDRŽE ===
        tank = self.state.tank

        if tank.get("TOP") is not None:
            self.set_value("tank_top", f"{tank['TOP']:.0f} °C")

        if tank.get("BOTTOM") is not None:
            self.set_value("tank_bottom", f"{tank['BOTTOM']:.0f} °C")

        if tank.get("IN") is not None:
            self.set_value("tank_in", f"{tank['IN']:.1f} °C")

        if tank.get("TUV") is not None:
            self.set_value("tank_tuv", f"{tank['TUV']:.0f} °C")

    def update_system_status(self):
        m = self.state.monitoring

        # =================================================
        # 1️⃣ NO DATA – absolutní priorita
        # =================================================
        if self.no_data:
            self.status_label.config(
                text="STAV: NO DATA",
                bg="#555555",
                fg="white"
            )
            self.status_reason.config(text="")

            if "cov_status" in self.values:
                self.values["cov_status"].config(text="NO DATA")

            if "cov_reason" in self.values:
                self.values["cov_reason"].config(text="")
                
            return

        # =================================================
        # 2️⃣ SBĚR CHYB ČOV
        # =================================================
        reasons = []

        # --- ČERPADLA ---
        if m.error_pump1:
            reasons.append("CHYBA ČERPADLA 1")

        if m.error_pump2:
            reasons.append("CHYBA ČERPADLA 2")

        # --- PLOVÁKY (PORUCHOVÉ) ---
        if m.float1:
            reasons.append("PLOVÁK 1 – PORUCHA")

        if m.float2:
            reasons.append("PLOVÁK 2 – PORUCHA")

        if m.float3:
            reasons.append("PLOVÁK 3 – PORUCHA")

        # float4 = pracovní → NEPATŘÍ do ERROR

        # =================================================
        # 3️⃣ VÝSLEDNÝ STAV
        # =================================================
        if reasons:
            reason_text = " | ".join(reasons)

            self.status_label.config(
                text="STAV: ERROR",
                bg=RED_ERR,
                fg="white"
            )

            self.status_reason.config(
                text=reason_text,
                fg="orange"
            )

            if "cov_status" in self.values:
                self.values["cov_status"].config(text="ERROR")

            if "cov_reason" in self.values:
                self.values["cov_reason"].config(
                    text=reason_text,
                    fg="orange"
                )

        else:
            self.status_label.config(
                text="STAV: OK",
                bg=GREEN_OK,
                fg="black"
            )

            self.status_reason.config(text="")

            if "cov_status" in self.values:
                self.values["cov_status"].config(text="OK")

            if "cov_reason" in self.values:
                self.values["cov_reason"].config(text="")

    def update_cov_view(self):
        m = self.state.monitoring

        for key in ["pump1", "pump2", "air",
                    "float1", "float2", "float3", "float4"]:

            item = self.layout.cov_indicators.get(key)
            if not item:                
                continue

            canvas, circle = item
            canvas.itemconfig(circle, fill=GREEN_OK if getattr(m, key) else FG_MUTED)
        # === TEPLOTY ČOV ===
        if m.temp_water is not None:
            self.set_value("cov_temp_water", f"{m.temp_water:.1f} °C")

        if m.temp_air is not None:
            self.set_value("cov_temp_air", f"{m.temp_air:.1f} °C")

        self.refresh_cov_history(force=self.cov_history_data is None)
        self.render_cov_history(live_temp=m.temp_air)

    def update_fve_view(self):
        for rid in (1,):
            r = self.state.regulators.get(rid)
            if not r:
                continue

            self.set_value(
                f"fve{rid}_batt",
                f"{self.batt_display(rid, r.batt):.2f} V"
            )

            self.set_value(f"fve{rid}_power",  f"{r.power:.0f} W")
            self.set_value(f"fve{rid}_energy_day", f"{r.energy_today:.0f} W")
            self.set_value(f"fve{rid}_energy_month", f"{r.energy_month / 1000.0:.2f} kWh")
            self.set_value(f"fve{rid}_energy_year", f"{r.energy_year / 1000.0:.2f} kWh")
            self.set_value(f"fve{rid}_vmax",   f"{r.vbat_max_day:.2f} V")
            self.set_value(f"fve{rid}_vmin",   f"{r.vbat_min_day:.2f} V")
            self.set_value(f"fve{rid}_3111",   f"{r.r3111:.0f} °C")
            self.set_charge_state(
                f"fve{rid}_state",
                self.charge_text(r.charge_state)
            )


    # =====================================================
    # POMOCNÉ
    # =====================================================
    def set_indicator(self, key, state):
        item = self.indicators.get(key)
        if not item:
            return

        last = self._last_values.get(key)
        if last == state:
            return

        canvas, circle = item
        canvas.itemconfig(circle, fill=GREEN_OK if state else FG_MUTED)
        self._last_values[key] = state


    def set_value(self, key, text):
        last = self._last_values.get(key)

        if last == text:
            return  # nic se nezměnilo

        lbl = self.values.get(key)
        if not lbl:
            return

        lbl.config(text=text)
        self._last_values[key] = text


    def set_charge_state(self, key, text):
        lbl = self.values.get(key)
        if not lbl:
            return

        lbl.config(
            text=("⬆ BOOST" if text == "BOOST" else "≈ FLOAT" if text == "FLOAT" else "OFF"),
            fg=COLOR_BOOST if text == "BOOST"
            else COLOR_FLOAT if text == "FLOAT"
            else COLOR_OFF
        )



    def charge_text(self, state):
        return "FLOAT" if state == 1 else "BOOST" if state == 2 else "OFF"

    def refresh_cov_history(self, force=False):
        now = time.time()
        if (
            not force
            and self.cov_history_data is not None
            and now - self.last_cov_history_refresh < self.COV_HISTORY_REFRESH_INTERVAL
        ):
            return

        self.cov_history_data = self.cov_history.get_air_temperature_history(
            today=date.today(),
        )
        self.last_cov_history_refresh = now

    def render_cov_history(self, live_temp=None):
        history = self.cov_history_data or {
            "day": {"min": None, "max": None},
            "month": {"min": None, "max": None},
            "year": {"min": None, "max": None},
            "months": {month: {"min": None, "max": None} for month in range(1, 13)},
        }

        for period in ("day", "month", "year"):
            bucket = dict(history.get(period, {}))
            if live_temp is not None:
                self._merge_temp(bucket, live_temp)
            self.set_value(f"cov_hist_{period}_min", self.format_temp(bucket.get("min")))
            self.set_value(f"cov_hist_{period}_max", self.format_temp(bucket.get("max")))

        months = history.get("months", {})
        for month in range(1, 13):
            bucket = dict(months.get(month, {}))
            if live_temp is not None and month == date.today().month:
                self._merge_temp(bucket, live_temp)
            self.set_value(f"cov_hist_m{month:02d}_min", self.format_temp(bucket.get("min"), compact=True))
            self.set_value(f"cov_hist_m{month:02d}_max", self.format_temp(bucket.get("max"), compact=True))

    def render_main_cov_history(self, live_temp=None):
        history = self.cov_history_data or {"day": {"min": None, "max": None}}
        day_bucket = dict(history.get("day", {}))

        if live_temp is not None:
            self._merge_temp(day_bucket, live_temp)

        self.set_value("main_cov_air_day_min", self.format_temp(day_bucket.get("min")))
        self.set_value("main_cov_air_day_max", self.format_temp(day_bucket.get("max")))

    def format_temp(self, value, compact=False):
        if value is None:
            return "--.-" if compact else "--.- °C"

        formatted = f"{value:.1f}"
        return formatted if compact else f"{formatted} °C"

    def _merge_temp(self, bucket, temp):
        if bucket.get("min") is None or temp < bucket["min"]:
            bucket["min"] = temp
        if bucket.get("max") is None or temp > bucket["max"]:
            bucket["max"] = temp

    def start_fullscreen(self):
        self.root.update_idletasks()   # dopočítá layout
        self.root.attributes("-fullscreen", True)
        self.root.attributes("-topmost", True)
        self.fullscreen = True


    def toggle_fullscreen(self, event=None):
        self.fullscreen = not self.fullscreen

        if self.fullscreen:
            # skutečný fullscreen (bez panelu)
            self.root.attributes("-fullscreen", True)
            self.root.attributes("-topmost", True)
        else:
            # návrat do okna
            self.root.attributes("-fullscreen", False)
            self.root.attributes("-topmost", False)
            self.root.geometry("1024x600")

    def _on_press(self, event):
        # naplánuj long-press
        self._press_job = self.root.after(
            self._long_press_time,
            self._on_long_press
        )


    def _on_release(self, event):
        # pokud uživatel pustil dřív → zruš long-press
        if self._press_job:
            self.root.after_cancel(self._press_job)
            self._press_job = None


    def _on_long_press(self):
        self._press_job = None
        self.toggle_fullscreen()


    def check_data_timeout(self):
        age = time.time() - self.last_data_ts

        if age > 30:  # 30 s bez VALIDNÍCH dat
            if not self.no_data:
                self.no_data = True
                self.usb_dead_since = time.time()
                print("USB watchdog: no data")

        else:
            if self.no_data:
                self.no_data = False
                self.usb_dead_since = None




    def set_no_data_state(self):
        self.status_label.config(
            text="STAV: NO DATA",
            bg="#555555",
            fg="white"
        )

        for lbl in self.values.values():
            lbl.config(fg="#777777")

    def restore_data_state(self):
        self.status_label.config(
            text="STAV: OK",
            bg=GREEN_OK,
            fg="black"
        )

        for lbl in self.values.values():
            lbl.config(fg=FG_MAIN)


    def shutdown(self):
        self.io_running = False
        self.root.destroy()


    def batt_display(self, rid, batt):
        return batt + BATT_OFFSET.get(rid, 0.0)
