import rp2
from machine import Pin


@rp2.asm_pio(
    out_init=rp2.PIO.OUT_HIGH,
    out_shiftdir=rp2.PIO.SHIFT_RIGHT,
    sideset_init=rp2.PIO.OUT_HIGH,
)
def _uart_tx():
    pull() .side(1)
    set(x, 7) .side(0) [7]
    label("bitloop")
    out(pins, 1)
    jmp(x_dec, "bitloop") [6]
    nop() .side(1) [7]


@rp2.asm_pio(
    in_shiftdir=rp2.PIO.SHIFT_RIGHT,
    autopush=True,
    push_thresh=32,
)
def _uart_rx():
    wait(0, pin, 0)
    set(x, 7) [10]
    label("bitloop")
    in_(pins, 1) [6]
    jmp(x_dec, "bitloop")


class PIOUARTTx:
    def __init__(self, sm_id, pin_num, baudrate=115200):
        self.pin = Pin(pin_num, Pin.OUT)
        self.sm = rp2.StateMachine(
            sm_id,
            _uart_tx,
            freq=baudrate * 8,
            out_base=self.pin,
            sideset_base=self.pin,
        )
        self.sm.active(1)

    def write(self, data):
        if isinstance(data, str):
            data = data.encode("utf-8")

        for byte in data:
            self.sm.put(byte)


class PIOUARTRx:
    def __init__(self, sm_id, pin_num, baudrate=115200):
        self.pin = Pin(pin_num, Pin.IN, Pin.PULL_UP)
        self.falling_edges = 0
        self.pin.irq(trigger=Pin.IRQ_FALLING, handler=self._on_falling_edge)
        self.sm = rp2.StateMachine(
            sm_id,
            _uart_rx,
            freq=baudrate * 8,
            in_base=self.pin,
            jmp_pin=self.pin,
        )
        self.sm.active(1)

    def _on_falling_edge(self, pin):
        self.falling_edges += 1

    def read(self):
        data = bytearray()
        while self.sm.rx_fifo():
            # Čtyři UART znaky jsou zabalené v jednom FIFO slovu od nejstaršího po nejnovější.
            word = self.sm.get()
            data.extend((
                word & 0xFF,
                (word >> 8) & 0xFF,
                (word >> 16) & 0xFF,
                (word >> 24) & 0xFF,
            ))
        return data

    def diagnostics(self):
        edges = self.falling_edges
        self.falling_edges = 0
        return self.pin.value(), edges
