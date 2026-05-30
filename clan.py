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
    if sub == "heist":       return _clan_heist(message, p)
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

def _clan_heist(message, p):
    uid     = message.from_user.id
    mem     = get_member(uid)
    if not mem:
        _bot.reply_to(message, "❌ You need to be in a clan to do a clan heist!"); return

    clan_id  = member_val(mem, "clan_id")
    clan     = get_clan_by_id(clan_id)
    members  = get_clan_members(clan_id)
    count    = len(members)
    cname    = clan_val(clan, "name")
    bank     = clan_val(clan, "bank") or 0

    # Heist cost = 10% of clan bank minimum 5000
    heist_cost = max(5_000, int(bank * 0.10))
    if bank < heist_cost:
        _bot.reply_to(message,
            f"❌ Clan bank needs at least *{fmt(heist_cost)}* chips to start a heist.\n"
            f"Current bank: *{fmt(bank)}*\n"
            "Ask members to `/clan deposit` first!"); return

    # Calculate reward based on members and level
    level       = clan_val(clan, "level") or 1
    multiplier  = round(random.uniform(1.5, 4.0) * level, 2)
    base_reward = int(heist_cost * multiplier)
    success     = random.random() < (0.5 + level * 0.08)  # 50-90% based on level

    db.execute("UPDATE clans SET bank=bank-? WHERE id=?", (heist_cost, clan_id))

    if success:
        reward_per = base_reward // count
        db.execute("UPDATE clans SET bank=bank+?, xp=xp+? WHERE id=?",
                   (base_reward, 50 * count, clan_id))
        for m in members:
            mid = member_val(m, "user_id")
            db.update_chips(mid, reward_per)
            db.add_xp(mid, 50)

        lines = [
            f"🏦 *CLAN HEIST SUCCESS!*\n",
            f"⚔️ Clan: *{cname}*",
            f"👥 Members: *{count}*",
            f"💥 Multiplier: *{multiplier}x*",
            f"💰 Total loot: *{fmt(base_reward)}* chips",
            f"👤 Per member: *{fmt(reward_per)}* chips",
            f"\n🎉 All members paid! Clan bank kept *{fmt(base_reward)}* too!"
        ]
        _bot.reply_to(message, "\n".join(lines))
    else:
        lines = [
            f"💀 *CLAN HEIST FAILED!*\n",
            f"⚔️ Clan: *{cname}*",
            f"👥 Members: *{count}*",
            f"💸 Lost: *{fmt(heist_cost)}* chips from clan bank",
            f"\nBetter luck next time! Train harder 💪"
        ]
        _bot.reply_to(message, "\n".join(lines))

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
