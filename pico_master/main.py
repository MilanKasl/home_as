# main.py – Pico (USB CDC verze)

from machine import UART, Pin
import time
import sys

from state import SystemState
from rs485 import read_uart
from parser import parse_cov, parse_reg, parse_fve
from machine import WDT

# ================= Watchdog řízení =================
DEV_MODE = True          # při ladění True, v provozu False
WDT_START_DELAY = 60000  # 60 s po startu
WDT_TIMEOUT = 8000       # max pro RP2350

wdt = None
start_time = time.ticks_ms()

def log(*args):
    print(*args)


# ==============================
# STAV LOGIKY
# ==============================
last_air_state = None
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
            if not parse_fve(frame, state):
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
        if last_air_state is None:
            last_air_state = air
        elif air != last_air_state:
            last_air_state = air
            send_regulator_logic(uart_fve, air)

        # ----- USB OUTPUT -----
        if time.ticks_diff(time.ticks_ms(), last_send) > 500:
            last_send = time.ticks_ms()
            out = []

            out.append(
                "<{},{},{},{},{:.1f},{:.1f},{},{}>".format(
                    state.stat["P1"],
                    state.stat["P2"],
                    state.stat["AIR"],
                    state.float_mask(),
                    state.stat["TW"],
                    state.stat["TA"],
                    state.stat["EP1"],
                    state.stat["EP2"],
                )
            )
            
            out.append(
                "FVE:{}".format(state.fve["LOAD"])
            )

            r1 = state.reg[1]
            r2 = state.reg[2]

            out.append(
                "R1:{:.2f},{:.0f},{:.2f},{},{:.2f},{:.2f},{:.2f}".format(
                    r1["BATT"], r1["PWR"], r1["ENG"], r1["CH"],
                    r1["R310E"], r1["R3304"], r1["R3111"]
                )
            )

            out.append(
                "R2:{:.2f},{:.0f},{:.2f},{},{:.2f},{:.2f},{:.2f}".format(
                    r2["BATT"], r2["PWR"], r2["ENG"], r2["CH"],
                    r2["R310E"], r2["R3304"], r2["R3111"]
                )
            )

            try:
                sys.stdout.write("\n" + "\n".join(out) + "\n\n")
            except:
                pass

    except Exception as e:
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



