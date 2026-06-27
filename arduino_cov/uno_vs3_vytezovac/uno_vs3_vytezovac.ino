#include <Wire.h>
#include <RTClib.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <SoftwareSerial.h>
#include <EEPROM.h>
#include <avr/wdt.h>    // umí watchdog reset (vložit mezi include kdykoliv)
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

bool restartDoneMorning = false;
bool restartDoneEvening = false;
byte lastResetDay = 0;     // 0 jako výchozí, po prvním čtení RTC se nastaví
const bool AUTO_RESTART_ENABLED = false;
byte lastResetFlags = 0;

//==========vytěžovací relé========
bool fve_load = false;
unsigned long lastFveReceiveTime = 0;
const unsigned long FVE_TIMEOUT = 600000;  // 10 minuty

// ==== Pinová konfigurace ====
SoftwareSerial rs485(10, 11); 
#define RS485_DIR 7  // pin pro směr RS485 (DE+RE)

const int PUMP1_PIN = 4;
const int PUMP2_PIN = 5;
const int AIR_PIN   = 6;
const int FVE_RELAY_PIN = 8;

const int FLOAT_1 = A0;
const int FLOAT_2 = A1;
const int FLOAT_3 = A2;
const int FLOAT_4 = A3;

const int ONEWIRE_PIN = 3;

// ==== Konstanty ====
const unsigned long PUMP2_LOW_MODE_MS = 60000;    // doladit podle reálně odčerpaného objemu
const unsigned long PUMP2_HIGH_MODE_MS = 140000;  // 60s = cca 13L 
const unsigned long FLOAT3_STOP_DELAY_MS = 2000;  // plovák 3 musí být sepnutý stabilně
const int EEPROM_MODE_ADDR = 0;

const byte PUMP_CYCLE_COUNT = 5;
const byte PUMP_CYCLE_HOURS[PUMP_CYCLE_COUNT] = {2, 7, 12, 17, 22};
const byte PUMP_CYCLE_MINUTES[PUMP_CYCLE_COUNT] = {3, 3, 3, 3, 3};
static bool cycleRunToday[PUMP_CYCLE_COUNT] = {false, false, false, false, false};
static byte lastDay = 0;
bool air_on = false;
bool ignorePumpErrors = false;

bool error_pump1 = false;
bool error_pump2 = false;
bool airPaused = false;
unsigned long airTimer = 0; 



// ==== DS18B20 ====
OneWire oneWire(ONEWIRE_PIN);
DallasTemperature sensors(&oneWire);
float tempWater = 0;
unsigned long lastTempRequest = 0;
bool waitingTemp = false; 
unsigned long lastJSONsend = 0;



// ==== RTC ====
RTC_DS3231 rtc;
bool rtcAvailable = false;
unsigned long lastRtcRetry = 0;
const unsigned long RTC_RETRY_MS = 60000;

// ==== Stav čerpadel (neblokující) ====
bool pump1_active = false;
bool pump2_active = false;
unsigned long pump1StopTime = 0; 
bool manualPump1 = false;
bool lastPumpState = false; // true = aspoň jedno čerpadlo běží
unsigned long pump1_startTime = 0;
const unsigned long PUMP1_TIMEOUT = 150000; // limit běhu čerpadla
enum PumpSequence { IDLE, PUMP2_RUNNING, PUMP1_WAITING };
PumpSequence pumpSeq = IDLE;
unsigned long pump2_runMs = PUMP2_LOW_MODE_MS;
unsigned long pump2_startTime = 0;
unsigned long pump2Float3LowSince = 0;
bool pump2Float4WasClosed = false;
bool pump2Float4OpenedAfterClosed = false;


// struktura pro režim
struct ModeParams {
  unsigned long pump2_runMs; // doba běhu Pump2 v ms (0 = žádné čerpání)
  bool  pumpEnabled;        // povolit pump2
  unsigned long airOnMs;    // doba běhu vzduchu v ms
  unsigned long airOffMs;   // doba pauzy vzduchu v ms
};

// dvě konfigurace (0 = menší objem, 1 = větší objem)
ModeParams modes[2];

