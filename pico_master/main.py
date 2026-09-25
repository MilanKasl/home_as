# main.py – Pico Master

from machine import UART, Pin
import time

from state import SystemState
from rs485 import read_uart
from parser import parse_cov, parse_reg, parse_outdoor, parse_heating
from machine import WDT
from pio_uart_tx import PIOUARTRx, PIOUARTTx

# ================= Watchdog řízení =================
DEV_MODE = False         # při ladění True, v provozu False
WDT_START_DELAY = 60000  # 60 s po startu
WDT_TIMEOUT = 8000       # max pro RP2350
HOST_UART_BAUDRATE = 115200
HOST_UART_TX_PIN = 8
HOST_UART_RX_PIN = 9

wdt = None
start_time = time.ticks_ms()


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
last_cov_rx = None
last_heating_rx = None
host_uart = PIOUARTTx(sm_id=0, pin_num=HOST_UART_TX_PIN, baudrate=HOST_UART_BAUDRATE)
host_uart_rx = PIOUARTRx(sm_id=1, pin_num=HOST_UART_RX_PIN, baudrate=HOST_UART_BAUDRATE)
host_rx_buffer = ""
last_host_rx_debug = time.ticks_ms()
HOST_RX_DEBUG_INTERVAL_MS = 10000


def write_host_lines(lines):
    payload = "\n" + "\n".join(lines) + "\n\n"
    host_uart.write(payload)


def forward_host_commands():
    """Předá platné teploty a povely ohřevu z RPi4 do Pico Slave."""
    global host_rx_buffer, last_host_rx_debug

    chunk = host_uart_rx.read()
    if not chunk:
        now = time.ticks_ms()
        if time.ticks_diff(now, last_host_rx_debug) >= HOST_RX_DEBUG_INTERVAL_MS:
            pin_level, falling_edges = host_uart_rx.diagnostics()
            print(
                "HOST RX: za posledních 10 s nepřišla žádná data z RPi4; "
                "GPIO9={}, sestupné hrany={}".format(pin_level, falling_edges)
            )
            last_host_rx_debug = now
        return

    received = chunk.decode("utf-8", "ignore")
    print("HOST RX z RPi4:", repr(received))
    last_host_rx_debug = time.ticks_ms()
    host_rx_buffer += received
    if len(host_rx_buffer) > 128:
        print("HOST RX: buffer je příliš dlouhý, zahazuji data")
        host_rx_buffer = ""
        return

    while True:
        start = host_rx_buffer.find("<")
        end = host_rx_buffer.find(">", start + 1)
        if start < 0 or end <= start:
            return

        frame = host_rx_buffer[start + 1:end].strip()
        host_rx_buffer = host_rx_buffer[end + 1:]
        if frame.startswith("TEMP:"):
            try:
                parts = frame[5:].split(",")
                if len(parts) not in (1, 2):
                    raise ValueError("invalid temperature frame")
                aku_c = int(parts[-1])
                if -55 <= aku_c <= 125:
                    uart_fve.write("<TEMP:{}>".format(aku_c))
                    print("TEMP -> Pico Slave: AKU={} C".format(aku_c))
                else:
                    print("HOST RX: teploty mimo povolený rozsah:", frame)
            except (ValueError, TypeError):
                print("HOST RX: neplatný teplotní rámec:", frame)
        elif frame.startswith("HEAT:"):
            mode = frame[5:].strip().upper()
            if mode in ("A", "T", "K", "0"):
                uart_fve.write("<HEAT:{}>".format(mode))
                print("HEAT -> Pico Slave: režim={}".format(mode))
            else:
                print("HOST RX: neplatný povel ohřevu:", frame)


# ==============================
# HLAVNÍ SMYČKA
# ==============================
while True:
    try:
        forward_host_commands()

        # ----- ČOV -----
        frame, buf_cov = read_uart(uart_cov, buf_cov)
        if frame:
            if parse_cov(frame, state):
                last_cov_rx = time.ticks_ms()

        # ----- FVE -----
        frame, buf_fve = read_uart(uart_fve, buf_fve)
        if frame:
            if parse_heating(frame, state):
                last_heating_rx = time.ticks_ms()
            elif not parse_outdoor(frame, state):
                parse_reg(frame, state)

        # ----- USB OUTPUT -----
        if time.ticks_diff(time.ticks_ms(), last_send) > 500:
            last_send = time.ticks_ms()
            out = []

            out.append(
                "<{},{},{},{},{:.1f},{},{},{},{},{}>".format(
                    state.stat["P1"],
                    state.stat["P2"],
                    state.stat["AIR"],
                    state.float_mask(),
                    state.stat["TW"],
                    state.stat["MODE"],
                    state.stat["EP1"],
                    state.stat["EP2"],
                    "{:.1f}".format(state.stat["TO"]) if state.stat["TO"] is not None else "",
                    time.ticks_diff(time.ticks_ms(), last_cov_rx) // 1000
                    if last_cov_rx is not None else -1,
                )
            )
            
            r1 = state.reg[1]

            out.append(
                "R1:{:.2f},{:.0f},{:.0f},{:.0f},{:.0f},{},{:.2f},{:.2f},{:.2f}".format(
                    r1["BATT"], r1["PWR"], r1["ENG_DAY"], r1["ENG_MONTH"], r1["ENG_YEAR"], r1["CH"],
                    r1["VBAT_MAX_DAY"], r1["VBAT_MIN_DAY"], r1["R3111"]
                )
            )

            heating_fresh = (
                last_heating_rx is not None
                and time.ticks_diff(time.ticks_ms(), last_heating_rx) <= 3000
            )
            out.append("H:{},{},{},{},{}".format(
                state.heating["MODE"],
                state.heating["ACTIVE"] if heating_fresh else "0",
                state.heating["REASON"] if heating_fresh else "NO_DATA",
                state.heating["END_HOUR"],
                "{:.2f}".format(state.heating["TUV_TEMP"])
                if heating_fresh and state.heating["TUV_TEMP"] is not None else "",
            ))

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
