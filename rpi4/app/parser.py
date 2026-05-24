# app/parser.py

def parse_cov_frame(line: str):
    """
    Očekává: <P1,P2,AIR,FLOATMASK,TW,MODE,EP1,EP2,TO>
    Vrací dict nebo None
    """
    if not (line.startswith("<") and line.endswith(">")):
        return None

    try:
        body = line[1:-1]
        parts = body.split(",")

        if len(parts) not in (8, 9):
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

def parse_fve_load_frame(line: str):
    """
    Očekává: FVE:0 nebo FVE:1
    """
    if not line.startswith("FVE:"):
        return None

    try:
        _, raw_value = line.split(":", 1)
        value = int(raw_value)
        if value not in (0, 1):
            return None
        return {"LOAD": value}
    except (TypeError, ValueError):
        return None