// aktuální index a hodnoty použitelné k volání v ostatních funkcích
volatile uint8_t modeIndex = 0; // 0 = menší objem, 1 = větší objem
unsigned long current_pump2_runMs = PUMP2_LOW_MODE_MS;
unsigned long current_airOnMs = 20UL * 60UL * 1000UL;
unsigned long current_airOffMs = 40UL * 60UL * 1000UL;

// debouncing pro čtení režimu z plováků
unsigned long lastModeReadTime = 0;
int lastModeCandidate = -1;
const unsigned long MODE_DEBOUNCE_MS = 50;


// ==== Pomocná funkce pro RS485 ====
void rs485Write(const char *msg) {
  digitalWrite(RS485_DIR, HIGH);   // směr: vysílání
  rs485.print(msg);                // pošli zprávu
  rs485.print("\r\n");
  rs485.flush();
  digitalWrite(RS485_DIR, LOW);    // hned zpět na příjem
}


uint8_t loadSavedMode() {
  byte saved = EEPROM.read(EEPROM_MODE_ADDR);
  return saved == 1 ? 1 : 0;
}

void saveMode(uint8_t mode) {
  EEPROM.update(EEPROM_MODE_ADDR, mode == 1 ? 1 : 0);
}


// ==== Monitoring ====
void sendMonitoringSimple() {
  // načtení vstupů
  byte floatState = (digitalRead(FLOAT_1)==LOW?1:0) |
                    ((digitalRead(FLOAT_2)==LOW?1:0)<<1) |
                    ((digitalRead(FLOAT_3)==LOW?1:0)<<2) |
                    ((digitalRead(FLOAT_4)==LOW?1:0)<<3);

  bool pump1State = digitalRead(PUMP1_PIN);
  bool pump2State = digitalRead(PUMP2_PIN);
  bool airState   = air_on;

  float tWater = isnan(tempWater) ? 0.0 : tempWater;
  byte activeMode = modeIndex; // 0 = menší objem, 1 = větší objem

  // sestavení jednoduchého řetězce bez Arduino String kvůli fragmentaci RAM na Uno
  char tempBuf[10];
  char msg[48];
  dtostrf(tWater, 0, 1, tempBuf);
  snprintf(msg, sizeof(msg), "<%d,%d,%d,%u,%s,%u,%d,%d>",
           pump1State ? 1 : 0,
           pump2State ? 1 : 0,
           airState ? 1 : 0,
           (unsigned int)floatState,
           tempBuf,
           (unsigned int)activeMode,
           error_pump1 ? 1 : 0,
           error_pump2 ? 1 : 0);

  rs485Write(msg);
  Serial.println(msg);
}

void handleIncomingRS485() {

  static char buffer[24];
  static byte pos = 0;

  while (rs485.available()) {
    char c = rs485.read();

    if (c == '<') {
      pos = 0;
    }

    if (pos < sizeof(buffer) - 1) {
      buffer[pos++] = c;
      buffer[pos] = '\0';
    } else {
      pos = 0;
      buffer[0] = '\0';
    }

    if (c == '>') {

      if (strncmp(buffer, "<FVE:", 5) == 0) {

        int val = atoi(buffer + 5);

        fve_load = (val == 1);
        digitalWrite(FVE_RELAY_PIN, fve_load ? HIGH : LOW);

        lastFveReceiveTime = millis();   // reset timeoutu

        Serial.print("FVE relé: ");
        Serial.println(fve_load);
      }

      pos = 0;
      buffer[0] = '\0';
    }
  }
}

bool pumpFaultActive() {
  return error_pump1 || error_pump2;
}

void startPumpFromSettler() {
  if (pump1_active || pumpFaultActive()) return;
  pump1_active = true;
  pump1_startTime = millis();
  pump1StopTime = 0; // jistota, že je resetován
  digitalWrite(PUMP1_PIN, HIGH);
  Serial.println("Přečerpávání z usazovací nádrže start...");
}


void startPumpOutBio(unsigned long runMs) {
  if (pump2_active || pumpFaultActive()) return;
  //pauseAir();
  pump2_runMs = runMs;
  pump2_startTime = millis();
  pump2Float3LowSince = 0;
  pump2Float4WasClosed = (digitalRead(FLOAT_4) == LOW);
  pump2Float4OpenedAfterClosed = false;
  pump2_active = true;
  digitalWrite(PUMP2_PIN, HIGH);
  Serial.print("Odčerpávání z biologické nádrže start, čas ms: ");
  Serial.println(pump2_runMs);
  Serial.print("Pump2 mód: ");
  Serial.println(modeIndex == 1 ? "vetsi objem" : "mensi objem");
}

