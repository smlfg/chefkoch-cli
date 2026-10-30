# chefkoch-cli — Anforderungen (Schritt 1)

Stand: 2026-10-30. Alle Live-Beobachtungen wurden mit dem User-Agent
`chefkoch-cli/0.1 (+https://github.com/smlfg/chefkoch-cli)` und maximal einem
Request pro Sekunde gegen die öffentliche Chefkoch-API erhoben.

## 1. Ziel

`chefkoch` ist eine read-only CLI für Agenten mit Live-Zugriff auf Chefkoch.de:

- Rezepte suchen und filtern
- Rezeptdetails inkl. Zutaten, auf Portionen skaliert, und Zubereitung abrufen
- Einkaufsliste aus mehreren Rezepten erzeugen
- Neue Rezepte zu einem Suchbegriff beobachten

Keine Accounts, keine Schreibzugriffe, keine Login-Daten. Laufzeitabhängigkeit:
nur `httpx` (Python >= 3.10, MIT).

## 2. Datenquelle

Basis: `https://api.chefkoch.de`. Es werden ausschließlich
`GET /v2/recipes` und `GET /v2/recipes/<id>` verwendet.

### 2.1 Robots.txt und Nutzungsgrenzen

Live geprüft:

- `https://api.chefkoch.de/robots.txt` erlaubt `/v2/recipes` und sperrt
  `/v2/search/suggestions/` sowie zwei Kommentar-Endpunkte.
- `https://www.chefkoch.de/robots.txt` sperrt u. a. `/rezepte/*?*`.

Daraus folgt für die CLI:

- `/v2/search/suggestions` wird nicht verwendet.
- `/rezepte/*?*` wird nicht abgerufen. Rezept-URLs werden nur lokal geparst;
  Details kommen ausschließlich über `/v2/recipes/<id>`.
- Jeder Prozess hält mindestens 1 Sekunde Abstand zwischen HTTP-Requests
  (auch bei mehreren Detail-Abrufen für Tag-Filter).
- Fester User-Agent wie oben. Keine Cookies, keine Accounts.

### 2.2 Suche: live belegte Parameter

Beispiel: `GET /v2/recipes?query=lasagne&limit=5` → HTTP 200,
`count=2164`, 5 Treffer. Antwortform:

```json
{
  "count": 2164,
  "queryId": "",
  "results": [
    {"score": 2164, "recipe": {"id": "...", "title": "...", "...": "..."}}
  ]
}
```

Live-Belege (jeweils gegen `query=lasagne`):

| Parameter | Live-Ergebnis |
|---|---|
| `limit` | `limit=5` liefert 5 Treffer; `limit=25` liefert 25; `limit=100` liefert 100 Treffer. |
| `offset` | `offset=2` verschiebt den ersten Treffer von `745721177147257` auf `555661153310338`; `count` bleibt 2164. |
| `minimumRating` | `minimumRating=4.8` → `count=380`; alle gelieferten Ratings lagen bei 4.85–4.94, also ≥ 4.8. |
| `maximumTime` | `maximumTime=15` → `count=196`; alle Treffer hatten `preparationTime <= 15`. Die Detailabfrage von `348581119961196` ergab `preparationTime=15`, aber `totalTime=55`: der Filter bezieht sich auf die **Zubereitungszeit**, nicht auf `totalTime`. |
| `tags` | Numerische Tag-ID, keine Namen. `tags=32` → `count=838` (Tag 32 = „Vegetarisch“); `tags=57` → `count=78` (Tag 57 = „Vegan“). `tags=vegetarisch` → `count=0`. |
| `sort` / `order` / `sortBy` | **Nicht serverseitig wirksam.** Getestet mit `sort=rating`, `sort=date`, `sort=time`, `sort=newest`, `sort=latest`, `sort=popular`, `sort=fastest`, `sort=relevance`, `sort=preparationTime`, `sort=createdAt`, `sort=numVotes`, `sort=viewCount`, `sort=title`, `sort=rating&order=desc/asc`, `order=rating`, `sortBy=rating`: Trefferreihenfolge und IDs blieben identisch. |
| `orderBy` | `orderBy=rating` → HTTP 400, `{"notification":{"hasErrors":true,"messages":[{"type":"error","identifier":"malformed_query"}]}}`. Wird nicht verwendet. |
| `difficulty` | **Nicht serverseitig wirksam.** Getestet mit `difficulty=1`, `difficulty=1,2`, `difficulty=1&difficulty=2`, `difficulty[]=1`, `difficulty=simpel`, `difficulty=pfiffig`: Treffer blieben unverändert. Schwierigkeit wird clientseitig gefiltert. |
| `categories` / `categoryIds` | `categories=32` → `count=0`; `categoryIds=32` wurde ignoriert. Kategorien werden nicht als Filter verwendet; Tags genügen. |

