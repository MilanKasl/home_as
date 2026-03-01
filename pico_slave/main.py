from machine import WDT, Pin  # type: ignore
import time

from config import *
from relay_control import RelayControl
from pwm_control import PWMControl
from power_logic import PowerLogic
from modbus_ep import read_regulator
from mega_protocol import poll_mega, send_frame

#============vytěžování-stav=========
FVE_REPEAT_INTERVAL = 30000  # 30 sekund
last_fve_send_time = 0
fve_state_last = None
fve_state_current = 0
cov_log_request = 0

# ================= Watchdog řízení =================
wdt = None
start_time = time.ticks_ms()

# ================= Piny =====================
COV_RELAY_PIN = 15      # Mega → AC měnič (COV)
FVE_RELAY_PIN = 16      # Pico → DC měnič (nadvýroba)
PWM_PIN       = 14

# ================= Výstupy ==================
cov_relay = RelayControl(Pin(COV_RELAY_PIN))
fve_relay = RelayControl(Pin(FVE_RELAY_PIN))
pwm = PWMControl(Pin(PWM_PIN))   # test: žárovka / MOSFET
sun_pull = Pin.PULL_UP if SUN_SENSOR_PULLUP else None
sun_input = Pin(SUN_SENSOR_PIN, Pin.IN, sun_pull)

# ================= Logika ===================
logic = PowerLogic(
    batt_on=BATT_ON,
    batt_off=BATT_OFF,
    batt_protect=BATT_PROTECT,
    load_power=LOAD_POWER,   # nový parametr
    power_max=POWER_MAX,
)

# ================= Bezpečný start ===========
cov_relay.off()
fve_relay.off()
pwm.off()

# ================= Mega callback ============
def apply_cov_output():
    if cov_log_request or fve_state_current:
        cov_relay.on()
    else:
        cov_relay.off()


def handle_log(val):
    global cov_log_request
    cov_log_request = 1 if val == "1" else 0
    apply_cov_output()


def is_sun_ok():
    return 1 if sun_input.value() == SUN_SENSOR_ACTIVE_LEVEL else 0

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
                pwm.off()
                fve_relay.off()
                fve_state = 0
            else:
                enabled = logic.update(batt_v, pv_power, sun_ok=is_sun_ok())
                if enabled:
                    fve_relay.on()
                    pwm.set(logic.pwm_value(pv_power))
                    fve_state = 1
                else:
                    pwm.off()
                    fve_relay.off()
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
