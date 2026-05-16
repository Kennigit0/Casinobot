"""
🎰 Telegram Casino Bot
━━━━━━━━━━━━━━━━━━━━━━
Games   : Slots, Blackjack (multiplayer), Dice Duel, Roulette
Economy : Virtual chips, Daily bonus, VIP membership
Deploy  : Railway (polling) or Vercel (webhook)
"""

import os
import json
import time
import threading
import telebot
from telebot import types

import database as db
import features
from config import Config
from games import slots, blackjack, dice, roulette

# ── Bot init ─────────────────────────────────────────────────────────
bot = telebot.TeleBot(Config.BOT_TOKEN, parse_mode="Markdown")

# pending_bj_games: { game_id: (timer_thread, game_data) }
pending_bj    = {}
pending_dice  = {}

# ── Helpers ───────────────────────────────────────────────────────────

def name(user):
    return user.first_name or user.username or "Player"

def check_registered(message):
    """Returns player dict or None (and sends error)."""
    p = db.get_player(message.from_user.id)
    if not p:
        bot.reply_to(message, "❗ You're not registered. Send /start to join!")
        return None
    return p

def fmt(n):
    return f"{n:,}"

def is_group(message):
    return message.chat.type in ("group", "supergroup")

# ── /start ────────────────────────────────────────────────────────────

@bot.message_handler(commands=["start"])
def cmd_start(message):
    uid = message.from_user.id
    existing = db.get_player(uid)
    if existing:
        bot.reply_to(message,
            f"🎰 Welcome back, *{name(message.from_user)}*!\n"
            f"💰 Balance: *{fmt(existing['chips'])}* chips\n\n"
            "Type /help to see all commands.")
        return

    # Age gate
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ Yes, I am 18+", callback_data=f"age_yes_{uid}"),
        types.InlineKeyboardButton("❌ No", callback_data=f"age_no_{uid}")
    )
    bot.reply_to(message,
        "🎰 *Welcome to Casino Bot!*\n\n"
        "⚠️ This bot is for *18+ users only*.\n"
        "All games use *virtual chips* — no real money involved.\n\n"
        "Are you 18 years or older?",
        reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("age_"))
def cb_age(call):
    parts = call.data.split("_")
    answer = parts[1]
    uid    = int(parts[2])

    if call.from_user.id != uid:
        bot.answer_callback_query(call.id, "This isn't for you!")
        return

    if answer == "no":
        bot.edit_message_text("❌ Sorry, you must be 18+ to use this bot.",
                              call.message.chat.id, call.message.message_id)
        return

    db.register_player(uid, call.from_user.username, call.from_user.first_name)
    bot.edit_message_text(
        f"✅ *Welcome, {name(call.from_user)}!*\n\n"
        f"🎁 You received *{fmt(Config.STARTING_CHIPS)}* starting chips!\n\n"
        "🎮 *Games:*\n"
        "• /slots — Spin the reels\n"
        "• /bj — Blackjack (group multiplayer)\n"
        "• /dice — Dice duel vs another player\n"
        "• /roulette — Bet on the wheel\n\n"
        "💡 Type /help for all commands.",
        call.message.chat.id, call.message.message_id)

# ── /help ─────────────────────────────────────────────────────────────

