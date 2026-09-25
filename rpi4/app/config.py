# app/config.py

SCREEN_WIDTH = 1024
SCREEN_HEIGHT = 600

BG_COLOR = "#000000"
FG_COLOR = "#FFFFFF"

PICO_LINK_DEVICE = "/dev/serial0"
PICO_LINK_BAUDRATE = 115200

TANK_TOP_SENSOR    = "28-062542ccdc09"
TANK_BOTTOM_SENSOR = "28-0625439e5b3a"
IN_SIDE_TEMP = "28-062542812ced"

# Odhad energie FVE dodané do akumulační nádrže.
TANK_VOLUME_LITERS = 470
TANK_HEAT_CAPACITY_KWH_PER_K = 0.5466 * TANK_VOLUME_LITERS / 470
TANK_UA_W_PER_K = 9.0
TANK_TOP_WEIGHT = 0.5  # dolní čidlo má váhu 1 - TANK_TOP_WEIGHT
FVE_ENERGY_STATE_PATH = "/home/milan/logs/home_as/fve_energy.json"
FVE_ENERGY_SAVE_INTERVAL_S = 300
FVE_MAX_SAMPLE_GAP_S = 3600  # krátký výpadek čidel nesmí zahodit teplotní nárůst
FVE_MAX_TEMPERATURE_STEP_C = 3.0
FVE_MAX_ESTIMATED_POWER_W = 10000.0
FVE_POWER_WINDOW_S = 600
FVE_CHARGE_END_HOUR_FALLBACK = 17  # pro starší firmware bez hodiny v H rámci
FVE_HEATING_STATUS_GAP_S = 90  # tolerovaná mezera zpráv při potvrzování cyklu
