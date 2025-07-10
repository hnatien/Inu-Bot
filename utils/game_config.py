"""
Configuration constants for the cluster-based slot game.
This includes grid size, symbols, rarities, and the payout table.
"""

# --- Game Constants ---
GRID_WIDTH, GRID_HEIGHT = 6, 5
MIN_CLUSTER_SIZE = 5

# --- Symbols & Weights (Rarity) ---
# Using emojis for visual representation
SYMBOLS = {
    "low": ["🍒", "🍋", "🍊", "🍉"],
    "mid": ["🔔", "⭐", "🍀"],
    "high": ["💎", "👑"],
}

WEIGHTS = {
    "low": 65,
    "mid": 25,
    "high": 10
}

# --- Pay Table (Multiplier x Bet) ---
# This is a simplified pay table. Payouts are for clusters of size 5 up to 15+.
# The key is (symbol_name, cluster_size)
PAY_TABLE = {
    # Low Tier
    ("🍒", 5): 0.2, ("🍒", 6): 0.4, ("🍒", 7): 0.6, ("🍒", 8): 0.8,
    ("🍒", 9): 1, ("🍒", 10): 1.5, ("🍒", 12): 2, ("🍒", 15): 5,
    ("🍋", 5): 0.2, ("🍋", 6): 0.4, ("🍋", 7): 0.6, ("🍋", 8): 0.8,
    ("🍋", 9): 1, ("🍋", 10): 1.5, ("🍋", 12): 2, ("🍋", 15): 5,
    ("🍊", 5): 0.3, ("🍊", 6): 0.5, ("🍊", 7): 0.7, ("🍊", 8): 0.9,
    ("🍊", 9): 1.2, ("🍊", 10): 1.8, ("🍊", 12): 2.5, ("🍊", 15): 6,
    ("🍉", 5): 0.3, ("🍉", 6): 0.5, ("🍉", 7): 0.7, ("🍉", 8): 0.9,
    ("🍉", 9): 1.2, ("🍉", 10): 1.8, ("🍉", 12): 2.5, ("🍉", 15): 6,
    # Mid Tier
    ("🔔", 5): 0.5, ("🔔", 6): 0.8, ("🔔", 7): 1.2, ("🔔", 8): 1.5,
    ("🔔", 9): 2, ("🔔", 10): 3, ("🔔", 12): 5, ("🔔", 15): 15,
    ("⭐", 5): 0.6, ("⭐", 6): 1,   ("⭐", 7): 1.5, ("⭐", 8): 2,
    ("⭐", 9): 3, ("⭐", 10): 5, ("⭐", 12): 8, ("⭐", 15): 25,
    ("🍀", 5): 0.8, ("🍀", 6): 1.2, ("🍀", 7): 1.8, ("🍀", 8): 2.5,
    ("🍀", 9): 4, ("🍀", 10): 8, ("🍀", 12): 12, ("🍀", 15): 50,
    # High Tier
    ("💎", 5): 1.5, ("💎", 6): 2.5, ("💎", 7): 4,   ("💎", 8): 6,
    ("💎", 9): 10, ("💎", 10): 20, ("💎", 12): 50, ("💎", 15): 250,
    ("👑", 5): 2.5, ("👑", 6): 4,   ("👑", 7): 6,   ("👑", 8): 10,
    ("👑", 9): 20, ("👑", 10): 50, ("👑", 12): 150, ("👑", 15): 1000,
}
# A special payout for filling the screen with the best symbol to reach the max win
PAY_TABLE[("👑", 30)] = 20000

# Reels for the visual spinning animation. They are made longer for a better visual effect.
# The contents are chosen to give a good distribution of symbols on the screen.
BASE_REELS = [
    ["💎", "🍀", "🍒", "⭐", "🍉", "🔔", "🍊", "👑", "🍒", "🍋", "⭐", "🍉", "🍀", "💎", "🔔", "🍒"],
    ["👑", "⭐", "🔔", "🍋", "🍀", "🍒", "💎", "🍉", "🍊", "⭐", "🔔", "🍒", "🍀", "👑", "🍋", "🍉"],
    ["🍉", "👑", "⭐", "🍒", "🍀", "🍋", "🔔", "💎", "🍉", "⭐", "🍒", "👑", "🍀", "🔔", "🍋", "💎"],
    ["🍀", "🍊", "🍒", "⭐", "🔔", "💎", "👑", "🍉", "🍀", "🍒", "⭐", "🔔", "💎", "🍉", "🍊", "👑"],
    ["⭐", "🍋", "👑", "🍉", "🔔", "🍒", "💎", "🍀", "⭐", "🍉", "👑", "🍋", "🔔", "💎", "🍒", "🍀"],
    ["🔔", "💎", "🍉", "🍀", "👑", "⭐", "🍋", "🍒", "🍊", "🔔", "🍉", "🍀", "⭐", "👑", "💎", "🍒"]
]

# Ante reels should have a higher chance of valuable symbols.
# For now, we'll make them a copy of the base reels.
# TODO: Adjust these reels to reflect the ante bet's higher risk/reward.
ANTE_REELS = [list(reel) for reel in BASE_REELS]

# To avoid hard-coding the length, we can extend them programmatically if needed
SPIN_REELS = [reel * 3 for reel in BASE_REELS]

# --- Animation & Effect Constants ---
BIG_WIN_MULTIPLIER = 50 # Multiplier that triggers the "Big Win" animation 