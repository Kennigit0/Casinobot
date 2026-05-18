"""
activities.py — Fishing, Mining, Farming, Shop, Inventory, Rbet
"""

import random
from datetime import datetime, timedelta
from telebot import types
import database as db

_bot = None

def register_activities(bot_instance):
    global _bot
    _bot = bot_instance
    bot_instance.register_message_handler(cmd_fish,      commands=["fish"])
    bot_instance.register_message_handler(cmd_mine,      commands=["mine"])
    bot_instance.register_message_handler(cmd_farm,      commands=["farm"])
    bot_instance.register_message_handler(cmd_collect,   commands=["collect"])
    bot_instance.register_message_handler(cmd_shop,      commands=["shop"])
    bot_instance.register_message_handler(cmd_buy,       commands=["buy"])
    bot_instance.register_message_handler(cmd_inventory, commands=["inventory", "inv"])
    bot_instance.register_message_handler(cmd_equip,     commands=["equip"])
    bot_instance.register_message_handler(cmd_rbet,      commands=["rbet"])
    bot_instance.register_message_handler(cmd_rtake,     commands=["rtake"])
    bot_instance.register_callback_query_handler(cb_rbet, func=lambda c: c.data.startswith("rbet_"))

def fmt(n): return f"{n:,}"

# ── Tool Configs ──────────────────────────────────────────────────────

FISHING_TOOLS = {
    "wooden_rod":     {"name": "🪵 Wooden Rod",      "price": 0,         "wait": 30, "rare": 0.05},
    "basic_rod":      {"name": "🎣 Basic Rod",        "price": 5000,      "wait": 25, "rare": 0.10},
    "silver_rod":     {"name": "🥈 Silver Rod",       "price": 25000,     "wait": 20, "rare": 0.20},
    "golden_rod":     {"name": "🥇 Golden Rod",       "price": 100000,    "wait": 15, "rare": 0.35},
    "diamond_rod":    {"name": "💎 Diamond Rod",      "price": 500000,    "wait": 10, "rare": 0.55},
    "magic_rod":      {"name": "🔮 Magic Rod",        "price": 2000000,   "wait": 7,  "rare": 0.75},
    "legendary_rod":  {"name": "⭐ Legendary Rod",    "price": 10000000,  "wait": 5,  "rare": 0.90},
}

MINING_TOOLS = {
    "stone_pickaxe":     {"name": "🪨 Stone Pickaxe",      "price": 0,        "wait": 30, "rare": 0.05},
    "iron_pickaxe":      {"name": "⚙️ Iron Pickaxe",       "price": 5000,     "wait": 25, "rare": 0.10},
    "silver_pickaxe":    {"name": "🥈 Silver Pickaxe",     "price": 25000,    "wait": 20, "rare": 0.20},
    "gold_pickaxe":      {"name": "🥇 Gold Pickaxe",       "price": 100000,   "wait": 15, "rare": 0.35},
    "diamond_pickaxe":   {"name": "💎 Diamond Pickaxe",    "price": 500000,   "wait": 10, "rare": 0.55},
    "enchanted_pickaxe": {"name": "🔮 Enchanted Pickaxe",  "price": 2000000,  "wait": 7,  "rare": 0.75},
    "legendary_pickaxe": {"name": "⭐ Legendary Pickaxe",  "price": 10000000, "wait": 5,  "rare": 0.90},
}

FARMING_TOOLS = {
    "bare_hands":        {"name": "🤲 Bare Hands",        "price": 0,        "wait": 30, "bonus": 0.0},
    "basic_hoe":         {"name": "🪚 Basic Hoe",         "price": 5000,     "wait": 25, "bonus": 0.10},
    "silver_hoe":        {"name": "🥈 Silver Hoe",        "price": 25000,    "wait": 20, "bonus": 0.25},
    "golden_hoe":        {"name": "🥇 Golden Hoe",        "price": 100000,   "wait": 15, "bonus": 0.50},
    "diamond_hoe":       {"name": "💎 Diamond Hoe",       "price": 500000,   "wait": 10, "bonus": 0.75},
    "magic_tractor":     {"name": "🚜 Magic Tractor",     "price": 2000000,  "wait": 7,  "bonus": 1.00},
    "legendary_tractor": {"name": "⭐ Legendary Tractor", "price": 10000000, "wait": 5,  "bonus": 2.00},
}

