"""
Each game owns its random source, and a saved game carries it.

Before this, every game drew from the process-wide `random` module: two browser
games interleaved their draws, so neither replayed its seed, and loading a save
reseeded from the integer seed, replaying turn 1's stream on turn N. The tests
below compare whole trajectories (news plus every company's price each turn), so
any draw taken from the wrong stream shows up as a divergence.
"""

import io
import json
import random

import numpy as np
import pytest
from rich.console import Console

import main as cli
import utils.save_manager as save_manager
from models.market import Market
from models.player import Player
from utils.save_manager import deserialize_game_state, serialize_game_state
from web.game_manager import GameManager
from web.session_store import SessionStore

TURNS = 8


@pytest.fixture
def save_dir(tmp_path, monkeypatch):
    d = tmp_path / "saves"
    monkeypatch.setattr(save_manager, "SAVE_DIR", d)
    return d


@pytest.fixture
def gm(tmp_path):
    return GameManager(store=SessionStore(tmp_path / "sessions.db"))


def _prices(market):
    return tuple((name, c.price) for name, c in sorted(market.companies.items()))


def _web_turn(gm, session):
    news, _, _ = gm.advance_turn(session)
    return tuple(news), _prices(session.market)


def _web_trajectory(gm, session, turns=TURNS):
    return [_web_turn(gm, session) for _ in range(turns)]


def _market_trajectory(market, player, turns=TURNS):
    return [(tuple(market.advance_turn(player)), _prices(market)) for _ in range(turns)]


# --- separate games no longer affect each other -----------------------------

def test_two_interleaved_games_with_the_same_seed_play_identically(gm):
    _, a = gm.create_game(seed=7)
    _, b = gm.create_game(seed=7)
    assert _prices(a.market) == _prices(b.market)

    traj_a, traj_b = [], []
    for _ in range(TURNS):
        traj_a.append(_web_turn(gm, a))
        traj_b.append(_web_turn(gm, b))

    assert traj_a == traj_b


def test_a_game_is_unaffected_by_another_game_advancing(gm):
    _, alone = gm.create_game(seed=7)
    reference = _web_trajectory(gm, alone)

    _, a = gm.create_game(seed=7)
    _, other = gm.create_game(seed=99)
    traj_a = []
    for _ in range(TURNS):
        _web_turn(gm, other)
        traj_a.append(_web_turn(gm, a))
        _web_turn(gm, other)

    assert traj_a == reference


# --- a saved game resumes with exactly the stream it had ---------------------

def test_save_file_resumes_the_exact_random_stream(gm, save_dir):
    _, session = gm.create_game(seed=7)
    _web_trajectory(gm, session, 5)
    gm.save_game_to_file(session, "mid")

    uninterrupted = _web_trajectory(gm, session)

    _, resumed, error = gm.load_game_from_file("mid")
    assert error is None
    assert _web_trajectory(gm, resumed) == uninterrupted


def test_session_store_restart_resumes_the_exact_random_stream(tmp_path):
    store = SessionStore(tmp_path / "sessions.db")
    before = GameManager(store=store)
    game_id, session = before.create_game(seed=7)
    _web_trajectory(before, session, 5)  # every turn is persisted

    after = GameManager(store=store)  # a server restart reads the DB back
    restored = after.get_session(game_id)
    assert restored is not None

    uninterrupted = _web_trajectory(before, session)
    assert _web_trajectory(after, restored) == uninterrupted


def test_cli_save_round_trip_resumes_the_exact_random_stream():
    """The CLI saves and loads through serialize/deserialize_game_state directly."""
    market, player = Market(random.Random(7)), Player()
    _market_trajectory(market, player, 5)
    state = json.loads(json.dumps(serialize_game_state(market, player, seed=7)))

    uninterrupted = _market_trajectory(market, player)

    loaded_market, loaded_player, seed = deserialize_game_state(state)
    assert seed == 7
    assert _market_trajectory(loaded_market, loaded_player) == uninterrupted


