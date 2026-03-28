# app/link_receiver.py

import serial
import time
import os


class PicoLinkReceiver:
    def __init__(self, device="/dev/serial0", baudrate=115200, timeout=0):
        self.device = device
        self.baudrate = baudrate
        self.timeout = timeout
        self.ser = None

        self._rx_buffer = ""
        self.last_connect_ts = 0.0
        self.last_rx_ts = 0.0
        self.total_rx_bytes = 0
        self.total_rx_lines = 0
        self.last_rx_chunk = ""
        self.last_rx_line = ""
        self.last_partial_log_ts = 0.0
        self.debug_log_path = "/home/milan/logs/home_as/link_debug.log"
        self._ensure_debug_log_dir()

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
            self.last_rx_chunk = ""
            self.last_rx_line = ""
            self.last_partial_log_ts = 0.0
            self._debug_log(f"[LINK] Connected to {self.device}")
            return True
        except serial.SerialException as e:
            self._debug_log(f"[LINK] Connect failed: {e}")
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
            self.total_rx_bytes += len(data)
            self.last_rx_chunk = data[-120:]
            self._rx_buffer += data

            lines = []

            while "\n" in self._rx_buffer:
                line, self._rx_buffer = self._rx_buffer.split("\n", 1)
                line = line.strip()
                if line:
                    lines.append(line)
                    self.last_rx_line = line[-120:]

            if lines:
                self.total_rx_lines += len(lines)
            elif self._rx_buffer:
                now = time.time()
                if now - self.last_partial_log_ts >= 10:
                    preview = self._rx_buffer[-120:].replace("\n", "\\n")
                    self._debug_log(
                        f"[LINK] Partial buffer only: len={len(self._rx_buffer)} tail='{preview}'"
                    )
                    self.last_partial_log_ts = now

            return lines if lines else None

        except (OSError, serial.SerialException) as e:
            self._debug_log(f"[LINK] DISCONNECTED: {e}")
            self.disconnect()
            return None

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

    def debug_snapshot(self):
        return {
            "device": self.device,
            "connected": self.ser is not None,
            "seconds_since_rx": self.seconds_since_rx(),
            "seconds_since_connect": self.seconds_since_connect(),
            "buffer_len": len(self._rx_buffer),
            "total_rx_bytes": self.total_rx_bytes,
            "total_rx_lines": self.total_rx_lines,
            "last_rx_chunk": self.last_rx_chunk,
            "last_rx_line": self.last_rx_line,
        }

    def _ensure_debug_log_dir(self):
        os.makedirs(os.path.dirname(self.debug_log_path), exist_ok=True)

    def _debug_log(self, message):
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        line = f"{ts} {message}"
        print(line)
        try:
            with open(self.debug_log_path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception as e:
            print(f"[LINK] Failed to write debug log: {e}")
