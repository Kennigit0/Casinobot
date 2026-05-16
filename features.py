"""
features.py — Bank, Rob, Jobs, Gift, Marriage, Profile, Bot-fix
Import this in bot.py and call register_features(bot)
"""

import random
import time
import threading
from telebot import types
import database as db

_bot = None

def register_features(bot_instance):
    global _bot
    _bot = bot_instance
    bot_instance.register_message_handler(cmd_bank,     commands=["bank"])
    bot_instance.register_message_handler(cmd_deposit,  commands=["deposit"])
    bot_instance.register_message_handler(cmd_withdraw, commands=["withdraw"])
    bot_instance.register_message_handler(cmd_interest, commands=["interest"])
    bot_instance.register_message_handler(cmd_rob,      commands=["rob"])
    bot_instance.register_message_handler(cmd_work,     commands=["work"])
    bot_instance.register_message_handler(cmd_crime,    commands=["crime"])
    bot_instance.register_message_handler(cmd_heist,    commands=["heist"])
    bot_instance.register_message_handler(cmd_gift,     commands=["gift"])
    bot_instance.register_message_handler(cmd_marry,    commands=["marry"])
    bot_instance.register_message_handler(cmd_divorce,  commands=["divorce"])
    bot_instance.register_message_handler(cmd_profile,  commands=["profile", "me"])
    bot_instance.register_callback_query_handler(cb_marry,  func=lambda c: c.data.startswith("marry_"))
    bot_instance.register_callback_query_handler(cb_heist,  func=lambda c: c.data.startswith("heist_join_"))

def fmt(n): return f"{n:,}"

# ── Bot detection (dice + blackjack fix) ─────────────────────────────

DICE_BOT_REPLIES = [
    "🤖 Bruh I'm the casino, I don't play against bots 💀",
    "😂 Bot vs Bot? Nah fam, challenge a human!",
    "🎲 Bots are broke, they got no chips 💸",
    "💀 You really tried to challenge a bot? L move bhai",
    "🤡 Bot ko challenge kiya? Seriously? 😭",
    "🤖 Bots don't gamble, we run the casino 😤",
]

BJ_BOT_REPLIES = [
    "🃏 Bots can't sit at my table! Human players only 😤",
    "💀 Bot se Blackjack? Skill issue bruh",
    "🤖 I deal cards to humans, not robots 🙅",
    "😂 Bot ko invite kiya table pe? Touch grass bhai",
    "🃏 No bots allowed at the casino! 🚫",
    "🤣 Bot challenged for Blackjack? Bro is cooked 💀",
]

def is_bot_involved(message):
    """Returns True if reply is to a bot OR any @mention looks like a bot"""
    if message.reply_to_message and message.reply_to_message.from_user.is_bot:
        return True
    if message.entities:
        for entity in message.entities:
            if entity.type == "mention":
                mention = message.text[entity.offset:entity.offset + entity.length].lower()
                if "bot" in mention:
                    return True
    return False

def check_bot_dice(message):
    if is_bot_involved(message):
        _bot.reply_to(message, random.choice(DICE_BOT_REPLIES))
        return True
    return False

def check_bot_bj(message):
    if is_bot_involved(message):
        _bot.reply_to(message, random.choice(BJ_BOT_REPLIES))
        return True
    return False

# ── Bank ──────────────────────────────────────────────────────────────

def cmd_bank(message):
    p = db.get_player(message.from_user.id)
    if not p:
        _bot.reply_to(message, "❗ Register first with /start"); return
    bank  = p.get("bank", 0) or 0
    wallet = p["chips"]
    _bot.reply_to(message,
        f"🏦 *{p['first_name']}'s Bank*\n\n"
        f"👛 Wallet: *{fmt(wallet)}* chips\n"
        f"🏦 Bank:   *{fmt(bank)}* chips\n"
        f"💰 Total:  *{fmt(wallet + bank)}* chips\n\n"
        f"🔒 Banked chips are *safe from robbery!*\n"
        f"📈 Earn *3% daily interest* with /interest\n\n"
        f"  /deposit — put chips in bank\n"
        f"  /withdraw — take chips out")

