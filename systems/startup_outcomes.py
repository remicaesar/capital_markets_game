"""
Where startup outcomes come from: a power law.

Each startup gets its own random stream, seeded once by the fund's deal flow, and
its entire life is drawn from it on the spot. So the same seed always produces the
same startups with the same fates, whatever the player chooses to back - a replay
can show you exactly what the deal you passed on became.

The fate draw:
  1. A hidden quality score (standard normal). The visible team / market / traction
     signals are that score plus noise, so they help, but only a little.
  2. Shut down, soft landing, or real exit. At seed, 45% shut down and 20% are sold
     for less than they raised (fewer of each at later stages).
  3. Real exits happen at a multiple drawn from a Pareto distribution:
         multiple = tail_min * U ** (-1 / tail_alpha)
     With alpha near 1 the tail is so fat that a handful of draws carry the total.
"""

import math
import random
from typing import Optional, Set, Tuple

from config.startup_data import NAME_ROOTS, NAME_SUFFIXES, SECTORS, TRACTION
from config.venture_settings import (
    HYPE_PREMIUM, MAX_EXIT_MULTIPLE, PERIODS_BETWEEN_ROUNDS, ROUND_NAMES,
    ROUND_VALUATION_NOISE, SHUTDOWN_RECOVERY, SOFT_LANDING_MULTIPLE, STAGE_MIX, STAGES,
)
from models.startup import ScheduledEvent, Startup


def draw_fate(rng: random.Random, stage: str, quality: float = 0.0) -> Tuple[bool, float]:
    """
    Return (shuts_down, exit_multiple).

    exit_multiple is the company's exit value over a fairly priced entry post-money -
    a company-level number, before any dilution or preference. It is 0 for a shutdown.
    """
    params = STAGES[stage]
    fail_prob = min(0.95, max(0.05, params["fail_prob"] - 0.07 * quality))
    roll = rng.random()
    if roll < fail_prob:
        return True, 0.0
    if roll < fail_prob + params["soft_landing_prob"]:
        return False, rng.uniform(*SOFT_LANDING_MULTIPLE)
    tail_min = params["tail_min"] * math.exp(0.15 * quality)
    u = 1.0 - rng.random()                       # (0, 1], never zero
    multiple = tail_min * u ** (-1.0 / params["tail_alpha"])
    return False, min(multiple, MAX_EXIT_MULTIPLE)


def _signal(rng: random.Random, quality: float) -> int:
    return max(1, min(5, round(3 + 0.9 * (quality + rng.gauss(0, 1)))))


def _unique_name(rng: random.Random, taken: Set[str]) -> str:
    while True:
        name = rng.choice(NAME_ROOTS) + rng.choice(NAME_SUFFIXES)
        if name not in taken:
            return name


def _pitch(rng: random.Random, name: str, sector: str, stage: str) -> str:
    products, customers = SECTORS[sector]
    traction = rng.choice(TRACTION[stage]).format(
        mrr=rng.randint(15, 90), growth=rng.randint(8, 25), pilots=rng.randint(3, 12),
        waitlist=rng.randint(5, 60), arr=rng.randint(1, 4) if stage == "Series A" else rng.randint(8, 30),
        customers=rng.randint(20, 400), nrr=rng.randint(105, 150),
    )
    return f"{name} builds {rng.choice(products)} for {rng.choice(customers)}. {traction}."


def _next_round_name(name: str) -> str:
    i = ROUND_NAMES.index(name)
    return ROUND_NAMES[min(i + 1, len(ROUND_NAMES) - 1)]


def generate_startup(seed: int, startup_id: int, period: int,
                     taken_names: Optional[Set[str]] = None) -> Startup:
    """Build a startup pitching in `period`, with its whole future already drawn."""
    rng = random.Random(seed)
    stage = rng.choices(list(STAGE_MIX), weights=list(STAGE_MIX.values()))[0]
    params = STAGES[stage]
    sector = rng.choice(list(SECTORS))
    name = _unique_name(rng, taken_names or set())

    quality = rng.gauss(0, 1)
    signals = {k: _signal(rng, quality) for k in ("team", "market", "traction")}

    # Strong-looking deals are bid up: you pay for the signals whether or not they
    # turn out to mean anything.
    fair_post = rng.uniform(*params["post_money"])
    hype = sum(signals.values()) / 3 - 3
    entry_post = fair_post * math.exp(HYPE_PREMIUM * hype)
    entry_raise = entry_post * rng.uniform(*params["raise_pct"])

    shuts_down, multiple = draw_fate(rng, stage, quality)
    if shuts_down:
        end = period + rng.randint(*params["periods_to_fail"])
        # A dying company can still raise a hopeful round before it runs out of road
        final_value = entry_post * rng.uniform(0.4, 1.6)
    else:
        end = period + rng.randint(*params["periods_to_exit"])
        final_value = fair_post * multiple

    schedule = [ScheduledEvent(period, "round", stage, entry_post - entry_raise, entry_raise)]
    round_name = stage
    t = period + rng.randint(*PERIODS_BETWEEN_ROUNDS)
    while t < end:
        # Valuations walk (noisily, in log space) from the entry price to the end value
        frac = (t - period) / (end - period)
        post = entry_post * (final_value / entry_post) ** frac
        post *= math.exp(rng.gauss(0, ROUND_VALUATION_NOISE))
        raise_amount = post * rng.uniform(0.15, 0.25)
        round_name = _next_round_name(round_name)
        schedule.append(ScheduledEvent(t, "round", round_name, post - raise_amount, raise_amount))
        t += rng.randint(*PERIODS_BETWEEN_ROUNDS)

    if shuts_down:
        schedule.append(ScheduledEvent(end, "shutdown", recovery=rng.uniform(*SHUTDOWN_RECOVERY)))
    else:
        schedule.append(ScheduledEvent(end, "exit", exit_value=final_value))

    return Startup(
        id=startup_id, name=name, sector=sector, stage=stage,
        pitch=_pitch(rng, name, sector, stage), signals=signals,
        offered_period=period, schedule=schedule, quality=quality,
        open_round=schedule[0],
    )
