"""gems.py — Rare currency, achievements, gem shop"""
import random
import database as db

_bot = None

# ── Gem Shop Items ──────────────────────────────────────────────────────
GEM_SHOP = {
    "daily_spin":   {"name": "🎰 Extra Daily Spin",      "cost": 2,  "desc": "Reset your daily bonus cooldown"},
    "cooldown_skip":{"name": "⚡ Cooldown Skip",          "cost": 3,  "desc": "Skip any activity cooldown"},
    "mystery_box":  {"name": "🎁 Mystery Box",            "cost": 5,  "desc": "Win 5,000–50,000 random chips"},
    "vip_day":      {"name": "👑 VIP for 24h",            "cost": 10, "desc": "Get VIP status for 24 hours"},
    "chip_boost":   {"name": "💰 2x Chip Boost (1hr)",   "cost": 7,  "desc": "Double all chip earnings for 1 hour"},
}

# ── Achievements ────────────────────────────────────────────────────────
ACHIEVEMENTS = {
    # Chips
    "getting_started": {"name": "🪙 Getting Started",  "desc": "Earn 10,000 chips total",         "reward_chips": 500,   "reward_gems": 0,  "check": lambda p: (p.get("total_earned") or 0) >= 10_000},
    "grinder":         {"name": "💵 Grinder",           "desc": "Earn 100,000 chips total",        "reward_chips": 0,     "reward_gems": 1,  "check": lambda p: (p.get("total_earned") or 0) >= 100_000},
    "rich_kid":        {"name": "💰 Rich Kid",          "desc": "Reach 500,000 chips",             "reward_chips": 0,     "reward_gems": 2,  "check": lambda p: (p.get("chips") or 0) >= 500_000},
    "millionaire":     {"name": "🤑 Millionaire",       "desc": "Reach 1,000,000 chips",           "reward_chips": 0,     "reward_gems": 5,  "check": lambda p: (p.get("chips") or 0) >= 1_000_000},
    "billionaire":     {"name": "💎 Billionaire",       "desc": "Reach 1,000,000,000 chips",        "reward_chips": 0,     "reward_gems": 10, "check": lambda p: (p.get("chips") or 0) >= 1_000_000_000},
    "banker":          {"name": "🏦 Banker",            "desc": "Have 500,000 chips in bank",      "reward_chips": 0,     "reward_gems": 2,  "check": lambda p: (p.get("bank") or 0) >= 500_000},
    # Streaks
    "hot_streak":      {"name": "🔥 Hot Streak",        "desc": "Win 10 minigames in a row",       "reward_chips": 1000,  "reward_gems": 1,  "check": lambda p: (p.get("best_streak") or 0) >= 10},
    "on_fire":         {"name": "🔥🔥 On Fire",          "desc": "Win 25 minigames in a row",       "reward_chips": 0,     "reward_gems": 3,  "check": lambda p: (p.get("best_streak") or 0) >= 25},
    "unstoppable":     {"name": "💀 Unstoppable",       "desc": "Win 50 minigames in a row",       "reward_chips": 0,     "reward_gems": 5,  "check": lambda p: (p.get("best_streak") or 0) >= 50},
    # Minigames
    "big_brain":       {"name": "🧠 Big Brain",         "desc": "Win 50 trivia questions",         "reward_chips": 0,     "reward_gems": 2,  "check": lambda p: (p.get("trivia_wins") or 0) >= 50},
    "sharp_mind":      {"name": "🎯 Sharp Mind",        "desc": "Win 100 minigames total",         "reward_chips": 0,     "reward_gems": 3,  "check": lambda p: (p.get("minigame_wins") or 0) >= 100},
    # Casino games
    "slot_addict":     {"name": "🎰 Slot Addict",       "desc": "Play slots 200 times",            "reward_chips": 0,     "reward_gems": 2,  "check": lambda p: (p.get("slots_played") or 0) >= 200},
    "card_shark":      {"name": "🃏 Card Shark",        "desc": "Win 50 blackjack games",          "reward_chips": 0,     "reward_gems": 3,  "check": lambda p: (p.get("bj_wins") or 0) >= 50},
    "casino_king":     {"name": "👑 Casino King",       "desc": "Win 500 games total",             "reward_chips": 0,     "reward_gems": 10, "check": lambda p: (p.get("wins") or 0) >= 500},
    "legend":          {"name": "🏆 Legend",            "desc": "Win 1000 games total",            "reward_chips": 0,     "reward_gems": 20, "check": lambda p: (p.get("wins") or 0) >= 1000},
    # Activities
    "fisher_king":     {"name": "🎣 Fisher King",       "desc": "Fish 50 times",                   "reward_chips": 0,     "reward_gems": 1,  "check": lambda p: (p.get("fish_count") or 0) >= 50},
    "miner":           {"name": "⛏️ Miner",             "desc": "Mine 50 times",                   "reward_chips": 0,     "reward_gems": 1,  "check": lambda p: (p.get("mine_count") or 0) >= 50},
    "farmer":          {"name": "🌾 Farmer",            "desc": "Farm 50 times",                   "reward_chips": 0,     "reward_gems": 1,  "check": lambda p: (p.get("farm_count") or 0) >= 50},
    # Other
    "high_roller":     {"name": "💸 High Roller",       "desc": "Bet 10,000+ in one game",         "reward_chips": 0,     "reward_gems": 1,  "check": lambda p: (p.get("max_bet") or 0) >= 10_000},
    "first_win":       {"name": "🎉 First Win",         "desc": "Win your first game",             "reward_chips": 500,   "reward_gems": 0,  "check": lambda p: (p.get("wins") or 0) >= 1},
    "vip_club":        {"name": "⭐ VIP Club",          "desc": "Reach Level 20",                  "reward_chips": 0,     "reward_gems": 3,  "check": lambda p: db.xp_to_level(p.get("xp") or 0) >= 20},
}

