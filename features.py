"""features.py — Bank, Rob, Jobs, Gift, Marriage, Profile, Bot-detection"""
import random, time, threading
from telebot import types
import database as db
from config import Config

_bot = None



def _btn(text, data): return types.InlineKeyboardButton(text, callback_data=data)
def _markup(*rows):
    m = types.InlineKeyboardMarkup()
    for row in rows: m.row(*row)
    return m

# ── /bank ──────────────────────────────────────────────────────────────

def cmd_bankupgrade(message):
    _show_bankupgrade(message.from_user.id, message)

def _show_bankupgrade(uid, message):
    p   = db.get_player(uid)
    lvl = p.get("bank_level") or 0
    lines = ["🏦 *Bank Upgrade Tiers*\n"]
    for l, data in db.BANK_LEVELS.items():
        arrow = " ◀ *YOU*" if l == lvl else ""
        cost  = f"{data['upgrade_cost']:,}" if data["upgrade_cost"] else "MAX"
        limit = f"{data['limit']:,}" if data["limit"] < 999_999_999 else "Unlimited"
        lines.append(f"Lv.{l} *{data['name']}* — {limit} chips | Cost: {cost}{arrow}")
    markup = None
    if lvl < 6:
        cost = db.BANK_LEVELS[lvl]["upgrade_cost"]
        lines.append(f"\n💡 Upgrade to *{db.BANK_LEVELS[lvl+1]['name']}* for *{cost:,}* chips")
        markup = _markup([_btn(f"⬆️ Upgrade for {cost:,} chips", "bank_upg_confirm")])
    else:
        lines.append("\n✅ Max level reached!")
    _bot.reply_to(message, "\n".join(lines), reply_markup=markup)

# ── /interest ──────────────────────────────────────────────────────────


def cmd_leaderboard(message):
    args = message.text.split()
    by   = "xp" if len(args) > 1 and args[1].lower() == "xp" else "chips"
    _send_leaderboard(message, by)

def _send_leaderboard(message, by):
    rows   = db.get_leaderboard(10, by)
    title  = "🏆 *Top 10 — Richest*" if by == "chips" else "⭐ *Top 10 — XP*"
    lines  = [f"{title}\n"]
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
    markup = _markup([
        _btn("💰 By Chips" if by == "xp" else "✅ By Chips", "lb_chips"),
        _btn("✅ By XP" if by == "xp" else "⭐ By XP",      "lb_xp"),
    ])
    _bot.reply_to(message, "\n".join(lines), reply_markup=markup)

# ── /shop ──────────────────────────────────────────────────────────────
def cmd_shop(message):
    markup = _markup(
        [_btn("🎣 Fishing Rods", "shop_fishing")],
        [_btn("⛏️ Pickaxes",     "shop_mining")],
        [_btn("🌾 Farming Tools", "shop_farming")],
    )
    args = message.text.split()
    if len(args) > 1:
        cat = args[1].lower()
        from config import Config
        cat_map = {'fishing': Config.FISHING_TOOLS, 'mining': Config.MINING_TOOLS, 'farming': Config.FARMING_TOOLS}
        items = cat_map.get(cat, {})
        if not items: _bot.reply_to(message, "❌ Invalid category."); return
        p = db.get_player(message.from_user.id)
        owned = db.get_player_tools(message.from_user.id).get("owned_tools", [])
        if isinstance(owned, str):
            import json; owned = json.loads(owned)
        lines = [f"🛒 *{cat.title()} Shop*\n"]
        btns = []
        for item_id, info in items.items():
            have = item_id in owned
            status = "✅ Owned" if have else f"{info['price']:,} chips"
            lines.append(f"{'✅' if have else '▫️'} *{info['name']}* — {status}")
            btns.append([_btn(f"Equip {info['name']}" if have else f"Buy {info['name']} {info['price']:,}", f"equip_{item_id}" if have else f"buy_{item_id}")])
        _bot.reply_to(message, "\n".join(lines), reply_markup=_markup(*btns), parse_mode="Markdown")
        return
    _bot.reply_to(message, "🛒 *Shop — Choose a category:*", reply_markup=markup)

# ── /inventory ─────────────────────────────────────────────────────────
def cmd_inventory(message):
    uid  = message.from_user.id
    p    = db.get_player(uid)
    if not p: _bot.reply_to(message, "❗ /start first"); return
    from activities import TOOLS
    tools = db.get_player_tools(uid)
    owned = tools.get("owned_tools", [])
    if isinstance(owned, str):
        import json; owned = json.loads(owned)
    lines = ["🎒 *Your Inventory*\n"]
    btns  = []
    for t in owned:
        for cat in ["fishing","mining","farming"]:
            if t in TOOLS[cat]:
                info    = TOOLS[cat][t]
                eq_fish = tools.get("fishing_tool") == t
                eq_mine = tools.get("mining_tool") == t
                eq_farm = tools.get("farming_tool") == t
                equipped = eq_fish or eq_mine or eq_farm
                lines.append(f"{'✅' if equipped else '▫️'} {info['name']}")
                if not equipped:
                    btns.append([_btn(f"Equip {info['name']}", f"equip_{t}")])
    markup = _markup(*btns) if btns else None
    _bot.reply_to(message, "\n".join(lines), reply_markup=markup)

