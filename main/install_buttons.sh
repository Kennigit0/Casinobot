#!/data/data/com.termux/files/usr/bin/bash
cd ~/casino_bot

echo "🔧 Adding buttons + fixing deposit bug..."

python3 << 'EOF'
with open("features.py", "r") as f:
    content = f.read()

# ── Fix deposit bug (bank_deposit now returns ok, msg but old caller didn't check) ──
# Already handled by new cmd_deposit we added — just make sure old one is removed
# Remove any duplicate /deposit handler registration
content = content.replace(
    '        (["deposit"],                  cmd_deposit),\n        (["deposit"],                  cmd_deposit),',
    '        (["deposit"],                  cmd_deposit),'
)

# ── Replace all button commands ──
button_cmds = '''
from telebot import types as _types

def _btn(text, data): return _types.InlineKeyboardButton(text, callback_data=data)
def _markup(*rows):
    m = _types.InlineKeyboardMarkup()
    for row in rows: m.row(*row)
    return m

# ── /bank ──────────────────────────────────────────────────────────────
def cmd_bank(message):
    p = db.get_player(message.from_user.id)
    if not p: _bot.reply_to(message, "❗ /start first"); return
    bank     = p.get("bank") or 0
    lvl      = p.get("bank_level") or 0
    info     = db.BANK_LEVELS[lvl]
    limit    = info["limit"]
    pct      = f"{bank/limit*100:.1f}%" if limit < 999_999_999 else "MAX"
    markup   = _markup(
        [_btn("💰 Deposit", "bank_dep"), _btn("💸 Withdraw", "bank_with")],
        [_btn("📈 Interest", "bank_int"), _btn("⬆️ Upgrade", "bank_upg")],
    )
    _bot.reply_to(message,
        f"🏦 *Your Bank*\\n\\n"
        f"👛 Wallet: *{fmt(p['chips'])}*\\n"
        f"🏦 Bank:   *{fmt(bank)}* / *{fmt(limit)}* ({pct})\\n"
        f"🏅 Tier: *{info['name']}* (Lv.{lvl})\\n\\n"
        f"💡 Deposit to earn 3% daily interest!", reply_markup=markup)

# ── /bankupgrade ───────────────────────────────────────────────────────
def cmd_bankupgrade(message):
    _show_bankupgrade(message.from_user.id, message)

def _show_bankupgrade(uid, message):
    p   = db.get_player(uid)
    lvl = p.get("bank_level") or 0
    lines = ["🏦 *Bank Upgrade Tiers*\\n"]
    for l, data in db.BANK_LEVELS.items():
        arrow = " ◀ *YOU*" if l == lvl else ""
        cost  = f"{data['upgrade_cost']:,}" if data["upgrade_cost"] else "MAX"
        limit = f"{data['limit']:,}" if data["limit"] < 999_999_999 else "Unlimited"
        lines.append(f"Lv.{l} *{data['name']}* — {limit} chips | Cost: {cost}{arrow}")
    markup = None
    if lvl < 6:
        cost = db.BANK_LEVELS[lvl]["upgrade_cost"]
        lines.append(f"\\n💡 Upgrade to *{db.BANK_LEVELS[lvl+1]['name']}* for *{cost:,}* chips")
        markup = _markup([_btn(f"⬆️ Upgrade for {cost:,} chips", "bank_upg_confirm")])
    else:
        lines.append("\\n✅ Max level reached!")
    _bot.reply_to(message, "\\n".join(lines), reply_markup=markup)

# ── /interest ──────────────────────────────────────────────────────────
def cmd_interest(message):
    p = db.get_player(message.from_user.id)
    if not p: _bot.reply_to(message, "❗ /start first"); return
    markup = _markup([_btn("📈 Claim 3% Interest", "bank_int")])
    bank   = p.get("bank") or 0
    est    = int(bank * 0.03)
    _bot.reply_to(message,
        f"📈 *Daily Interest*\\n\\n"
        f"🏦 Bank balance: *{fmt(bank)}*\\n"
        f"💰 Est. interest: *{fmt(est)}* chips (3%)\\n\\n"
        f"Claim once per day!", reply_markup=markup)

# ── /profile ───────────────────────────────────────────────────────────
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
    wins     = p.get("wins") or 0
    losses   = p.get("losses") or 0
    total_g  = wins + losses
    ratio    = f"{wins/total_g*100:.1f}%" if total_g > 0 else "N/A"
    bank_lvl = p.get("bank_level") or 0
    info     = db.BANK_LEVELS[bank_lvl]
    limit    = info["limit"]
    pct      = f"{bank/limit*100:.1f}%" if limit < 999_999_999 else "MAX"
    married  = ""
    if p.get("married_to") and p["married_to"] != 0:
        spouse = db.get_player(p["married_to"])
        if spouse: married = f"\\n💍 Married to: *{spouse['first_name']}*"
    markup = _markup(
        [_btn("💰 Deposit", "bank_dep"), _btn("💸 Withdraw", "bank_with")],
        [_btn("⬆️ Bank Upgrade", "bank_upg"), _btn("📈 Interest", "bank_int")],
    )
    _bot.reply_to(message,
        f"👤 *{p['first_name']}\\'s Profile*\\n\\n"
        f"🏅 Status: {vip_tag}\\n"
        f"⭐ Level: *{level}* — {title}\\n"
        f"✨ XP: *{fmt(xp)}*\\n"
        f"👛 Wallet: *{fmt(p['chips'])}*\\n"
        f"🏦 Bank: *{fmt(bank)}* / *{fmt(limit)}* ({pct})\\n"
        f"🏦 Tier: *{info['name']}* Lv.{bank_lvl}\\n"
        f"💰 Total: *{fmt(p['chips'] + bank)}*\\n\\n"
        f"🎮 Played: *{total_g}* | ✅ *{wins}* | ❌ *{losses}*\\n"
        f"📊 Win Rate: *{ratio}*"
        f"{married}", reply_markup=markup)

# ── /leaderboard ───────────────────────────────────────────────────────
def cmd_leaderboard(message):
    args = message.text.split()
    by   = "xp" if len(args) > 1 and args[1].lower() == "xp" else "chips"
    _send_leaderboard(message, by)

def _send_leaderboard(message, by):
    rows   = db.get_leaderboard(10, by)
    title  = "🏆 *Top 10 — Richest*" if by == "chips" else "⭐ *Top 10 — XP*"
    lines  = [f"{title}\\n"]
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
    _bot.reply_to(message, "\\n".join(lines), reply_markup=markup)

# ── /shop ──────────────────────────────────────────────────────────────
def cmd_shop(message):
    markup = _markup(
        [_btn("🎣 Fishing Rods", "shop_fishing")],
        [_btn("⛏️ Pickaxes",     "shop_mining")],
        [_btn("🌾 Farming Tools", "shop_farming")],
    )
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
    lines = ["🎒 *Your Inventory*\\n"]
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
    _bot.reply_to(message, "\\n".join(lines), reply_markup=markup)

# ── /games ─────────────────────────────────────────────────────────────
def cmd_games(message):
    markup = _markup(
        [_btn("🎰 Slots",     "game_slots"), _btn("🎲 Dice",  "game_dice")],
        [_btn("🃏 Blackjack", "game_bj"),    _btn("🎡 Roulette","game_rl")],
        [_btn("🎲 Risk Bet",  "game_rbet")],
    )
    _bot.reply_to(message,
        "🎮 *Casino Games*\\n\\nPick a game — then send your bet amount!\\n"
        "Example: after picking Slots → `/slots 500`", reply_markup=markup)

# ── /deposit fix ───────────────────────────────────────────────────────
def cmd_deposit(message):
    p = db.get_player(message.from_user.id)
    if not p: _bot.reply_to(message, "❗ /start first"); return
    args = message.text.split()
    if len(args) < 2:
        limit = db.get_bank_limit(message.from_user.id)
        _bot.reply_to(message,
            f"🏦 *Bank Deposit*\\nUsage: `/deposit [amount]` or `/deposit all`\\n\\n"
            f"💡 Your bank limit: *{fmt(limit)}* chips\\nUpgrade with /bankupgrade!")
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
            f"✅ Deposited *{fmt(result)}* chips!\\n"
            f"🏦 Bank: *{fmt(new['bank'])}* / *{fmt(db.get_bank_limit(message.from_user.id))}*\\n"
            f"👛 Wallet: *{fmt(new['chips'])}*")
    else:
        markup = _markup([_btn("⬆️ Upgrade Bank", "bank_upg")])
        _bot.reply_to(message, result, reply_markup=markup)

# ── Callbacks ───────────────────────────────────────────────────────────
def handle_bank_callbacks(call):
    uid  = call.from_user.id
    data = call.data
    p    = db.get_player(uid)
    if not p: _bot.answer_callback_query(call.id, "Register first! /start"); return

    if data == "bank_dep":
        _bot.answer_callback_query(call.id)
        _bot.send_message(call.message.chat.id,
            f"💰 Send: `/deposit [amount]` or `/deposit all`\\n"
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
                f"📈 Interest claimed! +*{fmt(bonus)}* chips\\n"
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
                f"✅ Bank upgraded to *{result['name']}*!\\n"
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
        _bot.send_message(call.message.chat.id, f"🛒 Use `/shop {cat}` to see items and `/buy [item]` to purchase!")

    elif data.startswith("equip_"):
        tool = data.replace("equip_","")
        _bot.answer_callback_query(call.id)
        _bot.send_message(call.message.chat.id, f"Use `/equip {tool}` to equip it!")

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

'''

