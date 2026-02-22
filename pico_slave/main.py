from machine import WDT, Pin
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

# ================= Logika ===================
logic = PowerLogic(
    batt_on=BATT_ON,
    batt_off=BATT_OFF,
    load_power=LOAD_POWER,   # nový parametr
    power_max=POWER_MAX,
)

# ================= Bezpečný start ===========
cov_relay.off()
fve_relay.off()
pwm.off()

# ================= Mega callback ============
def handle_log(val):
    if val == "1":
        cov_relay.on()
    else:
        cov_relay.off()

# ================= Časování ================
last_send = time.ticks_ms() - SEND_INTERVAL_MS


# ================= Hlavní smyčka ============
while True:
# ===== Watchdog aktivace =====
    if not DEV_MODE:
        if wdt is None:
            if time.ticks_diff(time.ticks_ms(), start_time) > WDT_START_DELAY:
                wdt = WDT(timeout=WDT_TIMEOUT)

        if wdt:
            wdt.feed()

    # 1) Mega polling (non-blocking)
    poll_mega(on_log=handle_log)

    # 2) Periodické čtení regulátorů
    if time.ticks_diff(time.ticks_ms(), last_send) >= SEND_INTERVAL_MS:
        last_send = time.ticks_ms()

        for slave in (1, 2):
            data = read_regulator(slave)
            if not data:
                print(f"[Reg {slave}] žádná data")
                continue

            (
                batt_v,
                pv_power,
                extra,
                chg,
                v310e,
                v3304,
                v3111,
            ) = data

            # ===== FVE logika jen pro regulátor 1 =====
            if slave == 1:
                enabled = logic.update(batt_v, pv_power)

                if enabled:
                    fve_relay.on()
                    pwm.set(logic.pwm_value(pv_power))
                    fve_state = 1
                else:
                    pwm.off()
                    fve_relay.off()
                    fve_state = 0

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
                    
            # ===== Debug =====
            # ===== Odeslání rámce na druhé Pico =====
            frame = "<R{}:{:.2f},{:.0f},{:.2f},{},{:.0f},{:.2f},{:.0f}>".format(
                slave,
                batt_v,
                pv_power,
                extra,
                chg,
                v310e,
                v3304,
                v3111,
            )

            send_frame(frame)
            print(f"<FVE:{fve_state}>")

            # Debug do USB
            print(frame)
            time.sleep_ms(1)