void updatePumpSequence() {
  if (pumpFaultActive()) {
    pumpSeq = IDLE;
    return;
  }

  if (pumpSeq == PUMP2_RUNNING) {
    // Jakmile Pump2 skončí, přejdeme do stavu čekání na Pump1
    if (!pump2_active) {
      pumpSeq = PUMP1_WAITING;
    }
  }
  else if (pumpSeq == PUMP1_WAITING) {
    // Spustíme Pump1, jen pokud float1 je HIGH a není chyba
    if (digitalRead(FLOAT_1) == HIGH && digitalRead(FLOAT_3) == HIGH ) {
      startPumpFromSettler();
      pumpSeq = IDLE; // sekvence dokončena
    }
  }
}

void updatePumps() {
  // Pump 1
  if (pump1_active) {
    if (digitalRead(FLOAT_4) == LOW && pump1StopTime == 0) {
        // Plovák sepnut – nastavíme čas pro zpožděné vypnutí
        pump1StopTime = millis() + 10000; // 10 vteřin
    }

    // Zkontrolujeme timeout čerpadla
    if (pump1_startTime != 0 && (millis() - pump1_startTime > PUMP1_TIMEOUT)) {
        digitalWrite(PUMP1_PIN, LOW);
        pump1_active = false;
        pump1_startTime = 0; 
        pump1StopTime = 0;
        error_pump1 = true;
        pumpSeq = IDLE;
        Serial.println("CHYBA: porucha čerpadla 1/plovák 4");
    }
    // Zpožděné vypnutí po sepnutí plováku
    else if (pump1StopTime != 0 && millis() >= pump1StopTime) {
        digitalWrite(PUMP1_PIN, LOW);
        pump1_active = false;
        pump1StopTime = 0;
        pump1_startTime = 0; // vyčistit startTime
        Serial.println("Přečerpávání z usazovací nádrže hotovo.");
    }
  }

  // Pump 2
  if (pump2_active) {
    unsigned long elapsed = millis() - pump2_startTime;

    if (digitalRead(FLOAT_4) == LOW) {
      pump2Float4WasClosed = true;
    }
    else if (pump2Float4WasClosed) {
      pump2Float4OpenedAfterClosed = true;
    }

    if (digitalRead(FLOAT_3) == LOW) {
      if (pump2Float3LowSince == 0) {
        pump2Float3LowSince = millis();
      }

      if (millis() - pump2Float3LowSince >= FLOAT3_STOP_DELAY_MS) {
        digitalWrite(PUMP2_PIN, LOW);
        pump2_active = false;
        Serial.println("Odčerpávání z biologické nádrže zastaveno plovákem 3.");
        Serial.print("Pump2 běžela ms: ");
        Serial.println(elapsed);
      }
    }
    else {
      pump2Float3LowSince = 0;
    }

    if (pump2_active && elapsed >= pump2_runMs) {
      digitalWrite(PUMP2_PIN, LOW);
      pump2_active = false;
      Serial.println("Odčerpávání z biologické nádrže hotovo podle času.");
      Serial.print("Pump2 běžela ms: ");
      Serial.println(elapsed);

      if (!pump2Float4OpenedAfterClosed) {
        error_pump2 = true;
        pumpSeq = IDLE;
        Serial.println("CHYBA: porucha čerpadla 2/plovák 4");
      }
    }
  }

}

// ==== Cyklus ====
void syncModeBeforePumpCycle() {
  uint8_t newIndex = readModeFromFloats();

  if (newIndex != modeIndex) {
    modeIndex = newIndex;
    lastModeCandidate = newIndex;
    applyMode();
  }
}

void runCycle() {
  syncModeBeforePumpCycle();

  if (pumpFaultActive()) {
    Serial.println("runCycle: porucha cerpadla/plovaku 4, cerpani blokovano do resetu.");
    return;
  }

  if (pumpSeq == IDLE && digitalRead(FLOAT_3) == HIGH) {
    if (modes[modeIndex].pumpEnabled && current_pump2_runMs > 0) {
      startPumpOutBio(current_pump2_runMs); // spustí Pump2
      pumpSeq = PUMP2_RUNNING;
    } else {
      Serial.println("runCycle: cerpani vypnuto v aktualnim rezimu. Nic se nespousti.");
    }
  }
}


