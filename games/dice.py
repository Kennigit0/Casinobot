import random
import uuid

DICE_EMOJI = ["⚀", "⚁", "⚂", "⚃", "⚄", "⚅"]

def roll():
    value = random.randint(1, 6)
    return value, DICE_EMOJI[value - 1]

def new_challenge(chat_id, challenger_id, challenged_id, bet):
    return str(uuid.uuid4())[:8]

def resolve_dice(challenger_id, challenger_name, challenged_id, challenged_name, bet):
    c1_val, c1_emoji = roll()
    c2_val, c2_emoji = roll()

    lines = [
        f"🎲 *Dice Duel!*\n",
        f"🧑 {challenger_name}: {c1_emoji} *{c1_val}*",
        f"🧑 {challenged_name}: {c2_emoji} *{c2_val}*",
        "",
    ]

    if c1_val > c2_val:
        winner = challenger_id
        loser  = challenged_id
        lines.append(f"🏆 {challenger_name} wins *{bet:,}* chips!")
    elif c2_val > c1_val:
        winner = challenged_id
        loser  = challenger_id
        lines.append(f"🏆 {challenged_name} wins *{bet:,}* chips!")
    else:
        winner = None
        loser  = None
        lines.append("🤝 It's a tie! Bets returned.")

    return "\n".join(lines), winner, loser
