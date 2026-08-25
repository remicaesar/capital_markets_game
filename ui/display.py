"""
Rich-based UI components and display functions
"""

import numpy as np
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.columns import Columns

from config.settings import MAX_TURNS

console = Console()


def display_advanced_stats(player, market) -> Panel:
    """Display comprehensive player statistics"""
    net_worth = player.net_worth(market)
    total_return = player.total_return_pct(market)
    sharpe = player.calculate_sharpe_ratio()
    max_dd = player.calculate_max_drawdown()

    # Win rate calculation (include covered shorts)
    winning_trades = sum(1 for t in player.trade_history if t.get("pnl", 0) > 0)
    total_closed = sum(1 for t in player.trade_history if t["type"] in ("sell", "cover", "margin_call_cover"))
    win_rate = (winning_trades / total_closed * 100) if total_closed > 0 else 0

    # Skill rating indicator
    skill_stars = "⭐" * int(player.skill_rating * 5)

    # Short position summary
    short_value = player.short_position_value(market)
    short_pnl = player.short_position_pnl(market)

    stats_text = f"""💰 Cash: ${player.cash:,.2f}
📊 Long Positions: ${player.portfolio_value(market):,.2f}
📉 Short Positions: ${short_value:,.2f}"""

    if short_value > 0:
        pnl_color = "green" if short_pnl >= 0 else "red"
        stats_text += f"\n   └─ Short P/L: [{pnl_color}]${short_pnl:,.2f}[/{pnl_color}]"
        stats_text += f"\n📋 Available Margin: ${player.available_margin(market):,.2f}"

    stats_text += f"""
💎 Net Worth: ${net_worth:,.2f}
📈 Total Return: {total_return:+.1f}%
📊 Sharpe Ratio: {sharpe:+.2f}
📉 Max Drawdown: -{max_dd:.1f}%
🎯 Win Rate: {win_rate:.1f}%
🔄 Total Trades: {player.trade_count}
💸 Fees Paid: ${player.total_fees_paid:.2f}"""

    if player.total_slippage_paid > 0:
        stats_text += f"\n   └─ Market Impact: ${player.total_slippage_paid:.2f}"

    if player.total_borrow_fees_paid > 0:
        stats_text += f"\n   └─ Borrow Fees: ${player.total_borrow_fees_paid:.2f}"

    if player.margin_calls_received > 0:
        stats_text += f"\n⚠️ [red]Margin Calls: {player.margin_calls_received}[/red]"

    stats_text += f"\n🌟 Skill Rating: {skill_stars}"

    return Panel(stats_text, title="📋 Advanced Stats", style="cyan")


