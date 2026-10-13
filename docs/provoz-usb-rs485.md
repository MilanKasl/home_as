# Provozní režim USB–RS-485

Na výslovný pokyn provozovatele z 12. 10. 2026 je připraven obousměrný
režim bez návratu k Masteru a bez měření analyzátorem. Jde o provozovatelem
povolený provoz se stávajícím firmwarem, nikoliv potvrzení bezkolizního
poloduplexu. `half_duplex_validated` zůstává **false**.

Provozní konfigurace `direct.operational.json` vzniká z uloženého fyzického
přiřazení ČOV/CH1/if00 a Slave/CH2/if02, serial BD63F2ABCD. Obsahuje
`tx_enabled=true`, `allow_unvalidated_half_duplex=true` a záznam
`operational_authorization`. Dodatečné povolení je výslovná změna předchozí
politiky vyžadující ověření; není technickým řešením arbitráže. Bez něj
zůstává původní blokace neověřeného TX zachována. Identifikační režim nikdy
nevysílá. Přijímací konfigurace se nemění.

Aplikace ověřuje soulad zaznamenaného přiřazení s identitami a před otevřením
portů v tomto režimu také přítomnost obou modemových výjimek v udev.
Chybějící výjimka, nejednoznačná identita či změna identifikátoru otevření
zablokuje. USB porty se nevybírají podle čísel ttyACM.

ČOV zůstává pouze přijímací. Slave dostává původní TEMP/PTEMP a požadované
HEAT/PUMP. Odesílání vyžaduje čerstvé HEAT i PUMP, kompletní rámce a dosavadní
klidové okno po HEAT. Tyto podmínky **nezaručují nepřítomnost kolizí**;
bez změny firmware/protokolu ji host nedokáže zajistit. Automatické řízení
směru tento problém neřeší. Neobnovuje se stará fronta povelů, jednotlivé
údaje stárnou samostatně. Obnova spojení nyní reaguje i na 30 s bez platného
rámce při pokračujícím příjmu nečitelných bajtů.

Povel odeslaný do ovladače není potvrzené sepnutí. HEAT/PUMP lze porovnat
s následným stavem MODE/ACTIVE/REASON; nejde o ACK konkrétního povelu.
TEMP/PTEMP nemají ACK ani echo přijaté hodnoty. Z jejich odeslání se tedy
nesmí odvozovat potvrzené doručení. Po startu GUI používá dosavadní výchozí
režimy AUTO. Nepřidává se testovací sepnutí ani změna ochran koncových zařízení.

## Spuštění na tomto RPi

Nová oddělená verze:
`/home/milan/home_as_releases/2026-10-12-usb-rs485-tx1`.
Před spuštěním řádně zavřít celé běžící Home AS klávesou Escape v hlavním
okně. Otevřít ikonu **Home AS – 3. Provoz USB–RS485**. Spouštěč
`deploy/launch.py operate` vyžaduje provozní konfiguraci a brání souběhu
s jinou instancí. Autostart není přidán; po restartu RPi je nutné aplikaci
spustit touto ikonou. V horní liště bude TX POVOLENO · poloduplex bez měření.

Po spuštění zkontrolovat příjem obou linek, skutečné stavy, logování,
zápisy TX a stáří HEAT/PUMP. Neoznačit TX jako potvrzený fyzický účinek.
Výkonové spotřebiče byly při přípravě podle uživatele odpojené; jejich
fyzické připojení aplikace neprovádí ani nezjišťuje.

## Vypnutí TX bez návratu k Masteru

Zavřít celou aplikaci a spustit `deploy/launch.py receive` (druhá ikona).
Ta stále používá zachovanou `direct.confirmed.json` s oběma příznaky false.
Slave potom nedostává teploty ani povely a běží jeho původní časové limity.
Modemovou výjimku ponechat nainstalovanou i při vypnutém TX aplikace.

## Stav ověření

Příjem obou fyzických linek a druhá obnova celého USB po vyloučení
ModemManager prošly. Uživatel potvrdil reakci GUI. Výpadek jednotlivé
větve nebyl fyzicky zkoušen kvůli společnému konektoru; pokrývají jej
simulované testy. Poloduplex není změřený a funkčnost fyzického obousměrného
provozu lze zaznamenat až po spuštění této verze. Firmware Uno, Pico Slave
a Pico Masteru zůstává beze změn. Lokální sada po úpravách: 58 testů OK.
