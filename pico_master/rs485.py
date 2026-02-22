# rs485.py

MAX_BUF = 256

def read_uart(uart, buffer):
    while uart.any():
        try:
            c = uart.read(1).decode()
        except:
            continue

        buffer += c

        # OCHRANA PROTI ROZJETÍ BUFFERU
        if len(buffer) > MAX_BUF:
            buffer = ""

        if "<" in buffer and ">" in buffer:
            start = buffer.index("<")
            end = buffer.index(">", start)
            frame = buffer[start + 1:end]
            buffer = buffer[end + 1:]
            return frame.strip(), buffer

    return None, buffer