ALL_TOOLS = {**FISHING_TOOLS, **MINING_TOOLS, **FARMING_TOOLS}

# ── Catch/Find Tables ─────────────────────────────────────────────────

COMMON_FISH  = [("🐟 Common Fish", 200), ("🐠 Tropical Fish", 500), ("🦐 Shrimp", 800)]
RARE_FISH    = [("🦑 Squid", 1500), ("🦈 Shark", 5000), ("🐋 Whale", 15000)]
EPIC_FISH    = [("👻 Ghost Fish", 50000), ("💎 Diamond Fish", 200000)]

COMMON_ORES  = [("🪨 Stone", 100), ("🔩 Iron", 500)]
RARE_ORES    = [("🥇 Gold", 2000), ("💎 Diamond", 10000)]
EPIC_ORES    = [("🔮 Magic Crystal", 50000), ("⭐ Star Fragment", 200000)]

COMMON_CROPS = [("🌾 Wheat", 500), ("🥕 Carrot", 1200)]
RARE_CROPS   = [("🍅 Tomato", 2500), ("🌽 Corn", 4000)]
EPIC_CROPS   = [("🍓 Strawberry", 8000), ("🌹 Rose", 20000)]

def pick_catch(rare_chance, common, rare, epic):
    roll = random.random()
    if roll < rare_chance * 0.3:
        return random.choice(epic)
    elif roll < rare_chance:
        return random.choice(rare)
    else:
        return random.choice(common)

# ── Cooldown Helper ───────────────────────────────────────────────────

