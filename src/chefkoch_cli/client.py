"""HTTP-Client für die inoffizielle Chefkoch-API."""

from __future__ import annotations

import math
import os
import time
from typing import Any
from urllib.parse import urlsplit

import httpx

from .errors import ConfigError, HttpError, NetworkError, NotFoundError, ParseError

DEFAULT_BASE_URL = "https://api.chefkoch.de"
DEFAULT_TIMEOUT = 15.0
DEFAULT_MIN_INTERVAL = 1.0
USER_AGENT = "chefkoch-cli/0.1 (+https://github.com/smlfg/chefkoch-cli)"
ACCEPT = "application/json"


def validate_base_url(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ConfigError(
            "CHEFKOCH_BASE_URL ist leer.",
            next_step="Setze eine gültige http(s)-URL oder entferne die Variable.",
        )
    parts = urlsplit(text)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise ConfigError(
            f"CHEFKOCH_BASE_URL ist keine gültige http(s)-URL: {text!r}.",
            next_step="Beispiel: https://api.chefkoch.de",
        )
    return text.rstrip("/")


def validate_min_interval(value: object) -> float:
    try:
        interval = float(value)
    except (TypeError, ValueError):
        raise ConfigError(
            f"CHEFKOCH_MIN_INTERVAL ist keine Zahl: {value!r}.",
            next_step="Nutze eine Zahl >= 0, z. B. 0 für Tests.",
        ) from None
    if not math.isfinite(interval) or interval < 0:
        raise ConfigError(
            f"CHEFKOCH_MIN_INTERVAL muss eine endliche Zahl >= 0 sein: {value!r}.",
            next_step="Nutze eine Zahl >= 0, z. B. 0 für Tests.",
        )
    return interval


def validate_timeout(value: object) -> float:
    try:
        timeout = float(value)
    except (TypeError, ValueError):
        raise ConfigError(
            f"Timeout ist keine Zahl: {value!r}.",
            next_step="Nutze eine Zahl > 0, z. B. --timeout 15.",
        ) from None
    if not math.isfinite(timeout) or timeout <= 0:
        raise ConfigError(
            f"Timeout muss eine endliche Zahl > 0 sein: {value!r}.",
            next_step="Nutze eine Zahl > 0, z. B. --timeout 15.",
        )
    return timeout


class ApiClient:
    """Kapselt Basis-URL, Timeout, User-Agent und Mindestabstand."""

    def __init__(
        self,
        base_url: str | None = None,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        min_interval: float | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        raw_base = base_url if base_url is not None else os.environ.get("CHEFKOCH_BASE_URL", DEFAULT_BASE_URL)
        raw_interval = (
            min_interval
            if min_interval is not None
            else os.environ.get("CHEFKOCH_MIN_INTERVAL", str(DEFAULT_MIN_INTERVAL))
        )
        self.base_url = validate_base_url(raw_base or DEFAULT_BASE_URL)
        self.timeout = validate_timeout(timeout)
        self.min_interval = validate_min_interval(raw_interval)
        self._last_request: float | None = None
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={"User-Agent": USER_AGENT, "Accept": ACCEPT},
            timeout=self.timeout,
            transport=transport,
            follow_redirects=True,
        )

    def __enter__(self) -> "ApiClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def _wait(self) -> None:
        if self.min_interval <= 0 or self._last_request is None:
            return
        remaining = self.min_interval - (time.monotonic() - self._last_request)
        if remaining > 0:
            time.sleep(remaining)

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self._wait()
        try:
            response = self._client.get(path, params=params)
        except httpx.TimeoutException:
            raise NetworkError(
                "Zeitüberschreitung beim Abruf der Chefkoch-API.",
                next_step="Prüfe die Verbindung oder erhöhe --timeout.",
            ) from None
        except httpx.HTTPError as exc:
            raise NetworkError(
                f"Netzwerkfehler beim Abruf der Chefkoch-API: {exc}.",
                next_step="Prüfe die Verbindung und versuche es erneut.",
            ) from None
        finally:
            self._last_request = time.monotonic()

        status = response.status_code
        if status == 404:
            if path.startswith("/v2/recipes/") and path.count("/") == 3:
                raise NotFoundError(
                    f"Rezept {path.rsplit('/', 1)[-1]} wurde nicht gefunden.",
                    next_step="Prüfe die ID/URL oder suche mit `chefkoch suche ...`.",
                )
            raise HttpError(
                "Die Chefkoch-API hat die Suche nicht gefunden (HTTP 404).",
                next_step="Prüfe CHEFKOCH_BASE_URL oder versuche es später erneut.",
            )
        if status == 429:
            raise HttpError(
                "Die Chefkoch-API begrenzt die Anfragen (HTTP 429).",
                next_step="Warte einen Moment und versuche es erneut.",
            )
        if 500 <= status <= 599:
            raise HttpError(
                f"Die Chefkoch-API meldet einen Serverfehler (HTTP {status}).",
                next_step="Versuche es später erneut.",
            )
        if status != 200:
            raise HttpError(
                f"Unerwartete Antwort der Chefkoch-API (HTTP {status}).",
                next_step="Prüfe CHEFKOCH_BASE_URL und versuche es erneut.",
            )
        try:
            payload = response.json()
        except ValueError:
            raise ParseError(
                "Die Chefkoch-API hat kein gültiges JSON geliefert.",
                next_step="Versuche es später erneut.",
            ) from None
        if not isinstance(payload, dict):
            raise ParseError(
                "Die Chefkoch-API hat ein unerwartetes JSON-Format geliefert.",
                next_step="Versuche es später erneut.",
            )
        return payload

    def search(
        self,
        query: str,
        *,
        limit: int,
        offset: int = 0,
        minimum_rating: float | None = None,
        maximum_time: int | None = None,
        tags: int | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"query": query, "limit": limit, "offset": offset}
        if minimum_rating is not None:
            params["minimumRating"] = minimum_rating
        if maximum_time is not None:
            params["maximumTime"] = maximum_time
        if tags is not None:
            params["tags"] = tags
        return self._get("/v2/recipes", params=params)

    def recipe(self, recipe_id: str) -> dict[str, Any]:
        return self._get(f"/v2/recipes/{recipe_id}")
