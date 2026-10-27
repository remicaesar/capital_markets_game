"""
The outcome model: startups follow a power law, and a seed replays the same
startups with the same fates no matter what the player does.
"""

import random
import statistics

from config.venture_settings import DEALS_PER_PERIOD, INVESTMENT_PERIODS, MAX_PERIODS
from models.venture_fund import VentureFund
from systems.startup_outcomes import draw_fate, generate_startup

DRAWS = 20_000


def _multiples(stage, seed=11):
    rng = random.Random(seed)
    return sorted((draw_fate(rng, stage)[1] for _ in range(DRAWS)), reverse=True)


def _top_share(multiples, fraction=0.05):
    top = multiples[: int(len(multiples) * fraction)]
    return sum(top) / sum(multiples)


def test_most_seed_companies_return_less_than_they_raised():
    multiples = _multiples("Seed")
    below_one = sum(m < 1 for m in multiples) / len(multiples)
    assert 0.55 <= below_one <= 0.80
    assert statistics.median(multiples) < 1


def test_a_few_seed_companies_carry_most_of_the_value():
    """The power law: the top 5% of outcomes hold more value than the other 95%."""
    multiples = _multiples("Seed")
    assert _top_share(multiples) > 0.5
    assert sum(m >= 20 for m in multiples) / len(multiples) > 0.01   # real outliers exist
    assert max(multiples) >= 100


def test_later_stages_are_safer_but_have_thinner_tails():
    seed, series_a, series_b = (_multiples(s) for s in ("Seed", "Series A", "Series B"))

    def failure_rate(ms):
        return sum(m == 0 for m in ms) / len(ms)

    assert failure_rate(seed) > failure_rate(series_a) > failure_rate(series_b)
    assert _top_share(seed) > _top_share(series_a) > _top_share(series_b)


def test_a_startup_is_fully_determined_by_its_seed():
    a = generate_startup(123, 1, period=3)
    b = generate_startup(123, 1, period=3)
    assert (a.name, a.pitch, a.signals, a.schedule) == (b.name, b.pitch, b.signals, b.schedule)


def test_every_startup_ends_in_exactly_one_exit_or_shutdown_after_its_rounds():
    rng = random.Random(4)
    for i in range(500):
        startup = generate_startup(rng.getrandbits(32), i, period=rng.randint(1, 10))
        kinds = [e.kind for e in startup.schedule]
        assert kinds[-1] in ("exit", "shutdown")
        assert all(k == "round" for k in kinds[:-1])
        periods = [e.period for e in startup.schedule]
        assert periods == sorted(periods) and len(set(periods)) == len(periods)


def test_deal_flow_does_not_depend_on_the_players_choices():
    """Backing a deal must not change which startups pitch later, or how they end."""
    passive = VentureFund(random.Random(99))
    active = VentureFund(random.Random(99))

    seen_passive, seen_active = [], []
    while not passive.is_over:
        seen_passive.append([(d.name, d.schedule) for d in passive.deal_flow])
        seen_active.append([(d.name, d.schedule) for d in active.deal_flow])
        for deal in active.deal_flow[:2]:
            active.commit_to_deal(deal.id, 150_000, 100_000)
        for pos in active.positions.values():
            if pos.active and pos.startup.open_round:
                active.decide_follow_on(pos.startup.id, min(pos.pro_rata(), pos.reserve))
        passive.advance()
        active.advance()

    assert seen_passive == seen_active
    assert len(active.positions) > 0


def test_new_deals_only_arrive_during_the_investment_period():
    fund = VentureFund(random.Random(1))
    for _ in range(MAX_PERIODS):
        expected = DEALS_PER_PERIOD if fund.period <= INVESTMENT_PERIODS else 0
        assert len(fund.deal_flow) == expected
        fund.advance()
    assert fund.is_over and fund.deal_flow == []
