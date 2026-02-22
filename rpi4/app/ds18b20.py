import glob

BASE_DIR = "/sys/bus/w1/devices/"

class DS18B20:
    def __init__(self):
        self.sensors = self._detect()

    def _detect(self):
        paths = glob.glob(BASE_DIR + "28-*")
        return {p.split("/")[-1]: p for p in paths}

    def read_temp(self, sensor_id):
        path = self.sensors.get(sensor_id)
        if not path:
            return None

        try:
            with open(path + "/w1_slave", "r") as f:
                lines = f.readlines()

            if "YES" not in lines[0]:
                return None

            t = lines[1].split("t=")[1]
            return float(t) / 1000.0

        except:
            return None