# ── /games ─────────────────────────────────────────────────────────────
def cmd_games(message):
    markup = _markup(
        [_btn("🎰 Slots",     "game_slots"), _btn("🎲 Dice",  "game_dice")],
        [_btn("🃏 Blackjack", "game_bj"),    _btn("🎡 Roulette","game_rl")],
        [_btn("🎲 Risk Bet",  "game_rbet")],
    )
    _bot.reply_to(message,
        "🎮 *Casino Games*\n\nPick a game — then send your bet amount!\n"
        "Example: after picking Slots → `/slots 500`", reply_markup=markup)

# ── /deposit fix ───────────────────────────────────────────────────────
def cmd_deposit(message):
    p = db.get_player(message.from_user.id)
    if not p: _bot.reply_to(message, "❗ /start first"); return
    args = message.text.split()
    if len(args) < 2:
        limit = db.get_bank_limit(message.from_user.id)
        _bot.reply_to(message,
            f"🏦 *Bank Deposit*\nUsage: `/deposit [amount]` or `/deposit all`\n\n"
            f"💡 Your bank limit: *{fmt(limit)}* chips\nUpgrade with /bankupgrade!")
        return
    amt_str = args[1].lower()
    try:
        amount = p["chips"] if amt_str == "all" else int(amt_str.replace(",",""))
    except:
        _bot.reply_to(message, "❌ Invalid amount."); return
    if amount <= 0: _bot.reply_to(message, "❌ Amount must be positive."); return
    if p["chips"] < amount: _bot.reply_to(message, "❌ Not enough chips in wallet!"); return
    ok, result = db.bank_deposit(message.from_user.id, amount)
    if ok:
        new = db.get_player(message.from_user.id)
        _bot.reply_to(message,
            f"✅ Deposited *{fmt(result)}* chips!\n"
            f"🏦 Bank: *{fmt(new['bank'])}* / *{fmt(db.get_bank_limit(message.from_user.id))}*\n"
            f"👛 Wallet: *{fmt(new['chips'])}*")
    else:
        markup = _markup([_btn("Upgrade Bank", "bank_upg")])
        _bot.reply_to(message, result, reply_markup=markup)

def handle_bank_callbacks(call):
    uid  = call.from_user.id
    data = call.data
    p    = db.get_player(uid)
    if not p: _bot.answer_callback_query(call.id, "Register first! /start"); return

    if data == "bank_dep":
        _bot.answer_callback_query(call.id)
        _bot.send_message(call.message.chat.id,
            f"💰 Send: `/deposit [amount]` or `/deposit all`\n"
            f"Bank limit: *{fmt(db.get_bank_limit(uid))}*")

    elif data == "bank_with":
        _bot.answer_callback_query(call.id)
        _bot.send_message(call.message.chat.id, "💸 Send: `/withdraw [amount]` or `/withdraw all`")

    elif data == "bank_int":
        ok, bonus, msg = db.claim_interest(uid)
        if ok:
            _bot.answer_callback_query(call.id, f"✅ +{bonus:,} chips interest!")
            new = db.get_player(uid)
            _bot.send_message(call.message.chat.id,
                f"📈 Interest claimed! +*{fmt(bonus)}* chips\n"
                f"🏦 Bank: *{fmt(new['bank'])}*")
        else:
            _bot.answer_callback_query(call.id, msg, show_alert=True)

    elif data == "bank_upg":
        _bot.answer_callback_query(call.id)
        _show_bankupgrade(uid, call.message)

    elif data == "bank_upg_confirm":
        ok, result = db.upgrade_bank(uid)
        if ok:
            _bot.answer_callback_query(call.id, f"✅ Upgraded to {result['name']}!")
            _bot.send_message(call.message.chat.id,
                f"✅ Bank upgraded to *{result['name']}*!\n"
                f"🏦 New limit: *{fmt(result['limit'])}* chips")
        else:
            _bot.answer_callback_query(call.id, result, show_alert=True)

    elif data == "lb_chips":
        _bot.answer_callback_query(call.id)
        _send_leaderboard(call.message, "chips")

    elif data == "lb_xp":
        _bot.answer_callback_query(call.id)
        _send_leaderboard(call.message, "xp")

    elif data.startswith("shop_"):
        cat = data.replace("shop_","")
        _bot.answer_callback_query(call.id)
        from config import Config
        cat_map = {'fishing': Config.FISHING_TOOLS, 'mining': Config.MINING_TOOLS, 'farming': Config.FARMING_TOOLS}
        items = cat_map.get(cat, {})
        if not items:
            _bot.send_message(call.message.chat.id, "❌ No items found.")
        else:
            p2   = db.get_player(uid)
            owned = db.get_player_tools(uid).get("owned_tools", [])
            if isinstance(owned, str):
                import json; owned = json.loads(owned)
            lines = [f"🛒 *{cat.title()} Shop*\n"]
            btns  = []
            for item_id, info in items.items():
                have = item_id in owned
                status = "✅ Owned" if have else f"{info['price']:,} chips"
                lines.append(f"{'✅' if have else '▫️'} *{info['name']}* — {status}\n_{info.get('desc','')}_ (+{info.get('bonus',0)}% yield)")
                if not have:
                    btns.append([_btn(f"Buy {info['name']} — {info['price']:,}", f"buy_{item_id}")])
                else:
                    btns.append([_btn(f"Equip {info['name']}", f"equip_{item_id}")])
            markup2 = _markup(*btns) if btns else None
            _bot.send_message(call.message.chat.id, "\n".join(lines), reply_markup=markup2, parse_mode="Markdown")

    elif data.startswith("buy_"):
        item_id = data.replace("buy_","")
        from config import Config
        all_tools = {**Config.FISHING_TOOLS, **Config.MINING_TOOLS, **Config.FARMING_TOOLS}
        for cat, items in [('fishing', Config.FISHING_TOOLS), ('mining', Config.MINING_TOOLS), ('farming', Config.FARMING_TOOLS)]:
            if item_id in items:
                info  = items[item_id]
                owned = db.get_player_tools(uid).get("owned_tools", [])
                if isinstance(owned, str):
                    import json; owned = json.loads(owned)
                if item_id in owned:
                    _bot.answer_callback_query(call.id, "Already owned!", show_alert=True); break
                p2 = db.get_player(uid)
                if p2["chips"] < info["price"]:
                    _bot.answer_callback_query(call.id, f"Need {info['price']:,} chips!", show_alert=True); break
                db.update_chips(uid, -info["price"])
                db.add_tool(uid, item_id)
                _bot.answer_callback_query(call.id, f"✅ Bought {info['name']}!")
                _bot.send_message(call.message.chat.id,
                    f"✅ Bought *{info['name']}*!\n"
                    f"💰 -{info['price']:,} chips\n"
                    f"Tap Equip to use it!", reply_markup=_markup([_btn(f"Equip {info['name']}", f"equip_{item_id}")]))
                break

    elif data.startswith("equip_"):
        item_id = data.replace("equip_","")
        from config import Config
        all_tools = {**Config.FISHING_TOOLS, **Config.MINING_TOOLS, **Config.FARMING_TOOLS}
        for cat, items in [('fishing', Config.FISHING_TOOLS), ('mining', Config.MINING_TOOLS), ('farming', Config.FARMING_TOOLS)]:
            if item_id in items:
                db.equip_tool(uid, cat, item_id)
                info = items[item_id]
                _bot.answer_callback_query(call.id, f"✅ Equipped {info['name']}!")
                _bot.send_message(call.message.chat.id, f"✅ *{info['name']}* equipped for {cat}!")
                break

    elif data.startswith("game_"):
        game = data.replace("game_","")
        tips = {
            "slots":  "🎰 `/slots [bet]` — e.g. `/slots 500`",
            "dice":   "🎲 `/dice even 500` or `/dice odd 500` or `/dice high 500`",
            "bj":     "🃏 `/bj [bet]` — e.g. `/bj 1000`",
            "rl":     "🎡 `/roulette color red 500`",
            "rbet":   "🎲 `/rbet [amount]` — risk bet game",
        }
        _bot.answer_callback_query(call.id)
        _bot.send_message(call.message.chat.id, tips.get(game, "Use the command to play!"))