@bot.message_handler(commands=["help"])
def cmd_help(message):
    bot.reply_to(message,
        "🎰 *Casino Bot — All Commands*\n\n"

        "👤 *Account*\n"
        "/start — Register with age verification\n"
        "/profile — View your full profile\n"
        "/balance — Your wallet balance\n"
        "/daily — Claim daily bonus chips\n"
        "/leaderboard — Top 10 richest players\n"
        "/vip — VIP membership info\n"
        "/terms — Terms of service\n\n"

        "🏦 *Bank*\n"
        "/bank — View wallet + bank balance\n"
        "/deposit `[amount]` — Save chips safely\n"
        "/withdraw `[amount]` — Take chips out\n"
        "/interest — Claim 3% daily interest\n\n"

        "💼 *Jobs*\n"
        "/work — Do a job, earn chips (1hr cooldown)\n"
        "/crime — Risky crime, big reward (2hr cooldown)\n"
        "/heist `[bet]` — Group heist in chat\n\n"

        "🔫 *Street*\n"
        "/rob — Reply to someone to rob them\n"
        "/gift `[amount]` — Reply to someone to gift chips\n\n"

        "💍 *Social*\n"
        "/marry — Reply to someone to propose\n"
        "/divorce — End your marriage\n\n"

        "🎮 *Games*\n"
        "/slots `[bet]` — 🎰 Spin the slot machine\n"
        "/dice `[type] [bet]` — 🎲 Bet on dice roll\n"
        "/bj `[bet]` — 🃏 Multiplayer blackjack\n"
        "/roulette `[type] [value] [bet]` — 🎡 Roulette\n\n"

        "*🎲 Dice types:*\n"
        "`/dice even 1000` `/dice odd 1000`\n"
        "`/dice high 1000` `/dice low 1000`\n"
        "`/dice 6 1000` — exact number (x6)\n\n"

        "*🎡 Roulette types:*\n"
        "`/roulette color red 1000`\n"
        "`/roulette color black 1000`\n"
        "`/roulette color green 1000` *(x14)*\n"
        "`/roulette number 17 1000` *(x35)*\n"
        "`/roulette odd_even odd 1000`\n"
        "`/roulette dozen 1st 1000`\n\n"

        f"Min bet: *{fmt(Config.MIN_BET)}* | Max bet: *{fmt(Config.MAX_BET)}*")

# ── /balance ──────────────────────────────────────────────────────────

@bot.message_handler(commands=["balance", "bal", "chips"])
def cmd_balance(message):
    p = check_registered(message)
    if not p:
        return
    vip_tag = " 👑 VIP" if p["vip"] else ""
    bot.reply_to(message,
        f"💰 *{p['first_name']}{vip_tag}*\n"
        f"Chips: *{fmt(p['chips'])}*\n\n"
        "Claim your daily bonus with /daily")

# ── /daily ────────────────────────────────────────────────────────────

@bot.message_handler(commands=["daily", "claim"])
def cmd_daily(message):
    p = check_registered(message)
    if not p:
        return
    ok, bonus, msg = db.claim_daily(message.from_user.id, p["vip"])
    if ok:
        new_bal = db.get_player(message.from_user.id)["chips"]
        vip_note = " *(VIP bonus!)*" if p["vip"] else ""
        bot.reply_to(message,
            f"🎁 Daily bonus claimed{vip_note}!\n"
            f"+*{fmt(bonus)}* chips\n"
            f"💰 New balance: *{fmt(new_bal)}*")
    else:
        bot.reply_to(message, f"⏰ {msg}")

# ── /leaderboard ──────────────────────────────────────────────────────

@bot.message_handler(commands=["leaderboard", "top", "lb"])
def cmd_leaderboard(message):
    rows = db.get_leaderboard(10)
    lines = ["🏆 *Leaderboard — Top 10*\n"]
    medals = ["🥇", "🥈", "🥉"]
    for i, r in enumerate(rows):
        m     = medals[i] if i < 3 else f"{i+1}."
        vip   = " 👑" if r["vip"] else ""
        lines.append(f"{m} *{r['first_name']}*{vip} — {fmt(r['chips'])} chips")
    bot.reply_to(message, "\n".join(lines))

# ── /vip ─────────────────────────────────────────────────────────────

@bot.message_handler(commands=["vip"])
def cmd_vip(message):
    p = check_registered(message)
    if not p:
        return
    if p["vip"]:
        bot.reply_to(message,
            "👑 *You are VIP!*\n\n"
            f"✅ Daily bonus: *{fmt(Config.VIP_DAILY_BONUS)}* chips\n"
            "✅ VIP badge on leaderboard\n"
            "✅ Priority support")
        return

    bot.reply_to(message,
        "👑 *VIP Membership*\n\n"
        f"Daily bonus: *{fmt(Config.VIP_DAILY_BONUS)}* chips (vs {fmt(Config.DAILY_BONUS)})\n"
        "VIP badge on leaderboard 🏆\n"
        "Exclusive VIP title\n\n"
        f"Price: *{Config.VIP_PRICE_STARS} Telegram Stars*\n\n"
        "Contact the admin to purchase VIP.")

# ── /terms ────────────────────────────────────────────────────────────

