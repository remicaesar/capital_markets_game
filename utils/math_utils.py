"""
Mathematical utilities and indicators
"""

import numpy as np
from typing import List


def calculate_rsi(prices: List[float], period: int = 14) -> float:
    """Calculate RSI (Relative Strength Index)"""
    if len(prices) < period + 1:
        return 50.0  # Neutral RSI if not enough data
    
    gains = []
    losses = []
    
    for i in range(1, len(prices)):
        change = prices[i] - prices[i - 1]
        if change > 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(change))
    
    avg_gain = np.mean(gains[-period:]) if gains else 0
    avg_loss = np.mean(losses[-period:]) if losses else 0
    
    if avg_loss == 0:
        return 100
    
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def calculate_momentum(prices: List[float], short_period: int = 5, long_period: int = 10) -> float:
    """Calculate momentum as difference between short and long moving averages"""
    if len(prices) < long_period:
        return 0.0
    
    short_ma = np.mean(prices[-short_period:])
    long_ma = np.mean(prices[-long_period:])
    
    return (short_ma - long_ma) / long_ma


def calculate_volatility(prices: List[float], period: int = 20) -> float:
    """Calculate price volatility"""
    if len(prices) < period:
        return 0.0
    
    returns = []
    for i in range(1, len(prices)):
        if prices[i-1] > 0:
            returns.append((prices[i] - prices[i-1]) / prices[i-1])
    
    if len(returns) < period:
        return 0.0
    
    return np.std(returns[-period:])


def calculate_beta(asset_returns: List[float], market_returns: List[float]) -> float:
    """Calculate beta relative to market"""
    if len(asset_returns) != len(market_returns) or len(asset_returns) < 2:
        return 1.0
    
    covariance = np.cov(asset_returns, market_returns)[0, 1]
    market_variance = np.var(market_returns)
    
    if market_variance == 0:
        return 1.0
    
    return covariance / market_variance 