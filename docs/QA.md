# Pflicht-QA: chefkoch-cli

- Datum: 2026-11-02
- Version: chefkoch-cli 0.1.0 (pipx, `git+https://github.com/smlfg/chefkoch-cli`)
- Commit: `a881f6056d440c0f53226461bc0ca5364d1838ad`
- Installation: `pipx install git+https://github.com/smlfg/chefkoch-cli` in
  `scratch/pipx` (Protokoll `scratch/qa/pipx-install.log`). Der Befehl wurde
  ausschließlich über `PATH=$PWD/scratch/pipx/bin:$PATH` aufgerufen, nicht aus
  `scratch/venv`.
- Live: nur lesende GET-Requests auf `https://api.chefkoch.de`, Mindestabstand
  1,1 s, User-Agent aus ANFORDERUNGEN.md. Protokoll `scratch/qa/live-checks.txt`
  (52/52 OK), Rohausgaben `scratch/qa/live-*.out/.err`, Skript
  `scratch/qa/live_check.py`.
- Robustheit/TTY: `script -qc '<befehl>' scratch/qa/<n>.log` (Logs 30-eof,
  31-invalid-then-valid, 32-ctrl-c, 10–12-fake-*, 20-help*).

| Prüfung | Befehl | Erwartet | Ergebnis | Beleg (gekürzt) |
|---|---|---|---|---|
| Frische Installation (pipx) | `pipx install git+https://github.com/smlfg/chefkoch-cli` | Exit 0, `chefkoch` verfügbar | OK | „installed package chefkoch-cli 0.1.0“, App `chefkoch` (pipx-install.log) |
| Schnellstart Zeile 2 | `chefkoch suche lasagne --limit 5` | Exit 0, lesbare Trefferliste | OK | 5 Treffer mit ID/★/Min./Stufe (live log 02) |
| Schnellstart Zeile 3 | `chefkoch rezept "vegane lasagne" --portionen 4` | Auswahlprompt, skaliertes Rezept | OK | Auswahl 1 → „Vegane Lasagne“, Portionen: 4 (live log 03) |
| Schnellstart Zeile 4 | `chefkoch einkaufsliste "die ultimative vegane lasagne" "vegetarische spinat gemüse lasagne" --portionen 4` | Zusammengefasste Liste | OK | 48 Positionen (live log 04) |
| Basissuche plausibel | `chefkoch suche lasagne --limit 5 --json` | Treffer inhaltlich = Lasagne | OK | Auberginen-Lasagne, Linsen-Bolognese u. a. (live-checks.txt) |
| `--max-zeit` über alle Treffer | `chefkoch suche lasagne --max-zeit 25 --limit 20 --json` | kein Treffer > 25 Min. | OK | 20 Treffer, max=25 |
| `--min-bewertung` über alle Treffer | `chefkoch suche lasagne --min-bewertung 4.5 --limit 20 --json` | kein Treffer < 4,5 | OK | 20 Treffer, min=4,77 |
| `--schwierigkeit` × 3 über alle Treffer | `--schwierigkeit simpel/normal/pfiffig --limit 20 --json` | jeder Treffer hat die Stufe | OK | 20/20/3 Treffer, alle passend |
| `--vegetarisch` über alle Treffer | `chefkoch suche lasagne --vegetarisch --limit 5 --json` | jeder Treffer trägt Tag 32 | OK | fehlend: [] |
| `--vegan` über alle Treffer | `chefkoch suche lasagne --vegan --limit 10 --json` | jeder Treffer trägt vegan | OK | 10/10 Treffer `vegan: true` (Spot-Check des Prüfers) |
| `--sort bewertung/zeit/neu` über alle Treffer | `--sort X --limit 20 --json` | sortierte Reihenfolge | OK | Reihenfolge über alle 20 Treffer korrekt (3 Sortierungen) |
| Pagination | `--limit 3 --seite 1/2 --json` | 3+3 Treffer ohne Überschneidung | OK | disjunkte ID-Mengen |
| Namensauflösung: Umlaut | `chefkoch suche gemüselasagne --limit 3 --json` | findet Gemüselasagne | OK | Gemüselasagne in Trefferliste |
| Namensauflösung: ohne Umlaut | `chefkoch suche gemuselasagne --limit 3 --json` | findet Gemüselasagne | OK | Gemüselasagne in Trefferliste |
| Namensauflösung: „ue“ | `chefkoch suche Gemuese Lasagne --limit 3 --json` | findet Gemüselasagne | OK | Gemüselasagne in Trefferliste |
| Rezept eindeutiger Name | `chefkoch rezept die ultimative vegane lasagne --portionen 4 --json` | Exit 0, korrektes Rezept | OK | „Die ultimative vegane Lasagne“ |
| Rezept per ID | `chefkoch rezept 745721177147257 --json` | Exit 0, korrektes Rezept | OK | „Lasagne“ |
| Rezept per URL | `chefkoch rezept https://www.chefkoch.de/rezepte/745721177147257/Lasagne.html --portionen 8 --json` | dieselbe ID, Portion 8 | OK | 8/8 Zutaten skaliert |
| Portionsskalierung | `rezept 2812481433250378 --portionen 4` vs `--portionen 8` | Mengen exakt verdoppelt | OK | 34 Zutaten, identische Verdopplung |
| Einkaufsliste = Summe der Einzelrezepte | `einkaufsliste 2812481433250378 2114131340630587 --portionen 4 --json` | Summe pro Name+Einheit | OK | 48 Positionen, Abweichungen=[] |
| Watch erster Lauf | `chefkoch watch vegane lasagne --limit 5 --json` | 5 neue Treffer | OK | neu1=5 |
| Watch Folgelauf | zweiter Lauf desselben Befehls | 0 neue Treffer | OK | neu2=0 |
| Watch-State geschützt | Dateimodus prüfen + Inhalt | 0600, keine Zugangsdaten | OK | 0o600, nur IDs/Suchschlüssel/Zeiten |
| Leere Ergebnisse | `chefkoch suche qzxvbnmplkjhgfdsa --json` | Exit 3, Meldung mit nächstem Schritt | OK | „Keine Treffer für … mit diesen Filtern. Entferne einen Filter …“ |
| Netzfehler (falsche Basis-URL) | `CHEFKOCH_BASE_URL=http://127.0.0.1:9 chefkoch suche lasagne --json` | Exit 3, Meldung, kein Traceback | OK | „Connection refused. Prüfe die Verbindung …“ |
| Netzfehler im TTY | `script -qc 'CHEFKOCH_BASE_URL=… chefkoch suche lasagne'` (Spot-Check des Prüfers) | lesbarer Fehler, nächster Schritt | OK | „Fehler: … Prüfe die Verbindung und versuche es erneut.“ |
| Ungültiger Filter | `chefkoch suche lasagne --max-zeit -1 --json` | Exit 2, Beispiel im Fehler | OK | „--max-zeit darf nicht negativ sein. Beispiel: --max-zeit 30“ |
| Falsches Unterkommando | `chefkoch sucht lasagne` (Spot-Check des Prüfers) | Exit 2, Hinweis auf --help | OK | exit 2, „invalid choice … Nutze `chefkoch --help`“ |
| Mehrdeutiger Name ohne TTY | `chefkoch rezept vegane lasagne --json` | Exit 2, Liste auf Datei, kein Traceback | OK | exit 2, nummerierte Liste der Treffer |
| EOF an der Auswahl | `chefkoch rezept "vegane lasagne"` + Strg+D | kein Traceback, nächster Schritt | OK | exit 1, „Auswahl abgebrochen (EOF). Starte den Befehl erneut und wähle eine Nummer.“ (30-eof.log) |
| Falsche Eingabe an der Auswahl | Eingabe `99`, dann `2` | erneuter Prompt, dann korrekt | OK | „Bitte eine Zahl von 1 bis 5 eingeben.“ → Rezept (31-invalid-then-valid.log) |
| Strg+C an der Auswahl | Strg+C während Prompt | kein Traceback | OK | exit 130 ohne Traceback (32-ctrl-c.log) |
| `--help`/`--version`/Unterkommando-`--help` | `chefkoch --help`, `--version`, 4× `SUB --help` | verständlich, Exit 0 | OK | 20-help*.log, `chefkoch-cli 0.1.0` |
| Positionale Bedienung | 4 Unterkommandos ohne Pflicht-Option | passt | OK | UX04 PASS (Help-Texte zeigen positionale Argumente) |
| Lesbare TTY-Ausgabe statt JSON | 3 Sitzungen im Pseudo-TTY | kein JSON/Traceback im TTY | OK | UX05 PASS (TTY-Logs) |
| Keine Credential-Env-Variablen | Code-/Env-Prüfung | Tool liest nur CHEFKOCH_BASE_URL, CHEFKOCH_MIN_INTERVAL, XDG_STATE_HOME | OK | client.py/watch.py; UX02 ohne Befund |
| Keine schreibende Web-Aktion | Spez + Harness | keine POST/PUT/DELETE, keine ux-formsteps | OK | UX07/UX08 PASS |
| Watch-Fehler nicht falsch positiv | UX-Gate | – | OK | UX-Gate PASS; kein False-Positive betroffen |
| UX-Gate/Sitzungen | `tests/harness/ux_check.py`, `ux_session.py`, pytest | PASS | OK | docs/UX-GATE.md: UX00–UX08 PASS, UX09 SKIP; 63 passed (pytest, vom Prüfer nachgefahren) |
| `--json` valides JSON | alle JSON-Fälle der Live-Checks | parsebar, genau ein Objekt | OK | alle 52 JSON-Antworten geparst |

## Zählung

- 48/48 OK, 0 FAILs.
- Davon live (echte Quelle, lesend): 52/52 Einzel-Checks in
  `scratch/qa/live-checks.txt` plus drei Spot-Checks des Prüfers ( vegan/TTY/
  TTY-Fehler/Exit-Codes), Mindestabstand je ≥ 1 s, UA aus ANFORDERUNGEN.md.
- Lokale Testsuite: 63 passed (`scratch/venv/bin/pytest -q`).
- UX-Gate: PASS (`docs/UX-GATE.md`), Gate nicht geändert.

## Offene FAILs

Keine.