@bot.message_handler(commands=["terms"])
def cmd_terms(message):
    bot.reply_to(message,
        "📋 *Terms of Service*\n\n"
        "1. All chips are *VIRTUAL* with zero real-world value.\n"
        "2. You must be *18 years or older* to use this bot.\n"
        "3. Buying, selling, or trading chips for real money is *strictly prohibited*.\n"
        "4. Chips cannot be withdrawn or converted to any currency.\n"
        "5. The developer is *not responsible* for any external transactions.\n"
        "6. Violations result in a permanent ban.\n"
        "7. This bot is for *entertainment only*.\n\n"
        "_By using this bot you agree to these terms._")

# ── /slots ────────────────────────────────────────────────────────────

@bot.message_handler(commands=["slots", "slot"])
def cmd_slots(message):
    import time
    p = check_registered(message)
    if not p:
        return
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, f"🎰 Usage: `/slots [bet]`\nExample: `/slots 1000`")
        return
    try:
        bet = int(args[1].replace(",", ""))
    except ValueError:
        bot.reply_to(message, "❌ Invalid bet amount.")
        return
    if bet < Config.MIN_BET or bet > Config.MAX_BET:
        bot.reply_to(message, f"❌ Bet must be *{fmt(Config.MIN_BET)}* — *{fmt(Config.MAX_BET)}*.")
        return
    if p["chips"] < bet:
        bot.reply_to(message, f"❌ Not enough chips! You have *{fmt(p['chips'])}*.")
        return
    slot_msg = bot.send_dice(message.chat.id, emoji="🎰")
    value = slot_msg.dice.value
    time.sleep(3)
    result_msg, net = slots.resolve(value, bet)
    db.update_chips(message.from_user.id, net)
    new_bal = db.get_player(message.from_user.id)["chips"]
    sign = "+" if net >= 0 else ""
    bot.reply_to(slot_msg,
        f"{result_msg}\n"
        f"Bet: *{fmt(bet)}* | {sign}*{fmt(net)}* chips\n"
        f"💰 Balance: *{fmt(new_bal)}*")

# ── /roulette ─────────────────────────────────────────────────────────

@bot.message_handler(commands=["roulette", "rl"])
def cmd_roulette(message):
    p = check_registered(message)
    if not p:
        return

    args = message.text.split()
    if len(args) < 4:
        bot.reply_to(message,
            "Usage: `/roulette [type] [value] [bet]`\n\n"
            "Examples:\n"
            "`/roulette color red 500`\n"
            "`/roulette color black 500`\n"
            "`/roulette color green 500` *(x14)*\n"
            "`/roulette number 17 500` *(x35)*\n"
            "`/roulette odd_even odd 500`\n"
            "`/roulette dozen 1st 500`")
        return

    bet_type  = args[1].lower()
    bet_value = args[2].lower()

    try:
        bet = int(args[3].replace(",", ""))
    except ValueError:
        bot.reply_to(message, "❌ Invalid bet amount.")
        return

    if bet < Config.MIN_BET or bet > Config.MAX_BET:
        bot.reply_to(message, f"❌ Bet must be *{fmt(Config.MIN_BET)}* — *{fmt(Config.MAX_BET)}*.")
        return

    if p["chips"] < bet:
        bot.reply_to(message, f"❌ Not enough chips! You have *{fmt(p['chips'])}*.")
        return

    valid_types = {"color", "number", "odd_even", "dozen"}
    if bet_type not in valid_types:
        bot.reply_to(message, f"❌ Invalid type. Use: color, number, odd_even, dozen")
        return

    if bet_type == "number":
        try:
            n = int(bet_value)
            if n < 0 or n > 36:
                raise ValueError
        except ValueError:
            bot.reply_to(message, "❌ Number must be 0–36.")
            return

    number, color, winnings, net, result_msg = roulette.resolve(bet_type, bet_value, bet)
    db.update_chips(message.from_user.id, net)
    new_bal = db.get_player(message.from_user.id)["chips"]

    sign = "+" if net >= 0 else ""
    bot.reply_to(message,
        f"🎡 *Roulette*\n\n"
        f"🔵 Ball lands on: *{number}* {color}\n\n"
        f"{result_msg}\n"
        f"Bet: *{fmt(bet)}* | {sign}*{fmt(net)}* chips\n"
        f"💰 Balance: *{fmt(new_bal)}*")

