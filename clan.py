"""clan.py — Clan System
Commands:
  /clan                   — show your clan or clan menu
  /clan create <name>     — create a clan (costs 50,000 chips)
  /clan join <name>       — join an open clan
  /clan leave             — leave your clan
  /clan info [name]       — show clan details
  /clan deposit <amount>  — deposit to clan bank
  /clan withdraw <amount> — leader withdraws from clan bank
  /clan kick @user        — leader kicks a member
  /clan promote @user     — leader promotes to officer
  /clan heist             — start a clan-exclusive heist
  /clan top               — clan leaderboard
"""
import random, threading, time
from datetime import datetime, timedelta
from telebot import types
import database as db
import gems as gems_mod

_bot = None

def fmt(n): return f"{n:,}"

def _rv(row, key, idx):
    if row is None: return None
    return row[key] if isinstance(row, dict) else row[idx]

# ── Clan levels ───────────────────────────────────────────────────────
CLAN_LEVELS = {
    1: {"name": "Rookie",    "max_members": 10,  "upgrade_cost": 100},
    2: {"name": "Rising",    "max_members": 20,  "upgrade_cost": 250},
    3: {"name": "Elite",     "max_members": 35,  "upgrade_cost": 500},
    4: {"name": "Champion",  "max_members": 50,  "upgrade_cost": 1000},
    5: {"name": "Legendary", "max_members": 100, "upgrade_cost": None},
}
CREATE_COST_GEMS = 50  # gems

# ── DB init ───────────────────────────────────────────────────────────
def init_clan_db():
    is_pg = db.get_conn()[1] == "pg"
    auto  = "SERIAL" if is_pg else "INTEGER"

    db.execute(f"""
        CREATE TABLE IF NOT EXISTS clans (
            id          {auto} PRIMARY KEY,
            name        TEXT UNIQUE NOT NULL,
            tag         TEXT,
            leader_id   BIGINT NOT NULL,
            bank        BIGINT DEFAULT 0,
            level       INTEGER DEFAULT 1,
            xp          BIGINT DEFAULT 0,
            description TEXT DEFAULT '',
            created_at  TEXT NOT NULL
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS clan_members (
            user_id     BIGINT PRIMARY KEY,
            clan_id     INTEGER NOT NULL,
            role        TEXT DEFAULT 'member',
            contribution BIGINT DEFAULT 0,
            joined_at   TEXT NOT NULL
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS clan_heists (
            id          """ + auto + """ PRIMARY KEY,
            clan_id     INTEGER NOT NULL,
            started_by  BIGINT NOT NULL,
            reward      BIGINT DEFAULT 0,
            status      TEXT DEFAULT 'pending',
            started_at  TEXT NOT NULL
        )
    """)
    print("✅ Clan loaded")

# ── Helpers ───────────────────────────────────────────────────────────
def get_clan_by_id(clan_id):
    return db.execute("SELECT * FROM clans WHERE id=?", (clan_id,), fetch="one")

def get_clan_by_name(name):
    return db.execute("SELECT * FROM clans WHERE LOWER(name)=LOWER(?)", (name,), fetch="one")

def get_member(user_id):
    return db.execute("SELECT * FROM clan_members WHERE user_id=?", (user_id,), fetch="one")

def get_clan_members(clan_id):
    return db.execute("SELECT * FROM clan_members WHERE clan_id=?", (clan_id,), fetch="all") or []

def get_member_count(clan_id):
    row = db.execute("SELECT COUNT(*) as cnt FROM clan_members WHERE clan_id=?", (clan_id,), fetch="one")
    return _rv(row, "cnt", 0) or 0

def clan_val(clan, key):
    return _rv(clan, key, {
        "id":0,"name":1,"tag":2,"leader_id":3,"bank":4,
        "level":5,"xp":6,"description":7,"created_at":8
    }.get(key, 0))

def member_val(m, key):
    return _rv(m, key, {"user_id":0,"clan_id":1,"role":2,"contribution":3,"joined_at":4}.get(key,0))

# ── Commands ──────────────────────────────────────────────────────────
def cmd_clan(message):
    p = db.get_player(message.from_user.id)
    if not p: _bot.reply_to(message, "❗ Register first with /start"); return

    args = message.text.split(None, 2)
    sub  = args[1].lower() if len(args) > 1 else None

    if sub is None:          return _clan_status(message, p)
    if sub == "create":      return _clan_create(message, p, args)
    if sub == "join":        return _clan_join(message, p, args)
    if sub == "leave":       return _clan_leave(message, p)
    if sub == "info":        return _clan_info(message, p, args)
    if sub == "deposit":     return _clan_deposit(message, p, args)
    if sub == "withdraw":    return _clan_withdraw(message, p, args)
    if sub == "kick":        return _clan_kick(message, p, args)
    if sub == "promote":     return _clan_promote(message, p, args)
    if sub in ("boss","raid","heist"): return _clan_raid(message, p)
    if sub in ("top","lb"):  return _clan_top(message)
    if sub == "upgrade":     return _clan_upgrade(message, p)
    if sub == "desc":        return _clan_desc(message, p, args)

    _bot.reply_to(message,
        "⚔️ *Clan Commands*\n\n"
        "`/clan` — your clan info\n"
        "`/clan create <name>` — create clan (50,000 chips)\n"
        "`/clan join <name>` — join a clan\n"
        "`/clan leave` — leave your clan\n"
        "`/clan info [name]` — clan details\n"
        "`/clan deposit <amount>` — deposit to clan bank\n"
        "`/clan withdraw <amount>` — leader withdraws\n"
        "`/clan kick @user` — kick a member\n"
        "`/clan promote @user` — promote to officer\n"
        "`/clan heist` — start clan heist\n"
        "`/clan upgrade` — upgrade clan level\n"
        "`/clan top` — clan leaderboard")