def fmt(n): return f"{n:,}"

# ── DB helpers ──────────────────────────────────────────────────────────
def get_gems(uid):
    p = db.get_player(uid)
    return p.get("gems") or 0 if p else 0

def add_gems(uid, amount):
    db.execute("UPDATE players SET gems = COALESCE(gems,0) + ? WHERE user_id=?", (amount, uid))

def spend_gems(uid, amount):
    gems = get_gems(uid)
    if gems < amount:
        return False
    db.execute("UPDATE players SET gems = gems - ? WHERE user_id=?", (amount, uid))
    return True

def get_unlocked(uid):
    rows = db.execute("SELECT achievement_id FROM achievements WHERE user_id=?", (uid,), fetch="all") or []
    return {r["achievement_id"] for r in rows} if rows else set()

def unlock_achievement(uid, ach_id):
    db.execute("INSERT INTO achievements (user_id, achievement_id) VALUES (?,?) ON CONFLICT DO NOTHING", (uid, ach_id))

def check_achievements(uid, chat_id=None):
    p        = db.get_player(uid)
    if not p: return
    unlocked = get_unlocked(uid)
    new_ones = []

    for ach_id, ach in ACHIEVEMENTS.items():
        if ach_id in unlocked: continue
        try:
            if ach["check"](p):
                unlock_achievement(uid, ach_id)
                new_ones.append(ach)
                if ach["reward_chips"]:
                    db.update_chips(uid, ach["reward_chips"])
                if ach["reward_gems"]:
                    add_gems(uid, ach["reward_gems"])
        except: pass

    if new_ones and chat_id and _bot:
        for ach in new_ones:
            reward_txt = ""
            if ach["reward_chips"]: reward_txt += f" +{fmt(ach['reward_chips'])} chips"
            if ach["reward_gems"]:  reward_txt += f" +{ach['reward_gems']} 💎"
            _bot.send_message(chat_id,
                f"🏆 *Achievement Unlocked!*\n\n"
                f"{ach['name']}\n"
                f"_{ach['desc']}_\n\n"
                f"🎁 Reward:{reward_txt}", parse_mode="Markdown")

# ── Commands ────────────────────────────────────────────────────────────
def cmd_gems(message):
    uid  = message.from_user.id
    p    = db.get_player(uid)
    if not p: _bot.reply_to(message, "❗ /start first"); return
    gems = p.get("gems") or 0
    _bot.reply_to(message,
        f"💎 *Your Gems*\n\n"
        f"You have *{gems}* 💎 gems\n\n"
        f"_Gems are rare currency earned through achievements,_\n"
        f"_winning streaks, and rare activity drops._\n\n"
        f"Use /gemshop to spend them!", parse_mode="Markdown")

ACH_PAGE_SIZE = 5

def _get_ach_page(uid, page=0):
    unlocked = get_unlocked(uid)
    all_achs = list(ACHIEVEMENTS.items())
    done     = [(k,a) for k,a in all_achs if k in unlocked]
    pending  = [(k,a) for k,a in all_achs if k not in unlocked]
    combined = done + pending
    total    = len(combined)
    pages    = (total + ACH_PAGE_SIZE - 1) // ACH_PAGE_SIZE
    start    = page * ACH_PAGE_SIZE
    chunk    = combined[start:start+ACH_PAGE_SIZE]
    return chunk, len(done), total, pages