def cmd_deposit(message):
    p = db.get_player(message.from_user.id)
    if not p:
        _bot.reply_to(message, "❗ Register first with /start"); return
    args = message.text.split()
    if len(args) < 2:
        _bot.reply_to(message, "Usage: `/deposit [amount]`\nExample: `/deposit 5000`"); return
    try:
        amount = int(args[1].replace(",", ""))
    except:
        _bot.reply_to(message, "❌ Invalid amount."); return
    if amount <= 0:
        _bot.reply_to(message, "❌ Amount must be positive."); return
    if p["chips"] < amount:
        _bot.reply_to(message, f"❌ Not enough chips! Wallet: *{fmt(p['chips'])}*"); return
    db.bank_deposit(message.from_user.id, amount)
    new = db.get_player(message.from_user.id)
    _bot.reply_to(message,
        f"🏦 Deposited *{fmt(amount)}* chips!\n"
        f"👛 Wallet: *{fmt(new['chips'])}*\n"
        f"🏦 Bank: *{fmt(new['bank'])}*")

def cmd_withdraw(message):
    p = db.get_player(message.from_user.id)
    if not p:
        _bot.reply_to(message, "❗ Register first with /start"); return
    args = message.text.split()
    if len(args) < 2:
        _bot.reply_to(message, "Usage: `/withdraw [amount]`\nExample: `/withdraw 5000`"); return
    try:
        amount = int(args[1].replace(",", ""))
    except:
        _bot.reply_to(message, "❌ Invalid amount."); return
    bank = p.get("bank", 0) or 0
    if bank < amount:
        _bot.reply_to(message, f"❌ Not enough in bank! Bank: *{fmt(bank)}*"); return
    db.bank_withdraw(message.from_user.id, amount)
    new = db.get_player(message.from_user.id)
    _bot.reply_to(message,
        f"💸 Withdrew *{fmt(amount)}* chips!\n"
        f"👛 Wallet: *{fmt(new['chips'])}*\n"
        f"🏦 Bank: *{fmt(new.get('bank', 0))}*")

def cmd_interest(message):
    ok, earned, msg = db.claim_interest(message.from_user.id)
    if ok:
        new = db.get_player(message.from_user.id)
        _bot.reply_to(message,
            f"📈 *Daily Interest Claimed!*\n"
            f"+*{fmt(earned)}* chips (3% of bank balance)\n"
            f"🏦 Bank: *{fmt(new.get('bank', 0))}*")
    else:
        _bot.reply_to(message, f"⏰ {msg}")

# ── Rob ───────────────────────────────────────────────────────────────

ROB_WIN  = [
    "🥷 Sneaked behind {name} and snatched *{amt}* chips! Gone! 😈",
    "🎭 Disguised as a waiter and pickpocketed *{amt}* from {name} 💀",
    "🏃 Grabbed *{amt}* chips from {name} and ran like Usain Bolt! 🤣",
    "🔦 Robbed {name} in the dark! Took *{amt}* chips, they didn't even notice 😂",
]
ROB_FAIL = [
    "🚔 {name} caught you red-handed! Fined *{fine}* chips by police 😭",
    "💀 You tripped while robbing {name}! Lost *{fine}* chips in court 🤡",
    "😳 {name} was awake! Called cops, you paid *{fine}* chips fine",
    "🤣 Security cameras caught you robbing {name}! -{fine} chips fine",
]

