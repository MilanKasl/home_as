# main.py
import tkinter as tk
from app.gui import DashboardGUI
from app.state import SystemState
from app.link_receiver import PicoLinkReceiver
from app.config import PICO_LINK_DEVICE, PICO_LINK_BAUDRATE

def main():
    state = SystemState()

    link = PicoLinkReceiver(device=PICO_LINK_DEVICE, baudrate=PICO_LINK_BAUDRATE)
    link.connect()

    root = tk.Tk()
    app = DashboardGUI(root, state, link)

    root.mainloop()


if __name__ == "__main__":
    main()