def display_portfolio_analysis(player, market) -> Table:
    """Enhanced portfolio display with risk metrics including shorts"""
    tbl = Table(title="📊 Portfolio Analysis", show_header=True, header_style="bold blue")
    tbl.add_column("Type", style="dim", min_width=5, max_width=6)
    tbl.add_column("Company", style="bold", min_width=8, max_width=12)
    tbl.add_column("Shares", justify="right", min_width=6, max_width=8)
    tbl.add_column("Entry", justify="right", min_width=7, max_width=9)
    tbl.add_column("Current", justify="right", min_width=7, max_width=9)
    tbl.add_column("Value", justify="right", min_width=8, max_width=10)
    tbl.add_column("P/L", justify="right", min_width=8, max_width=10)
    tbl.add_column("%", justify="right", min_width=5, max_width=6)
    tbl.add_column("Beta", justify="right", min_width=4, max_width=5)

    has_positions = player.portfolio or player.short_positions

    if not has_positions:
        tbl.add_row("", "No positions", "", "", "", "", "", "", "")
        return tbl

    total_long_value = player.portfolio_value(market)
    total_long_cost = 0
    portfolio_beta = 0
    total_exposure = total_long_value + player.short_position_value(market)

    # Long positions
    if player.portfolio:
        for name, (shares, avg) in sorted(player.portfolio.items()):
            company = market.companies[name]
            cur = company.price
            value = cur * shares
            cost = avg * shares
            pl = value - cost
            pl_pct = (pl / cost * 100) if cost > 0 else 0

            total_long_cost += cost
            if total_long_value > 0:
                portfolio_beta += company.beta * (value / total_long_value)

            pl_text = Text(f"${pl:,.2f}")
            pl_text.stylize("green" if pl >= 0 else "red")

            pct_text = Text(f"{pl_pct:+.1f}%")
            pct_text.stylize("green" if pl_pct >= 0 else "red")

            tbl.add_row(
                "[green]LONG[/green]",
                name,
                f"{shares:,}",
                f"${avg:.2f}",
                f"${cur:.2f}",
                f"${value:,.2f}",
                pl_text,
                pct_text,
                f"{company.beta:.2f}"
            )

    # Short positions
    if player.short_positions:
        if player.portfolio:
            tbl.add_section()

        total_short_value = 0
        total_short_pnl = 0

        for name, (shares, borrow_price) in sorted(player.short_positions.items()):
            company = market.companies[name]
            cur = company.price
            # Short value is what you'd pay to cover
            value = cur * shares
            # P&L for shorts: profit when price goes down
            pl = (borrow_price - cur) * shares
            pl_pct = (pl / (borrow_price * shares) * 100) if borrow_price > 0 else 0

            total_short_value += value
            total_short_pnl += pl

            pl_text = Text(f"${pl:,.2f}")
            pl_text.stylize("green" if pl >= 0 else "red")

            pct_text = Text(f"{pl_pct:+.1f}%")
            pct_text.stylize("green" if pl_pct >= 0 else "red")

            tbl.add_row(
                "[magenta]SHORT[/magenta]",
                name,
                f"{shares:,}",
                f"${borrow_price:.2f}",
                f"${cur:.2f}",
                f"-${value:,.2f}",
                pl_text,
                pct_text,
                f"-{company.beta:.2f}"  # Negative beta contribution
            )

    # Summary row
    tbl.add_section()

    total_pl = (total_long_value - total_long_cost) + player.short_position_pnl(market)
    total_cost = total_long_cost + sum(bp * s for _, (s, bp) in player.short_positions.items())
    total_pl_pct = (total_pl / total_cost * 100) if total_cost > 0 else 0

    total_pl_text = Text(f"${total_pl:,.2f}")
    total_pl_text.stylize("bold green" if total_pl >= 0 else "bold red")

    total_pct_text = Text(f"{total_pl_pct:+.1f}%")
    total_pct_text.stylize("bold green" if total_pl_pct >= 0 else "bold red")

    # Net exposure (longs - shorts)
    net_exposure = total_long_value - player.short_position_value(market)

    tbl.add_row(
        "[bold]NET[/bold]",
        "",
        "",
        "",
        "",
        f"[bold]${net_exposure:,.2f}[/bold]",
        total_pl_text,
        total_pct_text,
        f"[bold]{portfolio_beta:.2f}[/bold]"
    )

    return tbl


def display_market_analysis(market) -> Panel:
    """Show hidden market analysis hints"""
    hints = []

    # Regime hints
    if market.regime.turns_in_regime > 8:
        hints.append("📊 This market regime has persisted for a while...")

    # Psychology hints
    if market.psychology.fear_greed_index > 75:
        hints.append("🤔 The market seems quite euphoric lately")
    elif market.psychology.fear_greed_index < 25:
        hints.append("😰 Fear is dominating market sentiment")

    # Crisis hints
    if market.crisis_system.active_crisis:
        hints.append(f"⚠️ Crisis still affecting markets: {market.crisis_system.active_crisis.name}")

    # Correlation hints
    if market.psychology.herd_strength > 0.8:
        hints.append("🐑 Stocks are moving together more than usual")

    # Volume hints
    high_volume = [c for c in market.companies.values() if c.volume_history[-1] > 3]
    if high_volume:
        hints.append(f"📊 Unusual volume in {len(high_volume)} stocks")

    if not hints:
        hints.append("🔍 Markets appear relatively normal... or do they?")

    return Panel("\n".join(hints), title="🔮 Market Analysis", style="yellow")