def cmd_rob(message):
    if not message.reply_to_message:
        _bot.reply_to(message, "❗ *Reply* to the person you want to rob!\nThen send `/rob`"); return
    robber_id    = message.from_user.id
    victim_user  = message.reply_to_message.from_user
    if victim_user.is_bot:
        _bot.reply_to(message, "🤖 Rob a bot? They're broke too bhai 😂"); return
    if victim_user.id == robber_id:
        _bot.reply_to(message, "🤡 Robbing yourself? That's just moving chips pocket to pocket 💀"); return
    robber = db.get_player(robber_id)
    victim = db.get_player(victim_user.id)
    if not robber:
        _bot.reply_to(message, "❗ Register first with /start"); return
    if not victim:
        _bot.reply_to(message, f"❌ {victim_user.first_name} isn't registered in the casino!"); return
    ok, msg = db.can_rob(robber_id)
    if not ok:
        _bot.reply_to(message, f"⏰ {msg}"); return
    if victim["chips"] < 500:
        _bot.reply_to(message, f"😂 {victim_user.first_name} is broke! Only *{fmt(victim['chips'])}* in wallet. Find a richer target!"); return
    db.set_last_rob(robber_id)
    if random.random() < 0.45:
        stolen = int(victim["chips"] * random.uniform(0.10, 0.25))
        stolen = max(100, min(stolen, 50000))
        db.update_chips(victim_user.id, -stolen)
        db.update_chips(robber_id, stolen)
        msg = random.choice(ROB_WIN).format(name=victim_user.first_name, amt=fmt(stolen))
        _bot.reply_to(message, f"{msg}\n💰 Your wallet: *{fmt(db.get_player(robber_id)['chips'])}*")
    else:
        fine = min(random.randint(500, 2000), robber["chips"])
        db.update_chips(robber_id, -fine)
        msg = random.choice(ROB_FAIL).format(name=victim_user.first_name, fine=fmt(fine))
        _bot.reply_to(message, f"{msg}\n💸 Wallet: *{fmt(db.get_player(robber_id)['chips'])}*")

# ── Jobs ──────────────────────────────────────────────────────────────

JOBS = [
    ("🚗 Taxi Driver",         "drove 12 passengers across the city",   300, 800),
    ("👨‍🍳 Chef",                "cooked 50 plates of biryani",           400, 900),
    ("💻 Freelancer",          "fixed someone's broken website",         500, 1200),
    ("📦 Delivery Boy",        "delivered 20 packages without crashing", 200, 700),
    ("🏗️ Construction Worker", "built a wall brick by brick",           350, 750),
    ("🎵 Street Musician",     "performed in the park for strangers",    150, 500),
    ("📸 Photographer",        "shot a wedding and didn't drop the cam", 400, 1000),
    ("🧹 Cleaner",             "cleaned an entire office building",      200, 600),
    ("🎲 Casino Dealer",       "dealt cards all night without sleeping", 600, 1100),
    ("🛒 Shop Assistant",      "survived Black Friday at the mall",      250, 650),
    ("🐟 Fish Seller",         "sold fish at 5am in the market",         180, 550),
    ("🚜 Farmer",              "harvested crops in the scorching sun",   300, 700),
]

CRIMES_LIST = [
    ("🏪 Robbed a pan shop",     1500,  3000, 0.60),
    ("🎭 Scammed a tourist",     2000,  4000, 0.55),
    ("💊 Sold fake supplements", 2500,  5000, 0.50),
    ("🚗 Stole a scooty",        3000,  6000, 0.45),
    ("💳 Credit card fraud",     4000,  8000, 0.38),
    ("🏦 Mini bank heist",       6000, 12000, 0.28),
    ("💎 Jewellery shop break-in",8000, 15000, 0.22),
]

def cmd_work(message):
    p = db.get_player(message.from_user.id)
    if not p:
        _bot.reply_to(message, "❗ Register first with /start"); return
    ok, msg = db.can_work(message.from_user.id)
    if not ok:
        _bot.reply_to(message, f"😴 Still tired from last job!\n⏰ {msg}"); return
    title, desc, mn, mx = random.choice(JOBS)
    earned = random.randint(mn, mx)
    db.update_chips(message.from_user.id, earned)
    db.set_last_work(message.from_user.id)
    new_bal = db.get_player(message.from_user.id)["chips"]
    _bot.reply_to(message,
        f"{title}\n\n"
        f"You *{desc}* and earned *{fmt(earned)}* chips! 💪\n\n"
        f"💰 Balance: *{fmt(new_bal)}*\n"
        f"⏰ Next job available in 1 hour")

