# Etapa 1: RPi 4 přímo na USB–RS‑485

Stav k 10. 10. 2026: implementováno a ověřeno softwarově, **neověřeno na
skutečném převodníku ani v provozu**. Převodník podle uživatele zatím není
připojený. USB identifikátory jsou záměrně prázdné. Nic nebylo nasazeno na RPi,
nebyl nahrán firmware ani odeslán povel fyzickému zařízení.

Uno nadále řídí ČOV, Slave regulátor, ohřev a čerpadlo. Firmware všech tří MCU
zůstává beze změny, včetně uloženého Pico Masteru. Pico 2 ani kurník tato etapa
neřeší. Výchozí režim aplikace bez externí konfigurace zůstává `legacy`.

## Provedený plán a struktura změny

1. Porovnat skutečné zdrojové programy a původní testy, nikoliv pouze komentáře.
2. Oddělit přímé linky, rámcování, USB identifikaci a stáří dat od GUI.
3. Připojit je ke stávajícím stavům, loggerům a ovládacím prvkům aplikace.
4. Ověřit chybné rámce, časové limity, povely a obnovování na fake UART a PTY.
5. Připravit konfiguraci, zapojení, zkušební postup a návrat.

`app/communication.py` vybírá právě jeden backend. `direct_link.py` má vlastní
vlákno pro každou linku; detekce udev běží v třetím vlákně a nezdržuje jejich
čtení. `direct_protocol.py` parsuje skutečné koncové rámce. `telemetry.py`
počítá jednotlivá stáří. `gui.py` spotřebovává události se zachovaným časem
přijetí a používá stejné stavové objekty a loggery jako dosud.

## Hardware a zdroje