# ── /bj (Blackjack — group multiplayer) ──────────────────────────────

@bot.message_handler(commands=["bj", "blackjack"])
def cmd_bj(message):
    if features.check_bot_bj(message):
        return
    p = check_registered(message)
    if not p:
        return

    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "Usage: `/bj [bet]`\nExample: `/bj 1000`")
        return

    try:
        bet = int(args[1].replace(",", ""))
    except ValueError:
        bot.reply_to(message, "❌ Invalid bet.")
        return

    if bet < Config.MIN_BET or bet > Config.MAX_BET:
        bot.reply_to(message, f"❌ Bet must be *{fmt(Config.MIN_BET)}* — *{fmt(Config.MAX_BET)}*.")
        return

    if p["chips"] < bet:
        bot.reply_to(message, f"❌ Not enough chips! You have *{fmt(p['chips'])}*.")
        return

    uid  = message.from_user.id
    game = blackjack.new_game(uid, bet, message.chat.id)
    gid  = game["game_id"]

    # Reserve host chips
    db.update_chips(uid, -bet)
    blackjack.add_player(game, uid, name(message.from_user))
    game["players"][0]["chips_reserved"] = True

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🃏 Join Table", callback_data=f"bj_join_{gid}"),
        types.InlineKeyboardButton("▶️ Start Now",  callback_data=f"bj_start_{gid}")
    )

    sent = bot.reply_to(message,
        f"🃏 *Blackjack Table* #{gid}\n"
        f"Bet: *{fmt(bet)}* chips\n"
        f"Players: 1/6\n"
        f"1. *{name(message.from_user)}*\n\n"
        f"⏳ Joining open for *{Config.BJ_JOIN_TIMEOUT}s*...",
        reply_markup=markup)

    game["message_id"] = sent.message_id
    pending_bj[gid]    = game
    db.save_bj_game(gid, message.chat.id, sent.message_id, uid, bet, game)

    # Auto-start timer
    def auto_start():
        time.sleep(Config.BJ_JOIN_TIMEOUT)
        if gid in pending_bj:
            start_bj_game(gid, message.chat.id, sent.message_id)

    t = threading.Thread(target=auto_start, daemon=True)
    t.start()

@bot.callback_query_handler(func=lambda c: c.data.startswith("bj_join_"))
def cb_bj_join(call):
    gid = call.data.split("_")[2]
    uid = call.from_user.id
    p   = db.get_player(uid)

    if not p:
        bot.answer_callback_query(call.id, "Register first! Send /start")
        return

    game = pending_bj.get(gid)
    if not game:
        bot.answer_callback_query(call.id, "Table not found or already started.")
        return

    if any(pl["uid"] == uid for pl in game["players"]):
        bot.answer_callback_query(call.id, "You're already at this table!")
        return

    bet = game["bet"]
    if p["chips"] < bet:
        bot.answer_callback_query(call.id, f"Not enough chips! Need {fmt(bet)}.")
        return

    db.update_chips(uid, -bet)
    added = blackjack.add_player(game, uid, name(call.from_user))
    if not added:
        db.update_chips(uid, bet)
        bot.answer_callback_query(call.id, "Table is full!")
        return

    db.save_bj_game(gid, game["chat_id"], game["message_id"], game["host_id"], bet, game)

    player_list = "\n".join(f"{i+1}. *{pl['name']}*" for i, pl in enumerate(game["players"]))
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🃏 Join Table", callback_data=f"bj_join_{gid}"),
        types.InlineKeyboardButton("▶️ Start Now",  callback_data=f"bj_start_{gid}")
    )
    try:
        bot.edit_message_text(
            f"🃏 *Blackjack Table* #{gid}\n"
            f"Bet: *{fmt(bet)}* chips\n"
            f"Players: {len(game['players'])}/6\n"
            f"{player_list}\n\n"
            f"⏳ Joining open...",
            call.message.chat.id, call.message.message_id,
            reply_markup=markup, parse_mode="Markdown")
    except Exception:
        pass

    bot.answer_callback_query(call.id, f"✅ Joined! Bet {fmt(bet)} chips reserved.")

