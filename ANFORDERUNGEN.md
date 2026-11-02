# chefkoch-cli — Anforderungen

Stand: 2026-11-02. Grundlage sind die Live-Erkundung vom 2026-10-30/11-02,
`docs/UX.md` und die Fixtures unter `tests/fixtures/`. Alle Live-Aufrufe waren
lesende GET-Requests mit dem User-Agent
`chefkoch-cli/0.1 (+https://github.com/smlfg/chefkoch-cli)` und mindestens einer
Sekunde Abstand.

## 1. Zweck

`chefkoch` bringt Chefkoch.de-Rezepte ins Terminal:

- Rezepte nach Namen suchen und filtern
- Rezeptdetails mit auf Portionen skalierten Zutaten anzeigen
- aus mehreren Rezepten eine Einkaufsliste erzeugen
- neue Treffer zu einem Suchbegriff beobachten

Das Tool ist ausschließlich lesend. Es gibt keinen Login, keine Accounts, keine
Cookies und keine schreibenden Web-Aktionen. Laufzeit: Python >= 3.10,
`httpx` (MIT), optional `beautifulsoup4` wird nicht benötigt.

## 2. Nachfrage

Quelle: `./scratch/ref/NEXT20.md` bzw. `LOG 30.10.2026` (Nachfrage-Check vom
30.10.2026, GitHub/Glama/mcp.so, Web/Reddit).

Ergebnis: **GO**. Es gibt kein dediziertes CLI und keinen MCP-Server
(GitHub/Glama/mcp.so: 0 Treffer). Dazu kamen 6 offene Import-Issues von
Juli–Oktober 2026 sowie zwei Reddit-Threads mit Resonanz
(r/selfhosted 10↑/9c, r/de 22↑/43c). Der Bedarf ist damit belegt; Details und
Belege stehen in der genannten Quelle.

## 3. Nutzer-Aufgaben

Die drei wichtigsten Aufgaben sind in `docs/UX.md` als wörtlich abtippbare
Terminal-Sitzungen festgehalten:

1. **Installation und erste Suche:** `pipx install …`, danach
   `chefkoch suche lasagne --limit 5` und eine lesbare Trefferliste.
2. **Rezept per Name:** `chefkoch rezept "vegane lasagne" --portionen 4`.
   Bei mehreren Treffern erscheint im TTY eine nummerierte Auswahl; danach
   werden die Zutaten auf die gewünschten Portionen skaliert.
3. **Einkaufsliste per Name:** `chefkoch einkaufsliste "die ultimative vegane
   lasagne" "vegetarische spinat gemüse lasagne" --portionen 4`. Mehrdeutige
   Namen werden im TTY ausgewählt, gleiche Zutaten zusammengefasst.

IDs und Chefkoch-URLs bleiben als Eingabe möglich, sind aber nicht der
Normalfall für Menschen.

## 4. Datenquelle

Basis: `https://api.chefkoch.de`, überschreibbar über
`CHEFKOCH_BASE_URL` (für Tests und Fake-Server). Verwendet werden
ausschließlich:

- `GET /v2/recipes` (Suche)
- `GET /v2/recipes/<id>` (Details)

### 4.1 Robots und Grenzen der Quelle

Live geprüft am 2026-11-02:

- `https://api.chefkoch.de/robots.txt` erlaubt `/v2/recipes` und
  `/v2/recipes/<id>`.
- Gesperrt sind `/v2/search/suggestions/` sowie zwei Kommentar-Endpunkte;
  diese werden nicht abgerufen.
- `https://www.chefkoch.de/robots.txt` sperrt `/rezepte/*?*`. Rezept-URLs
  werden daher nur lokal geparst; die URL selbst wird nie geladen. Details
  kommen ausschließlich über `/v2/recipes/<id>`.

Jeder Prozess hält standardmäßig mindestens 1 Sekunde Abstand zwischen zwei
HTTP-Requests. Für Tests gegen den Fake-Server ist der Abstand über
`CHEFKOCH_MIN_INTERVAL=0` abschaltbar. Es gibt keine automatischen Retries.

### 4.2 Suchantwort

`GET /v2/recipes?query=lasagne&limit=5` liefert HTTP 200 mit `count` und
`results[]`; je Treffer steht das Rezept unter `results[].recipe` mit `id`,
`title`, `subtitle`, `createdAt`, `difficulty`, `preparationTime`, `rating`
(`rating`, `numVotes`), `siteUrl`, `slug` und `hasImage`.

Live belegte Parameter:

