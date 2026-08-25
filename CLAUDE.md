# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Ultra-realistic stock market simulation game (Python). Players trade 10 companies across 5 sectors over 50 turns with market regimes, psychology, algorithmic opponents, crisis events, and hidden information. Both CLI and web (FastAPI) interfaces.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run CLI game
python main.py
python main.py --seed 42          # Reproducible market
python main.py --load mysave      # Load save slot
python main.py --list-saves       # List saves

# Run web server
python run_web.py                 # http://localhost:8000
```

## Tests

```bash
pip install -r requirements-dev.txt
pytest                            # full suite
pytest -m "not slow"              # skip the end-to-end CLI run
```

The suite concentrates on money maths (short accounting, options settlement, share
validation, save-path safety, turn-loop termination). When changing anything that
moves cash, add a test and verify it fails without the fix — several bugs in this
codebase were silent by construction, and only a red-then-green check catches them.

## Architecture

### Core Game Loop

`main.py` runs the CLI game loop. Each turn: player acts → dividends/fees → metrics update → margin call check → `market.advance_turn()` → display news.

`market.advance_turn()` in `models/market.py` orchestrates all subsystems: regime changes → algorithmic trading → news generation → crisis check → psychology update → per-company price updates.

### Module Responsibilities

- **models/**: Core entities. `Market` is the central orchestrator integrating all systems. `Company` holds price, valuation metrics (P/E, EPS, growth), and technical indicators (RSI, momentum, beta). `Player` manages portfolio, short positions, orders, options, and performance metrics (Sharpe, drawdown, win rate). `MarketRegime` defines four modes (bull/bear/volatile/sideways) with different volatility multipliers. `Options` handles simplified call/put contracts.

- **systems/**: Simulation engines that run each turn. `psychology.py` (fear/greed index, herd behavior, complacency, capitulation), `hidden_factors.py` (true values diverging from market price, insider sentiment, smart money), `algorithmic_trading.py` (momentum/contrarian/arbitrage bots that compete against the player), `news_system.py` (sector-specific cause-and-effect news), `crisis_events.py` (flash crashes, scandals with warning signs and multi-turn duration).

- **ui/**: Rich-based terminal display (`display.py`) and input validation (`input_helpers.py`).

- **utils/**: `save_manager.py` serializes full game state to `~/.capital_markets_game/saves/{slot}.json`. `math_utils.py` provides technical indicators.

- **web/**: FastAPI app. `routes.py` defines REST endpoints, `game_manager.py` holds game sessions, `schemas.py` has Pydantic models, `session_store.py` persists sessions to SQLite so they survive a restart. The frontend lives in `web/static/`.

  Note: `schemas.py` response models are a *projection* — any key the schema does not
  declare is silently stripped from the payload. Adding a field to `game_manager.get_game_state()`
  is not enough; declare it on the matching model or the frontend never sees it.

- **config/**: `settings.py` has all game constants (initial cash $10K, transaction fee 1%, margin requirements, slippage, difficulty params). `company_data.py` defines company names per sector.

### Key Design Patterns

- All game state flows through `Market`, which holds references to every subsystem
- Price updates combine: regime effects + psychology + algorithmic pressure + growth drift + crisis impact + sector correlations
- Dynamic difficulty: algo intensity scales with player skill rating
- `legacy/stock_market_main.py` is the original monolithic prototype (~60KB), kept for reference only and not covered by tests; the modular version under `main.py` + packages is the active codebase

## Dependencies

rich (terminal UI), numpy (math/stats), fastapi + uvicorn (web API)