@bot.callback_query_handler(func=lambda c: c.data.startswith("bj_start_"))
def cb_bj_start(call):
    gid  = call.data.split("_")[2]
    game = pending_bj.get(gid)
    if not game:
        bot.answer_callback_query(call.id, "Game not found.")
        return
    if call.from_user.id != game["host_id"]:
        bot.answer_callback_query(call.id, "Only the host can start early.")
        return
    bot.answer_callback_query(call.id, "Starting game!")
    start_bj_game(gid, call.message.chat.id, call.message.message_id)

def start_bj_game(gid, chat_id, message_id):
    game = pending_bj.pop(gid, None)
    if not game:
        return
    if len(game["players"]) == 0:
        return

    blackjack.deal_cards(game)
    db.save_bj_game(gid, chat_id, message_id, game["host_id"], game["bet"], game)
    send_bj_board(gid, chat_id, message_id, game)

def send_bj_board(gid, chat_id, message_id, game):
    board  = blackjack.game_board(game, hide_dealer=game["state"] != "done")
    cp     = blackjack.current_player(game)

    if game["state"] == "done":
        results  = blackjack.resolve(game)
        lines    = [board, "\n\n🏁 *Results:*"]
        for r in results:
            db.update_chips(r["uid"], r["chips"])
            sign = "+" if r["chips"] >= 0 else ""
            lines.append(f"• *{r['name']}*: {r['result']} ({sign}{fmt(r['chips'])})")
        text   = "\n".join(lines)
        markup = None
        db.delete_bj_game(gid)
    elif cp:
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("👊 Hit",  callback_data=f"bj_hit_{gid}_{cp['uid']}"),
            types.InlineKeyboardButton("✋ Stand", callback_data=f"bj_stand_{gid}_{cp['uid']}")
        )
        text = board + f"\n\n👉 *{cp['name']}* — Hit or Stand?"
    else:
        text   = board
        markup = None

    try:
        bot.edit_message_text(text, chat_id, message_id,
                              reply_markup=markup, parse_mode="Markdown")
    except Exception:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c: c.data.startswith("bj_hit_") or c.data.startswith("bj_stand_"))
def cb_bj_action(call):
    parts  = call.data.split("_")
    action = parts[1]          # hit or stand
    gid    = parts[2]
    target = int(parts[3])

    if call.from_user.id != target:
        bot.answer_callback_query(call.id, "It's not your turn!")
        return

    game = db.get_bj_game(gid)
    if not game:
        bot.answer_callback_query(call.id, "Game not found.")
        return
    game = game["data"]

    if action == "hit":
        blackjack.hit(game, target)
        bot.answer_callback_query(call.id, "🃏 Hit!")
    else:
        blackjack.stand(game, target)
        bot.answer_callback_query(call.id, "✋ Stand!")

    db.update_bj_game(gid, game)
    send_bj_board(gid, call.message.chat.id, call.message.message_id, game)

# ── /dice ─────────────────────────────────────────────────────────────

@bot.message_handler(commands=["dice"])
def cmd_dice(message):
    import time
    if features.check_bot_dice(message):
        return
    p = check_registered(message)
    if not p:
        return
    args = message.text.split()
    if len(args) < 3:
        bot.reply_to(message,
            "🎲 *Dice Game*\n\n"
            "Usage: `/dice [type] [bet]`\n\n"
            "*2x payout:*\n"
            "`/dice even 1000`\n"
            "`/dice odd 1000`\n"
            "`/dice high 1000` — rolls 4,5,6\n"
            "`/dice low 1000` — rolls 1,2,3\n\n"
            "*6x payout:*\n"
            "`/dice 6 1000` — exact number 1-6")
        return
    bet_type = args[1].lower()
    try:
        bet = int(args[2].replace(",", ""))
    except ValueError:
        bot.reply_to(message, "❌ Invalid bet amount.")
        return
    if bet < Config.MIN_BET or bet > Config.MAX_BET:
        bot.reply_to(message, f"❌ Bet must be *{fmt(Config.MIN_BET)}* — *{fmt(Config.MAX_BET)}*.")
        return
    if p["chips"] < bet:
        bot.reply_to(message, f"❌ Not enough chips! You have *{fmt(p['chips'])}*.")
        return
    dice_msg = bot.send_dice(message.chat.id, emoji="🎲")
    value = dice_msg.dice.value
    time.sleep(4)
    result, net = dice.resolve(value, bet_type, bet)
    if result is None:
        bot.reply_to(message, "❌ Invalid type. Use: `even` `odd` `high` `low` or `1-6`")
        return
    db.update_chips(message.from_user.id, net)
    new_bal = db.get_player(message.from_user.id)["chips"]
    sign = "+" if net >= 0 else ""
    bot.reply_to(dice_msg,
        f"{result}\n"
        f"Bet: *{fmt(bet)}* | {sign}*{fmt(net)}* chips\n"
        f"💰 Balance: *{fmt(new_bal)}*")