def cmd_crime(message):
    p = db.get_player(message.from_user.id)
    if not p:
        _bot.reply_to(message, "❗ Register first with /start"); return
    ok, msg = db.can_crime(message.from_user.id)
    if not ok:
        _bot.reply_to(message, f"🕵️ Lay low for now!\n⏰ {msg}"); return
    title, reward, fine, chance = random.choice(CRIMES_LIST)
    db.set_last_crime(message.from_user.id)
    if random.random() < chance:
        db.update_chips(message.from_user.id, reward)
        new_bal = db.get_player(message.from_user.id)["chips"]
        _bot.reply_to(message,
            f"😈 *Crime Successful!*\n\n"
            f"{title}\n"
            f"Got away with *{fmt(reward)}* chips! 💰\n\n"
            f"Balance: *{fmt(new_bal)}*\n"
            f"⏰ Next crime in 2 hours")
    else:
        actual_fine = min(fine, p["chips"])
        db.update_chips(message.from_user.id, -actual_fine)
        new_bal = db.get_player(message.from_user.id)["chips"]
        _bot.reply_to(message,
            f"🚔 *Caught by Police!*\n\n"
            f"{title} — *FAILED* 💀\n"
            f"Fined *{fmt(actual_fine)}* chips!\n\n"
            f"Balance: *{fmt(new_bal)}*\n"
            f"⏰ Next crime in 2 hours")

# ── Heist ─────────────────────────────────────────────────────────────

pending_heists = {}

def cmd_heist(message):
    p = db.get_player(message.from_user.id)
    if not p:
        _bot.reply_to(message, "❗ Register first with /start"); return
    chat_id = message.chat.id
    if chat_id in pending_heists:
        _bot.reply_to(message, "⚠️ A heist is already being planned! Click Join."); return
    args = message.text.split()
    try:
        bet = int(args[1].replace(",", "")) if len(args) > 1 else 1000
    except:
        bet = 1000
    if p["chips"] < bet:
        _bot.reply_to(message, f"❌ Need *{fmt(bet)}* chips to join the heist!"); return
    db.update_chips(message.from_user.id, -bet)
    heist = {
        "host": message.from_user.id,
        "bet":  bet,
        "players": [(message.from_user.id, message.from_user.first_name)],
        "chat_id": chat_id,
    }
    pending_heists[chat_id] = heist
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔫 Join Heist", callback_data=f"heist_join_{chat_id}"))
    sent = _bot.reply_to(message,
        f"🏦 *HEIST PLANNING!*\n\n"
        f"👑 Leader: {message.from_user.first_name}\n"
        f"💰 Entry: *{fmt(bet)}* chips\n"
        f"👥 Crew: 1 member\n\n"
        f"⏳ *30 seconds to join!*\n"
        f"More crew = higher success rate! 😈",
        reply_markup=markup)
    heist["message_id"] = sent.message_id

    def execute():
        time.sleep(30)
        h = pending_heists.pop(chat_id, None)
        if not h:
            return
        players = h["players"]
        count   = len(players)
        chance  = min(0.25 + (count * 0.15), 0.85)
        if random.random() < chance:
            reward = int(h["bet"] * count * random.uniform(2.5, 5))
            for uid, _ in players:
                db.update_chips(uid, reward)
            names = ", ".join(n for _, n in players)
            _bot.send_message(chat_id,
                f"🎉 *HEIST SUCCESSFUL!*\n\n"
                f"👥 Crew: {names}\n"
                f"💰 Each member gets: *{fmt(reward)}* chips!\n\n"
                f"🏃 Escaped clean! Police still looking 😂")
        else:
            names = ", ".join(n for _, n in players)
            _bot.send_message(chat_id,
                f"🚨 *HEIST FAILED!*\n\n"
                f"👥 Crew: {names}\n"
                f"❌ Entry fees lost! Everyone arrested 💀\n\n"
                f"🤡 Caught at the entrance like amateurs 😭")

    threading.Thread(target=execute, daemon=True).start()

