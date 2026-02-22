# app/parser.py

def parse_cov_frame(line: str):
    """
    Očekává: <P1,P2,AIR,FLOATMASK,TW,TA,EP1,EP2>
    Vrací dict nebo None
    """
    if not (line.startswith("<") and line.endswith(">")):
        return None

    try:
        body = line[1:-1]
        parts = body.split(",")

        if len(parts) != 8:
            return None

        return {
            "P1": int(parts[0]),
            "P2": int(parts[1]),
            "AIR": int(parts[2]),
            "FLOATMASK": int(parts[3]),
            "TW": float(parts[4]),
            "TA": float(parts[5]),
            "EP1": int(parts[6]),
            "EP2": int(parts[7]),
        }

    except Exception:
        return None


def parse_reg_frame(line: str):
    """
    Očekává: R1:BATT,PWR,ENG,CH,310E,3304,3111
    """
    if not line.startswith("R"):
        return None

    try:
        rid, data = line.split(":", 1)
        idx = int(rid[1])

        parts = data.split(",")
        if len(parts) != 7:
            return None

        return {
            "IDX": idx,
            "BATT": float(parts[0]),
            "PWR": float(parts[1]),
            "ENG": float(parts[2]) * 1000,
            "CH": int(parts[3]),
            "R310E": float(parts[4]),
            "R3304": float(parts[5]) * 1000,
            "R3111": float(parts[6]),
        }

    except Exception:
        return None

def parse_fve_load_frame(line: str):
    """
    Očekává: FVE:0 nebo FVE:1
    """
    if not line.startswith("FVE:"):
        return None

    try:
        value = int(line.split(":")[1])
        return {"LOAD": value}
    except Exception:
        return None