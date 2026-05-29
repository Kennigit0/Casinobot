"""activities.py — Fishing, Mining, Farming, Shop, Inventory, Rbet"""
import random
from datetime import datetime, timedelta
from telebot import types
import database as db
from config import Config

_bot = None

def register_activities(bot_instance):
    global _bot
    _bot = bot_instance
    for cmd, fn in [
        (["fish"],              cmd_fish),
        (["mine"],              cmd_mine),
        (["farm"],              cmd_farm),
        (["shop"],              cmd_shop),
        (["buy"],               cmd_buy),
        (["equip"],             cmd_equip),
        (["inventory","inv"],   cmd_inventory),
    ]:
        bot_instance.register_message_handler(fn, commands=cmd)

def fmt(n): return f"{n:,}"

# ── Catch tables ──────────────────────────────────────────────────────
COMMON_FISH  = [("🐟 Common Fish",200),("🐠 Tropical Fish",500),("🦐 Shrimp",800)]
RARE_FISH    = [("🦑 Squid",1500),("🦈 Shark",5000),("🐋 Whale",15000)]
EPIC_FISH    = [("👻 Ghost Fish",50000),("💎 Diamond Fish",200000)]
COMMON_ORES  = [("🪨 Stone",100),("🔩 Iron",500)]
RARE_ORES    = [("🥇 Gold",2000),("💎 Diamond",10000)]
EPIC_ORES    = [("🔮 Magic Crystal",50000),("⭐ Star Fragment",200000)]
COMMON_CROPS = [("🌾 Wheat",500),("🥕 Carrot",1200)]
RARE_CROPS   = [("🍅 Tomato",2500),("🌽 Corn",4000)]
EPIC_CROPS   = [("🍓 Strawberry",8000),("🌹 Rose",20000)]

def pick_catch(rare_chance, common, rare, epic):
    roll = random.random()
    if roll < rare_chance * 0.3:   return random.choice(epic)
    elif roll < rare_chance:        return random.choice(rare)
    else:                           return random.choice(common)

