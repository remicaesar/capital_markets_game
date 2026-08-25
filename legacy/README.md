# Legacy prototype

`stock_market_main.py` is the original single-file version of this game — around
1,500 lines with the market, the player, every simulation system and the terminal
UI all in one module.

It is kept for reference only. **It is not the codebase.** Everything it did now
lives in the modular packages at the repository root:

| Prototype concern | Now lives in |
| --- | --- |
| Market loop and orchestration | `models/market.py` |
| Company pricing and indicators | `models/company.py` |
| Portfolio, shorting, options | `models/player.py` |
| Regimes, psychology, crises, algos | `systems/` |
| Terminal rendering | `ui/display.py` |
| Tunable constants | `config/settings.py` |

The prototype does not share code with the current game, is not covered by the
test suite, and does not include the bug fixes made since the rewrite — notably
the net-worth accounting for short positions. Read it as a snapshot of where the
project started, not as a second way to play.
