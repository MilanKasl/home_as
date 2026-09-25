from machine import WDT, Pin  # type: ignore
import time

from config import *
from modbus_ep import read_regulator
from mega_protocol import poll_commands, send_frame
from ds18b20_sensor import DS18B20Sensor
from ds3231 import DS3231
from heating_control import HeatingController, HysteresisRelay, RelayOutput

outdoor_temp = None
last_tuv_temp_read = time.ticks_ms() - TUV_TEMP_READ_INTERVAL_MS
last_outdoor_temp_read = time.ticks_ms() - OUTDOOR_TEMP_READ_INTERVAL_MS
last_sensor_diag = time.ticks_ms() - 60000
last_outdoor_temp_send = time.ticks_ms() - OUTDOOR_TEMP_SEND_INTERVAL_MS
tuv_temp = None
aku_temp = None
last_tuv_valid = None
last_aku_received = None

# ================= Watchdog řízení =================
wdt = None
start_time = time.ticks_ms()

outdoor_sensor = DS18B20Sensor(OUTDOOR_TEMP_PIN, OUTDOOR_TEMP_SENSOR_ROM)
tuv_sensor = DS18B20Sensor(TUV_TEMP_PIN, TUV_TEMP_SENSOR_ROM)
rtc = DS3231(
    RTC_I2C_ID,
    RTC_SDA_PIN,
    RTC_SCL_PIN,
    RTC_I2C_FREQUENCY,
)
heating = HeatingController(
    RelayOutput(Pin(TUV_RELAY_PIN, Pin.OUT), HEATING_RELAY_ACTIVE_HIGH),
    RelayOutput(Pin(AKU_RELAY_PIN, Pin.OUT), HEATING_RELAY_ACTIVE_HIGH),
    HEATING_START_HOUR,
    HEATING_END_HOUR,
    TUV_ON_C,
    TUV_OFF_C,
    AKU_ON_C,
    AKU_OFF_C,
    RELAY_SWITCH_DELAY_MS,
    MANUAL_COMMAND_TIMEOUT_MS,
)
aku_pump = HysteresisRelay(
    RelayOutput(Pin(AKU_PUMP_RELAY_PIN, Pin.OUT), AKU_PUMP_RELAY_ACTIVE_HIGH),
    AKU_PUMP_ON_C,
    AKU_PUMP_OFF_C,
)


def handle_temperature(aku_c):
    global aku_temp, last_aku_received
    aku_temp = aku_c
    last_aku_received = time.ticks_ms()
    print("TEMP RX z Pico Masteru: AKU={} C".format(aku_c))


def handle_heating_mode(mode):
    now = time.ticks_ms()
    if heating.set_mode(mode, now):
        print("OHŘEV RX z Pico Masteru: režim={}".format(mode))


# ================= Časování ================
last_send = time.ticks_ms() - SEND_INTERVAL_MS
last_heating_status_send = time.ticks_ms() - HEATING_STATUS_INTERVAL_MS