def _clan_status(message, p):
    uid  = message.from_user.id
    mem  = get_member(uid)
    if not mem:
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("⚔️ Create Clan", callback_data="clan_create_prompt"),
            types.InlineKeyboardButton("🔍 Browse Clans", callback_data="clan_browse"),
        )
        _bot.reply_to(message,
            "⚔️ *You're not in a clan!*\n\n"
            f"Create your own for *{CREATE_COST_GEMS}* 💎 gems\n"
            "or join an existing one.\n\n"
            "`/clan create <name>` — start your clan\n"
            "`/clan join <name>` — join existing\n"
            "`/clan top` — see top clans",
            reply_markup=markup); return

    clan_id = member_val(mem, "clan_id")
    clan    = get_clan_by_id(clan_id)
    if not clan: _bot.reply_to(message, "❌ Clan not found."); return

    _show_clan(message, clan, mem)

def _show_clan(message, clan, my_mem=None, edit=False, call=None):
    cid     = clan_val(clan, "id")
    name    = clan_val(clan, "name")
    tag     = clan_val(clan, "tag") or ""
    bank    = clan_val(clan, "bank") or 0
    level   = clan_val(clan, "level") or 1
    xp      = clan_val(clan, "xp") or 0
    desc    = clan_val(clan, "description") or ""
    leader  = clan_val(clan, "leader_id")
    lvl_info= CLAN_LEVELS[level]
    members = get_clan_members(cid)
    count   = len(members)

    leader_p = db.get_player(leader)
    lname    = leader_p["first_name"] if leader_p else "Unknown"

    next_cost = CLAN_LEVELS.get(level+1, {}).get("upgrade_cost")
    next_str  = f"{next_cost} 💎 gems" if next_cost else "MAX"

    my_role = member_val(my_mem, "role") if my_mem else ""
    my_contrib = member_val(my_mem, "contribution") if my_mem else 0

    text = (
        f"⚔️ *{name}* {f'[{tag}]' if tag else ''}\n"
        f"{'─'*22}\n"
        f"{f'_{desc}_' + chr(10) if desc else ''}"
        f"👑 Leader: *{lname}*\n"
        f"🏅 Level: *{level}* — {lvl_info['name']}\n"
        f"👥 Members: *{count}/{lvl_info['max_members']}*\n"
        f"🏦 Clan Bank: *{fmt(bank)}* chips\n"
        f"⭐ Clan XP: *{fmt(xp)}*\n"
        f"📈 Next level: *{next_str}*\n"
    )
    if my_mem:
        text += f"\n🎖️ Your role: *{my_role.title()}*\n💰 Your contribution: *{fmt(my_contrib)}*"

    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("👥 Members", callback_data=f"clan_members_{cid}"),
        types.InlineKeyboardButton("🔄 Refresh",  callback_data=f"clan_refresh_{cid}"),
    )
    if my_role in ("leader", "officer"):
        markup.add(types.InlineKeyboardButton("⬆️ Upgrade Clan", callback_data=f"clan_upgrade_{cid}"))

    if edit and call:
        try:
            _bot.edit_message_text(text, call.message.chat.id,
                call.message.message_id, reply_markup=markup, parse_mode="Markdown")
        except: pass
    else:
        _bot.reply_to(message, text, reply_markup=markup)

def _clan_create(message, p, args):
    uid = message.from_user.id
    if get_member(uid):
        _bot.reply_to(message, "❌ You're already in a clan! Leave first with `/clan leave`"); return
    if len(args) < 3:
        _bot.reply_to(message, "Usage: `/clan create <name>`\nExample: `/clan create Dragons`"); return

    name = args[2].strip()[:20]
    if len(name) < 3:
        _bot.reply_to(message, "❌ Clan name must be at least 3 characters."); return
    if not name.replace(" ","").replace("_","").replace("-","").isalnum():
        _bot.reply_to(message, "❌ Clan name can only contain letters, numbers, spaces, - and _"); return

    player_gems = gems_mod.get_gems(uid)
    if player_gems < CREATE_COST_GEMS:
        _bot.reply_to(message, f"❌ Need *{CREATE_COST_GEMS}* 💎 gems to create a clan.\nYou have: *{player_gems}* gems."); return

    existing = get_clan_by_name(name)
    if existing:
        _bot.reply_to(message, f"❌ A clan named *{name}* already exists!"); return

    gems_mod.spend_gems(uid, CREATE_COST_GEMS)
    now = datetime.utcnow().isoformat()
    db.execute(
        "INSERT INTO clans (name, leader_id, created_at) VALUES (?,?,?)",
        (name, uid, now)
    )
    clan = get_clan_by_name(name)
    clan_id = clan_val(clan, "id")
    db.execute(
        "INSERT INTO clan_members (user_id, clan_id, role, joined_at) VALUES (?,?,?,?)",
        (uid, clan_id, "leader", now)
    )
    _bot.reply_to(message,
        f"⚔️ *Clan '{name}' created!*\n\n"
        f"💎 Paid: *{CREATE_COST_GEMS}* gems\n"
        f"👥 Max members: *10* (upgrade to increase)\n\n"
        f"Invite players with: `/clan join {name}`\n"
        f"Set description: `/clan desc <text>`\n"
        f"Start heist: `/clan heist`")

