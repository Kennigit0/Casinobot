"""
🎰 Casino Bot V5 — Complete with all features
"""
import os, time, threading
import telebot
from telebot import types
from dotenv import load_dotenv
load_dotenv()

import database as db
import features
import activities
import heist_v2
import gems
import minigames
import lottery
import crash
import clan
import bounty
from config import Config
from games import slots, dice, roulette, blackjack

bot = telebot.TeleBot(Config.BOT_TOKEN, parse_mode="Markdown")

def name(user): return user.first_name or user.username or "Player"
def fmt(n): return f"{n:,}"

def check_registered(message):
    p = db.get_player(message.from_user.id)
    if not p:
        bot.reply_to(message, "❗ You're not registered. Send /start to join!")
        return None
    return p

def is_group(message):
    return message.chat.type in ("group", "supergroup")

pending_bj = {}

# ── /start ────────────────────────────────────────────────────────────
@bot.message_handler(commands=["start"])
def cmd_start(message):
    # Only allow /start in private DM
    if message.chat.type != "private":
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(
            "🎰 Start Bot", url=f"https://t.me/{bot.get_me().username}?start=go"))
        bot.reply_to(message,
            "👋 Hey! To register and play, start me in *private DM* first!",
            reply_markup=markup)
        return
    uid = message.from_user.id
    existing = db.get_player(uid)
    if existing:
        level = db.xp_to_level(existing.get("xp") or 0)
        title = db.get_title(level)
        bot.reply_to(message,
            f"🎰 Welcome back, *{name(message.from_user)}*!\n"
            f"💰 Balance: *{fmt(existing['chips'])}* chips\n"
            f"⭐ Level: *{level}* — {title}\n\n"
            "Type /help to see all commands."); return
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ Yes, I am 18+", callback_data=f"age_yes_{uid}"),
        types.InlineKeyboardButton("❌ No", callback_data=f"age_no_{uid}")
    )
    bot.reply_to(message,
        "🎰 *Welcome to Casino Bot!*\n\n"
        "⚠️ This bot is for *18+ users only*.\n"
        "All games use *virtual chips* — no real money involved.\n\n"
        "Are you 18 years or older?", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("age_"))
def cb_age(call):
    parts  = call.data.split("_")
    answer = parts[1]
    uid    = int(parts[2])
    if call.from_user.id != uid:
        bot.answer_callback_query(call.id, "This isn't for you!"); return
    if answer == "no":
        bot.edit_message_text("❌ Sorry, you must be 18+ to use this bot.",
                              call.message.chat.id, call.message.message_id); return
    db.register_player(uid, call.from_user.username, call.from_user.first_name)
    bot.edit_message_text(
        f"✅ *Welcome, {name(call.from_user)}!*\n\n"
        f"🎁 You received *{fmt(Config.STARTING_CHIPS)}* starting chips!\n\n"
        "🎮 *Games:* /slots /dice /bj /roulette /crash\n"
        "💰 *Economy:* /balance /daily /bank /work /crime\n"
        "👥 *Social:* /marry /gift /rob /profile\n"
        "🎣 *Activities:* /fish /mine /farm *(unlock by leveling up!)*\n\n"
        "Type /help for all commands!",
        call.message.chat.id, call.message.message_id)

