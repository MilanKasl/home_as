
DEV_MODE = False          # při ladění True, v provozu False
WDT_START_DELAY = 60000  # 60 s po startu napájení
WDT_TIMEOUT = 8000       # HW maximum pro RP2350

# ======== Časování ========
SEND_INTERVAL_MS = 5000

# ======== Řízení ohřevu ========
TUV_RELAY_PIN = 15
AKU_RELAY_PIN = 16
AKU_PUMP_RELAY_PIN = 17
HEATING_RELAY_ACTIVE_HIGH = True
AKU_PUMP_RELAY_ACTIVE_HIGH = True

HEATING_START_HOUR = 7
HEATING_END_HOUR = 17
RELAY_SWITCH_DELAY_MS = 5000
TEMPERATURE_TIMEOUT_MS = 5 * 60 * 1000
MANUAL_COMMAND_TIMEOUT_MS = 10000
HEATING_STATUS_INTERVAL_MS = 1000

TUV_ON_C = 47
TUV_OFF_C = 50
AKU_ON_C = 70
AKU_OFF_C = 75

# ======== Oběhové čerpadlo akumulační nádrže ========
AKU_PUMP_ON_C = 65
AKU_PUMP_OFF_C = 60

# ======== DS3231 (I2C1) ========
RTC_I2C_ID = 1
RTC_SDA_PIN = 2
RTC_SCL_PIN = 3
RTC_I2C_FREQUENCY = 400000

# ======== DS18B20: venkovní čidlo a stávající boilerové čidlo ========
OUTDOOR_TEMP_PIN = 19
OUTDOOR_TEMP_SENSOR_ROM = None  # samostatná 1-Wire sběrnice
TUV_TEMP_PIN = 11  # původní BOILER_TEMP_PIN na Pico Slave
TUV_TEMP_SENSOR_ROM = None  # jediné čidlo na GPIO 11
TUV_TEMP_READ_INTERVAL_MS = 10000
TUV_TEMP_TIMEOUT_MS = 60 * 60 * 1000
OUTDOOR_TEMP_READ_INTERVAL_MS = 60000
OUTDOOR_TEMP_SEND_INTERVAL_MS = 30000

# ======== RS485 ========
RS485_TX = 4
RS485_RX = 5

# ======== UART0 (Mega) ========
UART0_TX = 0
UART0_RX = 1
