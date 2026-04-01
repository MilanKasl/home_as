# main.py – Pico Master

from machine import UART, Pin
import time

from state import SystemState
from rs485 import read_uart
from parser import parse_cov, parse_reg, parse_fve, parse_outdoor
from machine import WDT
from pio_uart_tx import PIOUARTTx

# ================= Watchdog řízení =================
DEV_MODE = False         # při ladění True, v provozu False
WDT_START_DELAY = 60000  # 60 s po startu
WDT_TIMEOUT = 8000       # max pro RP2350
HOST_UART_BAUDRATE = 115200
HOST_UART_TX_PIN = 8

wdt = None
start_time = time.ticks_ms()


# ==============================
# STAV LOGIKY
# ==============================
last_air_state = None
AIR_REPEAT_INTERVAL = 60000  # 60 sekund
last_air_send_time = 0
last_fve_state = None
FVE_REPEAT_INTERVAL = 60000  # 60 sekund
last_fve_send_time = 0

def send_regulator_logic(uart, state):
    """
    Pošle povel regulátorům:
    <LOG:0> nebo <LOG:1>
    """
    uart.write(f"<LOG:{state}>")


# ==============================
# UARTy – RS485 vstupy
# ==============================
uart_cov = UART(0, baudrate=9600, tx=Pin(0), rx=Pin(1))
uart_fve = UART(1, baudrate=9600, tx=Pin(4), rx=Pin(5))


# ==============================
# STAV SYSTÉMU
# ==============================
state = SystemState()

buf_cov = ""
buf_fve = ""
last_send = time.ticks_ms()
host_uart = PIOUARTTx(sm_id=0, pin_num=HOST_UART_TX_PIN, baudrate=HOST_UART_BAUDRATE)


def write_host_lines(lines):
    payload = "\n" + "\n".join(lines) + "\n\n"
    host_uart.write(payload)


def effective_outdoor_temp(state):
    ta = state.stat["TA"]
    to = state.stat["TO"]
    if to is None:
        return ta
    return to if to < ta else ta



# ==============================
# HLAVNÍ SMYČKA
# ==============================
while True:
    try:
        # ----- ČOV -----
        frame, buf_cov = read_uart(uart_cov, buf_cov)
        if frame:
            parse_cov(frame, state)

        # ----- FVE -----
        frame, buf_fve = read_uart(uart_fve, buf_fve)
        if frame:
            if not parse_fve(frame, state) and not parse_outdoor(frame, state):
                parse_reg(frame, state)

        #------FVE přebytek------
        fve = state.fve["LOAD"]
        now = time.ticks_ms()

        # ===== při změně okamžitě =====
        if last_fve_state is None or fve != last_fve_state:
            last_fve_state = fve
            last_fve_send_time = now
            uart_cov.write(f"<FVE:{fve}>\n")

        # ===== periodické potvrzení =====
        elif time.ticks_diff(now, last_fve_send_time) > FVE_REPEAT_INTERVAL:
            last_fve_send_time = now
            uart_cov.write(f"<FVE:{fve}>\n")     

        # ----- LOGIKA -----
        air = state.stat["AIR"]
        if last_air_state is None or air != last_air_state:
            last_air_state = air
            last_air_send_time = now
            send_regulator_logic(uart_fve, air)
        elif time.ticks_diff(now, last_air_send_time) > AIR_REPEAT_INTERVAL:
            last_air_send_time = now
            send_regulator_logic(uart_fve, air)

        # ----- USB OUTPUT -----
        if time.ticks_diff(time.ticks_ms(), last_send) > 500:
            last_send = time.ticks_ms()
            out = []
            outdoor_temp = effective_outdoor_temp(state)

            out.append(
                "<{},{},{},{},{:.1f},{:.1f},{},{},{}>".format(
                    state.stat["P1"],
                    state.stat["P2"],
                    state.stat["AIR"],
                    state.float_mask(),
                    state.stat["TW"],
                    outdoor_temp,
                    state.stat["EP1"],
                    state.stat["EP2"],
                    "{:.1f}".format(state.stat["TO"]) if state.stat["TO"] is not None else "",
                )
            )
            
            out.append(
                "FVE:{}".format(state.fve["LOAD"])
            )

            r1 = state.reg[1]

            out.append(
                "R1:{:.2f},{:.0f},{:.0f},{:.0f},{:.0f},{},{:.2f},{:.2f},{:.2f}".format(
                    r1["BATT"], r1["PWR"], r1["ENG_DAY"], r1["ENG_MONTH"], r1["ENG_YEAR"], r1["CH"],
                    r1["VBAT_MAX_DAY"], r1["VBAT_MIN_DAY"], r1["R3111"]
                )
            )

            write_host_lines(out)

    except Exception:
        # poslední záchrana – NEZASTAVUJ firmware
        pass

    # ===== Watchdog aktivace =====
    if not DEV_MODE:
        if wdt is None:
            if time.ticks_diff(time.ticks_ms(), start_time) > WDT_START_DELAY:
                wdt = WDT(timeout=WDT_TIMEOUT)

        if wdt:
            wdt.feed()
    time.sleep_ms(5)
