"""Kommandozeilenschnittstelle für chefkoch."""

from __future__ import annotations

import argparse
import json
import math
import sys
from typing import Any, Sequence

from . import __version__, service
from .client import ApiClient
from .errors import (
    CliError,
    NoResultsError,
    UsageError,
    UserAbortError,
)
from .formatting import format_recipe_text, format_search_line, format_shopping_text
from .parsing import normalize_recipe
from .watch import run_watch


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:  # type: ignore[override]
        raise UsageError(
            message,
            next_step="Nutze `chefkoch --help` für die Übersicht.",
        )


def _common_options() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--json",
        action="store_true",
        default=argparse.SUPPRESS,
        help="JSON auf stdout ausgeben",
    )
    common.add_argument(
        "--timeout",
        type=float,
        default=argparse.SUPPRESS,
        metavar="SEK",
        help="Timeout pro Request in Sekunden (Default 15)",
    )
    return common


def _add_search_filters(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--vegetarisch",
        action="store_true",
        help="nur vegetarische Rezepte",
    )
    group.add_argument(
        "--vegan",
        action="store_true",
        help="nur vegane Rezepte",
    )
    parser.add_argument(
        "--max-zeit",
        type=int,
        default=None,
        metavar="MIN",
        help="maximale Zubereitungszeit in Minuten",
    )
    parser.add_argument(
        "--min-bewertung",
        type=float,
        default=None,
        metavar="X",
        help="minimale Bewertung (0 bis 5)",
    )
    parser.add_argument(
        "--schwierigkeit",
        choices=("simpel", "normal", "pfiffig"),
        default=None,
        help="Schwierigkeitsgrad",
    )


def build_parser() -> argparse.ArgumentParser:
    common = _common_options()
    parser = _Parser(
        prog="chefkoch",
        description="Chefkoch.de-Rezepte im Terminal: Suchen, Anzeigen, Einkaufsliste, Watch.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"chefkoch-cli {__version__}",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="JSON auf stdout ausgeben",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=15.0,
        metavar="SEK",
        help="Timeout pro Request in Sekunden (Default 15)",
    )
    subparsers = parser.add_subparsers(dest="command", metavar="BEFEHL")

    suche = subparsers.add_parser(
        "suche",
        parents=[common],
        help="Rezepte nach einem Begriff suchen",
        description="Rezepte nach einem Begriff suchen und filtern.",
    )
    suche.add_argument("begriff", help="Suchbegriff")
    _add_search_filters(suche)
    suche.add_argument(
        "--sort",
        choices=service.SORT_CHOICES,
        default="bewertung",
        help="Sortierung (Default bewertung)",
    )
    suche.add_argument(
        "--limit",
        type=int,
        default=service.DEFAULT_LIMIT,
        metavar="N",
        help="Treffer pro Seite (Default 10)",
    )
    suche.add_argument(
        "--seite",
        type=int,
        default=1,
        metavar="N",
        help="Seite (Default 1)",
    )

    rezept = subparsers.add_parser(
        "rezept",
        parents=[common],
        help="Ein Rezept per Name, ID oder URL anzeigen",
        description="Ein Rezept anzeigen und Zutaten auf Portionen skalieren.",
    )
    rezept.add_argument("referenz", metavar="NAME|ID|URL", help="Rezeptname, ID oder URL")
    rezept.add_argument(
        "--portionen",
        type=int,
        default=None,
        metavar="N",
        help="Zielportionen (Default: Portionen des Rezepts)",
    )

    einkauf = subparsers.add_parser(
        "einkaufsliste",
        parents=[common],
        help="Einkaufsliste aus mehreren Rezepten erzeugen",
        description="Zutaten mehrerer Rezepte skalieren und zusammenfassen.",
    )
    einkauf.add_argument(
        "referenzen",
        nargs="+",
        metavar="NAME|ID|URL",
        help="Rezeptnamen, IDs oder URLs",
    )
    einkauf.add_argument(
        "--portionen",
        type=int,
        default=None,
        metavar="N",
        help="Zielportionen für jedes Rezept",
    )

    watch = subparsers.add_parser(
        "watch",
        parents=[common],
        help="Neue Treffer zu einem Suchbegriff verfolgen",
        description="Treffer merken und beim nächsten Lauf neue Rezepte zeigen.",
    )
    watch.add_argument("begriff", help="Suchbegriff")
    _add_search_filters(watch)
    watch.add_argument(
        "--limit",
        type=int,
        default=service.DEFAULT_WATCH_LIMIT,
        metavar="N",
        help="höchstens N Treffer betrachten (Default 50)",
    )
    return parser


