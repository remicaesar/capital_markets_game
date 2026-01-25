"""
Player portfolio and trading logic
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, Tuple, List
from rich.console import Console
from rich.panel import Panel

from config.settings import (
    INITIAL_CASH, TRANSACTION_FEE, DIVIDEND_YIELD,
    SHORT_MARGIN_REQUIREMENT, SHORT_BORROW_RATE, MARGIN_CALL_THRESHOLD, SHORT_LOCATE_FEE,
    SLIPPAGE_FACTOR, BASE_DAILY_VOLUME, MIN_SLIPPAGE, MAX_SLIPPAGE
)

console = Console()


@dataclass
class Player:
    cash: float = INITIAL_CASH
    portfolio: Dict[str, Tuple[int, float]] = field(default_factory=dict)  # {name: (shares, avg_price)}
    short_positions: Dict[str, Tuple[int, float]] = field(default_factory=dict)  # {name: (shares, borrow_price)}
    trade_count: int = 0
    total_fees_paid: float = 0.0
    starting_cash: float = INITIAL_CASH

    # Advanced tracking
    trade_history: List[Dict] = field(default_factory=list)
    portfolio_values: List[float] = field(default_factory=list)
    skill_rating: float = 0.5

    # Short selling tracking
    total_borrow_fees_paid: float = 0.0
    margin_calls_received: int = 0
    total_slippage_paid: float = 0.0  # Track market impact costs

    @staticmethod
    def calculate_slippage(shares: int, company, is_buy: bool) -> tuple:
        """
        Calculate market impact slippage for an order.
        Large orders move the price against you.

        Returns: (slippage_pct, execution_price)
        """
        # Use recent volume or base volume
        avg_volume = BASE_DAILY_VOLUME
        if hasattr(company, 'volume_history') and company.volume_history:
            recent_vol = company.volume_history[-5:] if len(company.volume_history) >= 5 else company.volume_history
            avg_volume = max(BASE_DAILY_VOLUME, sum(recent_vol) / len(recent_vol) * BASE_DAILY_VOLUME)

        # Calculate slippage based on order size relative to volume
        volume_ratio = shares / avg_volume
        slippage_pct = volume_ratio * SLIPPAGE_FACTOR

        # Clamp slippage to bounds
        slippage_pct = max(MIN_SLIPPAGE, min(MAX_SLIPPAGE, slippage_pct))

        # Apply slippage direction (always against the trader)
        if is_buy:
            execution_price = company.price * (1 + slippage_pct)
        else:
            execution_price = company.price * (1 - slippage_pct)

        return slippage_pct, round(execution_price, 2)

    def portfolio_value(self, market: "Market") -> float:
        """Value of long positions"""
        return sum(market.companies[n].price * s for n, (s, _) in self.portfolio.items())

    def short_position_value(self, market: "Market") -> float:
        """Current market value of shorted shares (liability)"""
        return sum(market.companies[n].price * s for n, (s, _) in self.short_positions.items())

    def short_position_pnl(self, market: "Market") -> float:
        """Unrealized P&L on short positions"""
        pnl = 0.0
        for name, (shares, borrow_price) in self.short_positions.items():
            current_price = market.companies[name].price
            # Profit when price goes down
            pnl += (borrow_price - current_price) * shares
        return pnl

    def margin_equity(self, market: "Market") -> float:
        """
        Calculate margin equity for short positions.
        Equity = Cash + Long Portfolio Value + Short P&L
        """
        return self.cash + self.portfolio_value(market) + self.short_position_pnl(market)

    def available_margin(self, market: "Market") -> float:
        """Calculate how much margin is available for new shorts"""
        equity = self.margin_equity(market)
        # Current margin used by existing shorts
        current_short_value = self.short_position_value(market)
        margin_used = current_short_value * SHORT_MARGIN_REQUIREMENT
        return max(0, equity - margin_used)

    def max_short_value(self, market: "Market") -> float:
        """Maximum total short position value allowed"""
        return self.margin_equity(market) / SHORT_MARGIN_REQUIREMENT

    def net_worth(self, market: "Market") -> float:
        """Total net worth including short position P&L"""
        return self.cash + self.portfolio_value(market) + self.short_position_pnl(market)

    def total_return_pct(self, market: "Market") -> float:
        return ((self.net_worth(market) - self.starting_cash) / self.starting_cash) * 100

    def calculate_sharpe_ratio(self) -> float:
        """Calculate risk-adjusted returns"""
        if len(self.portfolio_values) < 2:
            return 0.0

        returns = []
        for i in range(1, len(self.portfolio_values)):
            ret = (self.portfolio_values[i] - self.portfolio_values[i - 1]) / self.portfolio_values[i - 1]
            returns.append(ret)

        if not returns or np.std(returns) == 0:
            return 0.0

        risk_free_rate = 0.001  # 0.1% per turn
        excess_returns = [r - risk_free_rate for r in returns]
        return np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(50)  # MAX_TURNS

    def calculate_max_drawdown(self) -> float:
        """Calculate maximum peak-to-trough decline"""
        if not self.portfolio_values:
            return 0.0

        peak = self.portfolio_values[0]
        max_dd = 0.0

        for value in self.portfolio_values:
            if value > peak:
                peak = value
            drawdown = (peak - value) / peak if peak > 0 else 0
            max_dd = max(max_dd, drawdown)

        return max_dd * 100  # As percentage

    def buy(self, market: "Market", company, shares: int):
        # Calculate slippage (market impact)
        slippage_pct, exec_price = self.calculate_slippage(shares, company, is_buy=True)
        slippage_cost = (exec_price - company.price) * shares

        cost = exec_price * shares * (1 + TRANSACTION_FEE)
        if cost > self.cash:
            console.print(f"[red]❌ Not enough cash. Need ${cost:,.2f}, have ${self.cash:,.2f}[/red]")
            return False

        fee = exec_price * shares * TRANSACTION_FEE
        self.cash -= cost
        self.total_fees_paid += fee
        self.total_slippage_paid += slippage_cost
        self.trade_count += 1

        # Update portfolio (use execution price as cost basis)
        total_shares, avg_price = self.portfolio.get(company.name, (0, 0))
        new_avg = ((total_shares * avg_price) + (exec_price * shares)) / (total_shares + shares)
        self.portfolio[company.name] = (total_shares + shares, new_avg)

        # Record trade
        self.trade_history.append({
            "type": "buy",
            "company": company.name,
            "shares": shares,
            "price": exec_price,
            "quoted_price": company.price,
            "slippage": slippage_pct,
            "turn": market.turn
        })

        console.print(f"[green]✅ Bought {shares} × {company.name} @ ${exec_price:.2f}[/green]")
        if slippage_pct > 0.001:
            console.print(f"[dim]   Market impact: +{slippage_pct:.2%} (${slippage_cost:.2f}) | Fee: ${fee:.2f}[/dim]")
        else:
            console.print(f"[dim]   Fee: ${fee:.2f}[/dim]")
        return True

    def sell(self, market: "Market", company, shares: int):
        if company.name not in self.portfolio:
            console.print("[red]❌ You don't own that stock.[/red]")
            return False

        owned_shares, avg_price = self.portfolio[company.name]
        if shares > owned_shares:
            console.print(f"[red]❌ You only own {owned_shares} shares.[/red]")
            return False

        # Calculate slippage (market impact)
        slippage_pct, exec_price = self.calculate_slippage(shares, company, is_buy=False)
        slippage_cost = (company.price - exec_price) * shares

        gross_proceeds = exec_price * shares
        fee = gross_proceeds * TRANSACTION_FEE
        net_proceeds = gross_proceeds - fee

        self.cash += net_proceeds
        self.total_fees_paid += fee
        self.total_slippage_paid += slippage_cost
        self.trade_count += 1

        # Calculate P&L (based on execution price)
        cost_basis = avg_price * shares
        gain_loss = gross_proceeds - cost_basis

        # Update portfolio
        remaining = owned_shares - shares
        if remaining:
            self.portfolio[company.name] = (remaining, avg_price)
        else:
            del self.portfolio[company.name]

        # Record trade
        self.trade_history.append({
            "type": "sell",
            "company": company.name,
            "shares": shares,
            "price": exec_price,
            "quoted_price": company.price,
            "slippage": slippage_pct,
            "pnl": gain_loss,
            "turn": market.turn
        })

        color = "green" if gain_loss >= 0 else "red"
        console.print(f"[{color}]💰 Sold {shares} × {company.name} @ ${exec_price:.2f} | P/L: ${gain_loss:.2f}[/{color}]")
        if slippage_pct > 0.001:
            console.print(f"[dim]   Market impact: -{slippage_pct:.2%} (${slippage_cost:.2f}) | Fee: ${fee:.2f}[/dim]")
        else:
            console.print(f"[dim]   Fee: ${fee:.2f}[/dim]")
        return True

    def short(self, market: "Market", company, shares: int) -> bool:
        """
        Open a short position (borrow and sell shares).
        Requires margin and pays locate fee. Subject to slippage.
        """
        # Check if already long this stock
        if company.name in self.portfolio:
            console.print("[red]❌ Cannot short a stock you own. Sell your long position first.[/red]")
            return False

        # Calculate slippage (selling pressure pushes price down)
        slippage_pct, exec_price = self.calculate_slippage(shares, company, is_buy=False)
        slippage_cost = (company.price - exec_price) * shares

        # Calculate costs and margin requirement (based on quoted price for margin)
        position_value = exec_price * shares
        margin_required = company.price * shares * SHORT_MARGIN_REQUIREMENT  # Margin on quoted
        locate_fee = position_value * SHORT_LOCATE_FEE
        transaction_fee = position_value * TRANSACTION_FEE
        total_margin_needed = margin_required + locate_fee + transaction_fee

        # Check available margin
        available = self.available_margin(market)
        if total_margin_needed > available:
            console.print(f"[red]❌ Insufficient margin. Need ${total_margin_needed:,.2f}, have ${available:,.2f}[/red]")
            console.print(f"[dim]Margin required: ${margin_required:,.2f} + Fees: ${locate_fee + transaction_fee:,.2f}[/dim]")
            return False

        # Execute short sale (receive proceeds at execution price)
        proceeds = position_value - transaction_fee - locate_fee
        self.cash += proceeds
        self.total_fees_paid += transaction_fee + locate_fee
        self.total_slippage_paid += slippage_cost

        # Track the short position (at execution price)
        if company.name in self.short_positions:
            existing_shares, existing_price = self.short_positions[company.name]
            new_shares = existing_shares + shares
            new_avg_price = ((existing_shares * existing_price) + (shares * exec_price)) / new_shares
            self.short_positions[company.name] = (new_shares, new_avg_price)
        else:
            self.short_positions[company.name] = (shares, exec_price)

        self.trade_count += 1

        # Record trade
        self.trade_history.append({
            "type": "short",
            "company": company.name,
            "shares": shares,
            "price": exec_price,
            "quoted_price": company.price,
            "slippage": slippage_pct,
            "turn": market.turn
        })

        console.print(f"[magenta]📉 Shorted {shares} × {company.name} @ ${exec_price:.2f}[/magenta]")
        if slippage_pct > 0.001:
            console.print(f"[dim]   Market impact: -{slippage_pct:.2%} (${slippage_cost:.2f})[/dim]")
        console.print(f"[dim]   Proceeds: ${proceeds:,.2f} | Locate fee: ${locate_fee:.2f} | Commission: ${transaction_fee:.2f}[/dim]")
        console.print(f"[dim]   Margin reserved: ${margin_required:,.2f}[/dim]")
        return True

    def cover(self, market: "Market", company, shares: int) -> bool:
        """
        Close a short position (buy shares to return). Subject to slippage.
        """
        if company.name not in self.short_positions:
            console.print("[red]❌ You don't have a short position in that stock.[/red]")
            return False

        shorted_shares, borrow_price = self.short_positions[company.name]
        if shares > shorted_shares:
            console.print(f"[red]❌ You only have {shorted_shares} shares shorted.[/red]")
            return False

        # Calculate slippage (buying pressure pushes price up)
        slippage_pct, exec_price = self.calculate_slippage(shares, company, is_buy=True)
        slippage_cost = (exec_price - company.price) * shares

        # Calculate cost to cover
        cover_cost = exec_price * shares
        transaction_fee = cover_cost * TRANSACTION_FEE
        total_cost = cover_cost + transaction_fee

        if total_cost > self.cash:
            console.print(f"[red]❌ Not enough cash to cover. Need ${total_cost:,.2f}, have ${self.cash:,.2f}[/red]")
            return False

        # Calculate P&L (profit when price went down, based on execution price)
        pnl = (borrow_price - exec_price) * shares

        # Execute cover
        self.cash -= total_cost
        self.total_fees_paid += transaction_fee
        self.total_slippage_paid += slippage_cost
        self.trade_count += 1

        # Update or remove position
        remaining = shorted_shares - shares
        if remaining > 0:
            self.short_positions[company.name] = (remaining, borrow_price)
        else:
            del self.short_positions[company.name]

        # Record trade
        self.trade_history.append({
            "type": "cover",
            "company": company.name,
            "shares": shares,
            "price": exec_price,
            "quoted_price": company.price,
            "slippage": slippage_pct,
            "pnl": pnl,
            "turn": market.turn
        })

        color = "green" if pnl >= 0 else "red"
        console.print(f"[{color}]🔄 Covered {shares} × {company.name} @ ${exec_price:.2f} | P/L: ${pnl:,.2f}[/{color}]")
        if slippage_pct > 0.001:
            console.print(f"[dim]   Market impact: +{slippage_pct:.2%} (${slippage_cost:.2f}) | Fee: ${transaction_fee:.2f}[/dim]")
        else:
            console.print(f"[dim]   Fee: ${transaction_fee:.2f}[/dim]")
        return True

    def check_margin_call(self, market: "Market") -> List[str]:
        """
        Check if any short positions trigger a margin call.
        Returns list of forced closures.
        """
        if not self.short_positions:
            return []

        forced_covers = []
        total_short_value = self.short_position_value(market)

        if total_short_value == 0:
            return []

        # Calculate margin ratio
        equity = self.margin_equity(market)
        margin_ratio = equity / total_short_value if total_short_value > 0 else float('inf')

        if margin_ratio < MARGIN_CALL_THRESHOLD:
            self.margin_calls_received += 1
            console.print(Panel(
                f"[bold red]⚠️ MARGIN CALL![/bold red]\n"
                f"Your margin ratio ({margin_ratio:.1%}) is below the {MARGIN_CALL_THRESHOLD:.0%} threshold.\n"
                f"Positions will be forcibly covered.",
                style="red"
            ))

            # Force cover positions starting with biggest losers
            positions_by_loss = sorted(
                self.short_positions.items(),
                key=lambda x: (x[1][1] - market.companies[x[0]].price) * x[1][0]
            )

            for name, (shares, borrow_price) in positions_by_loss:
                if self.margin_equity(market) / self.short_position_value(market) >= SHORT_MARGIN_REQUIREMENT:
                    break

                company = market.companies[name]
                # Force cover at market price with penalty
                cover_cost = company.price * shares * (1 + TRANSACTION_FEE * 2)  # Double fee for forced cover

                pnl = (borrow_price - company.price) * shares
                self.cash -= cover_cost
                self.total_fees_paid += company.price * shares * TRANSACTION_FEE * 2

                del self.short_positions[name]

                forced_covers.append(f"Force covered {shares} × {name} @ ${company.price:.2f} | P/L: ${pnl:,.2f}")

                self.trade_history.append({
                    "type": "margin_call_cover",
                    "company": name,
                    "shares": shares,
                    "price": company.price,
                    "pnl": pnl,
                    "turn": market.turn
                })

        return forced_covers

    def pay_borrow_fees(self, market: "Market") -> float:
        """
        Pay borrowing fees on short positions (called each turn).
        Returns total fees paid.
        """
        if not self.short_positions:
            return 0.0

        total_fee = 0.0
        for name, (shares, _) in self.short_positions.items():
            current_value = market.companies[name].price * shares
            fee = current_value * SHORT_BORROW_RATE
            total_fee += fee

        self.cash -= total_fee
        self.total_borrow_fees_paid += total_fee

        if total_fee > 0:
            console.print(f"[dim]📋 Short borrow fees: ${total_fee:.2f}[/dim]")

        return total_fee

    def collect_dividends(self, market: "Market"):
        """Collect dividends on long positions, pay dividends on short positions"""
        # Collect dividends on longs
        dividend_received = sum(
            shares * market.companies[name].price * DIVIDEND_YIELD
            for name, (shares, _) in self.portfolio.items()
        )

        # Pay dividends on shorts (you owe dividends when shorting)
        dividend_owed = sum(
            shares * market.companies[name].price * DIVIDEND_YIELD
            for name, (shares, _) in self.short_positions.items()
        )

        net_dividend = dividend_received - dividend_owed
        self.cash += net_dividend

        if dividend_received > 0:
            console.print(f"[cyan]🎁 Dividends collected: ${dividend_received:.2f}[/cyan]")
        if dividend_owed > 0:
            console.print(f"[yellow]💸 Dividends owed (short): ${dividend_owed:.2f}[/yellow]")

    def update_metrics(self, market: "Market"):
        """Update performance tracking"""
        self.portfolio_values.append(self.net_worth(market))

        # Update skill rating based on risk-adjusted performance
        if len(self.portfolio_values) >= 5:
            recent_sharpe = self.calculate_sharpe_ratio()
            if recent_sharpe > 1.0:
                self.skill_rating = min(1.0, self.skill_rating + 0.02)
            elif recent_sharpe < -0.5:
                self.skill_rating = max(0.0, self.skill_rating - 0.02) 