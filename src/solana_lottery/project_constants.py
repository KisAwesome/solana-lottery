"""
Project-wide immutable parameters for TokenXYZ lottery.

These values define the public rules of the draw.
Changing them changes eligibility and MUST be publicly announced.
"""

# Token mint (MAINNET)
TOKEN_MINT = "9NrkmoqwF1rBjsfKZvn7ngCy6zqvb8A6A5RfTvR2pump"

# Public exclusion list (committed to repo)
EXCLUDED_WALLETS_FILE = "excluded_wallets.mainnet.txt"

# Pump.fun tokens use 6 decimals
TOKEN_DECIMALS = 6

# Minimum balance to qualify (raw units)
MIN_RAW_BALANCE = 1 * (10**TOKEN_DECIMALS)  # 1 token in raw units (6 decimals)