Wichtig: Die Suchantwort enthält **keine Tags**. Für `--vegetarisch` und
`--vegan` wird deshalb zusätzlich pro Kandidat `/v2/recipes/<id>` abgerufen und
gegen `fullTags` geprüft. Die serverseitigen `tags`-Parameter (32/57) werden
nur als Vorfilter genutzt; die endgültige Entscheidung fällt clientseitig.

### 2.3 Suchfelder

Verwendete Felder aus `results[].recipe`:

- `id` (String), `title`, `subtitle`
- `createdAt` (ISO-8601, für Sortierung „neu“)
- `difficulty` (1, 2 oder 3)
- `preparationTime` (Minuten; für `--max-zeit`)
- `rating.rating`, `rating.numVotes`
- `siteUrl`, `slug`, `hasImage`

Nicht benötigt und daher nicht in Fixtures: `owner`, `editor`,
Profilbilder/Avatare, Nutrition-Details.

### 2.4 Detail: live belegte Felder

Beispiel: `GET /v2/recipes/745721177147257` → HTTP 200. Relevante Felder:

- `id`, `title`, `subtitle`, `slug`, `siteUrl`
- `servings` (Basisportionen)
- `difficulty` (1/2/3)
- `preparationTime`, `cookingTime`, `restingTime`, `totalTime` (Minuten)
- `rating.rating`, `rating.numVotes`
- `instructions` (Text)
- `tags` (Strings) und `fullTags` (`[{id, name}]`)
- `categoryBreadcrumb`
- `ingredientGroups[].header`
- `ingredientGroups[].ingredients[]` mit
  `name`, `amount` (Float), `unit` (String, kann leer sein), `unitId`,
  `isBasic`

Mengen werden mit `amount * (zielPortionen / servings)` skaliert. Runden auf
zwei Nachkommastellen; `-0.0` wird zu `0`. Fehlt `amount`, gilt `0`; fehlt
`unit`, gilt `""`. Fehlt `name` oder ist die Struktur ungültig, ist das ein
Parse-Fehler (Exit 4).

Tag-IDs (aus `fullTags` belegt): `32` = Vegetarisch, `57` = Vegan. Vegan-
Rezepte tragen zusätzlich Tag 32.

Schwierigkeits-Mapping: `1` = simpel, `2` = normal, `3` = pfiffig. Andere Werte
gelten als Parse-Fehler.

### 2.5 404

`GET /v2/recipes/1` und `GET /v2/recipes/999999999999999999` liefern HTTP 404:

```json
{"notification":{"hasErrors":true,"messages":[{"type":"error","identifier":"entity_not_found"}]}}
```

Die CLI bildet das auf `not_found` / Exit 3 ab.

### 2.6 Rezept-ID und URL

Akzeptiert werden:

- reine numerische ID, z. B. `745721177147257`
- Chefkoch-URL der Form
  `https://www.chefkoch.de/rezepte/<id>/<slug>.html`

Es wird nur die ID extrahiert; die URL selbst wird nie abgerufen. Andere Hosts,
Pfade oder nicht-numerische IDs sind Eingabefehler (Exit 1).

## 3. Befehle

Globale Option: `--timeout SEC` (positive Zahl, Default 15; gilt pro Request).
`--version` und `--help` beenden mit Exit 0. `--json` ist bei allen Befehlen
erlaubt und kann auch global stehen.