def create_market_table(market, player) -> Table:
    """Enhanced market display with advanced metrics"""
    progress = (market.turn - 1) / MAX_TURNS
    progress_bar = "█" * int(progress * 20) + "░" * (20 - int(progress * 20))

    # Title with regime indicator
    regime_desc = market.regime.REGIMES[market.regime.current]["description"]
    title = f"📈 Market - Turn {market.turn}/{MAX_TURNS} [{progress_bar}] | {regime_desc}"

    tbl = Table(title=title, show_header=True, header_style="bold magenta")
    tbl.add_column("Company", style="bold", min_width=8, max_width=12)
    tbl.add_column("Sector", style="dim", min_width=6, max_width=8)
    tbl.add_column("Price", justify="right", min_width=6, max_width=8)
    tbl.add_column("Chg%", justify="right", min_width=6, max_width=7)
    tbl.add_column("Trend", justify="center", min_width=4, max_width=5)
    tbl.add_column("Vol%", justify="right", min_width=5, max_width=6)
    tbl.add_column("RSI", justify="right", min_width=4, max_width=5)
    tbl.add_column("Mom%", justify="right", min_width=6, max_width=7)

    sorted_companies = sorted(market.companies.values(), key=lambda c: (c.sector, c.name))
    current_sector = None

    for c in sorted_companies:
        if c.sector != current_sector:
            if current_sector is not None:
                tbl.add_section()
            current_sector = c.sector

        change_pct = c.get_change_pct() * 100
        change_text = Text(f"{change_pct:+.1f}")
        change_text.stylize("green" if change_pct >= 0 else "red")

        trend = c.get_trend_indicator()
        vol_text = f"{c.volatility * 100:.1f}"

        # RSI coloring
        rsi_text = Text(f"{c.relative_strength:.0f}")
        if c.relative_strength > 70:
            rsi_text.stylize("red")  # Overbought
        elif c.relative_strength < 30:
            rsi_text.stylize("green")  # Oversold

        # Momentum indicator
        mom_text = Text(f"{c.momentum_score * 100:+.1f}")
        mom_text.stylize("green" if c.momentum_score > 0 else "red")

        # Highlight owned stocks (cyan for long, magenta for short)
        if c.name in player.portfolio:
            name_style = "bold cyan"
        elif c.name in player.short_positions:
            name_style = "bold magenta"
        else:
            name_style = ""

        # Add warning for extreme moves
        if abs(change_pct) > 10:
            name_style = "bold yellow"

        tbl.add_row(
            Text(c.name, style=name_style),
            c.sector,
            f"${c.price:.2f}",
            change_text,
            trend,
            vol_text,
            rsi_text,
            mom_text
        )

    return tbl


def create_psychology_panel(market) -> Panel:
    """Display market psychology indicators"""
    sentiment = market.psychology.get_sentiment_emoji()

    # Create visual bars
    fear_greed_bar = _create_bar(market.psychology.fear_greed_index, 100, 20)
    herd_bar = _create_bar(market.psychology.herd_strength * 100, 100, 20)
    complacency_bar = _create_bar(market.psychology.complacency * 100, 100, 20)

    text = f"""🧠 Market Psychology
{sentiment} ({market.psychology.fear_greed_index:.0f}/100)
Fear/Greed: {fear_greed_bar}
Herd Level: {herd_bar}
Complacency: {complacency_bar}"""

    if market.psychology.capitulation_risk > 0.5:
        text += "\n⚠️ [red]High capitulation risk![/red]"

    return Panel(text, title="🎭 Market Sentiment", style="magenta")


def _create_bar(value: float, max_val: float, width: int) -> str:
    """Create a visual progress bar"""
    filled = int((value / max_val) * width)
    return "█" * filled + "░" * (width - filled) 