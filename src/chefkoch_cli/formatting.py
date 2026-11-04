"""Lesbare Terminal-Ausgabe und Zahlenformatierung."""

from __future__ import annotations

import math
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any


def format_amount(value: object) -> str:
    if value is None or isinstance(value, bool):
        return "0"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "0"
    if not math.isfinite(number):
        return "0"
    try:
        rounded = Decimal(str(number)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
    except (InvalidOperation, ValueError):
        return "0"
    text = format(rounded, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    if text in {"", "-0"}:
        text = "0"
    return text.replace(".", ",")


def format_rating(value: object) -> str:
    if value is None:
        return "–"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "–"
    if not math.isfinite(number):
        return "–"
    return f"{number:.1f}".replace(".", ",")


def format_minutes(value: object) -> str:
    if value is None:
        return "? Min."
    try:
        number = int(value)
    except (TypeError, ValueError):
        return "? Min."
    return f"{number} Min."


def _difficulty(value: object) -> str:
    text = str(value or "").strip()
    return text or "?"


def format_search_line(index: int, item: dict[str, Any]) -> str:
    title = str(item.get("title") or "Ohne Titel")
    recipe_id = str(item.get("id") or "?")
    rating = format_rating(item.get("rating"))
    preparation = format_minutes(item.get("preparationTime"))
    difficulty = _difficulty(item.get("difficultyLabel"))
    return f"{index}) {title} (ID {recipe_id}) · {rating}★ · {preparation} · {difficulty}"


def _amount_text(value: object) -> str:
    if value is None:
        return ""
    text = format_amount(value)
    return "" if text == "0" else text


def _ingredient_line(name: str, unit: str, amount: object) -> str:
    parts = (_amount_text(amount), unit, name)
    return " ".join(part for part in parts if part).strip()


def format_ingredient(ingredient: dict[str, Any]) -> str:
    name = str(ingredient.get("name") or "").strip()
    unit = str(ingredient.get("unit") or "").strip()
    return _ingredient_line(name, unit, ingredient.get("amount"))


def format_recipe_text(recipe: dict[str, Any]) -> str:
    lines: list[str] = []
    title = str(recipe.get("title") or "Ohne Titel").strip()
    lines.append(title)
    subtitle = str(recipe.get("subtitle") or "").strip()
    if subtitle:
        lines.append(subtitle)
    lines.append(
        f"Portionen: {recipe.get('requestedServings')} "
        f"(Basis: {recipe.get('servings')})"
    )
    meta = [
        f"Bewertung: {format_rating(recipe.get('rating'))}★",
        f"Zubereitung: {format_minutes(recipe.get('preparationTime'))}",
        f"Schwierigkeit: {_difficulty(recipe.get('difficultyLabel'))}",
    ]
    lines.append(" · ".join(meta))

    groups = recipe.get("ingredientGroups") or []
    if groups:
        lines.append("")
    for group in groups:
        header = str(group.get("header") or "").strip()
        if header:
            lines.append(header)
        for ingredient in group.get("ingredients") or []:
            lines.append(format_ingredient(ingredient))

    instructions = str(recipe.get("instructions") or "").strip()
    if instructions:
        lines.extend(["", "Zubereitung:", instructions])
    return "\n".join(lines)


def format_shopping_line(item: dict[str, Any]) -> str:
    name = str(item.get("name") or "").strip()
    unit = str(item.get("unit") or "").strip()
    return _ingredient_line(name, unit, item.get("amount"))


def format_shopping_text(
    items: list[dict[str, Any]], portions: int | None
) -> str:
    if portions is None:
        header = "Einkaufsliste"
    else:
        header = f"Einkaufsliste ({portions} Portionen je Rezept)"
    lines = [header]
    lines.extend(format_shopping_line(item) for item in items)
    return "\n".join(lines)