- `limit`, `offset` wirken.
- `minimumRating` und `maximumTime` wirken; `maximumTime` bezieht sich auf
  `preparationTime`, nicht auf `totalTime`.
- `tags` wirkt nur numerisch (`32` = Vegetarisch, `57` = Vegan).
- `sort`, `order`, `sortBy` und `difficulty` werden ignoriert; `orderBy` führt
  zu HTTP 400. Sortierung und Schwierigkeitsfilter macht die CLI clientseitig.
- Die Suchantwort enthält keine Tags. Für `--vegetarisch`/`--vegan` werden
  Details nachgeladen und gegen `fullTags` geprüft (Tag 57 impliziert 32).

### 4.3 Detailantwort

`GET /v2/recipes/<id>` liefert u. a. `id`, `title`, `subtitle`, `slug`,
`siteUrl`, `servings`, `difficulty` (1 = simpel, 2 = normal, 3 = pfiffig),
`preparationTime`, `cookingTime`, `restingTime`, `totalTime`, `rating`,
`instructions`, `tags`, `fullTags`, `categoryBreadcrumb` und
`ingredientGroups[]` mit `header` und `ingredients[]`
(`name`, `amount`, `unit`, `unitId`, `isBasic`). `amount` und `unit` dürfen
fehlen; fehlende Werte gelten als `0` bzw. leerer String.

Ein unbekanntes Rezept liefert HTTP 404 mit
`{"notification":{"hasErrors":true,...}}` und wird als „nicht gefunden“
behandelt.

### 4.4 Rezept-ID und URL

Akzeptiert werden eine rein numerische ID oder eine URL der Form
`https://www.chefkoch.de/rezepte/<id>/<slug>.html`. Aus der URL wird nur die
ID gelesen. Fremde Hosts, andere Pfade und nicht-numerische IDs sind
Eingabefehler.

## 5. Funktionale Anforderungen

### 5.1 `chefkoch suche`

`chefkoch suche BEGRIFF [--vegetarisch|--vegan] [--max-zeit N]
[--min-bewertung X] [--schwierigkeit simpel|normal|pfiffig]
[--sort bewertung|zeit|neu] [--limit N] [--seite N]`

- Der Suchbegriff steht positional; `--limit` ist optional (Default 10).
- Jeder Filter wird zusätzlich clientseitig gegen jeden gelieferten Treffer
  erzwungen, auch wenn die API den Filter schon anwendet.
- Standardsortierung ist Bewertung absteigend (Tiebreak `numVotes`, dann
  Titel). `zeit` sortiert `preparationTime` aufsteigend, `neu` `createdAt`
  absteigend.
- Da die API nicht sortiert, wird ein Fenster von maximal 500 Treffern
  geladen, clientseitig gefiltert/sortiert und daraus die Seite geschnitten.
- Keine Treffer nach allen Filtern ist ein Fehler (`no_results`).

### 5.2 `chefkoch rezept`

`chefkoch rezept NAME|ID|URL [--portionen N]`

- Name: Suchanfrage über die API. Genau ein Treffer wird direkt geöffnet.
  Mehrere Treffer ergeben im TTY eine nummerierte Auswahl; ohne TTY wird die
  Liste ausgegeben und der Befehl endet mit Usage-Fehler (Exit 2).
- ID/URL: direkter Detailabruf ohne Suche.
- `--portionen` skaliert alle Zutaten mit `portionen / servings`; Default ist
  `servings` des Rezepts. Mengen werden auf zwei Nachkommastellen gerundet und
  mit Komma ausgegeben.
- Im TTY erscheinen Titel, Portionen, Zutaten und Zubereitung lesbar; mit
  `--json` oder ohne TTY kommt das normalisierte Rezeptobjekt.

### 5.3 `chefkoch einkaufsliste`

`chefkoch einkaufsliste NAME|ID|URL... [--portionen N]`

- Mindestens eine Angabe. Namen werden wie bei `rezept` aufgelöst; bei
  mehreren Treffern wird pro Name im TTY ausgewählt, ohne TTY endet der
  Befehl mit Exit 2.
- `--portionen` gilt für jedes Rezept. Ohne Angabe bleibt jedes Rezept bei
  seinen eigenen `servings`.
- Zutaten werden pro Rezept skaliert und danach über normalisierte
  Name+Einheit-Paare summiert (Unicode NFC, getrimmt, interne Whitespaces
  vereinfacht, `casefold()`). Unterschiedliche Einheiten bleiben getrennt;
  es gibt keine Synonym- oder Plural-Zusammenführung.
