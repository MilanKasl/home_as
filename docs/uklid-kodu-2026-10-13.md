# Konzervativní úklid aplikace RPi – 13. 10. 2026

Proveden schválený první úklid místního projektu. Změny nejsou nasazené na
RPi. Firmware Una, Pico Slave a Pico Masteru ani provozní konfigurace na RPi
nebyly upraveny. Běžící aplikace nebyla zastavena ani restartována.

## Rozsah a důvody

| Soubor v `rpi4/app/` | Změna | Důvod |
| --- | --- | --- |
| `gui_layout.py` | Odstraněno 10 metod starého rozložení a nepoužívané `self.indicators`. | Staré levé/pravé panely tvořily uzavřenou skupinu bez volání z používaných obrazovek; další tři pomocné metody nebyly volané. |
| `gui.py` | Odstraněno 6 nevolaných metod, `DEBUG`, `self.indicators` a `self.link_dead_since`. | Pozůstatky starých panelů a neaktivní obsluhy ztráty dat. Aktivní watchdog v `poll_gui` a hlášení v `update_system_status` zůstaly. |
| `config.py` | Odstraněny `SCREEN_WIDTH`, `SCREEN_HEIGHT`, `BG_COLOR`, `FG_COLOR`. | Nikde nebyly čtené; skutečné rozměry a barvy určuje používané rozložení. |
| `gui_style.py` | Odstraněny `ORANGE`, `BLUE`, `BG_ROW_1`, `BG_ROW_2`, `FONT_BIG`. | Nepoužívané konstanty, včetně kontroly modulů s hvězdičkovým importem. |
| `identify_link.py` | Odstraněna nepoužívaná místní proměnná `ages`. | Skutečné kontroly stáří dál čtou `snap['ages']` na původních místech. |
| `reg_logger.py`, `state.py` | Opraveny dva zastaralé komentáře. | Popis logování nyní odpovídá existujícím 5 minutám; chyby čerpadel nejsou placeholdery. |

Odstraněné metody rozložení:
`create_left_panel`, `create_section_label`, `create_status_row`,
`create_temp_row`, `create_right_panel`, `create_regulator_block`,
`create_value_row`, `_cov_history_inline`, `_main_cov_content_row`, `_fve_value`.

Odstraněné metody GUI:
`update_left_panel`, `update_right_panel`, `set_indicator`,
`check_data_timeout`, `set_no_data_state`, `restore_data_state`.

Samotný úklid mění 7 zdrojových souborů: 367 odstraněných a 3 přidané řádky
(včetně komentářů a prázdných řádků). Tento dokument je navíc.
Rozdíl je počítán vůči záloze bezprostředně před úklidem, nikoliv vůči Git
HEAD, protože projekt již obsahoval změny z migrace.

## Záměrně zachované části

Komunikace a její časování, stáří jednotlivých údajů, řízení výstupů,
ochrany, automatická obnova, provozní logování i servisní diagnostika
zůstaly. Zachována je také cache `_last_values` používaná metodou `set_value`
a aktuální indikátory ČOV `cov_indicators`.

Ponechány byly všechny testy, simulace bez skutečného hardwaru, identifikace
USB, původní komunikační režim, příklady konfigurací, závislosti a historické
zálohy. Nejde o prokázaně nepotřebné části. Do firmwaru se nezasahovalo.

## Záloha a ověření

Místní záloha před úklidem:
`deploy/output/cleanup-baseline-20261013-095729/source.tar.gz`.
Obsahuje 57 souborů, včetně dosavadních nesledovaných zdrojových souborů.
Neobsahuje Git databázi, provozní logy, cache ani dřívější sestavené balíčky.
Každý soubor archivu byl porovnán s uloženým SHA-256 v `SHA256SUMS`.
Vedle archivu jsou `git-status.txt`, `preexisting-changes.patch` a samostatný
rozdíl tohoto úklidu `cleanup.patch`. Záloha je místní a není verzovaná v Gitu.

- `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v`:
  **62 testů prošlo**, včetně PTY simulací, obnovy linek/čidel, směrování,
  stáří dat, blokování vysílání a ochran Uno/Slave. Bez skutečných zařízení.
- V paměti byla ověřena syntaxe všech 43 Python zdrojů.
- Porovnání syntaktických stromů potvrdilo pouze uvedené odstranění a
  opravu komentáře/docstringu. Zbývající logika je shodná s výchozí verzí.
- Ve skrytých místních oknech skutečného Tk byly porovnány hlavní obrazovka,
  ČOV a FVE: shodný strom prvků, jejich nastavení, obsah canvasů, datové
  klíče i přepínání pohledů. Test spustil pouze rozložení, nikoliv IO aplikace.
  Nešlo o vizuální kontrolu na displeji RPi.
- Ostatní soubory ze zálohy, včetně všech zdrojů firmwaru, zůstaly bajtově
  shodné. `git diff --check` prošel.

## Provozní instalace a další nasazení

Přes SSH byla pouze čtením ověřena instalace
`/home/milan/home_as_releases/2026-10-12-usb-rs485-tx1`.
Všech 41 položek jejího `OPERATIONAL.sha256` prošlo kontrolou.
Zdrojové soubory aplikace před úklidem odpovídaly provozní instalaci kromě
záměrně odlišného konfiguračního profilu.

**Při případném nasazení nepřepsat provozní konfiguraci distribučním
příkladem.** RPi používá `COV_LEVELS_AS_NOTICES=False`, zatímco místní
projekt má `True`. RPi má také vlastní `direct.confirmed.json` a
`direct.operational.json`, které nejsou součástí místní konfigurace.
Je nutné zachovat jejich obsah, USB přiřazení a provozní přepínače.

Riziko omezeného úklidu je nízké podle kontroly volání, shody používané
logiky a testů; tato změna ale dosud nebyla ověřena během ostrého běhu na
RPi. Další nasazení vyžaduje samostatný pokyn, novou zálohu aktuální
provozní instalace a konfigurací a zachování předchozí funkční verze pro
návrat. Původní provozní instalace zůstává nyní nedotčená.
