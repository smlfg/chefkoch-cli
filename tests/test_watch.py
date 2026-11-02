from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from chefkoch_cli import watch
from chefkoch_cli.errors import NoResultsError, StateError

REPO = Path(__file__).resolve().parents[1]
HARNESS = REPO / "tests" / "harness"
FIXTURES = REPO / "tests" / "fixtures" / "ux"
sys.path.insert(0, str(HARNESS))

from fake_server import FakeServer  # noqa: E402
from ux_spec import parse  # noqa: E402

SPEC = parse(REPO / "docs" / "UX.md")
TIMEOUT = 25.0


def _scratch_dir(name: str) -> Path:
    base = REPO / "scratch" / "tmp"
    base.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix=f"watch-{name}-", dir=base))


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class StubClient:
    def __init__(self, search_payload: dict):
        self.search_payload = search_payload
        self.search_calls: list[dict] = []

    def search(self, query: str, **kwargs):
        self.search_calls.append({"query": query, **kwargs})
        return self.search_payload

    def recipe(self, recipe_id: str):
        return {}


def _state_env(root: Path) -> dict[str, str]:
    home = root / "home"
    for relative in (".config", ".local/share", ".local/state", ".cache"):
        (home / relative).mkdir(parents=True, exist_ok=True)
    merged = dict(os.environ)
    merged.update(
        {
            "HOME": str(home),
            "XDG_CONFIG_HOME": str(home / ".config"),
            "XDG_DATA_HOME": str(home / ".local" / "share"),
            "XDG_STATE_HOME": str(home / ".local" / "state"),
            "XDG_CACHE_HOME": str(home / ".cache"),
            "CHEFKOCH_MIN_INTERVAL": "0",
            "PYTHONPATH": os.pathsep.join([str(REPO), str(HARNESS)]),
            "PYTHONUNBUFFERED": "1",
            "TERM": "xterm",
            "LANG": "C.UTF-8",
            "ACCEPTANCE_SANDBOX": "1",
            "ACCEPTANCE_NET_LOG": str(home / "net.log"),
        }
    )
    return merged


def test_erster_lauf_meldet_alle_treffer_als_neu():
    root = _scratch_dir("erstlauf")
    path = root / "watch.json"
    client = StubClient(load("search_lasagne.json"))

    data = watch.run_watch(client, "lasagne", limit=5, path=path)

    assert data["changed"] is True
    assert [item["id"] for item in data["new"]] == [
        "745721177147257",
        "491931143472316",
        "1112181217260303",
        "555661153310338",
        "484751142525322",
    ]
    assert path.is_file()
    assert (path.stat().st_mode & 0o777) == 0o600
    assert (path.parent.stat().st_mode & 0o777) == 0o700


def test_zweiter_lauf_ohne_neue_treffer_ist_unveraendert():
    root = _scratch_dir("zweiter")
    path = root / "watch.json"
    client = StubClient(load("search_lasagne.json"))

    watch.run_watch(client, "lasagne", limit=5, path=path)
    data = watch.run_watch(client, "lasagne", limit=5, path=path)

    assert data["changed"] is False
    assert data["new"] == []


def test_filter_gehoert_zum_suchschluessel():
    root = _scratch_dir("schluessel")
    path = root / "watch.json"
    client = StubClient(load("search_lasagne.json"))

    watch.run_watch(client, "lasagne", limit=5, path=path)
    data = watch.run_watch(client, "lasagne", limit=5, max_zeit=30, path=path)

    assert data["changed"] is True
    assert len(data["new"]) == 3
    assert client.search_calls[1]["maximum_time"] == 30


def test_ohne_treffer_bleibt_state_unveraendert():
    root = _scratch_dir("leer")
    path = root / "watch.json"
    client = StubClient({"count": 0, "results": []})

    with pytest.raises(NoResultsError):
        watch.run_watch(client, "nichts", path=path)

    assert not path.exists()


def test_kaputter_state_wird_nicht_ueberschrieben():
    root = _scratch_dir("kaputt")
    path = root / "watch.json"
    path.write_text("{kaputt", encoding="utf-8")
    client = StubClient(load("search_lasagne.json"))

    with pytest.raises(StateError):
        watch.run_watch(client, "lasagne", limit=5, path=path)

    assert path.read_text(encoding="utf-8") == "{kaputt"


def test_watch_ueber_cli_gegen_fake_server():
    root = _scratch_dir("cli")
    env = _state_env(root)
    command = [sys.executable, "-m", "chefkoch_cli", "watch", "lasagne", "--limit", "5", "--json"]

    with FakeServer(SPEC, REPO) as server:
        env["CHEFKOCH_BASE_URL"] = server.base_url
        first = subprocess.run(
            command,
            cwd=str(REPO),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=TIMEOUT,
        )
        second = subprocess.run(
            command,
            cwd=str(REPO),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=TIMEOUT,
        )

    first_data = json.loads(first.stdout)
    second_data = json.loads(second.stdout)
    assert first.returncode == 0, first.stderr
    assert first_data["ok"] is True
    assert first_data["data"]["changed"] is True
    assert len(first_data["data"]["new"]) == 5
    assert second.returncode == 0, second.stderr
    assert second_data["data"]["changed"] is False
    assert second_data["data"]["new"] == []
    assert "Traceback" not in first.stderr + second.stderr
