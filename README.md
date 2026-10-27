# Capital Markets Game

[![tests](https://github.com/remicaesar/capital_markets_game/actions/workflows/tests.yml/badge.svg)](https://github.com/remicaesar/capital_markets_game/actions/workflows/tests.yml)
[![python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![license](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

A stock market simulator you play over 50 turns, built to make the *mechanics* of
markets visible: regime shifts, crowd psychology, algorithmic counterparties, margin
calls, market impact, and options decay — all as readable Python you can step through.

Ten companies across five sectors. You start with $25,000. Beating the index is
harder than it looks, and the code shows you exactly why.

There is also a **[venture fund mode](#venture-fund-mode)**: run a $10M VC fund for
ten years and find out why one deal has to return the whole fund.

Plays in the terminal or the browser.

```
┏━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━┳━━━━━━━┳━━━━━━━┳━━━━━━┳━━━━━━━━┓
┃ Company    ┃ Sector   ┃   Price ┃   Chg% ┃ Trend ┃  Vol% ┃  RSI ┃   Mom% ┃
┡━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━╇━━━━━━━╇━━━━━━━╇━━━━━━╇━━━━━━━━┩
│ PetroMax   │ Energy   │ $149.61 │   +2.2 │  📈   │   3.3 │   50 │   +0.0 │
│ SolarTech  │ Energy   │  $37.88 │   -5.0 │  💥   │   2.8 │   50 │   +0.0 │
├────────────┼──────────┼─────────┼────────┼───────┼───────┼──────┼────────┤
│ MegaBank   │ Finance  │ $137.73 │   -2.8 │  📉   │   2.7 │   50 │   +0.0 │
│ TradeDesk  │ Finance  │  $82.10 │   -4.1 │  💥   │   2.9 │   50 │   +0.0 │
├────────────┼──────────┼─────────┼────────┼───────┼───────┼──────┼────────┤
│ QuantumAI  │ Tech     │  $25.90 │   -6.3 │  💥   │   1.7 │   50 │   +0.0 │
│ TechCore   │ Tech     │ $104.83 │   -4.2 │  💥   │   3.2 │   50 │   +0.0 │
└────────────┴──────────┴─────────┴────────┴───────┴───────┴──────┴────────┘

╭──────── 📋 Advanced Stats ────────╮   ╭─────── 🎭 Market Sentiment ───────╮
│ 💰 Cash: $25,000.00               │   │ 🧠 Market Psychology              │
│ 📊 Long Positions: $0.00          │   │ 😐 Neutral (50/100)               │
╰───────────────────────────────────╯   ╰───────────────────────────────────╯
```

---

## Quick start

```bash
git clone https://github.com/remicaesar/capital_markets_game.git
cd capital_markets_game
pip install -r requirements.txt
```

**Terminal:**

```bash
python main.py                 # new game
python main.py --seed 42       # reproducible market
python main.py --load mysave   # resume a save
python main.py --list-saves    # show saves
```

**Browser** (adds options and limit orders — see the feature table below):

```bash
python run_web.py              # http://localhost:8000
```

**Venture fund mode:**

```bash
python venture_main.py               # terminal
python venture_main.py --seed 42     # same startups, same fates, every time
python run_web.py                    # then open http://localhost:8000/venture
```

---

## How a turn actually works

Every turn runs the same pipeline in `Market.advance_turn()`. Each stage feeds the
next, which is why a single news event can cascade into a sector-wide move:

```mermaid
flowchart TD
    A["1 . Regime check<br/>bull / bear / volatile / sideways"] --> B["2 . Smart money moves<br/>positions taken before news breaks"]
    B --> C["3 . News generated<br/>sector and market-wide effects"]
    C --> D{"4 . Crisis?"}
    D -->|warning signs| E["Warning shown to the player"]
    D -->|triggered| F["Shock scaled by each company's beta"]
    E --> G["5 . Sector correlations applied"]
    F --> G
    G --> H["6 . Per-company price update"]
    H --> I["7 . Psychology updated<br/>fear and greed respond to the move"]
    I --> J["8 . Difficulty retuned to player skill"]
```

### What sets a single company's price

`Company.update_price()` sums these, then clamps the result to ±8% per turn:

| Input | Effect |
| --- | --- |
| News and sector impact | Scaled by the regime's `news_sensitivity` — the same headline hits 4× harder in a volatile market than a bull one |
| Regime trend | Persistent drift, positive in bulls and negative in bears |
| Algorithmic pressure | Momentum, contrarian and arbitrage bots, all trading against you |
| Growth drift | The company's annual growth rate, spread across the game |
| Fear / greed | Amplifies moves in the crowd's direction at index extremes (>80 or <20) |
| Debt level | High-debt companies fall harder; downside only |
| Mean reversion | A weak pull toward a hidden intrinsic value you never see directly |
| Volatility | Gaussian shock scaled by the regime |
| Herd behaviour | Above 0.7 herd strength, moves get multiplied |

The hidden intrinsic value is the interesting one: it is set at game start somewhere
between 0.4× and 2.5× the opening price and never displayed. Arbitrage bots can see
it. You have to infer it from how prices behave.

---

## What you can trade

| | Terminal | Browser |
| --- | :---: | :---: |
| Buy / sell long | ✅ | ✅ |
| Short selling, with margin and borrow fees | ✅ | ✅ |
| Margin calls and forced liquidation | ✅ | ✅ |
| Market impact (slippage on large orders) | ✅ | ✅ |
| Dividends (earned long, owed short) | ✅ | ✅ |
| Limit / stop-loss / take-profit orders | — | ✅ |
| Call and put options | — | ✅ |
| Price and volume charts | — | ✅ |
| Save / load | ✅ | ✅ |

Costs are modelled throughout: a 1% transaction fee, 0.5% to locate borrowed shares,
0.1% per turn to hold a short, and price impact that scales with order size against
average volume. Turning a profit means clearing all of it.

### Scoring

You are graded on **alpha** (return over the market) and **Sharpe ratio**, not raw
return. Doubling your money in a market that tripled is not a good game.

If your net worth falls to zero or below, the game ends immediately as bankrupt —
in both the terminal and the browser.

---

## Venture fund mode

You are the GP of a **$10M fund with a ten-year life**. Each turn is half a year.
For the first five years, four fictional startups pitch every turn; you back the
ones you like with a **cheque now and a reserve** held back for their later rounds.
After year five the fund only follows on and waits for exits. At the end you get a
letter to your LPs that names the deal (if any) that returned the fund.

The point is to feel portfolio construction from the inside: most of your deals
will fail, and the result is decided by the one or two that do not.

### How to play

| Terminal command | Browser | What it does |
| --- | --- | --- |
| `invest <#>` | **BACK IT** on a deal card | Cheque + reserve for a startup in this half-year's deal flow. Invest again to change it, 0 to withdraw. |
| `follow <#>` | **FULL / SET / PASS** on an offer | Answer a portfolio company's new round: up to your pro-rata, or pass and get diluted. Unanswered offers are passed. |
| `explain <topic>` | click any dotted label | A short explanation of the mechanic behind that number. |
| `next` | **NEXT HALF-YEAR** | Close this half-year's rounds, charge fees, and play out the next. |

Cheques are entered in thousands in the terminal (`300` = $300k). The minimum
cheque is $100k, and cheques plus reserves in any one company are capped at 20% of
the fund, as LP agreements usually require.

### What is modelled

| Mechanic | How it works here |
| --- | --- |
| Management fee | 2% of commitments a year for ten years: $2M of the $10M never reaches a startup. Called every half-year, which is what digs the J-curve. |
| Carry | 20% of profit, after LPs get back everything they paid in, fees included (whole-fund waterfall, no hurdle). |
| Power-law outcomes | Each startup is a shutdown (45% at seed), a soft landing below its entry price (20%), or a real exit at a Pareto-distributed multiple with α = 1.0. Later stages fail less and have thinner tails. |
| Priced rounds and dilution | Every 18–24 months a company raises at a new price, issuing new shares. Your stake shrinks by pre-money ÷ post-money unless you follow on. Down rounds happen and mark you down. |
| Pro-rata | Your ownership × the round size. Drawn from that company's reserve first, then from free capital. |
| Liquidation preference | Every round is 1x non-participating preferred, pari passu. Each exit runs a waterfall shown series by series: in small sales preferred is paid first and founders get nothing. |
| Reporting | NAV at last-round marks, net TVPI, net DPI, gross MOIC (before fees and carry), net IRR, and the J-curve of LPs' cumulative cash. |
| End of fund | Companies still private at year ten are sold to a secondary buyer 30% below their mark. |

Every startup's whole life is drawn the moment it pitches, from its own random
stream (`systems/startup_outcomes.py`). Your choices never consume randomness, so a
seed replays the same startups with the same fates whatever you back — replay a
seed to see what the deal you passed on became.

The visible team / market / traction stars are the startup's hidden quality plus
noise. They help a little, and strong-looking deals cost more.

Venture-mode code: `config/venture_settings.py` (every tunable number),
`utils/venture_math.py` (dilution, pro-rata, waterfall, carry, IRR as pure
functions), `models/startup.py`, `models/venture_fund.py`, `venture_main.py`,
`ui/venture_display.py`, and `web/venture_*.py` plus `web/static/venture.*`.

---

## Layout

```
capital_markets_game/
├── main.py              # terminal game loop
├── venture_main.py      # terminal loop for venture fund mode
├── run_web.py           # web server entry point
├── config/              # tunable constants — start here to change the game
│   ├── settings.py      # cash, fees, margin, slippage, difficulty
│   └── company_data.py  # company names per sector
├── models/
│   ├── market.py        # the orchestrator: owns every subsystem, runs the turn
│   ├── company.py       # price dynamics, P/E, RSI, momentum, beta
│   ├── player.py        # portfolio, shorts, orders, options, Sharpe, drawdown
│   ├── market_regime.py # the four regimes and the transitions between them
│   └── options.py       # simplified call/put pricing and expiry
├── systems/             # the simulation engines, one file each
│   ├── psychology.py    # fear/greed index, herd behaviour
│   ├── hidden_factors.py# intrinsic values and smart-money positioning
│   ├── algorithmic_trading.py  # momentum, contrarian and arbitrage bots
│   ├── news_system.py   # sector-specific cause-and-effect events
│   └── crisis_events.py # crashes and scandals, with warning signs
├── ui/                  # rich terminal rendering and input validation
├── utils/               # save/load, technical indicator maths
├── web/                 # FastAPI app, routes, schemas, session store
├── tests/               # pytest suite
└── legacy/              # the original single-file prototype, kept for reference
```

Two entry points share one simulation core. Nothing in `models/` or `systems/` knows
whether it is being played in a terminal or a browser.

---

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

The suite concentrates on the money maths, because that is where mistakes are silent —
a wrong number looks exactly like a right one. It covers short-position accounting,
options settlement at expiry, share-count validation, save-path safety, turn-loop
termination, the bankruptcy ending, and each game's own random stream (a seed replays
the same game in the terminal and the browser, and a save resumes the exact stream it
was saved with). For venture mode it covers the shape of the outcome distribution,
dilution and pro-rata, the liquidation waterfall, fee and carry maths, and that a web
fund restored from its seed and action log is identical to the one that was saved.

Every test in it was checked by reverting the fix it guards and confirming the suite
goes red. A test that passes both before and after a fix is not a test.

---

## Known limitations

Kept honest on purpose — this is a teaching codebase, and pretending otherwise would
defeat the point.

- **Unused hooks.** `HiddenFactors.insider_sentiment`, `.debt_levels` and
  `.pending_news`, along with `MarketRegime.strength` and each regime's
  `correlation_mult`, are populated and saved but not yet read by anything. They are
  scaffolding for mechanics that are not implemented.
- **Complacency and capitulation risk are indicators only.** They are computed and
  displayed but do not currently move prices.
- **Options pricing is deliberately simplified.** Intrinsic value plus a time value
  that decays with the square root of remaining turns — not Black-Scholes.
- **Sector correlations are static.** They do not widen in bear markets the way real
  ones do.
- **A margin call can drive cash negative.** The game continues as long as net worth
  stays above zero.
- **Venture mode simplifies the term sheet.** All preferred is 1x non-participating
  and pari passu (no seniority stacks, no participation), there is no carry hurdle or
  fee step-down, every share that existed before the round you see is treated as
  common, and there are no option-pool refreshes or SAFEs/notes. Startups you pass on
  are not followed after they leave the deal flow.

---

## Roadmap

- Wire up (or remove) the unused hidden-factor hooks
- Options and limit orders in the terminal client, for parity with the browser
- Regime-dependent sector correlations

---

## Contributing

Issues and pull requests are welcome. If you change anything that touches money,
please add a test and confirm it fails without your change.

## License

[MIT](LICENSE) © Emir Murat Sezer