### 3.1 `chefkoch suche`

```
chefkoch suche <begriff> [--max-zeit MIN] [--min-bewertung X]
    [--vegetarisch] [--vegan]
    [--schwierigkeit simpel|normal|pfiffig]
    [--sort bewertung|zeit|neu] [--limit N] [--seite N] [--json]
```

- `limit`: Default 10, gültig 1–100.
- `seite`: Default 1, gültig ≥ 1. Die Seite wird **clientseitig** nach dem
  Filtern und Sortieren gebildet.
- `sort`: Default `bewertung`.
  - `bewertung`: Rating absteigend, dann `numVotes` absteigend, dann Titel.
  - `zeit`: `preparationTime` aufsteigend, dann Rating absteigend.
  - `neu`: `createdAt` absteigend, dann `id` absteigend.
- `min-bewertung`: Zahl 0–5. Server-Parameter `minimumRating`; zusätzlich
  clientseitig gegen jeden Treffer geprüft.
- `max-zeit`: Minuten ≥ 0. Server-Parameter `maximumTime` (wirkt auf
  `preparationTime`); zusätzlich clientseitig geprüft.
- `vegetarisch` / `vegan`: serverseitig `tags=32` bzw. `tags=57`, danach
  Detailprüfung per `fullTags` gegen jeden Treffer. `--vegan` impliziert
  vegetarisch.
- `schwierigkeit`: clientseitig gegen `difficulty` geprüft.
- Alle Filter werden nach der API-Antwort nochmals gegen jeden Treffer
  erzwungen. Treffer, die einen Filter nicht erfüllen, werden verworfen.

Da die API weder Sortierung noch Schwierigkeit unterstützt, wird immer ab
Server-Offset 0 gelesen. Die CLI lädt `window = min(500, max(50, seite*limit))`
Treffer (in Blöcken von höchstens 100 pro Request), filtert und sortiert sie
clientseitig und schneidet danach
`[(seite-1)*limit : seite*limit]` heraus. Dadurch sind die Seiten disjunkt und
aufeinanderfolgend, solange sie innerhalb des 500-Treffer-Fensters liegen.
Sortierung ist nur innerhalb dieses Fensters garantiert. Bei `--json` stehen
`total` (Server-Count) und `count` (tatsächlich gelieferte Treffer) zur
Verfügung.

Erfolgs-JSON:

```json
{
  "ok": true,
  "command": "suche",
  "data": {
    "query": "lasagne",
    "page": 1,
    "limit": 10,
    "total": 2164,
    "count": 10,
    "results": [
      {
        "id": "745721177147257",
        "title": "Lasagne",
        "subtitle": "...",
        "rating": 4.7,
        "numVotes": 5033,
        "difficulty": 2,
        "difficultyLabel": "normal",
        "preparationTime": 30,
        "createdAt": "2007-04-21T17:55:01+02:00",
        "siteUrl": "https://www.chefkoch.de/rezepte/745721177147257/Lasagne.html",
        "vegetarian": null,
        "vegan": null
      }
    ]
  }
}
```

`vegetarian`/`vegan` sind `true`/`false`, wenn geprüft wurde (Tag-Filter
aktiv), sonst `null`.

Keine Treffer nach allen Filtern: `ok=false`, `error.type="no_results"`,
Exit 3.

### 3.2 `chefkoch rezept`

```
chefkoch rezept <id|url> [--portionen N] [--json]
```

- `portionen`: Default = `servings` des Rezepts, gültig ≥ 1.
- Zutaten werden auf `portionen` skaliert; Gruppen und Reihenfolge bleiben
  erhalten.
- `--json` liefert ein normalisiertes Rezeptobjekt inkl. `requestedServings`,
  `scale`, Zeiten, Rating, Schwierigkeit, Tags und skalierten Zutaten.

Erfolgs-JSON (gekürzt):