def _clan_join(message, p, args):
    uid = message.from_user.id
    if get_member(uid):
        _bot.reply_to(message, "❌ Already in a clan! Leave first with `/clan leave`"); return
    if len(args) < 3:
        _bot.reply_to(message, "Usage: `/clan join <name>`"); return

    name = args[2].strip()
    clan = get_clan_by_name(name)
    if not clan:
        _bot.reply_to(message, f"❌ Clan *{name}* not found."); return

    cid     = clan_val(clan, "id")
    level   = clan_val(clan, "level") or 1
    max_mem = CLAN_LEVELS[level]["max_members"]
    count   = get_member_count(cid)

    if count >= max_mem:
        _bot.reply_to(message, f"❌ *{name}* is full! ({count}/{max_mem} members)"); return

    db.execute(
        "INSERT INTO clan_members (user_id, clan_id, role, joined_at) VALUES (?,?,?,?)",
        (uid, cid, "member", datetime.utcnow().isoformat())
    )
    _bot.reply_to(message,
        f"⚔️ Joined *{name}*!\n\n"
        f"👥 Members: *{count+1}/{max_mem}*\n"
        f"Use `/clan` to see clan info.")

def _clan_leave(message, p):
    uid = message.from_user.id
    mem = get_member(uid)
    if not mem:
        _bot.reply_to(message, "❌ You're not in a clan."); return

    clan_id = member_val(mem, "clan_id")
    role    = member_val(mem, "role")

    if role == "leader":
        members = get_clan_members(clan_id)
        if len(members) > 1:
            _bot.reply_to(message,
                "❌ Transfer leadership first!\n"
                "Use `/clan promote @user` to promote someone, then leave."); return
        # Last member — disband clan
        db.execute("DELETE FROM clans WHERE id=?", (clan_id,))
        db.execute("DELETE FROM clan_members WHERE clan_id=?", (clan_id,))
        _bot.reply_to(message, "⚔️ Clan disbanded since you were the last member."); return

    db.execute("DELETE FROM clan_members WHERE user_id=?", (uid,))
    _bot.reply_to(message, "✅ Left the clan.")

def _clan_info(message, p, args):
    if len(args) >= 3:
        clan = get_clan_by_name(args[2].strip())
        if not clan:
            _bot.reply_to(message, f"❌ Clan not found."); return
    else:
        mem = get_member(message.from_user.id)
        if not mem:
            _bot.reply_to(message, "❌ You're not in a clan. Use `/clan info <name>`"); return
        clan = get_clan_by_id(member_val(mem, "clan_id"))

    _show_clan(message, clan)

def _clan_deposit(message, p, args):
    uid = message.from_user.id
    mem = get_member(uid)
    if not mem:
        _bot.reply_to(message, "❌ You're not in a clan."); return
    if len(args) < 3:
        _bot.reply_to(message, "Usage: `/clan deposit <amount>`"); return
    try: amount = int(args[2].replace(",",""))
    except: _bot.reply_to(message, "❌ Invalid amount."); return
    if amount <= 0:
        _bot.reply_to(message, "❌ Amount must be positive."); return
    if p["chips"] < amount:
        _bot.reply_to(message, f"❌ Not enough chips! Have: *{fmt(p['chips'])}*"); return

    clan_id = member_val(mem, "clan_id")
    db.update_chips(uid, -amount)
    db.execute("UPDATE clans SET bank=bank+? WHERE id=?", (amount, clan_id))
    db.execute("UPDATE clan_members SET contribution=contribution+? WHERE user_id=?", (amount, uid))
    clan = get_clan_by_id(clan_id)
    new_bank = clan_val(clan, "bank")
    _bot.reply_to(message,
        f"🏦 Deposited *{fmt(amount)}* chips to clan bank!\n"
        f"🏦 Clan Bank: *{fmt(new_bank)}*")

def _clan_withdraw(message, p, args):
    uid = message.from_user.id
    mem = get_member(uid)
    if not mem or member_val(mem, "role") != "leader":
        _bot.reply_to(message, "❌ Only the clan leader can withdraw."); return
    if len(args) < 3:
        _bot.reply_to(message, "Usage: `/clan withdraw <amount>`"); return
    try: amount = int(args[2].replace(",",""))
    except: _bot.reply_to(message, "❌ Invalid amount."); return
    if amount <= 0:
        _bot.reply_to(message, "❌ Amount must be positive."); return

    clan_id = member_val(mem, "clan_id")
    clan    = get_clan_by_id(clan_id)
    bank    = clan_val(clan, "bank") or 0
    if bank < amount:
        _bot.reply_to(message, f"❌ Clan bank only has *{fmt(bank)}* chips."); return

    db.execute("UPDATE clans SET bank=bank-? WHERE id=?", (amount, clan_id))
    db.update_chips(uid, amount)
    _bot.reply_to(message,
        f"💸 Withdrew *{fmt(amount)}* chips from clan bank!\n"
        f"🏦 Remaining: *{fmt(bank - amount)}*")

def _clan_kick(message, p, args):
    uid = message.from_user.id
    mem = get_member(uid)
    if not mem or member_val(mem, "role") not in ("leader", "officer"):
        _bot.reply_to(message, "❌ Only leader/officers can kick members."); return
    if not message.reply_to_message and len(args) < 3:
        _bot.reply_to(message, "Reply to a message or use `/clan kick @username`"); return

    target_id = None
    if message.reply_to_message:
        target_id = message.reply_to_message.from_user.id
    else:
        uname = args[2].lstrip("@")
        row   = db.execute("SELECT user_id FROM players WHERE LOWER(username)=LOWER(?)", (uname,), fetch="one")
        if not row: _bot.reply_to(message, "❌ Player not found."); return
        target_id = _rv(row, "user_id", 0)

    if target_id == uid:
        _bot.reply_to(message, "❌ Can't kick yourself."); return

    target_mem = get_member(target_id)
    if not target_mem or member_val(target_mem, "clan_id") != member_val(mem, "clan_id"):
        _bot.reply_to(message, "❌ That player is not in your clan."); return
    if member_val(target_mem, "role") == "leader":
        _bot.reply_to(message, "❌ Can't kick the leader."); return

    db.execute("DELETE FROM clan_members WHERE user_id=?", (target_id,))
    target_p = db.get_player(target_id)
    tname    = target_p["first_name"] if target_p else "Unknown"
    _bot.reply_to(message, f"👢 *{tname}* has been kicked from the clan.")

