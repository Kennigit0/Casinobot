# ═══════════════════════════════════════════════════════════════
# ALL CHANGES — paste each section into the correct file
# ═══════════════════════════════════════════════════════════════

# ──────────────────────────────────────────────────────────────
# 1. DATABASE.PY — add these 3 functions anywhere after init_db()
# ──────────────────────────────────────────────────────────────

BANK_LEVELS = {
    0: {"name": "Basic",    "limit": 50_000,      "upgrade_cost": 10_000},
    1: {"name": "Bronze",   "limit": 200_000,     "upgrade_cost": 50_000},
    2: {"name": "Silver",   "limit": 500_000,     "upgrade_cost": 150_000},
    3: {"name": "Gold",     "limit": 1_000_000,   "upgrade_cost": 400_000},
    4: {"name": "Platinum", "limit": 5_000_000,   "upgrade_cost": 1_200_000},
    5: {"name": "Diamond",  "limit": 20_000_000,  "upgrade_cost": 4_000_000},
    6: {"name": "Elite",    "limit": 999_999_999, "upgrade_cost": None},  # max
}

def add_win(user_id):
    execute("UPDATE players SET wins = COALESCE(wins,0) + 1 WHERE user_id=?", (user_id,))

def add_loss(user_id):
    execute("UPDATE players SET losses = COALESCE(losses,0) + 1 WHERE user_id=?", (user_id,))

def get_bank_level(user_id):
    p = get_player(user_id)
    return p.get("bank_level") or 0 if p else 0

def get_bank_limit(user_id):
    lvl = get_bank_level(user_id)
    return BANK_LEVELS[lvl]["limit"]

def upgrade_bank(user_id):
    lvl = get_bank_level(user_id)
    if lvl >= 6:
        return False, "🏦 Already at *Elite* level — max upgrade reached!"
    cost = BANK_LEVELS[lvl]["upgrade_cost"]
    p    = get_player(user_id)
    if not p:
        return False, "Player not found."
    if p["chips"] < cost:
        return False, f"❌ Need *{cost:,}* chips in wallet to upgrade."
    execute("UPDATE players SET chips=chips-?, bank_level=bank_level+1 WHERE user_id=?", (cost, user_id))
    new_lvl = lvl + 1
    return True, BANK_LEVELS[new_lvl]


# ──────────────────────────────────────────────────────────────
# 2. DATABASE.PY — add these 3 lines inside BOTH migration loops
#    (one for PostgreSQL, one for SQLite) alongside existing ones
# ──────────────────────────────────────────────────────────────

# ADD THESE TO THE for col, defn in [...] list in init_db():
#   ("wins",       "INTEGER DEFAULT 0"),
#   ("losses",     "INTEGER DEFAULT 0"),
#   ("bank_level", "INTEGER DEFAULT 0"),


# ──────────────────────────────────────────────────────────────
# 3. DATABASE.PY — update bank_deposit() to enforce limit
# ──────────────────────────────────────────────────────────────

def bank_deposit(user_id, amount):
    p     = get_player(user_id)
    limit = get_bank_limit(user_id)
    current_bank = p.get("bank") or 0
    if current_bank + amount > limit:
        space = limit - current_bank
        if space <= 0:
            return False, f"❌ Bank is full! Upgrade with /bankupgrade to store more."
        return False, f"❌ Only *{space:,}* space left. Deposit that or upgrade with /bankupgrade."
    execute("UPDATE players SET chips=chips-?, bank=bank+? WHERE user_id=?", (amount, amount, user_id))
    return True, amount

# NOTE: update callers in features.py for /deposit to use: ok, result = db.bank_deposit(uid, amount)


# ──────────────────────────────────────────────────────────────
# 4. BOT.PY — fix min_bet in ALL 4 game commands
#    Replace this line in /slots, /dice, /roulette, /bj:
#
#    OLD:  min_bet = max(1, int(p["chips"] * 0.15))
#    NEW:  min_bet = max(1, int((p["chips"] + (p.get("bank") or 0)) * 0.15))
#
#    Also add win/loss tracking after each game result:
#    After db.update_chips():
#      if net > 0:  db.add_win(message.from_user.id)
#      else:        db.add_loss(message.from_user.id)
# ──────────────────────────────────────────────────────────────


# ──────────────────────────────────────────────────────────────
# 5. FEATURES.PY — update cmd_profile to show wins/losses
#    Replace the _bot.reply_to inside cmd_profile with this:
# ──────────────────────────────────────────────────────────────

