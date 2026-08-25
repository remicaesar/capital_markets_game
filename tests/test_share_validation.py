"""
Bug #5: a negative share count credited cash instead of debiting it.

`buy` only checked `cost > self.cash`, and a negative share count makes `cost`
negative, so the check always passed. Over the HTTP API this was a money printer:
`buy -100` added ~$2,400 to the account and opened a -100 share position.
"""

import pytest
from pydantic import ValidationError

from web.schemas import ActionRequest, BuyOptionRequest, PlaceOrderRequest


BAD_COUNTS = [-100, -1, 0]


@pytest.mark.parametrize("shares", BAD_COUNTS)
def test_buy_rejects_non_positive_shares(market, player, company, shares):
    cash_before = player.cash

    assert player.buy(market, company, shares) is False
    assert player.cash == cash_before
    assert company.name not in player.portfolio
    assert player.trade_count == 0


@pytest.mark.parametrize("shares", BAD_COUNTS)
def test_sell_rejects_non_positive_shares(market, player, company, shares):
    player.buy(market, company, 10)
    cash_before = player.cash
    shares_before = player.portfolio[company.name][0]

    assert player.sell(market, company, shares) is False
    assert player.cash == cash_before
    assert player.portfolio[company.name][0] == shares_before


@pytest.mark.parametrize("shares", BAD_COUNTS)
def test_short_rejects_non_positive_shares(market, player, company, shares):
    cash_before = player.cash

    assert player.short(market, company, shares) is False
    assert player.cash == cash_before
    assert company.name not in player.short_positions


@pytest.mark.parametrize("shares", BAD_COUNTS)
def test_cover_rejects_non_positive_shares(market, player, company, shares):
    player.short(market, company, 10)
    cash_before = player.cash
    shares_before = player.short_positions[company.name][0]

    assert player.cover(market, company, shares) is False
    assert player.cash == cash_before
    assert player.short_positions[company.name][0] == shares_before


def test_buy_rejects_fractional_shares(market, player, company):
    cash_before = player.cash
    assert player.buy(market, company, 1.5) is False
    assert player.cash == cash_before


def test_buy_rejects_bool_disguised_as_int(market, player, company):
    """`True == 1` in Python, so a bool must be rejected explicitly."""
    cash_before = player.cash
    assert player.buy(market, company, True) is False
    assert player.cash == cash_before


@pytest.mark.parametrize("shares", BAD_COUNTS)
def test_game_manager_rejects_non_positive_shares(market, player, company, shares):
    """The web action layer must refuse before any cash moves."""
    from web.game_manager import GameSession, game_manager

    session = GameSession(game_id="test", market=market, player=player,
                          seed=1234, news_history=[])
    cash_before = player.cash

    ok, message = game_manager.execute_action(session, "buy", company.name, shares)

    assert ok is False
    assert "positive" in message.lower()
    assert player.cash == cash_before


@pytest.mark.parametrize("shares", BAD_COUNTS)
def test_action_schema_rejects_non_positive_shares(shares):
    with pytest.raises(ValidationError):
        ActionRequest(game_id="x", action="buy", company="TechCore", shares=shares)


@pytest.mark.parametrize("shares", BAD_COUNTS)
def test_order_schema_rejects_non_positive_shares(shares):
    with pytest.raises(ValidationError):
        PlaceOrderRequest(game_id="x", order_type="limit", action="buy",
                          company="TechCore", shares=shares, limit_price=10.0)


@pytest.mark.parametrize("contracts", BAD_COUNTS)
def test_option_schema_rejects_non_positive_contracts(contracts):
    with pytest.raises(ValidationError):
        BuyOptionRequest(game_id="x", company="TechCore", option_type="call",
                         strike_price=10.0, contracts=contracts)


def test_valid_buy_still_works(market, player, company):
    """The guard must not break the happy path."""
    assert player.buy(market, company, 10) is True
    assert player.portfolio[company.name][0] == 10
    assert player.cash < 10_000