def _clan_promote(message, p, args):
    uid = message.from_user.id
    mem = get_member(uid)
    if not mem or member_val(mem, "role") != "leader":
        _bot.reply_to(message, "❌ Only the leader can promote members."); return
    if not message.reply_to_message and len(args) < 3:
        _bot.reply_to(message, "Reply to a message or use `/clan promote @username`"); return

    target_id = None
    if message.reply_to_message:
        target_id = message.reply_to_message.from_user.id
    else:
        uname = args[2].lstrip("@")
        row   = db.execute("SELECT user_id FROM players WHERE LOWER(username)=LOWER(?)", (uname,), fetch="one")
        if not row: _bot.reply_to(message, "❌ Player not found."); return
        target_id = _rv(row, "user_id", 0)

    target_mem = get_member(target_id)
    if not target_mem or member_val(target_mem, "clan_id") != member_val(mem, "clan_id"):
        _bot.reply_to(message, "❌ That player is not in your clan."); return

    cur_role = member_val(target_mem, "role")
    if cur_role == "leader":
        # Transfer leadership
        db.execute("UPDATE clan_members SET role='officer' WHERE user_id=?", (uid,))
        db.execute("UPDATE clan_members SET role='leader' WHERE user_id=?", (target_id,))
        db.execute("UPDATE clans SET leader_id=? WHERE id=?", (target_id, member_val(mem, "clan_id")))
        target_p = db.get_player(target_id)
        tname    = target_p["first_name"] if target_p else "Unknown"
        _bot.reply_to(message, f"👑 Leadership transferred to *{tname}*!")
    elif cur_role == "member":
        db.execute("UPDATE clan_members SET role='officer' WHERE user_id=?", (target_id,))
        target_p = db.get_player(target_id)
        tname    = target_p["first_name"] if target_p else "Unknown"
        _bot.reply_to(message, f"🎖️ *{tname}* promoted to Officer!")
    else:
        _bot.reply_to(message, "Already an officer or higher.")

def _clan_upgrade(message, p):
    uid = message.from_user.id
    mem = get_member(uid)
    if not mem or member_val(mem, "role") != "leader":
        _bot.reply_to(message, "❌ Only the leader can upgrade the clan."); return

    clan_id = member_val(mem, "clan_id")
    clan    = get_clan_by_id(clan_id)
    level   = clan_val(clan, "level") or 1
    bank    = clan_val(clan, "bank") or 0

    if level >= 5:
        _bot.reply_to(message, "🏆 Clan is already at max level!"); return

    next_info   = CLAN_LEVELS[level + 1]
    cost        = CLAN_LEVELS[level]["upgrade_cost"]
    leader_gems = gems_mod.get_gems(uid)

    if leader_gems < cost:
        _bot.reply_to(message,
            f"❌ Need *{cost}* 💎 gems to upgrade.\n"
            f"You have: *{leader_gems}* gems."); return

    gems_mod.spend_gems(uid, cost)
    db.execute("UPDATE clans SET level=level+1 WHERE id=?", (clan_id,))
    _bot.reply_to(message,
        f"⬆️ *Clan upgraded to Level {level+1}!*\n\n"
        f"🏅 Tier: *{next_info['name']}*\n"
        f"👥 Max members: *{next_info['max_members']}*\n"
        f"💎 Cost: *{cost}* gems (paid by leader)")

def _clan_top(message):
    rows = db.execute(
        "SELECT name, level, bank, leader_id, (SELECT COUNT(*) FROM clan_members WHERE clan_id=clans.id) as mc "
        "FROM clans ORDER BY bank DESC LIMIT 10",
        fetch="all"
    ) or []

    if not rows:
        _bot.reply_to(message, "🏆 No clans yet! Create one with `/clan create <name>`"); return

    medals = ["🥇","🥈","🥉"]
    lines  = ["🏆 *Top Clans*\n"]
    for i, row in enumerate(rows):
        name   = _rv(row, "name", 0)
        level  = _rv(row, "level", 1) or 1
        bank   = _rv(row, "bank", 2) or 0
        mc     = _rv(row, "mc", 4) or 0
        medal  = medals[i] if i < 3 else f"{i+1}."
        tier   = CLAN_LEVELS[level]["name"]
        lines.append(f"{medal} *{name}* — Lv.{level} {tier} | 👥{mc} | 🏦{fmt(bank)}")

    _bot.reply_to(message, "\n".join(lines))

def _clan_desc(message, p, args):
    uid = message.from_user.id
    mem = get_member(uid)
    if not mem or member_val(mem, "role") != "leader":
        _bot.reply_to(message, "❌ Only the leader can set the description."); return
    if len(args) < 3:
        _bot.reply_to(message, "Usage: `/clan desc Your clan description`"); return
    desc = args[2][:100]
    db.execute("UPDATE clans SET description=? WHERE id=?", (desc, member_val(mem, "clan_id")))
    _bot.reply_to(message, f"✅ Clan description updated!")

