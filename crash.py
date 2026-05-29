"""crash.py — Crash Game
- Players place bets before round starts
- Multiplier climbs from 1.00x
- Can crash anytime — cash out before it crashes!
- Group game: everyone bets together, same multiplier
- Round every 30 seconds
"""
import random, threading, time
from telebot import types
import database as db

_bot        = None
ROUND_WAIT  = 20   # seconds to accept bets before round starts
MIN_BET     = 100
MAX_BET     = 1_000_000

def fmt(n): return f"{n:,}"

# ── Game state ────────────────────────────────────────────────────────
games = {}   # chat_id -> game state

def new_game_state():
    return {
        "phase":    "betting",   # betting | running | crashed
        "bets":     {},          # uid -> {"amount": int, "cashed_out": False, "multiplier": None}
        "multiplier": 1.00,
        "crash_at": gen_crash_point(),
        "msg_id":   None,
    }

def gen_crash_point():
    """Weighted crash point — mostly low, occasionally very high"""
    r = random.random()
    if r < 0.40: return round(random.uniform(1.00, 1.50), 2)   # 40% crash early
    if r < 0.70: return round(random.uniform(1.50, 3.00), 2)   # 30% medium
    if r < 0.90: return round(random.uniform(3.00, 7.00), 2)   # 20% high
    if r < 0.97: return round(random.uniform(7.00, 20.0), 2)   # 7% very high
    return round(random.uniform(20.0, 100.0), 2)                # 3% moon 🚀

# ── Board render ──────────────────────────────────────────────────────
def render_board(chat_id):
    game = games.get(chat_id)
    if not game: return "No active game.", None

    phase = game["phase"]
    bets  = game["bets"]
    mult  = game["multiplier"]

    if phase == "betting":
        lines = ["🚀 *Crash — Place Your Bets!*\n"]
        if bets:
            for uid, b in bets.items():
                p = db.get_player(uid)
                name = p["first_name"] if p else "?"
                lines.append(f"• *{name}* — {fmt(b['amount'])} chips")
        else:
            lines.append("_No bets yet..._")
        lines.append(f"\n⏳ Round starts in a moment!")
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("Bet 1K",   callback_data="crash_bet_1000"),
            types.InlineKeyboardButton("Bet 5K",   callback_data="crash_bet_5000"),
            types.InlineKeyboardButton("Bet 10K",  callback_data="crash_bet_10000"),
        )
        markup.row(
            types.InlineKeyboardButton("Bet 50K",  callback_data="crash_bet_50000"),
            types.InlineKeyboardButton("Bet 100K", callback_data="crash_bet_100000"),
            types.InlineKeyboardButton("Custom",   callback_data="crash_bet_custom"),
        )
        return "\n".join(lines), markup

    elif phase == "running":
        bar_len   = 12
        fill      = min(int((mult - 1) / (game["crash_at"] - 1 + 0.001) * bar_len), bar_len)
        bar       = "🟩" * fill + "⬜" * (bar_len - fill)
        lines = [f"🚀 *CRASH — IN FLIGHT!*\n",
                 f"📈 Multiplier: *{mult:.2f}x*",
                 f"{bar}\n"]
        cashed = []
        waiting = []
        for uid, b in bets.items():
            p    = db.get_player(uid)
            name = p["first_name"] if p else "?"
            if b["cashed_out"]:
                cashed.append(f"✅ *{name}* cashed @ {b['multiplier']:.2f}x (+{fmt(int(b['amount'] * b['multiplier'] - b['amount']))})")
            else:
                potential = int(b["amount"] * mult)
                waiting.append(f"⏳ *{name}* — {fmt(b['amount'])} → *{fmt(potential)}*")
        if cashed:  lines += cashed
        if waiting: lines += waiting
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("💰 CASH OUT!", callback_data="crash_cashout"))
        return "\n".join(lines), markup

    elif phase == "crashed":
        lines = [f"💥 *CRASHED at {mult:.2f}x!*\n"]
        for uid, b in bets.items():
            p    = db.get_player(uid)
            name = p["first_name"] if p else "?"
            if b["cashed_out"]:
                profit = int(b["amount"] * b["multiplier"]) - b["amount"]
                lines.append(f"✅ *{name}* — cashed @ {b['multiplier']:.2f}x (+{fmt(profit)})")
            else:
                lines.append(f"💀 *{name}* — lost {fmt(b['amount'])} chips")
        lines.append(f"\n🎮 New round starting in {ROUND_WAIT}s...")
        return "\n".join(lines), None