# ── /help ─────────────────────────────────────────────────────────────
@bot.message_handler(commands=["help"])
def cmd_help(message):
    bot.reply_to(message,
        "🎰 *Casino Bot V5 — All Commands*\n\n"

        "👤 *Account*\n"
        "/start — Register with age verification\n"
        "/profile — Full profile with level & stats\n"
        "/level — View level, XP & progress bar\n"
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
        "/work — Random job *(3min cooldown)*\n"
        "/crime — Risky crime *(15min cooldown)*\n"
        "/heist `[bet]` — Group heist *(30min cooldown)*\n\n"

        "🔫 *Street*\n"
        "/rob — Reply to someone to rob them *(2hr)*\n"
        "/gift `[amount]` — Reply to gift chips\n"
        "/lottery — 🎟️ Daily jackpot lottery\n"
        "/bounty @user [amount] — 🎯 Place a bounty\n"
        "/mybounty — Check bounties on you\n"
        "/clan — ⚔️ Clan system\n\n"

        "💍 *Social*\n"
        "/marry — Reply to propose\n"
        "/divorce — End marriage\n\n"

        "🎣 *Activities* *(unlock by leveling up!)*\n"
        "/fish — 🎣 Fish 10 items *(Level 5)*\n"
        "/mine — ⛏️ Mine 10 ores *(Level 10)*\n"
        "/farm — 🌾 Farm 10 crops *(Level 15)*\n"
        "/shop `[fishing/mining/farming]` — Browse tools\n"
        "/buy `[item]` — Purchase a tool\n"
        "/equip `[item]` — Equip owned tool\n"
        "/inventory — View your tools\n\n"

        "🎮 *Casino Games*\n"
        "/slots `[bet]` — 🎰 Slot machine animation\n"
        "/dice `[type] [bet]` — 🎲 Dice roll animation\n"
        "/bj `[bet]` — 🃏 Multiplayer blackjack\n"
        "/roulette `[type] [value] [bet]` — 🎡 Roulette\n"
        "/crash — 🚀 Multiplayer crash game\n"
        "/coinflip [amount] — 🪙 1v1 heads or tails\n\n"

        "*🎲 Dice types:*\n"
        "`/dice even 1000` `/dice odd 1000`\n"
        "`/dice high 1000` `/dice low 1000`\n"
        "`/dice 6 1000` — exact number *(x6)*\n\n"

        "*🎡 Roulette types:*\n"
        "`/roulette color red 1000`\n"
        "`/roulette color black 1000`\n"
        "`/roulette color green 1000` *(x14)*\n"
        "`/roulette number 17 1000` *(x35)*\n"
        "`/roulette odd_even odd 1000`\n"
        "`/roulette dozen 1st 1000`\n\n"

        "*🎣 Fishing Rods:*\n"
        "🪵 Wooden — Free | Lv.5 | ⏰ 30min\n"
        "🎣 Basic — 15,000 | Lv.10 | ⏰ 25min\n"
        "🥈 Silver — 75,000 | Lv.20 | ⏰ 20min\n"
        "🥇 Golden — 300,000 | Lv.30 | ⏰ 15min\n"
        "💎 Diamond — 1,500,000 | Lv.40 | ⏰ 10min\n"
        "🔮 Magic — 6,000,000 | Lv.50 | ⏰ 7min\n"
        "⭐ Legendary — 30,000,000 | Lv.75 | ⏰ 5min\n\n"

        "*⛏️ Pickaxes:*\n"
        "🪨 Stone — Free | Lv.10 | ⏰ 30min\n"
        "⚙️ Iron — 15,000 | Lv.15 | ⏰ 25min\n"
        "🥈 Silver — 75,000 | Lv.20 | ⏰ 20min\n"
        "🥇 Gold — 300,000 | Lv.30 | ⏰ 15min\n"
        "💎 Diamond — 1,500,000 | Lv.40 | ⏰ 10min\n"
        "🔮 Enchanted — 6,000,000 | Lv.50 | ⏰ 7min\n"
        "⭐ Legendary — 30,000,000 | Lv.75 | ⏰ 5min\n\n"

        "*🌾 Farming Tools:*\n"
        "🤲 Bare Hands — Free | Lv.15 | ⏰ 30min\n"
        "🪚 Basic Hoe — 15,000 | Lv.20 | ⏰ 25min\n"
        "🥈 Silver Hoe — 75,000 | Lv.25 | ⏰ 20min\n"
        "🥇 Golden Hoe — 300,000 | Lv.35 | ⏰ 15min\n"
        "💎 Diamond Hoe — 1,500,000 | Lv.45 | ⏰ 10min\n"
        "🚜 Magic Tractor — 6,000,000 | Lv.55 | ⏰ 7min\n"
        "⭐ Legendary Tractor — 30,000,000 | Lv.75 | ⏰ 5min\n\n"

        "💰 *Min bet = 15% of balance | No max bet!*\n"
        "⏰ *30 sec cooldown between games*")

# ── /balance ──────────────────────────────────────────────────────────
@bot.message_handler(commands=["balance", "bal", "chips"])
def cmd_balance(message):
    p = check_registered(message)
    if not p: return
    vip_tag = " 👑 VIP" if p["vip"] else ""
    level   = db.xp_to_level(p.get("xp") or 0)
    title   = db.get_title(level)
    bot.reply_to(message,
        f"💰 *{p['first_name']}{vip_tag}*\n"
        f"⭐ Level {level} — {title}\n"
        f"Chips: *{fmt(p['chips'])}*\n\n"
        "Claim your daily bonus with /daily")

# ── /daily ────────────────────────────────────────────────────────────
@bot.message_handler(commands=["daily", "claim"])
def cmd_daily(message):
    p = check_registered(message)
    if not p: return
    ok, bonus, msg = db.claim_daily(message.from_user.id, p["vip"])
    if ok:
        new_bal  = db.get_player(message.from_user.id)["chips"]
        vip_note = " *(VIP bonus!)*" if p["vip"] else ""
        bot.reply_to(message,
            f"🎁 Daily bonus claimed{vip_note}!\n"
            f"+*{fmt(bonus)}* chips | +{Config.XP_DAILY} XP\n"
            f"💰 Balance: *{fmt(new_bal)}*")
    else:
        bot.reply_to(message, f"⏰ {msg}")

# /leaderboard — handled by features.py

# ── /vip ─────────────────────────────────────────────────────────────
@bot.message_handler(commands=["vip"])
def cmd_vip(message):
    p = check_registered(message)
    if not p: return
    if p["vip"]:
        bot.reply_to(message,
            "👑 *You are VIP!*\n\n"
            f"✅ Daily bonus: *{fmt(Config.VIP_DAILY_BONUS)}* chips\n"
            "✅ VIP badge on leaderboard\n"
            "✅ Priority support"); return
    bot.reply_to(message,
        "👑 *VIP Membership*\n\n"
        f"Daily bonus: *{fmt(Config.VIP_DAILY_BONUS)}* chips\n"
        "VIP badge on leaderboard 🏆\n\n"
        f"Price: *{Config.VIP_PRICE_STARS} Telegram Stars*\n\n"
        "Contact the admin to purchase VIP.")

