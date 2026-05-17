import random

SYMBOLS  = ["🍒", "🍋", "🍊", "🍇", "💎", "7️⃣", "🃏"]
WEIGHTS  = [30,   25,   20,   15,   5,    3,    2  ]

# Multipliers for 3 of a kind
THREE_PAYOUTS = {
    "🃏": 50,
    "7️⃣": 30,
    "💎": 20,
    "🍇": 10,
    "🍊": 7,
    "🍋": 5,
    "🍒": 3,
}

def spin(bet: int):
    reels = random.choices(SYMBOLS, weights=WEIGHTS, k=3)

    if reels[0] == reels[1] == reels[2]:
        symbol    = reels[0]
        multi     = THREE_PAYOUTS[symbol]
        winnings  = bet * multi
        result    = f"🎊 JACKPOT! Three {symbol}! x{multi}"
    elif reels[0] == reels[1] or reels[1] == reels[2] or reels[0] == reels[2]:
        multi     = 1.5
        winnings  = int(bet * multi)
        result    = "✨ Two of a kind! x1.5"
    else:
        multi     = 0
        winnings  = 0
        result    = "😞 No match. Better luck next time!"

    net = winnings - bet  # positive = profit, negative = loss
    return reels, winnings, net, result


def format_reels(reels):
    return f"[ {reels[0]} | {reels[1]} | {reels[2]} ]"
