# main.py
import tkinter as tk
from app.gui import DashboardGUI
from app.state import SystemState
from app.usb_receiver import PicoUSBReceiver

def main():
    state = SystemState()

    usb = PicoUSBReceiver(device="/dev/pico-dashboard")
    usb.connect()

    root = tk.Tk()
    app = DashboardGUI(root, state, usb)

    root.mainloop()


if __name__ == "__main__":
    main()