# ── /terms ────────────────────────────────────────────────────────────
@bot.message_handler(commands=["terms"])
def cmd_terms(message):
    bot.reply_to(message,
        "📋 *Terms of Service*\n\n"
        "1. All chips are *VIRTUAL* with zero real-world value.\n"
        "2. You must be *18+* to use this bot.\n"
        "3. Buying/selling chips for real money is *prohibited*.\n"
        "4. Chips cannot be withdrawn or converted to currency.\n"
        "5. The developer is *not responsible* for external transactions.\n"
        "6. Violations result in permanent ban.\n"
        "7. This bot is for *entertainment only*.\n\n"
        "_By using this bot you agree to these terms._")

# ── /addcoins (Admin) ─────────────────────────────────────────────────
@bot.message_handler(commands=["addcoins", "add"])
def cmd_addcoins(message):
    uid = message.from_user.id
    if uid not in Config.ADMIN_IDS:
        bot.reply_to(message, "❌ Admin only command."); return
    args = message.text.split()
    if len(args) < 3:
        bot.reply_to(message, "Usage: `/addcoins [user_id] [amount]`"); return
    try:
        target = int(args[1])
        amount = int(args[2])
    except ValueError:
        bot.reply_to(message, "❌ Invalid user_id or amount."); return
    p = db.get_player(target)
    if not p:
        bot.reply_to(message, "❌ Player not found. They must /start first."); return
    new_bal = db.update_chips(target, amount)
    sign    = "+" if amount >= 0 else ""
    bot.reply_to(message,
        f"✅ {sign}*{fmt(amount)}* chips to *{p['first_name']}*!\n"
        f"💰 New balance: *{fmt(new_bal)}*")

# ── /slots ────────────────────────────────────────────────────────────
@bot.message_handler(commands=["slots", "slot"])
def cmd_slots(message):
    if features.check_bot_dice(message): return
    p = check_registered(message)
    if not p: return
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, f"🎰 Usage: `/slots [bet]`\nExample: `/slots 1000`"); return
    try:
        bet = int(args[1].replace(",", ""))
    except ValueError:
        bot.reply_to(message, "❌ Invalid bet amount."); return
    if p["chips"] <= 0:
        bot.reply_to(message, f"❌ You have no chips! Use /daily or /work to earn some.", parse_mode="Markdown")
        return
    min_bet = max(1, int(p["chips"] * 0.15))
    if bet > p["chips"]:
        bot.reply_to(message, f"❌ Not enough chips! You only have *{p['chips']:,}* chips.", parse_mode="Markdown")
        return
    if bet < min_bet:
        bot.reply_to(message, f"❌ Minimum bet: *{fmt(min_bet)}* chips *(15% of balance)*"); return
    if p["chips"] < bet:
        bot.reply_to(message, f"❌ Not enough chips! You have *{fmt(p['chips'])}*."); return
    # Block if player already has pending table
    for gid, g in pending_bj.items():
        if g.get("host_id") == message.from_user.id:
            bot.reply_to(message, "❌ You already have an open table! Start it or wait for it to expire.", parse_mode="Markdown")
            return
    # Block if player has an active running game in DB
    if db.has_active_bj_game(message.from_user.id):
        bot.reply_to(message, "❌ You already have a game in progress! Finish it first.", parse_mode="Markdown")
        return
    ok, msg = db.can_play_game(message.from_user.id)
    if not ok:
        bot.reply_to(message, f"⏰ {msg}"); return
    db.set_last_game(message.from_user.id)
    db.execute("UPDATE players SET slots_played=COALESCE(slots_played,0)+1, max_bet=GREATEST(COALESCE(max_bet,0),?) WHERE user_id=?", (bet, message.from_user.id))
    slot_msg = bot.send_dice(message.chat.id, emoji="🎰")
    value    = slot_msg.dice.value
    time.sleep(3)
    result_msg, net = slots.resolve(value, bet)
    db.update_chips(message.from_user.id, net)
    if net > 0:
        db.add_xp(message.from_user.id, Config.XP_GAME_WIN)
        db.add_win(message.from_user.id)
        if net > 0:
            db.execute("UPDATE players SET total_earned=COALESCE(total_earned,0)+? WHERE user_id=?", (net, message.from_user.id))
        gems.check_achievements(message.from_user.id, message.chat.id)
    else:
        db.add_loss(message.from_user.id)
    new_bal = db.get_player(message.from_user.id)["chips"]
    sign    = "+" if net >= 0 else ""
    xp_note = f" +{Config.XP_GAME_WIN} XP" if net > 0 else ""
    bot.reply_to(slot_msg,
        f"{result_msg}\n"
        f"Bet: *{fmt(bet)}* | {sign}*{fmt(net)}* chips{xp_note}\n"
        f"💰 Balance: *{fmt(new_bal)}*")

