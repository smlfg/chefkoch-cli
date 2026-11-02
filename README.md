# chefkoch-cli

Chefkoch.de-Rezepte im Terminal: Suche mit Filtern, Rezeptdetails mit auf
Portionen skalierten Zutaten, Einkaufsliste aus mehreren Rezepten und Watch auf
neue Rezepte. Ausschließlich lesend, ohne Login.

## Schnellstart

Voraussetzung: Python 3.10+ und `pipx`.

```bash
pipx install git+https://github.com/smlfg/chefkoch-cli
chefkoch suche lasagne --limit 5
chefkoch rezept "vegane lasagne" --portionen 4
chefkoch einkaufsliste "die ultimative vegane lasagne" "vegetarische spinat gemüse lasagne" --portionen 4
```

Die Suche nimmt den Begriff positional. `chefkoch rezept` und
`chefkoch einkaufsliste` akzeptieren Namen, IDs oder Chefkoch-URLs; bei
mehreren Treffern erscheint im Terminal eine nummerierte Auswahl.

## Befehle und Beispiele

### Suchen

```bash
chefkoch suche lasagne --limit 5
chefkoch suche chili --vegetarisch --max-zeit 30 --min-bewertung 4.5
chefkoch suche suppe --vegan --sort zeit
chefkoch suche kuchen --sort neu --limit 10 --seite 2
```

Filter: `--vegetarisch`, `--vegan`, `--max-zeit N`, `--min-bewertung X`,
`--schwierigkeit simpel|normal|pfiffig`, `--sort bewertung|zeit|neu`,
`--limit N`, `--seite N`.

### Rezept anzeigen

```bash
chefkoch rezept "vegane lasagne" --portionen 4
chefkoch rezept 745721177147257
chefkoch rezept https://www.chefkoch.de/rezepte/745721177147257/Lasagne.html --portionen 8
```

Ein Name sucht und zeigt bei mehreren Treffern eine nummerierte Auswahl. Eine
ID oder URL lädt das Rezept direkt. `--portionen` skaliert die Zutaten.

### Einkaufsliste

```bash
chefkoch einkaufsliste "die ultimative vegane lasagne" "vegetarische spinat gemüse lasagne" --portionen 4
```

Mehrere Namen, IDs oder URLs ergeben eine zusammengefasste Liste. Gleiche
Zutaten mit gleicher Einheit werden summiert, unterschiedliche Einheiten
bleiben getrennt.

### Watch

```bash
chefkoch watch "vegane lasagne" --min-bewertung 4.5
```

Watch merkt sich die zuletzt gesehenen IDs pro Suchbegriff und Filter und zeigt
beim nächsten Lauf nur neue Treffer.

## Ausgabe und JSON

Im Terminal ist die Ausgabe lesbar (Trefferliste, Rezept, Einkaufsliste). JSON
erscheint nur mit `--json` oder wenn stdout kein Terminal ist. Im JSON-Modus
steht genau ein Objekt auf stdout, auch bei Fehlern:

```bash
chefkoch suche lasagne --limit 5 --json
chefkoch rezept "vegane lasagne" --json
```

## Konfiguration

| Variable | Default | Bedeutung |
|---|---|---|
| `CHEFKOCH_BASE_URL` | `https://api.chefkoch.de` | API-Basis (Test/Fake-Server) |
| `CHEFKOCH_MIN_INTERVAL` | `1` | Mindestabstand zwischen Requests in Sekunden; `0` nur für Tests |
| `XDG_STATE_HOME` | `~/.local/state` | Basis für den Watch-State |

Der Watch-State liegt unter
`$XDG_STATE_HOME/chefkoch-cli/watch.json` (Fallback
`~/.local/state/chefkoch-cli/watch.json`) und enthält nur IDs, Suchschlüssel
und Zeitstempel. Weitere Config-Dateien gibt es nicht.

## Exit-Codes

| Exit | Bedeutung |
|---|---|
| 0 | Erfolg, inklusive `--help` und `--version` |
| 1 | Allgemeiner Fehler (z. B. kaputter Watch-State) |
| 2 | Usage: fehlende/ungültige Argumente, mehrdeutiger Name ohne TTY |
| 3 | Netz/Quelle: Timeout, HTTP-Fehler, Rezept-404, keine Treffer |
| 4 | Login erforderlich (nicht verwendet) bzw. Daten-/Parse-Fehler |

## Datenquelle und Grenzen

`chefkoch` nutzt die inoffizielle API `https://api.chefkoch.de` über
`GET /v2/recipes` und `GET /v2/recipes/<id>`. Die Website
`www.chefkoch.de/rezepte/*?*` und `/v2/search/suggestions` werden nicht
abgerufen. Das Tool sendet keine Cookies, speichert keine Zugangsdaten und
führt keine schreibenden Web-Aktionen aus.

Die API ist nicht offiziell dokumentiert und kann sich jederzeit ändern.
Details und Befehlsvertrag stehen in `ANFORDERUNGEN.md`, `INTERFACE.md` und
`docs/UX.md`.

## Lizenz

MIT, Copyright smlfg. Siehe `LICENSE`.
