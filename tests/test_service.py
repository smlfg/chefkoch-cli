from __future__ import annotations

import json
from pathlib import Path

import pytest

from chefkoch_cli import service
from chefkoch_cli.errors import NoResultsError, UsageError

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "ux"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class StubClient:
    def __init__(self, search_payload: dict, recipes: dict[str, dict] | None = None):
        self.search_payload = search_payload
        self.recipes = recipes or {}
        self.search_calls: list[dict] = []

    def search(self, query: str, **kwargs):
        self.search_calls.append({"query": query, **kwargs})
        return self.search_payload

    def recipe(self, recipe_id: str):
        return self.recipes[recipe_id]


def test_numerische_id_wird_direkt_erkannt():
    assert service.parse_recipe_reference("745721177147257") == (
        "id",
        "745721177147257",
    )


def test_chefkoch_url_liefert_id():
    assert service.parse_recipe_reference(
        "https://www.chefkoch.de/rezepte/745721177147257/Lasagne.html"
    ) == ("id", "745721177147257")


def test_url_ohne_schema_wird_erkannt():
    assert service.parse_recipe_reference(
        "www.chefkoch.de/rezepte/745721177147257/Lasagne.html"
    ) == ("id", "745721177147257")


def test_fremder_host_ist_usage_fehler():
    with pytest.raises(UsageError):
        service.parse_recipe_reference("https://example.invalid/rezepte/123/x.html")


def test_name_bleibt_name():
    assert service.parse_recipe_reference("vegane lasagne") == ("name", "vegane lasagne")


def test_suche_sortiert_nach_bewertung_und_limit():
    client = StubClient(load("search_lasagne.json"))

    data = service.search_recipes(client, "lasagne", limit=5)

    ids = [item["id"] for item in data["results"]]
    assert ids == [
        "745721177147257",
        "491931143472316",
        "1112181217260303",
        "555661153310338",
        "484751142525322",
    ]
    assert data["total"] == 2165
    assert client.search_calls[0]["limit"] == service.SEARCH_WINDOW


def test_suche_sortiert_nach_zeit():
    client = StubClient(load("search_lasagne.json"))

    data = service.search_recipes(client, "lasagne", sort="zeit", limit=5)

    times = [item["preparationTime"] for item in data["results"]]
    assert times == [20, 25, 30, 60, 60]


def test_suche_filtert_clientseitig():
    client = StubClient(load("search_lasagne.json"))

    data = service.search_recipes(client, "lasagne", max_zeit=30, limit=10)

    assert {item["id"] for item in data["results"]} == {
        "745721177147257",
        "555661153310338",
        "484751142525322",
    }


def test_suche_ohne_treffer_ist_no_results():
    client = StubClient(load("search_lasagne.json"))

    with pytest.raises(NoResultsError):
        service.search_recipes(client, "lasagne", max_zeit=1)


def test_vegane_suche_prueft_details():
    search_payload = load("search_vegane_lasagne.json")
    recipes = {
        "2812481433250378": load("recipe_2812481433250378.json"),
        "2114131340630587": load("recipe_2114131340630587.json"),
    }
    for item in search_payload["results"]:
        recipes.setdefault(item["recipe"]["id"], {"fullTags": [{"id": 57}]})
    recipes["2114131340630587"] = {"fullTags": [{"id": 32}]}
    client = StubClient(search_payload, recipes)

    data = service.search_recipes(client, "vegane lasagne", vegan=True, limit=5)

    assert "2114131340630587" not in {item["id"] for item in data["results"]}
    assert data["results"][0]["vegan"] is True


def test_einkaufsliste_summiert_nach_name_und_einheit():
    from chefkoch_cli.parsing import normalize_recipe

    recipes = [
        normalize_recipe(load("recipe_2812481433250378.json"), 4),
        normalize_recipe(load("recipe_2114131340630587.json"), 4),
    ]

    data = service.build_shopping_list(recipes, 4)
    items = {(item["name"], item["unit"]): item for item in data["items"]}

    knoblauch = items[("Knoblauchzehe(n)", "")]
    assert knoblauch["amount"] == pytest.approx(4.67)
    assert set(knoblauch["recipeIds"]) == {
        "2812481433250378",
        "2114131340630587",
    }
    assert items[("Käse, geriebener", "g")]["amount"] == pytest.approx(266.67)
    assert items[("Naturtofu", "g")]["amount"] == pytest.approx(125.0)


def test_einkaufsliste_trennt_verschiedene_einheiten():
    recipes = [
        {
            "id": "1",
            "servings": 1,
            "requestedServings": 1,
            "ingredientGroups": [
                {
                    "header": "",
                    "ingredients": [
                        {"name": "Mehl", "amount": 100, "unit": "g"},
                        {"name": "Mehl", "amount": 2, "unit": "EL"},
                    ],
                }
            ],
        }
    ]

    data = service.build_shopping_list(recipes, 1)

    assert len(data["items"]) == 2
    assert [item["unit"] for item in data["items"]] == ["EL", "g"]


def test_einkaufsliste_ohne_menge_liefert_amount_none():
    from chefkoch_cli.parsing import normalize_recipe

    recipe = normalize_recipe(load("recipe_2812481433250378.json"), 4)

    data = service.build_shopping_list([recipe], 4)
    items = {item["name"]: item for item in data["items"]}

    assert items["Pfeffer, schwarzer"]["amount"] is None
    assert items["Muskat"]["amount"] is None
    assert items["Naturtofu"]["amount"] == pytest.approx(125.0)
    assert items["Basilikum"]["amount"] == pytest.approx(1.0)