```json
{
  "ok": true,
  "command": "rezept",
  "data": {
    "id": "745721177147257",
    "title": "Lasagne",
    "subtitle": "...",
    "servings": 4,
    "requestedServings": 8,
    "scale": 2.0,
    "rating": 4.7,
    "numVotes": 5033,
    "difficulty": 2,
    "difficultyLabel": "normal",
    "preparationTime": 30,
    "cookingTime": 70,
    "restingTime": 10,
    "totalTime": 100,
    "siteUrl": "https://www.chefkoch.de/rezepte/745721177147257/Lasagne.html",
    "instructions": "...",
    "tags": ["Hauptspeise", "..."],
    "ingredientGroups": [
      {
        "header": "Für die Bolognese: ",
        "ingredients": [
          {"name": "Hackfleisch, gemischtes", "amount": 1000.0, "unit": "g"}
        ]
      }
    ]
  }
}
```

Nicht gefunden (HTTP 404): `error.type="not_found"`, Exit 3.

### 3.3 `chefkoch einkaufsliste`

```
chefkoch einkaufsliste <id|url>... [--portionen N] [--json]
```

- Mindestens eine ID/URL.
- `portionen` gilt für **jedes** Rezept; ohne Angabe wird pro Rezept dessen
  eigenes `servings` verwendet (Faktor 1).
- Zutaten werden zuerst pro Rezept skaliert.
- Gruppierung: normalisierter Name + normalisierte Einheit. Normalisierung:
  Unicode NFC, trimmen, interne Whitespaces auf ein Leerzeichen reduzieren,
  `casefold()`. Keine Synonym- oder Plural-Zusammenführung (z. B. bleibt
  „Zwiebel(n)“ von „Zwiebel“ getrennt).
- Gleiche Name+Einheit werden summiert. Unterschiedliche Einheiten bleiben
  getrennte Positionen. Leere Einheit ist eine eigene Einheit.
- Ausgabe nach Name, dann Einheit sortiert. `recipeIds` enthält die
  beteiligten Rezept-IDs, eindeutig und sortiert.
- Beträge werden erst nach der Summe auf zwei Nachkommastellen gerundet.

Erfolgs-JSON:

```json
{
  "ok": true,
  "command": "einkaufsliste",
  "data": {
    "recipes": [
      {"id": "745721177147257", "servings": 4, "requestedServings": 4},
      {"id": "2114131340630587", "servings": 3, "requestedServings": 4}
    ],
    "items": [
      {
        "name": "Käse, geriebener",
        "unit": "g",
        "amount": 466.67,
        "recipeIds": ["2114131340630587", "745721177147257"]
      }
    ]
  }
}
```

Beispielrechnung: 200 g (Basis 4, Ziel 4) + 200 g (Basis 3, Ziel 4) =
200 + 266,666… = 466,67 g.

### 3.4 `chefkoch watch`

```
chefkoch watch <begriff> [--max-zeit MIN] [--min-bewertung X]
    [--vegetarisch] [--vegan]
    [--schwierigkeit simpel|normal|pfiffig]
    [--limit N] [--json]
```

- Verwendet dieselben Filterregeln wie `suche`, aber ohne `--sort`/`--seite`.
- `limit`: Default 50, gültig 1–100. Es werden höchstens `limit` aktuelle
  Treffer betrachtet. Watch lädt dasselbe Abfragefenster wie `suche` (maximal
  500 Treffer), sortiert clientseitig nach `neu` und betrachtet die ersten
  `limit` Treffer.
- State: `$XDG_STATE_HOME/chefkoch-cli/watch.json`. Ist `XDG_STATE_HOME` nicht
  gesetzt oder leer, gilt `~/.local/state/chefkoch-cli/watch.json`.
- Verzeichnis wird mit `0700`, Datei mit `0600` angelegt; vorhandene Datei wird
  auf `0600` gesetzt. Schreiben atomar (Temp-Datei im selben Verzeichnis +
  `os.replace`).
- State-Schlüssel: normalisierter Suchbegriff + alle filternden Optionen.
- Erster Lauf ohne State für diesen Schlüssel: alle aktuellen Treffer gelten
  als neu, `changed=true`. Die aktuellen IDs werden gespeichert.