# Remove old cmd_profile, cmd_bankupgrade, cmd_deposit, cmd_bank, cmd_leaderboard, cmd_interest if duplicated
import re
# Insert button_cmds before register_features
content = content.replace("def register_features(", button_cmds + "def register_features(")

# Update registration to include all new commands + callback
old_reg_end = "bot_instance.register_message_handler"
# Add callback handler inside register_features
content = content.replace(
    "def register_features(bot_instance):",
    "def register_features(bot_instance):\n"
    "    bot_instance.register_callback_query_handler(\n"
    "        handle_bank_callbacks,\n"
    "        func=lambda c: c.data in ['bank_dep','bank_with','bank_int','bank_upg','bank_upg_confirm','lb_chips','lb_xp']\n"
    "            or c.data.startswith('shop_') or c.data.startswith('equip_') or c.data.startswith('game_')\n"
    "    )"
)

# Register /games and /interest
content = content.replace(
    '(["profile", "me"],     cmd_profile),',
    '(["profile", "me"],     cmd_profile),\n        (["games","game"],        cmd_games),\n        (["interest"],            cmd_interest),\n        (["bank"],                cmd_bank),\n        (["leaderboard","top","lb"], cmd_leaderboard),\n        (["shop"],                cmd_shop),\n        (["inventory"],           cmd_inventory),'
)

with open("features.py", "w") as f:
    f.write(content)
print("✅ features.py updated with all buttons")
EOF

echo ""
echo "🚀 Pushing to git..."
git add .
git commit -m "buttons for bank, profile, leaderboard, shop, inventory, games + deposit fix"
git push

echo ""
echo "✅ All done!"
