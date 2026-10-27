"""
Venture fund mode configuration and constants

Every number that shapes the fund lives here, so the economics can be changed in
one place and read in one place.
"""

# ------------------- FUND TERMS ------------------- #
FUND_SIZE = 10_000_000              # committed capital from LPs
FUND_LIFE_YEARS = 10
PERIODS_PER_YEAR = 2                # one turn is half a year
MAX_PERIODS = FUND_LIFE_YEARS * PERIODS_PER_YEAR
INVESTMENT_PERIOD_YEARS = 5         # new deals only in years 1-5; after that, harvest
INVESTMENT_PERIODS = INVESTMENT_PERIOD_YEARS * PERIODS_PER_YEAR

MANAGEMENT_FEE_RATE = 0.02          # per year, on committed capital, for the whole life
CARRY_RATE = 0.20                   # GP share of profit once LPs have their capital back

# Fees for the whole life are set aside up front: a $10M fund can only ever invest
# what is left after ten years of 2% fees.
LIFETIME_FEES = FUND_SIZE * MANAGEMENT_FEE_RATE * FUND_LIFE_YEARS
INVESTABLE_CAPITAL = FUND_SIZE - LIFETIME_FEES
FEE_PER_PERIOD = FUND_SIZE * MANAGEMENT_FEE_RATE / PERIODS_PER_YEAR

# ------------------- PORTFOLIO RULES ------------------- #
DEALS_PER_PERIOD = 4
MIN_CHECK = 100_000
# Total cost plus reserves in any one company, as a share of the fund. LP agreements
# cap concentration; without it one lucky all-in bet would be the whole game.
MAX_COMPANY_PCT = 0.20
DEFAULT_RESERVE_RATIO = 1.0         # suggested reserve per $1 of initial check

# When the fund's life ends, anything still private is sold to a secondary buyer
# at a discount to its last-round mark.
SECONDARY_DISCOUNT = 0.30

# ------------------- STARTUP STAGES ------------------- #
# post_money and raise_pct are (low, high) ranges. raise_pct is the round size as a
# share of post-money, which is also the dilution the round causes.
#
# fail_prob: chance the company shuts down and sells its assets for scraps.
# soft_landing_prob: chance it is sold for less than its entry price - the exits
#                    where liquidation preferences decide who gets paid.
# tail_alpha: Pareto exponent of a real exit's multiple. Lower = fatter tail; at 1.0
#             the uncapped mean is infinite, which is roughly what seed investing feels like.
# tail_min: smallest multiple (of a fairly priced entry post-money) of a real exit.
# periods_to_exit / periods_to_fail: how long, in half-years, each fate takes.
STAGES = {
    "Seed": {
        "post_money": (8_000_000, 16_000_000),
        "raise_pct": (0.15, 0.25),
        "fail_prob": 0.45,
        "soft_landing_prob": 0.20,
        "tail_alpha": 1.0,
        "tail_min": 2.0,
        "periods_to_exit": (6, 16),
        "periods_to_fail": (3, 9),
    },
    "Series A": {
        "post_money": (30_000_000, 60_000_000),
        "raise_pct": (0.18, 0.25),
        "fail_prob": 0.30,
        "soft_landing_prob": 0.25,
        "tail_alpha": 1.3,
        "tail_min": 1.6,
        "periods_to_exit": (5, 13),
        "periods_to_fail": (3, 8),
    },
    "Series B": {
        "post_money": (100_000_000, 220_000_000),
        "raise_pct": (0.15, 0.22),
        "fail_prob": 0.20,
        "soft_landing_prob": 0.30,
        "tail_alpha": 1.7,
        "tail_min": 1.3,
        "periods_to_exit": (4, 11),
        "periods_to_fail": (3, 8),
    },
}
STAGE_MIX = {"Seed": 0.6, "Series A": 0.3, "Series B": 0.1}
ROUND_NAMES = ["Seed", "Series A", "Series B", "Series C", "Series D", "Series E",
               "Series F", "Series G"]

PERIODS_BETWEEN_ROUNDS = (3, 4)     # 18-24 months of runway per round
MAX_EXIT_MULTIPLE = 400.0           # cap so one draw cannot be literally infinite
SHUTDOWN_RECOVERY = (0.0, 0.25)     # asset sale proceeds, as a share of preferred raised
SOFT_LANDING_MULTIPLE = (0.1, 1.0)  # sale price over a fair entry post-money
ROUND_VALUATION_NOISE = 0.30        # lognormal sigma on each round's valuation
HYPE_PREMIUM = 0.12                 # how much more strong-looking deals cost, per signal point
COMMON_SHARES_AT_ENTRY = 10_000_000  # founders + option pool before the round we see
