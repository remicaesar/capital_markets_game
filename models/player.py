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
import uuid
from models.options import Option, OptionType, options_manager

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

    # Pending orders (limit orders, stop loss, take profit)
    pending_orders: List[Dict] = field(default_factory=list)
    next_order_id: int = 1

    # Options positions
    options_positions: List[Option] = field(default_factory=list)
    options_pnl_realized: float = 0.0  # Track realized P&L from options

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
        """Total net worth including short position P&L and options"""
        return self.cash + self.portfolio_value(market) + self.short_position_pnl(market) + self.options_value(market)

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

    # =========================================================================
    # Limit Orders, Stop Loss, Take Profit
    # =========================================================================

    def place_order(self, market: "Market", order_type: str, action: str,
                    company_name: str, shares: int, limit_price: float) -> Tuple[bool, str, Dict]:
        """
        Place a pending order.

        Args:
            order_type: 'limit', 'stop_loss', or 'take_profit'
            action: 'buy', 'sell', 'short', or 'cover'
            company_name: Name of the company
            shares: Number of shares
            limit_price: Target price for execution

        Returns:
            (success, message, order_dict)
        """
        if company_name not in market.companies:
            return False, f"Company '{company_name}' not found", {}

        company = market.companies[company_name]
        current_price = company.price

        # Validate order logic
        if order_type == 'limit':
            if action == 'buy' and limit_price >= current_price:
                return False, f"Limit buy price (${limit_price:.2f}) must be below current price (${current_price:.2f})", {}
            if action == 'sell' and limit_price <= current_price:
                return False, f"Limit sell price (${limit_price:.2f}) must be above current price (${current_price:.2f})", {}
            if action == 'short' and limit_price <= current_price:
                return False, f"Limit short price (${limit_price:.2f}) must be above current price (${current_price:.2f})", {}
            if action == 'cover' and limit_price >= current_price:
                return False, f"Limit cover price (${limit_price:.2f}) must be below current price (${current_price:.2f})", {}

        elif order_type == 'stop_loss':
            if action not in ['sell', 'cover']:
                return False, "Stop loss orders can only be used for sell or cover actions", {}
            if action == 'sell':
                if company_name not in self.portfolio:
                    return False, f"You don't own any {company_name} to set a stop loss", {}
                if limit_price >= current_price:
                    return False, f"Stop loss price (${limit_price:.2f}) must be below current price (${current_price:.2f})", {}
            if action == 'cover':
                if company_name not in self.short_positions:
                    return False, f"You don't have a short position in {company_name}", {}
                if limit_price <= current_price:
                    return False, f"Stop loss for cover (${limit_price:.2f}) must be above current price (${current_price:.2f})", {}

        elif order_type == 'take_profit':
            if action not in ['sell', 'cover']:
                return False, "Take profit orders can only be used for sell or cover actions", {}
            if action == 'sell':
                if company_name not in self.portfolio:
                    return False, f"You don't own any {company_name} to set a take profit", {}
                if limit_price <= current_price:
                    return False, f"Take profit price (${limit_price:.2f}) must be above current price (${current_price:.2f})", {}
            if action == 'cover':
                if company_name not in self.short_positions:
                    return False, f"You don't have a short position in {company_name}", {}
                if limit_price >= current_price:
                    return False, f"Take profit for cover (${limit_price:.2f}) must be below current price (${current_price:.2f})", {}

        # Validate shares
        if action == 'sell' and company_name in self.portfolio:
            owned = self.portfolio[company_name][0]
            if shares > owned:
                return False, f"You only own {owned} shares of {company_name}", {}
        if action == 'cover' and company_name in self.short_positions:
            shorted = self.short_positions[company_name][0]
            if shares > shorted:
                return False, f"You only have {shorted} shares shorted", {}

        # Create the order
        order = {
            "id": self.next_order_id,
            "order_type": order_type,
            "action": action,
            "company": company_name,
            "shares": shares,
            "limit_price": limit_price,
            "created_turn": market.turn,
            "created_price": current_price,
            "status": "pending"
        }
        self.next_order_id += 1
        self.pending_orders.append(order)

        order_desc = f"{order_type.replace('_', ' ').title()} {action.upper()} {shares} {company_name} @ ${limit_price:.2f}"
        console.print(f"[cyan]📋 Order placed: {order_desc}[/cyan]")

        return True, f"Order #{order['id']} placed: {order_desc}", order

    def cancel_order(self, order_id: int) -> Tuple[bool, str]:
        """Cancel a pending order by ID"""
        for i, order in enumerate(self.pending_orders):
            if order["id"] == order_id:
                cancelled = self.pending_orders.pop(i)
                msg = f"Order #{order_id} cancelled: {cancelled['order_type']} {cancelled['action']} {cancelled['shares']} {cancelled['company']}"
                console.print(f"[yellow]❌ {msg}[/yellow]")
                return True, msg
        return False, f"Order #{order_id} not found"

    def process_pending_orders(self, market: "Market") -> List[str]:
        """
        Process all pending orders against current market prices.
        Called at the start of each turn after prices update.

        Returns list of execution messages.
        """
        executed_messages = []
        orders_to_remove = []

        for order in self.pending_orders:
            company_name = order["company"]
            if company_name not in market.companies:
                orders_to_remove.append(order["id"])
                continue

            company = market.companies[company_name]
            current_price = company.price
            limit_price = order["limit_price"]
            order_type = order["order_type"]
            action = order["action"]
            shares = order["shares"]

            should_execute = False

            # Check if order should trigger
            if order_type == 'limit':
                if action == 'buy' and current_price <= limit_price:
                    should_execute = True
                elif action == 'sell' and current_price >= limit_price:
                    should_execute = True
                elif action == 'short' and current_price >= limit_price:
                    should_execute = True
                elif action == 'cover' and current_price <= limit_price:
                    should_execute = True

            elif order_type == 'stop_loss':
                if action == 'sell' and current_price <= limit_price:
                    should_execute = True
                elif action == 'cover' and current_price >= limit_price:
                    should_execute = True

            elif order_type == 'take_profit':
                if action == 'sell' and current_price >= limit_price:
                    should_execute = True
                elif action == 'cover' and current_price <= limit_price:
                    should_execute = True

            if should_execute:
                # Validate the order can still be executed
                can_execute = True
                if action == 'sell' and (company_name not in self.portfolio or self.portfolio[company_name][0] < shares):
                    can_execute = False
                    executed_messages.append(f"⚠️ Order #{order['id']} expired: Not enough shares to sell")
                elif action == 'cover' and (company_name not in self.short_positions or self.short_positions[company_name][0] < shares):
                    can_execute = False
                    executed_messages.append(f"⚠️ Order #{order['id']} expired: No short position to cover")

                if can_execute:
                    # Execute the trade
                    success = False
                    if action == 'buy':
                        success = self.buy(market, company, shares)
                    elif action == 'sell':
                        success = self.sell(market, company, shares)
                    elif action == 'short':
                        success = self.short(market, company, shares)
                    elif action == 'cover':
                        success = self.cover(market, company, shares)

                    if success:
                        order_desc = f"{order_type.replace('_', ' ').title()}"
                        executed_messages.append(
                            f"✅ Order #{order['id']} executed: {order_desc} {action.upper()} {shares} {company_name} @ ${current_price:.2f} (target: ${limit_price:.2f})"
                        )
                    else:
                        executed_messages.append(f"⚠️ Order #{order['id']} failed to execute")

                orders_to_remove.append(order["id"])

        # Remove executed/expired orders
        self.pending_orders = [o for o in self.pending_orders if o["id"] not in orders_to_remove]

        # Print execution messages
        for msg in executed_messages:
            if msg.startswith("✅"):
                console.print(f"[green]{msg}[/green]")
            else:
                console.print(f"[yellow]{msg}[/yellow]")

        return executed_messages

    def get_pending_orders(self) -> List[Dict]:
        """Get all pending orders"""
        return self.pending_orders.copy()

    # =========================================================================
    # Options Trading
    # =========================================================================

    def buy_option(self, market: "Market", company_name: str, option_type: str,
                   strike_price: float, contracts: int, turns_to_expiry: int = 5) -> Tuple[bool, str, Dict]:
        """
        Buy a call or put option.

        Args:
            company_name: Name of the underlying company
            option_type: 'call' or 'put'
            strike_price: Strike price for the option
            contracts: Number of contracts (each = 100 shares)
            turns_to_expiry: Turns until expiration (default 5)

        Returns:
            (success, message, option_dict)
        """
        if company_name not in market.companies:
            return False, f"Company '{company_name}' not found", {}

        company = market.companies[company_name]

        # Parse option type
        try:
            opt_type = OptionType(option_type.lower())
        except ValueError:
            return False, f"Invalid option type: {option_type}. Use 'call' or 'put'", {}

        if contracts < 1:
            return False, "Must buy at least 1 contract", {}

        if strike_price <= 0:
            return False, "Strike price must be positive", {}

        # Create the option to get premium
        option = options_manager.create_option(
            company, opt_type, strike_price, contracts, market.turn, turns_to_expiry
        )

        # Calculate total cost
        total_premium = option.total_premium_paid()
        transaction_fee = total_premium * TRANSACTION_FEE

        total_cost = total_premium + transaction_fee

        if total_cost > self.cash:
            return False, f"Insufficient funds. Need ${total_cost:,.2f}, have ${self.cash:,.2f}", {}

        # Execute purchase
        self.cash -= total_cost
        self.total_fees_paid += transaction_fee
        self.options_positions.append(option)
        self.trade_count += 1

        # Record trade
        self.trade_history.append({
            "type": f"buy_{option_type}",
            "company": company_name,
            "contracts": contracts,
            "strike": strike_price,
            "premium": option.premium,
            "total_cost": total_cost,
            "expiry_turn": option.expiry_turn,
            "turn": market.turn
        })

        option_desc = f"{option_type.upper()} {company_name} @ ${strike_price:.2f}"
        console.print(f"[cyan]📋 Bought {contracts} {option_desc} contracts for ${total_premium:.2f}[/cyan]")
        console.print(f"[dim]   Premium: ${option.premium:.2f}/share | Expires: Turn {option.expiry_turn} | Fee: ${transaction_fee:.2f}[/dim]")

        option_dict = {
            "id": option.id,
            "type": option_type,
            "company": company_name,
            "strike": strike_price,
            "premium": option.premium,
            "contracts": contracts,
            "expiry_turn": option.expiry_turn
        }

        return True, f"Bought {contracts} {option_desc} contracts", option_dict

    def exercise_option(self, market: "Market", option_id: int) -> Tuple[bool, str]:
        """
        Exercise an option before expiry.

        For calls: Buy shares at strike price (must have cash)
        For puts: Sell shares at strike price (must own shares)
        """
        option = None
        for opt in self.options_positions:
            if opt.id == option_id:
                option = opt
                break

        if option is None:
            return False, f"Option #{option_id} not found"

        if option.is_expired(market.turn):
            return False, f"Option #{option_id} has expired"

        company = market.companies.get(option.company)
        if not company:
            return False, f"Company {option.company} not found"

        current_price = company.price
        shares = option.contracts * 100

        if not option.is_in_the_money(current_price):
            return False, f"Option is out of the money (current: ${current_price:.2f}, strike: ${option.strike_price:.2f})"

        if option.option_type == OptionType.CALL:
            # Exercise call: pay strike price to buy shares
            cost = option.strike_price * shares
            transaction_fee = cost * TRANSACTION_FEE

            if cost + transaction_fee > self.cash:
                return False, f"Insufficient funds to exercise. Need ${cost + transaction_fee:,.2f}"

            self.cash -= (cost + transaction_fee)
            self.total_fees_paid += transaction_fee

            # Add shares to portfolio
            existing_shares, avg_price = self.portfolio.get(option.company, (0, 0))
            if existing_shares > 0:
                new_avg = ((existing_shares * avg_price) + (shares * option.strike_price)) / (existing_shares + shares)
            else:
                new_avg = option.strike_price
            self.portfolio[option.company] = (existing_shares + shares, new_avg)

            profit = (current_price - option.strike_price) * shares - option.total_premium_paid()
            self.options_pnl_realized += profit

            console.print(f"[green]✅ Exercised CALL: Bought {shares} {option.company} @ ${option.strike_price:.2f}[/green]")
            console.print(f"[dim]   Market value: ${current_price * shares:,.2f} | Your cost: ${cost:,.2f} | Net gain: ${profit:,.2f}[/dim]")

        else:  # PUT
            # Exercise put: sell shares at strike price
            if option.company not in self.portfolio:
                return False, f"You don't own {option.company} shares to exercise the put"

            owned_shares, avg_price = self.portfolio[option.company]
            if owned_shares < shares:
                return False, f"You only own {owned_shares} shares, need {shares} to exercise"

            # Sell shares at strike price
            proceeds = option.strike_price * shares
            transaction_fee = proceeds * TRANSACTION_FEE
            net_proceeds = proceeds - transaction_fee

            self.cash += net_proceeds
            self.total_fees_paid += transaction_fee

            # Remove shares from portfolio
            remaining = owned_shares - shares
            if remaining > 0:
                self.portfolio[option.company] = (remaining, avg_price)
            else:
                del self.portfolio[option.company]

            profit = (option.strike_price - current_price) * shares - option.total_premium_paid()
            self.options_pnl_realized += profit

            console.print(f"[green]✅ Exercised PUT: Sold {shares} {option.company} @ ${option.strike_price:.2f}[/green]")
            console.print(f"[dim]   Market price: ${current_price:.2f} | Your price: ${option.strike_price:.2f} | Net gain: ${profit:,.2f}[/dim]")

        # Remove the exercised option
        self.options_positions = [o for o in self.options_positions if o.id != option_id]
        self.trade_count += 1

        self.trade_history.append({
            "type": f"exercise_{option.option_type.value}",
            "company": option.company,
            "contracts": option.contracts,
            "strike": option.strike_price,
            "market_price": current_price,
            "pnl": profit,
            "turn": market.turn
        })

        return True, f"Exercised option #{option_id} for ${profit:,.2f} profit"

    def sell_option(self, market: "Market", option_id: int) -> Tuple[bool, str]:
        """
        Sell an option back to the market before expiry.
        You receive the estimated current value minus transaction fees.
        """
        option = None
        for opt in self.options_positions:
            if opt.id == option_id:
                option = opt
                break

        if option is None:
            return False, f"Option #{option_id} not found"

        if option.is_expired(market.turn):
            return False, f"Option #{option_id} has expired and is worthless"

        company = market.companies.get(option.company)
        if not company:
            return False, f"Company {option.company} not found"

        current_price = company.price
        current_value = option.estimate_current_value(current_price, market.turn)

        # Apply bid-ask spread (you sell at slightly less than theoretical value)
        sell_value = current_value * 0.95  # 5% spread
        transaction_fee = sell_value * TRANSACTION_FEE
        net_proceeds = sell_value - transaction_fee

        pnl = net_proceeds - option.total_premium_paid()

        self.cash += net_proceeds
        self.total_fees_paid += transaction_fee
        self.options_pnl_realized += pnl

        # Remove the sold option
        self.options_positions = [o for o in self.options_positions if o.id != option_id]
        self.trade_count += 1

        self.trade_history.append({
            "type": f"sell_{option.option_type.value}",
            "company": option.company,
            "contracts": option.contracts,
            "strike": option.strike_price,
            "sell_value": sell_value,
            "pnl": pnl,
            "turn": market.turn
        })

        color = "green" if pnl >= 0 else "red"
        console.print(f"[{color}]💰 Sold {option.option_type.value.upper()} option for ${net_proceeds:,.2f} | P/L: ${pnl:,.2f}[/{color}]")

        return True, f"Sold option #{option_id} for ${net_proceeds:,.2f} (P/L: ${pnl:,.2f})"

    def process_expired_options(self, market: "Market") -> List[str]:
        """
        Process options that have expired.
        ITM options are auto-exercised if possible, OTM expire worthless.
        Called at the end of each turn.
        """
        messages = []
        options_to_remove = []

        for option in self.options_positions:
            if option.is_expired(market.turn):
                company = market.companies.get(option.company)
                if not company:
                    options_to_remove.append(option.id)
                    continue

                current_price = company.price

                if option.is_in_the_money(current_price):
                    # Try to auto-exercise ITM options
                    shares = option.contracts * 100

                    if option.option_type == OptionType.CALL:
                        cost = option.strike_price * shares
                        if cost <= self.cash:
                            # Auto-exercise
                            success, msg = self.exercise_option(market, option.id)
                            if success:
                                messages.append(f"📋 Auto-exercised ITM CALL #{option.id}: {msg}")
                            else:
                                # Can't exercise, expires worthless
                                loss = option.total_premium_paid()
                                self.options_pnl_realized -= loss
                                messages.append(f"⚠️ CALL #{option.id} expired ITM but couldn't exercise (insufficient funds). Lost ${loss:.2f}")
                                options_to_remove.append(option.id)
                        else:
                            loss = option.total_premium_paid()
                            self.options_pnl_realized -= loss
                            messages.append(f"⚠️ CALL #{option.id} expired ITM but couldn't exercise (need ${cost:.2f}). Lost ${loss:.2f}")
                            options_to_remove.append(option.id)
                    else:  # PUT
                        if option.company in self.portfolio and self.portfolio[option.company][0] >= shares:
                            success, msg = self.exercise_option(market, option.id)
                            if success:
                                messages.append(f"📋 Auto-exercised ITM PUT #{option.id}: {msg}")
                        else:
                            loss = option.total_premium_paid()
                            self.options_pnl_realized -= loss
                            messages.append(f"⚠️ PUT #{option.id} expired ITM but no shares to sell. Lost ${loss:.2f}")
                            options_to_remove.append(option.id)
                else:
                    # OTM - expires worthless
                    loss = option.total_premium_paid()
                    self.options_pnl_realized -= loss
                    opt_type = option.option_type.value.upper()
                    messages.append(f"📉 {opt_type} #{option.id} ({option.company} @ ${option.strike_price:.2f}) expired worthless. Lost ${loss:.2f}")
                    options_to_remove.append(option.id)

        # Remove expired options
        self.options_positions = [o for o in self.options_positions if o.id not in options_to_remove]

        for msg in messages:
            if "Auto-exercised" in msg:
                console.print(f"[green]{msg}[/green]")
            else:
                console.print(f"[yellow]{msg}[/yellow]")

        return messages

    def options_value(self, market: "Market") -> float:
        """Calculate total current value of all options positions"""
        total = 0.0
        for option in self.options_positions:
            company = market.companies.get(option.company)
            if company:
                total += option.estimate_current_value(company.price, market.turn)
        return total

    def get_options_positions(self) -> List[Option]:
        """Get all options positions"""
        return self.options_positions.copy() 