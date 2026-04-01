
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

# ======== PWM ========
PWM_PIN = 14

# ======== Povolení vytěžování ========
FVE_ENABLE_BUTTON_PIN = 18
FVE_ENABLE_BUTTON_PULLUP = True
FVE_ENABLE_ACTIVE_LEVEL = 0

# ======== Soumrakový vstup ========
SUN_SENSOR_PIN = 13          # GPIO vstup z relé/čidla
SUN_SENSOR_PULLUP = True     # True = interní pull-up (kontakt na GND)
SUN_SENSOR_ACTIVE_LEVEL = 0  # 0 = aktivní v log.0, 1 = aktivní v log.1

# ======== DS18B20 venkovní teplota ========
OUTDOOR_TEMP_PIN = 19
OUTDOOR_TEMP_SENSOR_ROM = None  # bytes hex bez oddělovačů, None = první nalezené čidlo
OUTDOOR_TEMP_READ_INTERVAL_MS = 60000
OUTDOOR_TEMP_SEND_INTERVAL_MS = 30000

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

# ======== Časované pomocné relé ========
AUX_RELAY_DELAY_MS = 60000
AUX_RELAY_PULSE_MS = 30000