def check_cooldown(user_id, field, wait_minutes):
    p = db.get_player(user_id)
    if not p: return False, "Not registered."
    last = p.get(field)
    if last:
        last_dt   = datetime.fromisoformat(str(last)[:19])
        next_dt   = last_dt + timedelta(minutes=wait_minutes)
        remaining = next_dt - datetime.now()
        if remaining.total_seconds() > 0:
            mins = int(remaining.total_seconds() // 60)
            secs = int(remaining.total_seconds() % 60)
            if mins > 0: return False, f"Wait *{mins}m {secs}s* before doing this again."
            return False, f"Wait *{secs}s* before doing this again."
    return True, ""

# ── Fishing ───────────────────────────────────────────────────────────
def cmd_fish(message):
    p = db.get_player(message.from_user.id)
    if not p: _bot.reply_to(message, "❗ Register first with /start"); return

    # Level check
    level = db.xp_to_level(p.get("xp") or 0)
    if level < 5:
        _bot.reply_to(message,
            f"🔒 *Fishing locked!*\n\nYou need *Level 5* to fish.\n"
            f"Your level: *{level}*\n\nPlay casino games to earn XP! 🎰"); return

    tool_key  = db.get_equipped(message.from_user.id, "fishing")
    tool      = Config.FISHING_TOOLS.get(tool_key, Config.FISHING_TOOLS["wooden_rod"])
    wait_mins = tool["wait"]

    ok, msg = check_cooldown(message.from_user.id, "last_fish", wait_mins)
    if not ok:
        _bot.reply_to(message, f"🎣 Already fished recently!\n{msg}"); return

    # Give 10 items immediately
    rare_chance = tool.get("rare", 0.05)
    bonus       = tool.get("bonus", 0.0)
    catches = []
    total   = 0
    for _ in range(10):
        item_name, base_chips = pick_catch(rare_chance, COMMON_FISH, RARE_FISH, EPIC_FISH)
        chips = int(base_chips * (1 + bonus))
        catches.append((item_name, chips))
        total += chips

    db.set_activity_time(message.from_user.id, "last_fish")
    import gems as gems_mod
    gems_mod.check_achievements(message.from_user.id, message.chat.id)
    db.execute("UPDATE players SET fish_count=COALESCE(fish_count,0)+1 WHERE user_id=?", (message.from_user.id,))
    db.update_chips(message.from_user.id, total)
    db.add_xp(message.from_user.id, Config.XP_FISH)
    new_bal = db.get_player(message.from_user.id)["chips"]

    lines = [f"🎣 *Fishing Results!* ({tool['name']})\n"]
    for item_name, chips in catches:
        lines.append(f"  {item_name} — {fmt(chips)} chips")
    lines.append(f"\n💰 Total: *{fmt(total)}* chips (+{Config.XP_FISH} XP)")
    lines.append(f"Balance: *{fmt(new_bal)}*")
    lines.append(f"⏰ Fish again in *{wait_mins} minutes*")
    _bot.reply_to(message, "\n".join(lines))

# ── Mining ────────────────────────────────────────────────────────────
def cmd_mine(message):
    p = db.get_player(message.from_user.id)
    if not p: _bot.reply_to(message, "❗ Register first with /start"); return

    level = db.xp_to_level(p.get("xp") or 0)
    if level < 10:
        _bot.reply_to(message,
            f"🔒 *Mining locked!*\n\nYou need *Level 10* to mine.\n"
            f"Your level: *{level}*\n\nPlay games to earn XP! 🎰"); return

    tool_key  = db.get_equipped(message.from_user.id, "mining")
    tool      = Config.MINING_TOOLS.get(tool_key, Config.MINING_TOOLS["stone_pickaxe"])
    wait_mins = tool["wait"]

    ok, msg = check_cooldown(message.from_user.id, "last_mine", wait_mins)
    if not ok:
        _bot.reply_to(message, f"⛏️ Already mined recently!\n{msg}"); return

    rare_chance = tool.get("rare", 0.05)
    bonus       = tool.get("bonus", 0.0)
    finds = []
    total = 0
    for _ in range(10):
        item_name, base_chips = pick_catch(rare_chance, COMMON_ORES, RARE_ORES, EPIC_ORES)
        chips = int(base_chips * (1 + bonus))
        finds.append((item_name, chips))
        total += chips

    db.set_activity_time(message.from_user.id, "last_mine")
    import gems as gems_mod
    gems_mod.check_achievements(message.from_user.id, message.chat.id)
    db.execute("UPDATE players SET mine_count=COALESCE(mine_count,0)+1 WHERE user_id=?", (message.from_user.id,))
    db.update_chips(message.from_user.id, total)
    db.add_xp(message.from_user.id, Config.XP_MINE)
    new_bal = db.get_player(message.from_user.id)["chips"]

    lines = [f"⛏️ *Mining Results!* ({tool['name']})\n"]
    for item_name, chips in finds:
        lines.append(f"  {item_name} — {fmt(chips)} chips")
    lines.append(f"\n💰 Total: *{fmt(total)}* chips (+{Config.XP_MINE} XP)")
    lines.append(f"Balance: *{fmt(new_bal)}*")
    lines.append(f"⏰ Mine again in *{wait_mins} minutes*")
    _bot.reply_to(message, "\n".join(lines))

# ── Farming ───────────────────────────────────────────────────────────
def cmd_farm(message):
    p = db.get_player(message.from_user.id)
    if not p: _bot.reply_to(message, "❗ Register first with /start"); return

    level = db.xp_to_level(p.get("xp") or 0)
    if level < 15:
        _bot.reply_to(message,
            f"🔒 *Farming locked!*\n\nYou need *Level 15* to farm.\n"
            f"Your level: *{level}*\n\nPlay games to earn XP! 🎰"); return

    tool_key  = db.get_equipped(message.from_user.id, "farming")
    tool      = Config.FARMING_TOOLS.get(tool_key, Config.FARMING_TOOLS["bare_hands"])
    wait_mins = tool["wait"]

    ok, msg = check_cooldown(message.from_user.id, "last_farm", wait_mins)
    if not ok:
        _bot.reply_to(message, f"🌾 Already farmed recently!\n{msg}"); return

    rare_chance = tool.get("rare", 0.05) if "rare" in tool else 0.05
    bonus       = tool.get("bonus", 0.0)
    harvests    = []
    total       = 0
    for _ in range(10):
        item_name, base_chips = pick_catch(rare_chance if rare_chance else 0.05, COMMON_CROPS, RARE_CROPS, EPIC_CROPS)
        chips = int(base_chips * (1 + bonus))
        harvests.append((item_name, chips))
        total += chips

    db.set_activity_time(message.from_user.id, "last_farm")
    import gems as gems_mod
    gems_mod.check_achievements(message.from_user.id, message.chat.id)
    db.execute("UPDATE players SET farm_count=COALESCE(farm_count,0)+1 WHERE user_id=?", (message.from_user.id,))
    db.update_chips(message.from_user.id, total)
    db.add_xp(message.from_user.id, Config.XP_FARM)
    new_bal = db.get_player(message.from_user.id)["chips"]

    lines = [f"🌾 *Farming Results!* ({tool['name']})\n"]
    for item_name, chips in harvests:
        lines.append(f"  {item_name} — {fmt(chips)} chips")
    lines.append(f"\n💰 Total: *{fmt(total)}* chips (+{Config.XP_FARM} XP)")
    lines.append(f"Balance: *{fmt(new_bal)}*")
    lines.append(f"⏰ Farm again in *{wait_mins} minutes*")
    _bot.reply_to(message, "\n".join(lines))

# ── Shop ──────────────────────────────────────────────────────────────
def cmd_shop(message):
    args     = message.text.split()
    category = args[1].lower() if len(args) > 1 else "all"

    if category in ("fish","fishing","rod"):
        lines = ["🎣 *Fishing Rods Shop*\n"]
        for key, t in Config.FISHING_TOOLS.items():
            price = "FREE" if t["price"] == 0 else fmt(t["price"])
            lines.append(f"{t['name']}\n  💰 {price} chips | ⏰ {t['wait']}min | 🔒 Lv.{t['level']} | 🎯 {int(t['rare']*100)}% rare\n  `/buy {key}`\n")
    elif category in ("mine","mining","pickaxe"):
        lines = ["⛏️ *Pickaxes Shop*\n"]
        for key, t in Config.MINING_TOOLS.items():
            price = "FREE" if t["price"] == 0 else fmt(t["price"])
            lines.append(f"{t['name']}\n  💰 {price} chips | ⏰ {t['wait']}min | 🔒 Lv.{t['level']} | 🎯 {int(t['rare']*100)}% rare\n  `/buy {key}`\n")
    elif category in ("farm","farming","hoe"):
        lines = ["🌾 *Farming Tools Shop*\n"]
        for key, t in Config.FARMING_TOOLS.items():
            price = "FREE" if t["price"] == 0 else fmt(t["price"])
            lines.append(f"{t['name']}\n  💰 {price} chips | ⏰ {t['wait']}min | 🔒 Lv.{t['level']} | 🎁 +{int(t['bonus']*100)}%\n  `/buy {key}`\n")
    else:
        lines = ["🏪 *Shop Categories*\n\n"
                 "🎣 `/shop fishing` — Fishing rods\n"
                 "⛏️ `/shop mining` — Pickaxes\n"
                 "🌾 `/shop farming` — Farming tools\n\n"
                 "Buy: `/buy [item]` | Equip: `/equip [item]`\nView owned: `/inventory`"]
    _bot.reply_to(message, "\n".join(lines))

def cmd_buy(message):
    p = db.get_player(message.from_user.id)
    if not p: _bot.reply_to(message, "❗ Register first"); return
    args = message.text.split()
    if len(args) < 2: _bot.reply_to(message, "Usage: `/buy [item_name]`\nCheck /shop"); return
    item_key = args[1].lower()
    if item_key not in Config.ALL_TOOLS:
        _bot.reply_to(message, f"❌ Item `{item_key}` not found!\nCheck /shop"); return

    tool  = Config.ALL_TOOLS[item_key]
    owned = db.get_owned_tools(message.from_user.id)

    if item_key in owned:
        _bot.reply_to(message, f"✅ You already own *{tool['name']}*!\nUse `/equip {item_key}` to equip it."); return

    # Level check
    player_level = db.xp_to_level(p.get("xp") or 0)
    required_level = tool.get("level", 0)
    if player_level < required_level:
        _bot.reply_to(message,
            f"🔒 Need *Level {required_level}* to buy *{tool['name']}*!\n"
            f"Your level: *{player_level}*"); return

    price = tool["price"]
    if price == 0:
        db.save_tool_purchase(message.from_user.id, item_key)
        _bot.reply_to(message, f"✅ *{tool['name']}* is free! Use `/equip {item_key}` to equip it."); return

    if p["chips"] < price:
        _bot.reply_to(message, f"❌ Not enough chips!\nNeed: *{fmt(price)}* | Have: *{fmt(p['chips'])}*"); return

    if item_key in Config.FISHING_TOOLS: tool_type = "fishing"
    elif item_key in Config.MINING_TOOLS: tool_type = "mining"
    else: tool_type = "farming"

    db.update_chips(message.from_user.id, -price)
    db.save_tool_purchase(message.from_user.id, item_key)
    new_bal = db.get_player(message.from_user.id)["chips"]
    _bot.reply_to(message,
        f"✅ *Purchased {tool['name']}!*\n💰 Paid: *{fmt(price)}* chips\n"
        f"Balance: *{fmt(new_bal)}*\n\nUse `/equip {item_key}` to equip it!")

def cmd_equip(message):
    p = db.get_player(message.from_user.id)
    if not p: _bot.reply_to(message, "❗ Register first"); return
    args = message.text.split()
    if len(args) < 2: _bot.reply_to(message, "Usage: `/equip [item_name]`"); return
    item_key = args[1].lower()
    if item_key not in Config.ALL_TOOLS:
        _bot.reply_to(message, f"❌ Item `{item_key}` not found!"); return
    owned = db.get_owned_tools(message.from_user.id)
    if item_key not in owned and Config.ALL_TOOLS[item_key]["price"] > 0:
        _bot.reply_to(message, f"❌ You don't own this! Buy with `/buy {item_key}`"); return

    if item_key in Config.FISHING_TOOLS: tool_type = "fishing"
    elif item_key in Config.MINING_TOOLS: tool_type = "mining"
    else: tool_type = "farming"

    db.equip_tool_db(message.from_user.id, item_key, tool_type)
    tool = Config.ALL_TOOLS[item_key]
    _bot.reply_to(message, f"✅ Equipped *{tool['name']}*!\n⏰ Wait time: *{tool['wait']} minutes*")

def cmd_inventory(message):
    uid      = message.from_user.id
    owned    = db.get_owned_tools(uid)
    fish_eq  = db.get_equipped(uid, "fishing")
    mine_eq  = db.get_equipped(uid, "mining")
    farm_eq  = db.get_equipped(uid, "farming")
    lines    = ["🎒 *Your Inventory*\n"]
    lines.append("🎣 *Fishing Rods:*")
    for key in owned:
        if key in Config.FISHING_TOOLS:
            eq = " ◀ equipped" if key == fish_eq else ""
            lines.append(f"  {Config.FISHING_TOOLS[key]['name']}{eq}")
    lines.append("\n⛏️ *Pickaxes:*")
    for key in owned:
        if key in Config.MINING_TOOLS:
            eq = " ◀ equipped" if key == mine_eq else ""
            lines.append(f"  {Config.MINING_TOOLS[key]['name']}{eq}")
    lines.append("\n🌾 *Farming Tools:*")
    for key in owned:
        if key in Config.FARMING_TOOLS:
            eq = " ◀ equipped" if key == farm_eq else ""
            lines.append(f"  {Config.FARMING_TOOLS[key]['name']}{eq}")
    _bot.reply_to(message, "\n".join(lines))

# ── Rbet ─────────────────────────────────────────────────────────────
""activities.py — Fishing, Mining, Farming, Shop, Inventory, Rbet"""
import random
from datetime import datetime, timedelta
from telebot import types
import database as db
from config import Config

_bot = None

def register_activities(bot_instance):
    global _bot
    _bot = bot_instance
    for cmd, fn in [
        (["fish"],              cmd_fish),
        (["mine"],              cmd_mine),
        (["farm"],              cmd_farm),
        (["shop"],              cmd_shop),
        (["buy"],               cmd_buy),
        (["equip"],             cmd_equip),
        (["inventory","inv"],   cmd_inventory),
    ]:
        bot_instance.register_message_handler(fn, commands=cmd)

def fmt(n): return f"{n:,}"

# ── Catch tables ──────────────────────────────────────────────────────
COMMON_FISH  = [("🐟 Common Fish",200),("🐠 Tropical Fish",500),("🦐 Shrimp",800)]
RARE_FISH    = [("🦑 Squid",1500),("🦈 Shark",5000),("🐋 Whale",15000)]
EPIC_FISH    = [("👻 Ghost Fish",50000),("💎 Diamond Fish",200000)]
COMMON_ORES  = [("🪨 Stone",100),("🔩 Iron",500)]
RARE_ORES    = [("🥇 Gold",2000),("💎 Diamond",10000)]
EPIC_ORES    = [("🔮 Magic Crystal",50000),("⭐ Star Fragment",200000)]
COMMON_CROPS = [("🌾 Wheat",500),("🥕 Carrot",1200)]
RARE_CROPS   = [("🍅 Tomato",2500),("🌽 Corn",4000)]
EPIC_CROPS   = [("🍓 Strawberry",8000),("🌹 Rose",20000)]

def pick_catch(rare_chance, common, rare, epic):
    roll = random.random()
    if roll < rare_chance * 0.3:   return random.choice(epic)
    elif roll < rare_chance:        return random.choice(rare)
    else:                           return random.choice(common)

def check_cooldown(user_id, field, wait_minutes):
    p = db.get_player(user_id)
    if not p: return False, "Not registered."
    last = p.get(field)
    if last:
        last_dt   = datetime.fromisoformat(str(last)[:19])
        next_dt   = last_dt + timedelta(minutes=wait_minutes)
        remaining = next_dt - datetime.now()
        if remaining.total_seconds() > 0:
            mins = int(remaining.total_seconds() // 60)
            secs = int(remaining.total_seconds() % 60)
            if mins > 0: return False, f"Wait *{mins}m {secs}s* before doing this again."
            return False, f"Wait *{secs}s* before doing this again."
    return True, ""

# ── Fishing ───────────────────────────────────────────────────────────
def cmd_fish(message):
    p = db.get_player(message.from_user.id)
    if not p: _bot.reply_to(message, "❗ Register first with /start"); return

    # Level check
    level = db.xp_to_level(p.get("xp") or 0)
    if level < 5:
        _bot.reply_to(message,
            f"🔒 *Fishing locked!*\n\nYou need *Level 5* to fish.\n"
            f"Your level: *{level}*\n\nPlay casino games to earn XP! 🎰"); return

    tool_key  = db.get_equipped(message.from_user.id, "fishing")
    tool      = Config.FISHING_TOOLS.get(tool_key, Config.FISHING_TOOLS["wooden_rod"])
    wait_mins = tool["wait"]

    ok, msg = check_cooldown(message.from_user.id, "last_fish", wait_mins)
    if not ok:
        _bot.reply_to(message, f"🎣 Already fished recently!\n{msg}"); return

    # Give 10 items immediately
    rare_chance = tool.get("rare", 0.05)
    bonus       = tool.get("bonus", 0.0)
    catches = []
    total   = 0
    for _ in range(10):
        item_name, base_chips = pick_catch(rare_chance, COMMON_FISH, RARE_FISH, EPIC_FISH)
        chips = int(base_chips * (1 + bonus))
        catches.append((item_name, chips))
        total += chips

    db.set_activity_time(message.from_user.id, "last_fish")
    import gems as gems_mod
    gems_mod.check_achievements(message.from_user.id, message.chat.id)
    db.execute("UPDATE players SET fish_count=COALESCE(fish_count,0)+1 WHERE user_id=?", (message.from_user.id,))
    db.update_chips(message.from_user.id, total)
    db.add_xp(message.from_user.id, Config.XP_FISH)
    new_bal = db.get_player(message.from_user.id)["chips"]

    lines = [f"🎣 *Fishing Results!* ({tool['name']})\n"]
    for item_name, chips in catches:
        lines.append(f"  {item_name} — {fmt(chips)} chips")
    lines.append(f"\n💰 Total: *{fmt(total)}* chips (+{Config.XP_FISH} XP)")
    lines.append(f"Balance: *{fmt(new_bal)}*")
    lines.append(f"⏰ Fish again in *{wait_mins} minutes*")
    _bot.reply_to(message, "\n".join(lines))

# ── Mining ────────────────────────────────────────────────────────────
def cmd_mine(message):
    p = db.get_player(message.from_user.id)
    if not p: _bot.reply_to(message, "❗ Register first with /start"); return

    level = db.xp_to_level(p.get("xp") or 0)
    if level < 10:
        _bot.reply_to(message,
            f"🔒 *Mining locked!*\n\nYou need *Level 10* to mine.\n"
            f"Your level: *{level}*\n\nPlay games to earn XP! 🎰"); return

    tool_key  = db.get_equipped(message.from_user.id, "mining")
    tool      = Config.MINING_TOOLS.get(tool_key, Config.MINING_TOOLS["stone_pickaxe"])
    wait_mins = tool["wait"]

    ok, msg = check_cooldown(message.from_user.id, "last_mine", wait_mins)
    if not ok:
        _bot.reply_to(message, f"⛏️ Already mined recently!\n{msg}"); return

    rare_chance = tool.get("rare", 0.05)
    bonus       = tool.get("bonus", 0.0)
    finds = []
    total = 0
    for _ in range(10):
        item_name, base_chips = pick_catch(rare_chance, COMMON_ORES, RARE_ORES, EPIC_ORES)
        chips = int(base_chips * (1 + bonus))
        finds.append((item_name, chips))
        total += chips

    db.set_activity_time(message.from_user.id, "last_mine")
    import gems as gems_mod
    gems_mod.check_achievements(message.from_user.id, message.chat.id)
    db.execute("UPDATE players SET mine_count=COALESCE(mine_count,0)+1 WHERE user_id=?", (message.from_user.id,))
    db.update_chips(message.from_user.id, total)
    db.add_xp(message.from_user.id, Config.XP_MINE)
    new_bal = db.get_player(message.from_user.id)["chips"]

    lines = [f"⛏️ *Mining Results!* ({tool['name']})\n"]
    for item_name, chips in finds:
        lines.append(f"  {item_name} — {fmt(chips)} chips")
    lines.append(f"\n💰 Total: *{fmt(total)}* chips (+{Config.XP_MINE} XP)")
    lines.append(f"Balance: *{fmt(new_bal)}*")
    lines.append(f"⏰ Mine again in *{wait_mins} minutes*")
    _bot.reply_to(message, "\n".join(lines))

# ── Farming ───────────────────────────────────────────────────────────
def cmd_farm(message):
    p = db.get_player(message.from_user.id)
    if not p: _bot.reply_to(message, "❗ Register first with /start"); return

    level = db.xp_to_level(p.get("xp") or 0)
    if level < 15:
        _bot.reply_to(message,
            f"🔒 *Farming locked!*\n\nYou need *Level 15* to farm.\n"
            f"Your level: *{level}*\n\nPlay games to earn XP! 🎰"); return

    tool_key  = db.get_equipped(message.from_user.id, "farming")
    tool      = Config.FARMING_TOOLS.get(tool_key, Config.FARMING_TOOLS["bare_hands"])
    wait_mins = tool["wait"]

    ok, msg = check_cooldown(message.from_user.id, "last_farm", wait_mins)
    if not ok:
        _bot.reply_to(message, f"🌾 Already farmed recently!\n{msg}"); return

    rare_chance = tool.get("rare", 0.05) if "rare" in tool else 0.05
    bonus       = tool.get("bonus", 0.0)
    harvests    = []
    total       = 0
    for _ in range(10):
        item_name, base_chips = pick_catch(rare_chance if rare_chance else 0.05, COMMON_CROPS, RARE_CROPS, EPIC_CROPS)
        chips = int(base_chips * (1 + bonus))
        harvests.append((item_name, chips))
        total += chips

    db.set_activity_time(message.from_user.id, "last_farm")
    import gems as gems_mod
    gems_mod.check_achievements(message.from_user.id, message.chat.id)
    db.execute("UPDATE players SET farm_count=COALESCE(farm_count,0)+1 WHERE user_id=?", (message.from_user.id,))
    db.update_chips(message.from_user.id, total)
    db.add_xp(message.from_user.id, Config.XP_FARM)
    new_bal = db.get_player(message.from_user.id)["chips"]

    lines = [f"🌾 *Farming Results!* ({tool['name']})\n"]
    for item_name, chips in harvests:
        lines.append(f"  {item_name} — {fmt(chips)} chips")
    lines.append(f"\n💰 Total: *{fmt(total)}* chips (+{Config.XP_FARM} XP)")
    lines.append(f"Balance: *{fmt(new_bal)}*")
    lines.append(f"⏰ Farm again in *{wait_mins} minutes*")
    _bot.reply_to(message, "\n".join(lines))

# ── Shop ──────────────────────────────────────────────────────────────
def cmd_shop(message):
    args     = message.text.split()
    category = args[1].lower() if len(args) > 1 else "all"

    if category in ("fish","fishing","rod"):
        lines = ["🎣 *Fishing Rods Shop*\n"]
        for key, t in Config.FISHING_TOOLS.items():
            price = "FREE" if t["price"] == 0 else fmt(t["price"])
            lines.append(f"{t['name']}\n  💰 {price} chips | ⏰ {t['wait']}min | 🔒 Lv.{t['level']} | 🎯 {int(t['rare']*100)}% rare\n  `/buy {key}`\n")
    elif category in ("mine","mining","pickaxe"):
        lines = ["⛏️ *Pickaxes Shop*\n"]
        for key, t in Config.MINING_TOOLS.items():
            price = "FREE" if t["price"] == 0 else fmt(t["price"])
            lines.append(f"{t['name']}\n  💰 {price} chips | ⏰ {t['wait']}min | 🔒 Lv.{t['level']} | 🎯 {int(t['rare']*100)}% rare\n  `/buy {key}`\n")
    elif category in ("farm","farming","hoe"):
        lines = ["🌾 *Farming Tools Shop*\n"]
        for key, t in Config.FARMING_TOOLS.items():
            price = "FREE" if t["price"] == 0 else fmt(t["price"])
            lines.append(f"{t['name']}\n  💰 {price} chips | ⏰ {t['wait']}min | 🔒 Lv.{t['level']} | 🎁 +{int(t['bonus']*100)}%\n  `/buy {key}`\n")
    else:
        lines = ["🏪 *Shop Categories*\n\n"
                 "🎣 `/shop fishing` — Fishing rods\n"
                 "⛏️ `/shop mining` — Pickaxes\n"
                 "🌾 `/shop farming` — Farming tools\n\n"
                 "Buy: `/buy [item]` | Equip: `/equip [item]`\nView owned: `/inventory`"]
    _bot.reply_to(message, "\n".join(lines))

def cmd_buy(message):
    p = db.get_player(message.from_user.id)
    if not p: _bot.reply_to(message, "❗ Register first"); return
    args = message.text.split()
    if len(args) < 2: _bot.reply_to(message, "Usage: `/buy [item_name]`\nCheck /shop"); return
    item_key = args[1].lower()
    if item_key not in Config.ALL_TOOLS:
        _bot.reply_to(message, f"❌ Item `{item_key}` not found!\nCheck /shop"); return

    tool  = Config.ALL_TOOLS[item_key]
    owned = db.get_owned_tools(message.from_user.id)

    if item_key in owned:
        _bot.reply_to(message, f"✅ You already own *{tool['name']}*!\nUse `/equip {item_key}` to equip it."); return

    # Level check
    player_level = db.xp_to_level(p.get("xp") or 0)
    required_level = tool.get("level", 0)
    if player_level < required_level:
        _bot.reply_to(message,
            f"🔒 Need *Level {required_level}* to buy *{tool['name']}*!\n"
            f"Your level: *{player_level}*"); return

    price = tool["price"]
    if price == 0:
        db.save_tool_purchase(message.from_user.id, item_key)
        _bot.reply_to(message, f"✅ *{tool['name']}* is free! Use `/equip {item_key}` to equip it."); return

    if p["chips"] < price:
        _bot.reply_to(message, f"❌ Not enough chips!\nNeed: *{fmt(price)}* | Have: *{fmt(p['chips'])}*"); return

    if item_key in Config.FISHING_TOOLS: tool_type = "fishing"
    elif item_key in Config.MINING_TOOLS: tool_type = "mining"
    else: tool_type = "farming"

    db.update_chips(message.from_user.id, -price)
    db.save_tool_purchase(message.from_user.id, item_key)
    new_bal = db.get_player(message.from_user.id)["chips"]
    _bot.reply_to(message,
        f"✅ *Purchased {tool['name']}!*\n💰 Paid: *{fmt(price)}* chips\n"
        f"Balance: *{fmt(new_bal)}*\n\nUse `/equip {item_key}` to equip it!")

def cmd_equip(message):
    p = db.get_player(message.from_user.id)
    if not p: _bot.reply_to(message, "❗ Register first"); return
    args = message.text.split()
    if len(args) < 2: _bot.reply_to(message, "Usage: `/equip [item_name]`"); return
    item_key = args[1].lower()
    if item_key not in Config.ALL_TOOLS:
        _bot.reply_to(message, f"❌ Item `{item_key}` not found!"); return
    owned = db.get_owned_tools(message.from_user.id)
    if item_key not in owned and Config.ALL_TOOLS[item_key]["price"] > 0:
        _bot.reply_to(message, f"❌ You don't own this! Buy with `/buy {item_key}`"); return

    if item_key in Config.FISHING_TOOLS: tool_type = "fishing"
    elif item_key in Config.MINING_TOOLS: tool_type = "mining"
    else: tool_type = "farming"

    db.equip_tool_db(message.from_user.id, item_key, tool_type)
    tool = Config.ALL_TOOLS[item_key]
    _bot.reply_to(message, f"✅ Equipped *{tool['name']}*!\n⏰ Wait time: *{tool['wait']} minutes*")

def cmd_inventory(message):
    uid      = message.from_user.id
    owned    = db.get_owned_tools(uid)
    fish_eq  = db.get_equipped(uid, "fishing")
    mine_eq  = db.get_equipped(uid, "mining")
    farm_eq  = db.get_equipped(uid, "farming")
    lines    = ["🎒 *Your Inventory*\n"]
    lines.append("🎣 *Fishing Rods:*")
    for key in owned:
        if key in Config.FISHING_TOOLS:
            eq = " ◀ equipped" if key == fish_eq else ""
            lines.append(f"  {Config.FISHING_TOOLS[key]['name']}{eq}")
    lines.append("\n⛏️ *Pickaxes:*")
    for key in owned:
        if key in Config.MINING_TOOLS:
            eq = " ◀ equipped" if key == mine_eq else ""
            lines.append(f"  {Config.MINING_TOOLS[key]['name']}{eq}")
    lines.append("\n🌾 *Farming Tools:*")
    for key in owned:
        if key in Config.FARMING_TOOLS:
            eq = " ◀ equipped" if key == farm_eq else ""
            lines.append(f"  {Config.FARMING_TOOLS[key]['name']}{eq}")
    _bot.reply_to(message, "\n".join(lines))

# ── Rbet ─────────────────────────────────────────────────────────────
active_rbets = {}

def cmd_rbet(message):
    p = db.get_player(message.from_user.id)
    if not p: _bot.reply_to(message, "❗ Register first with /start"); return
    uid = message.from_user.id
    if uid in active_rbets:
        game   = active_rbets[uid]
        prize  = game["prize"]
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("🎲 Risk It!", callback_data=f"rbet_risk_{uid}"),
            types.InlineKeyboardButton(f"💰 Take {fmt(prize)}", callback_data=f"rbet_take_{uid}")
        )
        _bot.reply_to(message,
            f"🎲 *Rbet Active!*\n\nPrize: *{fmt(prize)}* chips\nRounds survived: *{game['rounds']}*\n\n"
            f"🌻 80% → prize grows | 🐍 20% → lose all!", reply_markup=markup); return

    args = message.text.split()
    if len(args) < 2:
        _bot.reply_to(message,
            "🎲 *Risk Bet (Rbet)*\n\nUsage: `/rbet [amount]`\n\n"
            "🌻 80% chance → prize grows\n🐍 20% chance → lose everything!\n💰 `/rtake` to cash out safely"); return
    try: bet = int(args[1].replace(",", ""))
    except: _bot.reply_to(message, "❌ Invalid amount."); return

    min_bet = max(1, int(p["chips"] * 0.15))
    if bet < min_bet: _bot.reply_to(message, f"❌ Minimum bet: *{fmt(min_bet)}* chips (15% of balance)"); return
    if p["chips"] < bet: _bot.reply_to(message, f"❌ Not enough chips!"); return

    db.update_chips(uid, -bet)
    active_rbets[uid] = {"prize": bet, "rounds": 0, "chat_id": message.chat.id}
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("🎲 Risk It!", callback_data=f"rbet_risk_{uid}"),
        types.InlineKeyboardButton(f"💰 Take {fmt(bet)}", callback_data=f"rbet_take_{uid}")
    )
    _bot.reply_to(message,
        f"🎲 *Rbet Started!* Prize: *{fmt(bet)}* chips\n\n"
        f"⚠️ 🌻 80% → prize grows | 🐍 20% → lose everything!\n\n"
        f"/rbet → risk | /rtake → cash out", reply_markup=markup)

def cb_rbet(call):
    parts  = call.data.split("_")
    action = parts[1]
    uid    = int(parts[2])
    if call.from_user.id != uid: _bot.answer_callback_query(call.id, "Not your game!"); return
    if uid not in active_rbets:
        _bot.answer_callback_query(call.id, "No active rbet!")
        try: _bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
        except: pass
        return
    game = active_rbets[uid]
    if action == "take":
        prize = active_rbets.pop(uid)["prize"]
        db.update_chips(uid, prize)
        new_bal = db.get_player(uid)["chips"]
        _bot.edit_message_text(
            f"💰 *Cashed Out!*\n\nTook: *{fmt(prize)}* chips\nRounds survived: *{game['rounds']}*\n"
            f"Balance: *{fmt(new_bal)}*\n\nSmart move! 😎",
            call.message.chat.id, call.message.message_id, parse_mode="Markdown"); return
    if random.random() < 0.80:
        multi     = round(random.uniform(1.1, 1.5), 2)
        new_prize = int(game["prize"] * multi)
        game["prize"]  = new_prize
        game["rounds"] += 1
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("🎲 Risk Again!", callback_data=f"rbet_risk_{uid}"),
            types.InlineKeyboardButton(f"💰 Take {fmt(new_prize)}", callback_data=f"rbet_take_{uid}")
        )
        _bot.edit_message_text(
            f"🌻 *Survived! x{multi}*\n\nPrize: *{fmt(new_prize)}* chips\nRounds: *{game['rounds']}*\n\nKeep going or cash out?",
            call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
    else:
        lost = active_rbets.pop(uid)["prize"]
        _bot.edit_message_text(
            f"🐍 *SNAKE! Lost everything!*\n\nLost: *{fmt(lost)}* chips 💀\nRounds survived: *{game['rounds']}*\n\nShould've cashed out bhai 😭",
            call.message.chat.id, call.message.message_id, parse_mode="Markdown")

def cmd_rtake(message):
    uid = message.from_user.id
    if uid not in active_rbets: _bot.reply_to(message, "❌ No active rbet! Start with `/rbet [amount]`"); return
    game  = active_rbets.pop(uid)
    prize = game["prize"]
    db.update_chips(uid, prize)
    new_bal = db.get_player(uid)["chips"]
    _bot.reply_to(message,
        f"💰 *Cashed Out!*\n\nTook: *{fmt(prize)}* chips\nRounds survived: *{game['rounds']}*\n"
        f"Balance: *{fmt(new_bal)}*\n\nSmart move! 😎")
