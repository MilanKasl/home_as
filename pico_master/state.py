# state.py

class SystemState:
    def __init__(self):
        self.stat = {
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

        # ===== FVE =====
        self.fve = {
            "LOAD": 0
        }
        
        self.reg = {
            1: {
                "BATT": 0.0,
                "PWR": 0,
                "ENG": 0.0,
                "CH": 0,
                "R310E": 0.0,
                "R3304": 0.0,
                "R3111": 0.0,
            },
            2: {
                "BATT": 0.0,
                "PWR": 0,
                "ENG": 0.0,
                "CH": 0,
                "R310E": 0.0,
                "R3304": 0.0,
                "R3111": 0.0,
            },
        }


    def float_mask(self):
        return (
            (self.stat["F1"] << 0)
            | (self.stat["F2"] << 1)
            | (self.stat["F3"] << 2)
            | (self.stat["F4"] << 3)
        )

