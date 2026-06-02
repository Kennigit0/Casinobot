import random

RED_NUMBERS   = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
BLACK_NUMBERS = {2,4,6,8,10,11,13,15,17,20,22,24,26,28,29,31,33,35}

def spin():
    number = random.randint(0, 36)
    if number == 0:
        color = "🟢"
    elif number in RED_NUMBERS:
        color = "🔴"
    else:
        color = "⚫"
    return number, color

def resolve(bet_type: str, bet_value: str, bet_amount: int):
    """
    bet_type: 'number' | 'color' | 'odd_even' | 'dozen'
    bet_value: '17' | 'red' | 'odd' | '1st'
    Returns: (spin_number, color, winnings, net, result_msg)
    """
    number, color = spin()

    # Calculate payout
    if bet_type == "number":
        target = int(bet_value)
        if number == target:
            winnings = bet_amount * 35
            msg      = f"🎯 Exact hit! x35!"
        else:
            winnings = 0
            msg      = f"❌ It was {number} {color}"

    elif bet_type == "color":
        is_red   = number in RED_NUMBERS
        is_black = number in BLACK_NUMBERS
        if bet_value == "red" and is_red:
            winnings = bet_amount * 2
            msg      = f"✅ Red wins!"
        elif bet_value == "black" and is_black:
            winnings = bet_amount * 2
            msg      = f"✅ Black wins!"
        elif bet_value == "green" and number == 0:
            winnings = bet_amount * 14
            msg      = f"💚 Green 0! x14!"
        else:
            winnings = 0
            msg      = f"❌ It was {number} {color}"

    elif bet_type == "odd_even":
        if number == 0:
            winnings = 0
            msg      = f"❌ Green 0 — house wins"
        elif bet_value == "odd" and number % 2 == 1:
            winnings = bet_amount * 2
            msg      = f"✅ Odd wins!"
        elif bet_value == "even" and number % 2 == 0:
            winnings = bet_amount * 2
            msg      = f"✅ Even wins!"
        else:
            winnings = 0
            msg      = f"❌ It was {number} ({'odd' if number % 2 else 'even'})"

    elif bet_type == "dozen":
        if bet_value == "1st" and 1 <= number <= 12:
            winnings = bet_amount * 3
            msg      = f"✅ 1st dozen (1-12) wins!"
        elif bet_value == "2nd" and 13 <= number <= 24:
            winnings = bet_amount * 3
            msg      = f"✅ 2nd dozen (13-24) wins!"
        elif bet_value == "3rd" and 25 <= number <= 36:
            winnings = bet_amount * 3
            msg      = f"✅ 3rd dozen (25-36) wins!"
        else:
            winnings = 0
            msg      = f"❌ It was {number}"
    else:
        winnings = 0
        msg      = "❌ Invalid bet type"

    net = winnings - bet_amount
    return number, color, winnings, net, msg