# ── /dice ─────────────────────────────────────────────────────────────
@bot.message_handler(commands=["dice"])
def cmd_dice(message):
    if features.check_bot_dice(message): return
    p = check_registered(message)
    if not p: return
    args = message.text.split()
    if len(args) < 3:
        bot.reply_to(message,
            "🎲 *Dice Game*\n\nUsage: `/dice [type] [bet]`\n\n"
            "*2x payout:*\n"
            "`/dice even 1000` `/dice odd 1000`\n"
            "`/dice high 1000` — rolls 4,5,6\n"
            "`/dice low 1000` — rolls 1,2,3\n\n"
            "*6x payout:*\n"
            "`/dice 6 1000` — exact number 1-6"); return
    bet_type = args[1].lower()
    try:
        bet = int(args[2].replace(",", ""))
    except ValueError:
        bot.reply_to(message, "❌ Invalid bet amount."); return
    if p["chips"] <= 0:
        bot.reply_to(message, f"❌ You have no chips! Use /daily or /work to earn some.", parse_mode="Markdown")
        return
    min_bet = max(1, int(p["chips"] * 0.15))
    if bet > p["chips"]:
        bot.reply_to(message, f"❌ Not enough chips! You only have *{p['chips']:,}* chips.", parse_mode="Markdown")
        return
    if bet < min_bet:
        bot.reply_to(message, f"❌ Minimum bet: *{fmt(min_bet)}* chips *(15% of balance)*"); return
    if p["chips"] < bet:
        bot.reply_to(message, f"❌ Not enough chips! You have *{fmt(p['chips'])}*."); return
    # Block if player already has pending table
    for gid, g in pending_bj.items():
        if g.get("host_id") == message.from_user.id:
            bot.reply_to(message, "❌ You already have an open table! Start it or wait for it to expire.", parse_mode="Markdown")
            return
    # Block if player has an active running game in DB
    if db.has_active_bj_game(message.from_user.id):
        bot.reply_to(message, "❌ You already have a game in progress! Finish it first.", parse_mode="Markdown")
        return
    ok, msg = db.can_play_game(message.from_user.id)
    if not ok:
        bot.reply_to(message, f"⏰ {msg}"); return
    db.set_last_game(message.from_user.id)
    dice_msg = bot.send_dice(message.chat.id, emoji="🎲")
    value    = dice_msg.dice.value
    time.sleep(4)
    result, net = dice.resolve(value, bet_type, bet)
    if result is None:
        bot.reply_to(message, "❌ Invalid type. Use: `even` `odd` `high` `low` or `1-6`"); return
    db.update_chips(message.from_user.id, net)
    if net > 0:
        db.add_xp(message.from_user.id, Config.XP_GAME_WIN)
    new_bal = db.get_player(message.from_user.id)["chips"]
    sign    = "+" if net >= 0 else ""
    xp_note = f" +{Config.XP_GAME_WIN} XP" if net > 0 else ""
    bot.reply_to(dice_msg,
        f"{result}\n"
        f"Bet: *{fmt(bet)}* | {sign}*{fmt(net)}* chips{xp_note}\n"
        f"💰 Balance: *{fmt(new_bal)}*")

# ── /roulette ─────────────────────────────────────────────────────────
@bot.message_handler(commands=["roulette", "rl"])
def cmd_roulette(message):
    p = check_registered(message)
    if not p: return
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
            "`/roulette dozen 1st 500`"); return
    bet_type  = args[1].lower()
    bet_value = args[2].lower()
    try:
        bet = int(args[3].replace(",", ""))
    except ValueError:
        bot.reply_to(message, "❌ Invalid bet amount."); return
    if p["chips"] <= 0:
        bot.reply_to(message, f"❌ You have no chips! Use /daily or /work to earn some.", parse_mode="Markdown")
        return
    min_bet = max(1, int(p["chips"] * 0.15))
    if bet > p["chips"]:
        bot.reply_to(message, f"❌ Not enough chips! You only have *{p['chips']:,}* chips.", parse_mode="Markdown")
        return
    if bet < min_bet:
        bot.reply_to(message, f"❌ Minimum bet: *{fmt(min_bet)}* chips *(15% of balance)*"); return
    if p["chips"] < bet:
        bot.reply_to(message, f"❌ Not enough chips! You have *{fmt(p['chips'])}*."); return
    if bet_type not in {"color","number","odd_even","dozen"}:
        bot.reply_to(message, "❌ Invalid type. Use: color, number, odd_even, dozen"); return
    if bet_type == "number":
        try:
            n = int(bet_value)
            if n < 0 or n > 36: raise ValueError
        except ValueError:
            bot.reply_to(message, "❌ Number must be 0–36."); return
    # Block if player already has pending table
    for gid, g in pending_bj.items():
        if g.get("host_id") == message.from_user.id:
            bot.reply_to(message, "❌ You already have an open table! Start it or wait for it to expire.", parse_mode="Markdown")
            return
    # Block if player has an active running game in DB
    if db.has_active_bj_game(message.from_user.id):
        bot.reply_to(message, "❌ You already have a game in progress! Finish it first.", parse_mode="Markdown")
        return
    ok, msg = db.can_play_game(message.from_user.id)
    if not ok:
        bot.reply_to(message, f"⏰ {msg}"); return
    db.set_last_game(message.from_user.id)
    number, color, winnings, net, result_msg = roulette.resolve(bet_type, bet_value, bet)
    db.update_chips(message.from_user.id, net)
    if net > 0:
        db.add_xp(message.from_user.id, Config.XP_GAME_WIN)
    new_bal = db.get_player(message.from_user.id)["chips"]
    sign    = "+" if net >= 0 else ""
    xp_note = f" +{Config.XP_GAME_WIN} XP" if net > 0 else ""
    bot.reply_to(message,
        f"🎡 *Roulette*\n\n"
        f"🔵 Ball lands on: *{number}* {color}\n\n"
        f"{result_msg}\n"
        f"Bet: *{fmt(bet)}* | {sign}*{fmt(net)}* chips{xp_note}\n"
        f"💰 Balance: *{fmt(new_bal)}*")