def cmd_announce(message):
    uid = message.from_user.id
    from config import Config
    if uid not in Config.ADMIN_IDS:
        _bot.reply_to(message, "❌ Admins only!"); return
    args = message.text.split(None, 1)
    if len(args) < 2:
        _bot.reply_to(message, "Usage: /announce [your message]"); return
    text = args[1]
    sent = 0
    failed = 0
    # Send to all groups
    for chat_id in db.get_all_groups():
        try:
            _bot.send_message(chat_id, f"📢 *Announcement*\n\n{text}", parse_mode="Markdown")
            sent += 1
        except: failed += 1
    # Send DM to all registered players
    players = db.execute("SELECT DISTINCT user_id FROM players", fetch=True)
    for p in players:
        try:
            _bot.send_message(p["user_id"], f"📢 *Announcement*\n\n{text}", parse_mode="Markdown")
            sent += 1
        except: failed += 1
    _bot.reply_to(message, f"✅ Sent: {sent}\n❌ Failed: {failed} (players who never DMed bot)")

def _auto_save_group(message):
    if message.chat.type in ("group", "supergroup"):
        db.save_group(message.chat.id)


def cmd_group_to_play(message):
    from telebot import types as _types
    markup = _types.InlineKeyboardMarkup()
    markup.add(_types.InlineKeyboardButton("🎰 Join Kenni's Casino", url="https://t.me/kennicasinogc"))
    _bot.reply_to(message,
        "🔍 *Looking for a group to play Kenni's Casino?*\n"
        "_Check out the group below:_\n\n"
        "🎰 @kennicasinogc • 👥 Active daily\n\n"
        "Join and start playing! /start to register.",
        parse_mode="Markdown", reply_markup=markup)

def register_features(bot_instance):
    
    bot_instance.register_callback_query_handler(
        handle_bank_callbacks,
        func=lambda c: c.data in ['bank_dep','bank_with','bank_int','bank_upg','bank_upg_confirm','lb_chips','lb_xp']
            or c.data.startswith('shop_') or c.data.startswith('equip_') or c.data.startswith('game_')
    )
    global _bot
    _bot = bot_instance
    for cmd, fn in [
        (["bank"],              cmd_bank),
        (["deposit"],           cmd_deposit),
        (["withdraw"],          cmd_withdraw),
        (["interest"],          cmd_interest),
        (["rob"],               cmd_rob),
        (["work"],              cmd_work),
        (["crime"],             cmd_crime),
        (["heist"],             cmd_heist),
        (["gift"],              cmd_gift),
        (["marry"],             cmd_marry),
        (["divorce"],           cmd_divorce),
        (["profile", "me"],     cmd_profile),
        (["group_to_play","grouptoplay"], cmd_group_to_play),
        (["announce"],            cmd_announce),
        (["games","game"],        cmd_games),
        (["interest"],            cmd_interest),
        (["bank"],                cmd_bank),
        (["leaderboard","top","lb"], cmd_leaderboard),
        (["shop"],                cmd_shop),
        (["inventory"],           cmd_inventory),
        (["bankupgrade","upgradebank"], cmd_bankupgrade),
        (["deposit"],                  cmd_deposit),
        (["level", "xp"],       cmd_level),
    ]:
        bot_instance.register_message_handler(fn, commands=cmd)
    bot_instance.register_callback_query_handler(cb_marry,  func=lambda c: c.data.startswith("marry_"))
    bot_instance.register_callback_query_handler(cb_heist,  func=lambda c: c.data.startswith("heist_join_"))