@bot.callback_query_handler(func=lambda c: c.data.startswith("dice_"))
def cb_dice(call):
    parts  = call.data.split("_")
    action = parts[1]
    cid    = parts[2]
    ch     = db.get_dice(cid)

    if not ch or ch["state"] != "pending":
        bot.answer_callback_query(call.id, "Challenge expired or already played.")
        return

    if action == "decline":
        if call.from_user.id != ch["challenged"]:
            bot.answer_callback_query(call.id, "Not for you.")
            return
        db.update_dice_state(cid, "declined")
        db.update_chips(ch["challenger"], ch["bet"])
        bot.edit_message_text("❌ Challenge declined. Bet refunded.",
                              call.message.chat.id, call.message.message_id)
        return

    if call.from_user.id != ch["challenged"]:
        bot.answer_callback_query(call.id, "You're not the challenged player!")
        return

    opp = db.get_player(ch["challenged"])
    if opp["chips"] < ch["bet"]:
        bot.answer_callback_query(call.id, "Not enough chips!")
        return

    db.update_chips(ch["challenged"], -ch["bet"])
    db.update_dice_state(cid, "played")

    c_name  = db.get_player(ch["challenger"])["first_name"]
    ch_name = db.get_player(ch["challenged"])["first_name"]
    bet     = ch["bet"]

    result, winner, loser = dice.resolve_dice(
        ch["challenger"], c_name,
        ch["challenged"], ch_name,
        bet
    )

    if winner:
        db.update_chips(winner, bet * 2)
    else:
        db.update_chips(ch["challenger"], bet)
        db.update_chips(ch["challenged"], bet)

    bot.edit_message_text(result, call.message.chat.id, call.message.message_id,
                          parse_mode="Markdown")


@bot.message_handler(commands=["addcoins", "add"])
def cmd_addcoins(message):
    uid = message.from_user.id
    if uid not in Config.ADMIN_IDS:
        bot.reply_to(message, "❌ Admin only command.")
        return
    args = message.text.split()
    if len(args) < 3:
        bot.reply_to(message, "Usage: `/addcoins [user_id] [amount]`")
        return
    try:
        target = int(args[1])
        amount = int(args[2])
    except ValueError:
        bot.reply_to(message, "❌ Invalid user_id or amount.")
        return
    p = db.get_player(target)
    if not p:
        bot.reply_to(message, "❌ Player not found. They must /start first.")
        return
    new_bal = db.update_chips(target, amount)
    bot.reply_to(message, f"✅ Added *{fmt(amount)}* chips!\n💰 {p['first_name']} now has *{fmt(new_bal)}* chips.")

# ── Run ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("🎰 Casino Bot starting...")
    db.init_db()
    print("✅ Database ready")
    features.register_features(bot)
    print("✅ Features loaded")
    print("🤖 Bot polling...")
    bot.infinity_polling(timeout=30, long_polling_timeout=30)

@bot.message_handler(commands=["addcoins", "add"])
def cmd_addcoins(message):
    uid = message.from_user.id
    if uid not in Config.ADMIN_IDS:
        bot.reply_to(message, "❌ Admin only command.")
        return
    args = message.text.split()
    if len(args) < 3:
        bot.reply_to(message, "Usage: `/addcoins [user_id] [amount]`")
        return
    try:
        target = int(args[1])
        amount = int(args[2])
    except ValueError:
        bot.reply_to(message, "❌ Invalid user_id or amount.")
        return
    p = db.get_player(target)
    if not p:
        bot.reply_to(message, "❌ Player not found. They must /start first.")
        return
    new_bal = db.update_chips(target, amount)
    bot.reply_to(message, f"✅ Added *{fmt(amount)}* chips!\n💰 {p['first_name']} now has *{fmt(new_bal)}* chips.")
