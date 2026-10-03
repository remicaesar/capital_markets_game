"""
Bankruptcy end condition: net worth <= 0 after margin-call handling ends the game.

Fixture note: a short position with a price spike is the only way to drive net worth
below zero through play, because longs and cash alone can never go negative.

Every finished game must stay finished: across further actions and turns, across a
server restart (SessionStore), and across a save file loaded through the web API.
"""

import io
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from rich.console import Console

import main as cli
import utils.save_manager as save_manager
from config.settings import MAX_TURNS
from models.market import Market
from models.player import Player
from utils.save_manager import serialize_game_state
from web.app import app
from web.game_manager import GameManager, GameSession, game_manager
from web.session_store import SessionStore

GAME_OVER = "Game is over - no further actions are allowed"


def _spike_short_into_bankruptcy(market, player, company):
    """Short a stock, then spike its price so the liability exceeds all assets."""
    assert player.short(market, company, 100)
    company.price *= 10  # liability is now ~10x the position, far above cash
    return company


@pytest.fixture
def store(tmp_path, monkeypatch):
    """Point the shared game_manager at a throwaway DB, never ~/.capital_markets_game."""
    s = SessionStore(tmp_path / "sessions.db")
    monkeypatch.setattr(game_manager, "store", s)
    return s


@pytest.fixture
def save_dir(tmp_path, monkeypatch):
    d = tmp_path / "saves"
    monkeypatch.setattr(save_manager, "SAVE_DIR", d)
    return d


@pytest.fixture
def bankrupt_session(store, market, player, company):
    session = GameSession(game_id="bk", market=market, player=player,
                          seed=1234, news_history=[])
    game_manager.sessions["bk"] = session
    _spike_short_into_bankruptcy(market, player, company)
    yield session
    game_manager.sessions.pop("bk", None)


def test_suite_never_touches_the_real_home():
    """conftest redirects HOME; the import-time paths must not resolve to the real one."""
    pwd = pytest.importorskip("pwd")
    import web.session_store as session_store

    real_home = Path(pwd.getpwuid(os.getuid()).pw_dir).resolve()
    for path in (session_store.DB_PATH, save_manager.SAVE_DIR, game_manager.store.db_path):
        assert real_home not in Path(path).resolve().parents, path


# --- the condition itself ---------------------------------------------------

def test_not_bankrupt_at_start(market, player):
    assert player.is_bankrupt(market) is False


def test_bankrupt_when_short_squeeze_wipes_out_net_worth(market, player, company):
    _spike_short_into_bankruptcy(market, player, company)
    assert player.net_worth(market) < 0
    assert player.is_bankrupt(market) is True


def test_exactly_zero_net_worth_is_bankrupt(market, player):
    """Boundary: the end condition is `<= 0`, so zero itself ends the game."""
    player.cash = 0.0
    assert player.net_worth(market) == 0
    assert player.is_bankrupt(market) is True


def test_not_bankrupt_with_a_short_that_is_only_underwater(market, player, company):
    """Boundary: a losing short with positive net worth is not bankruptcy."""
    assert player.short(market, company, 100)
    company.price *= 1.5
    assert player.net_worth(market) > 0
    assert player.is_bankrupt(market) is False


# --- CLI ----------------------------------------------------------------------

def test_cli_ends_the_game_on_bankruptcy(monkeypatch):
    """Drive main() in-process with a player who starts at exactly zero net worth."""
    markets = []

    def recording_market():
        m = Market()
        markets.append(m)
        return m

    def broke_player():
        p = Player()
        p.cash = 0.0
        return p

    prompts = []

    def scripted_input(prompt=""):
        prompts.append(prompt)
        if len(prompts) > 20:
            raise RuntimeError("the CLI kept playing a bankrupt game")
        return "hold" if prompt.strip() == ">" else ""

    out = io.StringIO()
    monkeypatch.setattr(cli, "Market", recording_market)
    monkeypatch.setattr(cli, "Player", broke_player)
    monkeypatch.setattr(cli, "console", Console(file=out, width=120))
    monkeypatch.setattr("builtins.input", scripted_input)
    monkeypatch.setattr("sys.argv", ["main.py", "--new", "--no-autosave", "--seed", "1"])

    cli.main()

    text = out.getvalue()
    assert "BANKRUPT" in text
    assert "GAME OVER" in text
    assert markets[0].turn == 1, "bankruptcy must end the game before the turn advances"


