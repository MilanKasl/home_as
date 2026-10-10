# mega_protocol.py
from machine import UART, Pin  # type: ignore

# ======= UART0 pro Mega =======
uart_out = UART(0, baudrate=9600, tx=Pin(0), rx=Pin(1))

_buffer = ""
_MAX_BUFFER = 128


def poll_commands(on_temperature=None, on_heating_mode=None, on_pump_mode=None,
                  on_pump_temperature=None):
    """Přečte teploty a povely ohřevu i čerpadla od Pico Masteru."""
    global _buffer

    while uart_out.any():
        chunk = uart_out.read(64)
        if not chunk:
            break

        _buffer += chunk.decode("utf-8", "ignore")
        if len(_buffer) > _MAX_BUFFER:
            _buffer = ""

        while True:
            start = _buffer.find("<")
            end = _buffer.find(">", start + 1)
            if start < 0 or end <= start:
                break

            frame = _buffer[start + 1:end].strip()
            _buffer = _buffer[end + 1:]
            if frame.startswith("TEMP:"):
                try:
                    # Starší dvojice TUV,AKU je přijata, TUV se už nebere z linky.
                    parts = frame[5:].split(",")
                    if len(parts) not in (1, 2):
                        continue
                    aku_c = int(parts[-1])
                    if -55 <= aku_c <= 125:
                        if on_temperature:
                            on_temperature(aku_c)
                except (ValueError, TypeError):
                    pass
            elif frame.startswith("PTEMP:"):
                try:
                    value = frame[6:]
                    average = float(value) if value else None
                    if average is None or -55 <= average <= 125:
                        if on_pump_temperature:
                            on_pump_temperature(average)
                except (ValueError, TypeError):
                    pass
            elif frame.startswith("PUMP:"):
                mode = frame[5:].strip().upper()
                if mode in ("A", "M") and on_pump_mode:
                    on_pump_mode(mode)
            elif frame.startswith("HEAT:"):
                mode = frame[5:].strip().upper()
                if mode in ("A", "T", "K", "0") and on_heating_mode:
                    on_heating_mode(mode)


def poll_temperature(on_temperature=None):
    """Zpětně kompatibilní obsluha pouze teplotních rámců."""
    poll_commands(on_temperature=on_temperature)

def send_frame(frame):
    uart_out.write(frame + "\n")
