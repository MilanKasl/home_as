# Nasazení první etapy – konkrétní RPi, 12. 10. 2026

Tento postup doplňuje [technický popis migrace](migrace-usb-rs485.md).
Neobsahuje flashování ani změny Uno/Slave/Master. Identifikace probíhá přímo
v Home AS. Příjem neznamená ověřený poloduplex.

## Zjištěný stav před přípravou

Přístup: `ssh milan@192.168.0.98`. Jméno `raspberrypi.local` se z pracovního
prostředí nepřekládalo; přes IP byl přístup úspěšný. Stávající aplikace:

- adresář `/home/milan/home_as/rpi4`;
- `/usr/bin/python3 /home/milan/home_as/rpi4/main.py`;
- ikona `/home/milan/Desktop/COV-FVE.desktop`, pracovní složka stejná;
- při kontrole neběžel žádný Python proces aplikace;
- stará uživatelská `dashboard.service` je enabled, ale failed s výsledkem
  `200/CHDIR`. Ukazuje na `/home/milan/dashboard_vs2`, který neexistuje.
  Není opravována, spouštěna ani použita pro tuto zkoušku.
- dostupné pyserial 3.5 a Tk 8.6; netřeba pro tento kód měnit systémové balíčky.

Na RPi byly čtením udev potvrzeny `1a86:55d5`, serial `BD63F2ABCD`, ovladač
`cdc_acm`, interface `00/02/04/06`. Aktuální ttyACM1–4 nejsou mapováním ke svorkám.
Stabilní cesty: `/dev/serial/by-id/usb-WCH.CN_USB_Quad_Serial_BD63F2ABCD-if00`
a obdobně `if02`, `if04`, `if06`. Master má jiné USB zařízení; identifikace ho neotevírá.

## Záloha před změnami

Na RPi byla vytvořena a ověřena záloha:
`/home/milan/home_as_backups/2026-10-12-before-usb-rs485/`

- `original-app-and-startup.tar.gz`: celý `home_as`, původní ikona a soubor služby;
- `original-logs-and-energy.tar.gz`: celé `logs/home_as`, včetně energie;
- `SHA256SUMS`, seznam souborů, stav služby a výpis USB cest.

Kontrola obou archivů přes `sha256sum -c SHA256SUMS` prošla. Senzory a ostatní
hodnoty provozního `app/config.py` odpovídají lokálnímu výchozímu souboru.
Rozdíl proti repozitáři byl v GUI: starší instalace označuje plováky 1/2 jako
poruchy. Aby migrace neměnila toto dosavadní zobrazení, připravená instalace
použije kopii provozního configu doplněnou o `COV_LEVELS_AS_NOTICES = False`.
Toto nastavení mění pouze prezentaci, nikoliv řízení nebo protokol.

## Oddělená instalace a spuštění

### Nutná výjimka ze sondování ModemManager

Při skutečné zkoušce 12. 10. 2026 ModemManager po opětovném připojení
Waveshare otevřel jeho porty a spustil AT/QCDM sondy. To narušilo příjem
Home AS. RX-only konfigurace aplikace neblokuje vysílání jiných procesů.
Před dalším připojením použít přiložené pravidlo
`deploy/78-mm-home-as-waveshare.rules`, omezené na tento konkrétní sériový
identifikátor. Na tomto RPi je již instalované a ověřené pomocí `udevadm test`.
Při nové instalaci po záloze existujících pravidel:

```bash
sudo install -m 0644 deploy/78-mm-home-as-waveshare.rules /etc/udev/rules.d/78-mm-home-as-waveshare.rules
sudo udevadm control --reload-rules
```

