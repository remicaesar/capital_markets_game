#!/usr/bin/env python3
"""
Venture Fund Mode
=================
Run a $10M venture fund for ten years, half a year per turn.

Run:
$ python venture_main.py
$ python venture_main.py --seed 42     # Same startups, same fates, every time
"""

import argparse
from typing import Optional

from rich.console import Console
from rich.panel import Panel

from config.venture_glossary import MECHANICS
from config.venture_settings import (
    DEFAULT_RESERVE_RATIO, FUND_SIZE, INVESTABLE_CAPITAL, LIFETIME_FEES, MAX_PERIODS,
)
from models.market import new_game_rng
from models.venture_fund import VentureFund
from ui.venture_display import (
    concentration_table, deal_flow_table, follow_on_offers, follow_on_table, fund_panel,
    j_curve_table, money, portfolio_table, waterfall_table, final_report_panel,
)

console = Console(width=120)

COMMANDS = "invest <#> | follow <#> | explain \\[topic] | next | quit"


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Venture fund mode of the Capital Markets Game")
    parser.add_argument("--seed", type=int, default=None,
                        help="Random seed for a reproducible fund (integer)")
    return parser.parse_args(argv)


def ask_amount(prompt: str, default: Optional[float] = None) -> Optional[float]:
    """Read a dollar amount typed in thousands ('250' = $250k). Enter takes the default."""
    while True:
        raw = input(prompt).strip().lower().replace("$", "").replace("k", "")
        if not raw and default is not None:
            return default
        if raw in ("", "cancel"):
            return None
        try:
            value = float(raw) * 1000
        except ValueError:
            console.print("[red]Enter an amount in $ thousands, e.g. 250 for $250k[/red]")
            continue
        if value < 0:
            console.print("[red]Amount cannot be negative[/red]")
            continue
        return value


def pick(arg: str, count: int, what: str) -> Optional[int]:
    """Turn the '<#>' of a command into a 0-based index, or explain why not."""
    if count == 0:
        console.print(f"[yellow]No {what} right now.[/yellow]")
        return None
    try:
        index = int(arg) - 1
    except ValueError:
        index = -1
    if not 0 <= index < count:
        console.print(f"[red]Pick a {what[:-1]} number from 1 to {count}[/red]")
        return None
    return index


def explain(topic: str):
    if topic in MECHANICS:
        title, body = MECHANICS[topic]
        console.print(Panel(body, title=f"💡 {title}", style="cyan"))
        return
    console.print("[bold]Topics:[/bold] " + ", ".join(MECHANICS))
    console.print("[dim]e.g. explain pro_rata[/dim]")


def invest(fund: VentureFund, arg: str):
    index = pick(arg, len(fund.deal_flow), "deals")
    if index is None:
        return
    deal = fund.deal_flow[index]
    rnd = deal.open_round
    console.print(f"[bold]{deal.name}[/bold] raises {money(rnd.raise_amount)} at "
                  f"{money(rnd.post_money)} post. Free capital: {money(fund.available())}")
    check = ask_amount("Cheque in $k (0 to withdraw, Enter to cancel): ")
    if check is None:
        return
    reserve = 0.0
    if check > 0:
        suggested = check * DEFAULT_RESERVE_RATIO
        reserve = ask_amount(f"Reserve for follow-ons in $k [Enter = {money(suggested)}]: ",
                             default=suggested)
        if reserve is None:
            return
    ok, message = fund.commit_to_deal(deal.id, check, reserve)
    console.print(f"[{'green' if ok else 'red'}]{message}[/]")


def follow(fund: VentureFund, arg: str):
    offers = follow_on_offers(fund)
    index = pick(arg, len(offers), "offers")
    if index is None:
        return
    pos = offers[index]
    pro_rata = pos.pro_rata()
    console.print(f"Pro-rata in {pos.startup.name}: {money(pro_rata)} "
                  f"(reserve {money(pos.reserve)}, free {money(fund.available())})")
    amount = ask_amount(f"Amount in $k (0 = pass) [Enter = full pro-rata {money(pro_rata)}]: ",
                        default=pro_rata)
    if amount is None:
        return
    ok, message = fund.decide_follow_on(pos.startup.id, amount)
    console.print(f"[{'green' if ok else 'red'}]{message}[/]")


def show_turn_results(fund: VentureFund, events):
    if events:
        console.print(Panel("\n".join(events), title="📰 What happened",
                            style="bold yellow", border_style="yellow"))
    else:
        console.print("[dim]A quiet half-year.[/dim]")
    for record in fund.exits:
        if record.period == fund.period and record.waterfall is not None:
            console.print(waterfall_table(record))


def main(argv=None):
    args = parse_args(argv)
    seed, rng = new_game_rng(args.seed)
    fund = VentureFund(rng)

    console.print(Panel(
        f"[bold magenta]VENTURE FUND MODE[/bold magenta]\n\n"
        f"🎯 You are the GP of a {money(FUND_SIZE)} fund with a {MAX_PERIODS // 2}-year life.\n"
        f"💸 {money(LIFETIME_FEES)} of it goes on management fees, so you can invest "
        f"{money(INVESTABLE_CAPITAL)}.\n"
        f"📥 Each half-year a few startups pitch. Back the ones you like: a cheque now plus a "
        f"reserve for later rounds.\n"
        f"🔁 When portfolio companies raise again, take your pro-rata or get diluted.\n"
        f"⚡ Most deals will fail. One great one can return the whole fund - finding it is the game.\n\n"
        f"📋 Commands: {COMMANDS}",
        style="magenta",
    ))
    console.print(f"[dim]Seed {seed}: replay this fund with --seed {seed}[/dim]")
    input("\nPress Enter to open the fund...")

    while not fund.is_over:
        console.clear()
        console.print(fund_panel(fund))
        if fund.deal_flow:
            console.print(deal_flow_table(fund))
        else:
            console.print("[dim]Investment period over: no new deals, only follow-ons and exits.[/dim]")
        if follow_on_offers(fund):
            console.print(follow_on_table(fund))
        console.print(portfolio_table(fund))

        console.print(f"\n[bold]Actions:[/bold] {COMMANDS}")
        command, _, arg = input("\n> ").strip().lower().partition(" ")
        arg = arg.strip()

        if command == "invest":
            invest(fund, arg)
        elif command == "follow":
            follow(fund, arg)
        elif command == "explain":
            explain(arg)
        elif command == "next":
            if fund.period == MAX_PERIODS:
                input("\nPress Enter to close out the fund's final half-year...")
            events = fund.advance()
            show_turn_results(fund, events)
        elif command == "quit":
            if input("Really quit? (y/N): ").lower().startswith("y"):
                return
            continue
        else:
            console.print("[red]Invalid command.[/red]")
        input("\nPress Enter to continue...")

    console.clear()
    console.print(final_report_panel(fund, seed))
    console.print(concentration_table(fund))
    console.print(j_curve_table(fund))
    console.print(f"\n[dim]Replay this fund with: python venture_main.py --seed {seed}[/dim]")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n\n[yellow]Fund closed early. Thanks for playing![/yellow]")
