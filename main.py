#!/usr/bin/env python3
"""
Ultra Advanced Stock Market CLI Game
====================================
Main entry point for the capital markets game.

Run:
$ pip install rich numpy
$ python main.py

Options:
$ python main.py --seed 12345          # Reproducible game with specific seed
$ python main.py --load                # Load last autosave
$ python main.py --load mysave         # Load specific save slot
$ python main.py --list-saves          # List available saves
$ python main.py --new                 # Force new game (ignore autosave)
"""

import random
import argparse
import numpy as np
from rich.console import Console
from rich.panel import Panel
from rich.columns import Columns
from rich.table import Table

from models.market import Market
from models.player import Player
from ui.display import (
    display_advanced_stats,
    display_portfolio_analysis,
    display_market_analysis,
    create_market_table,
    create_psychology_panel
)
from ui.input_helpers import get_int_input, get_company_input
from config.settings import MAX_TURNS, TRANSACTION_FEE
from utils.save_manager import (
    save_game, load_game, deserialize_game_state,
    list_saves, delete_save, get_save_path, validate_slot, InvalidSlotName
)

console = Console(width=120)  # Set reasonable width for better formatting


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Ultra Advanced Stock Market CLI Game",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                    Start new game or continue autosave
  python main.py --seed 42          Start reproducible game with seed 42
  python main.py --load             Load last autosave
  python main.py --load mysave      Load specific save slot
  python main.py --save-slot quick  Use 'quick' as save slot name
  python main.py --list-saves       Show all available saves
  python main.py --new              Force new game (ignore autosave)
        """
    )
    parser.add_argument(
        '--seed', type=int, default=None,
        help='Random seed for reproducible game (integer)'
    )
    parser.add_argument(
        '--load', nargs='?', const='autosave', default=None,
        help='Load saved game (default: autosave, or specify slot name)'
    )
    parser.add_argument(
        '--save-slot', type=str, default='autosave',
        help='Save slot name (default: autosave)'
    )
    parser.add_argument(
        '--list-saves', action='store_true',
        help='List all available save files and exit'
    )
    parser.add_argument(
        '--new', action='store_true',
        help='Force new game, ignoring any existing autosave'
    )
    parser.add_argument(
        '--no-autosave', action='store_true',
        help='Disable automatic saving after each turn'
    )
    return parser.parse_args()


def display_saves():
    """Display available save files"""
    saves = list_saves()
    if not saves:
        console.print("[yellow]No save files found.[/yellow]")
        return

    table = Table(title="Available Saves")
    table.add_column("Slot", style="cyan")
    table.add_column("Turn", justify="right")
    table.add_column("Seed", justify="right")
    table.add_column("Timestamp")

    for save in saves:
        table.add_row(
            save["slot"],
            str(save["turn"]),
            str(save["seed"]) if save["seed"] else "-",
            save["timestamp"][:19] if save["timestamp"] else "-"
        )

    console.print(table)


def initialize_random(seed: int = None) -> int:
    """Initialize random number generators with seed, return the seed used"""
    if seed is None:
        seed = random.randint(0, 2**31 - 1)

    random.seed(seed)
    np.random.seed(seed)
    return seed


def main():
    """Main game loop"""
    args = parse_args()

    # Handle --list-saves
    if args.list_saves:
        display_saves()
        return

    # Reject unusable slot names up front rather than at the first autosave
    for slot_arg in (args.save_slot, args.load):
        if slot_arg is not None:
            try:
                validate_slot(slot_arg)
            except InvalidSlotName as exc:
                console.print(f"[red]{exc}[/red]")
                return

    # Initialize game state
    market = None
    player = None
    game_seed = None
    save_slot = args.save_slot
    loaded_from_save = False

    # Try to load game if requested
    if args.load:
        save_slot = args.load
        state = load_game(save_slot)
        if state:
            market, player, game_seed = deserialize_game_state(state)
            loaded_from_save = True
            # Re-initialize RNG with saved seed for consistency
            if game_seed is not None:
                initialize_random(game_seed)
            console.print(f"[green]Loaded save '{save_slot}' at turn {market.turn}[/green]")
            if game_seed:
                console.print(f"[dim]Seed: {game_seed}[/dim]")
        else:
            console.print(f"[yellow]Save '{save_slot}' not found. Starting new game.[/yellow]")

    # Check for autosave if not forcing new game and not explicitly loading
    if market is None and not args.new and args.load is None:
        state = load_game('autosave')
        if state:
            console.print("[cyan]Autosave found.[/cyan]")
            resume = input("Resume previous game? (Y/n): ").strip().lower()
            if not resume.startswith('n'):
                market, player, game_seed = deserialize_game_state(state)
                loaded_from_save = True
                if game_seed is not None:
                    initialize_random(game_seed)
                console.print(f"[green]Resumed at turn {market.turn}[/green]")

    # Start new game if needed
    if market is None:
        game_seed = initialize_random(args.seed)
        market = Market()
        player = Player()
        console.print(f"[dim]Game seed: {game_seed}[/dim]")

    welcome = """
