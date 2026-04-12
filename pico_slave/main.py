from machine import WDT, Pin  # type: ignore
import time

from config import *
from relay_control import RelayControl
from power_logic import PowerLogic
from ssr_burst_control import SSRBurstControl
from boiler_dump_logic import BoilerDumpLogic
from modbus_ep import read_regulator
from mega_protocol import poll_mega, send_frame
from ds18b20_sensor import DS18B20Sensor

#============vytěžování-stav=========
FVE_REPEAT_INTERVAL = 30000  # 30 sekund
last_fve_send_time = 0
fve_state_last = None
fve_state_current = 0
cov_log_request = 0
cov_log_prev = 0
aux_relay_trigger_at = None
aux_relay_pulse_until = None
outdoor_temp = None
boiler_temp = None
boiler_temp_ready = False
boiler_duty_current = 0.0
last_outdoor_temp_read = time.ticks_ms() - OUTDOOR_TEMP_READ_INTERVAL_MS
last_outdoor_temp_send = time.ticks_ms() - OUTDOOR_TEMP_SEND_INTERVAL_MS
last_boiler_temp_read = time.ticks_ms() - BOILER_TEMP_READ_INTERVAL_MS

# ================= Watchdog řízení =================
wdt = None
start_time = time.ticks_ms()

# ================= Výstupy ==================
cov_relay = RelayControl(Pin(COV_RELAY_PIN))
fve_relay = RelayControl(Pin(FVE_RELAY_PIN))
aux_relay = RelayControl(Pin(AUX_RELAY_PIN), active_high=AUX_RELAY_ACTIVE_HIGH)
ssr = SSRBurstControl(
    Pin(SSR_PIN),
    period_ms=SSR_BURST_PERIOD_MS,
    active_high=SSR_ACTIVE_HIGH,
)
sun_pull = Pin.PULL_UP if SUN_SENSOR_PULLUP else None
sun_input = Pin(SUN_SENSOR_PIN, Pin.IN, sun_pull)
fve_enable_pull = Pin.PULL_UP if FVE_ENABLE_BUTTON_PULLUP else None
fve_enable_input = Pin(FVE_ENABLE_BUTTON_PIN, Pin.IN, fve_enable_pull)
boiler_enable_pull = Pin.PULL_UP if BOILER_ENABLE_BUTTON_PULLUP else None
boiler_enable_input = Pin(BOILER_ENABLE_BUTTON_PIN, Pin.IN, boiler_enable_pull)
outdoor_sensor = DS18B20Sensor(OUTDOOR_TEMP_PIN, OUTDOOR_TEMP_SENSOR_ROM)
boiler_sensor = DS18B20Sensor(BOILER_TEMP_PIN, BOILER_TEMP_SENSOR_ROM)

# ================= Logika ===================
cov_logic = PowerLogic(
    batt_on=BATT_ON,
    batt_off=BATT_OFF,
    batt_protect=BATT_PROTECT,
    load_power=LOAD_POWER,   # nový parametr
    power_max=POWER_MAX,
)
boiler_gate_logic = PowerLogic(
    batt_on=BATT_ON,
    batt_off=BATT_OFF,
    batt_protect=BATT_PROTECT,
    load_power=LOAD_POWER,
    power_max=POWER_MAX,
)
boiler_logic = BoilerDumpLogic(
    heater_power_w=BOILER_HEATER_POWER_W,
    power_reserve_w=BOILER_POWER_RESERVE_W,
    v_min=BOILER_V_MIN,
    v_limit=BOILER_V_LIMIT,
    v_critical=BOILER_V_CRITICAL,
    duty_step_up=BOILER_DUTY_STEP_UP,
    duty_step_down=BOILER_DUTY_STEP_DOWN,
    duty_step_fast_down=BOILER_DUTY_STEP_FAST_DOWN,
    step_up_interval_ms=BOILER_STEP_UP_INTERVAL_MS,
    step_down_interval_ms=BOILER_STEP_DOWN_INTERVAL_MS,
    good_cycles_to_step_up=BOILER_GOOD_CYCLES_TO_STEP_UP,
    bad_cycles_to_step_down=BOILER_BAD_CYCLES_TO_STEP_DOWN,
    battery_avg_alpha=BOILER_BATTERY_AVG_ALPHA,
    battery_trend_epsilon=BOILER_BATTERY_TREND_EPSILON,
)

# ================= Bezpečný start ===========
cov_relay.off()
fve_relay.off()
aux_relay.off()
ssr.set_duty(0.0)
ssr.off()

# ================= Mega callback ============
def apply_cov_output():
    if cov_log_request or fve_state_current:
        cov_relay.on()
    else:
        cov_relay.off()


def handle_log(val):
    global cov_log_request, cov_log_prev, aux_relay_trigger_at
    cov_log_request = 1 if val == "1" else 0
    if cov_log_request and not cov_log_prev:
        aux_relay_trigger_at = time.ticks_add(time.ticks_ms(), AUX_RELAY_DELAY_MS)
    cov_log_prev = cov_log_request
    apply_cov_output()


