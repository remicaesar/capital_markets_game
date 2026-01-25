"""
Options trading system for the Capital Markets Game.
Simplified model for educational purposes.
"""

import math
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from enum import Enum


class OptionType(Enum):
    CALL = "call"
    PUT = "put"


@dataclass
class Option:
    """Represents an options contract"""
    id: int
    option_type: OptionType  # call or put
    company: str
    strike_price: float
    premium: float  # price paid for the option
    contracts: int  # each contract = 100 shares
    created_turn: int
    expiry_turn: int
    underlying_price_at_purchase: float

    def is_expired(self, current_turn: int) -> bool:
        return current_turn > self.expiry_turn

    def turns_remaining(self, current_turn: int) -> int:
        return max(0, self.expiry_turn - current_turn)

    def intrinsic_value(self, current_price: float) -> float:
        """Calculate intrinsic value per share"""
        if self.option_type == OptionType.CALL:
            return max(0, current_price - self.strike_price)
        else:  # PUT
            return max(0, self.strike_price - current_price)

    def is_in_the_money(self, current_price: float) -> bool:
        """Check if option is in the money"""
        return self.intrinsic_value(current_price) > 0

    def total_intrinsic_value(self, current_price: float) -> float:
        """Total intrinsic value for all contracts (100 shares each)"""
        return self.intrinsic_value(current_price) * self.contracts * 100

    def total_premium_paid(self) -> float:
        """Total premium paid for all contracts"""
        return self.premium * self.contracts * 100

    def current_pnl(self, current_price: float, current_turn: int) -> float:
        """
        Calculate current P&L.
        For simplicity, P&L = intrinsic value - premium paid
        (ignoring time value for held options)
        """
        if self.is_expired(current_turn):
            # At expiry, value is purely intrinsic
            return self.total_intrinsic_value(current_price) - self.total_premium_paid()
        else:
            # Before expiry, estimate current value
            estimated_value = self.estimate_current_value(current_price, current_turn)
            return estimated_value - self.total_premium_paid()

    def estimate_current_value(self, current_price: float, current_turn: int) -> float:
        """Estimate current option value (simplified)"""
        intrinsic = self.total_intrinsic_value(current_price)

        # Time value decreases as expiry approaches
        turns_left = self.turns_remaining(current_turn)
        total_turns = self.expiry_turn - self.created_turn
        time_factor = turns_left / total_turns if total_turns > 0 else 0

        # Time value is roughly proportional to sqrt of time remaining
        time_value_factor = math.sqrt(time_factor) if time_factor > 0 else 0

        # Estimate time value as portion of original premium
        original_time_value = self.total_premium_paid() * 0.5  # Assume 50% was time value
        current_time_value = original_time_value * time_value_factor

        return intrinsic + current_time_value


class OptionsManager:
    """Manages options pricing and trading"""

    # Constants
    SHARES_PER_CONTRACT = 100
    DEFAULT_EXPIRY_TURNS = 5
    RISK_FREE_RATE = 0.02  # 2% per game (simplified)

    def __init__(self):
        self.next_option_id = 1

    def calculate_premium(self, company, strike_price: float,
                         option_type: OptionType, turns_to_expiry: int) -> float:
        """
        Calculate option premium using simplified Black-Scholes-like model.
        Returns premium per share.
        """
        current_price = company.price
        volatility = company.volatility

        # Moneyness (how far in/out of the money)
        if option_type == OptionType.CALL:
            moneyness = current_price / strike_price
        else:
            moneyness = strike_price / current_price

        # Time value factor (sqrt of time)
        time_factor = math.sqrt(turns_to_expiry / 10)  # Normalized to ~10 turns

        # Volatility impact
        vol_factor = volatility * 5  # Scale volatility impact

        # Base premium calculation
        # ITM options have intrinsic + time value
        # OTM options have only time value
        intrinsic = 0
        if option_type == OptionType.CALL:
            intrinsic = max(0, current_price - strike_price)
        else:
            intrinsic = max(0, strike_price - current_price)

        # Time value based on volatility and time
        # Higher vol = higher premium, more time = higher premium
        time_value = current_price * vol_factor * time_factor * 0.1

        # Adjust for moneyness (ATM options have highest time value)
        atm_factor = 1 - abs(1 - moneyness) * 0.5
        atm_factor = max(0.3, min(1.0, atm_factor))
        time_value *= atm_factor

        premium = intrinsic + time_value

        # Minimum premium
        premium = max(0.10, premium)

        return round(premium, 2)

    def get_available_strikes(self, company) -> List[float]:
        """Generate available strike prices for a company"""
        current_price = company.price
        strikes = []

        # Generate strikes at 5% intervals from -20% to +20%
        for pct in [-20, -15, -10, -5, 0, 5, 10, 15, 20]:
            strike = current_price * (1 + pct / 100)
            strike = round(strike, 2)
            if strike > 0:
                strikes.append(strike)

        return sorted(strikes)

    def create_option(self, company, option_type: OptionType,
                     strike_price: float, contracts: int,
                     current_turn: int, turns_to_expiry: int = None) -> Option:
        """Create a new option contract"""
        if turns_to_expiry is None:
            turns_to_expiry = self.DEFAULT_EXPIRY_TURNS

        premium = self.calculate_premium(
            company, strike_price, option_type, turns_to_expiry
        )

        option = Option(
            id=self.next_option_id,
            option_type=option_type,
            company=company.name,
            strike_price=strike_price,
            premium=premium,
            contracts=contracts,
            created_turn=current_turn,
            expiry_turn=current_turn + turns_to_expiry,
            underlying_price_at_purchase=company.price
        )

        self.next_option_id += 1
        return option

    def calculate_exercise_value(self, option: Option, current_price: float) -> Tuple[float, float]:
        """
        Calculate the value and cost of exercising an option.
        Returns (proceeds, cost) tuple.

        For calls: Buy shares at strike, can sell at market = profit if price > strike
        For puts: Sell shares at strike = profit if price < strike (need to own shares)
        """
        shares = option.contracts * self.SHARES_PER_CONTRACT

        if option.option_type == OptionType.CALL:
            # Exercise call: pay strike price, receive shares worth current price
            cost = option.strike_price * shares
            proceeds = current_price * shares
        else:
            # Exercise put: sell shares at strike price
            cost = current_price * shares  # Current value of shares you're selling
            proceeds = option.strike_price * shares

        return proceeds, cost


# Global options manager
options_manager = OptionsManager()