# ── Callbacks ─────────────────────────────────────────────────────────
def cb_clan(call):
    uid  = call.from_user.id
    data = call.data

    if data == "clan_create_prompt":
        _bot.answer_callback_query(call.id)
        _bot.send_message(call.message.chat.id,
            f"⚔️ Create a clan for *{fmt(CREATE_COST)}* chips!\n\n"
            "Usage: `/clan create <name>`\n"
            "Example: `/clan create Dragons`")
        return

    if data == "clan_browse":
        _bot.answer_callback_query(call.id)
        rows = db.execute(
            "SELECT name, level, (SELECT COUNT(*) FROM clan_members WHERE clan_id=clans.id) as mc "
            "FROM clans ORDER BY bank DESC LIMIT 8", fetch="all"
        ) or []
        if not rows:
            _bot.send_message(call.message.chat.id, "No clans yet! Be the first: `/clan create <name>`")
            return
        lines = ["🔍 *Open Clans*\n"]
        for row in rows:
            n  = _rv(row,"name",0)
            lv = _rv(row,"level",1) or 1
            mc = _rv(row,"mc",2) or 0
            max_m = CLAN_LEVELS[lv]["max_members"]
            if mc < max_m:
                lines.append(f"• *{n}* — Lv.{lv} | {mc}/{max_m} members — `/clan join {n}`")
        _bot.send_message(call.message.chat.id, "\n".join(lines) if len(lines)>1 else "All clans are full!")
        return

    if data.startswith("clan_members_"):
        clan_id = int(data.split("_")[-1])
        members = get_clan_members(clan_id)
        lines   = ["👥 *Clan Members*\n"]
        role_icon = {"leader":"👑","officer":"🎖️","member":"👤"}
        for m in members:
            mid   = member_val(m, "user_id")
            role  = member_val(m, "role")
            contrib = member_val(m, "contribution") or 0
            pl    = db.get_player(mid)
            pname = pl["first_name"] if pl else "Unknown"
            lines.append(f"{role_icon.get(role,'👤')} *{pname}* — {role.title()} | 💰{fmt(contrib)}")
        _bot.answer_callback_query(call.id)
        _bot.send_message(call.message.chat.id, "\n".join(lines))
        return

    if data.startswith("clan_refresh_"):
        clan_id = int(data.split("_")[-1])
        clan    = get_clan_by_id(clan_id)
        mem     = get_member(uid)
        if not clan: _bot.answer_callback_query(call.id, "Clan not found"); return
        _bot.answer_callback_query(call.id, "Refreshed!")
        _show_clan(None, clan, mem, edit=True, call=call)
        return

    if data.startswith("clan_upgrade_"):
        _bot.answer_callback_query(call.id)
        clan_id = int(data.split("_")[-1])
        clan    = get_clan_by_id(clan_id)
        mem     = get_member(uid)
        if not mem or member_val(mem, "role") != "leader":
            _bot.answer_callback_query(call.id, "Leaders only!", show_alert=True); return
        level = clan_val(clan, "level") or 1
        bank  = clan_val(clan, "bank") or 0
        cost  = CLAN_LEVELS[level].get("upgrade_cost")
        if not cost:
            _bot.send_message(call.message.chat.id, "Already max level!"); return
        leader_gems = gems_mod.get_gems(uid)
        if leader_gems < cost:
            _bot.send_message(call.message.chat.id,
                f"❌ Need *{cost}* 💎 gems to upgrade.\nYou have: *{leader_gems}* gems."); return
        gems_mod.spend_gems(uid, cost)
        db.execute("UPDATE clans SET level=level+1 WHERE id=?", (clan_id,))
        next_info = CLAN_LEVELS[level+1]
        _bot.send_message(call.message.chat.id,
            f"⬆️ *Upgraded to Level {level+1} — {next_info['name']}!*\n"
            f"👥 Max members: *{next_info['max_members']}*\n"
            f"💎 Cost: *{cost}* gems")

# ── Register ──────────────────────────────────────────────────────────
def register_clan(bot_instance):
    global _bot
    _bot = bot_instance
    init_clan_db()
    bot_instance.register_message_handler(cmd_clan, commands=["clan"])
    bot_instance.register_callback_query_handler(
        cb_clan, func=lambda c: c.data.startswith("clan_"))

# ── Boss Raid System ──────────────────────────────────────────────────
BOSSES = {
    1: {"name": "👹 Goblin King",    "hp": 1000,  "entry": 5_000,      "min_reward": 50_000,    "max_reward": 100_000},
    2: {"name": "🐉 Fire Drake",     "hp": 3000,  "entry": 20_000,     "min_reward": 200_000,   "max_reward": 500_000},
    3: {"name": "💀 Death Knight",   "hp": 8000,  "entry": 100_000,    "min_reward": 1_000_000, "max_reward": 3_000_000},
    4: {"name": "🌑 Shadow Demon",   "hp": 20000, "entry": 500_000,    "min_reward": 5_000_000, "max_reward": 10_000_000},
    5: {"name": "☠️ Ancient Dragon", "hp": 50000, "entry": 2_000_000,  "min_reward": 20_000_000,"max_reward": 50_000_000},
}

RAID_JOIN_TIME  = 120   # 2 min joining phase
RAID_ROUND_TIME = 60    # 60s per attack round
RAID_ROUNDS     = 3
RAID_COOLDOWN   = 86400 # 24 hours

active_raids = {}  # clan_id -> raid state