Pak při řízené zkoušce odpojit a připojit USB. Ověřit značky
`ID_MM_DEVICE_IGNORE=1` a `ID_MM_PORT_IGNORE=1` ve výpisu `udevadm info`
všech čtyř portů a nepřítomnost nových AT/QCDM sond v journalu ModemManager.
Nezaměňovat ověření pravidel za úspěšnou zkoušku obnovy příjmu.
Pravidlo při běžném návratu k Masteru ponechat: brání nežádoucím sondám
tohoto převodníku. Odstranění při úplné odinstalaci dělat až s odpojeným
Waveshare, následně znovu načíst pravidla. Ostatní pravidla nepřepisovat.
Podklad: [dokumentace ModemManager](https://modemmanager.org/docs/modemmanager/port-and-device-detection/).

Nová verze patří do `/home/milan/home_as_releases/2026-10-12-usb-rs485-rx1`.
Původní `/home/milan/home_as` ani původní ikona se nepřepisují. Balíček se
vytváří lokálně pomocí `python3 deploy/build_release.py`, zahrnuje RPi kód,
testy a dokumentaci, **žádný firmware**. Nové spouštěče nic nespouštějí automaticky.

Při ručním opakování na jiné instalaci nepřepisovat existující adresář release:
nejprve zvolit nový název a odpovídající cesty ikon. Pro tento konkrétní release:

```bash
# Na počítači s repozitářem, nikoliv na provozním RPi:
python3 deploy/build_release.py
scp deploy/output/home-as-usb-rs485-rx1.tar.gz deploy/output/SHA256SUMS milan@192.168.0.98:/home/milan/
```

Na RPi nejdříve ověřit kontrolní součet, vytvořit nový adresář a rozbalit do něj:

```bash
cd /home/milan
sha256sum -c SHA256SUMS
mkdir -p /home/milan/home_as_releases
mkdir /home/milan/home_as_releases/2026-10-12-usb-rs485-rx1
tar -xzf home-as-usb-rs485-rx1.tar.gz -C /home/milan/home_as_releases/2026-10-12-usb-rs485-rx1
cd /home/milan/home_as_releases/2026-10-12-usb-rs485-rx1
sha256sum -c MANIFEST.sha256
cp rpi4/app/config.py rpi4/app/config.py.distributed
cp /home/milan/home_as/rpi4/app/config.py rpi4/app/config.py
printf '\nCOV_LEVELS_AS_NOTICES = False\n' >> rpi4/app/config.py
python3 -m compileall -q rpi4 deploy tests
python3 deploy/check_release.py
```

Po lokální úpravě configu se jeho hash vůči distribučnímu manifestu záměrně
liší. Distribuční verze zůstává v `config.py.distributed`; po dokončení se
uloží zvlášť `INSTALLED.sha256`. Testy používají fake UART a PTY, nikoli
fyzická zařízení. Spouštěč hlídá druhou novou instanci a známý proces původní
aplikace; původní ikona ovšem tento zámek nezná, proto ji nespouštět během zkoušky.

Na grafické ploše RPi budou připravené dvě nové ikony:

1. **Home AS – 1. Určit porty (pouze příjem)** – `launch.py identify`.
2. **Home AS – 2. Příjem (ověřené porty)** – `launch.py receive`.

Obě používají `/usr/bin/python3` a vyžadují `tx_enabled=false` i
`half_duplex_validated=false`; jinou konfiguraci odmítnou. Jejich terminálové
ekvivalenty (spouštějí celou GUI aplikaci, nejsou to sériové testovací skripty):

```bash
/usr/bin/python3 /home/milan/home_as_releases/2026-10-12-usb-rs485-rx1/deploy/launch.py identify
/usr/bin/python3 /home/milan/home_as_releases/2026-10-12-usb-rs485-rx1/deploy/launch.py receive
```

Tyto příkazy jsou určené pro terminál grafické relace RPi. Přes SSH použít
skutečné ověřené DISPLAY/XAUTHORITY relace, nikoliv hádat jejich hodnoty.

## Praktický postup – po jednotlivých krocích

### 1. Nejdříve připravené soubory a záloha

Potvrdit existenci záloh a nové verze, zavřenou původní aplikaci a zachovanou
původní ikonu. Zatím nic nepřepojovat, dokud nejsou soubory připravené.
Případný právě běžící ruční režim bezpečně posoudit místně. Aplikace při
kontrole neběžela, takže nelze předpokládat čerstvé povely ani počítat
40 minut až od budoucího přepojení – limit běží od poslední platné zprávy Slave.

### 2. Fyzicky přepojit

Po oznámení připravenosti uživatel odpojí obě linky od Masteru a připojí:
ČOV na svorky **CH1**, Slave UART0 na **CH2**. Slave–regulátor beze změny.
Dodržet dříve popsanou kontrolu A/B, reference a zakončení; u Pico modulu
není svorková zem podle schématu automaticky stejnosměrná logická zem.
Porty CH3/CH4 zůstanou nezapojené. Dokončení přepojení potvrdit před spuštěním.

### 3. První spuštění pouze s příjmem

Otevřít první novou ikonu. Aplikace načte
`rpi4/config/waveshare-BD63F2ABCD.identify.json` a pasivně otevře **všechna
čtyři** známá USB rozhraní při 9600 8N1. To je dočasná výjimka pouze pro
identifikaci, nikoli provozní využití rezervních kanálů. Nikdy neodesílá
povely, ani při chybném zaplnění fronty; TX nelze v tomto režimu povolit.

Automaticky se otevře okno **Komunikace RS‑485**, dostupné i tlačítkem v
hlavním okně. Ukáže if00/02/04/06, aktuální cestu, počet platných/chybných
rámců, přijaté bajty, stáří každého typu a TX bajty (musí zůstat 0).

- „NEPŘIPOJENO“: USB chybí, není jednoznačné nebo se port nepodařilo otevřít;
- „PORT OTEVŘEN – čekám na platné zprávy“: zařízení existuje, ale nebyla
  přijata rozpoznatelná telemetrie;
- zprávy ČOV / HEAT / PUMP atd. a jejich stáří: skutečný příjem.
- horní lišta stále uvádí **TX VYPNUTO – teploty ani povely se neposílají**.
  Ovládací tlačítka jsou neaktivní, lokální měření a logování pokračují.

Vyčkat přibližně 20–30 s. Rozpoznání vyžaduje alespoň dvě platné zprávy ČOV,
ale zároveň i dvě HEAT a dvě PUMP na jiném rozhraní. HEAT/PUMP musí být při
potvrzení nejvýše 3 s staré, ČOV 30 s. Samotné R1 nestačí. Stejný typ na
více rozhraních, smíšené protokoly na jednom nebo staré údaje blokují potvrzení.
Odpojení portu dosavadní důkazy zneplatní. Neodvozuje se fyzické pořadí portů.

### 4. Potvrdit a uložit skutečné přiřazení

Teprve po ověření kabeláže označit v aplikaci:
**„Potvrzuji: ČOV na CH1, Slave na CH2, Master od obou linek odpojen.“**
Stisknout **„Uložit potvrzené přiřazení (TX zůstane vypnuté)“**.

Aplikace atomicky uloží vedle identifikační konfigurace
`rpi4/config/direct.confirmed.json`. Obsahuje konkrétní naměřené rozhraní pro
obě role, USB identifikátory, čas a způsob potvrzení. Případný starší soubor
nejprve zálohuje. V souboru stále zůstávají oba TX přepínače `false`.
Výsledek ještě není automaticky přepnut do běžného režimu.

Zavřít první aplikaci (Escape) a otevřít druhou novou ikonu. Ta otevře pouze
potvrzené dva porty; ostatní dva zůstanou zavřené. Ověřit příjem, věk dat,
logy a nulový TX. Zavření diagnostiky nezavírá aplikaci – zavřít celé Home AS.

### 5. Vyhodnotit další postup, nezapínat TX pouze kvůli příjmu

Zaznamenat z diagnostiky skutečné přiřazení, dobu zkoušky, chyby a výpadky.
Posoudit samostatně ČOV, HEAT, PUMP, R1, OUT. Funkční příjem potvrzuje jen RX
část. `half_duplex_validated` nadále zůstává false.

Pro obousměrný provoz jsou stále nutné kontroly průběhů a souběhu pravidelné
telemetrie s povely, včetně opožděného R1, USB latence, chyb Modbusu, 1-Wire
konverzí a návratu po odpojení. Existující firmware nemá ACK ani arbitráž;
30–150ms hostovský guard není důkaz nepřítomnosti kolizí. Zkoušku se skutečnými
povely dohodnout zvlášť a bez připojených výkonových spotřebičů. Samotným
přepnutím příznaku se poloduplex neověří.

V celém RX-only režimu Slave nedostává TEMP/PTEMP/HEAT/PUMP z RPi. Jeho
původní 40min limity se nepozastaví ani neobnoví příjmem na RPi. Při blížícím
se limitu / nevyhovujícím chování zkoušku ukončit a vrátit původní hostovskou
komunikaci; nezapínat neověřený TX jen pro udržení ručního režimu.

## Okamžitý návrat

1. Zavřít celou novou aplikaci; nepouštět obě verze souběžně.
2. Odpojit CH1/CH2 a vrátit obě linky na Master podle původní kabeláže.
   Linka Slave–regulátor zůstává nedotčená.
3. Spustit původní ikonu **COV / FVE Dashboard**. Ta stále ukazuje na
   `/home/milan/home_as/rpi4/main.py` a původní sériový režim.
4. Ověřit stav ohřevu/pumpy, teploty, COV_AGE a logování. Nová aplikace není
   v autostartu; starou nefunkční službu kvůli návratu nepouštět.

Pokud by původní soubory byly později změněny, obnovit je až se zastavenou
aplikací z `original-app-and-startup.tar.gz`; před obnovou ověřit SHA256SUMS.
Logy/energii nevracet automaticky do minulosti – jejich archiv je nouzová
záloha, běžný rollback jej nerozbaluje.

## Softwarové ověření

Lokálně kompletní sada 53 testů; kontrola instalačního balíčku `deploy/check_release.py`
obsahuje 38 testů bez závislosti na zdrojích firmwaru. Na RPi nespouštět
úplné discovery nad balíčkem: firmware se záměrně nepřenáší, tyto testy by
skončily chybou chybějících souborů (při prvním pokusu ověřeno).
Sady zahrnují identifikaci čtyř PTY, nesprávného pořadí USB
rozhraní, smíšených/duplicitních zpráv, zastarání, atomického uložení,
zákazu TX a původních ochranných funkcí. Skutečný příjem a přiřazení lze
zaznamenat teprve po fyzickém přepojení; dokud není spuštěna zkouška,
`direct.confirmed.json` záměrně neexistuje.
