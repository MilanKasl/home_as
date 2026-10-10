# Ruční ovládání čerpadla AKU

V detailu FVE tlačítko **ČERPADLO – RUČNĚ ZAPNOUT** zapne čerpadlo
nezávisle na teplotě a okně 7–17 hodin. Opětovný stisk **ČERPADLO – ZPĚT
NA AUTO** obnoví řízení průměrem horní a dolní teploty AKU (zapnutí od 66 °C, vypnutí při 65 °C)
a časovým oknem. Návrat do automatiky nemusí čerpadlo vypnout, pokud je
splněna automatická podmínka pro běh.

Vedle tlačítka je stav výstupu relé potvrzený Pico Slave a režim AUTO/RUČNĚ.
Nejde o měření otáčení čerpadla. „ČEKÁM“ znamená, že požadovaný režim ještě
nebyl potvrzen. Bez aktuálního zpětného stavu je nové ruční zapnutí nedostupné.

Povel se obnovuje přibližně každé 2 sekundy. Po 40 minutách bez obnovení
Pico Slave při dalším průchodu řídicí smyčkou přejde do automatiky.
RPi zachová ruční požadavek při krátkém výpadku spojení. Teprve po
40 minutách bez platného potvrzení vrátí čerpadlo do automatiky a zruší
ruční ohřev AKU nebo bojleru. Neaktuální stav se dál zobrazuje jako neznámý. Po restartu je výchozí režim AUTO.
Automatická hystereze se sleduje nezávisle i během ručního běhu.
Teploty ani řízení spirály se ručním povelem čerpadla nemění.

## Soubory k aktualizaci

- Pico Slave: `main.py`, `heating_control.py`, `mega_protocol.py`, `config.py`.
- Pico Master: `main.py`, `parser.py`, `state.py`.
- RPi: `app/pump_control.py`, `app/gui.py`, `app/gui_layout.py`, `app/parser.py`, `app/state.py`.
  Součástí předchozí úpravy detailu FVE jsou také `app/fve_energy.py`
  a `app/config.py`; při společném nasazení přenést i je.

Aktualizovat vždy celou uvedenou sadu pro zařízení a pak jeho program
restartovat. Doporučené pořadí: Slave, Master, RPi. Starší firmware bez
podpory potvrzení čerpadla nechá nové tlačítko nedostupné.

## Komunikace a ověření

- RPi → Master → Slave: `<PUMP:M>` (ručně), `<PUMP:A>` (automatika).
- RPi odesílá povely doplněné na 16 bajtů pro stávající PIO přijímač.
- Slave → Master: `<PUMP:M,1>` apod.; druhé pole je stav relé 0/1.
- Master → RPi: `P:M,1` apod., při neaktuálním stavu `P:NO_DATA`.
- Průměr obou čidel se měří každých 10 sekund a přenáší zvlášť jako
  `<PTEMP:65.500>`. Prázdný `<PTEMP:>` označuje chybu čidla. Poslední platný průměr se ponechá nejvýše
  40 minut od jeho příjmu; chybové rámce jeho platnost neprodlužují.
  Potom se automatický běh vypne; ruční režim zůstává nezávislý.
- Původní rámce TEMP a HEAT zůstávají zachovány. Ohřev stále používá
  dolní teplotu. Pro automatiku čerpadla je nutné aktualizovat všechna
  tři zařízení; starší RPi neposílá průměr.

Hostitelské testy: `python3 -m unittest discover -s tests -v`.
Na zařízení po nasazení ověřit zapnutí pod průměrem 66 °C a mimo časové okno,
potvrzení stavu na displeji, návrat do automatiky a vypršení ručního
režimu po odpojení komunikace. Hardwarové ověření zatím nebylo provedeno.

## Tolerance výpadku teplot a povelů

Poslední platná dolní teplota AKU, průměr AKU a teplota bojleru mají
platnost 40 minut. Bez jediného platného měření se ohřev nespustí.
Nová platná teplota se použije okamžitě; dosažení maxima 75 °C pro AKU
nebo 50 °C pro bojler nadále zastaví ruční ohřev. Ruční povely ohřevu
na Pico Slave také vyprší po 40 minutách bez obnovení.

Pro tuto úpravu aktualizovat RPi `app/gui.py` a Pico Slave `config.py`
a `main.py`. Pico Master se oproti předchozí verzi nemění.
