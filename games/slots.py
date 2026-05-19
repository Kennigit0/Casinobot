PAYOUTS = {
    64: (50, "🎰🎰🎰 MEGA JACKPOT! x50!"),
    43: (20, "💎💎💎 Jackpot! x20!"),
    22: (10, "7️⃣7️⃣7️⃣ Big Win! x10!"),
    1:  (5,  "🍒🍒🍒 Win! x5!"),
}

def resolve(value: int, bet: int):
    if value in PAYOUTS:
        multi, label = PAYOUTS[value]
        winnings = bet * multi
        net      = winnings - bet
        msg      = f"🎊 *{label}*\nYou win *{winnings:,}* chips!"
    else:
        net = -bet
        msg = "😞 No match! Better luck next time."
    return msg, net
