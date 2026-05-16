def resolve(value: int, bet_type: str, bet_amount: int):
    """value = 1-6 from Telegram dice animation"""
    is_even = value % 2 == 0
    is_high  = value >= 4
    lines = []

    if bet_type == "even":
        if is_even:
            winnings = bet_amount * 2
            lines.append(f"✅ Even *{value}*! You win *{winnings:,}* chips!")
        else:
            winnings = 0
            lines.append(f"❌ Odd *{value}*! You lose.")

    elif bet_type == "odd":
        if not is_even:
            winnings = bet_amount * 2
            lines.append(f"✅ Odd *{value}*! You win *{winnings:,}* chips!")
        else:
            winnings = 0
            lines.append(f"❌ Even *{value}*! You lose.")

    elif bet_type == "high":
        if is_high:
            winnings = bet_amount * 2
            lines.append(f"✅ High *{value}* (4-6)! You win *{winnings:,}* chips!")
        else:
            winnings = 0
            lines.append(f"❌ Low *{value}*! You lose.")

    elif bet_type == "low":
        if not is_high:
            winnings = bet_amount * 2
            lines.append(f"✅ Low *{value}* (1-3)! You win *{winnings:,}* chips!")
        else:
            winnings = 0
            lines.append(f"❌ High *{value}*! You lose.")

    elif bet_type.isdigit():
        target = int(bet_type)
        if 1 <= target <= 6:
            if value == target:
                winnings = bet_amount * 6
                lines.append(f"🎯 Exact *{value}*! x6! You win *{winnings:,}* chips!")
            else:
                winnings = 0
                lines.append(f"❌ Got *{value}*, not {target}. You lose.")
        else:
            return None, None
    else:
        return None, None

    net = winnings - bet_amount
    return "\n".join(lines), net
