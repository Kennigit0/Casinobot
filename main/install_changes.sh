#!/data/data/com.termux/files/usr/bin/bash
cd ~/casino_bot

echo "📦 Copying new files..."
cp /storage/emulated/0/Download/minigames.py ~/casino_bot/
cp /storage/emulated/0/Download/changes.py ~/casino_bot/

echo "🔧 Patching database.py..."
python3 << 'EOF'
with open("database.py", "r") as f:
    content = f.read()

# 1. Add new columns to SQLite migration list
old = '("married_to","INTEGER DEFAULT 0")]:'
new = '("married_to","INTEGER DEFAULT 0"),\n            ("wins","INTEGER DEFAULT 0"),\n            ("losses","INTEGER DEFAULT 0"),\n            ("bank_level","INTEGER DEFAULT 0")]:'
content = content.replace(old, new)

# 2. Add new columns to PostgreSQL migration list
old = '("married_to","BIGINT DEFAULT 0"),'
new = '("married_to","BIGINT DEFAULT 0"),\n            ("wins","BIGINT DEFAULT 0"),\n            ("losses","BIGINT DEFAULT 0"),\n            ("bank_level","INTEGER DEFAULT 0"),'
content = content.replace(old, new)

# 3. Add BANK_LEVELS + new functions before bank_deposit
bank_code = '''
BANK_LEVELS = {
    0: {"name": "Basic",    "limit": 50_000,      "upgrade_cost": 10_000},
    1: {"name": "Bronze",   "limit": 200_000,     "upgrade_cost": 50_000},
    2: {"name": "Silver",   "limit": 500_000,     "upgrade_cost": 150_000},
    3: {"name": "Gold",     "limit": 1_000_000,   "upgrade_cost": 400_000},
    4: {"name": "Platinum", "limit": 5_000_000,   "upgrade_cost": 1_200_000},
    5: {"name": "Diamond",  "limit": 20_000_000,  "upgrade_cost": 4_000_000},
    6: {"name": "Elite",    "limit": 999_999_999, "upgrade_cost": None},
}

def add_win(user_id):
    execute("UPDATE players SET wins = COALESCE(wins,0) + 1 WHERE user_id=?", (user_id,))

def add_loss(user_id):
    execute("UPDATE players SET losses = COALESCE(losses,0) + 1 WHERE user_id=?", (user_id,))

def get_bank_limit(user_id):
    p = get_player(user_id)
    lvl = (p.get("bank_level") or 0) if p else 0
    return BANK_LEVELS[lvl]["limit"]

def upgrade_bank(user_id):
    p = get_player(user_id)
    if not p: return False, "Player not found."
    lvl = p.get("bank_level") or 0
    if lvl >= 6: return False, "🏦 Already at *Elite* — max level!"
    cost = BANK_LEVELS[lvl]["upgrade_cost"]
    if p["chips"] < cost:
        return False, f"❌ Need *{cost:,}* chips in wallet to upgrade."
    execute("UPDATE players SET chips=chips-?, bank_level=bank_level+1 WHERE user_id=?", (cost, user_id))
    return True, BANK_LEVELS[lvl + 1]

'''
content = content.replace("def bank_deposit(user_id, amount):", bank_code + "def bank_deposit(user_id, amount):")

# 4. Replace bank_deposit to enforce limit
old_deposit = """def bank_deposit(user_id, amount):
    execute("UPDATE players SET chips=chips-?, bank=bank+? WHERE user_id=?", (amount, amount, user_id))"""
new_deposit = """def bank_deposit(user_id, amount):
    p = get_player(user_id)
    limit = get_bank_limit(user_id)
    current_bank = p.get("bank") or 0
    if current_bank + amount > limit:
        space = limit - current_bank
        if space <= 0:
            return False, "❌ Bank is full! Use /bankupgrade to store more."
        return False, f"❌ Only *{space:,}* space left. Deposit that or /bankupgrade."
    execute("UPDATE players SET chips=chips-?, bank=bank+? WHERE user_id=?", (amount, amount, user_id))
    return True, amount"""
content = content.replace(old_deposit, new_deposit)

with open("database.py", "w") as f:
    f.write(content)
print("✅ database.py patched")
EOF

echo "🔧 Patching bot.py..."
python3 << 'EOF'
with open("bot.py", "r") as f:
    content = f.read()

# 1. Import minigames
if "import minigames" not in content:
    content = content.replace("import activities", "import activities\nimport minigames")

# 2. Register minigames
content = content.replace(
    'activities.register_activities(bot)\n    print("✅ Activities loaded")',
    'activities.register_activities(bot)\n    print("✅ Activities loaded")\n    minigames.register_minigames(bot)\n    print("✅ Minigames loaded")'
)

# 3. Fix min_bet in all 4 games to include bank
content = content.replace(
    'min_bet = max(1, int(p["chips"] * 0.15))',
    'min_bet = max(1, int((p["chips"] + (p.get("bank") or 0)) * 0.15))'
)

# 4. Add win/loss tracking after slots
content = content.replace(
    '    if net > 0:\n        db.add_xp(message.from_user.id, Config.XP_GAME_WIN)\n    new_bal = db.get_player(message.from_user.id)["chips"]\n    sign    = "+" if net >= 0 else ""\n    xp_note = f" +{Config.XP_GAME_WIN} XP" if net > 0 else ""\n    bot.reply_to(slot_msg,',
    '    if net > 0:\n        db.add_xp(message.from_user.id, Config.XP_GAME_WIN)\n        db.add_win(message.from_user.id)\n    else:\n        db.add_loss(message.from_user.id)\n    new_bal = db.get_player(message.from_user.id)["chips"]\n    sign    = "+" if net >= 0 else ""\n    xp_note = f" +{Config.XP_GAME_WIN} XP" if net > 0 else ""\n    bot.reply_to(slot_msg,'
)

