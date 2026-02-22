# mega_protocol.py
from machine import UART, Pin

# ======= UART0 pro Mega =======
uart_out = UART(0, baudrate=9600, tx=Pin(0), rx=Pin(1))

_buffer = ""
_MAX_BUFFER = 256   # ochrana proti zahlcení

# ======= Polling Mega (non-blocking) =======
def poll_mega(on_log=None):
    global _buffer

    while uart_out.any():
        chunk = uart_out.read(64)
        if not chunk:
            break

        try:
            text = chunk.decode("utf-8", "ignore")
        except:
            continue

        _buffer += text

        # ochrana bufferu
        if len(_buffer) > _MAX_BUFFER:
            _buffer = ""

        while True:
            start = _buffer.find("<")
            end = _buffer.find(">", start + 1)

            if start >= 0 and end > start:
                frame = _buffer[start + 1:end].strip()
                _buffer = _buffer[end + 1:]

                if frame.startswith("LOG:"):
                    val = frame.split(":", 1)[1]
                    if on_log:
                        on_log(val)
            else:
                break

def send_frame(frame):
    uart_out.write(frame + "\n")
