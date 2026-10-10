# parser.py

def parse_cov(frame, state):
    # formát:
    # <P1,P2,AIR,FLOATMASK,TW,MODE,EP1,EP2>
    parts = frame.split(",")
    if len(parts) != 8:
        return False

    try:
        s = state.stat

        s["P1"] = int(parts[0])
        s["P2"] = int(parts[1])
        s["AIR"] = int(parts[2])

        mask = int(parts[3])
        s["F1"] = (mask >> 0) & 1
        s["F2"] = (mask >> 1) & 1
        s["F3"] = (mask >> 2) & 1
        s["F4"] = (mask >> 3) & 1

        s["TW"] = float(parts[4])
        s["MODE"] = int(float(parts[5]))
        s["EP1"] = int(parts[6])
        s["EP2"] = int(parts[7])
        return True
    except (ValueError, TypeError, IndexError):
        return False


def parse_reg(frame, state):
    # formát:
    # R1:BATT,PWR,ENG_DAY,ENG_MONTH,ENG_YEAR,CH,3302,3303,3111
    if not frame.startswith("R"):
        return

    try:
        rid, data = frame.split(":")
        idx = int(rid[1])
        if idx != 1:
            return
        vals = data.split(",")

        if len(vals) != 9:
            return

        r = state.reg[idx]

        r["BATT"]  = float(vals[0])
        r["PWR"]   = float(vals[1])
        r["ENG_DAY"] = float(vals[2])
        r["ENG_MONTH"] = float(vals[3])
        r["ENG_YEAR"] = float(vals[4])
        r["CH"] = int(vals[5])
        r["VBAT_MAX_DAY"] = float(vals[6])
        r["VBAT_MIN_DAY"] = float(vals[7])
        r["R3111"] = float(vals[8])

    except:
        pass

def parse_outdoor(frame, state):
    if not frame.startswith("OUT:"):
        return False

    try:
        state.stat["TO"] = float(frame.split(":", 1)[1])
    except Exception:
        pass

    return True


def parse_heating(frame, state):
    # formát: HEAT:MODE,ACTIVE,REASON,END_HOUR,TUV_TEMP
    if not frame.startswith("HEAT:"):
        return False

    try:
        parts = frame[5:].split(",")
        if len(parts) not in (3, 4, 5):
            return False
        mode, active, reason = parts[:3]
        if mode not in ("A", "T", "K", "0"):
            return False
        if active not in ("T", "K", "0"):
            return False
        end_hour = int(parts[3]) if len(parts) >= 4 else state.heating["END_HOUR"]
        if not 0 <= end_hour <= 24:
            return False
        tuv_temp = float(parts[4]) if len(parts) == 5 and parts[4] else None
        if tuv_temp is not None and (not -55 <= tuv_temp <= 125 or tuv_temp == 85):
            tuv_temp = None
        state.heating["MODE"] = mode
        state.heating["ACTIVE"] = active
        state.heating["REASON"] = reason[:20]
        state.heating["END_HOUR"] = end_hour
        state.heating["TUV_TEMP"] = tuv_temp
        return True
    except (ValueError, TypeError):
        return False


def parse_pump(frame, state):
    if not frame.startswith("PUMP:"):
        return False
    parts = frame[5:].split(",")
    if len(parts) != 2 or parts[0] not in ("A", "M") or parts[1] not in ("0", "1"):
        return False
    state.pump = {"MODE": parts[0], "ACTIVE": int(parts[1])}
    return True