# ── /bj ──────────────────────────────────────────────────────────────
@bot.message_handler(commands=["bj", "blackjack"])
def cmd_bj(message):
    if features.check_bot_bj(message): return
    p = check_registered(message)
    if not p: return
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "Usage: `/bj [bet]`\nExample: `/bj 1000`"); return
    try:
        bet = int(args[1].replace(",", ""))
    except ValueError:
        bot.reply_to(message, "❌ Invalid bet."); return
    if p["chips"] <= 0:
        bot.reply_to(message, f"❌ You have no chips! Use /daily or /work to earn some.", parse_mode="Markdown")
        return
    min_bet = max(1, int(p["chips"] * 0.15))
    if bet > p["chips"]:
        bot.reply_to(message, f"❌ Not enough chips! You only have *{p['chips']:,}* chips.", parse_mode="Markdown")
        return
    if bet < min_bet:
        bot.reply_to(message, f"❌ Minimum bet: *{fmt(min_bet)}* chips *(15% of balance)*"); return
    if p["chips"] < bet:
        bot.reply_to(message, f"❌ Not enough chips! You have *{fmt(p['chips'])}*."); return
    # Block if player already has pending table
    for gid, g in pending_bj.items():
        if g.get("host_id") == message.from_user.id:
            bot.reply_to(message, "❌ You already have an open table! Start it or wait for it to expire.", parse_mode="Markdown")
            return
    # Block if player has an active running game in DB
    if db.has_active_bj_game(message.from_user.id):
        bot.reply_to(message, "❌ You already have a game in progress! Finish it first.", parse_mode="Markdown")
        return
    ok, msg = db.can_play_game(message.from_user.id)
    if not ok:
        bot.reply_to(message, f"⏰ {msg}"); return
    db.set_last_game(message.from_user.id)
    uid  = message.from_user.id
    db.update_chips(uid, -bet)  # deduct host bet immediately
    game = blackjack.new_game(uid, bet, message.chat.id)
    gid  = game["game_id"]
    blackjack.add_player(game, uid, name(message.from_user))
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🃏 Join Table", callback_data=f"bj_join_{gid}"),
        types.InlineKeyboardButton("▶️ Start Now",  callback_data=f"bj_start_{gid}")
    )
    sent = bot.reply_to(message,
        f"🃏 *Blackjack Table* #{gid}\n"
        f"Bet: *{fmt(bet)}* chips\nPlayers: 1/6\n1. *{name(message.from_user)}*\n\n"
        f"✋ *Start the game when ready!*", reply_markup=markup)
    game["message_id"] = sent.message_id
    pending_bj[gid]    = game
    def auto_cancel():
        if gid in pending_bj:
            g = pending_bj.pop(gid)
            db.update_chips(g["host_id"], g["bet"])
            for pl in g.get("players", []):
                if pl["uid"] != g["host_id"]:
                    db.update_chips(pl["uid"], g["bet"])
            bot.send_message(g["chat_id"], f"⏰ Blackjack table #{gid} expired — bets refunded.")
    threading.Timer(120, auto_cancel).start()
    db.save_bj_game(gid, message.chat.id, sent.message_id, uid, bet, game)



