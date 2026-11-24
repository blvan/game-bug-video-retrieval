# Prvé vizuálne overenie kandidátov · variant B

**24. november 2026.** Z pilotného súboru 67 dvojíc bolo skontrolovaných 10 dvojíc z dvoch hier. Výber bol zámerný: zahŕňa záznamy z hry, hlásenia o hlavnom menu, prílohy v komentároch aj dve nahrávky toho istého problému. Z takejto vzorky nemožno odhadnúť úspešnosť zberu v celom súbore.

Kontrolu vykonal **Codex** porovnaním pôvodného hlásenia s časovo označenými snímkami dekódovanými z nahrávky. Pri krátkych zmenách boli skontrolované susedné snímky a zväčšený detail. Ide o predbežné posúdenie pomocou AI. Nezávislé ľudské posúdenie zatiaľ chýba.

Skontrolované boli aj licencie zdrojového kódu. Wesnoth je ťahová strategická hra pod GNU GPL v2 alebo novšou. OpenRCT2 je hrateľná implementácia parkového simulátora pod GNU GPL v3 alebo novšou. Do rozsahu bol zaradený jej otvorený kód; hranie vyžaduje aj pôvodné dátové súbory RCT2. [Wesnoth README](https://github.com/wesnoth/wesnoth/blob/master/README.md) · [Wesnoth COPYING](https://github.com/wesnoth/wesnoth/blob/master/COPYING) · [OpenRCT2 README](https://github.com/OpenRCT2/OpenRCT2/blob/develop/readme.md) · [OpenRCT2 licencia](https://github.com/OpenRCT2/OpenRCT2/blob/develop/licence.txt)

| Hlásenie | Rozhodnutie | Pozorovanie v nahrávke (min:sek) |
|---|---|---|
| [Wesnoth #6787](https://github.com/wesnoth/wesnoth/issues/6787) | Vyradené | 0:16–0:19. Po zmene filtra vidno iba jednotlivé riadky zoznamu doplnkov. Ide o hlavné menu. |
| [Wesnoth #6960](https://github.com/wesnoth/wesnoth/issues/6960) | Zaradené · rendering | 0:01.40–0:02.90. Jazdec bliká naľavo, stredové políčko má tieň a stavový ukazovateľ bez jazdca. Neskôr sa tam jazdec zobrazí. |
| [Wesnoth #7163](https://github.com/wesnoth/wesnoth/issues/7163) | Zaradené · rendering | Červená špička palice chýba v 0:03.50, je viditeľná v 0:04.00 a 0:06.25 a po zmene zvýraznenia políčka v 0:06.50 opäť chýba. |
| [Wesnoth #7087](https://github.com/wesnoth/wesnoth/issues/7087) | Vyradené | 0:00–0:07.86. Vidno dialóg načítania hry a náhľad mapy. Záznam nezobrazuje hranie. |
| [Wesnoth #10296](https://github.com/wesnoth/wesnoth/issues/10296) | Neisté | 0:05–0:13.90. Jednotky stoja na mieste. Zo 14,4-sekundového klipu sa nedá rozlíšiť bežné čakanie od hláseného spomalenia ťahu AI. |
| [OpenRCT2 #19152](https://github.com/OpenRCT2/OpenRCT2/issues/19152), klip 234672225 | Zaradené · other_visual | 1:50. Okno stanice uvádza „No entrance“, hoci pri stanici vidno vstupnú budovu. |
| [OpenRCT2 #19152](https://github.com/OpenRCT2/OpenRCT2/issues/19152), klip 234680031 | Zaradené · other_visual | 0:55 vidno vstup a výstup. V 1:02 pokus o test jazdy vyvolá hlásenie „Entrance not yet built“. |
| [OpenRCT2 #19506](https://github.com/OpenRCT2/OpenRCT2/issues/19506) | Zaradené · spatial_collision | 0:06–0:12. Hráč postaví ohradený prístupový chodník krížom cez existujúcu železničnú trať. |
| [OpenRCT2 #20684](https://github.com/OpenRCT2/OpenRCT2/issues/20684) | Zaradené · rendering | 0:04 vidno lavičky a lampy. V 0:07–0:10 postupne miznú pri pohybe náhľadu koľaje nad chodníkom. |
| [OpenRCT2 #22116](https://github.com/OpenRCT2/OpenRCT2/issues/22116) | Neisté | Parser spojil text odkazu s jeho adresou. Aj správna cieľová adresa z hlásenia vrátila HTTP 404. Hlásenie nemalo komentár s náhradným videom. |

**Výsledok.** Deväť záznamov sa podarilo otvoriť. Šesť dvojíc spĺňa kritériá, dve boli vyradené a dve zostali neisté. Šesť nahrávok patrí k piatim rôznym hláseniam. Zvyšných 57 dvojíc v pilotnom súbore čaká na posúdenie.

- **RQ1.** Pre Wesnoth sú k dispozícii dve relevantné nahrávky k dvom hláseniam, pre OpenRCT2 štyri nahrávky k trom hláseniam. Pri #19152 treba uznať obe nahrávky ako relevantné. V takýchto malých skupinách by Recall@5 vždy dosiahol 1.
- **RQ2.** V lokálnom súbore `data/review/rq2-batch-01.json` je pre každé z piatich hlásení názov, názov s očisteným opisom a názov s dostupnými štruktúrovanými časťami. Text pochádza iba z pôvodného hlásenia. Odkazy na prílohy, bloky diagnostiky a prázdne odpovede boli odstránené. Chýbajúce časti neboli dopĺňané z videa.
- **RQ3.** Podľa jedinečných hlásení sú tri prípady v kategórii `rendering`, jeden v `spatial_collision` a jeden v `other_visual`. V ďalšej dávke treba vyhľadať aj príklady pre `camera` a `animation`. Ide o výsledok anotácie pred experimentom s CLIP.

Následné vyhľadávanie v oboch repozitároch použilo dotazy `camera in:title` a `animation in:title`, najviac osem hlásení na hru a dotaz. Prvý beh spracoval 11 hlásení a našiel jednu kandidátsku dvojicu, druhý spracoval 16 hlásení a našiel päť. Všetkých šesť dvojíc bolo nových a pribudli do Excelu bez rozhodnutia o zaradení. Excel teraz obsahuje 73 dvojíc, z ktorých 63 čaká na prvú kontrolu. Príklady pre ďalšie posúdenie: [Wesnoth #11555](https://github.com/wesnoth/wesnoth/issues/11555) a [OpenRCT2 #22856](https://github.com/OpenRCT2/OpenRCT2/issues/22856). V druhom prípade treba pri sledovaní rozlíšiť chybu kamery od chyby vykresľovania závislej od uhla pohľadu.