def _ach_markup(uid, page, pages):
    from telebot import types as _types
    markup = _types.InlineKeyboardMarkup(row_width=3)
    btns = []
    if page > 0:
        btns.append(_types.InlineKeyboardButton("◀", callback_data=f"ach_page_{uid}_{page-1}"))
    btns.append(_types.InlineKeyboardButton(f"{page+1}/{pages}", callback_data="ach_noop"))
    if page < pages - 1:
        btns.append(_types.InlineKeyboardButton("▶", callback_data=f"ach_page_{uid}_{page+1}"))
    markup.add(*btns)
    return markup

def _build_ach_text(uid, page=0):
    unlocked = get_unlocked(uid)
    chunk, done_count, total, pages = _get_ach_page(uid, page)
    lines = [f"🏆 *Achievements* — {done_count}/{total} unlocked | Page {page+1}/{pages}\n"]
    for k, a in chunk:
        is_done = k in unlocked
        r = ""
        if a["reward_chips"]: r += f" +{fmt(a['reward_chips'])} chips"
        if a["reward_gems"]:  r += f" +{a['reward_gems']} 💎"
        status = "✅" if is_done else "🔒"
        lines.append(f"{status} *{a['name']}*{' ~~' if not is_done else ''}")
        lines.append(f"   _{a['desc']}_  —{r}")
    return "\n".join(lines), pages

def cmd_achievements(message):
    uid = message.from_user.id
    p   = db.get_player(uid)
    if not p: _bot.reply_to(message, "❗ /start first"); return
    check_achievements(uid, message.chat.id)
    text, pages = _build_ach_text(uid, 0)
    markup = _ach_markup(uid, 0, pages)
    _bot.reply_to(message, text, parse_mode="Markdown", reply_markup=markup)

def cb_ach_page(call):
    parts = call.data.split("_")
    if parts[1] == "noop": _bot.answer_callback_query(call.id); return
    uid  = int(parts[2])
    page = int(parts[3])
    text, pages = _build_ach_text(uid, page)
    markup = _ach_markup(uid, page, pages)
    _bot.answer_callback_query(call.id)
    try:
        _bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
            parse_mode="Markdown", reply_markup=markup)
    except: pass

def cmd_gemshop(message):
    from telebot import types as _types
    uid  = message.from_user.id
    gems = get_gems(uid)
    lines = [f"💎 *Gem Shop* — You have *{gems}* 💎\n"]
    btns  = []
    for item_id, item in GEM_SHOP.items():
        can = "✅" if gems >= item["cost"] else "🔒"
        lines.append(f"{can} {item['name']} — *{item['cost']}* 💎\n_{item['desc']}_")
        btns.append([_types.InlineKeyboardButton(
            f"{item['name']} ({item['cost']} 💎)",
            callback_data=f"gem_buy_{item_id}_{uid}"
        )])
    markup = _types.InlineKeyboardMarkup()
    for row in btns: markup.row(*row)
    _bot.reply_to(message, "\n".join(lines), parse_mode="Markdown", reply_markup=markup)

_gem_processing = set()

def handle_gem_callbacks(call):
    uid  = call.from_user.id
    data = call.data
    if not data.startswith("gem_buy_"): return

    # Spam protection
    lock = f"gem_{uid}_{data}"
    if lock in _gem_processing:
        _bot.answer_callback_query(call.id, "⏳ Processing..."); return
    _gem_processing.add(lock)

    # uid check — only owner can use their gem shop buttons
    parts = data.split("_")
    if parts[-1].isdigit() and str(uid) != parts[-1]:
        _bot.answer_callback_query(call.id, "❌ This is not your gem shop!", show_alert=True)
        _gem_processing.discard(lock); return

    item_id = "_".join(parts[2:-1]) if parts[-1].isdigit() else data.replace("gem_buy_", "")
    item    = GEM_SHOP.get(item_id)
    if not item:
        _bot.answer_callback_query(call.id, "❌ Item not found!")
        _gem_processing.discard(lock); return

    try:
        _do_gem_buy(call, uid, item_id, item)
    finally:
        _gem_processing.discard(lock)