// ==== Vzduchování ====
void manageAir(){ 
  unsigned long now = millis();

  // Normální přepínání podle časovače
  if (air_on && now - airTimer >= current_airOnMs) {
    air_on = false;
    digitalWrite(AIR_PIN, LOW);
    airTimer = now;
    Serial.println("Vzduch vypnut.");
  } 
  else if (!air_on && now - airTimer >= current_airOffMs) {
    air_on = true;
    digitalWrite(AIR_PIN, HIGH);
    airTimer = now;
    Serial.println("Vzduch zapnut.");
  }

  // Výstup vzduchování se drží podle vlastního časovače bez ohledu na chyby čerpadel.
  digitalWrite(AIR_PIN, air_on ? HIGH : LOW);
}


void safeRestart() {
  Serial.println("Safe restart: vypínám výstupy a spouštím WDT...");

  // 1) bezpečně vypni výstupy (relé / řízení)
  digitalWrite(RS485_DIR, LOW);
  digitalWrite(PUMP1_PIN, LOW);
  digitalWrite(PUMP2_PIN, LOW);
  digitalWrite(AIR_PIN, LOW);
  air_on = false;

  // Pokud máš další výstupy/rele, vypni je zde také.
  // (Nepoužívej delay dlouhé více než pár sekund; 2 s je dost pro relé/motory.)
  delay(2000); // počkej aby se zařízení bezpečně zastavilo

  // 2) iniciuj watchdog reset (hard reset)
  // Používám nejkratší dostupný timeout, aby reset nastal rychle.
  wdt_enable(WDTO_15MS);
  while (1) { } // čekej na reset
}

// Zavolat v místě, kde už máš DateTime nowRTC = rtc.now();
void checkAutoRestart(const DateTime &nowRTC) {
  if (!AUTO_RESTART_ENABLED) return;

  // Na prvním volání inicializuj lastResetDay
  if (lastResetDay == 0) {
    lastResetDay = nowRTC.day();
  }

  // Reset příznaků při novém dni
  if (nowRTC.day() != lastResetDay) {
    restartDoneMorning = false;
    restartDoneEvening = false;
    lastResetDay = nowRTC.day();
  }

  // Ráno 06:00 (provedeme jednou v rámci minuty 06:00..06:00)
  if (!restartDoneMorning && nowRTC.hour() == 5 && nowRTC.minute() == 0) {
    Serial.println("Plánovaný restart: 06:00");
    restartDoneMorning = true;
    safeRestart(); // funkce nevrátí, protože provede reset
  }


  // Večer 18:00
  if (!restartDoneEvening && nowRTC.hour() == 17 && nowRTC.minute() == 0) {
    Serial.println("Plánovaný restart: 18:00");
    restartDoneEvening = true;
    safeRestart();
  }
}
void applyMode() {
  // nastavíme běžící parametry podle aktuálního režimu
  current_pump2_runMs = modes[modeIndex].pump2_runMs;
  current_airOnMs = modes[modeIndex].airOnMs;
  current_airOffMs = modes[modeIndex].airOffMs;

  // pokud nový mód zakazuje čerpání a pumpa teď běží, bezpečně ji zastav
  if (!modes[modeIndex].pumpEnabled) {
    if (pump2_active) {
      digitalWrite(PUMP2_PIN, LOW);
      pump2_active = false;
      Serial.println("Rezim zmenen: Pump2 vypnuta (rezim zakazuje cerpani).");
    }
  }

  // uprav chování vzduchu: pokud právě běží vzduch, uprav airTimer tak, aby
  // cyklus pokračoval korektně od nového startu (volitelné). Zde nastavíme
  // airTimer = millis() aby se pauza počítala od právě zapnutého času.
  airTimer = millis();
  saveMode(modeIndex);
  Serial.print("Applied mode "); Serial.println(modeIndex);
}

