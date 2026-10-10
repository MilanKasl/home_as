"""Teplota pro automatické řízení čerpadla AKU."""
import math


def pump_temperature_frame(top, bottom):
    """Průměr obou čidel, nebo prázdná hodnota při chybě kteréhokoli čidla."""
    if not all(isinstance(value, (int, float)) and not isinstance(value, bool)
               and math.isfinite(value) and -55 <= value <= 125 and value != 85
               for value in (top, bottom)):
        return "<PTEMP:>"
    return "<PTEMP:{:.3f}>".format((top + bottom) / 2)