def check_activity_cooldown(user_id, field, wait_minutes):
    p = db.get_player(user_id)
    if not p:
        return False, "Not registered.", 0
    last = p.get(field) if isinstance(p, dict) else None
    if last:
        last_dt   = datetime.fromisoformat(last)
        next_dt   = last_dt + timedelta(minutes=wait_minutes)
        remaining = next_dt - datetime.now()
        if remaining.total_seconds() > 0:
            mins = int(remaining.total_seconds() // 60)
            secs = int(remaining.total_seconds() % 60)
            if mins > 0:
                return False, f"⏰ Wait *{mins}m {secs}s* before doing this again.", 0
            return False, f"⏰ Wait *{secs}s* before doing this again.", 0
    return True, "", wait_minutes

def set_activity_time(user_id, field):
    db.execute(f"UPDATE players SET {field}=? WHERE user_id=?",
               (datetime.now().isoformat()[:19], user_id))

def get_equipped(user_id, tool_type):
    """Returns equipped tool key for this type"""
    row = db.execute("SELECT * FROM player_tools WHERE user_id=?", (user_id,), fetch="one")
    defaults = {"fishing": "wooden_rod", "mining": "stone_pickaxe", "farming": "bare_hands"}
    if not row:
        return defaults.get(tool_type, "wooden_rod")
    return row.get(f"{tool_type}_tool") or defaults.get(tool_type, "wooden_rod")
def get_owned_tools(user_id):
    import json
    row = db.execute("SELECT * FROM player_tools WHERE user_id=?", (user_id,), fetch="one")
    defaults = ["wooden_rod", "stone_pickaxe", "bare_hands"]
    if not row:
        return defaults
    owned = json.loads(row["owned_tools"]) if row.get("owned_tools") else []
    return list(set(owned + defaults))

def save_tool_purchase(user_id, tool_key, tool_type):
    import json
    row = db.execute("SELECT * FROM player_tools WHERE user_id=?", (user_id,), fetch="one")
    if row:
        owned = json.loads(row["owned_tools"]) if row.get("owned_tools") else []
        owned.append(tool_key)
        db.execute("UPDATE player_tools SET owned_tools=? WHERE user_id=?",
                   (json.dumps(owned), user_id))
    else:
        owned = ["wooden_rod", "stone_pickaxe", "bare_hands", tool_key]
        db.execute("""INSERT INTO player_tools (user_id, fishing_tool, mining_tool, farming_tool, owned_tools)
                      VALUES (?, 'wooden_rod', 'stone_pickaxe', 'bare_hands', ?)
                      ON CONFLICT (user_id) DO NOTHING""",
                   (user_id, json.dumps(owned)))

def equip_tool_db(user_id, tool_key, tool_type):
    row = db.execute("SELECT user_id FROM player_tools WHERE user_id=?", (user_id,), fetch="one")
    if row:
        db.execute(f"UPDATE player_tools SET {tool_type}_tool=? WHERE user_id=?", (tool_key, user_id))
    else:
        defaults = {"fishing": "wooden_rod", "mining": "stone_pickaxe", "farming": "bare_hands"}
        defaults[tool_type] = tool_key
        db.execute("""INSERT INTO player_tools (user_id, fishing_tool, mining_tool, farming_tool, owned_tools)
                      VALUES (?, ?, ?, ?, ?)
                      ON CONFLICT (user_id) DO NOTHING""",
                   (user_id, defaults["fishing"], defaults["mining"], defaults["farming"],
                    '["wooden_rod","stone_pickaxe","bare_hands"]'))

# ── Fishing ───────────────────────────────────────────────────────────

def cmd_fish(message):
    p = db.get_player(message.from_user.id)
    if not p:
        _bot.reply_to(message, "❗ Register first with /start"); return

    tool_key  = get_equipped(message.from_user.id, "fishing")
    tool      = FISHING_TOOLS.get(tool_key, FISHING_TOOLS["wooden_rod"])
    wait_mins = tool["wait"]

    ok, msg, _ = check_activity_cooldown(message.from_user.id, "last_fish", wait_mins)
    if not ok:
        _bot.reply_to(message,
            f"🎣 Already fishing!\n{msg}\n\n"
            f"Equipped: {tool['name']}\n"
            f"Use /collect when ready!"); return

    set_activity_time(message.from_user.id, "last_fish")
    _bot.reply_to(message,
        f"🎣 *Cast your rod!*\n\n"
        f"Rod: {tool['name']}\n"
        f"⏰ Come back in *{wait_mins} minutes*\n"
        f"Then use /collect fish")

def cmd_mine(message):
    p = db.get_player(message.from_user.id)
    if not p:
        _bot.reply_to(message, "❗ Register first with /start"); return

    tool_key  = get_equipped(message.from_user.id, "mining")
    tool      = MINING_TOOLS.get(tool_key, MINING_TOOLS["stone_pickaxe"])
    wait_mins = tool["wait"]

    ok, msg, _ = check_activity_cooldown(message.from_user.id, "last_mine", wait_mins)
    if not ok:
        _bot.reply_to(message,
            f"⛏️ Already mining!\n{msg}\n\n"
            f"Equipped: {tool['name']}\n"
            f"Use /collect when ready!"); return

    set_activity_time(message.from_user.id, "last_mine")
    _bot.reply_to(message,
        f"⛏️ *Started Mining!*\n\n"
        f"Pickaxe: {tool['name']}\n"
        f"⏰ Come back in *{wait_mins} minutes*\n"
        f"Then use /collect mine")

def cmd_farm(message):
    p = db.get_player(message.from_user.id)
    if not p:
        _bot.reply_to(message, "❗ Register first with /start"); return

    tool_key  = get_equipped(message.from_user.id, "farming")
    tool      = FARMING_TOOLS.get(tool_key, FARMING_TOOLS["bare_hands"])
    wait_mins = tool["wait"]

    ok, msg, _ = check_activity_cooldown(message.from_user.id, "last_farm", wait_mins)
    if not ok:
        _bot.reply_to(message,
            f"🌾 Already farming!\n{msg}\n\n"
            f"Equipped: {tool['name']}\n"
            f"Use /collect when ready!"); return

    set_activity_time(message.from_user.id, "last_farm")
    _bot.reply_to(message,
        f"🌾 *Started Farming!*\n\n"
        f"Tool: {tool['name']}\n"
        f"⏰ Come back in *{wait_mins} minutes*\n"
        f"Then use /collect farm")

def cmd_collect(message):
    p = db.get_player(message.from_user.id)
    if not p:
        _bot.reply_to(message, "❗ Register first with /start"); return

    args = message.text.split()
    if len(args) < 2:
        _bot.reply_to(message,
            "Usage:\n"
            "`/collect fish` — collect fishing catch\n"
            "`/collect mine` — collect mined ores\n"
            "`/collect farm` — collect farmed crops"); return

    activity = args[1].lower()
    uid = message.from_user.id

    if activity == "fish":
        tool_key = get_equipped(uid, "fishing")
        tool     = FISHING_TOOLS.get(tool_key, FISHING_TOOLS["wooden_rod"])
        field    = "last_fish"
        catches  = (COMMON_FISH, RARE_FISH, EPIC_FISH)
        emoji    = "🎣"
        label    = "caught"
    elif activity == "mine":
        tool_key = get_equipped(uid, "mining")
        tool     = MINING_TOOLS.get(tool_key, MINING_TOOLS["stone_pickaxe"])
        field    = "last_mine"
        catches  = (COMMON_ORES, RARE_ORES, EPIC_ORES)
        emoji    = "⛏️"
        label    = "found"
    elif activity == "farm":
        tool_key = get_equipped(uid, "farming")
        tool     = FARMING_TOOLS.get(tool_key, FARMING_TOOLS["bare_hands"])
        field    = "last_farm"
        catches  = (COMMON_CROPS, RARE_CROPS, EPIC_CROPS)
        emoji    = "🌾"
        label    = "harvested"
    else:
        _bot.reply_to(message, "❌ Use: `/collect fish`, `/collect mine`, or `/collect farm`"); return

    # Check if activity was started
    row = db.execute(f"SELECT {field} FROM players WHERE user_id=?", (uid,), fetch="one")

    if not row or not row.get(field):
        _bot.reply_to(message, f"❌ You haven't started {activity}ing yet!\nUse /{activity} first."); return

    last_dt   = datetime.fromisoformat(str(row[field])[:19])
    next_dt   = last_dt + timedelta(minutes=tool["wait"])
    remaining = next_dt - datetime.now()

    if remaining.total_seconds() > 0:
        mins = int(remaining.total_seconds() // 60)
        secs = int(remaining.total_seconds() % 60)
        _bot.reply_to(message,
            f"{emoji} Not ready yet!\n"
            f"⏰ Wait *{mins}m {secs}s* more\n"
            f"Then /collect {activity}"); return

    # Collect!
    rare_chance = tool.get("rare", 0.05)
    bonus       = tool.get("bonus", 0.0)
    item_name, base_chips = pick_catch(rare_chance, *catches)
    chips = int(base_chips * (1 + bonus))

    # Reset activity
    db.execute(f"UPDATE players SET {field}=NULL WHERE user_id=?", (uid,))

    db.update_chips(uid, chips)
    new_bal = db.get_player(uid)["chips"]

    _bot.reply_to(message,
        f"{emoji} *Collected!*\n\n"
        f"You {label}: *{item_name}*\n"
        f"💰 Earned: *{fmt(chips)}* chips\n\n"
        f"Balance: *{fmt(new_bal)}*\n\n"
        f"Use /{activity} to start again!")

# ── Shop ──────────────────────────────────────────────────────────────

def cmd_shop(message):
    args = message.text.split()
    category = args[1].lower() if len(args) > 1 else "all"

    if category in ("fish", "fishing", "rod"):
        lines = ["🎣 *Fishing Rods Shop*\n"]
        for key, t in FISHING_TOOLS.items():
            price = "FREE" if t["price"] == 0 else fmt(t["price"])
            lines.append(f"{t['name']} — *{price}* chips\n"
                        f"  ⏰ Wait: {t['wait']}min | 🎯 Rare: {int(t['rare']*100)}%\n"
                        f"  `/buy {key}`\n")

    elif category in ("mine", "mining", "pickaxe"):
        lines = ["⛏️ *Pickaxes Shop*\n"]
        for key, t in MINING_TOOLS.items():
            price = "FREE" if t["price"] == 0 else fmt(t["price"])
            lines.append(f"{t['name']} — *{price}* chips\n"
                        f"  ⏰ Wait: {t['wait']}min | 🎯 Rare: {int(t['rare']*100)}%\n"
                        f"  `/buy {key}`\n")

    elif category in ("farm", "farming", "hoe"):
        lines = ["🌾 *Farming Tools Shop*\n"]
        for key, t in FARMING_TOOLS.items():
            price = "FREE" if t["price"] == 0 else fmt(t["price"])
            lines.append(f"{t['name']} — *{price}* chips\n"
                        f"  ⏰ Wait: {t['wait']}min | 🎁 Bonus: +{int(t['bonus']*100)}%\n"
                        f"  `/buy {key}`\n")

    else:
        lines = [
            "🏪 *Shop Categories*\n\n"
            "🎣 `/shop fishing` — Fishing rods\n"
            "⛏️ `/shop mining` — Pickaxes\n"
            "🌾 `/shop farming` — Farming tools\n\n"
            "Buy with `/buy [item_name]`\n"
            "Equip with `/equip [item_name]`\n"
            "View owned with `/inventory`"
        ]

    _bot.reply_to(message, "\n".join(lines))

def cmd_buy(message):
    p = db.get_player(message.from_user.id)
    if not p:
        _bot.reply_to(message, "❗ Register first with /start"); return

    args = message.text.split()
    if len(args) < 2:
        _bot.reply_to(message, "Usage: `/buy [item_name]`\nExample: `/buy golden_rod`"); return

    item_key = args[1].lower()
    if item_key not in ALL_TOOLS:
        _bot.reply_to(message, f"❌ Item `{item_key}` not found!\nCheck /shop for available items."); return

    tool  = ALL_TOOLS[item_key]
    owned = get_owned_tools(message.from_user.id)

    if item_key in owned:
        _bot.reply_to(message, f"✅ You already own *{tool['name']}*!\nUse `/equip {item_key}` to equip it."); return

    price = tool["price"]
    if price == 0:
        _bot.reply_to(message, f"✅ *{tool['name']}* is free! Use `/equip {item_key}` to equip it."); return

    if p["chips"] < price:
        _bot.reply_to(message, f"❌ Not enough chips!\nNeed: *{fmt(price)}* | Have: *{fmt(p['chips'])}*"); return

    # Determine tool type
    if item_key in FISHING_TOOLS:
        tool_type = "fishing"
    elif item_key in MINING_TOOLS:
        tool_type = "mining"
    else:
        tool_type = "farming"

    db.update_chips(message.from_user.id, -price)
    save_tool_purchase(message.from_user.id, item_key, tool_type)
    new_bal = db.get_player(message.from_user.id)["chips"]

    _bot.reply_to(message,
        f"✅ *Purchased {tool['name']}!*\n"
        f"💰 Paid: *{fmt(price)}* chips\n"
        f"Balance: *{fmt(new_bal)}*\n\n"
        f"Use `/equip {item_key}` to equip it!")

def cmd_equip(message):
    p = db.get_player(message.from_user.id)
    if not p:
        _bot.reply_to(message, "❗ Register first with /start"); return

    args = message.text.split()
    if len(args) < 2:
        _bot.reply_to(message, "Usage: `/equip [item_name]`\nExample: `/equip golden_rod`"); return

    item_key = args[1].lower()
    if item_key not in ALL_TOOLS:
        _bot.reply_to(message, f"❌ Item `{item_key}` not found!"); return

    owned = get_owned_tools(message.from_user.id)
    if item_key not in owned and ALL_TOOLS[item_key]["price"] > 0:
        _bot.reply_to(message, f"❌ You don't own this item!\nBuy it with `/buy {item_key}`"); return

    if item_key in FISHING_TOOLS:
        tool_type = "fishing"
    elif item_key in MINING_TOOLS:
        tool_type = "mining"
    else:
        tool_type = "farming"

    equip_tool_db(message.from_user.id, item_key, tool_type)
    tool = ALL_TOOLS[item_key]
    _bot.reply_to(message,
        f"✅ Equipped *{tool['name']}*!\n"
        f"⏰ Wait time: *{tool['wait']} minutes*")

def cmd_inventory(message):
    uid   = message.from_user.id
    owned = get_owned_tools(uid)

    fish_eq  = get_equipped(uid, "fishing")
    mine_eq  = get_equipped(uid, "mining")
    farm_eq  = get_equipped(uid, "farming")

    lines = ["🎒 *Your Inventory*\n"]

    lines.append("🎣 *Fishing Rods:*")
    for key in owned:
        if key in FISHING_TOOLS:
            eq = " ← equipped" if key == fish_eq else ""
            lines.append(f"  {FISHING_TOOLS[key]['name']}{eq}")

    lines.append("\n⛏️ *Pickaxes:*")
    for key in owned:
        if key in MINING_TOOLS:
            eq = " ← equipped" if key == mine_eq else ""
            lines.append(f"  {MINING_TOOLS[key]['name']}{eq}")

    lines.append("\n🌾 *Farming Tools:*")
    for key in owned:
        if key in FARMING_TOOLS:
            eq = " ← equipped" if key == farm_eq else ""
            lines.append(f"  {FARMING_TOOLS[key]['name']}{eq}")

    _bot.reply_to(message, "\n".join(lines))

# ── Rbet ─────────────────────────────────────────────────────────────

active_rbets = {}

def cmd_rbet(message):
    p = db.get_player(message.from_user.id)
    if not p:
        _bot.reply_to(message, "❗ Register first with /start"); return

    uid = message.from_user.id

    # If already in a game — continue
    if uid in active_rbets:
        game = active_rbets[uid]
        prize = game["prize"]
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton(f"🎲 Risk It! (80% win)", callback_data=f"rbet_risk_{uid}"),
            types.InlineKeyboardButton(f"💰 Take {fmt(prize)} chips", callback_data=f"rbet_take_{uid}")
        )
        _bot.reply_to(message,
            f"🎲 *Rbet Active!*\n\n"
            f"Current Prize: *{fmt(prize)}* chips\n"
            f"Rounds survived: *{game['rounds']}*\n\n"
            f"🌻 80% → prize increases\n"
            f"🐍 20% → lose everything!",
            reply_markup=markup)
        return

    args = message.text.split()
    if len(args) < 2:
        _bot.reply_to(message,
            "🎲 *Risk Bet (Rbet)*\n\n"
            "Usage: `/rbet [amount]`\n"
            "Example: `/rbet 10000`\n\n"
            "🌻 80% chance → prize grows\n"
            "🐍 20% chance → lose everything!\n"
            "💰 `/rtake` anytime to cash out safely"); return

    try:
        bet = int(args[1].replace(",", ""))
    except:
        _bot.reply_to(message, "❌ Invalid amount."); return

    min_bet = max(1, int(p["chips"] * 0.15))
    if bet < min_bet:
        _bot.reply_to(message, f"❌ Minimum bet: *{fmt(min_bet)}* chips (15% of balance)"); return
    if p["chips"] < bet:
        _bot.reply_to(message, f"❌ Not enough chips! Balance: *{fmt(p['chips'])}*"); return

    db.update_chips(uid, -bet)
    active_rbets[uid] = {"prize": bet, "rounds": 0, "chat_id": message.chat.id}

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("🎲 Risk It!", callback_data=f"rbet_risk_{uid}"),
        types.InlineKeyboardButton(f"💰 Take {fmt(bet)} chips", callback_data=f"rbet_take_{uid}")
    )
    _bot.reply_to(message,
        f"🎲 *Rbet Started!* Prize: *{fmt(bet)}* chips\n\n"
        f"⚠️ Each round:\n"
        f"🌻 80% → prize increases\n"
        f"🐍 20% → you lose everything!\n\n"
        f"/rbet → risk more | /rtake → cash out",
        reply_markup=markup)

