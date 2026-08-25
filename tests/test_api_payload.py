"""
Bug #11: response_model silently dropped the chart series.

`get_game_state` built each company dict with `price_history` and `volume_history`,
but `CompanyState` declared neither, so FastAPI's response_model projection deleted
them from the payload. The frontend read `company.price_history || [company.price]`
and drew a single flat point. Nothing errored anywhere.
"""

import json

from web.schemas import GameState


def _serialized_state(session, game_manager):
    raw = game_manager.get_game_state(session)
    served = json.loads(GameState(**raw).model_dump_json())
    return raw, served


def test_chart_series_survive_the_response_model(market, player):
    from web.game_manager import GameSession, game_manager

    session = GameSession(game_id="t", market=market, player=player,
                          seed=1234, news_history=[])
    for _ in range(5):
        market.advance_turn(player)

    raw, served = _serialized_state(session, game_manager)
    company = served["companies"][0]

    assert "price_history" in company, "response_model dropped price_history"
    assert "volume_history" in company, "response_model dropped volume_history"
    assert len(company["price_history"]) > 1, "chart would render a single flat point"
    assert company["price_history"] == raw["companies"][0]["price_history"]


def test_response_model_declares_every_key_the_builder_emits(market, player):
    """
    Contract test: catches the next field someone adds to the state builder and
    forgets to declare, not just this one.
    """
    from web.game_manager import GameSession, game_manager

    session = GameSession(game_id="t", market=market, player=player,
                          seed=1234, news_history=[])
    market.advance_turn(player)

    raw, served = _serialized_state(session, game_manager)

    dropped = set(raw["companies"][0]) - set(served["companies"][0])
    assert not dropped, f"response_model silently drops: {sorted(dropped)}"