def is_sun_ok():
    return 1 if sun_input.value() == SUN_SENSOR_ACTIVE_LEVEL else 0


def is_fve_enabled():
    return 1 if fve_enable_input.value() == FVE_ENABLE_ACTIVE_LEVEL else 0


def is_boiler_enabled():
    return 1 if boiler_enable_input.value() == BOILER_ENABLE_ACTIVE_LEVEL else 0


def update_boiler_temp_ready():
    global boiler_temp_ready

    if boiler_temp is None:
        boiler_temp_ready = False
        return

    if boiler_temp_ready:
        if boiler_temp >= BOILER_TEMP_TARGET_C:
            boiler_temp_ready = False
    elif boiler_temp <= (BOILER_TEMP_TARGET_C - BOILER_TEMP_HYSTERESIS_C):
        boiler_temp_ready = True


def update_aux_relay(now):
    global aux_relay_trigger_at, aux_relay_pulse_until

    if aux_relay_pulse_until is not None:
        if time.ticks_diff(now, aux_relay_pulse_until) >= 0:
            aux_relay.off()
            aux_relay_pulse_until = None
        else:
            aux_relay.on()
        return

    if aux_relay_trigger_at is not None and time.ticks_diff(now, aux_relay_trigger_at) >= 0:
        aux_relay_trigger_at = None
        aux_relay_pulse_until = time.ticks_add(now, AUX_RELAY_PULSE_MS)
        aux_relay.on()
        return

    aux_relay.off()

# ================= Časování ================
last_send = time.ticks_ms() - SEND_INTERVAL_MS


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

        # 1) Mega polling (non-blocking)
        poll_mega(on_log=handle_log)
        now = time.ticks_ms()
        update_aux_relay(now)
        ssr.update(now)

        if time.ticks_diff(now, last_outdoor_temp_read) >= OUTDOOR_TEMP_READ_INTERVAL_MS:
            last_outdoor_temp_read = now
            measured_temp = outdoor_sensor.read_temp()
            if measured_temp is not None:
                outdoor_temp = measured_temp

        if time.ticks_diff(now, last_boiler_temp_read) >= BOILER_TEMP_READ_INTERVAL_MS:
            last_boiler_temp_read = now
            measured_boiler_temp = boiler_sensor.read_temp()
            if measured_boiler_temp is not None:
                boiler_temp = measured_boiler_temp
                update_boiler_temp_ready()

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

            # Při ztrátě linky držet bezpečný stav a nezastavit smyčku.
            if batt_v is None or pv_power is None:
                ssr.set_duty(0.0)
                fve_relay.off()
                cov_logic.reset()
                boiler_gate_logic.reset()
                boiler_logic.reset()
                fve_state = 0
            else:
                sun_ok = is_sun_ok()
                cov_button = bool(is_fve_enabled())
                boiler_button = bool(is_boiler_enabled())

                cov_allowed = cov_button and cov_logic.update(batt_v, pv_power, sun_ok=sun_ok)
                if not cov_button:
                    cov_logic.reset()

                if boiler_button:
                    boiler_gate_enabled = boiler_gate_logic.update(batt_v, pv_power, sun_ok=sun_ok)
                else:
                    boiler_gate_enabled = False
                    boiler_gate_logic.reset()

                boiler_allowed = boiler_gate_enabled and boiler_temp_ready

                # Pokud jsou povolené obě větve a boiler ještě nedosáhl cíle,
                # boiler dostane prioritu a ČOV zůstane dočasně blokovaná.
                boiler_priority = cov_allowed and boiler_allowed
                cov_output_enabled = cov_allowed and not boiler_priority

                if cov_output_enabled:
                    fve_relay.on()
                else:
                    fve_relay.off()

                boiler_duty_current = boiler_logic.update(
                    now_ms=now,
                    enabled=boiler_allowed,
                    batt_v=batt_v,
                    pv_power=pv_power,
                )
                ssr.set_duty(boiler_duty_current)

                if cov_output_enabled or boiler_duty_current > 0.0:
                    fve_state = 1
                else:
                    fve_state = 0

            fve_state_current = fve_state
            apply_cov_output()

            # ===== Odeslat změnu stavu =====
            now = time.ticks_ms()

            # ===== při změně okamžitě =====
            if fve_state_last is None or fve_state != fve_state_last:
                fve_state_last = fve_state
                last_fve_send_time = now
                send_frame(f"<FVE:{fve_state}>")

            # ===== periodické opakování =====
            elif time.ticks_diff(now, last_fve_send_time) > FVE_REPEAT_INTERVAL:
                last_fve_send_time = now
                send_frame(f"<FVE:{fve_state}>")

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
            print(f"<FVE:{fve_state_current}>")

            # Debug do USB
            print(frame)
            time.sleep_ms(1)
    except Exception as e:
        # Poslední záchrana: držet firmware živý i při neočekávané chybě.
        print("Loop error:", e)
        time.sleep_ms(20)