def get_last_raid(clan_id):
    row = db.execute(
        "SELECT started_at FROM clan_raids WHERE clan_id=? ORDER BY started_at DESC LIMIT 1",
        (clan_id,), fetch="one"
    )
    return _rv(row, "started_at", 0) if row else None

def init_raid_db():
    is_pg = db.get_conn()[1] == "pg"
    db.execute(f"""
        CREATE TABLE IF NOT EXISTS clan_raids (
            id         {"SERIAL" if is_pg else "INTEGER"} PRIMARY KEY,
            clan_id    BIGINT NOT NULL,
            boss_name  TEXT,
            result     TEXT,
            reward     BIGINT DEFAULT 0,
            raiders    INTEGER DEFAULT 0,
            started_at TEXT NOT NULL
        )
    """)

def _hp_bar(current, maximum, length=12):
    filled = max(0, int(current / maximum * length))
    return "🟥" * filled + "⬛" * (length - filled)

def _calc_damage(uid, role):
    p = db.get_player(uid)
    if not p: return 0
    xp    = p.get("xp") or 0
    level = db.xp_to_level(xp)
    dmg   = level * 50
    if random.random() < 0.20:
        dmg *= 2  # crit
    if role == "leader":   dmg = int(dmg * 1.20)
    elif role == "officer": dmg = int(dmg * 1.10)
    return max(50, dmg)

def _render_raid(raid):
    boss     = raid["boss"]
    hp       = raid["hp"]
    max_hp   = raid["max_hp"]
    phase    = raid["phase"]
    rnd      = raid["round"]
    raiders  = raid["raiders"]  # uid -> {name, role, dmg_total, penalty}

    bar  = _hp_bar(hp, max_hp)
    pct  = f"{hp/max_hp*100:.1f}%"

    if phase == "joining":
        lines = [
            f"⚔️ *CLAN BOSS RAID*\n",
            f"{boss['name']}",
            f"❤️ HP: *{hp:,}* / *{max_hp:,}*",
            f"{bar} {pct}\n",
            f"👥 Raiders joined: *{len(raiders)}*",
            f"⏳ Joining phase — click below to join!\n",
            f"_Raid starts when timer ends or leader is ready_"
        ]
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("⚔️ Join Raid", callback_data="clan_raid_join"),
            types.InlineKeyboardButton("▶️ Start Now", callback_data="clan_raid_start"),
        )
        return "\n".join(lines), markup

    elif phase == "attacking":
        attacked = [uid for uid, r in raiders.items() if rnd in r.get("attacked_rounds", [])]
        lines = [
            f"⚔️ *ROUND {rnd}/{RAID_ROUNDS}*\n",
            f"{boss['name']}",
            f"❤️ HP: *{hp:,}* / *{max_hp:,}*",
            f"{bar} {pct}\n",
            f"👥 Raiders: *{len(raiders)}* | Attacked: *{len(attacked)}*",
            f"⏳ Attack now!"
        ]
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⚔️ ATTACK!", callback_data="clan_raid_attack"))
        return "\n".join(lines), markup

    elif phase == "finished":
        won = hp <= 0
        lines = [
            f"{'🏆' if won else '💀'} *RAID {'VICTORY' if won else 'FAILED'}!*\n",
            f"{boss['name']}",
            f"❤️ HP: *{max(0,hp):,}* / *{max_hp:,}*",
            f"{bar} {pct}\n",
        ]
        if won and raiders:
            total  = raid.get("total_reward", 0)
            per    = total // len(raiders)
            lines += [f"💰 Total reward: *{fmt(total)}* chips",
                      f"👤 Per raider: *{fmt(per)}* chips\n",
                      "🎉 *Raid members paid!*"]
        elif raiders:
            lines.append("💸 No reward — boss survived!")
        return "\n".join(lines), None

