"""
Rich-based display for venture fund mode
"""

from typing import List

from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from config.venture_settings import (
    CARRY_RATE, FUND_SIZE, INVESTABLE_CAPITAL, MANAGEMENT_FEE_RATE, MAX_PERIODS,
)
from models.venture_fund import ExitRecord, VentureFund, period_label


def money(value: float) -> str:
    """$1.25M / $350k / -$900 - compact enough for a table cell."""
    sign = "-" if value < 0 else ""
    value = abs(value)
    if value >= 1e6:
        return f"{sign}${value / 1e6:,.2f}M"
    if value >= 1e3:
        return f"{sign}${value / 1e3:,.0f}k"
    return f"{sign}${value:,.0f}"


def _stars(score: int) -> str:
    return "★" * score + "☆" * (5 - score)


def fund_panel(fund: VentureFund) -> Panel:
    phase = "INVESTING" if fund.in_investment_period else "HARVESTING"
    irr = fund.net_irr()
    irr_text = f"{irr:+.1%}" if irr is not None else "n/a"
    text = (
        f"📅 {period_label(fund.period)} (turn {fund.period}/{MAX_PERIODS}) - {phase}\n"
        f"🏦 Fund: {money(FUND_SIZE)} | fees {MANAGEMENT_FEE_RATE:.0%}/yr | carry {CARRY_RATE:.0%}\n"
        f"💵 Investable {money(INVESTABLE_CAPITAL)}: invested {money(fund.invested())}, "
        f"reserved {money(fund.reserved())}, promised {money(fund.pending())}, "
        f"[bold]free {money(fund.available())}[/bold]\n"
        f"💸 Fees paid {money(fund.fees_paid)} | Paid-in {money(fund.paid_in())} | "
        f"NAV {money(fund.nav())} | Distributed {money(fund.distributions)}\n"
        f"📊 Net TVPI {fund.tvpi():.2f}x | DPI {fund.dpi():.2f}x | "
        f"Gross MOIC {fund.gross_moic():.2f}x | Net IRR {irr_text}"
    )
    return Panel(text, title="🚀 Your Venture Fund", style="magenta")


def deal_flow_table(fund: VentureFund) -> Table:
    tbl = Table(title="📥 Deal flow - this period's pitches", show_header=True,
                header_style="bold magenta", show_lines=True)
    tbl.add_column("#", justify="right")
    tbl.add_column("Startup", style="bold")
    tbl.add_column("Stage")
    tbl.add_column("Raising", justify="right")
    tbl.add_column("Post", justify="right")
    tbl.add_column("Team/Mkt/Traction")
    tbl.add_column("Pitch", max_width=48)
    tbl.add_column("You", justify="right")
    for i, deal in enumerate(fund.deal_flow, 1):
        rnd = deal.open_round
        commitment = fund.commitments.get(deal.id)
        mine = (f"[green]{money(commitment.check)}[/green]\n+{money(commitment.reserve)} rsv"
                if commitment else "-")
        signals = " ".join(_stars(deal.signals[k]) for k in ("team", "market", "traction"))
        tbl.add_row(str(i), f"{deal.name}\n[dim]{deal.sector}[/dim]", deal.stage,
                    money(rnd.raise_amount), money(rnd.post_money), signals, deal.pitch, mine)
    return tbl


def follow_on_offers(fund: VentureFund) -> List:
    return [p for p in fund.positions.values() if p.active and p.startup.open_round]


def follow_on_table(fund: VentureFund) -> Table:
    tbl = Table(title="🔁 Pro-rata offers - portfolio companies raising now",
                header_style="bold yellow")
    tbl.add_column("#", justify="right")
    tbl.add_column("Company", style="bold")
    tbl.add_column("Round")
    tbl.add_column("Pre-money", justify="right")
    tbl.add_column("vs last post", justify="right")
    tbl.add_column("You own", justify="right")
    tbl.add_column("Pro-rata", justify="right")
    tbl.add_column("Reserve", justify="right")
    tbl.add_column("Decision", justify="right")
    for i, pos in enumerate(follow_on_offers(fund), 1):
        rnd = pos.startup.open_round
        step = rnd.pre_money / pos.startup.last_post_money()
        step_text = Text(f"{step:.2f}x" + (" DOWN" if step < 1 else ""),
                         style="red" if step < 1 else "green")
        decision = ("[dim]pass (default)[/dim]" if pos.follow_on is None
                    else ("pass" if pos.follow_on == 0 else money(pos.follow_on)))
        tbl.add_row(str(i), pos.startup.name, rnd.round_name, money(rnd.pre_money), step_text,
                    f"{pos.ownership():.2%}", money(pos.pro_rata()), money(pos.reserve), decision)
    return tbl


