"""Normalisierung der Chefkoch-API-Antworten."""

from __future__ import annotations

import math
from typing import Any

from .errors import ParseError

DIFFICULTY_LABELS = {1: "simpel", 2: "normal", 3: "pfiffig"}
TAG_VEGETARISCH = 32
TAG_VEGAN = 57


def _text(value: object, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def _number(value: object, default: float = 0.0) -> float:
    if value is None or isinstance(value, bool):
        return default
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(number):
        return default
    return number


def _integer(value: object, default: int = 0) -> int:
    number = _number(value, float(default))
    return int(number)


def _optional_amount(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number == 0:
        return None
    return number


def _rating_parts(value: object) -> tuple[float | None, int]:
    if isinstance(value, dict):
        rating = _number(value.get("rating"), 0.0)
        votes = _integer(value.get("numVotes"), 0)
        return (rating if value.get("rating") is not None else None), votes
    if value is None:
        return None, 0
    return _number(value, 0.0), 0


def difficulty_label(value: object) -> str:
    number = _integer(value, 0)
    return DIFFICULTY_LABELS.get(number, "")


def normalize_search_result(item: object) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise ParseError(
            "Die Suche hat einen unerwarteten Treffer geliefert.",
            next_step="Versuche es später erneut.",
        )
    recipe = item.get("recipe")
    if not isinstance(recipe, dict):
        recipe = item if "id" in item else {}
    if not recipe:
        raise ParseError(
            "Die Suche hat einen Treffer ohne Rezeptdaten geliefert.",
            next_step="Versuche es später erneut.",
        )
    rating, votes = _rating_parts(recipe.get("rating"))
    preparation = recipe.get("preparationTime")
    return {
        "id": _text(recipe.get("id")),
        "title": _text(recipe.get("title")),
        "subtitle": _text(recipe.get("subtitle")),
        "createdAt": _text(recipe.get("createdAt")),
        "difficulty": _integer(recipe.get("difficulty"), 0) or None,
        "difficultyLabel": difficulty_label(recipe.get("difficulty")),
        "preparationTime": _integer(preparation, 0) if preparation is not None else None,
        "rating": rating,
        "numVotes": votes,
        "siteUrl": _text(recipe.get("siteUrl")),
        "slug": _text(recipe.get("slug")),
        "vegetarian": None,
        "vegan": None,
    }


def normalize_search_payload(payload: dict[str, Any]) -> tuple[int, list[dict[str, Any]]]:
    results = payload.get("results")
    if not isinstance(results, list):
        raise ParseError(
            "Die Suchantwort der Chefkoch-API enthält keine Trefferliste.",
            next_step="Versuche es später erneut.",
        )
    count = _integer(payload.get("count"), len(results))
    return count, [normalize_search_result(item) for item in results]


def recipe_tag_ids(payload: dict[str, Any]) -> set[int]:
    ids: set[int] = set()
    full_tags = payload.get("fullTags")
    if isinstance(full_tags, list):
        for tag in full_tags:
            if isinstance(tag, dict) and tag.get("id") is not None:
                ids.add(_integer(tag.get("id"), 0))
    if ids:
        return ids
    names = payload.get("tags")
    if isinstance(names, list):
        folded = {_text(name).casefold() for name in names}
        if any("vegan" in name for name in folded):
            ids.update({TAG_VEGAN, TAG_VEGETARISCH})
        elif any("vegetarisch" in name for name in folded):
            ids.add(TAG_VEGETARISCH)
    return ids


def normalize_recipe(
    payload: dict[str, Any], requested_servings: int | None = None
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ParseError(
            "Die Rezeptantwort der Chefkoch-API ist kein Objekt.",
            next_step="Versuche es später erneut.",
        )
    servings = _integer(payload.get("servings"), 0)
    if requested_servings is None:
        requested = servings
    else:
        requested = int(requested_servings)
    if servings > 0:
        scale = requested / servings
    else:
        scale = 1.0

    groups: list[dict[str, Any]] = []
    raw_groups = payload.get("ingredientGroups")
    if isinstance(raw_groups, list):
        for group in raw_groups:
            if not isinstance(group, dict):
                continue
            ingredients: list[dict[str, Any]] = []
            raw_ingredients = group.get("ingredients")
            if isinstance(raw_ingredients, list):
                for ingredient in raw_ingredients:
                    if not isinstance(ingredient, dict):
                        continue
                    raw_amount = _optional_amount(ingredient.get("amount"))
                    amount = (
                        None if raw_amount is None else round(raw_amount * scale, 4)
                    )
                    ingredients.append(
                        {
                            "name": _text(ingredient.get("name")),
                            "amount": amount,
                            "unit": _text(ingredient.get("unit")),
                        }
                    )
            groups.append(
                {
                    "header": _text(group.get("header")),
                    "ingredients": ingredients,
                }
            )

    rating, votes = _rating_parts(payload.get("rating"))
    tags = payload.get("tags")
    return {
        "id": _text(payload.get("id")),
        "title": _text(payload.get("title")),
        "subtitle": _text(payload.get("subtitle")),
        "servings": servings,
        "requestedServings": requested,
        "scale": round(scale, 6),
        "rating": rating,
        "numVotes": votes,
        "difficulty": _integer(payload.get("difficulty"), 0) or None,
        "difficultyLabel": difficulty_label(payload.get("difficulty")),
        "preparationTime": _integer(payload.get("preparationTime"), 0),
        "cookingTime": _integer(payload.get("cookingTime"), 0),
        "restingTime": _integer(payload.get("restingTime"), 0),
        "totalTime": _integer(payload.get("totalTime"), 0),
        "siteUrl": _text(payload.get("siteUrl")),
        "instructions": _text(payload.get("instructions")),
        "tags": [str(tag) for tag in tags] if isinstance(tags, list) else [],
        "ingredientGroups": groups,
    }
