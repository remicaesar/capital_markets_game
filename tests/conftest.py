"""
Shared fixtures.

Every test builds its market from a fixed seed so prices are deterministic, then
sets the prices it actually cares about by hand. Tests that assert on money should
never depend on what the RNG happened to produce.
"""

import os
import random
import sys
import tempfile
from pathlib import Path

import pytest

# Save files and the web session DB live under ~/.capital_markets_game, resolved from
# HOME at import time. Point HOME at a throwaway directory before anything imports
# them, so no test can read or write the player's real saves or sessions.db.
os.environ["HOME"] = tempfile.mkdtemp(prefix="cmg-test-home-")

# Make the project importable when pytest is run from the repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models.market import Market  # noqa: E402
from models.player import Player  # noqa: E402


@pytest.fixture
def market():
    return Market(random.Random(1234))


@pytest.fixture
def player():
    return Player()


@pytest.fixture
def company(market):
    """A single company with a round price, so expected values are easy to read."""
    c = sorted(market.companies.values(), key=lambda x: x.name)[0]
    c.price = 100.0
    c.volatility = 0.02
    return c
