"""
Game configuration and constants
"""

# ------------------- CONFIG ------------------- #
INITIAL_CASH = 10_000
NUM_COMPANIES = 10
MAX_TURNS = 50  # Increased for more complex gameplay
SECTORS = ["Tech", "Energy", "Finance", "Retail", "Healthcare"]
TRANSACTION_FEE = 0.01
DIVIDEND_YIELD = 0.002

# ------------- SHORT SELLING CONFIG -------------- #
SHORT_MARGIN_REQUIREMENT = 0.5  # 50% margin required (can short up to 2x margin)
SHORT_BORROW_RATE = 0.001  # 0.1% per turn borrowing cost
MARGIN_CALL_THRESHOLD = 0.25  # Margin call if equity drops below 25% of position
SHORT_LOCATE_FEE = 0.005  # 0.5% fee to locate/borrow shares

# ------------- MARKET IMPACT / SLIPPAGE -------------- #
# Large orders move the price against you
SLIPPAGE_FACTOR = 0.02  # 2% price impact per 100% of avg volume traded
BASE_DAILY_VOLUME = 10000  # Assumed average daily volume per stock
MIN_SLIPPAGE = 0.0  # Minimum slippage (small orders)
MAX_SLIPPAGE = 0.05  # Maximum slippage cap (5%)

# ---------- ADVANCED DIFFICULTY SETTINGS ---------- #
BASE_FALSE_SIGNAL_CHANCE = 0.25
BASE_ALGO_INTENSITY = 0.5
BASE_CRISIS_PROBABILITY = 0.02
INFORMATION_NOISE = 0.3
SMART_MONEY_ADVANTAGE = 3  # Turns ahead they trade

# ------------- SECTOR CORRELATIONS -------------- #
SECTOR_CORRELATIONS = {
    ("Tech", "Finance"): 0.35,
    ("Energy", "Finance"): 0.25,
    ("Tech", "Retail"): 0.15,
    ("Healthcare", "Finance"): 0.20,
    ("Energy", "Retail"): -0.10,  # Negative correlation
} 