# --- web: ending the game ---------------------------------------------------

def test_advance_turn_ends_game_as_bankrupt_and_rejects_further_actions(bankrupt_session, company):
    session = bankrupt_session
    turn_before = session.market.turn

    _, game_over, final_stats = game_manager.advance_turn(session)

    assert game_over is True
    assert final_stats["game_over_reason"] == "bankrupt"
    assert session.market.turn == turn_before, "bankruptcy must end the game before the turn advances"

    state = game_manager.get_game_state(session)
    assert state["game_over"] is True
    assert state["game_over_reason"] == "bankrupt"

    ok, msg = game_manager.execute_action(session, "buy", company.name, 1)
    assert (ok, msg) == (False, GAME_OVER)


def test_advancing_a_finished_game_changes_nothing(bankrupt_session):
    session = bankrupt_session
    game_manager.advance_turn(session)
    cash, news, turn = session.player.cash, list(session.news_history), session.market.turn

    news_events, game_over, final_stats = game_manager.advance_turn(session)

    assert game_over is True
    assert news_events == []
    assert final_stats["game_over_reason"] == "bankrupt"
    assert session.player.cash == cash, "dividends or borrow fees ran on a finished game"
    assert session.news_history == news
    assert session.market.turn == turn


def test_game_over_reason_survives_the_response_model(bankrupt_session):
    """Goes through the real FastAPI route: response_model strips undeclared keys."""
    client = TestClient(app)
    resp = client.post("/api/game/advance", json={"game_id": "bk"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["game_over"] is True
    assert body["state"]["game_over_reason"] == "bankrupt"

    state = client.get("/api/game/state", params={"game_id": "bk"}).json()["state"]
    assert state["game_over"] is True
    assert state["game_over_reason"] == "bankrupt"


def test_live_game_reports_no_reason(market, player):
    session = GameSession(game_id="live", market=market, player=player,
                          seed=1234, news_history=[])
    state = game_manager.get_game_state(session)
    assert state["game_over"] is False
    assert state["game_over_reason"] is None


# --- web: every mutating method refuses a finished game ---------------------

def _call(method, session, company):
    """Invoke one mutating GameManager method with arguments that succeed while live."""
    option_id = session.player.options_positions[0].id
    calls = {
        "execute_action": lambda: game_manager.execute_action(session, "buy", company.name, 1),
        "place_order": lambda: game_manager.place_order(session, "limit", "buy", company.name, 1, 90.0),
        "buy_option": lambda: game_manager.buy_option(session, company.name, "call", 90.0, 1),
        "exercise_option": lambda: game_manager.exercise_option(session, option_id),
        "sell_option": lambda: game_manager.sell_option(session, option_id),
    }
    return calls[method]()


MUTATING_METHODS = ["execute_action", "place_order", "buy_option", "exercise_option", "sell_option"]


@pytest.fixture
def session_with_itm_call(store, market, player, company):
    """A healthy session holding an in-the-money call, so every method has a valid target."""
    ok, msg, _ = player.buy_option(market, company.name, "call", 90.0, 1)
    assert ok, msg
    return GameSession(game_id="opt", market=market, player=player, seed=1234, news_history=[])


@pytest.mark.parametrize("method", MUTATING_METHODS)
def test_each_mutating_method_works_while_live(method, session_with_itm_call, company):
    """Proves the rejection test below is not vacuous: the same call succeeds live."""
    result = _call(method, session_with_itm_call, company)
    assert result[0] is True, result[1]


@pytest.mark.parametrize("method", MUTATING_METHODS)
def test_each_mutating_method_rejects_a_finished_game(method, session_with_itm_call, company):
    session = session_with_itm_call
    session.game_over_reason = "bankrupt"
    player = session.player
    before = (player.cash, dict(player.portfolio), len(player.options_positions),
              len(player.pending_orders))

    result = _call(method, session, company)

    assert result[:2] == (False, GAME_OVER)
    assert (player.cash, dict(player.portfolio), len(player.options_positions),
            len(player.pending_orders)) == before


# --- persistence: restart and save files -------------------------------------

def _persisted_then_restored(store, session):
    writer = GameManager(store=store)
    writer._persist_session(session)
    return GameManager(store=store).sessions[session.game_id]


def test_bankrupt_reason_survives_a_restart(store, bankrupt_session, company):
    game_manager.advance_turn(bankrupt_session)  # ends the game and persists it

    restored = GameManager(store=store).sessions["bk"]

    assert restored.game_over_reason == "bankrupt"
    ok, msg = GameManager(store=store).execute_action(restored, "buy", company.name, 1)
    assert (ok, msg) == (False, GAME_OVER)


def test_live_game_at_zero_net_worth_restores_live(store, market, player, company):
    """Net worth <= 0 mid-turn is not bankruptcy until the end-of-turn check says so."""
    _spike_short_into_bankruptcy(market, player, company)
    session = GameSession(game_id="dip", market=market, player=player, seed=1234, news_history=[])

    restored = _persisted_then_restored(store, session)

    assert restored.game_over_reason is None


def _store_legacy_row(store, game_id, market, player):
    state = serialize_game_state(market, player, 1234)
    del state["game_over_reason"]  # written before the field existed
    store.save_session(game_id, state, [], 1234)


def test_legacy_row_past_the_final_turn_restores_completed(store, market, player):
    market.turn = MAX_TURNS + 1
    _store_legacy_row(store, "old-done", market, player)

    assert GameManager(store=store).sessions["old-done"].game_over_reason == "completed"


def test_legacy_row_at_zero_net_worth_restores_live(store, market, player, company):
    _spike_short_into_bankruptcy(market, player, company)
    _store_legacy_row(store, "old-dip", market, player)

    assert GameManager(store=store).sessions["old-dip"].game_over_reason is None


@pytest.mark.parametrize("reason", ["bankrupt", "completed"])
def test_finished_save_loads_finished_through_the_api(reason, store, save_dir, bankrupt_session, company):
    session = bankrupt_session
    session.game_over_reason = reason
    client = TestClient(app)
    assert client.post("/api/game/save", json={"game_id": "bk", "slot": "finished"}).status_code == 200

    body = client.post("/api/game/load", json={"slot": "finished"}).json()

    assert body["success"] is True, body["message"]
    assert body["state"]["game_over"] is True
    assert body["state"]["game_over_reason"] == reason
    assert body["final_stats"]["game_over_reason"] == reason
    loaded_id = body["game_id"]
    try:
        trade = client.post("/api/game/action", json={
            "game_id": loaded_id, "action": "buy", "company": company.name, "shares": 1,
        }).json()
        assert (trade["success"], trade["message"]) == (False, GAME_OVER)

        turn = body["state"]["turn"]
        advanced = client.post("/api/game/advance", json={"game_id": loaded_id}).json()
        assert advanced["game_over"] is True
        assert advanced["state"]["turn"] == turn
    finally:
        game_manager.sessions.pop(loaded_id, None)


def test_live_save_loads_live_through_the_api(store, save_dir, market, player):
    session = GameSession(game_id="ok", market=market, player=player, seed=1234, news_history=[])
    game_manager.sessions["ok"] = session
    client = TestClient(app)
    try:
        assert client.post("/api/game/save", json={"game_id": "ok", "slot": "live"}).status_code == 200
        body = client.post("/api/game/load", json={"slot": "live"}).json()
        game_manager.sessions.pop(body["game_id"], None)
    finally:
        game_manager.sessions.pop("ok", None)

    assert body["state"]["game_over"] is False
    assert body["state"]["game_over_reason"] is None
    assert body["final_stats"] is None