Použit je **USB TO 4CH RS485**, nikoliv varianta (B) ani RS485/422 s FTDI.
Výrobce uvádí CH344L/SP485EEN, neizolované provedení, automatické přepínání
vysílání/příjmu a použití výchozího ovladače Linux/RPi. Na konkrétním Raspberry
Pi OS je nutné ověřit enumeraci všech čtyř rozhraní, ovladač a oprávnění.
Název `/dev/ttyACM0` v příkladu výrobce není stabilní identita ani závazné
přiřazení fyzického portu. Zdroj: [Waveshare wiki](https://www.waveshare.com/wiki/USB_TO_4CH_RS485).

Výrobce označuje A jako A+, B jako B−, PE jako signal ground a uvádí
přepínatelné 120Ω zakončení pomocí DIP. Ověřit konkrétní polohu ON a vazbu
přepínače na kanál podle potisku kusu, nikoliv odhadem.
Zdroj: [produkt USB TO 4CH RS485](https://www.waveshare.com/product/iot-communication/wired-comm-converter/usb-to-4ch-rs485.htm).
Uživatelem zvolený prodejce: [RPishop USB převodník](https://rpishop.cz/643783/waveshare-prumyslovy-usb-prevodnik-na4-rs485/).

Uživatel doložil [Pico‑2CH‑RS485](https://www.waveshare.com/wiki/Pico-2CH-RS485).
Pinout odpovídá firmwaru: GP0/GP1 = UART0, GP4/GP5 = UART1.
Z [veřejného schématu](https://files.waveshare.com/upload/0/02/Pico-2CH-RS485.pdf)
vyplývá řízení DE a /RE tranzistorem z TX, bez zvláštního GPIO. DI je uzemněné;
logická jednička spoléhá na uvolnění sběrnice a bias. Zakreslené R8/R18 jsou
120 Ω přímo mezi A/B, R7/R9 a R17/R19 tvoří bias. S1/S2 jsou tranzistory,
**ne přepínače zakončení**. Svorkové GND_0/GND_1 vede k logické zemi přes
C5/C6 = 1 nF, tedy podle schématu nejde o přímou stejnosměrnou referenci.
Tyto závěry ze schématu je nutné porovnat s revizí a osazením skutečné desky.

| Port / linka | Protistrana | Rychlost a formát | Směr a řízení |
|---|---|---|---|
| USB port 1 (`cov`) | stávající RS‑485 modul Uno | 9600, 8N1 | Uno → RPi; RPi zde nikdy nevysílá. Uno přepíná `RS485_DIR`, po `flush()` vrací příjem. |
| USB port 2 (`slave`) | Pico‑2CH‑RS485, UART0 GP0/GP1 | 9600, 8N1 | obousměrný poloduplex; Waveshare a Pico modul řídí směr hardwarově |
| USB porty 3 a 4 | rezerva | nekonfigurovány | aplikace je neotevírá |
| Slave UART1 GP4/GP5 | solární regulátor | 115200, 8N1, Modbus RTU | beze změny; Slave iniciuje čtení, kontroluje CRC |
| původní RPi ↔ Master | `/dev/serial0`, Master PIO GP8/GP9 | 115200, 8N1, TTL | pouze v režimu `legacy` |

### Kontrola vodičů a zakončení

- Master odpojit od obou provozních RS‑485 linek před připojením nového hostu.
  Nepropojovat mezi sebou USB porty 1 a 2. Nezasahovat do druhého kanálu Slave
  vedoucího k regulátoru.
- Zkontrolovat A/B podle označení konkrétních transceiverů a jejich schémat;
  různí výrobci používají různá označení. U Pico schéma uvádí pin A = 6,
  B = 7 na SP3485. Při nečitelnosti dat ověřit polaritu měřením, ne změnou
  parseru či předpokladem jiné rychlosti.
- Určit skutečný referenční vodič a zemní potenciály. Nezaměňovat název PE
  na převodníku bez kontroly dokumentace za pokyn k připojení ochranného PE
  sítě. U Pico není svorkový GND podle uvedeného schématu přímé logické GND;
  ověřit kontinuitu při vypnutém napájení a navrhnout referenci podle reálného
  zapojení. Schéma není důkaz skutečného zapojení instalace.
- Na každé samostatné lince zakončovat její dva fyzické konce, ne každou
  svorku či odbočku. Zkontrolovat již osazený odpor Pico/Uno, nepřidat třetí.
  Při dvou odporech 120 Ω se bez napájení očekává přibližně 60 Ω mezi A/B
  (ostatní součástky mohou měření ovlivnit). DIP nepoužitých USB portů ponechat OFF.
- Model a osazení převodníku **u Una nebyly dodány**. Jeho A/B, reference,
  propojení DE/RE a zakončení zůstávají povinnou kontrolou; firmware dokládá
  logiku ovládání směru, nikoliv model hardwaru.

## Skutečné protokoly a časování

Zdrojový audit: `arduino_cov/uno_vs3_vytezovac/uno_vs3_vytezovac.ino`,
`pico_master/{main,parser,rs485,pio_uart_tx,state}.py`,
`pico_slave/{main,mega_protocol,modbus_ep,config,heating_control}.py`,
`rpi4/app/{gui,parser,link_receiver,state,fve_energy}.py` a všechny původní testy.

| Vysílač | Skutečný rámec | Perioda / poznámka |
|---|---|---|
| Uno | `<P1,P2,AIR,FLOATMASK,TW,MODE,EP1,EP2>\r\n` | 10 s; např. `<1,0,1,6,18.5,1,0,0>`; není implementovaný přijímač ovládacích povelů |
| Slave | `<PUMP:A,1>\n` | nominálně 1 s, před HEAT |
| Slave | `<HEAT:A,K,AUTO,17,42.50>\n` | nominálně 1 s; MODE, ACTIVE, REASON, END_HOUR, TUV; prázdná teplota = chybí |
| Slave | `<OUT:12.25>\n` | odesílání 30 s, lokální měření 60 s |
| Slave | `<R1:52.12,1234,567,890,12345,2,54.20,49.10,26>\n` | nominálně 5 s, pouze při kompletních datech regulátoru |

R1 obsahuje BATT, PWR, ENG_DAY, ENG_MONTH, ENG_YEAR, CH, VBAT_MAX_DAY,
VBAT_MIN_DAY, R3111. Zachováno škálování a jednotky dosavadního protokolu
(včetně stávajících popisků energie v UI). Nejde o raw Modbus rámce pro RPi.

Slave provádí synchronní čtení DS18B20 a regulátoru. Jedno Modbus čtení může
čekat 200 ms, celá sada má 11 čtení; po opakovaných selháních reinicializuje
UART1. Nominální sekundové statusy proto nejsou pevně časované sloty.

Master dosud každých přibližně 500 ms vytvářel nový agregát:
`<osm hodnot ČOV,OUT,COV_AGE>`, `R1:...`, `H:...`, `P:...`, oddělený LF.
Při stáří HEAT přes 3 s vydával `ACTIVE=0,REASON=NO_DATA`; PUMP nahrazoval
`P:NO_DATA`. Regulátor a OUT opakoval i bez nových dat. Nový backend tyto
agregáty nepředpokládá a platnost ze syntetického opakování neobnovuje.
Legacy protokol včetně 16bytového PIO paddingu na TX zůstává dostupný.

Rámcovač přijímá rozdělené i spojené `<...>` bez závislosti na LF, má limit
256 B, při novém `<` resynchronizuje a neignoruje poškozené ASCII bajty.
Neúplný rámec po 1 s ticha zahodí. Chybné typy, počty polí, stavy a nečíselné
hodnoty nezvyšují čas platných dat. Protokol koncových zařízení nemá CRC;
syntakticky platnou změnu číslice po kolizi nelze spolehlivě detekovat.

## Stáří a provozní reakce

Čas se zaznamená v přijímacím vlákně při dokončení platného rámce, používá
`monotonic()`. Pozdější čtení události GUI ani připojení portu jej neposune.
Každý typ má samostatný čas; údaje uvnitř R1 sdílí čas svého rámce.

| Údaj | Limit / reakce |
|---|---|
| ČOV | pro logování zachováno ≤15 s; po >30 s stávající COV NO DATA; poslední hodnoty se nemažou |
| HEAT | ≤3 s, poté neznámý MODE/ACTIVE, NO_DATA; ne potvrzené vypnutí |
| PUMP | ≤3 s, poté neznámý MODE/ACTIVE, BEZ ZPĚTNÉHO STAVU |
| TUV | platná hodnota z HEAT, ≤3 s; prázdné pole ji zneplatní okamžitě |
| R1 | stáří od R1; nový zobrazovací limit 30 s, pak `---`, žádné logování starého vzorku |
| OUT | stáří od OUT; nový zobrazovací limit 90 s (3 periody), pak `---` |
| neaktivní port | 30 s bez bajtů → zavřít, samostatně zkusit znovu po 1 s |
| ruční požadavky GUI | zachováno 40 min bez příslušného statusu: pumpa → A, ohřev → 0 |

R1/OUT dříve neměly samostatný limit; uvedené nové limity se týkají pouze
zobrazení a dostupnosti vzorků, ne lokální automatiky. Přijetí OUT dokládá
přijetí zprávy, nikoliv nové měření: Slave si drží poslední venkovní teplotu.
Uno obdobně místo chybné teploty vody odesílá 0; bez změny firmwaru to nelze
odlišit od skutečné nuly.

Lokální čtení teplot na RPi a ovládací perioda se nemění: AKU po 10 s,
požadované režimy HEAT/PUMP po 2 s. Odhad energie dostává skutečné HEAT
události a při chybě `None`; zachována jeho tolerance mezery 90 s.
Slavovy limity platnosti teplot a ručních povelů 40 min, maxima TUV 50 °C /
AKU 75 °C, ochranná prodleva relé 5 s, časové okno a hystereze pumpy
66/65 °C zůstávají ve firmwaru beze změny. Totéž platí pro plováky, časovače,
watchdog a místní ochrany Una.

## Povely, fronta a poloduplex

| Povel RPi → Slave | Potvrzení |
|---|---|
| `<HEAT:A/T/K/0>` (jedna z hodnot) | bez ACK; až následující HEAT ukáže pozorovaný MODE a skutečný ACTIVE/REASON |
| `<PUMP:A/M>` | bez ACK; následující PUMP ukáže pozorovaný MODE a ACTIVE |
| `<TEMP:62>` | bez ACK i bez echo hodnoty; nelze prokázat doručení pouze ze stavové zprávy |
| `<PTEMP:66.000>` nebo `<PTEMP:>` | totéž; prázdná hodnota u Slave nemaže ani neobnovuje poslední platný průměr |

Veřejné metody přímého transportu vracejí přijetí požadavku do krátkodobého
bufferu, **nikoliv odeslání nebo potvrzení**. Diagnostika rozlišuje `queued`,
`written_unconfirmed`, `state_observed`, `expired_unsent`, `connection_lost`.
`state_observed` je shoda režimu v pozdější telemetrii, nikoliv korelované ACK
ani záruka sepnutí relé. UI používá přijatý ACTIVE; požadavek zobrazuje jako čekání.

Na ČOV se nic neposílá. Pro Slave jsou povoleny pouze čtyři známé typy povelů,
bez LF/paddingu Masteru. Uchovává se jen poslední požadavek každého typu,
maximálně 2 s. Po ztrátě spojení se požadavky zahodí. Po novém spojení jsou
nutné nové platné HEAT i PUMP, nejvýše 3 s staré. Neexistuje disková fronta.
GUI pak znovu předává aktuální záměr po aplikaci dosavadního 40min limitu;
krátký výpadek tedy záměr zachová, dlouhý výpadek starý ruční běh neobnoví.
Restart aplikace zůstává s výchozím AUTO stejně jako dříve.

Odesílač čeká na kompletní HEAT, nejméně 30 ms bez příjmu, prázdný RX buffer
a čas nejvýše 150 ms po HEAT. Pošle nejvýše jeden burst do 64 B v daném okně
(asi 67 ms na vodiči při 9600 Bd). Žádný blokující `flush()`; zápis má timeout
50 ms. Částečný zápis znamená neurčitý výsledek, uzavření linky a zahození
fronty. Úspěšný zápis do ovladače se nikdy nepovažuje za stav zařízení.

**Tento guard omezuje kolize, není arbitráž sběrnice.** Slave může po HEAT
odeslat OUT a po nepředvídatelně dlouhém čtení regulátoru R1. USB buffering a
plánovač Linuxu přidávají nejistotu. Host nemůže bez změny protokolu zaručit,
že Slave nezačne vysílat během hostova povelu. Automatický směr řeší pouze
DE/RE. Proto jsou v příkladu obě podmínky `tx_enabled` a
`half_duplex_validated` vypnuté. Druhá je záznam úspěšné zkoušky daného
zapojení, nikoliv technická záruka nulových kolizí. Pokud zkouška nevyhoví,
obousměrný provoz neschválit; bude nutná samostatně dohodnutá změna protokolu
např. polling/rezervovaný slot a ACK, případně jiné fyzické řešení.

## Stabilní přiřazení čtyř portů

Aplikace nepoužívá pořadí ttyUSB/ttyACM. Pro každý aktivní port požaduje
přesnou shodu skutečných udev vlastností:

- `ID_VENDOR_ID`, `ID_MODEL_ID`, `ID_SERIAL_SHORT`, `ID_USB_INTERFACE_NUM`,
  pokud jsou skutečně dostupné a kombinace jednoznačná; nebo
- `ID_VENDOR_ID`, `ID_MODEL_ID`, `ID_PATH` pro konkrétní USB zásuvku/topologii
  a rozhraní, pokud chybí spolehlivé sériové číslo.

Lze zadat všechny dostupné uvedené klíče pro přísnější shodu. Hodnoty jsou
řetězce přesně z udev, včetně vedoucích nul; VID/PID ani čísla rozhraní se
nedoplňují podle odhadu. Prázdná identita, více shod nebo stejný port pro obě
role znamená zákaz otevření daného přiřazení, tedy i vysílání. Chybějící Uno
neblokuje jednoznačně určený Slave a naopak. Neexistuje fallback na první tty.

Postup až s připojeným zařízením, bez čerpadel a s vypnutým TX:

1. Uložit `lsusb`, `uname -a`, `/etc/os-release`, `ls -l /dev/serial/by-id/ /dev/serial/by-path/`
   a výpis `python3 rpi4/serial_inventory.py`. Tento nástroj jen čte udev,
   sériové porty neotevírá a neposílá data.
2. Pro každý nalezený port uložit
   `udevadm info --query=property --name=/dev/ttyACM…` (nebo skutečné ttyUSB…).
   Ověřit čtyři rozhraní a skutečný kernelový ovladač; nepředpokládat FTDI.
3. Na fyzický kanál vždy jednotlivě přivést známý zkušební RS‑485 vysílač při
   9600 8N1, pozorovat jeho unikátní zprávu a příslušnou RX LED. Zapsat vazbu
   CH1–CH4 ↔ tty ↔ USB interface ↔ by-id/by-path. Není bezpečné hádat podle
   názvu tty ani čísla interface. Vysílač nemá ovládat provozní zařízení.
4. Zkopírovat [direct.example.json](../rpi4/config/direct.example.json) do vlastní
   konfigurace a vyplnit objekty `identity` z naměřených hodnot: CH1 do `cov`,
   CH2 do `slave`. Porty 3/4 do konfigurace vůbec nepřidávat. TX stále false.
5. Odpojit/připojit USB a restartovat testovací RPi. Potvrdit, že se obě role
   nezaměnily ani při změně čísel tty. U `ID_PATH` zachovat USB zásuvku/hub;
   po změně topologie provést identifikaci znovu. Ověřit také nepřítomnost
   druhého převodníku se stejnými identifikátory.

Pro vlastní udev aliasy lze použít stejné ověřené klíče, ale aplikace je
nevyžaduje a není potřeba v této etapě instalovat neověřená udev pravidla.
Pro přístup k portům ověřit práva běžného uživatele (typicky skupina dialout),
nezapínat celou aplikaci jako root. `exclusive=True` chrání port proti druhému
spolupracujícímu procesu; přesto nesmí souběžně běžet terminál nebo druhá instance.

## Ověření bez fyzických zařízení

Z kořene repozitáře, Python 3 s pyserial 3.5, pro původní Uno test také g++:

```bash
python3 -m unittest discover -s tests -v
python3 examples/simulate_rs485.py --seconds 8
python3 examples/simulate_rs485.py --tx --seconds 8
python3 -m compileall -q rpi4 examples tests
```

Simulátor vždy vytvoří vlastní dva PTY a používá pouze `/dev/pts/…`, žádný
systémový USB port ani GPIO. Bez `--tx` ověřuje příjem, s `--tx` ukáže přenos
všech čtyř typů povelů a následnou stavovou zprávu. Nenapodobuje fyzikální
kolize, relé ani kompletní automatiku. Integrační PTY test navíc zavírá jeden
a oba protějšky, znovu je vytváří a ověřuje obnovu i zákaz přehrání fronty.

Výsledek lokálního ověření: **42 testů prošlo** (16 původních, 26 nových),
včetně C++ simulace původního Uno programu a testů původního Slave řízení.
Ověřeny přímé formáty, rozdělení/spojení, šum, neplatné hodnoty, samostatná
stáří, logger/energy adaptér, 16B legacy TX, identita/nejednoznačnost, TX
routing, čekání na volnou linku, partial write, TTL, obnovení a místní ochrany.
Headless simulace s `--tx` úspěšně přenesla TEMP/PTEMP/HEAT/PUMP a zaznamenala
`state_observed` pouze pro stavové povely. GUI nebylo vizuálně ověřeno na
1024×600 displeji RPi. Firmware nebyl kompilován cílovým embedded toolchainem
ani nahráván; relevantní původní logika byla testována hostovými simulacemi.

## Příjem na stole, potom obousměrná zkouška

Následující kroky jsou **návod pro později schválenou zkoušku, nejsou provedené**.
Na provozní RPi nic nenasazovat bez výslovného pokynu vlastníka.

1. Zálohovat provozní konfiguraci a zaznamenat kabeláž, DIP, revize modulů.
   Dokončit výše uvedenou identifikaci a kontrolu elektrického zapojení.
   Pro stolní zkoušku bezpečně odpojit výkonové spotřebiče od relé.
2. Připojit CH1 k Unu, CH2 k UART0 Slave. Master od těchto linek odpojený.
   Regulátor zůstává na UART1 Slave. První fáze pouze příjem:

   ```bash
   HOME_AS_LINK_CONFIG=/absolutni/cesta/direct.json python3 rpi4/main.py
   ```

   Konfigurace je načtena při startu, nikoliv živě. S prázdnými identitami
   se žádný USB port neotevře. `tx_enabled=false` blokuje i periodické teploty.
3. Ověřit všechny typy rámců, masku plováků, skutečné režimy, teploty, logy
   ČOV a FVE a data historie. Srovnat hodnoty s lokálním výpisem koncových
   zařízení. RX-only zkoušku plánovat s vědomím, že po 40 min bez teplot/povelů
   se projeví zachované lokální timeouty Slave; při relé bez spotřebičů je to
   zároveň vhodný test.
4. Vyzkoušet výpadek každé linky samostatně, výpadek obou USB portů najednou,
   odpojení celého převodníku a nové připojení. GUI musí dále reagovat.
   Průběžné R1 nesmí udržet staré HEAT/PUMP, Uno nesmí maskovat výpadek Slave.
   Diagnostika v `link_debug.log` uvádí pro každou linku připojení, chyby,
   počet validních/nevalidních rámců, časy a povely (snapshot po 10 s).
5. Na zkušebním zapojení bez spotřebičů připravit samostatný, výslovně
   autorizovaný postup zkušebního vysílání. **Nenastavovat
   `half_duplex_validated=true` pouze kvůli obejití blokace před zkouškou.**
   Současný provozní spouštěč dovoluje jen RX; první TX zkouška vyžaduje
   předem připravený a omezený testovací režim, který nezamění zkoušku
   za potvrzené ověření. Ověřit HEAT/PUMP a TEMP/PTEMP a zachytit
   sběrnici logickým analyzátorem
   nebo RS‑485 analyzátorem; sledovat DE/RE, dojetí posledního stop bitu,
   polaritu, idle bias a souběh s telemetrií. Návratová stavová zpráva musí
   odpovídat požadavku, ACTIVE může zůstat vypnutý kvůli ochraně/časování.
6. Zátěžová zkouška musí zahrnout 1s HEAT/PUMP, 5s čtení regulátoru, 30s OUT,
   60s DS konverzi, timeouty/obnovy Modbusu, restart Slave, USB latenci a
   zatížení RPi. Zkusit povely blízko hran zpráv. U TEMP/PTEMP ověřit přijetí
   také na lokální diagnostice Slave, protože nemají ACK ani echo.
7. Změřit četnost chybných/ztracených rámců a požadavek → stav, prokázat
   nepřítomnost nežádoucích sepnutí při výpadku/obnově a správné chování po
   40 min. Pokud dochází ke kolizím nebo nejistým změnám stavu, TX znovu
   vypnout a obousměrnou migraci nenasazovat bez doplnění arbitráže.

## Návrat k Pico Masteru

1. Zastavit aplikaci v režimu direct; tím se uzavřou obě linky. Odpojit
   Waveshare od provozních RS‑485 linek, neponechat druhého vysílače paralelně.
2. Vrátit původní kabeláž Uno → Master UART0, Slave UART0 → Master UART1,
   RPi `/dev/serial0` ↔ Master GP8/GP9. Vrátit původní zakončení a referenci.
   Samostatná linka Slave ↔ regulátor zůstává po celou dobu stejná.
3. Použít [legacy.example.json](../rpi4/config/legacy.example.json), nebo zrušit
   `HOME_AS_LINK_CONFIG`; aplikaci spustit znovu. Neexistuje automatický
   fallback ani souběžné spuštění backendů uvnitř aplikace.
4. Zkontrolovat agregované řádky, aktuální COV_AGE, H/P statusy a logy.
   Master firmware se při migraci nemění a není potřeba jej nahrávat.
   Po restartu aplikace zkontrolovat požadované AUTO a skutečné stavy.

## Co zůstává pro skutečný hardware

- USB inventura čtyř rozhraní, sériové číslo / interface / ID_PATH, ovladač
  konkrétního Raspberry Pi OS a jednoznačná fyzická identifikace CH1–CH4.
- Model Uno RS‑485 modulu; revize Pico desky, osazení R8/R18, skutečná
  reference GND, A/B, DIP, odpor celé linky a vhodnost neizolovaného propojení.
- Obousměrné časování, USB latence, průběhy DE/RE a zátěžové souběhy uvedené
  výše. PTY důkaz nemůže nahradit měření kolizí na dvouvodičové RS‑485.
- Dlouhodobá zkouška, místní ochrany s odpojeným hostem, návrat po dlouhém
  výpadku, skutečné logy, dotykové GUI a fyzický postup rollbacku.
- Výslovné schválení nasazení na provozní RPi. Softwarové testy samy o sobě
  nejsou schválením provozu ani tvrzením, že je hardware ověřen.
