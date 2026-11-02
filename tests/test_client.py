from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from chefkoch_cli.client import ApiClient, validate_base_url, validate_min_interval
from chefkoch_cli.errors import (
    ConfigError,
    HttpError,
    NetworkError,
    NotFoundError,
    ParseError,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "ux"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def make_client(handler) -> ApiClient:
    return ApiClient(
        base_url="http://api.example.invalid",
        min_interval=0,
        transport=httpx.MockTransport(handler),
    )


def test_suche_sendet_query_und_limit():
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(dict(request.url.params))
        return httpx.Response(200, json=load("search_lasagne.json"))

    with make_client(handler) as client:
        payload = client.search("lasagne", limit=5)

    assert payload["count"] == 2165
    assert seen["query"] == "lasagne"
    assert seen["limit"] == "5"
    assert seen["offset"] == "0"


def test_suche_sendet_optionale_filter():
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(dict(request.url.params))
        return httpx.Response(200, json=load("search_vegane_lasagne.json"))

    with make_client(handler) as client:
        client.search(
            "vegane lasagne",
            limit=5,
            minimum_rating=4.5,
            maximum_time=30,
            tags=57,
        )

    assert seen["minimumRating"] == "4.5"
    assert seen["maximumTime"] == "30"
    assert seen["tags"] == "57"


def test_rezept_404_ist_not_found():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"notification": {"hasErrors": True}})

    with make_client(handler) as client:
        with pytest.raises(NotFoundError):
            client.recipe("123")


def test_serverfehler_ist_http_fehler():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="down")

    with make_client(handler) as client:
        with pytest.raises(HttpError):
            client.search("lasagne", limit=1)


def test_kaputtes_json_ist_parse_fehler():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="kein json")

    with make_client(handler) as client:
        with pytest.raises(ParseError):
            client.recipe("123")


def test_netzfehler_wird_network_fehler():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("kein netz", request=request)

    with make_client(handler) as client:
        with pytest.raises(NetworkError):
            client.search("lasagne", limit=1)


def test_ungueltige_basis_url_ist_config_fehler():
    with pytest.raises(ConfigError):
        validate_base_url("ftp://example.invalid")


def test_ungueltiges_intervall_ist_config_fehler():
    for value in ("-1", "abc", "nan", "inf"):
        with pytest.raises(ConfigError):
            validate_min_interval(value)