uint8_t readModeFromFloats() {
  // Plovák 2 má prioritu: při vysoké hladině se přepne na větší objem.
  if (digitalRead(FLOAT_2) == LOW) {
    return 1;
  }

  // Plovák 1 je dolní mez: při nízké hladině se přepne na menší objem.
  if (digitalRead(FLOAT_1) == LOW) {
    return 0;
  }

  // Mezi plováky držíme poslední režim, aby mód nepřeskakoval hned po rozepnutí plováku.
  return modeIndex;
}

void checkMode() {
  uint8_t candidate = readModeFromFloats();

  if (candidate != lastModeCandidate) {
    lastModeReadTime = millis();
    lastModeCandidate = candidate;
    return;
  }

  if (millis() - lastModeReadTime < MODE_DEBOUNCE_MS) return;

  if (candidate != modeIndex) {
    modeIndex = candidate;
    applyMode();
  }
}


void print2Digits(int value) {
  if (value < 10) Serial.print('0');
  Serial.print(value);
}

void printRtcTime(const DateTime &nowRTC) {
  print2Digits(nowRTC.hour());
  Serial.print(':');
  print2Digits(nowRTC.minute());
  Serial.print(':');
  print2Digits(nowRTC.second());
}

void printRtcDate(const DateTime &nowRTC) {
  Serial.print(nowRTC.year());
  Serial.print('-');
  print2Digits(nowRTC.month());
  Serial.print('-');
  print2Digits(nowRTC.day());
}

bool rtcTimeLooksValid(const DateTime &nowRTC) {
  return nowRTC.year() >= 2024 && nowRTC.year() <= 2099;
}

bool detectRtc(bool logResult) {
  bool ok = rtc.begin();

  if (logResult) {
    Serial.print("RTC stav: ");
    Serial.println(ok ? "OK" : "NEDOSTUPNE");
  }

  return ok;
}

bool ensureRtcAvailable(unsigned long now) {
  if (rtcAvailable) return true;
  if (lastRtcRetry != 0 && now - lastRtcRetry < RTC_RETRY_MS) return false;

  lastRtcRetry = now;
  rtcAvailable = detectRtc(true);
  return rtcAvailable;
}



void setup() {

  // --- 1) Pojistka proti zacyklení watchdogem ---
  lastResetFlags = MCUSR;
  MCUSR = 0;        
  wdt_disable();    
  delay(50);        


  // --- 2) Nastavení pinů ještě před periferiemi ---
  pinMode(PUMP1_PIN, OUTPUT);
  pinMode(PUMP2_PIN, OUTPUT);
  pinMode(AIR_PIN, OUTPUT);
  pinMode(FVE_RELAY_PIN, OUTPUT);

  pinMode(FLOAT_1, INPUT_PULLUP);
  pinMode(FLOAT_2, INPUT_PULLUP);
  pinMode(FLOAT_3, INPUT_PULLUP);
  pinMode(FLOAT_4, INPUT_PULLUP);

  pinMode(RS485_DIR, OUTPUT);
  digitalWrite(RS485_DIR, LOW); // výchozí příjem

  // --- 3) Výstupy do bezpečného stavu ---
  digitalWrite(PUMP1_PIN, LOW);
  digitalWrite(PUMP2_PIN, LOW);
  digitalWrite(AIR_PIN, HIGH);
  digitalWrite(FVE_RELAY_PIN, LOW);   // výchozí stav

  air_on = true;
  airTimer = millis();


  // --- 4) Inicializace základních periferií ---
  Serial.begin(9600);
  rs485.begin(9600);
  Serial.print("Reset flags: ");
  Serial.println(lastResetFlags, BIN);
  if (lastResetFlags & _BV(WDRF)) {
    Serial.println("Posledni reset provedl watchdog.");
  }

  Wire.begin();
#if defined(WIRE_HAS_TIMEOUT)
  Wire.setWireTimeout(3000, true);
#endif
  delay(10);         // malá prodleva pomáhá stabilizaci RTC/I2C

  rtcAvailable = detectRtc(true);       // až po Wire.begin()



  // --- 6) Inicializace DS18B20 ---
  sensors.begin();
  sensors.setWaitForConversion(false);

  // --- 8) Nastavení režimů ---
  modes[0].pump2_runMs  = PUMP2_LOW_MODE_MS;
  modes[0].pumpEnabled  = true;
  modes[0].airOnMs      = 20UL * 60UL * 1000UL;
  modes[0].airOffMs     = 40UL * 60UL * 1000UL;

  modes[1].pump2_runMs  = PUMP2_HIGH_MODE_MS;
  modes[1].pumpEnabled  = true;
  modes[1].airOnMs      = 30UL * 60UL * 1000UL;
  modes[1].airOffMs     = 30UL * 60UL * 1000UL;

  modeIndex = loadSavedMode();
  modeIndex = readModeFromFloats();
  lastModeCandidate = modeIndex;

  applyMode();

  // Když se hlavní smyčka opravdu zasekne, AVR watchdog provede bezpečný restart.
  // Běžný průchod loopem ho krmí na konci smyčky.
  wdt_enable(WDTO_8S);
}


