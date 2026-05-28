"""bounty.py — Bounty System
- Place a chip bounty on any player
- Multiple players can stack bounties on same target
- Anyone who successfully robs the target collects all bounties
- Bounties expire after 24 hours if not collected
- Can't place bounty on yourself or your spouse
"""
from datetime import datetime, timedelta
from telebot import types
import database as db

_bot = None

def fmt(n): return f"{n:,}"

# ── DB init ───────────────────────────────────────────────────────────
def init_bounty_db():
    is_pg = db.get_conn()[1] == "pg"
    db.execute("""
        CREATE TABLE IF NOT EXISTS bounties (
            id """ + ("SERIAL" if is_pg else "INTEGER") + """ PRIMARY KEY,
            target_id BIGINT NOT NULL,
            placer_id BIGINT NOT NULL,
            amount BIGINT NOT NULL,
            placed_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            collected INTEGER DEFAULT 0
        )
    """)
    print("✅ Bounty loaded")

# ── Helpers ───────────────────────────────────────────────────────────
def get_active_bounties(target_id):
    now = datetime.utcnow().isoformat()
    return db.execute(
        "SELECT id, placer_id, amount, placed_at FROM bounties WHERE target_id=? AND collected=0 AND expires_at>?",
        (target_id, now), fetch="all"
    ) or []

def get_total_bounty(target_id):
    rows = get_active_bounties(target_id)
    return sum(r[2] for r in rows)

def get_all_active_bounties():
    now = datetime.utcnow().isoformat()
    return db.execute(
        "SELECT target_id, SUM(amount) as total FROM bounties WHERE collected=0 AND expires_at>? GROUP BY target_id ORDER BY total DESC",
        (now,), fetch="all"
    ) or []

def collect_bounty(target_id):
    """Mark all bounties on target as collected, return total amount"""
    now = datetime.utcnow().isoformat()
    rows = db.execute(
        "SELECT id, amount FROM bounties WHERE target_id=? AND collected=0 AND expires_at>?",
        (target_id, now), fetch="all"
    ) or []
    if not rows:
        return 0
    total = sum(r[1] for r in rows)
    ids   = [r[0] for r in rows]
    for bid in ids:
        db.execute("UPDATE bounties SET collected=1 WHERE id=?", (bid,))
    return total

# ── Commands ──────────────────────────────────────────────────────────
def cmd_bounty(message):
    p = db.get_player(message.from_user.id)
    if not p: _bot.reply_to(message, "❗ Register first with /start"); return

    args = message.text.split()

    # /bounty — show active bounties
    if len(args) == 1:
        rows = get_all_active_bounties()
        if not rows:
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔄 Refresh", callback_data="bounty_refresh"))
            _bot.reply_to(message,
                "🎯 *Active Bounties*\n\nNo bounties posted yet!\n"
                "Use `/bounty @user [amount]` to place one.",
                reply_markup=markup)
            return

        lines = ["🎯 *Active Bounties*\n"]
        medals = ["🥇","🥈","🥉"]
        for i, (tid, total) in enumerate(rows[:10]):
            target = db.get_player(tid)
            name   = target["first_name"] if target else "Unknown"
            medal  = medals[i] if i < 3 else f"{i+1}."
            lines.append(f"{medal} *{name}* — 💰 {fmt(total)} chips")

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔄 Refresh", callback_data="bounty_refresh"))
        _bot.reply_to(message, "\n".join(lines), reply_markup=markup)
        return

    # /bounty @user [amount]
    if not message.reply_to_message and len(args) < 3:
        _bot.reply_to(message, "Usage: Reply to a message or use `/bounty @username [amount]`")
        return

    # Get target from reply or username
    target_id = None
    target_p  = None

    if message.reply_to_message:
        target_id = message.reply_to_message.from_user.id
        target_p  = db.get_player(target_id)
        try: amount = int(args[1].replace(",", ""))
        except: _bot.reply_to(message, "❌ Invalid amount."); return
    else:
        username = args[1].lstrip("@")
        # Find player by username
        row = db.execute("SELECT * FROM players WHERE username=?", (username,), fetch="one")
        if not row:
            _bot.reply_to(message, f"❌ Player @{username} not found."); return
        cols = ["user_id","username","first_name","chips","bank","wins","losses",
                "last_daily","last_rob","last_interest","last_game","vip","xp"]
        target_p = dict(zip(cols, row))
        target_id = target_p["user_id"]
        try: amount = int(args[2].replace(",", ""))
        except: _bot.reply_to(message, "❌ Invalid amount."); return

    uid = message.from_user.id

    # Validations
    if not target_p:
        _bot.reply_to(message, "❌ Player not found."); return
    if target_id == uid:
        _bot.reply_to(message, "❌ You can't put a bounty on yourself!"); return
    if amount < 1000:
        _bot.reply_to(message, "❌ Minimum bounty is *1,000* chips."); return
    if p["chips"] < amount:
        _bot.reply_to(message, f"❌ Not enough chips! Have: *{fmt(p['chips'])}*"); return

    # Check spouse
    spouse_id = p.get("spouse_id") or p.get("married_to")
    if spouse_id and str(spouse_id) == str(target_id):
        _bot.reply_to(message, "❌ You can't put a bounty on your spouse! 💍"); return

    # Place bounty
    db.update_chips(uid, -amount)
    now     = datetime.utcnow()
    expires = (now + timedelta(hours=24)).isoformat()
    db.execute(
        "INSERT INTO bounties (target_id, placer_id, amount, placed_at, expires_at) VALUES (?,?,?,?,?)",
        (target_id, uid, amount, now.isoformat(), expires)
    )

    total_on_target = get_total_bounty(target_id)
    target_name     = target_p["first_name"]

    _bot.reply_to(message,
        f"🎯 *Bounty placed on {target_name}!*\n\n"
        f"💰 Your bounty: *{fmt(amount)}* chips\n"
        f"💰 Total bounty: *{fmt(total_on_target)}* chips\n"
        f"⏰ Expires in: *24 hours*\n\n"
        f"Anyone who robs *{target_name}* successfully will collect the bounty! 🔫")

