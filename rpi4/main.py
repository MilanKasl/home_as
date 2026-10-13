# main.py
import tkinter as tk
from app.gui import DashboardGUI
from app.state import SystemState
from app.communication import create_link

def main():
    state = SystemState()

    link = create_link()
    root = tk.Tk()
    try:
        link.connect()
        app = DashboardGUI(root, state, link)
        root.mainloop()
    finally:
        link.disconnect()


if __name__ == "__main__":
    main()