- Folgelauf: `new` = aktuelle IDs minus gespeicherte IDs; `changed` ist
  `true`, wenn `new` nicht leer ist. Danach wird die aktuelle ID-Menge
  gespeichert. Ohne neue Rezepte ist `changed=false` (zweiter Lauf bei
  unveränderten Fixtures).
- Keine Treffer: `error.type="no_results"`, Exit 3; State wird nicht
  verändert.
- Kaputter/nicht lesbarer State: `error.type="state"`, Exit 1, keine
  Traceback-Ausgabe.
- Watch speichert nur IDs und den Zeitpunkt, keine Nutzerdaten.

Erfolgs-JSON:

```json
{
  "ok": true,
  "command": "watch",
  "data": {
    "query": "lasagne",
    "changed": true,
    "new": [{"id": "...", "title": "...", "...": "..."}],
    "checkedAt": "2026-10-30T10:30:00+00:00"
  }
}
```

`new` verwendet dieselbe normalisierte Trefferform wie `suche`.

### 3.5 `chefkoch --version` / `chefkoch --help`

Beide beenden mit Exit 0. `--version` gibt `chefkoch-cli <version>` aus.
`--help` zeigt alle Befehle und Optionen.

## 4. Vertrag

### 4.1 stdout/stderr und JSON

- Mit `--json` wird **genau ein** JSON-Objekt auf stdout geschrieben — auch bei
  Fehlern. Keine Logs, Warnungen oder Tracebacks auf stdout.
- Im JSON-Fehlermodus gilt exakt:

  ```json
  {"ok": false, "error": {"type": "<typ>", "message": "<text>"}}
  ```

- Im Human-Modus gehen Fortschritt/Warnungen auf stderr; Fehler werden als
  kurze Meldung auf stderr ausgegeben. Niemals Traceback.
- Unerwartete Exceptions werden abgefangen und als `internal` (Exit 4)
  gemeldet.

### 4.2 Exitcodes

| Exit | Bedeutung |
|---|---|
| 0 | Erfolg, inkl. `--help` und `--version` |
| 1 | Nutzung/Eingabe: argparse-Fehler, ungültige ID/URL, ungültige Optionen, kaputter State |
| 2 | Netzwerk/HTTP: Timeout, Verbindungsfehler, 429, 5xx, sonstige HTTP-Fehler |
| 3 | Nicht gefunden / keine Treffer: Rezept-404, leere Suche nach Filtern |
| 4 | Parse-/Verarbeitungsfehler: ungültiges JSON, fehlende Pflichtfelder, unerwartete Struktur |

Argparse-Fehler müssen auf Exit 1 abgebildet werden (nicht auf den
argparse-Standard 2). Dazu wird `ArgumentParser.error` überschrieben; `--json`
wird vor dem Parsen erkannt, damit auch Syntaxfehler als JSON gemeldet werden.

### 4.3 Fehlertypen

| `error.type` | Exit | Auslöser |
|---|---|---|
| `usage` | 1 | fehlende/ungültige Argumente, ungültige ID/URL, `--timeout <= 0` |
| `state` | 1 | Watch-State nicht lesbar, ungültig, falsche Version/Struktur |
| `network` | 2 | Timeout, DNS-, Verbindungsfehler |
| `http` | 2 | unerwarteter HTTP-Status, inkl. 429/5xx |
| `not_found` | 3 | Rezept-ID existiert nicht (HTTP 404) |
| `no_results` | 3 | Suche/Watch liefert nach allen Filtern keine Treffer |
| `parse` | 4 | ungültige JSON-Struktur, fehlende Pflichtfelder, ungültige Mengen |
| `internal` | 4 | unerwarteter interner Fehler (letztes Sicherheitsnetz) |

### 4.4 HTTP-Verhalten

- Basis-URL fest `https://api.chefkoch.de`; nur `/v2/recipes` und
  `/v2/recipes/<id>`.
- Fester User-Agent, `Accept: application/json`.
- `--timeout` gilt pro Request; Default 15 s.
- Mindestens 1 s zwischen zwei Requests desselben Prozesses.
- Keine automatischen Retries bei 429/5xx (Agent kann den Befehl wiederholen).
- 404 bei Rezept → `not_found`; 404 bei Suche → `http`.
- 200 mit ungültigem JSON → `parse`.

