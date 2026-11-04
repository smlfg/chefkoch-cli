from __future__ import annotations

from chefkoch_cli.formatting import (
    format_amount,
    format_ingredient,
    format_rating,
    format_recipe_text,
    format_search_line,
    format_shopping_line,
)


def test_mengen_mit_maximal_zwei_nachkommastellen_und_komma():
    assert format_amount(125) == "125"
    assert format_amount(0.5) == "0,5"
    assert format_amount(4.666666) == "4,67"
    assert format_amount(266.666666) == "266,67"


def test_bewertung_mit_einer_nachkommastelle():
    assert format_rating(4.7) == "4,7"
    assert format_rating(4.85) == "4,8"
    assert format_rating(None) == "–"


def test_trefferzeile_entspricht_ux_beispiel():
    line = format_search_line(
        1,
        {
            "id": "745721177147257",
            "title": "Lasagne",
            "rating": 4.7,
            "preparationTime": 30,
            "difficultyLabel": "normal",
        },
    )

    assert line == "1) Lasagne (ID 745721177147257) · 4,7★ · 30 Min. · normal"


def test_zutatenzeile_setzt_einheit_vor_namen():
    assert (
        format_ingredient({"name": "Naturtofu", "amount": 125, "unit": "g"})
        == "125 g Naturtofu"
    )
    assert (
        format_ingredient({"name": "Knoblauchzehe(n)", "amount": 4.6666, "unit": ""})
        == "4,67 Knoblauchzehe(n)"
    )


def test_einkaufslisten_zeile():
    assert (
        format_shopping_line(
            {"name": "Käse, geriebener", "amount": 266.6666, "unit": "g"}
        )
        == "266,67 g Käse, geriebener"
    )


def test_rezepttext_enthaelt_portionen_und_zutaten():
    text = format_recipe_text(
        {
            "title": "Die ultimative vegane Lasagne",
            "subtitle": "",
            "servings": 8,
            "requestedServings": 4,
            "rating": 4.66,
            "preparationTime": 45,
            "difficultyLabel": "normal",
            "ingredientGroups": [
                {
                    "header": "",
                    "ingredients": [
                        {"name": "Naturtofu", "amount": 125, "unit": "g"},
                        {"name": "Räuchertofu", "amount": 125, "unit": "g"},
                    ],
                }
            ],
            "instructions": "Tofu zerbröseln.",
        }
    )

    assert "Portionen: 4 (Basis: 8)" in text
    assert "125 g Naturtofu" in text
    assert "125 g Räuchertofu" in text


def test_zutaten_ohne_menge_zeigen_keine_null():
    assert (
        format_ingredient({"name": "Basilikum", "amount": None, "unit": ""})
        == "Basilikum"
    )
    assert (
        format_ingredient({"name": "Butter", "amount": 0, "unit": "etwas"})
        == "etwas Butter"
    )
    assert (
        format_ingredient({"name": "Pfeffer", "amount": None, "unit": "n. B."})
        == "n. B. Pfeffer"
    )


def test_einkaufslisten_zeile_ohne_menge_zeigt_keine_null():
    assert (
        format_shopping_line({"name": "Basilikum", "amount": None, "unit": ""})
        == "Basilikum"
    )
    assert (
        format_shopping_line({"name": "Butter", "amount": 0, "unit": "etwas"})
        == "etwas Butter"
    )
    assert (
        format_shopping_line({"name": "Pfeffer", "amount": None, "unit": "n. B."})
        == "n. B. Pfeffer"
    )
