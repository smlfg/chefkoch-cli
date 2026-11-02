# UX-Spec: chefkoch

`chefkoch` liest Rezepte von Chefkoch.de im Terminal: Suche mit Filtern,
Rezeptdetails mit auf Portionen skalierten Zutaten, Einkaufsliste aus mehreren
Rezepten und Watch auf neue Treffer. Das Tool ist ausschließlich lesend. Es
gibt keinen Login, keine schreibende Web-Aktion und deshalb auch keine
`ux-formsteps`.

Alle Befehle sind so abtippbar, wie ein Mensch sie im Terminal eingibt.
Ausgaben im Terminal sind lesbar; JSON erscheint nur mit `--json` oder wenn
stdout kein TTY ist. Die Sitzungen unten laufen im TTY und erwarten die
lesbare Form.

## Meta

`CHEFKOCH_BASE_URL` überschreibt die API-Basis (Standard
`https://api.chefkoch.de`) und wird von der Harness auf den Fake-Server
gesetzt. `CHEFKOCH_MIN_INTERVAL=0` schaltet den Mindestabstand von einer
Sekunde zwischen Requests nur für Tests ab.

```ux-meta
{"tool": "chefkoch",
 "install": "pipx install git+https://github.com/smlfg/chefkoch-cli",
 "base_url_env": "CHEFKOCH_BASE_URL",
 "env": {"CHEFKOCH_MIN_INTERVAL": "0"}}
```

## Sitzungen

### Installation und erste Suche

`pipx` legt den Befehl `chefkoch` in den PATH. Der erste Befehl sucht
positional nach einem Begriff und zeigt eine lesbare Trefferliste mit ID,
Bewertung, Zubereitungszeit und Schwierigkeit. Die Standardsortierung ist
Bewertung absteigend.

```ux-session
$ pipx install git+https://github.com/smlfg/chefkoch-cli
$ chefkoch suche lasagne --limit 5
< 1) Lasagne (ID 745721177147257) · 4,7★ · 30 Min. · normal
< 2) Italienische Lasagne (ID 491931143472316) · 4,6★ · 60 Min. · normal
< 3) Lasagne Bolognese (ID 1112181217260303) · 4,6★ · 60 Min. · normal
< 4) Béchamel-Hackfleisch-Lasagne (ID 555661153310338) · 4,6★ · 25 Min. · normal
< 5) Idiotensichere Lasagne (ID 484751142525322) · 4,5★ · 20 Min. · normal
! exit 0
```

### Rezept per Name mit Auswahl und Portionen

`chefkoch rezept "vegane lasagne"` sucht per Name. Bei mehreren Treffern
erscheint im TTY eine nummerierte Auswahl. Nach der Eingabe zeigt das Tool das
gewählte Rezept; die Zutaten sind auf vier Portionen skaliert (Basis acht).
Bewertungen haben eine Nachkommastelle, Mengen höchstens zwei und werden mit
Komma ausgegeben.

```ux-session
$ chefkoch rezept "vegane lasagne" --portionen 4
< 1) Vegane Gemüselasagne (ID 3824501582218163) · 4,8★ · 20 Min. · normal
< 2) Die ultimative vegane Lasagne (ID 2812481433250378) · 4,7★ · 45 Min. · normal
< 3) Vegane Gemüselasagne (ID 2580281404670704) · 4,5★ · 30 Min. · simpel
< 4) Vegane Bolognese-Lasagne (ID 2617931411122824) · 4,3★ · 30 Min. · normal
< 5) Gesunde Lasagne mit veganer Bechamelsoße (ID 3322271493312524) · 4,3★ · 30 Min. · normal
< Auswahl [1-5]:
> 2
< Die ultimative vegane Lasagne
< Portionen: 4 (Basis: 8)
< 125 g Naturtofu
< 125 g Räuchertofu
! exit 0
```

### Einkaufsliste aus zwei Rezepten per Name

Der erste Name ist eindeutig. Der zweite liefert mehrere Treffer; nach der
Auswahl werden beide Rezepte auf vier Portionen skaliert und die Zutaten
zusammengefasst. Gleiche Name+Einheit werden summiert, hier
`Knoblauchzehe(n)` aus beiden Rezepten. Andere Einheiten bleiben getrennt.

```ux-session
$ chefkoch einkaufsliste "die ultimative vegane lasagne" "vegetarische spinat gemüse lasagne" --portionen 4
< 1) Vegetarische Spinat-Gemüse-Lasagne mit Tomatensoße (ID 2114131340630587) · 4,8★ · 25 Min. · normal
< 2) Spinat - Tomaten - Lasagne (ID 1191361224959138) · 4,7★ · 40 Min. · normal
< 3) Vegane Spinat-Tomaten-Lasagne (ID 3340981496420766) · 4,3★ · 45 Min. · normal
< 4) Vegetarische Spinat-Tomaten-Lasagne (ID 2356391374557463) · 4,3★ · 60 Min. · normal
< 5) Grüne Lasagne (ID 950811200586076) · 4,0★ · 45 Min. · normal
< Auswahl [1-5]:
> 1
< Einkaufsliste (4 Portionen je Rezept)
< 4,67 Knoblauchzehe(n)
< 266,67 g Käse, geriebener
< 125 g Naturtofu
! exit 0
```

## Lesende Routen

Alle Sitzungen brauchen nur `GET /v2/recipes` und `GET /v2/recipes/<id>`.
Spezifischere Suchrouten stehen vor allgemeineren, weil der Fake-Server die
erste passende Route nimmt. Die Antworten sind echte Live-Antworten, auf die
benötigten Felder gekürzt und anonymisiert; Owner-, Editor- und Avatar-Felder
fehlen.

```ux-routes
[{"method":"GET","path":"/v2/recipes","query_contains":"ultimative","response":"tests/fixtures/ux/search_ultimative_vegane_lasagne.json","status":200,"content_type":"application/json"},
 {"method":"GET","path":"/v2/recipes","query_contains":"spinat","response":"tests/fixtures/ux/search_vegetarische_spinat_lasagne.json","status":200,"content_type":"application/json"},
 {"method":"GET","path":"/v2/recipes","query_contains":"vegane","response":"tests/fixtures/ux/search_vegane_lasagne.json","status":200,"content_type":"application/json"},
 {"method":"GET","path":"/v2/recipes","query_contains":"lasagne","response":"tests/fixtures/ux/search_lasagne.json","status":200,"content_type":"application/json"},
 {"method":"GET","path":"/v2/recipes/2812481433250378","response":"tests/fixtures/ux/recipe_2812481433250378.json","status":200,"content_type":"application/json"},
 {"method":"GET","path":"/v2/recipes/2114131340630587","response":"tests/fixtures/ux/recipe_2114131340630587.json","status":200,"content_type":"application/json"}]
```

## Schreibende Aktion

Es gibt keine. `chefkoch` ist read-only, benötigt keinen Login und sendet
keine POST-/PUT-/DELETE-Requests. Damit entfallen `ux-formsteps` und
`credential_env`.