- Ausgabe nach Name, dann Einheit sortiert. Beträge werden erst nach der Summe
  gerundet.

### 5.4 `chefkoch watch`

`chefkoch watch BEGRIFF [--vegetarisch|--vegan] [--max-zeit N]
[--min-bewertung X] [--schwierigkeit ...] [--limit N]`

- Nutzt dieselben Filter wie `suche`, aber ohne `--sort` und `--seite`.
- Der State liegt unter `$XDG_STATE_HOME/chefkoch-cli/watch.json`, sonst unter
  `~/.local/state/chefkoch-cli/watch.json`. Verzeichnis `0700`, Datei `0600`,
  atomares Schreiben.
- Erster Lauf für einen Suchschlüssel: alle aktuellen Treffer sind neu
  (`changed=true`). Folgelauf: `new` sind die aktuellen IDs minus die zuletzt
  gespeicherten IDs; ohne neue Treffer ist `changed=false`.
- Keine Treffer ist ein Fehler (`no_results`), der State bleibt unverändert.
- Kaputter State ergibt einen Fehler ohne Traceback und ohne Überschreiben.

### 5.5 Hilfe und Version

`chefkoch --help`, `chefkoch --version` und `chefkoch <unterbefehl> --help`
beenden mit Exit 0. `--version` gibt `chefkoch-cli <version>` aus.

## 6. Ausgabe und Exit-Codes

- Im TTY ist die Ausgabe lesbar (Tabelle/Zeilen). JSON erscheint nur mit
  `--json` oder wenn stdout kein TTY ist.
- Im JSON-Modus steht genau ein Objekt auf stdout, auch bei Fehlern:
  `{"ok": true, "command": "...", "data": {...}}` bzw.
  `{"ok": false, "error": {"type": "...", "message": "..."}}`.
- Fehler nennen den nächsten Schritt; niemals Tracebacks, auch nicht bei
  Strg+C oder EOF.

| Exit | Bedeutung |
|---|---|
| 0 | Erfolg, inklusive `--help` und `--version` |
| 1 | Allgemeiner Fehler: kaputter Watch-State, Konfigurations-/IO-Fehler, unerwarteter interner Fehler |
| 2 | Usage: fehlende/ungültige Argumente, ungültige ID/URL, mehrdeutiger Name ohne TTY, ungültige Optionen |
| 3 | Netz/Quelle: Timeout, Verbindungsfehler, HTTP 429/5xx, Rezept-404, keine Treffer |
| 4 | Login erforderlich (bei diesem Tool nicht verwendet) bzw. Daten-/Parse-Fehler |

## 7. Umgebung und Pfade

| Variable | Bedeutung |
|---|---|
| `CHEFKOCH_BASE_URL` | API-Basis, Default `https://api.chefkoch.de` |
| `CHEFKOCH_MIN_INTERVAL` | Mindestabstand in Sekunden zwischen Requests, Default `1`; `0` nur für Tests |
| `XDG_STATE_HOME` | Basis für den Watch-State; Fallback `~/.local/state` |

Weitere Config-Dateien gibt es nicht. Der Watch-State ist die einzige
persistente Datei; er enthält nur IDs, Suchschlüssel und Zeitstempel, keine
Nutzerdaten.

## 8. Grenzen

- Die API ist **inoffiziell** und nicht dokumentiert. Felder, Filter und
  Antwortstrukturen können sich jederzeit ändern; es gibt keine Garantie auf
  Verfügbarkeit.
- Live getestet wurden ausschließlich lesende GET-Requests auf öffentliche
  Seiten/Endpunkte. Schreibende Aktionen, Logins und echte Konten sind weder
  getestet noch vorgesehen.
- Die CLI ist kein Scraper der Website: HTML-Seiten unter `www.chefkoch.de`
  werden nicht abgerufen.
- Fixtures sind echte, gekürzte und anonymisierte Antworten; sie enthalten
  keine Owner-, Editor- oder Avatar-Daten.

## 9. Akzeptanztests

`tests/acceptance/test_ux_sessions.py` enthält je UX-Sitzung mindestens einen
pytest-Test. Die Tests starten das Tool als Subprozess gegen
`tests/harness/fake_server.py` mit den `ux-routes` aus `docs/UX.md` und prüfen
die Kernausgaben. Bis zum Bau in Schritt 4 dürfen sie rot sein.

Das UX-Gate unter `tests/harness/` wird nicht verändert oder aufgeweicht.