# ================= Hlavní smyčka ============
while True:
    try:
        # ===== Watchdog aktivace =====
        if not DEV_MODE:
            if wdt is None:
                if time.ticks_diff(time.ticks_ms(), start_time) > WDT_START_DELAY:
                    wdt = WDT(timeout=WDT_TIMEOUT)

            if wdt:
                wdt.feed()

        poll_commands(
            on_temperature=handle_temperature,
            on_heating_mode=handle_heating_mode,
        )
        now = time.ticks_ms()
        if time.ticks_diff(now, last_outdoor_temp_read) >= OUTDOOR_TEMP_READ_INTERVAL_MS:
            last_outdoor_temp_read = now
            measured_outdoor = outdoor_sensor.read_temp()
            if measured_outdoor is not None:
                outdoor_temp = measured_outdoor

        if time.ticks_diff(now, last_tuv_temp_read) >= TUV_TEMP_READ_INTERVAL_MS:
            last_tuv_temp_read = now
            measured_tuv = tuv_sensor.read_temp()
            if measured_tuv is not None:
                tuv_temp = measured_tuv
                last_tuv_valid = time.ticks_ms()
            else:
                if (last_tuv_valid is None
                        or time.ticks_diff(now, last_tuv_valid) > TUV_TEMP_TIMEOUT_MS):
                    tuv_temp = None
                if time.ticks_diff(now, last_sensor_diag) >= 60000:
                    last_sensor_diag = now
                    print("1-Wire: TUV čidlo na GPIO {} nemá platné měření".format(TUV_TEMP_PIN))
            now = time.ticks_ms()

        aku_fresh = (
            last_aku_received is not None
            and time.ticks_diff(now, last_aku_received) <= TEMPERATURE_TIMEOUT_MS
        )
        tuv_fresh = (
            tuv_temp is not None and last_tuv_valid is not None
            and time.ticks_diff(now, last_tuv_valid) <= TUV_TEMP_TIMEOUT_MS
        )
        rtc_time = rtc.read_time()
        heating.update(
            now,
            rtc_time,
            tuv_temp if tuv_fresh else None,
            aku_temp if aku_fresh else None,
        )
        pump_time_allowed = heating.is_in_window(rtc_time)
        aku_pump.update(
            aku_temp if aku_fresh and pump_time_allowed else None
        )

        if time.ticks_diff(now, last_heating_status_send) >= HEATING_STATUS_INTERVAL_MS:
            last_heating_status_send = now
            heat = heating.diagnostics(now)
            active_code = {
                heating.TUV: "T",
                heating.AKU: "K",
            }.get(heating.active, "0")
            send_frame("<HEAT:{},{},{},{},{}>".format(
                heat["mode"], active_code, heat["reason"], HEATING_END_HOUR,
                "{:.2f}".format(tuv_temp) if tuv_fresh else ""
            ))

        if (
            outdoor_temp is not None
            and time.ticks_diff(now, last_outdoor_temp_send) >= OUTDOOR_TEMP_SEND_INTERVAL_MS
        ):
            last_outdoor_temp_send = now
            send_frame(f"<OUT:{outdoor_temp:.2f}>")

        # 2) Periodické čtení regulátoru 1
        if time.ticks_diff(time.ticks_ms(), last_send) >= SEND_INTERVAL_MS:
            last_send = time.ticks_ms()
            slave = 1
            data = read_regulator(slave)
            if not data:
                print(f"[Reg {slave}] žádná data")
                continue

            (
                batt_v,
                pv_power,
                eng_today,
                eng_month,
                eng_year,
                chg,
                v3302,
                v3303,
                v3111,
            ) = data

            # ===== Odeslání rámce na druhé Pico =====
            if None in (batt_v, pv_power, eng_today, eng_month, eng_year, chg, v3302, v3303, v3111):
                print(f"[Reg {slave}] neplatná/neúplná data")
                continue

            frame = "<R{}:{:.2f},{:.0f},{:.0f},{:.0f},{:.0f},{},{:.2f},{:.2f},{:.0f}>".format(
                slave,
                batt_v,
                pv_power,
                eng_today,
                eng_month,
                eng_year,
                chg,
                v3302,
                v3303,
                v3111,
            )

            send_frame(frame)

            # Debug do USB
            print(frame)
            if rtc_time is None:
                print("RTC: neplatný čas")
            else:
                hour, minute, second = rtc_time
                print("RTC: {:02d}:{:02d}:{:02d}".format(hour, minute, second))

            if last_aku_received is None:
                print("TEMP AKU: od startu nepřišel žádný rámec z Pico Masteru")
            else:
                temperature_age = time.ticks_diff(now, last_aku_received)
                print(
                    "TEMP: TUV lokálně={} C, AKU={} C, stáří AKU={} ms, platné={}".format(
                        tuv_temp if tuv_fresh else "neplatná",
                        aku_temp,
                        temperature_age,
                        "ANO" if aku_fresh else "NE",
                    )
                )

            heat = heating.diagnostics(now)
            print(
                "OHŘEV: aktivní={}, čeká={}, TUV požadavek={}, AKU požadavek={}, "
                "relé TUV={}, relé AKU={}, prodleva={} ms".format(
                    heat["active"],
                    heat["pending"],
                    "ANO" if heat["tuv_call"] else "NE",
                    "ANO" if heat["aku_call"] else "NE",
                    "ZAP" if heat["tuv_relay"] else "VYP",
                    "ZAP" if heat["aku_relay"] else "VYP",
                    heat["remaining_ms"],
                )
            )
            print(
                "ČERPADLO AKU: {} (časové okno={}; AKU {} C; sepne od {} C, vypne při {} C)".format(
                    "ZAP" if aku_pump.relay.is_on else "VYP",
                    "ANO" if pump_time_allowed else "NE",
                    aku_temp if aku_fresh else "neplatná teplota",
                    AKU_PUMP_ON_C,
                    AKU_PUMP_OFF_C,
                )
            )
            time.sleep_ms(1)
    except Exception as e:
        # Poslední záchrana: držet firmware živý i při neočekávané chybě.
        print("Loop error:", e)
        time.sleep_ms(20)