void loop() {
  unsigned long now = millis();

  handleIncomingRS485();
  // ===== Bezpečnostní timeout FVE =====
  if (fve_load && (millis() - lastFveReceiveTime > FVE_TIMEOUT)) {
    fve_load = false;
    digitalWrite(FVE_RELAY_PIN, LOW);
    Serial.println("FVE timeout – relé vypnuto");
  }



  checkMode();
  


  // --- DS18B20 teploty ---
  if (!waitingTemp && now - lastTempRequest >= 60000) { 
      sensors.requestTemperatures();    // spustí měření
      lastTempRequest = now;
      waitingTemp = true;
  }

  if (waitingTemp && now - lastTempRequest >= 750) {   
      float t0 = sensors.getTempCByIndex(0);

      bool waterSensorOK = (t0 != DEVICE_DISCONNECTED_C);

      // Uložíme hodnotu, pokud je čidlo OK.
      tempWater = waterSensorOK ? t0 : 0;

      waitingTemp = false;
  }
  // --- Odesílání JSON  ---
  if (now - lastJSONsend >= 10000) {
      sendMonitoringSimple();
      lastJSONsend = now;
  }
      // ==== Čerpací cykly podle času ====
  // Proměnná pro uchování času poslední kontroly cyklu
  static unsigned long lastCycleCheck = 0;

  // Interval kontroly cyklu v milisekundách (tady každých 5 sekund)
  const unsigned long CYCLE_INTERVAL = 10000;

  // Kontrola cyklů prováděná v hlavní smyčce
  if (now - lastCycleCheck >= CYCLE_INTERVAL) {
    lastCycleCheck = now; // aktualizace času poslední kontroly

    if (!ensureRtcAvailable(now)) {
      Serial.println("RTC nedostupne, casove cykly preskoceny.");
      updatePumps();
      updatePumpSequence();
      manageAir();
      wdt_reset();
      return;
    }

    DateTime nowRTC = rtc.now(); // načtení aktuálního času z RTC

    if (!rtcTimeLooksValid(nowRTC)) {
      rtcAvailable = false;
      Serial.println("RTC vraci neplatny cas, casove cykly preskoceny.");
      updatePumps();
      updatePumpSequence();
      manageAir();
      wdt_reset();
      return;
    }

    Serial.print("RTC čas: ");
    printRtcTime(nowRTC);
    Serial.println();
    Serial.print("RTC datum: ");
    printRtcDate(nowRTC);
    Serial.println();
    Serial.println("Kontrola cyklu proběhla");
    checkAutoRestart(nowRTC);

    // ===== Reset flagu pro nový den =====
    if (nowRTC.day() != lastDay) {
      for (byte i = 0; i < PUMP_CYCLE_COUNT; i++) {
        cycleRunToday[i] = false;
      }
      lastDay = nowRTC.day();     // aktualizace dne
    }

    // ===== Čerpací cykly =====
    for (byte i = 0; i < PUMP_CYCLE_COUNT; i++) {
      if (nowRTC.hour() == PUMP_CYCLE_HOURS[i] &&
          nowRTC.minute() == PUMP_CYCLE_MINUTES[i] &&
          !cycleRunToday[i]) {
        runCycle();               // spuštění čerpadel
        cycleRunToday[i] = true;  // tento čas už byl dnes proveden
        Serial.print("Čerpadla spuštěna v ");
        print2Digits(PUMP_CYCLE_HOURS[i]);
        Serial.print(':');
        print2Digits(PUMP_CYCLE_MINUTES[i]);
        Serial.println();
      }
    }
  }

  updatePumps();
  updatePumpSequence();
  manageAir();

  wdt_reset();

}