def fmt(n): return f"{n:,}"

# ── Bot detection ─────────────────────────────────────────────────────
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
]

def is_bot_involved(message):
    if message.reply_to_message and message.reply_to_message.from_user.is_bot:
        return True
    if message.entities:
        for entity in message.entities:
            if entity.type == "mention":
                mention = message.text[entity.offset:entity.offset + entity.length].lower()
                if "bot" in mention:
                    return True
    for word in message.text.split():
        if word.startswith("@") and "bot" in word.lower():
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
    if not p: _bot.reply_to(message, "❗ Register first with /start"); return
    bank   = p.get("bank") or 0
    wallet = p["chips"]
    _bot.reply_to(message,
        f"🏦 *{p['first_name']}'s Bank*\n\n"
        f"👛 Wallet: *{fmt(wallet)}* chips\n"
        f"🏦 Bank:   *{fmt(bank)}* chips\n"
        f"💰 Total:  *{fmt(wallet + bank)}* chips\n\n"
        f"🔒 Banked chips are *safe from robbery!*\n"
        f"📈 Earn *3% daily interest* with /interest")

def cmd_deposit(message):
    p = db.get_player(message.from_user.id)
    if not p: _bot.reply_to(message, "❗ Register first with /start"); return
    args = message.text.split()
    if len(args) < 2: _bot.reply_to(message, "Usage: `/deposit [amount]`"); return
    try: amount = int(args[1].replace(",", ""))
    except: _bot.reply_to(message, "❌ Invalid amount."); return
    if amount <= 0: _bot.reply_to(message, "❌ Amount must be positive."); return
    if p["chips"] < amount: _bot.reply_to(message, f"❌ Not enough chips! Wallet: *{fmt(p['chips'])}*"); return
    db.bank_deposit(message.from_user.id, amount)
    new = db.get_player(message.from_user.id)
    _bot.reply_to(message, f"🏦 Deposited *{fmt(amount)}* chips!\n👛 Wallet: *{fmt(new['chips'])}*\n🏦 Bank: *{fmt(new['bank'])}*")

def cmd_withdraw(message):
    p = db.get_player(message.from_user.id)
    if not p: _bot.reply_to(message, "❗ Register first with /start"); return
    args = message.text.split()
    if len(args) < 2: _bot.reply_to(message, "Usage: `/withdraw [amount]`"); return
    try: amount = int(args[1].replace(",", ""))
    except: _bot.reply_to(message, "❌ Invalid amount."); return
    bank = p.get("bank") or 0
    if bank < amount: _bot.reply_to(message, f"❌ Not enough in bank! Bank: *{fmt(bank)}*"); return
    db.bank_withdraw(message.from_user.id, amount)
    new = db.get_player(message.from_user.id)
    _bot.reply_to(message, f"💸 Withdrew *{fmt(amount)}* chips!\n👛 Wallet: *{fmt(new['chips'])}*\n🏦 Bank: *{fmt(new.get('bank', 0))}*")

def cmd_interest(message):
    ok, earned, msg = db.claim_interest(message.from_user.id)
    if ok:
        new = db.get_player(message.from_user.id)
        _bot.reply_to(message, f"📈 *Daily Interest Claimed!*\n+*{fmt(earned)}* chips (3% of bank)\n🏦 Bank: *{fmt(new.get('bank', 0))}*")
    else:
        _bot.reply_to(message, f"⏰ {msg}")

# ── Level ─────────────────────────────────────────────────────────────
def cmd_level(message):
    if message.reply_to_message and not message.reply_to_message.from_user.is_bot:
        uid = message.reply_to_message.from_user.id
    else:
        uid = message.from_user.id
    p = db.get_player(uid)
    if not p: _bot.reply_to(message, "❌ Player not registered."); return
    xp      = p.get("xp") or 0
    level   = db.xp_to_level(xp)
    title   = db.get_title(level)
    bar     = db.progress_bar(xp)
    next_xp = db.level_to_xp(level + 1)

    # Unlocks
    unlocks = []
    if level >= 5:  unlocks.append("🎣 Fishing")
    if level >= 10: unlocks.append("⛏️ Mining")
    if level >= 15: unlocks.append("🌾 Farming")
    unlock_str = " | ".join(unlocks) if unlocks else "None yet"

    next_unlock = ""
    if level < 5:   next_unlock = f"\n🔒 Next unlock at Level 5: Fishing"
    elif level < 10: next_unlock = f"\n🔒 Next unlock at Level 10: Mining"
    elif level < 15: next_unlock = f"\n🔒 Next unlock at Level 15: Farming"

    _bot.reply_to(message,
        f"👤 *{p['first_name']}* — Level *{level}* {title}\n\n"
        f"XP: *{fmt(xp)}* / *{fmt(next_xp)}*\n"
        f"{bar}\n\n"
        f"🔓 Unlocked: {unlock_str}"
        f"{next_unlock}")