def _validated_timeout(value: object) -> float:
    try:
        timeout = float(value)
    except (TypeError, ValueError):
        raise UsageError(
            f"--timeout ist keine Zahl: {value!r}.",
            next_step="Beispiel: --timeout 15",
        ) from None
    if not math.isfinite(timeout) or timeout <= 0:
        raise UsageError(
            f"--timeout muss eine endliche Zahl > 0 sein: {value!r}.",
            next_step="Beispiel: --timeout 15",
        )
    return timeout


def _emit_success(
    command: str, data: dict[str, Any], text: str, json_mode: bool
) -> None:
    if json_mode:
        print(
            json.dumps(
                {"ok": True, "command": command, "data": data},
                ensure_ascii=False,
            )
        )
    else:
        print(text)


def _emit_error(error: CliError, json_mode: bool) -> int:
    message = error.full_message()
    if json_mode:
        print(
            json.dumps(
                {"ok": False, "error": {"type": error.error_type, "message": message}},
                ensure_ascii=False,
            )
        )
    else:
        print(f"Fehler: {message}", file=sys.stderr)
    return error.exit_code


def _search_text(data: dict[str, Any]) -> str:
    return "\n".join(
        format_search_line(index, item)
        for index, item in enumerate(data.get("results") or [], start=1)
    )


def _watch_text(data: dict[str, Any]) -> str:
    query = data.get("query") or ""
    results = list(data.get("new") or [])
    if not results:
        return f"Keine neuen Rezepte für {query!r}."
    return "\n".join(
        [f"Neue Rezepte für {query!r}:", _result_list_text(results)]
    )


def _result_list_text(results: Sequence[dict[str, Any]]) -> str:
    return "\n".join(
        format_search_line(index, item)
        for index, item in enumerate(results, start=1)
    )


def choose_result(
    results: list[dict[str, Any]],
    *,
    json_mode: bool,
    query: str,
) -> dict[str, Any]:
    if not results:
        raise NoResultsError(
            f"Kein Rezept zu {query!r} gefunden.",
            next_step="Nutze einen anderen Namen oder `chefkoch suche ...`.",
        )
    if len(results) == 1:
        return results[0]

    listing = _result_list_text(results)
    interactive = sys.stdin.isatty() and sys.stdout.isatty()
    if not interactive:
        print(listing, file=sys.stderr)
        raise UsageError(
            f"Der Name {query!r} ist mehrdeutig ({len(results)} Treffer).",
            next_step="Nutze eine ID/URL oder starte den Befehl im Terminal.",
        )

    print(listing, file=sys.stderr if json_mode else sys.stdout)
    while True:
        print(
            f"Auswahl [1-{len(results)}]: ",
            end="",
            file=sys.stderr,
            flush=True,
        )
        try:
            answer = sys.stdin.readline()
        except KeyboardInterrupt:
            raise UserAbortError(
                "Auswahl abgebrochen.",
                next_step="Starte den Befehl erneut und wähle eine Nummer.",
            ) from None
        if answer == "":
            raise UserAbortError(
                "Auswahl abgebrochen (EOF).",
                next_step="Starte den Befehl erneut und wähle eine Nummer.",
            )
        answer = answer.strip()
        if answer.isdigit() and 1 <= int(answer) <= len(results):
            return results[int(answer) - 1]
        print(
            f"Bitte eine Zahl von 1 bis {len(results)} eingeben.",
            file=sys.stderr,
        )


