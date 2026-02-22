# parser.py

def parse_cov(frame, state):
    # formát:
    # <P1,P2,AIR,FLOATMASK,TW,TA,EP1,EP2>
    parts = frame.split(",")
    if len(parts) != 8:
        return

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
    s["TA"] = float(parts[5])
    s["EP1"] = int(parts[6])
    s["EP2"] = int(parts[7])


def parse_reg(frame, state):
    # formát:
    # R1:BATT,PWR,ENG,CH,310E,3304,3111
    if not frame.startswith("R"):
        return

    try:
        rid, data = frame.split(":")
        idx = int(rid[1])
        vals = data.split(",")

        if len(vals) != 7:
            return

        r = state.reg[idx]

        r["BATT"]  = float(vals[0])
        r["PWR"]   = float(vals[1])
        r["ENG"]   = float(vals[2])
        r["CH"]    = int(vals[3])
        r["R310E"] = float(vals[4])
        r["R3304"] = float(vals[5])
        r["R3111"] = float(vals[6])

    except:
        pass

def parse_fve(frame, state):
    # formát: FVE:1 nebo FVE:0
    if not frame.startswith("FVE:"):
        return False

    try:
        val = int(frame.split(":")[1])
        state.fve["LOAD"] = val
    except:
        pass

    return True