def cb_heist(call):
    parts   = call.data.split("_")
    chat_id = int(parts[2])
    uid     = call.from_user.id
    heist   = pending_heists.get(chat_id)
    if not heist:
        _bot.answer_callback_query(call.id, "Heist already started or expired!"); return
    if any(u == uid for u, _ in heist["players"]):
        _bot.answer_callback_query(call.id, "You're already in the crew!"); return
    p = db.get_player(uid)
    if not p:
        _bot.answer_callback_query(call.id, "Register first! Send /start"); return
    if p["chips"] < heist["bet"]:
        _bot.answer_callback_query(call.id, f"Need {fmt(heist['bet'])} chips!"); return
    db.update_chips(uid, -heist["bet"])
    heist["players"].append((uid, call.from_user.first_name))
    names = ", ".join(n for _, n in heist["players"])
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔫 Join Heist", callback_data=f"heist_join_{chat_id}"))
    try:
        _bot.edit_message_text(
            f"🏦 *HEIST PLANNING!*\n\n"
            f"💰 Entry: *{fmt(heist['bet'])}* chips\n"
            f"👥 Crew ({len(heist['players'])}): {names}\n\n"
            f"⏳ Heist executing soon...",
            chat_id, heist["message_id"], reply_markup=markup, parse_mode="Markdown")
    except:
        pass
    _bot.answer_callback_query(call.id, f"✅ Joined! {fmt(heist['bet'])} chips reserved.")

# ── Gift ──────────────────────────────────────────────────────────────

def cmd_gift(message):
    if not message.reply_to_message:
        _bot.reply_to(message, "❗ *Reply* to the person you want to gift!\nThen send `/gift [amount]`"); return
    sender_id    = message.from_user.id
    receiver_user = message.reply_to_message.from_user
    if receiver_user.is_bot:
        _bot.reply_to(message, "🤖 Gift a bot? They can't spend chips bro 😂"); return
    if receiver_user.id == sender_id:
        _bot.reply_to(message, "🤡 Gifting yourself? Just keep it bhai 💀"); return
    sender   = db.get_player(sender_id)
    receiver = db.get_player(receiver_user.id)
    if not sender:
        _bot.reply_to(message, "❗ Register first with /start"); return
    if not receiver:
        _bot.reply_to(message, f"❌ {receiver_user.first_name} hasn't registered yet!"); return
    args = message.text.split()
    if len(args) < 2:
        _bot.reply_to(message, "Usage: Reply to someone → `/gift [amount]`"); return
    try:
        amount = int(args[1].replace(",", ""))
    except:
        _bot.reply_to(message, "❌ Invalid amount."); return
    if amount < 100:
        _bot.reply_to(message, "❌ Minimum gift is *100* chips."); return
    if sender["chips"] < amount:
        _bot.reply_to(message, f"❌ Not enough chips! Wallet: *{fmt(sender['chips'])}*"); return
    db.update_chips(sender_id, -amount)
    db.update_chips(receiver_user.id, amount)
    _bot.reply_to(message,
        f"🎁 *Gift Sent!*\n\n"
        f"{message.from_user.first_name} gifted *{fmt(amount)}* chips to *{receiver_user.first_name}*! 💝\n\n"
        f"💰 Your balance: *{fmt(db.get_player(sender_id)['chips'])}*")

# ── Marriage ──────────────────────────────────────────────────────────

