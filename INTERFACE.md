# chefkoch-cli — Interface

Verbindlicher Schnittstellenvertrag für `chefkoch` (Console-Script) bzw.
`python -m chefkoch_cli`. Änderungen nur zusammen mit `ANFORDERUNGEN.md`, den
Akzeptanztests und `docs/UX.md`.

## 1. Aufruf

```
chefkoch [--json] [--timeout SEK] <unterbefehl> ...
chefkoch --version
chefkoch --help
```

`--json` und `--timeout` dürfen global oder nach dem Unterbefehl stehen.
`--help` und `--version` beenden mit Exit 0. Für alle Unterbefehle gilt:
Name/Suchbegriff positional, keine Pflicht-Optionen.

## 2. Unterbefehle

### 2.1 `suche`

```
chefkoch suche BEGRIFF [--vegetarisch | --vegan]
    [--max-zeit MIN] [--min-bewertung X]
    [--schwierigkeit simpel|normal|pfiffig]
    [--sort bewertung|zeit|neu]
    [--limit N] [--seite N]
    [--json] [--timeout SEK]
```

| Argument/Flag | Default | Bedeutung |
|---|---|---|
| `BEGRIFF` | — | Suchbegriff, positional (erforderlich) |
| `--vegetarisch` | aus | nur Rezepte mit Tag 32 (Detailprüfung) |
| `--vegan` | aus | nur Rezepte mit Tag 57; impliziert vegetarisch |
| `--max-zeit MIN` | aus | `preparationTime <= MIN`, Minuten >= 0 |
| `--min-bewertung X` | aus | Rating >= X, Zahl 0–5 |
| `--schwierigkeit` | aus | `simpel` (1), `normal` (2), `pfiffig` (3) |
| `--sort` | `bewertung` | `bewertung`, `zeit` oder `neu`, clientseitig |
| `--limit N` | `10` | Treffer pro Seite, 1–100 |
| `--seite N` | `1` | Seite >= 1, clientseitig gebildet |

Sortierung: `bewertung` = Rating absteigend, dann `numVotes` absteigend, dann
Titel; `zeit` = `preparationTime` aufsteigend, dann Rating absteigend;
`neu` = `createdAt` absteigend, dann ID absteigend. Es werden höchstens 500
Treffer ab Server-Offset 0 geladen und daraus die Seite geschnitten.

### 2.2 `rezept`

```
chefkoch rezept NAME|ID|URL [--portionen N] [--json] [--timeout SEK]
```

| Argument/Flag | Default | Bedeutung |
|---|---|---|
| `NAME|ID|URL` | — | Rezeptname, numerische ID oder Chefkoch-URL |
| `--portionen N` | `servings` | Zielportionen, ganzzahlig >= 1 |

Namensauflösung: Suchanfrage an `GET /v2/recipes`. Genau ein Treffer wird
direkt geöffnet. Bei mehreren Treffern erscheint im TTY eine nummerierte
Liste und die Frage `Auswahl [1-<n>]:`; die Eingabe ist eine Nummer. Ohne TTY
wird dieselbe Liste ausgegeben und der Befehl endet mit Exit 2 (`usage`).
Eine ID/URL wird ohne Suche direkt geladen.

Im TTY erscheinen Titel, Portionen, Zutaten und Zubereitung lesbar. Zutaten
werden mit `portionen / servings` skaliert; Mengen haben höchstens zwei
Nachkommastellen und werden mit Komma ausgegeben.

### 2.3 `einkaufsliste`

```
chefkoch einkaufsliste NAME|ID|URL... [--portionen N] [--json] [--timeout SEK]
```

| Argument/Flag | Default | Bedeutung |
|---|---|---|
| `NAME|ID|URL...` | — | mindestens eine Angabe |
| `--portionen N` | je Rezept `servings` | Zielportionen für **jedes** Rezept |

Jede Angabe wird wie bei `rezept` aufgelöst. Mehrdeutige Namen fragen im TTY
nacheinander nach einer Auswahl; ohne TTY endet der Befehl mit Exit 2.
Zutaten werden pro Rezept skaliert, dann über normalisierte Name+Einheit-Paare
summiert. Gleiche Namen mit unterschiedlicher Einheit bleiben getrennt.
Ausgabe nach Name, dann Einheit sortiert.

### 2.4 `watch`

```
chefkoch watch BEGRIFF [--vegetarisch | --vegan]
    [--max-zeit MIN] [--min-bewertung X]
    [--schwierigkeit simpel|normal|pfiffig]
    [--limit N] [--json] [--timeout SEK]
```

| Argument/Flag | Default | Bedeutung |
|---|---|---|
| `BEGRIFF` | — | Suchbegriff, positional |
| Filter | aus | wie bei `suche` |
| `--limit N` | `50` | höchstens N aktuelle Treffer betrachten, 1–100 |

Kein `--sort`, keine `--seite`. Erster Lauf für einen Suchschlüssel markiert
alle aktuellen Treffer als neu. Folgeläufe vergleichen die aktuellen IDs mit
dem gespeicherten State. Ohne neue Treffer ist `changed=false`.

## 3. Namensauflösung und Auswahl

- Namen sind Freitext; Groß-/Kleinschreibung spielt für die Suche keine Rolle
  (die API entscheidet über die Treffer).
- Im TTY: nummerierte Liste mit ID, Bewertung, Zubereitungszeit und
  Schwierigkeit sowie Prompt `Auswahl [1-<n>]:`.
- Ohne TTY (Pipe/Agent): dieselbe Liste, danach Abbruch mit Exit 2. Es wird
  keine Eingabe von stdin erwartet.
- Ungültige Auswahl im TTY wird erneut abgefragt; EOF/Strg+C bricht ohne
  Traceback mit Exit 1 ab.