# ── Rob ───────────────────────────────────────────────────────────────
ROB_WIN  = [
    "🥷 Sneaked behind {name} and snatched *{amt}* chips! 😈",
    "🎭 Disguised as a waiter and pickpocketed *{amt}* from {name} 💀",
    "🏃 Grabbed *{amt}* chips from {name} and ran! 🤣",
    "🔦 Robbed {name} in the dark! Took *{amt}* chips 😂",
]
ROB_FAIL = [
    "🚔 {name} caught you! Fined *{fine}* chips 😭",
    "💀 You tripped while robbing {name}! Lost *{fine}* chips 🤡",
    "😳 {name} was awake! Cops fined you *{fine}* chips",
    "🤣 Security cameras caught you! -{fine} chips fine",
]

def cmd_rob(message):
    if not message.reply_to_message:
        _bot.reply_to(message, "❗ *Reply* to the person you want to rob!\nThen send `/rob`"); return
    robber_id   = message.from_user.id
    victim_user = message.reply_to_message.from_user
    if victim_user.is_bot:
        _bot.reply_to(message, "🤖 Rob a bot? They're broke too bhai 😂"); return
    if victim_user.id == robber_id:
        _bot.reply_to(message, "🤡 Robbing yourself? That's just moving chips 💀"); return
    robber = db.get_player(robber_id)
    victim = db.get_player(victim_user.id)
    if not robber: _bot.reply_to(message, "❗ Register first with /start"); return
    if not victim: _bot.reply_to(message, f"❌ {victim_user.first_name} isn't registered!"); return

    # Level restriction — within 5 levels
    robber_level = db.xp_to_level(robber.get("xp") or 0)
    victim_level = db.xp_to_level(victim.get("xp") or 0)
    level_diff   = abs(robber_level - victim_level)
    if level_diff > 5:
        _bot.reply_to(message,
            f"❌ Can't rob someone more than 5 levels away!\n"
            f"Your level: *{robber_level}* | Their level: *{victim_level}*"); return

    ok, msg = db.can_rob(robber_id)
    if not ok: _bot.reply_to(message, f"⏰ {msg}"); return
    if victim["chips"] < 500:
        _bot.reply_to(message, f"😂 {victim_user.first_name} is broke! Only *{fmt(victim['chips'])}* chips."); return

    db.set_last_rob(robber_id)

    # Steal % based on level difference
    if robber_level >= victim_level + 3:
        steal_pct = random.uniform(0.20, 0.30)
    elif robber_level >= victim_level + 1:
        steal_pct = random.uniform(0.15, 0.25)
    else:
        steal_pct = random.uniform(0.10, 0.20)

    if random.random() < 0.45:
        stolen = int(victim["chips"] * steal_pct)
        stolen = max(100, min(stolen, 100000))
        db.update_chips(victim_user.id, -stolen)
        db.update_chips(robber_id, stolen)
        msg = random.choice(ROB_WIN).format(name=victim_user.first_name, amt=fmt(stolen))
        _bot.reply_to(message, f"{msg}\n💰 Your wallet: *{fmt(db.get_player(robber_id)['chips'])}*")
    else:
        # Fine = 10% of robber's wallet
        fine = max(100, int(robber["chips"] * 0.10))
        fine = min(fine, robber["chips"])
        db.update_chips(robber_id, -fine)
        msg = random.choice(ROB_FAIL).format(name=victim_user.first_name, fine=fmt(fine))
        _bot.reply_to(message, f"{msg}\n💸 Wallet: *{fmt(db.get_player(robber_id)['chips'])}*")

# ── Jobs ──────────────────────────────────────────────────────────────
JOBS = [
    ("🚗 Taxi Driver",         "drove 12 passengers across the city",   300, 800),
    ("👨‍🍳 Chef",               "cooked 50 plates of biryani",           400, 900),
    ("💻 Freelancer",          "fixed someone's broken website",         500, 1200),
    ("📦 Delivery Boy",        "delivered 20 packages on time",          200, 700),
    ("🏗️ Construction Worker", "built a wall brick by brick",           350, 750),
    ("🎵 Street Musician",     "performed in the park for strangers",    150, 500),
    ("📸 Photographer",        "shot a wedding without dropping cam",    400, 1000),
    ("🧹 Cleaner",             "cleaned an entire office building",      200, 600),
    ("🎲 Casino Dealer",       "dealt cards all night without sleeping", 600, 1100),
    ("🛒 Shop Assistant",      "survived Black Friday at the mall",      250, 650),
    ("🐟 Fish Seller",         "sold fish at 5am in the market",         180, 550),
    ("🚜 Farmer",              "harvested crops in the scorching sun",   300, 700),
]

CRIMES_LIST = [
    ("🏪 Robbed a pan shop",      1500,  0.10, 0.60),
    ("🎭 Scammed a tourist",      2000,  0.12, 0.55),
    ("💊 Sold fake supplements",  2500,  0.14, 0.50),
    ("🚗 Stole a scooty",         3000,  0.16, 0.45),
    ("💳 Credit card fraud",      4000,  0.18, 0.38),
    ("🏦 Mini bank heist",        6000,  0.20, 0.28),
    ("💎 Jewellery shop break-in",8000,  0.25, 0.22),
]