def cmd_profile_updated(message):
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
    wins     = p.get("wins") or 0
    losses   = p.get("losses") or 0
    total_g  = wins + losses
    ratio    = f"{wins/total_g*100:.1f}%" if total_g > 0 else "N/A"
    bank_lvl = p.get("bank_level") or 0
    bank_info = db.BANK_LEVELS[bank_lvl]
    bank_limit = bank_info["limit"]
    bank_pct  = f"{bank/bank_limit*100:.1f}%" if bank_limit < 999_999_999 else "MAX"
    married  = ""
    if p.get("married_to") and p["married_to"] != 0:
        spouse = db.get_player(p["married_to"])
        if spouse: married = f"\n💍 Married to: *{spouse['first_name']}*"
    _bot.reply_to(message,
        f"👤 *{p['first_name']}'s Profile*\n\n"
        f"🏅 Status: {vip_tag}\n"
        f"⭐ Level: *{level}* — {title}\n"
        f"✨ XP: *{xp:,}*\n"
        f"👛 Wallet: *{p['chips']:,}* chips\n"
        f"🏦 Bank:   *{bank:,}* / *{bank_limit:,}* chips ({bank_pct})\n"
        f"🏦 Bank Tier: *{bank_info['name']}* (Lv.{bank_lvl})\n"
        f"💰 Total:  *{p['chips'] + bank:,}* chips\n\n"
        f"🎮 Games: *{total_g}* played\n"
        f"✅ Wins: *{wins}*  ❌ Losses: *{losses}*\n"
        f"📊 Win Rate: *{ratio}*"
        f"{married}")


# ──────────────────────────────────────────────────────────────
# 6. FEATURES.PY — add /bankupgrade and /deposit fix
#    Add to the handler registration list:
#    (["bankupgrade", "upgradebank"], cmd_bankupgrade),
#    (["deposit"],                    cmd_deposit_updated),
# ──────────────────────────────────────────────────────────────

def cmd_bankupgrade(message):
    p = db.get_player(message.from_user.id)
    if not p: _bot.reply_to(message, "❗ /start first"); return
    lvl   = p.get("bank_level") or 0
    info  = db.BANK_LEVELS[lvl]
    lines = ["🏦 *Bank Upgrade Tiers*\n"]
    for l, data in db.BANK_LEVELS.items():
        arrow = " ◀ *YOU*" if l == lvl else ""
        cost  = f"{data['upgrade_cost']:,} chips" if data['upgrade_cost'] else "MAX"
        limit = f"{data['limit']:,}" if data['limit'] < 999_999_999 else "Unlimited"
        lines.append(f"Lv.{l} {data['name']} — Limit: {limit} | Cost: {cost}{arrow}")
    if lvl < 6:
        next_cost = info['upgrade_cost']
        lines.append(f"\n💡 Upgrade to *{db.BANK_LEVELS[lvl+1]['name']}* for *{next_cost:,}* chips")
        lines.append("Type `/bankupgrade confirm` to upgrade")
    else:
        lines.append("\n✅ You are at *Elite* — max level!")
    _bot.reply_to(message, "\n".join(lines))

def cmd_bankupgrade_confirm(message):
    if "confirm" not in message.text.lower(): return
    ok, result = db.upgrade_bank(message.from_user.id)
    if ok:
        _bot.reply_to(message,
            f"✅ Bank upgraded to *{result['name']}*!\n"
            f"🏦 New limit: *{result['limit']:,}* chips")
    else:
        _bot.reply_to(message, result)

def cmd_deposit_updated(message):
    p = db.get_player(message.from_user.id)
    if not p: _bot.reply_to(message, "❗ /start first"); return
    args = message.text.split()
    if len(args) < 2:
        limit = db.get_bank_limit(message.from_user.id)
        _bot.reply_to(message,
            f"🏦 *Bank Deposit*\n"
            f"Usage: `/deposit [amount]` or `/deposit all`\n\n"
            f"💡 Your bank limit: *{limit:,}* chips\n"
            f"   Upgrade with /bankupgrade to store more!")
        return
    amt_str = args[1].lower()
    amount  = p["chips"] if amt_str == "all" else int(amt_str.replace(",",""))
    if amount <= 0: _bot.reply_to(message, "❌ Amount must be positive."); return
    if p["chips"] < amount: _bot.reply_to(message, f"❌ Not enough chips in wallet!"); return
    ok, result = db.bank_deposit(message.from_user.id, amount)
    if ok:
        new = db.get_player(message.from_user.id)
        _bot.reply_to(message,
            f"✅ Deposited *{result:,}* chips!\n"
            f"🏦 Bank: *{new['bank']:,}* / *{db.get_bank_limit(message.from_user.id):,}*\n"
            f"👛 Wallet: *{new['chips']:,}*")
    else:
        _bot.reply_to(message, result)