def test_rng_state_survives_a_pending_gauss_value():
    """random.gauss caches a second value; the saved state has to carry it."""
    market, player = Market(random.Random(7)), Player()
    market.rng.gauss(0, 1)  # leaves gauss_next populated
    state = json.loads(json.dumps(serialize_game_state(market, player, seed=7)))

    loaded_market, _, _ = deserialize_game_state(state)

    assert loaded_market.rng.gauss(0, 1) == market.rng.gauss(0, 1)


# --- saves written before the stream was stored ------------------------------

def _legacy_state(seed):
    market, player = Market(random.Random(seed)), Player()
    _market_trajectory(market, player, 3)
    state = json.loads(json.dumps(serialize_game_state(market, player, seed=seed)))
    del state["market"]["rng_state"]
    return state


def test_legacy_save_without_rng_state_reseeds_from_its_seed():
    loaded_market, loaded_player, _ = deserialize_game_state(_legacy_state(7))

    assert loaded_market.rng.getstate() == random.Random(7).getstate()
    _market_trajectory(loaded_market, loaded_player, 2)  # and it still plays


def test_legacy_save_without_rng_state_or_seed_still_loads():
    state = _legacy_state(7)
    state["seed"] = None

    loaded_market, loaded_player, seed = deserialize_game_state(state)

    assert seed is None
    _market_trajectory(loaded_market, loaded_player, 2)


def test_legacy_save_file_loads_through_the_web_api(gm, save_dir):
    save_dir.mkdir(parents=True)
    (save_dir / "old.json").write_text(json.dumps(_legacy_state(7)))

    _, session, error = gm.load_game_from_file("old")

    assert error is None
    assert session.market.turn == 4
    _web_trajectory(gm, session, 2)


def test_legacy_session_row_without_rng_state_restores(tmp_path):
    store = SessionStore(tmp_path / "sessions.db")
    store.save_session("legacy", _legacy_state(7), [], 7)

    restored = GameManager(store=store).get_session("legacy")

    assert restored is not None
    assert restored.market.turn == 4


# --- the same seed reproduces the same game in browser and terminal ----------

def test_cli_and_web_play_the_same_game_from_the_same_seed(gm, monkeypatch):
    holds = 3
    markets = []

    def recording_market(*args, **kwargs):
        m = Market(*args, **kwargs)
        markets.append(m)
        return m

    answers = iter(["hold"] * holds + ["quit"])
    quit_answers = iter(["y", "n"])

    def scripted_input(prompt=""):
        if prompt.strip() == ">":
            return next(answers)
        if prompt.startswith("Really quit") or prompt.startswith("Save before"):
            return next(quit_answers)
        return ""

    monkeypatch.setattr(cli, "Market", recording_market)
    monkeypatch.setattr(cli, "console", Console(file=io.StringIO(), width=120))
    monkeypatch.setattr("builtins.input", scripted_input)
    monkeypatch.setattr("sys.argv", ["main.py", "--new", "--no-autosave", "--seed", "7"])
    cli.main()

    _, web = gm.create_game(seed=7)
    _web_trajectory(gm, web, holds)

    (terminal,) = markets
    assert terminal.turn == web.market.turn == 1 + holds
    for name, company in web.market.companies.items():
        assert terminal.companies[name].price_history == company.price_history, name


# --- no game code draws from the process-wide random state -------------------

def _churn_global_random(salt):
    random.seed(1000 + salt)
    np.random.seed(1000 + salt)
    for _ in range(salt % 5 + 1):
        random.random()
        np.random.random()


def test_churning_the_process_wide_random_state_does_not_change_a_game(gm):
    _, calm = gm.create_game(seed=7)
    reference = _web_trajectory(gm, calm)

    _churn_global_random(0)
    _, churned = gm.create_game(seed=7)
    trajectory = []
    for turn in range(TURNS):
        _churn_global_random(turn + 1)
        trajectory.append(_web_turn(gm, churned))

    assert trajectory == reference