def portfolio_table(fund: VentureFund) -> Table:
    tbl = Table(title="💼 Portfolio", header_style="bold blue")
    tbl.add_column("Company", style="bold")
    tbl.add_column("Entry")
    tbl.add_column("Status")
    tbl.add_column("Invested", justify="right")
    tbl.add_column("Own", justify="right")
    tbl.add_column("Mark", justify="right")
    tbl.add_column("Returned", justify="right")
    tbl.add_column("Multiple", justify="right")
    if not fund.positions:
        tbl.add_row("No investments yet", "", "", "", "", "", "", "")
        return tbl
    for pos in sorted(fund.positions.values(), key=lambda p: p.proceeds + p.mark(), reverse=True):
        multiple = pos.multiple()
        tbl.add_row(
            pos.startup.name, f"{pos.startup.stage} {period_label(pos.entry_period)}",
            pos.startup.status, money(pos.invested),
            f"{pos.ownership():.2%}" if pos.active else "-", money(pos.mark()),
            money(pos.proceeds),
            Text(f"{multiple:.2f}x", style="green" if multiple >= 1 else "red"),
        )
    return tbl


def waterfall_table(record: ExitRecord) -> Table:
    """Who got what when a company was sold, series by series."""
    result = record.waterfall
    title = (f"🌊 {record.name}: {'asset sale' if record.kind == 'shutdown' else 'exit'} "
             f"for {money(result.exit_value)}")
    tbl = Table(title=title, header_style="bold cyan")
    tbl.add_column("Class")
    tbl.add_column("Invested (1x pref)", justify="right")
    tbl.add_column("Took", justify="right")
    tbl.add_column("Paid", justify="right")
    tbl.add_column("Yours", justify="right")
    yours = {r["series"]: r["payout"] for r in record.fund_rows}
    for row in reversed(result.rows):
        tbl.add_row(row.name, money(row.preference),
                    "converted" if row.converted else "preference",
                    money(row.payout), money(yours[row.name]) if row.name in yours else "-")
    tbl.add_row("Common (founders, staff)", "-", "-", money(result.common_payout), "-")
    return tbl


def j_curve_table(fund: VentureFund) -> Table:
    """The J-curve as a bar per period: LP cumulative net cash, below or above zero."""
    tbl = Table(title="📉📈 J-curve: LPs' cumulative net cash flow", header_style="bold")
    tbl.add_column("Period")
    tbl.add_column("Net cash", justify="right")
    tbl.add_column("", min_width=42)
    points = fund.history
    scale = max(1.0, max(abs(h["cumulative_net_cash_flow"]) for h in points))
    for h in points:
        value = h["cumulative_net_cash_flow"]
        width = int(round(abs(value) / scale * 20))
        if value < 0:
            bar = Text(" " * (20 - width) + "█" * width + "│", style="red")
        else:
            bar = Text(" " * 20 + "│" + "█" * width, style="green")
        tbl.add_row(period_label(h["period"]), money(value), bar)
    return tbl


def final_report_panel(fund: VentureFund, seed: int) -> Panel:
    report = fund.final_report()
    irr = report["net_irr"]
    lines = [
        f"[bold]{report['headline']}[/bold]",
        "",
        f"Deals made: {report['deal_count']} ({report['losers']} returned less than they cost)",
        f"Paid in by LPs: {money(report['paid_in'])} "
        f"({money(report['invested'])} invested + {money(report['fees_paid'])} fees)",
        f"Gross proceeds from exits: {money(report['gross_proceeds'])}",
        f"GP carry: {money(report['carry_paid'])}",
        f"Net to LPs: {money(report['net_to_lps'])}",
        "",
        f"Gross MOIC (the deals): {report['gross_moic']:.2f}x",
        f"Net TVPI (what LPs got): {report['tvpi']:.2f}x",
        f"Net DPI: {report['dpi']:.2f}x",
        f"Net IRR: {irr:+.1%}" if irr is not None else "Net IRR: n/a",
        f"Seed: {seed}",
        "",
        report["rating"],
    ]
    return Panel("\n".join(lines), title="📜 END OF FUND - letter to LPs", style="bold magenta")


def concentration_table(fund: VentureFund) -> Table:
    """Each deal's share of total value: the power law, made visible."""
    report = fund.final_report()
    tbl = Table(title="⚡ Where the returns came from", header_style="bold")
    tbl.add_column("Company", style="bold")
    tbl.add_column("Invested", justify="right")
    tbl.add_column("Returned", justify="right")
    tbl.add_column("Multiple", justify="right")
    tbl.add_column("Share of all value", min_width=30)
    for deal in report["deals"]:
        share = deal["share_of_value"]
        bar = Text("█" * int(round(share * 25)) + f" {share:.0%}",
                   style="bold green" if deal["returned_fund"] else "cyan")
        name = deal["name"] + (" 🏆" if deal["returned_fund"] else "")
        tbl.add_row(name, money(deal["invested"]), money(deal["value"]),
                    f"{deal['multiple']:.1f}x", bar)
    return tbl
