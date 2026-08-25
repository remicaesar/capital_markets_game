"""
Bug #8: options auto-exercise at expiry was unreachable code.
Bug #9: an expired ITM put never left the book.

`process_expired_options` only acts on contracts where `is_expired()` is true, and
`exercise_option` refused any contract where `is_expired()` is true. So settlement
could never exercise anything: a deeply ITM call held against $1,000,000 of cash
expired worthless with the message "insufficient funds".

The put branch additionally failed to book the contract for removal when exercise
failed, so an ITM put sat on the book forever, silently re-counted into net worth
every remaining turn.
"""

import pytest

from models.options import OptionType


def _buy_call(market, player, company, strike, contracts=1, expiry=2):
    ok, msg, _ = player.buy_option(market, company.name, "call", strike, contracts,
                                   turns_to_expiry=expiry)
    assert ok, msg
    return player.options_positions[-1]


def _buy_put(market, player, company, strike, contracts=1, expiry=2):
    ok, msg, _ = player.buy_option(market, company.name, "put", strike, contracts,
                                   turns_to_expiry=expiry)
    assert ok, msg
    return player.options_positions[-1]


def test_itm_call_is_exercised_at_expiry(market, player, company):
    player.cash = 500_000
    option = _buy_call(market, player, company, strike=80.0)  # price 100, deep ITM
    cash_before = player.cash

    market.turn = option.expiry_turn + 1
    messages = player.process_expired_options(market)

    assert player.portfolio.get(company.name, (0, 0))[0] == 100, \
        f"shares were not delivered; messages={messages}"
    assert player.cash < cash_before  # paid the strike
    assert player.options_positions == []
    assert any("Auto-exercised" in m for m in messages)


def test_call_settles_at_intrinsic_less_premium(market, player, company):
    """
    Bought 20 points ITM and held to expiry with no move: the loss is exactly the
    time value that decayed, never the whole premium.
    """
    player.cash = 500_000
    option = _buy_call(market, player, company, strike=80.0)
    premium = option.total_premium_paid()
    intrinsic = 20.0 * 100  # (price 100 - strike 80) * 100 shares

    market.turn = option.expiry_turn + 1
    player.process_expired_options(market)

    assert player.options_pnl_realized == pytest.approx(intrinsic - premium, abs=1e-6)
    # The whole premium being booked as a loss was the bug.
    assert player.options_pnl_realized > -premium


def test_itm_call_exercise_is_profitable_when_the_stock_runs(market, player, company):
    """A call that finishes well above its strike must book a real gain."""
    player.cash = 500_000
    option = _buy_call(market, player, company, strike=80.0)
    premium = option.total_premium_paid()

    company.price = 150.0
    market.turn = option.expiry_turn + 1
    player.process_expired_options(market)

    intrinsic = 70.0 * 100  # (150 - 80) * 100 shares
    assert player.options_pnl_realized > 0
    assert player.options_pnl_realized == pytest.approx(intrinsic - premium, abs=1e-6)


def test_itm_put_is_exercised_and_leaves_the_book(market, player, company):
    """The exact leak: ITM put, shares held, must settle once and disappear."""
    player.cash = 500_000
    player.buy(market, company, 100)
    option = _buy_put(market, player, company, strike=120.0)  # price 100, ITM

    market.turn = option.expiry_turn + 1
    messages = player.process_expired_options(market)

    assert player.options_positions == [], "expired put stayed on the book"
    assert company.name not in player.portfolio, "shares were not delivered into the put"
    assert any("Auto-exercised" in m for m in messages)


def test_expired_options_never_survive_a_settlement_pass(market, player, company):
    """
    Regression guard for the leak in general: whatever happens to an expired
    contract, a second settlement pass must find nothing left to do.
    """
    player.cash = 500_000
    player.buy(market, company, 100)
    _buy_put(market, player, company, strike=120.0)     # ITM, deliverable
    _buy_call(market, player, company, strike=200.0)    # OTM, worthless
    option = _buy_call(market, player, company, strike=80.0)  # ITM, affordable

    market.turn = option.expiry_turn + 1

    first = player.process_expired_options(market)
    assert player.options_positions == []
    assert len(first) == 3

    second = player.process_expired_options(market)
    assert second == [], "an expired contract was settled twice"


def test_itm_option_that_cannot_settle_is_still_removed(market, player, company):
    """A call the player cannot afford to exercise expires - but must not linger."""
    option = _buy_call(market, player, company, strike=90.0)
    player.cash = 1.0  # cannot pay the strike

    market.turn = option.expiry_turn + 1
    messages = player.process_expired_options(market)

    assert player.options_positions == []
    assert len(messages) == 1
    assert "could not be exercised" in messages[0]
    assert "cash" in messages[0]


def test_unaffordable_call_reports_the_real_reason(market, player, company):
    """The old message blamed 'insufficient funds' even with $1M available."""
    player.cash = 500_000
    option = _buy_call(market, player, company, strike=80.0)

    market.turn = option.expiry_turn + 1
    messages = player.process_expired_options(market)

    assert not any("insufficient funds" in m for m in messages)


def test_otm_option_expires_worthless(market, player, company):
    option = _buy_call(market, player, company, strike=200.0)
    premium = option.total_premium_paid()

    market.turn = option.expiry_turn + 1
    messages = player.process_expired_options(market)

    assert player.options_positions == []
    assert player.options_pnl_realized == pytest.approx(-premium)
    assert any("worthless" in m for m in messages)


def test_unexpired_options_are_left_alone(market, player, company):
    player.cash = 500_000
    option = _buy_call(market, player, company, strike=80.0)

    market.turn = option.expiry_turn  # not yet expired
    messages = player.process_expired_options(market)

    assert messages == []
    assert len(player.options_positions) == 1


def test_manual_exercise_still_refuses_expired_contracts(market, player, company):
    """
    allow_expired must stay off by default. A player must not be able to reach back
    past expiry by hand.
    """
    player.cash = 500_000
    option = _buy_call(market, player, company, strike=80.0)
    market.turn = option.expiry_turn + 1

    ok, message = player.exercise_option(market, option.id)

    assert ok is False
    assert "expired" in message
    assert len(player.options_positions) == 1


def test_expired_options_stop_counting_toward_net_worth(market, player, company):
    """The leaked put kept adding its intrinsic value to net worth every turn."""
    player.cash = 500_000
    player.buy(market, company, 100)
    option = _buy_put(market, player, company, strike=120.0)

    market.turn = option.expiry_turn + 1
    player.process_expired_options(market)

    assert player.options_value(market) == 0.0
