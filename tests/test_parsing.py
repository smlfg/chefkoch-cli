from __future__ import annotations

import json
from pathlib import Path

import pytest

from chefkoch_cli.errors import ParseError
from chefkoch_cli.parsing import (
    normalize_recipe,
    normalize_search_payload,
    normalize_search_result,
    recipe_tag_ids,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "ux"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_suche_fixture_liefert_count_und_treffer():
    count, results = normalize_search_payload(load("search_lasagne.json"))

    assert count == 2165
    assert len(results) == 5
    assert results[0]["id"] == "745721177147257"
    assert results[0]["title"] == "Lasagne"
    assert results[0]["rating"] == pytest.approx(4.7)
    assert results[0]["preparationTime"] == 30
    assert results[0]["difficultyLabel"] == "normal"
    assert results[0]["vegetarian"] is None


def test_rezept_wird_auf_portionen_skaliert():
    recipe = normalize_recipe(load("recipe_2812481433250378.json"), requested_servings=4)

    assert recipe["servings"] == 8
    assert recipe["requestedServings"] == 4
    assert recipe["scale"] == pytest.approx(0.5)
    ingredients = {
        item["name"]: item
        for group in recipe["ingredientGroups"]
        for item in group["ingredients"]
    }
    assert ingredients["Naturtofu"]["amount"] == pytest.approx(125.0)
    assert ingredients["Räuchertofu"]["amount"] == pytest.approx(125.0)
    assert ingredients["Naturtofu"]["unit"] == "g"


def test_tags_aus_fulltags_und_vegan():
    recipe = load("recipe_2812481433250378.json")

    tags = recipe_tag_ids(recipe)

    assert 57 in tags
    assert 32 in tags


def test_nur_vegetarisch_bei_vegetarischem_rezept():
    tags = recipe_tag_ids(load("recipe_2114131340630587.json"))

    assert 32 in tags
    assert 57 not in tags


def test_fehlende_trefferliste_ist_parse_fehler():
    with pytest.raises(ParseError):
        normalize_search_payload({"count": 0})


def test_treffer_ohne_rezept_ist_parse_fehler():
    with pytest.raises(ParseError):
        normalize_search_result({"score": 1})


def test_rezept_ohne_menge_liefert_amount_none():
    recipe = normalize_recipe(load("recipe_2812481433250378.json"), requested_servings=4)

    ingredients = {
        item["name"]: item
        for group in recipe["ingredientGroups"]
        for item in group["ingredients"]
    }
    assert ingredients["Pfeffer, schwarzer"]["amount"] is None
    assert ingredients["Muskat"]["amount"] is None
    assert ingredients["Naturtofu"]["amount"] == pytest.approx(125.0)
