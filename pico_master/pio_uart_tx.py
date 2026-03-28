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
