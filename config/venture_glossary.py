"""
Short explanations of every venture mechanic, shared by the terminal and browser.

Keep each one to a few sentences and tie it to a number the player can see in the
game: the point is to make the mechanic visible, not to write a textbook.
"""

from config.venture_settings import (
    CARRY_RATE, FUND_LIFE_YEARS, FUND_SIZE, INVESTABLE_CAPITAL, INVESTMENT_PERIOD_YEARS,
    LIFETIME_FEES, MANAGEMENT_FEE_RATE, MAX_COMPANY_PCT, SECONDARY_DISCOUNT,
)

MECHANICS = {
    "fees": (
        "Management fee",
        f"The GP charges {MANAGEMENT_FEE_RATE:.0%} of the ${FUND_SIZE / 1e6:.0f}M a year for "
        f"{FUND_LIFE_YEARS} years: ${LIFETIME_FEES / 1e6:.0f}M that never gets invested. Only "
        f"${INVESTABLE_CAPITAL / 1e6:.0f}M reaches startups, so the deals must make well over "
        f"1x just for LPs to get their money back.",
    ),
    "carry": (
        "Carried interest",
        f"Once LPs have every dollar they paid in back (fees included), the GP keeps "
        f"{CARRY_RATE:.0%} of the profit. Gross MOIC is what the deals made; net TVPI is "
        f"what is left for LPs after fees and carry. The gap between them is the cost of "
        f"hiring a VC.",
    ),
    "power_law": (
        "The power law",
        "Most startups fail or return less than they raised. A few return 10x, 50x, 100x+. "
        "Outcomes are drawn from a fat-tailed (Pareto) distribution, so a fund's result is "
        "usually decided by its one or two best deals - which is why VCs ask of every deal, "
        "'could this one return the fund?'",
    ),
    "reserves": (
        "Reserves",
        "When you back a company you also earmark money for its later rounds. Reserved "
        "money is not available for new deals. Reserve too little and you cannot defend "
        "your winners; too much and you make too few bets to find one.",
    ),
    "pro_rata": (
        "Pro-rata",
        "When a portfolio company raises again you may invest your ownership share of the "
        "new round (ownership x round size). That keeps your stake from shrinking. Doing it "
        "for the companies that are working is how one great deal becomes a fund-returner.",
    ),
    "dilution": (
        "Dilution",
        "Every new round issues new shares, so existing holders own a smaller slice: "
        "ownership x pre-money / post-money. A seed stake typically halves by exit. A down "
        "round (priced below the last round) dilutes harder and marks your stake down.",
    ),
    "liquidation_preference": (
        "Liquidation preference",
        "Every round here is 1x non-participating preferred: on a sale, each series takes "
        "back what it invested OR converts and shares as common - whichever pays more. In a "
        "small sale preferred is paid first and founders can get nothing; in a big one "
        "everyone converts and the preference stops mattering.",
    ),
    "tvpi_dpi": (
        "TVPI and DPI",
        "TVPI (total value to paid-in) counts cash returned plus what is still held at its "
        "last-round mark. DPI (distributions to paid-in) counts only cash. Early on TVPI is "
        "mostly marks; LPs trust DPI.",
    ),
    "j_curve": (
        "The J-curve",
        "Fees and investments go out years before exits come back, so an LP's cumulative "
        "cash position dips deep below zero first and climbs later, if at all. Plotted over "
        "time it looks like a J.",
    ),
    "investment_period": (
        "Investment period",
        f"New deals are only made in the first {INVESTMENT_PERIOD_YEARS} years. After that "
        f"the fund only follows on and waits for exits. At year {FUND_LIFE_YEARS} anything "
        f"still private is sold to a secondary buyer {SECONDARY_DISCOUNT:.0%} below its mark.",
    ),
    "concentration": (
        "Concentration limit",
        f"No more than {MAX_COMPANY_PCT:.0%} of the fund (cheques plus reserves) may go into "
        f"one company, as most LP agreements require.",
    ),
}
