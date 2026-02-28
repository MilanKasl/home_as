
# modbus_ep.py
from machine import UART, Pin  # type: ignore
import time

# ======= UART1 pro RS485 =======
uart_rs = UART(1, baudrate=115200, tx=Pin(4), rx=Pin(5))

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

# ======= Non-blocking Modbus read =======
def modbus_read_input(slave, reg, count, timeout_ms=200):
    msg = bytearray([
        slave,
        0x04,
        (reg >> 8) & 0xFF,
        reg & 0xFF,
        (count >> 8) & 0xFF,
        count & 0xFF
    ])
    msg += crc16(msg)

    uart_rs.write(msg)

    start = time.ticks_ms()
    resp = bytearray()

    while time.ticks_diff(time.ticks_ms(), start) < timeout_ms:
        if uart_rs.any():
            part = uart_rs.read()
            if part:
                resp += part
                t0 = time.ticks_ms()
                while time.ticks_diff(time.ticks_ms(), t0) < 30:
                    if uart_rs.any():
                        more = uart_rs.read()
                        if more:
                            resp += more
                    else:
                        time.sleep_ms(1)
                return bytes(resp)
        time.sleep_ms(1)

    return bytes(resp) if resp else None

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



    extra = parse_value(
        modbus_read_input(slave, 0x330C, 2), factor=0.01
    )

    chg = parse_charge_state(
        modbus_read_input(slave, 0x3201, 1)
    )

    # === NOVÉ HODNOTY ===
    val_310E = parse_value(
        modbus_read_input(slave, 0x310E, 1), factor=0.01
    )

    val_3304 = parse_value(
        modbus_read_input(slave, 0x3304, 1), factor=0.01
    )

    val_3111 = parse_value(
        modbus_read_input(slave, 0x3111, 1), factor=0.01
    )

    return (
        batt_v,
        pv_power,
        extra,
        chg,
        val_310E,
        val_3304,
        val_3111,
    )
