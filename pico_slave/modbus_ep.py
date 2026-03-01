
# modbus_ep.py
from machine import UART, Pin  # type: ignore
import time

# ======= UART1 pro RS485 =======
_UART_ID = 1
_UART_BAUD = 115200
_UART_TX = 4
_UART_RX = 5
_FAIL_REINIT_THRESHOLD = 3
_INTER_BYTE_TIMEOUT_MS = 30

uart_rs = UART(_UART_ID, baudrate=_UART_BAUD, tx=Pin(_UART_TX), rx=Pin(_UART_RX))
_consecutive_failures = 0

# ======= CRC16 (Modbus RTU) =======
def crc16(data):
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc.to_bytes(2, 'little')


def _clear_rx():
    while uart_rs.any():
        uart_rs.read()


def _reinit_uart():
    global uart_rs
    try:
        uart_rs.deinit()
    except:
        pass
    time.sleep_ms(2)
    uart_rs = UART(_UART_ID, baudrate=_UART_BAUD, tx=Pin(_UART_TX), rx=Pin(_UART_RX))


def _extract_valid_response(resp, slave, count):
    expected_len = 5 + (count * 2)  # adr + fn + bytes + data + crc16
    if len(resp) < expected_len:
        return None

    for i in range(0, len(resp) - expected_len + 1):
        if resp[i] != slave:
            continue
        if resp[i + 1] != 0x04:
            continue
        if resp[i + 2] != count * 2:
            continue

        frame = bytes(resp[i:i + expected_len])
        if crc16(frame[:-2]) == frame[-2:]:
            return frame
    return None

# ======= Non-blocking Modbus read =======
def modbus_read_input(slave, reg, count, timeout_ms=200):
    global _consecutive_failures

    msg = bytearray([
        slave,
        0x04,
        (reg >> 8) & 0xFF,
        reg & 0xFF,
        (count >> 8) & 0xFF,
        count & 0xFF
    ])
    msg += crc16(msg)

    # Po výpadku linky bývají v RX zbytky dat/šumu.
    _clear_rx()
    uart_rs.write(msg)

    start = time.ticks_ms()
    resp = bytearray()
    last_byte_time = None

    while time.ticks_diff(time.ticks_ms(), start) < timeout_ms:
        if uart_rs.any():
            part = uart_rs.read()
            if part:
                resp += part
                last_byte_time = time.ticks_ms()
                valid = _extract_valid_response(resp, slave, count)
                if valid:
                    _consecutive_failures = 0
                    return valid
        elif last_byte_time is not None and time.ticks_diff(time.ticks_ms(), last_byte_time) > _INTER_BYTE_TIMEOUT_MS:
            valid = _extract_valid_response(resp, slave, count)
            if valid:
                _consecutive_failures = 0
                return valid
            break
        time.sleep_ms(1)

    _consecutive_failures += 1
    if _consecutive_failures >= _FAIL_REINIT_THRESHOLD:
        _consecutive_failures = 0
        _reinit_uart()
    return None

# ======= Parsování hodnot =======
def parse_value(resp, factor=0.01):
    if not resp or len(resp) < 5:
        return None
    try:
        raw = (resp[3] << 8) | resp[4]
        return raw * factor
    except:
        return None
    
def parse_u32(resp):
    if not resp or len(resp) < 9:
        return None

    # základní validace
    if resp[1] != 0x04:
        return None

    byte_count = resp[2]
    if byte_count != 4:
        return None

    data = resp[3:3+byte_count]

    high = (data[0] << 8) | data[1]
    low  = (data[2] << 8) | data[3]

    return (high << 16) | low

def parse_u32_lh(resp):
    if not resp or len(resp) < 9:
        return None

    if resp[1] != 0x04:
        return None

    byte_count = resp[2]
    if byte_count != 4:
        return None

    data = resp[3:3+byte_count]

    low  = (data[0] << 8) | data[1]
    high = (data[2] << 8) | data[3]

    return (high << 16) | low


def parse_charge_state(resp):
    if not resp or len(resp) < 5:
        return None
    try:
        raw = (resp[3] << 8) | resp[4]
        return (raw >> 2) & 0b11
    except:
        return None

# ======= Funkce pro načtení dat z jednoho regulátoru (pouze volána při odesílání) =======
def read_regulator(slave):
    batt_v = parse_value(
        modbus_read_input(slave, 0x331A, 2), factor=0.01
    )  # V

    pv_l = parse_value(
        modbus_read_input(slave, 0x3102, 1), factor=1.0
    )

    pv_h = parse_value(
        modbus_read_input(slave, 0x3103, 1), factor=1.0
    )

    if pv_l is None or pv_h is None:
        pv_power = None
    else:
        pv_power = int(pv_h) << 16 | int(pv_l)
        pv_power_raw = (int(pv_h) << 16) | int(pv_l)
        pv_power = pv_power_raw * 0.01   # W



    eng_today_raw = parse_u32_lh(
        modbus_read_input(slave, 0x330C, 2)
    )
    eng_month_raw = parse_u32_lh(
        modbus_read_input(slave, 0x330E, 2)
    )
    eng_year_raw = parse_u32_lh(
        modbus_read_input(slave, 0x3310, 2)
    )

    if eng_today_raw is None:
        eng_today = None
    else:
        eng_today = eng_today_raw * 10.0  # 0.01 kWh -> W

    if eng_month_raw is None:
        eng_month = None
    else:
        eng_month = eng_month_raw * 10.0  # 0.01 kWh -> W

    if eng_year_raw is None:
        eng_year = None
    else:
        eng_year = eng_year_raw * 10.0  # 0.01 kWh -> W

    chg = parse_charge_state(
        modbus_read_input(slave, 0x3201, 1)
    )

    val_3302 = parse_value(
        modbus_read_input(slave, 0x3302, 1), factor=0.01
    )

    val_3303 = parse_value(
        modbus_read_input(slave, 0x3303, 1), factor=0.01
    )

    val_3111 = parse_value(
        modbus_read_input(slave, 0x3111, 1), factor=0.01
    )

    return (
        batt_v,
        pv_power,
        eng_today,
        eng_month,
        eng_year,
        chg,
        val_3302,
        val_3303,
        val_3111,
    )