def cmd_mybounty(message):
    """Show bounties on yourself"""
    uid   = message.from_user.id
    p     = db.get_player(uid)
    if not p: _bot.reply_to(message, "❗ Register first with /start"); return

    rows  = get_active_bounties(uid)
    total = sum(r[2] for r in rows)

    if not rows:
        _bot.reply_to(message, "🎯 No active bounties on your head. You're safe! 😌")
        return

    lines = [f"🎯 *Bounties on your head*\n\n💰 Total: *{fmt(total)}* chips\n"]
    for bid, placer_id, amount, placed_at in rows:
        placer = db.get_player(placer_id)
        pname  = placer["first_name"] if placer else "Unknown"
        lines.append(f"• *{pname}* — {fmt(amount)} chips")

    lines.append(f"\n⚠️ Stay safe and don't get robbed!")
    _bot.reply_to(message, "\n".join(lines))

# ── Callback ──────────────────────────────────────────────────────────
def cb_bounty(call):
    if call.data == "bounty_refresh":
        rows = get_all_active_bounties()
        if not rows:
            try:
                _bot.edit_message_text(
                    "🎯 *Active Bounties*\n\nNo bounties posted yet!\n"
                    "Use `/bounty @user [amount]` to place one.",
                    call.message.chat.id, call.message.message_id,
                    reply_markup=call.message.reply_markup, parse_mode="Markdown"
                )
            except: pass
            _bot.answer_callback_query(call.id, "No active bounties")
            return

        lines = ["🎯 *Active Bounties*\n"]
        medals = ["🥇","🥈","🥉"]
        for i, (tid, total) in enumerate(rows[:10]):
            target = db.get_player(tid)
            name   = target["first_name"] if target else "Unknown"
            medal  = medals[i] if i < 3 else f"{i+1}."
            lines.append(f"{medal} *{name}* — 💰 {fmt(total)} chips")

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔄 Refresh", callback_data="bounty_refresh"))
        try:
            _bot.edit_message_text(
                "\n".join(lines),
                call.message.chat.id, call.message.message_id,
                reply_markup=markup, parse_mode="Markdown"
            )
        except: pass
        _bot.answer_callback_query(call.id, "Refreshed!")

# ── Hook into rob system ───────────────────────────────────────────────
def check_and_pay_bounty(robber_id, target_id, chat_id):
    """Call this after a successful rob — pays out any bounties"""
    total = collect_bounty(target_id)
    if total <= 0:
        return
    db.update_chips(robber_id, total)
    robber = db.get_player(robber_id)
    target = db.get_player(target_id)
    robber_name = robber["first_name"] if robber else "Unknown"
    target_name = target["first_name"] if target else "Unknown"
    try:
        _bot.send_message(chat_id,
            f"🎯 *BOUNTY COLLECTED!*\n\n"
            f"🔫 *{robber_name}* collected the bounty on *{target_name}*!\n"
            f"💰 Bounty reward: *{fmt(total)}* chips!")
    except: pass

# ── Register ──────────────────────────────────────────────────────────
def register_bounty(bot_instance):
    global _bot
    _bot = bot_instance
    init_bounty_db()
    bot_instance.register_message_handler(cmd_bounty,   commands=["bounty", "bounties"])
    bot_instance.register_message_handler(cmd_mybounty, commands=["mybounty"])
    bot_instance.register_callback_query_handler(
        cb_bounty,
        func=lambda c: c.data.startswith("bounty_")
    )
