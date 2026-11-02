"""Fachlogik: Suche, Namensauflösung, Skalierung und Einkaufsliste."""

from __future__ import annotations

import re
import unicodedata
from typing import Any
from urllib.parse import urlsplit

from .client import ApiClient
from .errors import NoResultsError, NotFoundError, UsageError
from .parsing import (
    TAG_VEGAN,
    TAG_VEGETARISCH,
    normalize_recipe,
    normalize_search_payload,
    recipe_tag_ids,
)

SEARCH_WINDOW = 500
LOOKUP_LIMIT = 10
DEFAULT_LIMIT = 10
DEFAULT_WATCH_LIMIT = 50
SORT_CHOICES = ("bewertung", "zeit", "neu")
DIFFICULTIES = {"simpel": 1, "normal": 2, "pfiffig": 3}
CHEFKOCH_HOSTS = {"www.chefkoch.de", "chefkoch.de"}


def _validate_limit(value: int, name: str = "--limit") -> int:
    if value < 1 or value > 100:
        raise UsageError(
            f"{name} muss zwischen 1 und 100 liegen.",
            next_step="Beispiel: --limit 10",
        )
    return value


def _validate_page(value: int) -> int:
    if value < 1:
        raise UsageError(
            "--seite muss mindestens 1 sein.",
            next_step="Beispiel: --seite 1",
        )
    return value


def _validate_max_time(value: int | None) -> int | None:
    if value is not None and value < 0:
        raise UsageError(
            "--max-zeit darf nicht negativ sein.",
            next_step="Beispiel: --max-zeit 30",
        )
    return value


def _validate_min_rating(value: float | None) -> float | None:
    if value is None:
        return None
    if value < 0 or value > 5:
        raise UsageError(
            "--min-bewertung muss zwischen 0 und 5 liegen.",
            next_step="Beispiel: --min-bewertung 4.5",
        )
    return value


def _validate_difficulty(value: str | None) -> int | None:
    if value is None:
        return None
    if value not in DIFFICULTIES:
        raise UsageError(
            f"Unbekannte Schwierigkeit: {value!r}.",
            next_step="Erlaubt sind simpel, normal oder pfiffig.",
        )
    return DIFFICULTIES[value]


def sort_results(items: list[dict[str, Any]], sort: str) -> list[dict[str, Any]]:
    if sort not in SORT_CHOICES:
        raise UsageError(
            f"Unbekannte Sortierung: {sort!r}.",
            next_step="Erlaubt sind bewertung, zeit oder neu.",
        )
    if sort == "zeit":
        return sorted(
            items,
            key=lambda item: (
                item.get("preparationTime")
                if item.get("preparationTime") is not None
                else float("inf"),
                -(item.get("rating") or 0.0),
            ),
        )
    if sort == "neu":
        return sorted(
            items,
            key=lambda item: (
                str(item.get("createdAt") or ""),
                str(item.get("id") or ""),
            ),
            reverse=True,
        )
    return sorted(
        items,
        key=lambda item: (
            -(item.get("rating") or 0.0),
            -int(item.get("numVotes") or 0),
            str(item.get("title") or "").casefold(),
        ),
    )


def search_recipes(
    client: ApiClient,
    query: str,
    *,
    vegetarisch: bool = False,
    vegan: bool = False,
    max_zeit: int | None = None,
    min_bewertung: float | None = None,
    schwierigkeit: str | None = None,
    sort: str = "bewertung",
    limit: int = DEFAULT_LIMIT,
    seite: int = 1,
) -> dict[str, Any]:
    text = str(query or "").strip()
    if not text:
        raise UsageError(
            "Der Suchbegriff fehlt.",
            next_step="Beispiel: chefkoch suche lasagne",
        )
    _validate_limit(limit)
    _validate_page(seite)
    _validate_max_time(max_zeit)
    _validate_min_rating(min_bewertung)
    difficulty = _validate_difficulty(schwierigkeit)
    if sort not in SORT_CHOICES:
        raise UsageError(
            f"Unbekannte Sortierung: {sort!r}.",
            next_step="Erlaubt sind bewertung, zeit oder neu.",
        )

    tags = TAG_VEGAN if vegan else TAG_VEGETARISCH if vegetarisch else None
    payload = client.search(
        text,
        limit=SEARCH_WINDOW,
        offset=0,
        minimum_rating=min_bewertung,
        maximum_time=max_zeit,
        tags=tags,
    )
    count, items = normalize_search_payload(payload)

    filtered: list[dict[str, Any]] = []
    for item in items:
        if max_zeit is not None:
            preparation = item.get("preparationTime")
            if preparation is None or preparation > max_zeit:
                continue
        if min_bewertung is not None:
            rating = item.get("rating")
            if rating is None or rating < min_bewertung:
                continue
        if difficulty is not None and item.get("difficulty") != difficulty:
            continue
        filtered.append(item)

    filtered = sort_results(filtered, sort)

    if tags is not None:
        wanted = {tags}
        need = limit * seite
        verified: list[dict[str, Any]] = []
        for item in filtered:
            if len(verified) >= need:
                break
            try:
                detail = client.recipe(str(item.get("id")))
            except NotFoundError:
                continue
            detail_tags = recipe_tag_ids(detail)
            if not wanted.issubset(detail_tags):
                continue
            item = dict(item)
            item["vegetarian"] = TAG_VEGETARISCH in detail_tags
            item["vegan"] = TAG_VEGAN in detail_tags
            verified.append(item)
        filtered = verified

    page_items = filtered[(seite - 1) * limit : seite * limit]
    if not page_items:
        raise NoResultsError(
            f"Keine Treffer für {text!r} mit diesen Filtern.",
            next_step="Entferne einen Filter oder nutze einen anderen Suchbegriff.",
        )

    return {
        "query": text,
        "page": seite,
        "limit": limit,
        "total": count,
        "count": len(page_items),
        "results": page_items,
    }