def cb_rbet(call):
    parts  = call.data.split("_")
    action = parts[1]
    uid    = int(parts[2])

    if call.from_user.id != uid:
        _bot.answer_callback_query(call.id, "This isn't your game!"); return

    if uid not in active_rbets:
        _bot.answer_callback_query(call.id, "No active rbet found!")
        _bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
        return

    game = active_rbets[uid]

    if action == "take":
        prize = game.pop
        prize = active_rbets.pop(uid)["prize"]
        db.update_chips(uid, prize)
        new_bal = db.get_player(uid)["chips"]
        _bot.edit_message_text(
            f"💰 *Cashed Out!*\n\n"
            f"You took: *{fmt(prize)}* chips\n"
            f"Rounds survived: *{game['rounds']}*\n"
            f"Balance: *{fmt(new_bal)}*\n\n"
            f"Smart move! 😎",
            call.message.chat.id, call.message.message_id, parse_mode="Markdown")
        return

    # Risk it!
    if random.random() < 0.80:
        # Win — prize grows
        multiplier   = round(random.uniform(1.1, 1.5), 2)
        new_prize    = int(game["prize"] * multiplier)
        game["prize"]  = new_prize
        game["rounds"] += 1
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("🎲 Risk Again!", callback_data=f"rbet_risk_{uid}"),
            types.InlineKeyboardButton(f"💰 Take {fmt(new_prize)}", callback_data=f"rbet_take_{uid}")
        )
        _bot.edit_message_text(
            f"🌻 *Survived! x{multiplier}*\n\n"
            f"Prize: *{fmt(new_prize)}* chips\n"
            f"Rounds: *{game['rounds']}*\n\n"
            f"Keep going or cash out?",
            call.message.chat.id, call.message.message_id,
            reply_markup=markup, parse_mode="Markdown")
    else:
        # Snake! Lose everything
        lost = active_rbets.pop(uid)["prize"]
        _bot.edit_message_text(
            f"🐍 *SNAKE! You lost everything!*\n\n"
            f"Lost: *{fmt(lost)}* chips 💀\n"
            f"Rounds survived: *{game['rounds']}*\n\n"
            f"Should've cashed out bhai 😭",
            call.message.chat.id, call.message.message_id, parse_mode="Markdown")

def cmd_rtake(message):
    uid = message.from_user.id
    if uid not in active_rbets:
        _bot.reply_to(message, "❌ No active rbet! Start one with `/rbet [amount]`"); return
    game  = active_rbets.pop(uid)
    prize = game["prize"]
    db.update_chips(uid, prize)
    new_bal = db.get_player(uid)["chips"]
    _bot.reply_to(message,
        f"💰 *Cashed Out!*\n\n"
        f"Took: *{fmt(prize)}* chips\n"
        f"Rounds survived: *{game['rounds']}*\n"
        f"Balance: *{fmt(new_bal)}*\n\n"
        f"Smart move! 😎")