def _fetch_recipe(
    client: ApiClient,
    reference: str,
    requested_servings: int | None,
    *,
    json_mode: bool,
) -> dict[str, Any]:
    kind, value = service.parse_recipe_reference(reference)
    if kind == "name":
        results = service.search_candidates(client, value)
        chosen = choose_result(results, json_mode=json_mode, query=value)
        recipe_id = str(chosen.get("id"))
    else:
        recipe_id = value
    payload = client.recipe(recipe_id)
    return normalize_recipe(payload, requested_servings)


def _run(args: argparse.Namespace, timeout: float, json_mode: bool) -> None:
    if args.command == "suche":
        with ApiClient(timeout=timeout) as client:
            data = service.search_recipes(
                client,
                args.begriff,
                vegetarisch=args.vegetarisch,
                vegan=args.vegan,
                max_zeit=args.max_zeit,
                min_bewertung=args.min_bewertung,
                schwierigkeit=args.schwierigkeit,
                sort=args.sort,
                limit=args.limit,
                seite=args.seite,
            )
        _emit_success("suche", data, _search_text(data), json_mode)
        return
    if args.command == "rezept":
        portions = service.validate_servings(args.portionen)
        with ApiClient(timeout=timeout) as client:
            recipe = _fetch_recipe(
                client,
                args.referenz,
                portions,
                json_mode=json_mode,
            )
        _emit_success("rezept", recipe, format_recipe_text(recipe), json_mode)
        return
    if args.command == "einkaufsliste":
        portions = service.validate_servings(args.portionen)
        recipes: list[dict[str, Any]] = []
        with ApiClient(timeout=timeout) as client:
            for reference in args.referenzen:
                recipes.append(
                    _fetch_recipe(
                        client,
                        reference,
                        portions,
                        json_mode=json_mode,
                    )
                )
        data = service.build_shopping_list(recipes, portions)
        _emit_success(
            "einkaufsliste",
            data,
            format_shopping_text(data["items"], portions),
            json_mode,
        )
        return
    if args.command == "watch":
        with ApiClient(timeout=timeout) as client:
            data = run_watch(
                client,
                args.begriff,
                vegetarisch=args.vegetarisch,
                vegan=args.vegan,
                max_zeit=args.max_zeit,
                min_bewertung=args.min_bewertung,
                schwierigkeit=args.schwierigkeit,
                limit=args.limit,
            )
        _emit_success("watch", data, _watch_text(data), json_mode)
        return
    raise UsageError(
        "Unbekanntes Unterkommando.",
        next_step="Nutze `chefkoch --help` für die Übersicht.",
    )


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    json_mode = "--json" in arguments or not sys.stdout.isatty()
    try:
        parser = build_parser()
        args = parser.parse_args(arguments)
        json_mode = bool(getattr(args, "json", False)) or not sys.stdout.isatty()
        if not getattr(args, "command", None):
            raise UsageError(
                "Es fehlt ein Unterkommando.",
                next_step="Nutze `chefkoch --help` für die Übersicht.",
            )
        timeout = _validated_timeout(getattr(args, "timeout", 15.0))
        _run(args, timeout, json_mode)
        return 0
    except SystemExit as exc:
        code = exc.code
        if code is None:
            return 0
        if isinstance(code, int):
            return code
        return 2
    except KeyboardInterrupt:
        return _emit_error(
            UserAbortError(
                "Abgebrochen.",
                next_step="Starte den Befehl erneut.",
            ),
            json_mode,
        )
    except CliError as exc:
        return _emit_error(exc, json_mode)
    except BrokenPipeError:
        try:
            sys.stdout.close()
        except OSError:
            pass
        return 1
    except Exception as exc:  # noqa: BLE001 - nie Tracebacks nach außen
        return _emit_error(
            CliError(
                f"Unerwarteter Fehler: {exc}",
                next_step="Versuche es erneut oder prüfe `chefkoch --help`.",
            ),
            json_mode,
        )


__all__ = ["main", "build_parser", "choose_result", "format_recipe_text", "format_shopping_text"]