@bot.callback_query_handler(func=lambda c: c.data.startswith("bj_join_"))
def cb_bj_join(call):
    gid  = call.data.split("_")[2]
    uid  = call.from_user.id
    p    = db.get_player(uid)
    if not p:
        bot.answer_callback_query(call.id, "Register first! /start"); return
    game = pending_bj.get(gid)
    if not game:
        bot.answer_callback_query(call.id, "Table not found or already started."); return
    if any(pl["uid"] == uid for pl in game["players"]):
        bot.answer_callback_query(call.id, "You're already at this table!"); return
    bet = game["bet"]
    if p["chips"] < bet:
        bot.answer_callback_query(call.id, f"Not enough chips! Need {fmt(bet)}."); return
    db.update_chips(uid, -bet)  # deduct joiner bet immediately
    blackjack.add_player(game, uid, name(call.from_user))
    db.save_bj_game(gid, game["chat_id"], game["message_id"], game["host_id"], bet, game)
    player_list = "\n".join(f"{i+1}. *{pl['name']}*" for i, pl in enumerate(game["players"]))
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🃏 Join Table", callback_data=f"bj_join_{gid}"),
        types.InlineKeyboardButton("▶️ Start Now",  callback_data=f"bj_start_{gid}")
    )
    try:
        bot.edit_message_text(
            f"🃏 *Blackjack Table* #{gid}\nBet: *{fmt(bet)}* chips\n"
            f"Players: {len(game['players'])}/6\n{player_list}\n\n⏳ Joining open...",
            call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
    except: pass
    bot.answer_callback_query(call.id, f"✅ Joined! Bet {fmt(bet)} reserved.")

@bot.callback_query_handler(func=lambda c: c.data.startswith("bj_start_"))
def cb_bj_start(call):
    gid  = call.data.split("_")[2]
    game = pending_bj.get(gid)
    if not game:
        bot.answer_callback_query(call.id, "Game not found."); return
    if call.from_user.id != game["host_id"]:
        bot.answer_callback_query(call.id, "Only the host can start early."); return
    bot.answer_callback_query(call.id, "Starting!")
    start_bj_game(gid, call.message.chat.id, call.message.message_id)

def start_bj_game(gid, chat_id, message_id):
    game = pending_bj.pop(gid, None)
    if not game or not game["players"]: return
    blackjack.deal_cards(game)
    db.save_bj_game(gid, chat_id, message_id, game["host_id"], game["bet"], game)
    send_bj_board(gid, chat_id, message_id, game)

def send_bj_board(gid, chat_id, message_id, game):
    board = blackjack.game_board(game, hide_dealer=game["state"] != "done")
    cp    = blackjack.current_player(game)
    if game["state"] == "done":
        # Delete game FIRST to prevent double payout from concurrent callbacks
        deleted = db.delete_bj_game(gid)
        if not deleted:
            return  # already paid out by another callback
        results = blackjack.resolve(game)
        lines   = [board, "\n\n🏁 *Results:*"]
        bet = game["bet"]
        for r in results:
            # Chips were deducted upfront on join, so add back bet to get correct net:
            # Win: resolve=+bet, payout=+bet+bet=+2bet → net +bet ✅
            # Lose: resolve=-bet, payout=0 → net -bet ✅
            # Push: resolve=0, payout=+bet → net 0 ✅
            payout = r["chips"] + bet
            if payout > 0:
                db.update_chips(r["uid"], payout)
                db.add_xp(r["uid"], Config.XP_BJ_WIN)
                db.add_win(r["uid"])
                db.execute("UPDATE players SET bj_wins=COALESCE(bj_wins,0)+1 WHERE user_id=?", (r["uid"],))
            elif payout == 0:
                pass  # push or loss — chips already taken upfront
            else:
                db.add_loss(r["uid"])
            net  = payout - bet  # net change from player perspective
            sign = "+" if net >= 0 else ""
            lines.append(f"• *{r['name']}*: {r['result']} ({sign}{fmt(net)})")
        text   = "\n".join(lines)
        markup = None
    elif cp:
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("👊 Hit",  callback_data=f"bj_hit_{gid}_{cp['uid']}"),
            types.InlineKeyboardButton("✋ Stand", callback_data=f"bj_stand_{gid}_{cp['uid']}")
        )
        text = board + f"\n\n👉 *{cp['name']}* — Hit or Stand?"
    else:
        text = board; markup = None
    try:
        bot.edit_message_text(text, chat_id, message_id, reply_markup=markup, parse_mode="Markdown")
    except Exception:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c: c.data.startswith("bj_hit_") or c.data.startswith("bj_stand_"))
def cb_bj_action(call):
    parts  = call.data.split("_")
    action = parts[1]
    gid    = parts[2]
    target = int(parts[3])
    if call.from_user.id != target:
        bot.answer_callback_query(call.id, "It's not your turn!"); return
    game = db.get_bj_game(gid)
    if not game:
        bot.answer_callback_query(call.id, "Game not found."); return
    game = game["data"]
    if action == "hit":
        blackjack.hit(game, target)
        bot.answer_callback_query(call.id, "🃏 Hit!")
    else:
        blackjack.stand(game, target)
        bot.answer_callback_query(call.id, "✋ Stand!")
    db.update_bj_game(gid, game)
    send_bj_board(gid, call.message.chat.id, call.message.message_id, game)


@bot.message_handler(commands=["addvip", "vip_add"])
def cmd_addvip(message):
    uid = message.from_user.id
    if uid not in Config.ADMIN_IDS:
        bot.reply_to(message, "❌ Admin only command.")
        return
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "Usage: `/addvip [user_id]`")
        return
    try:
        target = int(args[1])
    except ValueError:
        bot.reply_to(message, "❌ Invalid user_id.")
        return
    p = db.get_player(target)
    if not p:
        bot.reply_to(message, "❌ Player not found. They must /start first.")
        return
    db.set_vip(target, 1)
    bot.reply_to(message, f"✅ *{p['first_name']}* is now VIP! 👑")

@bot.message_handler(commands=["removevip"])
def cmd_removevip(message):
    uid = message.from_user.id
    if uid not in Config.ADMIN_IDS:
        bot.reply_to(message, "❌ Admin only command.")
        return
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "Usage: `/removevip [user_id]`")
        return
    try:
        target = int(args[1])
    except ValueError:
        bot.reply_to(message, "❌ Invalid user_id.")
        return
    p = db.get_player(target)
    if not p:
        bot.reply_to(message, "❌ Player not found.")
        return
    db.set_vip(target, 0)
    bot.reply_to(message, f"✅ VIP removed from *{p['first_name']}*.")

# ── Run ───────────────────────────────────────────────────────────────
def keep_db_alive():
    """Ping database every 4 minutes to prevent Supabase pause"""
    import threading
    def ping():
        while True:
            try:
                db.execute("SELECT 1", fetch="one")
            except Exception as e:
                print(f"DB ping error: {e}")
            time.sleep(240)  # 4 minutes
    t = threading.Thread(target=ping, daemon=True)
    t.start()
    print("✅ DB keep-alive started")

