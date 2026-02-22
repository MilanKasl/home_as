# app/state.py

class MonitoringView:
    def __init__(self, cov: dict):
        self._c = cov

    # pumpy / vzduch
    @property
    def pump1(self): return self._c["P1"]

    @property
    def pump2(self): return self._c["P2"]

    @property
    def air(self): return self._c["AIR"]

    # plováky
    @property
    def float1(self): return self._c["F1"]

    @property
    def float2(self): return self._c["F2"]

    @property
    def float3(self): return self._c["F3"]

    @property
    def float4(self): return self._c["F4"]

    # teploty
    @property
    def temp_water(self): return self._c["TW"]

    @property
    def temp_air(self): return self._c["TA"]

    # chyby (zatím jen placeholdery – můžeš rozšířit)
    @property
    def error_pump1(self): return self._c["EP1"]

    @property
    def error_pump2(self): return self._c["EP2"]


class RegulatorView:
    def __init__(self, reg: dict):
        self._r = reg

    @property
    def batt(self): return self._r["BATT"]

    @property
    def power(self): return self._r["PWR"]

    @property
    def energy(self): return self._r["ENG"]

    @property
    def charge_state(self): return self._r["CH"]

    @property
    def r310e(self): return self._r["R310E"]

    @property
    def r3304(self): return self._r["R3304"]

    @property
    def r3111(self): return self._r["R3111"]


class SystemState:
    def __init__(self):
        # ČOV / technologie
        self.cov = {
            "P1": 0,
            "P2": 0,
            "AIR": 0,
            "F1": 0,
            "F2": 0,
            "F3": 0,
            "F4": 0,
            "TW": 0.0,
            "TA": 0.0,
            "EP1": 0,
            "EP2": 0,
        }

        # Regulátory FVE (raw data)
        self.reg = {
            1: {
                "BATT": 0.0,
                "PWR": 0.0,
                "ENG": 0.0,
                "CH": 0,
                "R310E": 0.0,
                "R3304": 0.0,
                "R3111": 0.0,
            },
            2: {
                "BATT": 0.0,
                "PWR": 0.0,
                "ENG": 0.0,
                "CH": 0,
                "R310E": 0.0,
                "R3304": 0.0,
                "R3111": 0.0,
            },
        }


        # === ADAPTÉRY PRO GUI ===
        self.monitoring = MonitoringView(self.cov)
        self.regulators = {
            1: RegulatorView(self.reg[1]),
            2: RegulatorView(self.reg[2]),
        }

    #čidla aku
        self.tank = {
            "TOP": None,
            "BOTTOM": None,
            "IN": None,     # vnitřní teplota
            "TUV": None,    # TUV
        }

        # FVE vytěžování (globální)
        self.fve_load = 0

    # -------------------------
    # Aktualizace ČOV
    # -------------------------
    def update_from_cov(self, data: dict):
        self.cov["P1"] = data["P1"]
        self.cov["P2"] = data["P2"]
        self.cov["AIR"] = data["AIR"]

        mask = data["FLOATMASK"]
        self.cov["F1"] = (mask >> 0) & 1
        self.cov["F2"] = (mask >> 1) & 1
        self.cov["F3"] = (mask >> 2) & 1
        self.cov["F4"] = (mask >> 3) & 1

        self.cov["TW"] = data["TW"]
        self.cov["TA"] = data["TA"]
        self.cov["EP1"] = data["EP1"]
        self.cov["EP2"] = data["EP2"]

    # -------------------------
    # Aktualizace regulátorů
    # -------------------------
    def update_from_reg(self, data: dict):
        idx = data["IDX"]
        if idx not in self.reg:
            return

        self.reg[idx]["BATT"] = data["BATT"]
        self.reg[idx]["PWR"] = data["PWR"]
        self.reg[idx]["ENG"] = data["ENG"]
        self.reg[idx]["CH"] = data["CH"]

        self.reg[idx]["R310E"] = data["R310E"]
        self.reg[idx]["R3304"] = data["R3304"]
        self.reg[idx]["R3111"] = data["R3111"]

    def update_fve_load(self, data: dict):
        self.fve_load = data["LOAD"]
