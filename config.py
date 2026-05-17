import os

class Config:
    BOT_TOKEN        = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN")
    STARTING_CHIPS   = 10_000
    DAILY_BONUS      = 5_000
    VIP_DAILY_BONUS  = 25_000
    VIP_PRICE_STARS  = 150        # Telegram Stars for VIP
    MIN_BET          = 100
    MAX_BET          = 500_000
    BJ_JOIN_TIMEOUT  = 30         # seconds to join blackjack table
    DICE_TIMEOUT     = 60         # seconds to accept dice challenge
    ADMIN_IDS        = []         # add your Telegram user_id here
