
DEV_MODE = True          # při ladění True, v provozu False
WDT_START_DELAY = 60000  # 60 s po startu napájení
WDT_TIMEOUT = 8000       # HW maximum pro RP2350

# ======== Časování ========
SEND_INTERVAL_MS = 5000

# ======== Piny relé ========
COV_RELAY_PIN = 15      # Mega → AC měnič (COV)
FVE_RELAY_PIN = 16      # Pico → DC měnič (nadvýroba)

# ======== PWM ========
PWM_PIN = 14

# ======== RS485 ========
RS485_TX = 4
RS485_RX = 5

# ======== UART0 (Mega) ========
UART0_TX = 0
UART0_RX = 1

# ======== Logika nadvýroby ========
BATT_ON = 13.7
BATT_OFF = 13.4
LOAD_POWER = 200   # skutečný výkon zátěže (W)

POWER_MAX = 1000