if __name__ == "__main__":
    print("🎰 Casino Bot V5 starting...")
    db.init_db()
    keep_db_alive()
    print("✅ Database ready")
    features.register_features(bot)
    print("✅ Features loaded")
    activities.register_activities(bot)
    print("✅ Activities loaded")
    heist_v2.register_heist2(bot)
    print("✅ Heist V2 loaded")
    gems.register_gems(bot)
    print("✅ Gems loaded")
    minigames.register_minigames(bot)
    print("✅ Minigames loaded")
    lottery.register_lottery(bot)
    print("✅ Lottery loaded")
    crash.register_crash(bot)
    print("✅ Crash loaded")
    clan.register_clan(bot)
    print("✅ Clan loaded")
    bot.register_message_handler(lottery.cmd_lastlottery, commands=["lastlottery", "lastwinner"])
    bot.register_message_handler(lottery.cmd_drawlottery, commands=["drawlottery"])
    bounty.register_bounty(bot)
    print("✅ Bounty loaded")

@bot.message_handler(commands=["bjcancel", "cancelBJ", "bjleave"])
def cmd_bjcancel(message):
    uid = message.from_user.id
    p   = db.get_player(uid)
    if not p: bot.reply_to(message, "❗ Register first with /start"); return

    # Check pending table
    for gid, g in list(pending_bj.items()):
        if g.get("host_id") == uid:
            bet = g.get("bet", 0)
            # Refund all players
            for pl in g.get("players", []):
                db.update_chips(pl["uid"], bet)
            pending_bj.pop(gid, None)
            db.execute("DELETE FROM bj_games WHERE game_id=?", (gid,))
            bot.reply_to(message, f"✅ Table cancelled! *{fmt(bet)}* chips refunded.")
            return

    # Check active DB game
    row = db.execute(
        "SELECT game_id, bet, data FROM bj_games WHERE host_id=?",
        (uid,), fetch="one"
    )
    if not row:
        # Check if player is a joiner (not host)
        import json
        rows = db.execute("SELECT game_id, bet, data FROM bj_games", fetch="all") or []
        for r in rows:
            gid  = r["game_id"] if isinstance(r, dict) else r[0]
            bet  = r["bet"]     if isinstance(r, dict) else r[1]
            data = r["data"]    if isinstance(r, dict) else r[2]
            try:
                gdata = json.loads(data)
                players = gdata.get("players", [])
                if any(pl["uid"] == uid for pl in players):
                    # Remove player from game
                    gdata["players"] = [pl for pl in players if pl["uid"] != uid]
                    db.update_chips(uid, bet)
                    db.execute("UPDATE bj_games SET data=? WHERE game_id=?",
                               (json.dumps(gdata), gid))
                    bot.reply_to(message, f"✅ Left the BJ table! *{fmt(bet)}* chips refunded.")
                    return
            except: continue
        bot.reply_to(message, "❌ You have no active BJ game.")
        return

    gid  = row["game_id"] if isinstance(row, dict) else row[0]
    bet  = row["bet"]     if isinstance(row, dict) else row[1]
    data_str = row["data"] if isinstance(row, dict) else row[2]
    try:
        import json
        gdata   = json.loads(data_str)
        players = gdata.get("players", [])
        # Refund all players
        for pl in players:
            db.update_chips(pl["uid"], bet)
    except: db.update_chips(uid, bet)

    db.execute("DELETE FROM bj_games WHERE game_id=?", (gid,))
    bot.reply_to(message, f"✅ BJ game cancelled! Chips refunded to all players.")


if __name__ == "__main__":
    pass  # already initialized above


# ── /coinflip ──────────────────────────────────────────────────────────
pending_flips = {}  # chat_id -> {host_id, bet, host_choice, msg_id}

@bot.message_handler(commands=["coinflip", "cf", "headstails"])
def cmd_coinflip(message):
    uid  = message.from_user.id
    p    = db.get_player(uid)
    if not p: bot.reply_to(message, "❗ Register first with /start"); return
    if message.chat.type == "private":
        bot.reply_to(message, "❌ Coinflip is a group game! Use it in a group chat."); return

    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "Usage: `/coinflip [amount]`\nExample: `/coinflip 5000`"); return
    try: bet = int(args[1].replace(",",""))
    except: bot.reply_to(message, "❌ Invalid amount."); return
    if bet <= 0:
        bot.reply_to(message, "❌ Amount must be positive."); return
    if p["chips"] < bet:
        bot.reply_to(message, f"❌ Not enough chips! Have: *{fmt(p['chips'])}*"); return

    chat_id = message.chat.id
    if chat_id in pending_flips:
        bot.reply_to(message, "⚠️ A coinflip is already waiting in this chat! Accept or wait."); return

    # Host picks heads or tails
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("🪙 Heads", callback_data=f"cf_pick_heads_{uid}_{bet}"),
        types.InlineKeyboardButton("🍀 Tails", callback_data=f"cf_pick_tails_{uid}_{bet}"),
    )
    bot.reply_to(message,
        f"🪙 *Coinflip — {fmt(bet)} chips*\n\n"
        f"*{message.from_user.first_name}* — pick your side!",
        reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("cf_pick_") or c.data.startswith("cf_accept_") or c.data.startswith("cf_cancel_"))