# ── Round loop ────────────────────────────────────────────────────────
def run_round(chat_id):
    game = games[chat_id]

    # Betting phase
    game["phase"] = "betting"
    text, markup  = render_board(chat_id)
    try:
        msg = _bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
        game["msg_id"] = msg.message_id
    except Exception as e:
        print(f"Crash send error: {e}"); return

    time.sleep(ROUND_WAIT)

    # If nobody bet, schedule next round
    if not game["bets"]:
        try: _bot.edit_message_text("🚀 *Crash* — No bets, skipping round.\n\n`/crash` to start a new round.",
            chat_id, game["msg_id"], parse_mode="Markdown")
        except: pass
        games.pop(chat_id, None)
        return

    # Deduct bets from wallets
    for uid, b in game["bets"].items():
        db.update_chips(uid, -b["amount"])

    # Running phase
    game["phase"]     = "running"
    game["multiplier"] = 1.00
    crash_at           = game["crash_at"]

    step = 0.05
    while game["multiplier"] < crash_at:
        time.sleep(0.5)
        # Speed increases as multiplier grows
        if game["multiplier"] < 2:   step = 0.05
        elif game["multiplier"] < 5: step = 0.10
        else:                        step = 0.20
        game["multiplier"] = round(game["multiplier"] + step, 2)

        # Update board every 2 steps
        if round(game["multiplier"] / step) % 2 == 0:
            text, markup = render_board(chat_id)
            try: _bot.edit_message_text(text, chat_id, game["msg_id"],
                    reply_markup=markup, parse_mode="Markdown")
            except: pass

        # Check if all cashed out early
        if all(b["cashed_out"] for b in game["bets"].values()):
            break

    # Crash!
    game["multiplier"] = crash_at
    game["phase"]      = "crashed"

    # Pay out anyone who didn't cash out — they lose
    for uid, b in game["bets"].items():
        if b["cashed_out"]:
            winnings = int(b["amount"] * b["multiplier"])
            db.update_chips(uid, winnings)
            db.add_win(uid)

    text, _ = render_board(chat_id)
    try:
        _bot.edit_message_text(text, chat_id, game["msg_id"], parse_mode="Markdown")
    except: pass

    # Schedule next round
    games.pop(chat_id, None)

# ── Commands ──────────────────────────────────────────────────────────
def cmd_crash(message):
    p = db.get_player(message.from_user.id)
    if not p: _bot.reply_to(message, "❗ Register first with /start"); return

    chat_id = message.chat.id

    if chat_id in games:
        game  = games[chat_id]
        phase = game["phase"]
        if phase == "betting":
            _bot.reply_to(message, "🚀 A round is already in betting phase — place your bet above!")
        else:
            _bot.reply_to(message, f"🚀 Round in progress at *{game['multiplier']:.2f}x* — wait for next round!")
        return

    games[chat_id] = new_game_state()
    t = threading.Thread(target=run_round, args=(chat_id,), daemon=True)
    t.start()

