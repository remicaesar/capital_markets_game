"""
Venture fund web API: the payload contract, hidden information, and persistence.

response_model is a projection (see tests/test_api_payload.py): a key the state
builder emits but the schema does not declare disappears without an error. The
contract test walks the whole payload, nested lists included.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from config.venture_settings import MAX_PERIODS
from web.app import app
from web.session_store import VentureSessionStore
from web.venture_manager import VentureManager
from web.venture_schemas import VentureState

REPO = Path(__file__).resolve().parent.parent


@pytest.fixture
def vm(tmp_path):
    return VentureManager(store=VentureSessionStore(tmp_path / "sessions.db"))


def _play(vm, session, turns):
    """Back the first two deals each turn, follow on with whatever reserve covers."""
    for _ in range(turns):
        for deal in session.fund.deal_flow[:2]:
            vm.act(session, ["commit", deal.id, 200_000, 200_000])
        for pos in session.fund.positions.values():
            if pos.active and pos.startup.open_round:
                vm.act(session, ["follow_on", pos.startup.id, min(pos.pro_rata(), pos.reserve)])
        vm.act(session, ["advance"])


def _dropped_keys(raw, served, path="state"):
    """Every key present in `raw` but missing from `served`, at any depth."""
    missing = []
    if isinstance(raw, dict):
        for key, value in raw.items():
            if key not in served:
                missing.append(f"{path}.{key}")
            else:
                missing += _dropped_keys(value, served[key], f"{path}.{key}")
    elif isinstance(raw, list):
        for i, (r, s) in enumerate(zip(raw, served)):
            missing += _dropped_keys(r, s, f"{path}[{i}]")
    return missing


def test_response_model_declares_every_key_the_builder_emits(vm):
    _, session = vm.create_game(seed=5)
    _play(vm, session, MAX_PERIODS)              # through exits, waterfalls and the report
    raw = vm.get_state(session)
    assert raw["exits"] and raw["report"] and raw["history"]
    assert any(e["waterfall"] for e in raw["exits"])

    served = json.loads(VentureState(**raw).model_dump_json())
    assert _dropped_keys(raw, served) == []


def test_mid_game_state_survives_the_response_model(vm):
    _, session = vm.create_game(seed=8)
    _play(vm, session, 7)
    raw = vm.get_state(session)
    assert raw["follow_ons"] or raw["portfolio"]
    served = json.loads(VentureState(**raw).model_dump_json())
    assert _dropped_keys(raw, served) == []


def test_the_future_is_never_sent_to_the_browser(vm):
    _, session = vm.create_game(seed=3)
    _play(vm, session, 4)
    payload = json.dumps(vm.get_state(session))
    for key in ("quality", "schedule", "recovery"):
        assert f'"{key}"' not in payload

    fund = session.fund
    startups = fund.deal_flow + [p.startup for p in fund.positions.values()]
    future = [e for s in startups for e in s.schedule
              if e.period > fund.period and e is not s.open_round]
    assert future, "nothing in the future to check"
    for event in future:
        secret = event.pre_money if event.kind == "round" else event.exit_value
        if secret:
            assert str(round(secret, 2)) not in payload
    for startup in startups:
        assert f"{startup.quality:.6f}"[:8] not in payload


def test_a_restored_session_replays_to_the_identical_fund(tmp_path):
    store = VentureSessionStore(tmp_path / "sessions.db")
    first = VentureManager(store=store)
    game_id, session = first.create_game(seed=21)
    _play(first, session, 9)
    before = first.get_state(session)
    kinds = {action[0] for action in session.actions}
    assert kinds == {"commit", "follow_on", "advance"}, "the replay would not cover every action"

    restarted = VentureManager(store=VentureSessionStore(tmp_path / "sessions.db"))
    after = restarted.get_state(restarted.get_session(game_id))
    assert after == before


def test_failed_actions_are_not_logged_for_replay(vm):
    _, session = vm.create_game(seed=2)
    deal = session.fund.deal_flow[0]
    ok, _, _ = vm.act(session, ["commit", deal.id, 1, 0])          # below the minimum
    assert not ok
    assert session.actions == []


def test_http_flow_from_new_fund_to_final_report():
    client = TestClient(app)
    response = client.post("/api/venture/new", json={"seed": 77})
    assert response.status_code == 200
    game_id = response.json()["game_id"]
    deal = response.json()["state"]["deals"][0]

    response = client.post("/api/venture/commit", json={
        "game_id": game_id, "deal_id": deal["id"], "check": 250_000, "reserve": 250_000})
    body = response.json()
    assert body["success"], body["message"]
    assert body["state"]["deals"][0]["committed_check"] == 250_000

    bad = client.post("/api/venture/follow-on", json={
        "game_id": game_id, "startup_id": deal["id"], "amount": 1})
    assert bad.json()["success"] is False

    negative = client.post("/api/venture/commit", json={
        "game_id": game_id, "deal_id": deal["id"], "check": -5, "reserve": 0})
    assert negative.status_code == 422

    for _ in range(MAX_PERIODS):
        state = client.post("/api/venture/advance", json={"game_id": game_id}).json()["state"]
    assert state["fund"]["phase"] == "over"
    assert state["report"]["deal_count"] == 1
    assert state["report"]["headline"]

    # A finished fund refuses further turns instead of advancing past its end
    again = client.post("/api/venture/advance", json={"game_id": game_id}).json()
    assert again["events"] == [] and again["state"]["fund"]["period"] == MAX_PERIODS + 1

    assert client.get("/api/venture/state", params={"game_id": "nope"}).status_code == 404
    mechanics = client.get("/api/venture/mechanics").json()["mechanics"]
    assert {m["key"] for m in mechanics} >= {"fees", "carry", "pro_rata", "dilution",
                                             "liquidation_preference", "j_curve", "power_law"}
    assert client.get("/venture").status_code == 200


@pytest.mark.slow
def test_cli_venture_playthrough_reaches_the_letter_to_lps():
    """End to end: back one deal, then advance every half-year to the report."""
    stdin = "\n" + "invest 1\n300\n\n\n" + "next\n\n" * (MAX_PERIODS + 5)
    result = subprocess.run(
        [sys.executable, "main.py", "--venture", "--seed", "4"],
        input=stdin, capture_output=True, text=True, timeout=180, cwd=REPO,
    )
    out = result.stdout + result.stderr
    assert "Committed $300,000" in out
    assert "END OF FUND" in out, "the fund never reached its report"
    assert "J-curve" in out
    assert "Traceback" not in out