def cmd_work(message):
    p = db.get_player(message.from_user.id)
    if not p: _bot.reply_to(message, "❗ Register first with /start"); return
    ok, msg = db.can_work(message.from_user.id)
    if not ok: _bot.reply_to(message, f"😴 Still tired!\n⏰ {msg}"); return
    title, desc, mn, mx = random.choice(JOBS)
    earned = random.randint(mn, mx)
    db.update_chips(message.from_user.id, earned)
    db.set_last_work(message.from_user.id)
    db.add_xp(message.from_user.id, Config.XP_WORK)
    new_bal = db.get_player(message.from_user.id)["chips"]
    _bot.reply_to(message,
        f"{title}\n\nYou *{desc}* and earned *{fmt(earned)}* chips! 💪\n\n"
        f"💰 Balance: *{fmt(new_bal)}*\n+{Config.XP_WORK} XP\n⏰ Work again in 3 minutes")


CRIME_WIN_MSGS = [
    "🎭 Pizza delivery wala ban ke nikla aur poora loot ke aa gaya! Absolute legend!",
    "🐱 Billi pe blame daal diya. They believed it. Genius move bhai.",
    "🤡 Joker suit pehna tha. Nobody suspected a thing. Respect.",
    "🧠 Big brain play! Tu khud bhi shocked hoga ki yeh kaam kar gaya.",
    "😎 So smooth bhai, unhone thank you bola jaate waqt. LOL.",
    "🤑 Paisa aa gaya, mood ban gaya. Chal chai pite hain.",
    "🐍 Saanp jaisi chaal. Silent, deadly, successful. Bindaas!",
    "🦸 Criminal mastermind unlocked. CBI notes le rahi hai teri.",
]

CRIME_LOSS_MSGS = [
    "🚓 Bhaagте waqt apne hi pair pe gir gaya. Classic Bollywood fail.",
    "📸 Camera dhakna bhool gaya. Bhai seedha selfie de di police ko.",
    "🤦 Crime scene pe ID card chhod aaya. Bro are you okay??",
    "😂 Victim ne tujhe chase kiya. Ab tu victim hai. Ironic.",
    "💀 Sweeper ne pakad liya. SWEEPER NE. Sharam kar thodi.",
    "🤡 Galat number dial kiya backup ke liye. Pizza delivery aa gayi.",
    "🫠 Itna bura plan tha ki police ko bhi taras aa gaya.",
    "🐔 Darr ke wall se takra gaya. The wall won. You lost.",
]

HEIST_WIN_MSGS = [
    "🎬 Ocean's Eleven vibes! Pure cinema tha yaar. Ekdum mast!",
    "💼 Bags bhar ke nikle aur security guard ne khud darwaza khola. LOL.",
    "🧨 Plan kaam aaya - jo tha aur jo nahi tha dono ne kaam kiya!",
    "🦅 Bhoot jaisa aaya, bhoot jaisa gaya. Kisi ko kuch pata nahi.",
    "🎯 Mission Impossible ka BGM bajne laga. Flawless execution crew!",
    "🤑 Poori crew ne aaj mast khaya. Respect to the gang!",
]

HEIST_LOSS_MSGS = [
    "💥 Alarm bypass karte waqt kisi ne chheenk maari. Sab barbaad ho gaya.",
    "🚨 Getaway driver seedha police station le gaya. Bhai seriously??",
    "😭 Bags lena bhool gaye. Wapas aaye. Pakde gaye. Typical Indian heist.",
    "🤦 Ek banda mid-heist Instagram pe story daal raha tha. Fired on spot.",
    "🐕 Kutte ne blueprint kha liya. Everything fell apart bhai.",
    "📵 Walkie talkie galat channel pe tha poore time. Communication zero.",
    "🫠 Itna bura heist tha ki criminals ko bhi sharam aa gayi.",
]

def cmd_crime(message):
    p = db.get_player(message.from_user.id)
    if not p: _bot.reply_to(message, "❗ Register first with /start"); return
    ok, msg = db.can_crime(message.from_user.id)
    if not ok: _bot.reply_to(message, f"🕵️ Lay low!\n⏰ {msg}"); return
    title, reward, fine_pct, chance = random.choice(CRIMES_LIST)
    db.set_last_crime(message.from_user.id)
    if random.random() < chance:
        db.update_chips(message.from_user.id, reward)
        db.add_xp(message.from_user.id, Config.XP_CRIME)
        new_bal = db.get_player(message.from_user.id)["chips"]
        _bot.reply_to(message,
            f"😈 *Crime Successful!*\n\n{title}\n+*{fmt(reward)}* chips!\n\n"
            f"{random.choice(CRIME_WIN_MSGS)}\n\nBalance: *{fmt(new_bal)}*\n+{Config.XP_CRIME} XP\n⏰ Next crime in 15 minutes")
    else:
        # Fine = % of wallet, not all chips
        fine = max(100, int(p["chips"] * fine_pct))
        fine = min(fine, p["chips"])
        db.update_chips(message.from_user.id, -fine)
        new_bal = db.get_player(message.from_user.id)["chips"]
        _bot.reply_to(message,
            f"🚔 *Caught by Police!*\n\n{title} — *FAILED* 💀\n"
            f"Fined *{fmt(fine)}* chips ({int(fine_pct*100)}% of wallet)\n\n"
            f"{random.choice(CRIME_LOSS_MSGS)}\n\nBalance: *{fmt(new_bal)}*\n⏰ Next crime in 15 minutes")

# ── Heist ─────────────────────────────────────────────────────────────
pending_heists = {}

