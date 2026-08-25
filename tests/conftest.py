"""
Shared fixtures.

Every test builds its market from a fixed seed so prices are deterministic, then
sets the prices it actually cares about by hand. Tests that assert on money should
never depend on what the RNG happened to produce.
"""

import random
import sys
from pathlib import Path

import numpy as np
import pytest

# Make the project importable when pytest is run from the repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models.market import Market  # noqa: E402
from models.player import Player  # noqa: E402


@pytest.fixture
def market():
    random.seed(1234)
    np.random.seed(1234)
    return Market()


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