def _run_raid(clan_id, chat_id, msg_id):
    raid = active_raids.get(clan_id)
    if not raid: return

    # ── Joining phase ─────────────────────────────────────────────────
    time.sleep(RAID_JOIN_TIME)
    raid = active_raids.get(clan_id)
    if not raid or raid.get("cancelled"): return

    if not raid["raiders"]:
        raid["phase"] = "finished"
        raid["hp"]    = raid["max_hp"]  # boss survives
        text, _       = _render_raid(raid)
        try: _bot.edit_message_text(text + "\n\n_No raiders joined!_",
            chat_id, msg_id, parse_mode="Markdown")
        except: pass
        active_raids.pop(clan_id, None)
        return

    # ── 3 Attack rounds ───────────────────────────────────────────────
    for rnd in range(1, RAID_ROUNDS + 1):
        raid["phase"] = "attacking"
        raid["round"] = rnd

        text, markup = _render_raid(raid)
        try: _bot.edit_message_text(text, chat_id, msg_id,
            reply_markup=markup, parse_mode="Markdown")
        except: pass

        time.sleep(RAID_ROUND_TIME)
        raid = active_raids.get(clan_id)
        if not raid: return

        # Calculate round damage
        round_dmg = 0
        for uid, r in raid["raiders"].items():
            if rnd in r.get("attacked_rounds", []):
                round_dmg += r.get("round_dmg", {}).get(rnd, 0)

        raid["hp"] = max(0, raid["hp"] - round_dmg)

        # Boss counterattack between rounds (not after last round)
        counter_msg = ""
        if rnd < RAID_ROUNDS and raid["hp"] > 0 and raid["raiders"]:
            target_uid = random.choice(list(raid["raiders"].keys()))
            penalty    = random.randint(10, 30)
            raid["raiders"][target_uid]["penalty"] = raid["raiders"][target_uid].get("penalty", 0) + penalty
            tname      = raid["raiders"][target_uid]["name"]
            counter_msg = f"\n💥 *Boss counterattacks {tname}!* (-{penalty}% reward)"

        if counter_msg:
            try: _bot.send_message(chat_id, counter_msg, parse_mode="Markdown")
            except: pass

        # Boss dead?
        if raid["hp"] <= 0:
            break

    # ── Finish ────────────────────────────────────────────────────────
    raid["phase"] = "finished"
    won           = raid["hp"] <= 0
    boss          = raid["boss"]

    if won:
        base_reward   = random.randint(boss["min_reward"], boss["max_reward"])
        raiders_count = len(raid["raiders"])
        raid["total_reward"] = base_reward

        for uid, r in raid["raiders"].items():
            penalty  = r.get("penalty", 0)
            share    = base_reward // raiders_count
            share    = int(share * (1 - penalty / 100))
            entry    = raid["boss"]["entry"]
            db.update_chips(uid, share + entry)  # reward + entry refund
            db.add_xp(uid, 100)

        # Save to DB and add clan XP
        clan = get_clan_by_id(clan_id)
        db.execute("UPDATE clans SET xp=xp+? WHERE id=?", (100 * raiders_count, clan_id))
        db.execute(
            "INSERT INTO clan_raids (clan_id, boss_name, result, reward, raiders, started_at) VALUES (?,?,?,?,?,?)",
            (clan_id, boss["name"], "win", base_reward, raiders_count, datetime.utcnow().isoformat())
        )
    else:
        db.execute(
            "INSERT INTO clan_raids (clan_id, boss_name, result, reward, raiders, started_at) VALUES (?,?,?,?,?,?)",
            (clan_id, boss["name"], "loss", 0, len(raid["raiders"]), datetime.utcnow().isoformat())
        )

    text, _ = _render_raid(raid)
    try: _bot.edit_message_text(text, chat_id, msg_id, parse_mode="Markdown")
    except: pass

    active_raids.pop(clan_id, None)

def _clan_raid(message, p):
    uid = message.from_user.id
    mem = get_member(uid)
    if not mem:
        _bot.reply_to(message, "❌ You need to be in a clan!"); return

    clan_id = member_val(mem, "clan_id")
    role    = member_val(mem, "role")

    if role not in ("leader", "officer"):
        _bot.reply_to(message, "❌ Only leader or officers can start a raid!"); return

    if clan_id in active_raids:
        _bot.reply_to(message, "⚔️ A raid is already in progress!"); return

    # Check cooldown
    last = get_last_raid(clan_id)
    if last:
        last_dt = datetime.fromisoformat(last)
        diff    = (datetime.utcnow() - last_dt).total_seconds()
        if diff < RAID_COOLDOWN:
            remaining = int(RAID_COOLDOWN - diff)
            hrs  = remaining // 3600
            mins = (remaining % 3600) // 60
            _bot.reply_to(message, f"⏰ Clan raid on cooldown!\nNext raid in: *{hrs}h {mins}m*"); return

    clan    = get_clan_by_id(clan_id)
    level   = clan_val(clan, "level") or 1
    boss    = BOSSES[level]
    cname   = clan_val(clan, "name")

    entry = boss["entry"]
    p2    = db.get_player(uid)
    if (p2.get("chips") or 0) < entry:
        _bot.reply_to(message,
            f"❌ You need *{fmt(entry)}* chips to start this raid!\nYou have: *{fmt(p2.get('chips',0))}*"); return

    # Confirmation message first
    markup_confirm = types.InlineKeyboardMarkup()
    markup_confirm.row(
        types.InlineKeyboardButton("⚔️ Start Raid", callback_data=f"clan_raid_confirm_{clan_id}"),
        types.InlineKeyboardButton("❌ Cancel",      callback_data=f"clan_raid_cancel_{clan_id}"),
    )
    boss_name = boss['name']
    boss_hp   = boss['hp']
    min_rew   = boss['min_reward']
    max_rew   = boss['max_reward']
    _bot.reply_to(message,
        f"⚔️ *Boss Raid — {boss_name}*\n\n"
        f"❤️ HP: *{boss_hp:,}*\n"
        f"💰 Entry fee: *{fmt(entry)}* chips per raider\n"
        f"🏆 Reward: *{fmt(min_rew)}* – *{fmt(max_rew)}* chips\n"
        f"🕐 Joining: 2 min | ⚔️ Rounds: 3 × 60s\n\n"
        "Entry fee deducted when joining. Refunded on win.\n"
        "Ready to start?",
        reply_markup=markup_confirm)

    # Run raid in background
    t = threading.Thread(
        target=_run_raid,
        args=(clan_id, message.chat.id, msg.message_id),
        daemon=True
    )
    t.start()

def _cb_raid_join(call, uid, clan_id):
    raid = active_raids.get(clan_id)
    if not raid or raid["phase"] != "joining":
        _bot.answer_callback_query(call.id, "Joining phase is over!"); return
    if uid in raid["raiders"]:
        _bot.answer_callback_query(call.id, "Already in the raid!"); return

    mem  = get_member(uid)
    role = member_val(mem, "role") if mem and member_val(mem,"clan_id") == clan_id else "member"
    p    = db.get_player(uid)
    if not p:
        _bot.answer_callback_query(call.id, "Register first!"); return

    entry = raid["boss"]["entry"]
    p2    = db.get_player(uid)
    if (p2.get("chips") or 0) < entry:
        _bot.answer_callback_query(call.id, f"❌ Need {fmt(entry)} chips to join!", show_alert=True); return
    db.update_chips(uid, -entry)
    raid["raiders"][uid] = {
        "name": call.from_user.first_name,
        "role": role,
        "attacked_rounds": [],
        "round_dmg": {},
        "penalty": 0,
        "entry_paid": True,
    }
    _bot.answer_callback_query(call.id, f"⚔️ Joined! {fmt(entry)} chips deducted. Get ready to attack!")

    text, markup = _render_raid(raid)
    try:
        _bot.edit_message_text(text, call.message.chat.id,
            call.message.message_id, reply_markup=markup, parse_mode="Markdown")
    except: pass