def cmd_heist(message):
    p = db.get_player(message.from_user.id)
    if not p: _bot.reply_to(message, "❗ Register first with /start"); return
    ok, msg = db.can_heist(message.from_user.id)
    if not ok: _bot.reply_to(message, f"⏰ {msg}"); return
    chat_id = message.chat.id
    if chat_id in pending_heists: _bot.reply_to(message, "⚠️ A heist is already being planned!"); return
    args = message.text.split()
    try: bet = int(args[1].replace(",", "")) if len(args) > 1 else 1000
    except: bet = 1000
    min_bet = max(1, int(p["chips"] * 0.15))
    if bet < min_bet: _bot.reply_to(message, f"❌ Minimum bet: *{fmt(min_bet)}* chips"); return
    if p["chips"] < bet: _bot.reply_to(message, f"❌ Not enough chips!"); return
    db.update_chips(message.from_user.id, -bet)
    db.set_last_heist(message.from_user.id)
    heist = {"host": message.from_user.id, "bet": bet,
             "players": [(message.from_user.id, message.from_user.first_name)], "chat_id": chat_id}
    pending_heists[chat_id] = heist
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔫 Join Heist", callback_data=f"heist_join_{chat_id}"))
    sent = _bot.reply_to(message,
        f"🏦 *HEIST PLANNING!*\n\n👑 Leader: {message.from_user.first_name}\n"
        f"💰 Entry: *{fmt(bet)}* chips\n👥 Crew: 1\n\n⏳ *30 seconds to join!*\nMore crew = higher success! 😈",
        reply_markup=markup)
    heist["message_id"] = sent.message_id

    def execute_heist():
        time.sleep(30)
        h = pending_heists.pop(chat_id, None)
        if not h: return
        players = h["players"]
        count   = len(players)
        chance  = min(0.25 + (count * 0.15), 0.85)
        if random.random() < chance:
            reward = int(h["bet"] * count * random.uniform(2.5, 5))
            for uid, _ in players:
                db.update_chips(uid, reward)
                db.add_xp(uid, Config.XP_HEIST)
            names = ", ".join(n for _, n in players)
            _bot.send_message(chat_id,
                f"🎉 *HEIST SUCCESSFUL!*\n\n👥 Crew: {names}\n"
                f"💰 Each member gets: *{fmt(reward)}* chips!\n🏃 Escaped clean! 😎")
        else:
            names = ", ".join(n for _, n in players)
            _bot.send_message(chat_id,
                f"🚨 *HEIST FAILED!*\n\n👥 Crew: {names}\n❌ Entry fees lost!\n🤡 Caught at the door 💀")

    threading.Thread(target=execute_heist, daemon=True).start()

def cb_heist(call):
    parts   = call.data.split("_")
    chat_id = int(parts[2])
    uid     = call.from_user.id
    heist   = pending_heists.get(chat_id)
    if not heist: _bot.answer_callback_query(call.id, "Heist already started!"); return
    if any(u == uid for u, _ in heist["players"]): _bot.answer_callback_query(call.id, "Already in crew!"); return
    p = db.get_player(uid)
    if not p: _bot.answer_callback_query(call.id, "Register first! /start"); return
    if p["chips"] < heist["bet"]: _bot.answer_callback_query(call.id, f"Need {fmt(heist['bet'])} chips!"); return
    db.update_chips(uid, -heist["bet"])
    heist["players"].append((uid, call.from_user.first_name))
    names = ", ".join(n for _, n in heist["players"])
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔫 Join Heist", callback_data=f"heist_join_{chat_id}"))
    try:
        _bot.edit_message_text(
            f"🏦 *HEIST PLANNING!*\n\n💰 Entry: *{fmt(heist['bet'])}* chips\n"
            f"👥 Crew ({len(heist['players'])}): {names}\n\n⏳ Executing soon...",
            chat_id, heist["message_id"], reply_markup=markup, parse_mode="Markdown")
    except: pass
    _bot.answer_callback_query(call.id, f"✅ Joined!")

# ── Gift ──────────────────────────────────────────────────────────────
def cmd_gift(message):
    if not message.reply_to_message:
        _bot.reply_to(message, "❗ *Reply* to the person you want to gift!\nThen `/gift [amount]`"); return
    sender_id     = message.from_user.id
    receiver_user = message.reply_to_message.from_user
    if receiver_user.is_bot: _bot.reply_to(message, "🤖 Gift a bot? 😂"); return
    if receiver_user.id == sender_id: _bot.reply_to(message, "🤡 Gifting yourself? 💀"); return
    sender   = db.get_player(sender_id)
    receiver = db.get_player(receiver_user.id)
    if not sender: _bot.reply_to(message, "❗ Register first"); return
    if not receiver: _bot.reply_to(message, f"❌ {receiver_user.first_name} isn't registered!"); return
    args = message.text.split()
    if len(args) < 2: _bot.reply_to(message, "Usage: Reply → `/gift [amount]`"); return
    try: amount = int(args[1].replace(",", ""))
    except: _bot.reply_to(message, "❌ Invalid amount."); return
    if amount < 100: _bot.reply_to(message, "❌ Minimum gift is *100* chips."); return
    if sender["chips"] < amount: _bot.reply_to(message, f"❌ Not enough chips!"); return
    db.update_chips(sender_id, -amount)
    db.update_chips(receiver_user.id, amount)
    _bot.reply_to(message,
        f"🎁 *Gift Sent!*\n\n{message.from_user.first_name} gifted *{fmt(amount)}* chips to *{receiver_user.first_name}*! 💝\n\n"
        f"💰 Your balance: *{fmt(db.get_player(sender_id)['chips'])}*")

