# app/usb_receiver.py

import serial
import time


class PicoUSBReceiver:
    def __init__(self, device="/dev/pico-dashboard", baudrate=115200, timeout=0):
        self.device = device
        self.baudrate = baudrate
        self.timeout = timeout
        self.ser = None

        self._rx_buffer = ""
        self.last_connect_ts = 0.0
        self.last_rx_ts = 0.0

    # ------------------------------
    # Připojení k Pico
    # ------------------------------
    def connect(self):
        try:
            if self.ser:
                self.disconnect()

            self.ser = serial.Serial(
                self.device,
                self.baudrate,
                timeout=self.timeout,
            )
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
            self._rx_buffer = ""
            now = time.time()
            self.last_connect_ts = now
            self.last_rx_ts = now
            print(f"[USB] Connected to {self.device}")
            return True
        except serial.SerialException as e:
            print(f"[USB] Connect failed: {e}")
            return False

    # ------------------------------
    # Čtení BLOKU (RAW STREAM)
    # ------------------------------
    def read_block(self):
        if not self.ser:
            return None

        try:
            n = self.ser.in_waiting
            if n == 0:
                return None

            data = self.ser.read(n).decode(errors="ignore")
            self.last_rx_ts = time.time()
            self._rx_buffer += data

            lines = []

            while "\n" in self._rx_buffer:
                line, self._rx_buffer = self._rx_buffer.split("\n", 1)
                line = line.strip()
                if line:
                    lines.append(line)

            return lines if lines else None

        except (OSError, serial.SerialException) as e:
            print("[USB] DISCONNECTED:", e)
            self.disconnect()
            return None

        #připojení po opětovném spojení USB
    def disconnect(self):
        if self.ser:
            try:
                self.ser.close()
            except Exception:
                pass
            self.ser = None
        self._rx_buffer = ""

    def seconds_since_rx(self):
        if self.last_rx_ts <= 0:
            return None
        return time.time() - self.last_rx_ts

    def seconds_since_connect(self):
        if self.last_connect_ts <= 0:
            return None
        return time.time() - self.last_connect_ts