🎯 Goal: Beat the market with $10,000 starting capital!
⚠️ WARNING: This market is ULTRA REALISTIC:
   • News can be misleading or have delayed effects
   • Algorithmic traders compete against you
   • Market psychology drives irrational moves
   • Hidden forces affect prices
   • Crisis events can strike anytime

📊 Commands: buy, sell, short, cover, hold, analysis, hints, save, quit
📉 Short selling: Profit when prices fall (50% margin required, beware margin calls!)
💡 Watch for: RSI extremes, momentum shifts, regime changes
"""

    if not loaded_from_save:
        console.print(Panel("[bold red]ULTRA ADVANCED STOCK MARKET GAME[/bold red]" + welcome, style="red"))
        console.print(f"[dim]Tip: Use --seed {game_seed} to replay this exact market[/dim]")
        input("\nPress Enter to begin your trading career...")

    while market.turn <= MAX_TURNS:
        console.clear()

        # Main display
        market_table = create_market_table(market, player)
        stats_panel = display_advanced_stats(player, market)
        psych_panel = create_psychology_panel(market)

        # Layout with better organization
        console.print(market_table)
        console.print()
        
        # Side-by-side panels for better space usage
        console.print(Columns([stats_panel, psych_panel], equal=True, expand=True))
        console.print()
        
        # Portfolio analysis
        portfolio_table = display_portfolio_analysis(player, market)
        console.print(portfolio_table)

        # Actions
        console.print("\n[bold]Actions:[/bold] buy | sell | short | cover | hold | analysis | hints | save | quit")
        action = input("\n> ").strip().lower()

        if action == "buy":
            cname = get_company_input(market)
            if not cname:
                continue
            company = market.companies[cname]
            max_shares = int(player.cash // (company.price * (1 + TRANSACTION_FEE)))
            if max_shares == 0:
                console.print("[red]❌ Not enough cash to buy any shares.[/red]")
                input("\nPress Enter to continue...")
                continue
            console.print(f"Max affordable shares: {max_shares:,}")
            console.print(f"RSI: {company.relative_strength:.0f} | Momentum: {company.momentum_score * 100:+.1f}%")
            qty = get_int_input("Shares to buy: ", 1, max_shares)
            if qty:
                player.buy(market, company, qty)

        elif action == "sell":
            if not player.portfolio:
                console.print("[yellow]No holdings to sell.[/yellow]")
                input("\nPress Enter to continue...")
                continue
            cname = get_company_input(market)
            if cname not in player.portfolio:
                console.print("[red]❌ You don't own that stock.[/red]")
                input("\nPress Enter to continue...")
                continue
            owned = player.portfolio[cname][0]
            console.print(f"Shares owned: {owned:,}")
            qty = get_int_input("Shares to sell: ", 1, owned)
            if qty:
                player.sell(market, market.companies[cname], qty)

        elif action == "short":
            cname = get_company_input(market)
            if not cname:
                continue
            company = market.companies[cname]

            # Calculate max shortable shares based on margin
            available_margin = player.available_margin(market)
            margin_per_share = company.price * 0.5  # SHORT_MARGIN_REQUIREMENT
            fee_per_share = company.price * 0.015  # locate + transaction fee
            cost_per_share = margin_per_share + fee_per_share
            max_shares = int(available_margin // cost_per_share) if cost_per_share > 0 else 0

            if max_shares == 0:
                console.print("[red]❌ Insufficient margin to short any shares.[/red]")
                console.print(f"[dim]Available margin: ${available_margin:,.2f}[/dim]")
                input("\nPress Enter to continue...")
                continue

            console.print(f"[magenta]Short selling {company.name} @ ${company.price:.2f}[/magenta]")
            console.print(f"Available margin: ${available_margin:,.2f}")
            console.print(f"Max shortable shares: {max_shares:,}")
            console.print(f"RSI: {company.relative_strength:.0f} | Momentum: {company.momentum_score * 100:+.1f}%")
            console.print("[dim]Tip: Profit when price goes DOWN. Risk: unlimited if price rises.[/dim]")

            qty = get_int_input("Shares to short: ", 1, max_shares)
            if qty:
                player.short(market, company, qty)

        elif action == "cover":
            if not player.short_positions:
                console.print("[yellow]No short positions to cover.[/yellow]")
                input("\nPress Enter to continue...")
                continue

            # Show current short positions
            console.print("[bold]Current short positions:[/bold]")
            for name, (shares, borrow_price) in player.short_positions.items():
                current_price = market.companies[name].price
                pnl = (borrow_price - current_price) * shares
                pnl_color = "green" if pnl >= 0 else "red"
                console.print(f"  {name}: {shares} shares @ ${borrow_price:.2f} → ${current_price:.2f} [{pnl_color}]P/L: ${pnl:,.2f}[/{pnl_color}]")

            cname = get_company_input(market)
            if cname not in player.short_positions:
                console.print("[red]❌ You don't have a short position in that stock.[/red]")
                input("\nPress Enter to continue...")
                continue

            shorted = player.short_positions[cname][0]
            console.print(f"Shares shorted: {shorted:,}")
            qty = get_int_input("Shares to cover: ", 1, shorted)
            if qty:
                player.cover(market, market.companies[cname], qty)

        elif action == "hold":
            console.print("[blue]⏩ Holding positions...[/blue]")

        elif action == "analysis":
            console.clear()
            console.print(display_market_analysis(market))
            console.print()

            # Sector analysis
            sector_performance = {}
            for company in market.companies.values():
                if company.sector not in sector_performance:
                    sector_performance[company.sector] = []
                sector_performance[company.sector].append(company.get_change_pct())

            console.print("[bold]Sector Performance:[/bold]")
            for sector, changes in sorted(sector_performance.items()):
                avg_change = sum(changes) / len(changes) * 100
                color = "green" if avg_change > 0 else "red"
                console.print(f"  {sector}: [{color}]{avg_change:+.1f}%[/{color}]")

            input("\nPress Enter to continue...")
            continue

        elif action == "hints":
            hints = [
                "💡 High RSI (>70) often precedes reversals... but not always",
                "💡 In bear markets, correlations increase - diversification fails",
                "💡 Watch for volume spikes - someone knows something",
                "💡 Regime changes invalidate old strategies",
                "💡 Smart money moves before news breaks",
                "💡 Fear and greed extremes mark turning points",
                "💡 Crisis events favor low-beta defensive stocks",
                "💡 Some news has delayed effects - patience pays",
                "💡 Short selling: profit in bear markets, but losses are unlimited",
                "💡 High RSI + momentum slowing = potential short opportunity",
                "💡 Shorting high-beta stocks amplifies gains AND losses",
                "💡 Borrow fees eat into short profits over time",
                "💡 Large orders move the market against you (slippage)",
                "💡 Split large orders to reduce market impact costs"
            ]
            console.print(Panel(random.choice(hints), title="💡 Trading Wisdom", style="cyan"))
            input("\nPress Enter to continue...")
            continue

        elif action == "save":
            slot_name = input("Save slot name (Enter for autosave): ").strip() or "autosave"
            try:
                save_path = save_game(market, player, game_seed, slot_name)
            except InvalidSlotName as exc:
                console.print(f"[red]❌ {exc}[/red]")
                input("\nPress Enter to continue...")
                continue
            console.print(f"[green]Game saved to {save_path}[/green]")
            input("\nPress Enter to continue...")
            continue

        elif action == "quit":
            if input("Really quit? (y/N): ").lower().startswith("y"):
                # Offer to save before quitting
                if input("Save before quitting? (Y/n): ").strip().lower() != 'n':
                    save_game(market, player, game_seed, save_slot)
                    console.print(f"[green]Game saved to '{save_slot}'[/green]")
                break
            continue

        else:
            console.print("[red]Invalid command.[/red]")
            input("\nPress Enter to continue...")
            continue

        # End of turn
        player.collect_dividends(market)
        player.pay_borrow_fees(market)  # Pay borrowing costs on short positions
        player.update_metrics(market)

        # Check for margin calls on short positions
        margin_call_events = player.check_margin_call(market)
        if margin_call_events:
            for event in margin_call_events:
                console.print(f"[red]{event}[/red]")
            input("\nPress Enter to continue...")

        # `<=` not `<`: on the final turn the clock still has to tick over to
        # MAX_TURNS + 1, otherwise the `while` condition never goes false and the
        # game loops on turn 50 forever without ever reaching the results screen.
        if market.turn <= MAX_TURNS:
            if market.turn == MAX_TURNS:
                input("\nPress Enter to close out the final turn...")
            else:
                input("\nPress Enter to advance to next turn...")
            # Advance turn and capture news events
            news_events = market.advance_turn(player)

            # Auto-save after each turn (unless disabled)
            if not args.no_autosave:
                save_game(market, player, game_seed, save_slot)

            # Display news events if any
            if news_events:
                news_text = "\n".join(news_events)
                console.print(Panel(news_text, title="📰 MARKET NEWS", style="bold yellow", border_style="yellow"))
                console.print()  # Add spacing after news
            else:
                console.print("[dim]No significant news this turn.[/dim]")
                console.print()

    # Game Over
    console.clear()
    worth = player.net_worth(market)
    ret = player.total_return_pct(market)
    sharpe = player.calculate_sharpe_ratio()
    max_dd = player.calculate_max_drawdown()

    # Market return for comparison
    market_return = ((market.get_market_cap() - sum(c.price_history[0] for c in market.companies.values())) /
                     sum(c.price_history[0] for c in market.companies.values())) * 100

    alpha = ret - market_return

    # Performance rating
    if sharpe > 2.0 and alpha > 20:
        msg, style = "🏅 LEGENDARY TRADER! You've mastered the markets!", "bold green"
    elif sharpe > 1.5 and alpha > 10:
        msg, style = "🏆 EXPERT PERFORMANCE! Outstanding risk-adjusted returns!", "bold cyan"
    elif sharpe > 1.0 and alpha > 0:
        msg, style = "🎉 SKILLED TRADER! You beat the market!", "green"
    elif sharpe > 0.5:
        msg, style = "👍 SOLID PERFORMANCE! Positive risk-adjusted returns.", "yellow"
    elif ret > 0:
        msg, style = "🙂 Break-even trader. Room for improvement.", "yellow"
    else:
        msg, style = "😢 The market humbled you. Study and try again.", "red"

    summary = f"""
Final Net Worth: ${worth:,.2f}
Total Return: {ret:+.1f}%
Market Return: {market_return:+.1f}%
Alpha (Outperformance): {alpha:+.1f}%
Sharpe Ratio: {sharpe:+.2f}
Maximum Drawdown: -{max_dd:.1f}%
Total Trades: {player.trade_count}
Fees Paid: ${player.total_fees_paid:.2f}
Game Seed: {game_seed}

{msg}
"""

    console.print(Panel("🎮 [bold]GAME OVER[/bold]\n" + summary, style=style))

    # Clean up autosave on game completion
    if save_slot == 'autosave' and get_save_path('autosave').exists():
        if input("\nDelete autosave? (Y/n): ").strip().lower() != 'n':
            delete_save('autosave')
            console.print("[dim]Autosave deleted.[/dim]")

    console.print(f"\n[dim]Replay this market with: python main.py --seed {game_seed}[/dim]")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n\n[yellow]Game interrupted. Thanks for playing![/yellow]")
    except Exception as e:
        console.print(f"\n[red]An error occurred: {e}[/red]")
        console.print("[yellow]Please ensure you have required packages: pip install rich numpy[/yellow]")