def search_candidates(client: ApiClient, name: str) -> list[dict[str, Any]]:
    text = str(name or "").strip()
    if not text:
        raise UsageError(
            "Der Rezeptname fehlt.",
            next_step="Beispiel: chefkoch rezept \"vegane lasagne\"",
        )
    payload = client.search(text, limit=LOOKUP_LIMIT)
    _count, items = normalize_search_payload(payload)
    return sort_results(items, "bewertung")


_URL_RE = re.compile(r"^/rezepte/(\d+)(?:/[^/]*)?$")


def parse_recipe_reference(value: str) -> tuple[str, str]:
    text = str(value or "").strip()
    if not text:
        raise UsageError(
            "Die Rezeptangabe fehlt.",
            next_step="Nutze einen Namen, eine ID oder eine Chefkoch-URL.",
        )
    if text.isdigit():
        return "id", text

    candidate = text
    if "://" not in candidate and (
        candidate.startswith("www.") or candidate.startswith("chefkoch.de/")
    ):
        candidate = "https://" + candidate
    if "://" in candidate:
        parts = urlsplit(candidate)
        if parts.scheme not in {"http", "https"}:
            raise UsageError(
                f"Ungültige URL: {text!r}.",
                next_step="Nutze eine https://www.chefkoch.de/rezepte/<id>/... URL.",
            )
        host = (parts.hostname or "").lower()
        if host not in CHEFKOCH_HOSTS:
            raise UsageError(
                f"Fremder Host in der URL: {host or text!r}.",
                next_step="Nutze eine URL von www.chefkoch.de.",
            )
        match = _URL_RE.match(parts.path)
        if not match:
            raise UsageError(
                f"Die URL enthält keine Rezept-ID: {text!r}.",
                next_step="Nutze eine URL der Form https://www.chefkoch.de/rezepte/<id>/...",
            )
        return "id", match.group(1)
    return "name", text


def validate_servings(value: int | None) -> int | None:
    if value is None:
        return None
    if value < 1:
        raise UsageError(
            "--portionen muss mindestens 1 sein.",
            next_step="Beispiel: --portionen 4",
        )
    return value


def _normalize_key(value: object) -> str:
    text = unicodedata.normalize("NFC", str(value or ""))
    text = " ".join(text.split())
    return text.casefold()


def build_shopping_list(
    recipes: list[dict[str, Any]], portions: int | None
) -> dict[str, Any]:
    aggregates: dict[tuple[str, str], dict[str, Any]] = {}
    recipe_rows: list[dict[str, Any]] = []
    for recipe in recipes:
        recipe_rows.append(
            {
                "id": recipe.get("id"),
                "servings": recipe.get("servings"),
                "requestedServings": recipe.get("requestedServings"),
            }
        )
        recipe_id = str(recipe.get("id") or "")
        for group in recipe.get("ingredientGroups") or []:
            for ingredient in group.get("ingredients") or []:
                name = str(ingredient.get("name") or "").strip()
                unit = str(ingredient.get("unit") or "").strip()
                key = (_normalize_key(name), _normalize_key(unit))
                entry = aggregates.get(key)
                if entry is None:
                    entry = {
                        "name": name,
                        "unit": unit,
                        "amount": 0.0,
                        "recipeIds": [],
                    }
                    aggregates[key] = entry
                entry["amount"] += float(ingredient.get("amount") or 0.0)
                if recipe_id and recipe_id not in entry["recipeIds"]:
                    entry["recipeIds"].append(recipe_id)

    items = sorted(
        aggregates.values(),
        key=lambda entry: (
            str(entry["name"]).casefold(),
            str(entry["unit"]).casefold(),
        ),
    )
    for entry in items:
        entry["amount"] = round(entry["amount"], 2)
    return {"recipes": recipe_rows, "items": items}


def load_recipe(
    client: ApiClient, reference: str, requested_servings: int | None
) -> dict[str, Any]:
    """Lädt ein Rezept per Name, ID oder URL ohne interaktive Auswahl."""
    kind, value = parse_recipe_reference(reference)
    if kind == "name":
        candidates = search_candidates(client, value)
        if not candidates:
            raise NoResultsError(
                f"Kein Rezept zu {value!r} gefunden.",
                next_step="Nutze einen anderen Namen oder `chefkoch suche ...`.",
            )
        if len(candidates) > 1:
            raise UsageError(
                f"Der Name {value!r} ist mehrdeutig.",
                next_step="Nutze eine ID/URL oder die interaktive Auswahl im Terminal.",
            )
        recipe_id = str(candidates[0]["id"])
    else:
        recipe_id = value
    payload = client.recipe(recipe_id)
    return normalize_recipe(payload, requested_servings)