# ── Marriage ──────────────────────────────────────────────────────────
def cmd_marry(message):
    if not message.reply_to_message:
        _bot.reply_to(message, "❗ *Reply* to the person you want to marry!"); return
    proposer_id = message.from_user.id
    target_user = message.reply_to_message.from_user
    if target_user.is_bot: _bot.reply_to(message, "🤖 Marry a bot?! 💀"); return
    if target_user.id == proposer_id: _bot.reply_to(message, "🤡 Marry yourself? 😂"); return
    proposer = db.get_player(proposer_id)
    target   = db.get_player(target_user.id)
    if not proposer: _bot.reply_to(message, "❗ Register first"); return
    if not target: _bot.reply_to(message, f"❌ {target_user.first_name} isn't registered!"); return
    if proposer.get("married_to") and proposer["married_to"] != 0:
        _bot.reply_to(message, "💍 You're already married! Use /divorce first."); return
    if target.get("married_to") and target["married_to"] != 0:
        _bot.reply_to(message, f"💔 {target_user.first_name} is already married!"); return
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("💍 Accept", callback_data=f"marry_yes_{proposer_id}_{target_user.id}"),
        types.InlineKeyboardButton("💔 Reject", callback_data=f"marry_no_{proposer_id}_{target_user.id}")
    )
    _bot.reply_to(message,
        f"💍 *Marriage Proposal!*\n\n*{message.from_user.first_name}* is proposing to *{target_user.first_name}*! 💕\n\n"
        f"{target_user.first_name}, do you accept? 🌹", reply_markup=markup)

def cb_marry(call):
    parts       = call.data.split("_")
    action      = parts[1]
    proposer_id = int(parts[2])
    target_id   = int(parts[3])
    if call.from_user.id != target_id: _bot.answer_callback_query(call.id, "Not for you!"); return
    if action == "yes":
        db.marry(proposer_id, target_id)
        p1 = db.get_player(proposer_id)
        p2 = db.get_player(target_id)
        _bot.edit_message_text(
            f"💍 *Married!*\n\n💒 {p1['first_name']} & {p2['first_name']} are now married!\n"
            f"May your chips multiply! 💕\n\nUse /divorce if things go south 😂",
            call.message.chat.id, call.message.message_id, parse_mode="Markdown")
    else:
        p1 = db.get_player(proposer_id)
        _bot.edit_message_text(
            f"💔 Proposal rejected!\n\n{call.from_user.first_name} said NO to {p1['first_name']} 😭\nGot rejected in public 💀",
            call.message.chat.id, call.message.message_id)

def cmd_divorce(message):
    p = db.get_player(message.from_user.id)
    if not p: _bot.reply_to(message, "❗ Register first"); return
    if not p.get("married_to") or p["married_to"] == 0:
        _bot.reply_to(message, "❌ You're not married!"); return
    spouse = db.get_player(p["married_to"])
    db.divorce(message.from_user.id, p["married_to"])
    spouse_name = spouse["first_name"] if spouse else "your partner"
    _bot.reply_to(message, f"💔 *Divorced from {spouse_name}*\n\nChips are still yours 😂")

# ── Profile ───────────────────────────────────────────────────────────
def cmd_profile(message):
    if message.reply_to_message and not message.reply_to_message.from_user.is_bot:
        uid = message.reply_to_message.from_user.id
    else:
        uid = message.from_user.id
    p = db.get_player(uid)
    if not p: _bot.reply_to(message, "❌ Player not registered."); return
    vip_tag  = "👑 VIP" if p["vip"] else "👤 Regular"
    bank     = p.get("bank") or 0
    xp       = p.get("xp") or 0
    level    = db.xp_to_level(xp)
    title    = db.get_title(level)
    married  = ""
    if p.get("married_to") and p["married_to"] != 0:
        spouse = db.get_player(p["married_to"])
        if spouse: married = f"\n💍 Married to: *{spouse['first_name']}*"
    wins     = p.get("wins") or 0
    losses   = p.get("losses") or 0
    total_g  = wins + losses
    ratio    = f"{wins/total_g*100:.1f}%" if total_g > 0 else "N/A"
    bank_lvl = p.get("bank_level") or 0
    bank_info  = db.BANK_LEVELS[bank_lvl]
    bank_limit = bank_info["limit"]
    bank_pct   = f"{bank/bank_limit*100:.1f}%" if bank_limit < 999_999_999 else "MAX"
    _bot.reply_to(message,
        f"👤 *{p['first_name']}'s Profile*\n\n"
        f"🏅 Status: {vip_tag}\n"
        f"⭐ Level: *{level}* — {title}\n"
        f"✨ XP: *{fmt(xp)}*\n"
        f"👛 Wallet: *{fmt(p['chips'])}* chips\n"
        f"🏦 Bank: *{fmt(bank)}* / *{fmt(bank_limit)}* ({bank_pct})\n"
        f"🏦 Bank Tier: *{bank_info['name']}* Lv.{bank_lvl}\n"
        f"💰 Total: *{fmt(p['chips'] + bank)}* chips\n\n"
        f"🎮 Games Played: *{total_g}*\n"
        f"✅ Wins: *{wins}*  ❌ Losses: *{losses}*\n"
        f"📊 Win Rate: *{ratio}*"
        f"{married}")
