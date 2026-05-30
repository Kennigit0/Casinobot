import os, json, math
from datetime import datetime, date, timedelta

DATABASE_URL = os.environ.get("DATABASE_URL")

# ── Level helpers ─────────────────────────────────────────────────────
def xp_to_level(xp):
    return int(math.sqrt((xp or 0) / 100))

def level_to_xp(level):
    return level * level * 100

def get_title(level):
    from config import Config
    title = "🥉 Beginner"
    for lvl, t in sorted(Config.TITLES.items()):
        if level >= lvl:
            title = t
    return title

def progress_bar(current_xp):
    level    = xp_to_level(current_xp)
    curr_xp  = level_to_xp(level)
    next_xp  = level_to_xp(level + 1)
    progress = current_xp - curr_xp
    needed   = next_xp - curr_xp
    filled   = int(10 * progress / needed) if needed > 0 else 10
    bar      = "█" * filled + "░" * (10 - filled)
    return f"[{bar}] {progress}/{needed} XP"

# ── Connection ────────────────────────────────────────────────────────
def get_conn():
    if DATABASE_URL:
        import psycopg2
        conn = psycopg2.connect(DATABASE_URL, sslmode="require", connect_timeout=10)
        return conn, "pg"
    else:
        import sqlite3
        conn = sqlite3.connect("casino.db", check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn, "sqlite"

def execute(query, params=(), fetch=None):
    conn, db_type = get_conn()
    if db_type == "pg":
        query = query.replace("?", "%s")
    else:
        # SQLite uses MIN/MAX as scalar; replace LEAST/GREATEST
        query = query.replace("LEAST(", "MIN(").replace("GREATEST(", "MAX(")
    try:
        cur = conn.cursor()
        cur.execute(query, params)
        conn.commit()
        if fetch == "one":
            row = cur.fetchone()
            if row and db_type == "pg":
                cols = [d[0] for d in cur.description]
                return dict(zip(cols, row))
            return dict(row) if row and db_type == "sqlite" else row
        elif fetch == "all":
            rows = cur.fetchall()
            if rows and db_type == "pg":
                cols = [d[0] for d in cur.description]
                return [dict(zip(cols, r)) for r in rows]
            return [dict(r) for r in rows] if rows and db_type == "sqlite" else rows
        return None
    except Exception as e:
        try: conn.rollback()
        except: pass
        print(f"DB Error: {e} | Query: {query[:80]}")
        return None
    finally:
        conn.close()

# ── Init ──────────────────────────────────────────────────────────────
def init_db():
    execute('''
        CREATE TABLE IF NOT EXISTS groups (
            chat_id BIGINT PRIMARY KEY
        )
    ''')
    conn, db_type = get_conn()
    cur = conn.cursor()
    if db_type == "pg":
        cur.execute("""
            CREATE TABLE IF NOT EXISTS players (
                user_id       BIGINT PRIMARY KEY,
                username      TEXT,
                first_name    TEXT,
                chips         BIGINT DEFAULT 10000,
                bank          BIGINT DEFAULT 0,
                xp            BIGINT DEFAULT 0,
                level         INTEGER DEFAULT 0,
                vip           INTEGER DEFAULT 0,
                age_ok        INTEGER DEFAULT 0,
                last_daily    TEXT,
                last_work     TEXT,
                last_crime    TEXT,
                last_rob      TEXT,
                last_interest TEXT,
                last_game     TEXT,
                last_heist    TEXT,
                last_fish     TEXT,
                last_mine     TEXT,
                last_farm     TEXT,
                married_to    BIGINT DEFAULT 0,
                joined_at     TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS bj_games (
                game_id    TEXT PRIMARY KEY,
                chat_id    BIGINT,
                message_id BIGINT,
                host_id    BIGINT,
                state      TEXT DEFAULT 'waiting',
                bet        BIGINT,
                data       TEXT DEFAULT '{}',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS dice_challenges (
                challenge_id TEXT PRIMARY KEY,
                chat_id      BIGINT,
                challenger   BIGINT,
                challenged   BIGINT,
                bet          BIGINT,
                state        TEXT DEFAULT 'pending',
                created_at   TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS player_tools (
                user_id      BIGINT PRIMARY KEY,
                fishing_tool TEXT DEFAULT 'wooden_rod',
                mining_tool  TEXT DEFAULT 'stone_pickaxe',
                farming_tool TEXT DEFAULT 'bare_hands',
                owned_tools  TEXT DEFAULT '["wooden_rod","stone_pickaxe","bare_hands"]'
            )
        """)
        # Safe migrations
        for col, defn in [
            ("xp","BIGINT DEFAULT 0"), ("level","INTEGER DEFAULT 0"),
            ("bank","BIGINT DEFAULT 0"), ("last_work","TEXT"),
            ("last_crime","TEXT"), ("last_rob","TEXT"),
            ("last_interest","TEXT"), ("last_game","TEXT"),
            ("last_heist","TEXT"), ("last_fish","TEXT"),
            ("last_mine","TEXT"), ("last_farm","TEXT"),
            ("married_to","BIGINT DEFAULT 0"),
            ("wins","BIGINT DEFAULT 0"),
            ("losses","BIGINT DEFAULT 0"),
            ("bank_level","INTEGER DEFAULT 0"),
        ]:
            try: cur.execute(f"ALTER TABLE players ADD COLUMN IF NOT EXISTS {col} {defn}")
            except: pass
    else:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS players (
                user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT,
                chips INTEGER DEFAULT 10000, bank INTEGER DEFAULT 0,
                xp INTEGER DEFAULT 0, level INTEGER DEFAULT 0,
                vip INTEGER DEFAULT 0, age_ok INTEGER DEFAULT 0,
                last_daily TEXT, last_work TEXT, last_crime TEXT,
                last_rob TEXT, last_interest TEXT, last_game TEXT,
                last_heist TEXT, last_fish TEXT, last_mine TEXT,
                last_farm TEXT, married_to INTEGER DEFAULT 0,
                joined_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""CREATE TABLE IF NOT EXISTS bj_games (
            game_id TEXT PRIMARY KEY, chat_id INTEGER, message_id INTEGER,
            host_id INTEGER, state TEXT DEFAULT 'waiting', bet INTEGER,
            data TEXT DEFAULT '{}', created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS dice_challenges (
            challenge_id TEXT PRIMARY KEY, chat_id INTEGER, challenger INTEGER,
            challenged INTEGER, bet INTEGER, state TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS player_tools (
            user_id INTEGER PRIMARY KEY,
            fishing_tool TEXT DEFAULT 'wooden_rod',
            mining_tool TEXT DEFAULT 'stone_pickaxe',
            farming_tool TEXT DEFAULT 'bare_hands',
            owned_tools TEXT DEFAULT '["wooden_rod","stone_pickaxe","bare_hands"]')""")
        for col, defn in [("xp","INTEGER DEFAULT 0"),("level","INTEGER DEFAULT 0"),
            ("bank","INTEGER DEFAULT 0"),("last_work","TEXT"),("last_crime","TEXT"),
            ("last_rob","TEXT"),("last_interest","TEXT"),("last_game","TEXT"),
            ("last_heist","TEXT"),("last_fish","TEXT"),("last_mine","TEXT"),
            ("last_farm","TEXT"),("married_to","INTEGER DEFAULT 0"),
            ("wins","INTEGER DEFAULT 0"),
            ("losses","INTEGER DEFAULT 0"),
            ("bank_level","INTEGER DEFAULT 0")]:
            try: cur.execute(f"ALTER TABLE players ADD COLUMN IF NOT EXISTS {col} {defn}")
            except: pass
    conn.commit()
    conn.close()
    print(f"✅ DB ready ({'PostgreSQL' if db_type == 'pg' else 'SQLite'})")

def init_activities_db(): pass

# ── XP & Level ────────────────────────────────────────────────────────
def add_xp(user_id, amount):
    p = get_player(user_id)
    if not p: return
    new_xp    = (p.get("xp") or 0) + amount
    new_level = xp_to_level(new_xp)
    execute("UPDATE players SET xp=?, level=? WHERE user_id=?", (new_xp, new_level, user_id))
    return new_level, new_xp

# ── Players ───────────────────────────────────────────────────────────

def save_group(chat_id):
    """Save group chat_id so lottery/announcements can reach it"""
    existing = execute("SELECT chat_id FROM groups WHERE chat_id=?", (chat_id,), fetch="one")
    if not existing:
        execute("INSERT INTO groups (chat_id) VALUES (?)", (chat_id,))

def get_groups():
    rows = execute("SELECT chat_id FROM groups", fetch="all") or []
    return [r["chat_id"] if isinstance(r, dict) else r[0] for r in rows]

def get_player(user_id):
    return execute("SELECT * FROM players WHERE user_id=?", (user_id,), fetch="one")

def register_player(user_id, username, first_name):
    from config import Config
    execute("""INSERT INTO players (user_id, username, first_name, chips, age_ok)
               VALUES (?, ?, ?, ?, 1) ON CONFLICT (user_id) DO NOTHING""",
            (user_id, username or "unknown", first_name or "Player", Config.STARTING_CHIPS))

WALLET_MAX = 999_999_999

def update_chips(user_id, amount):
    execute("UPDATE players SET chips=GREATEST(LEAST(chips+?, ?), 0) WHERE user_id=?", (amount, WALLET_MAX, user_id))
    if amount > 0:
        execute("UPDATE players SET total_earned=COALESCE(total_earned,0)+? WHERE user_id=?", (amount, user_id))
    p = get_player(user_id)
    return p["chips"] if p else 0

def claim_daily(user_id, is_vip=False):
    from config import Config
    p = get_player(user_id)
    if not p: return False, 0, "Not registered."
    today = str(date.today())
    if p.get("last_daily") == today:
        return False, 0, "Already claimed today. Come back tomorrow!"
    bonus = Config.VIP_DAILY_BONUS if is_vip else Config.DAILY_BONUS
    execute("UPDATE players SET last_daily=?, chips=LEAST(chips+?, ?) WHERE user_id=?", (today, bonus, WALLET_MAX, user_id))
    add_xp(user_id, Config.XP_DAILY)
    return True, bonus, ""

def set_vip(user_id, status=1):
    execute("UPDATE players SET vip=? WHERE user_id=?", (status, user_id))

def get_leaderboard(limit=10, by="chips"):
    if by == "xp":
        return execute("SELECT user_id, first_name, username, chips, bank, xp, level, vip FROM players ORDER BY xp DESC LIMIT ?", (limit,), fetch="all") or []
    return execute("SELECT user_id, first_name, username, chips, bank, xp, level, vip FROM players ORDER BY (chips+bank) DESC LIMIT ?", (limit,), fetch="all") or []

# ── Bank ──────────────────────────────────────────────────────────────

BANK_LEVELS = {
    0: {"name": "Basic",    "limit": 50_000,      "upgrade_cost": 10_000},
    1: {"name": "Bronze",   "limit": 200_000,     "upgrade_cost": 50_000},
    2: {"name": "Silver",   "limit": 500_000,     "upgrade_cost": 150_000},
    3: {"name": "Gold",     "limit": 1_000_000,   "upgrade_cost": 400_000},
    4: {"name": "Platinum", "limit": 5_000_000,   "upgrade_cost": 1_200_000},
    5: {"name": "Diamond",  "limit": 20_000_000,  "upgrade_cost": 4_000_000},
    6: {"name": "Elite",    "limit": 999_999_999, "upgrade_cost": None},
}


# Add your group chat IDs here
ANNOUNCE_GROUPS = [-1002726768482]  # e.g. [-1001234567890, -1009876543210]

def get_all_groups():
    return ANNOUNCE_GROUPS

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
    conn2, db_type2 = get_conn()
    cur2 = conn2.cursor()
    q2 = "UPDATE players SET chips=chips-?, bank_level=bank_level+1 WHERE user_id=? AND chips>=?"
    if db_type2 == "pg": q2 = q2.replace("?", "%s")
    cur2.execute(q2, (cost, user_id, cost))
    conn2.commit()
    if cur2.rowcount == 0: return False, "❌ Not enough chips!"
    return True, BANK_LEVELS[lvl + 1]

def bank_deposit(user_id, amount):
    p = get_player(user_id)
    if not p: return False, "❌ Player not found."
    limit        = get_bank_limit(user_id)
    current_bank = p.get("bank") or 0
    current_chips= p.get("chips") or 0

    if current_bank + amount > limit:
        space = limit - current_bank
        if space <= 0:
            return False, "❌ Bank is full! Use /bankupgrade to store more."
        return False, f"❌ Only *{space:,}* space left. Deposit that or /bankupgrade."

    if current_chips < amount:
        return False, "❌ Not enough chips!"

    # Atomic: only deduct if chips >= amount (prevents race condition)
    conn, db_type = get_conn()
    cur = conn.cursor()
    query = "UPDATE players SET chips=chips-?, bank=bank+? WHERE user_id=? AND chips>=?"
    if db_type == "pg":
        query = query.replace("?", "%s")
    cur.execute(query, (amount, amount, user_id, amount))
    conn.commit()
    affected = cur.rowcount

    if affected == 0:
        return False, "❌ Not enough chips! (concurrent request blocked)"
    return True, amount

def bank_withdraw(user_id, amount):
    execute("UPDATE players SET bank=bank-?, chips=GREATEST(LEAST(chips+?, ?), 0) WHERE user_id=?", (amount, amount, WALLET_MAX, user_id))

def claim_interest(user_id):
    p = get_player(user_id)
    if not p: return False, 0, "Not registered."
    if not p.get("bank") or p["bank"] <= 0:
        return False, 0, "No chips in bank! Deposit first with /deposit"
    today = str(date.today())
    if p.get("last_interest") == today:
        return False, 0, "Already claimed interest today. Come back tomorrow!"
    interest = max(1, int(p["bank"] * 0.03))
    bank_limit = get_bank_limit(user_id)
    execute("UPDATE players SET bank=LEAST(bank+?, ?), last_interest=? WHERE user_id=?", (interest, bank_limit, today, user_id))
    return True, interest, ""

# ── Cooldowns ─────────────────────────────────────────────────────────
def _check_cooldown(user_id, field, hours):
    p = get_player(user_id)
    if not p: return False, "Not registered."
    last = p.get(field)
    if last:
        last_dt   = datetime.fromisoformat(str(last)[:19])
        next_dt   = last_dt + timedelta(hours=hours)
        remaining = next_dt - datetime.now()
        if remaining.total_seconds() > 0:
            mins = int(remaining.total_seconds() // 60)
            hrs  = mins // 60
            mins = mins % 60
            secs = int(remaining.total_seconds() % 60)
            if hrs > 0:   return False, f"Wait *{hrs}h {mins}m* before doing this again."
            if mins > 0:  return False, f"Wait *{mins}m {secs}s* before doing this again."
            return False, f"Wait *{secs}s* before doing this again."
    return True, ""

def can_play_game(user_id): return _check_cooldown(user_id, "last_game",   0.0083)
def can_work(user_id):      return _check_cooldown(user_id, "last_work",   0.05)
def can_crime(user_id):     return _check_cooldown(user_id, "last_crime",  0.25)
def can_rob(user_id):       return _check_cooldown(user_id, "last_rob",    2)
def can_heist(user_id):     return _check_cooldown(user_id, "last_heist",  0.5)

def _set_ts(user_id, field):
    execute(f"UPDATE players SET {field}=? WHERE user_id=?", (datetime.now().isoformat()[:19], user_id))

def set_last_game(user_id):  _set_ts(user_id, "last_game")
def set_last_work(user_id):  _set_ts(user_id, "last_work")
def set_last_crime(user_id): _set_ts(user_id, "last_crime")
def set_last_rob(user_id):   _set_ts(user_id, "last_rob")
def set_last_heist(user_id): _set_ts(user_id, "last_heist")

# ── Marriage ──────────────────────────────────────────────────────────
def marry(u1, u2):
    execute("UPDATE players SET married_to=? WHERE user_id=?", (u2, u1))
    execute("UPDATE players SET married_to=? WHERE user_id=?", (u1, u2))

def divorce(u1, u2):
    execute("UPDATE players SET married_to=0 WHERE user_id=?", (u1,))
    execute("UPDATE players SET married_to=0 WHERE user_id=?", (u2,))

# ── Blackjack ─────────────────────────────────────────────────────────
def save_bj_game(game_id, chat_id, message_id, host_id, bet, data):
    execute("""INSERT INTO bj_games (game_id,chat_id,message_id,host_id,bet,state,data)
               VALUES (?,?,?,?,?,?,?) ON CONFLICT (game_id) DO UPDATE SET state=EXCLUDED.state, data=EXCLUDED.data""",
            (game_id, chat_id, message_id, host_id, bet, data.get("state","waiting"), json.dumps(data)))

def get_bj_game(game_id):
    row = execute("SELECT * FROM bj_games WHERE game_id=?", (game_id,), fetch="one")
    if row:
        row["data"] = json.loads(row["data"])
    return row

def update_bj_game(game_id, data):
    execute("UPDATE bj_games SET state=?, data=? WHERE game_id=?",
            (data.get("state","waiting"), json.dumps(data), game_id))

def delete_bj_game(game_id):
    """Returns True if deleted, False if already gone (prevents double payout)"""
    existing = execute("SELECT game_id FROM bj_games WHERE game_id=?", (game_id,), fetch="one")
    if not existing:
        return False
    execute("DELETE FROM bj_games WHERE game_id=?", (game_id,))
    return True

# ── Dice ──────────────────────────────────────────────────────────────
def save_dice(challenge_id, chat_id, challenger, challenged, bet):
    execute("""INSERT INTO dice_challenges (challenge_id,chat_id,challenger,challenged,bet)
               VALUES (?,?,?,?,?)""", (challenge_id, chat_id, challenger, challenged, bet))

def get_dice(challenge_id):
    return execute("SELECT * FROM dice_challenges WHERE challenge_id=?", (challenge_id,), fetch="one")

def update_dice_state(challenge_id, state):
    execute("UPDATE dice_challenges SET state=? WHERE challenge_id=?", (state, challenge_id))

# ── Player Tools ──────────────────────────────────────────────────────
def get_player_tools(user_id):
    row = execute("SELECT * FROM player_tools WHERE user_id=?", (user_id,), fetch="one")
    if not row:
        return {"fishing_tool": "wooden_rod", "mining_tool": "stone_pickaxe",
                "farming_tool": "bare_hands",
                "owned_tools": '["wooden_rod","stone_pickaxe","bare_hands"]'}
    return row

def get_equipped(user_id, tool_type):
    row = get_player_tools(user_id)
    defaults = {"fishing": "wooden_rod", "mining": "stone_pickaxe", "farming": "bare_hands"}
    key = f"{tool_type}_tool"
    return (row.get(key) if row else None) or defaults.get(tool_type, "wooden_rod")

def get_owned_tools(user_id):
    row = get_player_tools(user_id)
    defaults = ["wooden_rod", "stone_pickaxe", "bare_hands"]
    owned = json.loads(row["owned_tools"]) if row and row.get("owned_tools") else []
    return list(set(owned + defaults))

def save_tool_purchase(user_id, tool_key):
    owned = get_owned_tools(user_id)
    if tool_key not in owned:
        owned.append(tool_key)
    execute("""INSERT INTO player_tools (user_id, fishing_tool, mining_tool, farming_tool, owned_tools)
               VALUES (?, 'wooden_rod', 'stone_pickaxe', 'bare_hands', ?)
               ON CONFLICT (user_id) DO UPDATE SET owned_tools=EXCLUDED.owned_tools""",
            (user_id, json.dumps(owned)))

def equip_tool_db(user_id, tool_key, tool_type):
    row = execute("SELECT user_id FROM player_tools WHERE user_id=?", (user_id,), fetch="one")
    if row:
        execute(f"UPDATE player_tools SET {tool_type}_tool=? WHERE user_id=?", (tool_key, user_id))
    else:
        defaults = {"fishing": "wooden_rod", "mining": "stone_pickaxe", "farming": "bare_hands"}
        defaults[tool_type] = tool_key
        execute("""INSERT INTO player_tools (user_id, fishing_tool, mining_tool, farming_tool, owned_tools)
                   VALUES (?, ?, ?, ?, ?) ON CONFLICT (user_id) DO NOTHING""",
                (user_id, defaults["fishing"], defaults["mining"], defaults["farming"],
                 '["wooden_rod","stone_pickaxe","bare_hands"]'))

def set_activity_time(user_id, field):
    execute(f"UPDATE players SET {field}=? WHERE user_id=?", (datetime.now().isoformat()[:19], user_id))

def clear_activity_time(user_id, field):
    execute(f"UPDATE players SET {field}=NULL WHERE user_id=?", (user_id,))
