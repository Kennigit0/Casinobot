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
import minigames
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
        "🎮 *Games:* /slots /dice /bj /roulette /rbet\n"
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
        "/gift `[amount]` — Reply to gift chips\n\n"

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
        "/rbet `[amount]` — 🎲 Risk bet game\n"
        "/rtake — 💰 Cash out from rbet\n\n"

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

# ── /leaderboard ──────────────────────────────────────────────────────
@bot.message_handler(commands=["leaderboard", "top", "lb"])
def cmd_leaderboard(message):
    args = message.text.split()
    by   = "xp" if len(args) > 1 and args[1].lower() == "xp" else "chips"
    rows = db.get_leaderboard(10, by)
    title_str = "🏆 *Leaderboard — Top 10*" if by == "chips" else "⭐ *XP Leaderboard — Top 10*"
    lines  = [f"{title_str}\n"]
    medals = ["🥇","🥈","🥉"]
    for i, r in enumerate(rows):
        m   = medals[i] if i < 3 else f"{i+1}."
        vip = " 👑" if r["vip"] else ""
        lvl = db.xp_to_level(r.get("xp") or 0)
        if by == "xp":
            lines.append(f"{m} *{r['first_name']}*{vip} — Lv.{lvl} | {fmt(r.get('xp',0))} XP")
        else:
            total = (r["chips"] or 0) + (r.get("bank") or 0)
            lines.append(f"{m} *{r['first_name']}*{vip} — {fmt(total)} chips")
    lines.append("\n`/leaderboard xp` — sort by level")
    bot.reply_to(message, "\n".join(lines))

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
    min_bet = max(1, int(p["chips"] * 0.15))
    if bet > p["chips"]:
        bot.reply_to(message, f"❌ Not enough chips! You only have *{p['chips']:,}* chips.", parse_mode="Markdown")
        return
    if bet < min_bet:
        bot.reply_to(message, f"❌ Minimum bet: *{fmt(min_bet)}* chips *(15% of balance)*"); return
    if p["chips"] < bet:
        bot.reply_to(message, f"❌ Not enough chips! You have *{fmt(p['chips'])}*."); return
    ok, msg = db.can_play_game(message.from_user.id)
    if not ok:
        bot.reply_to(message, f"⏰ {msg}"); return
    db.set_last_game(message.from_user.id)
    slot_msg = bot.send_dice(message.chat.id, emoji="🎰")
    value    = slot_msg.dice.value
    time.sleep(3)
    result_msg, net = slots.resolve(value, bet)
    db.update_chips(message.from_user.id, net)
    if net > 0:
        db.add_xp(message.from_user.id, Config.XP_GAME_WIN)
        db.add_win(message.from_user.id)
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
    min_bet = max(1, int(p["chips"] * 0.15))
    if bet > p["chips"]:
        bot.reply_to(message, f"❌ Not enough chips! You only have *{p['chips']:,}* chips.", parse_mode="Markdown")
        return
    if bet < min_bet:
        bot.reply_to(message, f"❌ Minimum bet: *{fmt(min_bet)}* chips *(15% of balance)*"); return
    if p["chips"] < bet:
        bot.reply_to(message, f"❌ Not enough chips! You have *{fmt(p['chips'])}*."); return
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
    min_bet = max(1, int(p["chips"] * 0.15))
    if bet > p["chips"]:
        bot.reply_to(message, f"❌ Not enough chips! You only have *{p['chips']:,}* chips.", parse_mode="Markdown")
        return
    if bet < min_bet:
        bot.reply_to(message, f"❌ Minimum bet: *{fmt(min_bet)}* chips *(15% of balance)*"); return
    if p["chips"] < bet:
        bot.reply_to(message, f"❌ Not enough chips! You have *{fmt(p['chips'])}*."); return
    ok, msg = db.can_play_game(message.from_user.id)
    if not ok:
        bot.reply_to(message, f"⏰ {msg}"); return
    db.set_last_game(message.from_user.id)
    uid  = message.from_user.id
    game = blackjack.new_game(uid, bet, message.chat.id)
    gid  = game["game_id"]
    db.update_chips(uid, -bet)
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
        results = blackjack.resolve(game)
        lines   = [board, "\n\n🏁 *Results:*"]
        for r in results:
            db.update_chips(r["uid"], r["chips"])
            if r["chips"] > 0:
                db.add_xp(r["uid"], Config.XP_BJ_WIN)
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
    minigames.register_minigames(bot)
    print("✅ Minigames loaded")
    minigames.register_minigames(bot)
    print("✅ Minigames loaded")
    print("🤖 Bot polling...")
    bot.infinity_polling(timeout=30, long_polling_timeout=30)