def _do_gem_buy(call, uid, item_id, item):
    item    = GEM_SHOP.get(item_id)
    if not item: _bot.answer_callback_query(call.id, "❌ Item not found!"); return

    gems = get_gems(uid)
    if gems < item["cost"]:
        _bot.answer_callback_query(call.id, f"❌ Need {item['cost']} 💎! You have {gems}.", show_alert=True)
        return

    spend_gems(uid, item["cost"])

    if item_id == "mystery_box":
        reward = random.randint(5_000, 50_000)
        db.update_chips(uid, reward)
        _bot.answer_callback_query(call.id, f"🎁 You got {fmt(reward)} chips!", show_alert=True)
        _bot.send_message(call.message.chat.id,
            f"🎁 *Mystery Box Opened!*\n\n"
            f"{call.from_user.first_name} won *{fmt(reward)}* chips! 🎉",
            parse_mode="Markdown")

    elif item_id == "daily_spin":
        db.execute("UPDATE players SET last_daily=NULL WHERE user_id=?", (uid,))
        _bot.answer_callback_query(call.id, "✅ Daily bonus reset! Use /daily now.", show_alert=True)

    elif item_id == "vip_day":
        db.execute("UPDATE players SET vip=1 WHERE user_id=?", (uid,))
        _bot.answer_callback_query(call.id, "👑 VIP activated for 24h!", show_alert=True)
        _bot.send_message(call.message.chat.id,
            f"👑 *{call.from_user.first_name}* is now VIP for 24 hours!", parse_mode="Markdown")

    elif item_id == "cooldown_skip":
        db.execute("UPDATE players SET last_work=NULL, last_crime=NULL, last_fish=NULL, last_mine=NULL, last_farm=NULL WHERE user_id=?", (uid,))
        _bot.answer_callback_query(call.id, "⚡ All cooldowns cleared!", show_alert=True)

    elif item_id == "chip_boost":
        add_gems(uid, item["cost"])  # refund - not implemented yet
        _bot.answer_callback_query(call.id, "⚠️ 2x Chip Boost is coming soon! Gems refunded.", show_alert=True)

# ── Register ─────────────────────────────────────────────────────────────
def register_gems(bot_instance):
    global _bot
    _bot = bot_instance

    # Add achievements table
    db.execute("""
        CREATE TABLE IF NOT EXISTS achievements (
            user_id      BIGINT,
            achievement_id TEXT,
            unlocked_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, achievement_id)
        )
    """)
    # Add gems column
    try:
        db.execute("ALTER TABLE players ADD COLUMN IF NOT EXISTS gems INTEGER DEFAULT 0")
    except: pass
    try:
        db.execute("ALTER TABLE players ADD COLUMN IF NOT EXISTS best_streak INTEGER DEFAULT 0")
    except: pass
    try:
        db.execute("ALTER TABLE players ADD COLUMN IF NOT EXISTS total_earned BIGINT DEFAULT 0")
    except: pass
    try:
        db.execute("ALTER TABLE players ADD COLUMN IF NOT EXISTS trivia_wins INTEGER DEFAULT 0")
    except: pass
    try:
        db.execute("ALTER TABLE players ADD COLUMN IF NOT EXISTS minigame_wins INTEGER DEFAULT 0")
    except: pass
    try:
        db.execute("ALTER TABLE players ADD COLUMN IF NOT EXISTS slots_played INTEGER DEFAULT 0")
    except: pass
    try:
        db.execute("ALTER TABLE players ADD COLUMN IF NOT EXISTS bj_wins INTEGER DEFAULT 0")
    except: pass
    try:
        db.execute("ALTER TABLE players ADD COLUMN IF NOT EXISTS max_bet INTEGER DEFAULT 0")
    except: pass
    try:
        db.execute("ALTER TABLE players ADD COLUMN IF NOT EXISTS fish_count INTEGER DEFAULT 0")
    except: pass
    try:
        db.execute("ALTER TABLE players ADD COLUMN IF NOT EXISTS mine_count INTEGER DEFAULT 0")
    except: pass
    try:
        db.execute("ALTER TABLE players ADD COLUMN IF NOT EXISTS farm_count INTEGER DEFAULT 0")
    except: pass

    bot_instance.register_callback_query_handler(cb_ach_page, func=lambda c: c.data.startswith('ach_page_') or c.data == 'ach_noop')
    bot_instance.register_message_handler(cmd_gems,         commands=["gems"])
    bot_instance.register_message_handler(cmd_achievements, commands=["achievements", "ach"])
    bot_instance.register_message_handler(cmd_gemshop,      commands=["gemshop"])
    bot_instance.register_callback_query_handler(
        handle_gem_callbacks,
        func=lambda c: c.data.startswith("gem_buy_")
    )
    print("✅ Gems & Achievements loaded")
# gems columns migration