def _cb_raid_start(call, uid, clan_id):
    mem = get_member(uid)
    if not mem or member_val(mem,"role") not in ("leader","officer") or member_val(mem,"clan_id") != clan_id:
        _bot.answer_callback_query(call.id, "Leaders/officers only!"); return
    raid = active_raids.get(clan_id)
    if not raid or raid["phase"] != "joining":
        _bot.answer_callback_query(call.id, "Already started!"); return
    raid["cancelled"] = True  # stop the sleep loop
    _bot.answer_callback_query(call.id, "▶️ Starting raid now!")
    # Restart raid immediately
    active_raids[clan_id] = {**raid, "cancelled": False}
    t = threading.Thread(
        target=_run_raid,
        args=(clan_id, call.message.chat.id, call.message.message_id),
        daemon=True
    )
    t.start()

def _cb_raid_attack(call, uid, clan_id):
    raid = active_raids.get(clan_id)
    if not raid or raid["phase"] != "attacking":
        _bot.answer_callback_query(call.id, "No attack phase active!"); return
    if uid not in raid["raiders"]:
        _bot.answer_callback_query(call.id, "You didn't join this raid!"); return

    rnd    = raid["round"]
    raider = raid["raiders"][uid]
    if rnd in raider.get("attacked_rounds", []):
        _bot.answer_callback_query(call.id, f"Already attacked this round!"); return

    dmg = _calc_damage(uid, raider["role"])
    raider.setdefault("attacked_rounds", []).append(rnd)
    raider.setdefault("round_dmg", {})[rnd] = dmg
    _bot.answer_callback_query(call.id,
        f"⚔️ You dealt *{fmt(dmg)}* damage!", show_alert=True)

# Hook raid callbacks into main cb_clan
_orig_cb_clan = cb_clan

def cb_clan(call):
    uid     = call.from_user.id
    data    = call.data
    mem     = get_member(uid)
    clan_id = member_val(mem, "clan_id") if mem else None

    if data.startswith("clan_raid_confirm_"):
        cid2 = int(data.split("_")[-1])
        mem2 = get_member(uid)
        if not mem2 or member_val(mem2,"clan_id") != cid2 or member_val(mem2,"role") not in ("leader","officer"):
            _bot.answer_callback_query(call.id, "Leaders/officers only!", show_alert=True); return
        if cid2 in active_raids:
            _bot.answer_callback_query(call.id, "Raid already started!"); return
        clan2  = get_clan_by_id(cid2)
        level2 = clan_val(clan2,"level") or 1
        boss2  = BOSSES[level2]
        entry2 = boss2["entry"]
        p3     = db.get_player(uid)
        if (p3.get("chips") or 0) < entry2:
            _bot.answer_callback_query(call.id, f"Not enough chips! Need {fmt(entry2)}", show_alert=True); return
        # Start the raid
        db.update_chips(uid, -entry2)
        raid2 = {
            "clan_id": cid2, "boss": boss2, "hp": boss2["hp"], "max_hp": boss2["hp"],
            "phase": "joining", "round": 0, "raiders": {}, "cancelled": False,
        }
        raid2["raiders"][uid] = {"name": call.from_user.first_name, "role": member_val(mem2,"role"),
            "attacked_rounds": [], "round_dmg": {}, "penalty": 0, "entry_paid": True}
        active_raids[cid2] = raid2
        text2, markup2 = _render_raid(raid2)
        try: _bot.edit_message_text(text2, call.message.chat.id, call.message.message_id,
            reply_markup=markup2, parse_mode="Markdown")
        except: pass
        _bot.answer_callback_query(call.id, "⚔️ Raid started!")
        t = threading.Thread(target=_run_raid, args=(cid2, call.message.chat.id, call.message.message_id), daemon=True)
        t.start()
        return

    if data.startswith("clan_raid_cancel_"):
        cid2 = int(data.split("_")[-1])
        active_raids.pop(cid2, None)
        _bot.answer_callback_query(call.id, "❌ Raid cancelled.")
        try: _bot.edit_message_text("❌ Raid cancelled.", call.message.chat.id, call.message.message_id)
        except: pass
        return

    if data == "clan_raid_join" and clan_id:
        _cb_raid_join(call, uid, clan_id); return
    if data == "clan_raid_start" and clan_id:
        _cb_raid_start(call, uid, clan_id); return
    if data == "clan_raid_attack" and clan_id:
        _cb_raid_attack(call, uid, clan_id); return
    if data.startswith("clan_") and not data.startswith("clan_raid"):
        _orig_cb_clan(call); return
    if not mem and data.startswith("clan_raid"):
        _bot.answer_callback_query(call.id, "You're not in a clan!"); return

# Update register to also init raid DB and register new cb_clan
_orig_register = register_clan

def register_clan(bot_instance):
    global _bot
    _bot = bot_instance
    init_clan_db()
    init_raid_db()
    bot_instance.register_message_handler(cmd_clan, commands=["clan"])
    bot_instance.register_callback_query_handler(
        cb_clan, func=lambda c: c.data.startswith("clan_"))
    print("✅ Clan + Boss Raid loaded")
