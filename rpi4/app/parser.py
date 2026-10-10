# app/parser.py

def parse_cov_frame(line: str):
    """
    Očekává: <P1,P2,AIR,FLOATMASK,TW,MODE,EP1,EP2[,TO[,COV_AGE]]>
    Vrací dict nebo None
    """
    if not (line.startswith("<") and line.endswith(">")):
        return None

    try:
        body = line[1:-1]
        parts = body.split(",")

        if len(parts) not in (8, 9, 10):
            return None

        data = {
            "P1": int(parts[0]),
            "P2": int(parts[1]),
            "AIR": int(parts[2]),
            "FLOATMASK": int(parts[3]),
            "TW": float(parts[4]),
            "MODE": int(float(parts[5])),
            "EP1": int(parts[6]),
            "EP2": int(parts[7]),
        }
        data["TO"] = float(parts[8]) if len(parts) == 9 and parts[8] != "" else None
        if len(parts) == 10:
            data["TO"] = float(parts[8]) if parts[8] != "" else None
            data["COV_AGE"] = int(parts[9])
        else:
            data["COV_AGE"] = None
        return data

    except (TypeError, ValueError, IndexError):
        return None


def parse_reg_frame(line: str):
    """
    Očekává: R1:BATT,PWR,ENG_DAY,ENG_MONTH,ENG_YEAR,CH,3302,3303,3111
    """
    if not line.startswith("R"):
        return None

    try:
        rid, data = line.split(":", 1)
        idx = int(rid[1])

        if idx != 1:
            return None

        parts = data.split(",")
        if len(parts) != 9:
            return None

        return {
            "IDX": idx,
            "BATT": float(parts[0]),
            "PWR": float(parts[1]),
            "ENG_DAY": float(parts[2]),
            "ENG_MONTH": float(parts[3]),
            "ENG_YEAR": float(parts[4]),
            "CH": int(parts[5]),
            "VBAT_MAX_DAY": float(parts[6]),
            "VBAT_MIN_DAY": float(parts[7]),
            "R3111": float(parts[8]),
        }

    except (TypeError, ValueError, IndexError):
        return None


def parse_heating_frame(line: str):
    """Očekává: H:MODE,ACTIVE,REASON[,END_HOUR[,TUV_TEMP]]."""
    if not line.startswith("H:"):
        return None

    try:
        parts = line[2:].split(",")
        if len(parts) not in (3, 4, 5):
            return None
        mode, active, reason = parts[:3]
        if mode not in ("A", "T", "K", "0"):
            return None
        if active not in ("T", "K", "0"):
            return None
        end_hour = int(parts[3]) if len(parts) >= 4 else None
        if end_hour is not None and not 0 <= end_hour <= 24:
            return None
        tuv_temp = float(parts[4]) if len(parts) == 5 and parts[4] else None
        if tuv_temp is not None and (not -55 <= tuv_temp <= 125 or tuv_temp == 85):
            tuv_temp = None
        return {
            "MODE": mode,
            "ACTIVE": active,
            "REASON": reason[:20],
            "END_HOUR": end_hour,
            "TUV_TEMP": tuv_temp,
            "HAS_TUV_TEMP": len(parts) == 5,
        }
    except (TypeError, ValueError):
        return None


def parse_pump_frame(line: str):
    if line == "P:NO_DATA":
        return {"MODE": None, "ACTIVE": None}
    if not line.startswith("P:"):
        return None
    parts = line[2:].split(",")
    if len(parts) != 2 or parts[0] not in ("A", "M") or parts[1] not in ("0", "1"):
        return None
    return {"MODE": parts[0], "ACTIVE": int(parts[1])}
