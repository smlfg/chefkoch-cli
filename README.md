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

## Befehle

- `chefkoch suche BEGRIFF [--vegetarisch|--vegan] [--max-zeit N] [--min-bewertung X] [--schwierigkeit ...] [--sort ...] [--limit N] [--seite N]`
- `chefkoch rezept NAME|ID|URL [--portionen N]`
- `chefkoch einkaufsliste NAME|ID|URL... [--portionen N]`
- `chefkoch watch BEGRIFF [Filter]`

`--json` liefert genau ein JSON-Objekt, auch bei Fehlern. Ohne `--json` und
außerhalb eines Terminals wird ebenfalls JSON ausgegeben.

## Lizenz

MIT, Copyright smlfg.
