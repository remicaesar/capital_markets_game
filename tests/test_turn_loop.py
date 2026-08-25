"""
Bug #7: the CLI game never ended.

`while market.turn <= MAX_TURNS` paired with `if market.turn < MAX_TURNS: advance`
meant turn 50 never advanced. The only `turn += 1` in the codebase is inside
`Market.advance_turn`, so the loop spun on the final turn forever and the results
screen was unreachable. A scripted playthrough took 50 actions but only 49 advances.
"""

import re
import subprocess
import sys
from pathlib import Path

import pytest

from config.settings import MAX_TURNS

REPO = Path(__file__).resolve().parent.parent


def test_market_advances_past_the_final_turn(market, player):
    """The clock itself must not be capped below MAX_TURNS + 1."""
    market.turn = MAX_TURNS
    market.advance_turn(player)
    assert market.turn == MAX_TURNS + 1


def test_cli_guard_lets_the_final_turn_tick_over():
    """
    The loop condition and the advance guard must agree. If the loop runs while
    `turn <= MAX_TURNS` but only advances while `turn < MAX_TURNS`, the final turn
    is a fixed point and the loop never exits.
    """
    src = (REPO / "main.py").read_text()

    loop = re.search(r"while market\.turn (<=?) MAX_TURNS:", src)
    guard = re.search(r"if market\.turn (<=?) MAX_TURNS:\n\s+if market\.turn == MAX_TURNS", src)

    assert loop, "could not find the main game loop"
    assert guard, "could not find the advance guard"
    assert loop.group(1) == guard.group(1), (
        f"loop runs while turn {loop.group(1)} MAX_TURNS but only advances while "
        f"turn {guard.group(1)} MAX_TURNS - the final turn can never end"
    )


@pytest.mark.slow
def test_cli_playthrough_reaches_the_results_screen():
    """End to end: hold every turn and confirm the game actually finishes."""
    stdin = "\n" + "hold\n\n" * (MAX_TURNS + 5)
    result = subprocess.run(
        [sys.executable, "main.py", "--new", "--no-autosave", "--seed", "1"],
        input=stdin, capture_output=True, text=True, timeout=180, cwd=REPO,
    )
    out = result.stdout + result.stderr

    advances = out.count("advance to next turn") + out.count("close out the final turn")
    assert advances == MAX_TURNS, f"expected {MAX_TURNS} advances, saw {advances}"
    assert "GAME OVER" in out, "the game never reached its results screen"
    assert "Traceback" not in out