with open("bot.py", "w") as f:
    f.write(content)
print("✅ bot.py patched")
EOF

echo "🔧 Patching features.py..."
python3 << 'EOF'
with open("features.py", "r") as f:
    content = f.read()

# 1. Add bankupgrade to handler list
content = content.replace(
    '(["profile", "me"],     cmd_profile),',
    '(["profile", "me"],     cmd_profile),\n        (["bankupgrade","upgradebank"], cmd_bankupgrade),\n        (["deposit"],                  cmd_deposit),'
)

# 2. Replace cmd_profile body
old_profile = '''    _bot.reply_to(message,
        f"👤 *{p['first_name']}'s Profile*\\n\\n"
        f"🏅 Status: {vip_tag}\\n"
        f"⭐ Level: *{level}* — {title}\\n"
        f"✨ XP: *{fmt(xp)}*\\n"
        f"👛 Wallet: *{fmt(p['chips'])}* chips\\n"
        f"🏦 Bank:   *{fmt(bank)}* chips\\n"
        f"💰 Total:  *{fmt(p['chips'] + bank)}* chips"
        f"{married}")'''
new_profile = '''    wins     = p.get("wins") or 0
    losses   = p.get("losses") or 0
    total_g  = wins + losses
    ratio    = f"{wins/total_g*100:.1f}%" if total_g > 0 else "N/A"
    bank_lvl = p.get("bank_level") or 0
    bank_info  = db.BANK_LEVELS[bank_lvl]
    bank_limit = bank_info["limit"]
    bank_pct   = f"{bank/bank_limit*100:.1f}%" if bank_limit < 999_999_999 else "MAX"
    _bot.reply_to(message,
        f"👤 *{p['first_name']}'s Profile*\\n\\n"
        f"🏅 Status: {vip_tag}\\n"
        f"⭐ Level: *{level}* — {title}\\n"
        f"✨ XP: *{fmt(xp)}*\\n"
        f"👛 Wallet: *{fmt(p['chips'])}* chips\\n"
        f"🏦 Bank: *{fmt(bank)}* / *{fmt(bank_limit)}* ({bank_pct})\\n"
        f"🏦 Bank Tier: *{bank_info['name']}* Lv.{bank_lvl}\\n"
        f"💰 Total: *{fmt(p['chips'] + bank)}* chips\\n\\n"
        f"🎮 Games Played: *{total_g}*\\n"
        f"✅ Wins: *{wins}*  ❌ Losses: *{losses}*\\n"
        f"📊 Win Rate: *{ratio}*"
        f"{married}")'''
content = content.replace(old_profile, new_profile)

# 3. Add bankupgrade + deposit commands before last function
bank_cmds = '''
def cmd_bankupgrade(message):
    p = db.get_player(message.from_user.id)
    if not p: _bot.reply_to(message, "❗ /start first"); return
    lvl  = p.get("bank_level") or 0
    lines = ["🏦 *Bank Upgrade Tiers*\\n"]
    for l, data in db.BANK_LEVELS.items():
        arrow = " ◀ *YOU*" if l == lvl else ""
        cost  = f"{data['upgrade_cost']:,} chips" if data["upgrade_cost"] else "MAX"
        limit = f"{data['limit']:,}" if data["limit"] < 999_999_999 else "Unlimited"
        lines.append(f"Lv.{l} *{data['name']}* — Limit: {limit} | Cost: {cost}{arrow}")
    if lvl < 6:
        next_cost = db.BANK_LEVELS[lvl]["upgrade_cost"]
        lines.append(f"\\n💡 Cost to upgrade: *{next_cost:,}* chips")
        lines.append("Type `/bankupgrade confirm` to upgrade")
    else:
        lines.append("\\n✅ Max level reached!")
    if "confirm" in message.text.lower():
        ok, result = db.upgrade_bank(message.from_user.id)
        if ok:
            _bot.reply_to(message, f"✅ Upgraded to *{result['name']}*!\\n🏦 New limit: *{result['limit']:,}* chips")
        else:
            _bot.reply_to(message, result)
        return
    _bot.reply_to(message, "\\n".join(lines))

def cmd_deposit(message):
    p = db.get_player(message.from_user.id)
    if not p: _bot.reply_to(message, "❗ /start first"); return
    args = message.text.split()
    if len(args) < 2:
        limit = db.get_bank_limit(message.from_user.id)
        _bot.reply_to(message,
            f"🏦 *Bank Deposit*\\nUsage: `/deposit [amount]` or `/deposit all`\\n\\n"
            f"💡 Your bank limit: *{limit:,}* chips\\nUpgrade with /bankupgrade!")
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
            f"✅ Deposited *{result:,}* chips!\\n"
            f"🏦 Bank: *{new['bank']:,}* / *{db.get_bank_limit(message.from_user.id):,}*\\n"
            f"👛 Wallet: *{new['chips']:,}*")
    else:
        _bot.reply_to(message, result)

'''
content = content.replace("def register_features(", bank_cmds + "def register_features(")

with open("features.py", "w") as f:
    f.write(content)
print("✅ features.py patched")
EOF

echo ""
echo "🚀 Pushing to git..."
git add .
git commit -m "wins/losses ratio, bank upgrade tiers, min bet fix, minigames"
git push

echo ""
echo "✅ All done!"
