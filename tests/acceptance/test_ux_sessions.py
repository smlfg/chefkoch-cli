"""Akzeptanztests aus den drei UX-Sitzungen (docs/UX.md).

Die Tests starten ``python -m chefkoch_cli`` als Subprozess gegen den
Fake-Server aus ``tests/harness/`` und die dort registrierten ``ux-routes``.
Bis zum Bau in Schritt 4 dürfen sie rot sein.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
HARNESS = REPO / "tests" / "harness"
sys.path.insert(0, str(HARNESS))

from fake_server import FakeServer  # noqa: E402
from ux_session import PtySession, strip_ansi  # noqa: E402
from ux_spec import parse  # noqa: E402

SPEC = parse(REPO / "docs" / "UX.md")
TIMEOUT = 25.0


def _scratch_dir(name: str) -> Path:
    base = REPO / "scratch" / "tmp"
    base.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix=f"acceptance-{name}-", dir=base))


@pytest.fixture()
def env() -> dict[str, str]:
    home = _scratch_dir("home")
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


def _command(args: list[str]) -> list[str]:
    return [sys.executable, "-m", "chefkoch_cli", *args]


def _run_tty(
    args: list[str],
    env: dict[str, str],
    server: FakeServer,
    inputs: list[tuple[str, str]] | None = None,
) -> tuple[int, str]:
    merged = dict(env)
    merged["CHEFKOCH_BASE_URL"] = server.base_url
    session = PtySession(_command(args), env=merged, cwd=REPO)
    try:
        for pattern, answer in inputs or []:
            assert session.expect(pattern, timeout=TIMEOUT), (
                f"erwartete Ausgabe nicht gefunden: {pattern!r}\n"
                f"Mitschnitt:\n{strip_ansi(session.transcript)}"
            )
            session.send_line(answer)
        code = session.wait_exit(TIMEOUT)
        output = strip_ansi(session.transcript)
        return code, output
    finally:
        session.close()


def test_suche_lasagne_zeigt_lesbare_trefferliste(env):
    """Sitzung 1: Installation und erste Suche (hier ohne pipx)."""
    with FakeServer(SPEC, REPO) as server:
        code, output = _run_tty(["suche", "lasagne", "--limit", "5"], env, server)

    assert code == 0, output
    assert "1) Lasagne (ID 745721177147257) · 4,7★ · 30 Min. · normal" in output
    assert "2) Italienische Lasagne (ID 491931143472316) · 4,6★ · 60 Min. · normal" in output
    assert "3) Lasagne Bolognese (ID 1112181217260303) · 4,6★ · 60 Min. · normal" in output
    assert "4) Béchamel-Hackfleisch-Lasagne (ID 555661153310338) · 4,6★ · 25 Min. · normal" in output
    assert "5) Idiotensichere Lasagne (ID 484751142525322) · 4,5★ · 20 Min. · normal" in output
    assert not output.lstrip().startswith("{"), "TTY-Ausgabe darf nicht JSON sein"


def test_rezept_per_name_auswahl_und_portionen(env):
    """Sitzung 2: Rezept per Name, Auswahl 2, Skalierung von 8 auf 4."""
    with FakeServer(SPEC, REPO) as server:
        code, output = _run_tty(
            ["rezept", "vegane lasagne", "--portionen", "4"],
            env,
            server,
            inputs=[(r"Auswahl \[1-5\]:", "2")],
        )

    assert code == 0, output
    assert "1) Vegane Gemüselasagne (ID 3824501582218163) · 4,8★ · 20 Min. · normal" in output
    assert "2) Die ultimative vegane Lasagne (ID 2812481433250378) · 4,7★ · 45 Min. · normal" in output
    assert "Die ultimative vegane Lasagne" in output
    assert "Portionen: 4 (Basis: 8)" in output
    assert "125 g Naturtofu" in output
    assert "125 g Räuchertofu" in output


def test_einkaufsliste_per_namen_summiert_zutaten(env):
    """Sitzung 3: zwei Rezepte per Name, Auswahl beim zweiten, Summe 4,67."""
    with FakeServer(SPEC, REPO) as server:
        code, output = _run_tty(
            [
                "einkaufsliste",
                "die ultimative vegane lasagne",
                "vegetarische spinat gemüse lasagne",
                "--portionen",
                "4",
            ],
            env,
            server,
            inputs=[(r"Auswahl \[1-5\]:", "1")],
        )

    assert code == 0, output
    assert "1) Vegetarische Spinat-Gemüse-Lasagne mit Tomatensoße (ID 2114131340630587) · 4,8★ · 25 Min. · normal" in output
    assert "Einkaufsliste (4 Portionen je Rezept)" in output
    assert "4,67 Knoblauchzehe(n)" in output
    assert "266,67 g Käse, geriebener" in output
    assert "125 g Naturtofu" in output


def test_mehrdeutiger_name_ohne_tty_liste_und_exit_2(env):
    """Ohne TTY wird nicht interaktiv geraten: Liste plus Usage-Fehler."""
    with FakeServer(SPEC, REPO) as server:
        merged = dict(env)
        merged["CHEFKOCH_BASE_URL"] = server.base_url
        import subprocess

        result = subprocess.run(
            _command(["rezept", "vegane lasagne", "--portionen", "4"]),
            cwd=str(REPO),
            env=merged,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=TIMEOUT,
        )

    output = result.stdout + result.stderr
    assert result.returncode == 2, output
    assert "Die ultimative vegane Lasagne" in output
    assert "Traceback" not in output