### 4.5 Suche/Filter/Sortierung

- Serverseitig unterstützte Filter (`minimumRating`, `maximumTime`, `tags`)
  werden mitgesendet.
- Jeder Filter wird zusätzlich clientseitig gegen jeden gelieferten Treffer
  geprüft. Das gilt auch für `minimumRating`, `maximumTime` und Tags.
- Sortierung ist immer clientseitig (API ignoriert `sort`).
- Schwierigkeit ist immer clientseitig (API ignoriert `difficulty`).
- Bei aktivem Tag-Filter werden Details nachgeladen; dabei gilt das
  Request-Limit von 1/s.
- `--vegan` impliziert vegetarisch; die Detailprüfung akzeptiert nur Treffer
  mit Tag 57 (und damit auch 32).

### 4.6 Portionen und Einkaufsliste

- `portionen >= 1`; `servings` aus der API muss > 0 sein, sonst Parse-Fehler.
- Skalierungsfaktor = `portionen / servings`.
- Zutaten mit `amount=0` bleiben erhalten (z. B. „Salz und Pfeffer“).
- Einkaufsliste summiert nur exakt normalisierte Name+Einheit-Paare.
- Mehrfach genannte Rezept-IDs werden mehrfach gezählt (Zutaten entsprechend
  mehrfach addiert).

### 4.7 Watch-State

- Format:

  ```json
  {
    "version": 1,
    "queries": {
      "<key>": {"seenIds": ["..."], "checkedAt": "2026-10-30T10:30:00+00:00"}
    }
  }
  ```

- `<key>` ist ein stabiler, normalisierter String aus Begriff und Filtern.
- Datei/Verzeichnis-Rechte werden bei jedem Schreiben erzwungen.
- State-Fehler dürfen niemals einen Traceback erzeugen.

## 5. Akzeptanztests (pytest, nur Fixtures)

Alle Tests laufen offline. Eine autouse-Fixture ersetzt den httpx-Transport
durch `httpx.MockTransport` und lässt unmatched Requests fehlschlagen; echte
Netzwerkverbindungen sind blockiert. Es werden ausschließlich die Fixtures aus
`tests/fixtures/` verwendet.

### 5.1 Fixtures

- `search_lasagne.json` — echte Suche `query=lasagne&limit=25`, 25 Treffer,
  `count=2164`, anonymisiert (keine Owner-/Avatar-Felder).
- `search_vegan_lasagne.json` — echte Suche `query=vegane lasagne&limit=5`,
  5 Treffer, u. a. `2812481433250378`.
- `search_empty.json` — echte Suche ohne Treffer (`count=0`).
- `recipe_745721177147257.json` — Lasagne, 4 Portionen, 3 Zutatengruppen.
- `recipe_2114131340630587.json` — vegetarische Lasagne, 3 Portionen.
- `recipe_2812481433250378.json` — vegane Lasagne, 8 Portionen, 3 Gruppen.
- `recipe_404.json` — echte 404-Antwort (`entity_not_found`).

Alle Rezept-Fixtures sind auf die benötigten Felder gekürzt; Owner, Editor und
Profilbilder wurden entfernt.

### 5.2 Testfälle

1. **Fixture-Integrität:** Such-Fixtures enthalten `count`/`results`; Rezept-
   Fixtures enthalten `id`, `servings`, `ingredientGroups`; nirgends kommen
   `owner`, `username`, `displayName` oder Avatar-URLs vor.
2. **Hilfe/Version:** `chefkoch --help` und `chefkoch --version` → Exit 0, keine
   Netzwerkaufrufe.
3. **Argparse/JSON:** `chefkoch suche --json` (Begriff fehlt) → Exit 1, genau
   ein JSON-Objekt, `ok=false`, `error.type="usage"`, kein Traceback.
4. **Suche normal:** `suche lasagne --limit 25 --json` gegen
   `search_lasagne.json` → Exit 0, `count=25`, `total=2164`,
   Default-Sortierung nach Bewertung absteigend.
