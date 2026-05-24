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
    def mode(self): return self._c["MODE"]

    @property
    def temp_outdoor(self): return self._c["TO"]

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
    def energy_today(self): return self._r["ENG_DAY"]

    @property
    def energy_month(self): return self._r["ENG_MONTH"]

    @property
    def energy_year(self): return self._r["ENG_YEAR"]

    @property
    def charge_state(self): return self._r["CH"]

    @property
    def vbat_max_day(self): return self._r["VBAT_MAX_DAY"]

    @property
    def vbat_min_day(self): return self._r["VBAT_MIN_DAY"]

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
            "MODE": 0,
            "TO": None,
            "EP1": 0,
            "EP2": 0,
        }

        # Regulátory FVE (raw data)
        self.reg = {
            1: {
                "BATT": 0.0,
                "PWR": 0.0,
                "ENG_DAY": 0.0,
                "ENG_MONTH": 0.0,
                "ENG_YEAR": 0.0,
                "CH": 0,
                "VBAT_MAX_DAY": 0.0,
                "VBAT_MIN_DAY": 0.0,
                "R3111": 0.0,
            },
        }


        # === ADAPTÉRY PRO GUI ===
        self.monitoring = MonitoringView(self.cov)
        self.regulators = {
            1: RegulatorView(self.reg[1]),
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
        self.cov["MODE"] = data["MODE"]
        self.cov["TO"] = data.get("TO")
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
        self.reg[idx]["ENG_DAY"] = data["ENG_DAY"]
        self.reg[idx]["ENG_MONTH"] = data["ENG_MONTH"]
        self.reg[idx]["ENG_YEAR"] = data["ENG_YEAR"]
        self.reg[idx]["CH"] = data["CH"]

        self.reg[idx]["VBAT_MAX_DAY"] = data["VBAT_MAX_DAY"]
        self.reg[idx]["VBAT_MIN_DAY"] = data["VBAT_MIN_DAY"]
        self.reg[idx]["R3111"] = data["R3111"]

    def update_fve_load(self, data: dict):
        self.fve_load = data["LOAD"]
