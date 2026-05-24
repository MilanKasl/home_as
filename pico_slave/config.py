
DEV_MODE = False          # při ladění True, v provozu False
WDT_START_DELAY = 60000  # 60 s po startu napájení
WDT_TIMEOUT = 8000       # HW maximum pro RP2350

# ======== Časování ========
SEND_INTERVAL_MS = 5000

# ======== Piny relé ========
COV_RELAY_PIN = 15      # Mega → AC měnič (COV)
FVE_RELAY_PIN = 16      # Pico → DC měnič (nadvýroba)
AUX_RELAY_PIN = 17      # zpožděné  relé čerpadla od COV log.1
AUX_RELAY_ACTIVE_HIGH = True

# ======== Boiler SSR ========
SSR_PIN = 14
SSR_ACTIVE_HIGH = True
SSR_BURST_PERIOD_MS = 1000

# ======== Povolení vytěžování ========
FVE_ENABLE_BUTTON_PIN = 18
FVE_ENABLE_BUTTON_PULLUP = True
FVE_ENABLE_ACTIVE_LEVEL = 0

# ======== Povolení boiler vytěžování ========
BOILER_ENABLE_BUTTON_PIN = 12
BOILER_ENABLE_BUTTON_PULLUP = True
BOILER_ENABLE_ACTIVE_LEVEL = 0

# ======== Soumrakový vstup ========
SUN_SENSOR_PIN = 13          # GPIO vstup z relé/čidla
SUN_SENSOR_PULLUP = True     # True = interní pull-up (kontakt na GND)
SUN_SENSOR_ACTIVE_LEVEL = 0  # 0 = aktivní v log.0, 1 = aktivní v log.1

# ======== DS18B20 venkovní teplota ========
OUTDOOR_TEMP_PIN = 19
OUTDOOR_TEMP_SENSOR_ROM = None  # bytes hex bez oddělovačů, None = první nalezené čidlo
OUTDOOR_TEMP_READ_INTERVAL_MS = 60000
OUTDOOR_TEMP_SEND_INTERVAL_MS = 30000

# ======== DS18B20 boiler ========
BOILER_TEMP_PIN = 11
BOILER_TEMP_SENSOR_ROM = None
BOILER_TEMP_READ_INTERVAL_MS = 30000
BOILER_TEMP_TARGET_C = 60.0
BOILER_TEMP_HYSTERESIS_C = 3.0

# ======== RS485 ========
RS485_TX = 4
RS485_RX = 5

# ======== UART0 (Mega) ========
UART0_TX = 0
UART0_RX = 1

# ======== Logika nadvýroby ========
BATT_ON = 13.50
BATT_OFF = 13.40
BATT_PROTECT = 13.20  # okamžitá ochrana baterie při vytěžování (V)
LOAD_POWER = 200   # skutečný výkon zátěže (W)

POWER_MAX = 1000

# ======== Boiler vytěžování ========
BOILER_HEATER_POWER_W = 500
BOILER_POWER_RESERVE_W = 30
BOILER_V_MIN = 13.40
BOILER_V_LIMIT = 13.70
BOILER_V_CRITICAL = 13.30
BOILER_DUTY_STEP_UP = 0.05
BOILER_DUTY_STEP_DOWN = 0.05
BOILER_DUTY_STEP_FAST_DOWN = 0.15
BOILER_STEP_UP_INTERVAL_MS = 15000
BOILER_STEP_DOWN_INTERVAL_MS = 5000
BOILER_GOOD_CYCLES_TO_STEP_UP = 3
BOILER_BAD_CYCLES_TO_STEP_DOWN = 2
BOILER_BATTERY_AVG_ALPHA = 0.2
BOILER_BATTERY_TREND_EPSILON = 0.01
BOILER_PV_POWER_TOLERANCE_W = 100
BOILER_STEP_UP_GRACE_MS = 15000

# ======== Časované pomocné relé ========
AUX_RELAY_DELAY_MS = 60000
AUX_RELAY_PULSE_MS = 30000