- IDs/URLs sind immer eindeutig und lösen keine Auswahl aus.

## 4. Ausgabeformat

### 4.1 TTY (lesbar)

```
1) Lasagne (ID 745721177147257) · 4,7★ · 30 Min. · normal
2) Italienische Lasagne (ID 491931143472316) · 4,6★ · 60 Min. · normal
```

```
Die ultimative vegane Lasagne
Portionen: 4 (Basis: 8)
125 g Naturtofu
125 g Räuchertofu
```

```
Einkaufsliste (4 Portionen je Rezept)
4,67 Knoblauchzehe(n)
266,67 g Käse, geriebener
125 g Naturtofu
```

Bewertungen: eine Nachkommastelle, Dezimalkomma. Mengen: höchstens zwei
Nachkommastellen, Dezimalkomma. Fortschritt/Warnungen gehen auf stderr.

### 4.2 JSON

JSON wird ausgegeben mit `--json` oder wenn stdout kein TTY ist. Auf stdout
steht dann genau ein Objekt, auch bei Fehlern:

```json
{"ok": true, "command": "suche", "data": {"query": "lasagne", "page": 1,
 "limit": 5, "total": 2165, "count": 5, "results": []}}
```

```json
{"ok": false, "error": {"type": "usage", "message": "..."}}
```

Feldformen:

- `suche`: `query`, `page`, `limit`, `total` (Server-Count), `count`,
  `results[]` mit `id`, `title`, `subtitle`, `rating`, `numVotes`,
  `difficulty`, `difficultyLabel`, `preparationTime`, `createdAt`, `siteUrl`,
  `vegetarian`, `vegan` (je `true`/`false` bei Tag-Prüfung, sonst `null`).
- `rezept`: `id`, `title`, `subtitle`, `servings`, `requestedServings`,
  `scale`, `rating`, `numVotes`, `difficulty`, `difficultyLabel`,
  `preparationTime`, `cookingTime`, `restingTime`, `totalTime`, `siteUrl`,
  `instructions`, `tags`, `ingredientGroups[]` mit `header` und
  `ingredients[]` (`name`, `amount`, `unit`).
- `einkaufsliste`: `recipes[]` (`id`, `servings`, `requestedServings`) und
  `items[]` (`name`, `unit`, `amount`, `recipeIds[]`).
- `watch`: `query`, `changed`, `new[]` (Trefferform wie `suche`),
  `checkedAt` (ISO-8601).

## 5. Exit-Codes

| Exit | Bedeutung | Beispiele |
|---|---|---|
| 0 | Erfolg | Treffer, Rezept, Einkaufsliste, Watch ohne Fehler, `--help`, `--version` |
| 1 | Allgemeiner Fehler | kaputter Watch-State, Konfigurations-/IO-Fehler, unerwarteter interner Fehler, Abbruch per EOF/Strg+C |
| 2 | Usage | fehlende/ungültige Argumente, ungültige ID/URL, mehrdeutiger Name ohne TTY, ungültige Option, `--timeout <= 0` |
| 3 | Netz/Quelle | Timeout, Verbindungsfehler, HTTP 429/5xx, unerwarteter Status, Rezept-404, keine Treffer |
| 4 | Login erforderlich / Daten | bei diesem Tool kein Login; Parse-Fehler, ungültiges JSON, fehlende Pflichtfelder |

Argparse-Fehler werden auf Exit 2 abgebildet. Im JSON-Modus gilt das auch für
Syntaxfehler; `--json` wird vor dem Parsen erkannt.

Fehlertypen im JSON: `usage` (2), `state`/`internal` (1), `network`/`http`/
`not_found`/`no_results` (3), `parse` (4). `login_required` ist reserviert und
wird von `chefkoch` nicht erzeugt.

## 6. Umgebungsvariablen

| Variable | Default | Bedeutung |
|---|---|---|
| `CHEFKOCH_BASE_URL` | `https://api.chefkoch.de` | API-Basis; Test/Fake-Server überschreiben sie |
| `CHEFKOCH_MIN_INTERVAL` | `1` | Mindestabstand in Sekunden zwischen Requests; `0` nur für Tests |
| `XDG_STATE_HOME` | `~/.local/state` | Basis für den Watch-State |

`CHEFKOCH_MIN_INTERVAL` und `CHEFKOCH_BASE_URL` müssen robust validiert werden:
ungültige Zahlen oder URLs ergeben einen Fehler ohne Traceback (Exit 1 bzw. 2).
Es gibt keine Credential-Variablen und keinen `login`-Befehl.

## 7. Config-Pfade

- Watch-State: `$XDG_STATE_HOME/chefkoch-cli/watch.json`; ist die Variable
  nicht gesetzt oder leer, `~/.local/state/chefkoch-cli/watch.json`.
- Verzeichnis `0700`, Datei `0600`, atomares Schreiben über eine Temp-Datei im
  selben Verzeichnis und `os.replace`.
- Weitere Config-Dateien gibt es nicht.

## 8. HTTP-Verhalten

- Nur `GET /v2/recipes` und `GET /v2/recipes/<id>`.
- Fester User-Agent `chefkoch-cli/0.1 (+https://github.com/smlfg/chefkoch-cli)`,
  `Accept: application/json`.
- `--timeout SEK` gilt pro Request, Default 15.
- Mindestens `CHEFKOCH_MIN_INTERVAL` Sekunden zwischen Requests desselben
  Prozesses (Default 1).
- Keine automatischen Retries bei 429/5xx.
- 404 bei Rezeptdetails → `not_found` (Exit 3); 404 bei der Suche → `http`
  (Exit 3). 200 mit ungültigem JSON → `parse` (Exit 4).