5. **Filter:** `--min-bewertung 4.6`, `--max-zeit 25`,
   `--schwierigkeit simpel|normal|pfiffig` → jeder gelieferte Treffer erfüllt
   den jeweiligen Filter; Kombinationen erfüllen alle Filter.
6. **Sortierung:** `--sort zeit` → `preparationTime` nicht absteigend;
   `--sort neu` → `createdAt` absteigend; `--sort bewertung` → Rating
   absteigend, Tiebreak `numVotes`.
7. **Paginierung:** `--limit 3` und `--seite 1/2` liefern disjunkte,
   aufeinanderfolgende Ausschnitte; `--seite` außerhalb des Fensters → leere
   Seite bzw. `no_results`, falls nichts übrig bleibt.
8. **Tag-Filter:** `suche "vegane lasagne" --vegan --limit 1 --json` mit
   `search_vegan_lasagne.json` und `recipe_2812481433250378.json` → genau ein
   Treffer, `vegan=true`; `--vegetarisch` → ebenfalls Treffer.
   Nicht passende Detail-Fixtures werden verworfen.
9. **Keine Treffer:** `suche zzzzzzzzzz --json` gegen `search_empty.json` →
   Exit 3, `error.type="no_results"`.
10. **Rezept-ID:** `rezept 745721177147257 --json` → Basis `servings=4`,
    3 Gruppen, unskalierte Mengen.
11. **Rezept-URL:** Dieselbe URL
    `https://www.chefkoch.de/rezepte/745721177147257/Lasagne.html` liefert das
    gleiche Ergebnis wie die ID; es wird kein `/rezepte/...`-Request gemacht.
12. **Portionen:** `rezept 745721177147257 --portionen 8` → Faktor 2,
    `Hackfleisch, gemischtes` von 500 auf 1000 g, `requestedServings=8`.
13. **Rezept-404:** `rezept 1 --json` mit `recipe_404.json` → Exit 3,
    `error.type="not_found"`, genau ein JSON-Objekt, kein Traceback.
14. **Ungültige ID/URL:** `rezept abc`, fremder Host, fehlendes HTML →
    Exit 1, `error.type="usage"`.
15. **Einkaufsliste summiert:** `einkaufsliste 745721177147257
    2114131340630587 --json` → gemeinsame Position `Käse, geriebener` /
    `g` mit 400 g (ohne Portionsangabe). Mit `--portionen 4` → 466,67 g.
16. **Einkaufsliste Einheiten:** Gleicher Name mit unterschiedlicher Einheit
    bleibt getrennt; gleiche ID zweimal zählt doppelt.
17. **Watch erster/zweiter Lauf:** Mit temporärem `XDG_STATE_HOME` liefert der
    erste Lauf `changed=true` und legt `watch.json` mit Modus `0600` an; der
    zweite Lauf mit identischen Fixtures liefert `changed=false` und `new=[]`.
18. **Watch-State kaputt:** Ungültiges JSON im State → Exit 1,
    `error.type="state"`, kein Traceback; State wird nicht überschrieben.
19. **Netzwerkfehler:** MockTransport wirft `httpx.ConnectError` → Exit 2,
    `error.type="network"`.
20. **HTTP-Fehler:** MockTransport liefert 500 → Exit 2, `error.type="http"`.
21. **Parse-Fehler:** Such-/Detail-Fixture mit ungültigem JSON oder fehlendem
    Pflichtfeld → Exit 4, `error.type="parse"`.
22. **JSON-Ein-Objekt-Regel:** Für alle Fehlerfälle aus 3, 9, 13, 14, 18–21
    gilt: stdout parst als genau ein Objekt mit `ok=false` und `error`; es
    erscheint kein Traceback auf stdout/stderr.
23. **Timeout:** `--timeout 0` → Exit 1 (`usage`); `--timeout 5` wird an den
    httpx-Client übergeben (Mock-Inspection).
24. **User-Agent:** Jeder gemockte Request trägt den festen User-Agent
    `chefkoch-cli/0.1 (+https://github.com/smlfg/chefkoch-cli)`.
