"""
Builders for venture tests: a startup whose future is written by the test, and a
fund whose deal flow is just that startup. Money assertions should never depend on
what the outcome RNG happened to draw.
"""

import random

from models.startup import ScheduledEvent, Startup
from models.venture_fund import VentureFund


def seed_round(pre=8_000_000, raise_amount=2_000_000, period=1):
    return ScheduledEvent(period, "round", "Seed", pre, raise_amount)


def crafted_startup(schedule, startup_id=1001, name="Testco"):
    """10M common shares, then whatever rounds and ending `schedule` lists."""
    startup = Startup(
        id=startup_id, name=name, sector="AI", stage=schedule[0].round_name, pitch="",
        signals={"team": 3, "market": 3, "traction": 3},
        offered_period=schedule[0].period, schedule=schedule,
    )
    startup.open_round = schedule[0]
    return startup


def fund_offering(*startups, seed=0):
    """A fresh fund in period 1 whose only deal flow is `startups`."""
    fund = VentureFund(random.Random(seed))
    fund.deal_flow = list(startups)
    fund.commitments = {}
    return fund


def advance_to(fund, period):
    while fund.period < period:
        fund.advance()
