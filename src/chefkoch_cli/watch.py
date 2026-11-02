"""Persistenter Watch-State und Vergleich neuer Treffer."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import service
from .client import ApiClient
from .errors import StateError

STATE_VERSION = 1


def state_path() -> Path:
    base = os.environ.get("XDG_STATE_HOME") or os.path.join(
        os.path.expanduser("~"), ".local", "state"
    )
    return Path(base) / "chefkoch-cli" / "watch.json"


def _watch_key(
    query: str,
    *,
    vegetarisch: bool,
    vegan: bool,
    max_zeit: int | None,
    min_bewertung: float | None,
    schwierigkeit: str | None,
    limit: int,
) -> str:
    return json.dumps(
        {
            "query": query,
            "vegetarian": vegetarisch,
            "vegan": vegan,
            "maxTime": max_zeit,
            "minRating": min_bewertung,
            "difficulty": schwierigkeit,
            "limit": limit,
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"version": STATE_VERSION, "watches": {}}
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise StateError(
            f"Watch-State konnte nicht gelesen werden: {exc}.",
            next_step=f"Prüfe die Rechte von {path}.",
        ) from None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        raise StateError(
            f"Watch-State ist beschädigt: {path}.",
            next_step="Lösche die Datei oder repariere das JSON und versuche es erneut.",
        ) from None
    if not isinstance(data, dict) or not isinstance(data.get("watches"), dict):
        raise StateError(
            f"Watch-State hat ein unbekanntes Format: {path}.",
            next_step="Lösche die Datei und versuche es erneut.",
        )
    return data


def save_state(path: Path, state: dict[str, Any]) -> None:
    directory = path.parent
    try:
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(directory, 0o700)
    except OSError as exc:
        raise StateError(
            f"Watch-State-Verzeichnis konnte nicht angelegt werden: {exc}.",
            next_step=f"Prüfe die Rechte von {directory}.",
        ) from None

    handle = None
    temp_path = None
    try:
        handle, temp_name = tempfile.mkstemp(prefix=".watch-", dir=str(directory))
        temp_path = Path(temp_name)
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            handle = None
            json.dump(state, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temp_path, 0o600)
        os.replace(temp_path, path)
        temp_path = None
    except OSError as exc:
        raise StateError(
            f"Watch-State konnte nicht geschrieben werden: {exc}.",
            next_step=f"Prüfe die Rechte von {directory}.",
        ) from None
    finally:
        if handle is not None:
            try:
                os.close(handle)
            except OSError:
                pass
        if temp_path is not None:
            try:
                temp_path.unlink()
            except OSError:
                pass


def run_watch(
    client: ApiClient,
    query: str,
    *,
    vegetarisch: bool = False,
    vegan: bool = False,
    max_zeit: int | None = None,
    min_bewertung: float | None = None,
    schwierigkeit: str | None = None,
    limit: int = service.DEFAULT_WATCH_LIMIT,
    path: Path | None = None,
) -> dict[str, Any]:
    data = service.search_recipes(
        client,
        query,
        vegetarisch=vegetarisch,
        vegan=vegan,
        max_zeit=max_zeit,
        min_bewertung=min_bewertung,
        schwierigkeit=schwierigkeit,
        sort="bewertung",
        limit=limit,
        seite=1,
    )
    current = list(data.get("results") or [])
    current_ids = [str(item.get("id")) for item in current]

    target = path or state_path()
    state = load_state(target)
    key = _watch_key(
        data["query"],
        vegetarisch=vegetarisch,
        vegan=vegan,
        max_zeit=max_zeit,
        min_bewertung=min_bewertung,
        schwierigkeit=schwierigkeit,
        limit=limit,
    )
    previous = state["watches"].get(key)
    if previous is None:
        previous_ids: set[str] = set()
        changed = True
    else:
        previous_ids = {
            str(item)
            for item in previous.get("ids", [])
            if isinstance(item, (str, int))
        }
        changed = False

    new_items = [item for item in current if str(item.get("id")) not in previous_ids]
    if previous is not None and not new_items:
        changed = False
    elif previous is not None and new_items:
        changed = True

    checked_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    state["version"] = STATE_VERSION
    state["watches"][key] = {
        "ids": current_ids,
        "checkedAt": checked_at,
    }
    save_state(target, state)

    return {
        "query": data["query"],
        "changed": bool(changed and new_items),
        "new": new_items,
        "checkedAt": checked_at,
    }
