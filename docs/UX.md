# UX-Spec: kurstool

Diese Datei ist die Vorlage für `docs/UX.md` in jedem neuen Repo. Sie wird vor der ersten Codezeile ausgefüllt. Alle Befehle sind so abtippbar, wie ein Mensch sie im Terminal eingibt. Beispielwerte (Tool `kurstool`, Kursnummern, Mails auf `.invalid`) werden durch die echten Werte des Projekts ersetzt.

Ablauf beim Ausfüllen:

1. Website live öffnen und die drei wichtigsten Aufgaben eines Menschen heraussuchen.
2. Jede Aufgabe als Sitzung mitschreiben: Befehl, Eingabe, erwartete Ausgabe.
3. Lesende Routen und alle Formularschritte der schreibenden Aktion ergänzen.
4. Fixtures unter `tests/fixtures/ux/` ablegen.
5. `python tests/harness/ux_check.py --spec-only` laufen lassen; erst bei grünem UX01 weiterbauen.

## Meta

Das Meta-Objekt benennt den Befehlsnamen im PATH, den Installationsbefehl und alle Umgebungsvariablen. `base_url_env` ist Pflicht, sobald es Routen oder Formsteps gibt. `credential_env` führt dazu, dass das Tool einen `login`-Befehl haben muss.

```ux-meta
{"tool": "kurstool",
 "install": "pipx install git+https://github.com/smlfg/kurstool-cli",
 "base_url_env": "KURSTOOL_BASE_URL",
 "env": {"KURSTOOL_STATUSGRUPPE": "studierende"},
 "credential_env": ["KURSTOOL_LOGIN_USER", "KURSTOOL_LOGIN_PASSWORD"]}
```

## Sitzungen

Jede Sitzung ist eine Nutzer-Aufgabe. Es müssen mindestens drei sein, darunter Login, Suche per Name und eine schreibende Aktion. `$` ist ein Befehl, `>` eine Eingabe, `<` eine erwartete Ausgabe und `!` der erwartete Exit-Code. Der Installationsbefehl wird von der Harness durch eine lokale Installation in ein frisches venv ersetzt.

### Installation und Login

Der Login fragt im Terminal interaktiv nach Benutzer und Passwort. Das Passwort wird nicht angezeigt und nicht gespeichert; die Sitzung landet im Schlüsselbund oder in einer Datei mit Rechten 0600. Die Zugangsdaten stammen aus einem Testkonto, nie aus echten Daten.

```ux-session
$ pipx install git+https://github.com/smlfg/kurstool-cli
< kurstool
$ kurstool login
< Benutzer:
> max.mustermann@example.invalid
< Passwort:
> geheim
< Login erfolgreich
! exit 0
```

### Kurse nach Namen suchen

Der Suchbegriff ist positional. Die Ausgabe zeigt Namen und Kursnummer, damit ein Mensch ohne Nachschlagen weiterarbeiten kann.

```ux-session
$ kurstool search volleyball
< 1) Volleyball Anfänger (Kurs 32304)
< 2) Volleyball Fortgeschritten (Kurs 32305)
! exit 0
```

### Kurs verbindlich buchen

Die schreibende Aktion zeigt zuerst Kurs, Ort und Preis. Danach fragt sie mit Default Nein. Erst nach `j` werden alle Formularschritte bis zur endgültigen Bestätigung gesendet. Bei `N` endet der Befehl ohne Request an einen Schritt ohne `before_confirm`.

```ux-session
$ kurstool book "Volleyball Anfänger"
< Kurs: Volleyball Anfänger (32304)
< Ort: Sporthalle Nord
< Preis: 25,00 EUR
< Buchung verbindlich? [j/N]
> j
< Buchung bestätigt
< Bestätigungsnummer: KB-2026-0042
! exit 0
```

## Lesende Routen

Hier stehen alle Routen, die die Sitzungen gegen den Fake-Server brauchen. `path` wird ohne Querystring exakt verglichen; `query_contains` ist optional. Der Login ist ein POST, löst aber keine Buchung aus und gehört deshalb zu den lesenden Routen. Die Antwortdateien liegen relativ zum Repo.

```ux-routes
[{"method":"POST","path":"/login","response":"tests/fixtures/ux/login_erfolg.html","status":200,"content_type":"text/html; charset=utf-8"},
 {"method":"GET","path":"/kurse","query_contains":"volleyball","response":"tests/fixtures/ux/kurse.html","status":200,"content_type":"text/html; charset=utf-8"},
 {"method":"GET","path":"/kurse/32304","response":"tests/fixtures/ux/kurs_32304.html","status":200,"content_type":"text/html; charset=utf-8"}]
```

## Formularschritte der schreibenden Aktion

Die Liste enthält ALLE Requests in Reihenfolge, bis die Buchung endgültig bestätigt ist. `sends` nennt Feldnamen, die im Body vorkommen müssen; ein `*` am Ende erlaubt Präfix-Treffer. `before_confirm: true` ist nur für Schritte erlaubt, die vor der `[j/N]`-Frage laufen und nichts verbindlich auslösen, zum Beispiel das Öffnen des Formulars. `live: erkundet` heißt lesend auf der echten Seite gesehen, `live: synthetisch` heißt nachgebaut und als solches markiert.

```ux-formsteps
[{"id":"formular_oeffnen","method":"POST","path":"/buchen/32304","sends":["kurs_id"],"response":"tests/fixtures/ux/buchen_formular.html","before_confirm":true,"live":"erkundet"},
 {"id":"teilnehmerdaten","method":"POST","path":"/buchen/32304","sends":["vorname","nachname","email","statusgruppe"],"response":"tests/fixtures/ux/buchen_uebersicht.html","live":"synthetisch"},
 {"id":"verbindlich","method":"POST","path":"/buchen/32304","sends":["bestaetigungstoken"],"response":"tests/fixtures/ux/buchen_bestaetigt.html","final":true,"live":"synthetisch"}]
```

Der letzte Schritt trägt `"final": true`. Fehlt ein Schritt oder endet die Aktion nach dem ersten Request, meldet `ux_check.py` UX08 und `ux_session.py` bricht den Lauf ab. Beide Gates müssen grün sein, bevor der Build als fertig gilt.