def cb_crash(call):
    uid     = call.from_user.id
    chat_id = call.message.chat.id
    p       = db.get_player(uid)
    if not p: _bot.answer_callback_query(call.id, "Register first! /start"); return

    game = games.get(chat_id)
    if not game:
        _bot.answer_callback_query(call.id, "No active game! Use /crash"); return

    data = call.data

    # Cash out
    if data == "crash_cashout":
        if game["phase"] != "running":
            _bot.answer_callback_query(call.id, "Round not in progress!"); return
        if uid not in game["bets"]:
            _bot.answer_callback_query(call.id, "You didn't bet this round!"); return
        b = game["bets"][uid]
        if b["cashed_out"]:
            _bot.answer_callback_query(call.id, f"Already cashed out @ {b['multiplier']:.2f}x!"); return
        b["cashed_out"] = True
        b["multiplier"] = game["multiplier"]
        profit = int(b["amount"] * b["multiplier"]) - b["amount"]
        _bot.answer_callback_query(call.id,
            f"✅ Cashed out @ {game['multiplier']:.2f}x! +{fmt(profit)} chips", show_alert=True)
        return

    # Place bet
    if game["phase"] != "betting":
        _bot.answer_callback_query(call.id, "Betting phase is over!"); return
    if uid in game["bets"]:
        _bot.answer_callback_query(call.id, "You already placed a bet this round!"); return

    if data == "crash_bet_custom":
        _bot.answer_callback_query(call.id)
        msg = _bot.send_message(chat_id,
            f"💬 *{call.from_user.first_name}*, reply with your bet amount:")
        _bot.register_next_step_handler(msg, lambda m: _handle_custom_bet(m, uid, chat_id))
        return

    amount = int(data.split("_")[-1])
    _place_bet(call, uid, chat_id, p, amount)

def _handle_custom_bet(message, uid, chat_id):
    p = db.get_player(uid)
    if not p: return
    try: amount = int(message.text.replace(",", ""))
    except: _bot.reply_to(message, "❌ Invalid amount."); return
    _place_bet(message, uid, chat_id, p, amount, is_msg=True)

def _place_bet(call_or_msg, uid, chat_id, p, amount, is_msg=False):
    game = games.get(chat_id)
    if not game or game["phase"] != "betting":
        if is_msg: _bot.reply_to(call_or_msg, "❌ Betting phase is over!")
        else: _bot.answer_callback_query(call_or_msg.id, "Betting phase is over!")
        return

    if amount < MIN_BET:
        msg = f"Minimum bet is {fmt(MIN_BET)} chips"
        if is_msg: _bot.reply_to(call_or_msg, f"❌ {msg}")
        else: _bot.answer_callback_query(call_or_msg.id, msg, show_alert=True)
        return
    if amount > MAX_BET:
        msg = f"Maximum bet is {fmt(MAX_BET)} chips"
        if is_msg: _bot.reply_to(call_or_msg, f"❌ {msg}")
        else: _bot.answer_callback_query(call_or_msg.id, msg, show_alert=True)
        return
    if p["chips"] < amount:
        msg = f"Not enough chips! Have: {fmt(p['chips'])}"
        if is_msg: _bot.reply_to(call_or_msg, f"❌ {msg}")
        else: _bot.answer_callback_query(call_or_msg.id, msg, show_alert=True)
        return

    game["bets"][uid] = {"amount": amount, "cashed_out": False, "multiplier": None}

    if not is_msg:
        _bot.answer_callback_query(call_or_msg.id, f"✅ Bet placed: {fmt(amount)} chips!")

    # Refresh board
    text, markup = render_board(chat_id)
    try:
        _bot.edit_message_text(text, chat_id, game["msg_id"],
            reply_markup=markup, parse_mode="Markdown")
    except: pass

# ── Register ──────────────────────────────────────────────────────────
def register_crash(bot_instance):
    global _bot
    _bot = bot_instance
    bot_instance.register_message_handler(cmd_crash, commands=["crash"])
    bot_instance.register_callback_query_handler(
        cb_crash, func=lambda c: c.data.startswith("crash_"))
    print("✅ Crash loaded")