def cb_coinflip(call):
    uid  = call.from_user.id
    data = call.data
    cid  = call.message.chat.id

    if data.startswith("cf_pick_"):
        parts     = data.split("_")
        choice    = parts[2]           # heads or tails
        host_id   = int(parts[3])
        bet       = int(parts[4])

        if uid != host_id:
            bot.answer_callback_query(call.id, "❌ Only the challenger can pick!", show_alert=True); return

        p = db.get_player(uid)
        if p["chips"] < bet:
            bot.answer_callback_query(call.id, "❌ Not enough chips!", show_alert=True); return

        pending_flips[cid] = {"host_id": host_id, "bet": bet, "host_choice": choice, "msg_id": call.message.message_id}
        opponent_choice = "Tails 🍀" if choice == "heads" else "Heads 🪙"
        host_choice_str = "Heads 🪙" if choice == "heads" else "Tails 🍀"

        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("✅ Accept", callback_data=f"cf_accept_{host_id}_{bet}"),
            types.InlineKeyboardButton("❌ Cancel", callback_data=f"cf_cancel_{host_id}"),
        )
        try:
            bot.edit_message_text(
                f"🪙 *Coinflip — {fmt(bet)} chips*\n\n"
                f"🎯 *{call.from_user.first_name}* picked *{host_choice_str}*\n"
                f"Anyone can accept and take *{opponent_choice}*!\n\n"
                f"Winner takes *{fmt(bet * 2)}* chips 🏆",
                cid, call.message.message_id,
                reply_markup=markup, parse_mode="Markdown"
            )
        except: pass
        bot.answer_callback_query(call.id, f"You picked {host_choice_str}!")
        return

    if data.startswith("cf_cancel_"):
        host_id = int(data.split("_")[-1])
        if uid != host_id:
            bot.answer_callback_query(call.id, "Only the host can cancel!"); return
        pending_flips.pop(cid, None)
        bot.answer_callback_query(call.id, "Cancelled!")
        try: bot.edit_message_text("❌ Coinflip cancelled.", cid, call.message.message_id)
        except: pass
        return

    if data.startswith("cf_accept_"):
        parts   = data.split("_")
        host_id = int(parts[2])
        bet     = int(parts[3])

        if uid == host_id:
            bot.answer_callback_query(call.id, "❌ You can\'t accept your own coinflip!", show_alert=True); return

        flip = pending_flips.get(cid)
        if not flip:
            bot.answer_callback_query(call.id, "❌ No active coinflip found!"); return

        p_host  = db.get_player(host_id)
        p_guest = db.get_player(uid)
        if p_host["chips"] < bet:
            bot.answer_callback_query(call.id, "Host no longer has enough chips!", show_alert=True)
            pending_flips.pop(cid, None); return
        if p_guest["chips"] < bet:
            bot.answer_callback_query(call.id, f"❌ Need {fmt(bet)} chips to accept!", show_alert=True); return

        # Flip the coin!
        import random
        result        = random.choice(["heads", "tails"])
        host_choice   = flip["host_choice"]
        host_name     = p_host["first_name"]
        guest_name    = p_guest["first_name"]
        result_str    = "Heads 🪙" if result == "heads" else "Tails 🍀"

        pending_flips.pop(cid, None)

        if result == host_choice:
            # Host wins
            db.update_chips(uid, -bet)
            db.update_chips(host_id, bet)
            winner, loser = host_name, guest_name
            winner_id = host_id
        else:
            # Guest wins
            db.update_chips(host_id, -bet)
            db.update_chips(uid, bet)
            winner, loser = guest_name, host_name
            winner_id = uid

        db.add_xp(winner_id, 20)
        bot.answer_callback_query(call.id)
        try:
            bot.edit_message_text(
                f"🪙 *Coinflip Result!*\n\n"
                f"🎲 The coin landed on *{result_str}*!\n\n"
                f"🏆 *{winner}* wins *{fmt(bet * 2)}* chips!\n"
                f"💸 *{loser}* loses *{fmt(bet)}* chips.",
                cid, call.message.message_id, parse_mode="Markdown"
            )
        except: pass

# ── Auto-cleanup stale BJ games + start polling ───────────────────────
if __name__ == "__main__":
    from datetime import datetime, timedelta, timezone
    import json
    stale_time = (datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=30)).isoformat()
    stale = db.execute(
        "SELECT game_id, bet, data FROM bj_games WHERE created_at < ? OR created_at IS NULL",
        (stale_time,), fetch="all"
    ) or []
    for row in stale:
        gid2     = row["game_id"] if isinstance(row, dict) else row[0]
        bet2     = row["bet"]     if isinstance(row, dict) else row[1]
        data_str2= row["data"]    if isinstance(row, dict) else row[2]
        try:
            gdata2 = json.loads(data_str2)
            for pl in gdata2.get("players", []):
                db.update_chips(pl["uid"], bet2)
        except: pass
        db.execute("DELETE FROM bj_games WHERE game_id=?", (gid2,))
    if stale: print(f"🧹 Cleaned {len(stale)} stale BJ game(s)")
    print("🤖 Bot polling...")
    bot.infinity_polling(timeout=30, long_polling_timeout=30)
