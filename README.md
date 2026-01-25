# Capital Markets Game

An ultra-advanced stock market simulation game with sophisticated market mechanics including hidden information, algorithmic trading, market psychology, and crisis events.

## Features

- **Market Regimes**: Bull, bear, volatile, and sideways markets with different characteristics
- **Hidden Factors**: True values, insider sentiment, debt levels, and smart money movements
- **Market Psychology**: Fear/greed index, herd behavior, complacency, and capitulation risk
- **Algorithmic Trading**: Momentum, contrarian, and arbitrage strategies competing against the player
- **Advanced News System**: Ambiguous news with multiple interpretations and delayed effects
- **Crisis Events**: Flash crashes, liquidity crises, scandals, and geopolitical shocks
- **Dynamic Difficulty**: Game adapts to player skill level
- **Comprehensive Analytics**: Sharpe ratio, drawdown, win rate, and portfolio analysis

## Project Structure

```
capital_markets_game/
├── README.md                 # This file
├── main.py                   # Main game entry point
├── config/
│   ├── __init__.py
│   ├── settings.py          # Game configuration and constants
│   └── company_data.py      # Company names and sector data
├── models/
│   ├── __init__.py
│   ├── market.py            # Main market simulation
│   ├── company.py           # Company entity with advanced metrics
│   ├── player.py            # Player portfolio and trading logic
│   └── market_regime.py     # Market regime system
├── systems/
│   ├── __init__.py
│   ├── psychology.py        # Market psychology and sentiment
│   ├── hidden_factors.py    # Hidden information system
│   ├── algorithmic_trading.py # Algo trading simulation
│   ├── news_system.py       # News generation and interpretation
│   └── crisis_events.py     # Crisis event management
├── ui/
│   ├── __init__.py
│   ├── display.py           # Rich-based UI components
│   ├── input_helpers.py     # Input validation and helpers
│   └── analytics.py         # Performance analytics and charts
└── utils/
    ├── __init__.py
    └── math_utils.py        # Mathematical utilities and indicators
```

## Installation

```bash
pip install rich numpy
```

## Running the Game

```bash
python main.py
```

## Game Commands

- `buy` - Purchase shares of a company
- `sell` - Sell shares of a company  
- `hold` - Skip trading this turn
- `analysis` - View market analysis and sector performance
- `hints` - Get random trading wisdom
- `quit` - Exit the game

## Game Mechanics

### Market Regimes
- **Bull Market**: Lower volatility, positive trends, reduced correlations
- **Bear Market**: Higher volatility, negative trends, increased correlations
- **Volatile Market**: Extreme volatility, chaotic price movements
- **Sideways Market**: Range-bound trading with mean reversion

### Hidden Information
- **True Values**: Companies have intrinsic values that may differ from market prices
- **Insider Sentiment**: Predicts future price movements
- **Smart Money**: Institutional traders with information advantage
- **Debt Levels**: Hidden leverage that amplifies crashes

### Market Psychology
- **Fear/Greed Index**: Drives irrational price movements
- **Herd Behavior**: Stocks move together at sentiment extremes
- **Complacency**: Risk in bull markets
- **Capitulation Risk**: Extreme selling pressure in bear markets

## Advanced Features

- **Dynamic Difficulty**: Game adapts to player performance
- **Sector Correlations**: Inter-sector relationships affect prices
- **Technical Indicators**: RSI, momentum, relative strength
- **Risk Metrics**: Sharpe ratio, maximum drawdown, win rate
- **Portfolio Analytics**: Beta, concentration risk, P&L tracking

## Contributing

This project demonstrates advanced game design principles and market simulation techniques. Feel free to extend the systems or add new features! 