def cmd_marry(message):
    if not message.reply_to_message:
        _bot.reply_to(message, "❗ *Reply* to the person you want to marry!\nThen send `/marry`"); return
    proposer_id  = message.from_user.id
    target_user  = message.reply_to_message.from_user
    if target_user.is_bot:
        _bot.reply_to(message, "🤖 Marry a bot?! Go touch grass bro 💀"); return
    if target_user.id == proposer_id:
        _bot.reply_to(message, "🤡 Marry yourself? Ultimate loner move 😂"); return
    proposer = db.get_player(proposer_id)
    target   = db.get_player(target_user.id)
    if not proposer:
        _bot.reply_to(message, "❗ Register first with /start"); return
    if not target:
        _bot.reply_to(message, f"❌ {target_user.first_name} isn't registered!"); return
    if proposer.get("married_to") and proposer["married_to"] != 0:
        _bot.reply_to(message, "💍 You're already married! Use /divorce first."); return
    if target.get("married_to") and target["married_to"] != 0:
        _bot.reply_to(message, f"💔 {target_user.first_name} is already married to someone!"); return
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("💍 Accept", callback_data=f"marry_yes_{proposer_id}_{target_user.id}"),
        types.InlineKeyboardButton("💔 Reject", callback_data=f"marry_no_{proposer_id}_{target_user.id}")
    )
    _bot.reply_to(message,
        f"💍 *Marriage Proposal!*\n\n"
        f"*{message.from_user.first_name}* is proposing to *{target_user.first_name}*! 💕\n\n"
        f"{target_user.first_name}, do you accept? 🌹",
        reply_markup=markup)

def cb_marry(call):
    parts      = call.data.split("_")
    action     = parts[1]
    proposer_id = int(parts[2])
    target_id  = int(parts[3])
    if call.from_user.id != target_id:
        _bot.answer_callback_query(call.id, "This proposal isn't for you!"); return
    if action == "yes":
        db.marry(proposer_id, target_id)
        p1 = db.get_player(proposer_id)
        p2 = db.get_player(target_id)
        _bot.edit_message_text(
            f"💍 *Married!*\n\n"
            f"💒 {p1['first_name']} & {p2['first_name']} are now married!\n"
            f"May your chips multiply! 💕\n\n"
            f"Use /divorce if things go south 😂",
            call.message.chat.id, call.message.message_id, parse_mode="Markdown")
    else:
        p1 = db.get_player(proposer_id)
        _bot.edit_message_text(
            f"💔 Proposal rejected!\n\n"
            f"{call.from_user.first_name} said NO to {p1['first_name']} 😭\n"
            f"Bro got rejected in public 💀",
            call.message.chat.id, call.message.message_id)

def cmd_divorce(message):
    p = db.get_player(message.from_user.id)
    if not p:
        _bot.reply_to(message, "❗ Register first with /start"); return
    if not p.get("married_to") or p["married_to"] == 0:
        _bot.reply_to(message, "❌ You're not married! Who you divorcing? 😂"); return
    spouse = db.get_player(p["married_to"])
    db.divorce(message.from_user.id, p["married_to"])
    spouse_name = spouse["first_name"] if spouse else "your partner"
    _bot.reply_to(message,
        f"💔 *Divorced from {spouse_name}*\n\n"
        f"Hope you're okay bhai 🥀\n"
        f"Chips are still yours at least 😂")

# ── Profile ───────────────────────────────────────────────────────────

def cmd_profile(message):
    if message.reply_to_message and not message.reply_to_message.from_user.is_bot:
        uid = message.reply_to_message.from_user.id
    else:
        uid = message.from_user.id
    p = db.get_player(uid)
    if not p:
        _bot.reply_to(message, "❌ Player not registered. Send /start first."); return
    vip_tag = "👑 VIP" if p["vip"] else "👤 Regular"
    bank    = p.get("bank", 0) or 0
    married = ""
    if p.get("married_to") and p["married_to"] != 0:
        spouse = db.get_player(p["married_to"])
        if spouse:
            married = f"\n💍 Married to: *{spouse['first_name']}*"
    _bot.reply_to(message,
        f"👤 *{p['first_name']}'s Profile*\n\n"
        f"🏅 Status: {vip_tag}\n"
        f"👛 Wallet: *{fmt(p['chips'])}* chips\n"
        f"🏦 Bank:   *{fmt(bank)}* chips\n"
        f"💰 Total:  *{fmt(p['chips'] + bank)}* chips"
        f"{married}")
