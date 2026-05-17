import os
import json
from datetime import datetime, date, timedelta

# ── Connection ────────────────────────────────────────────────────────

DATABASE_URL = os.environ.get("DATABASE_URL")

def get_conn():
    if DATABASE_URL:
        return conn, "pg"
    else:
        import sqlite3
        conn = sqlite3.connect("casino.db", check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn, "sqlite"

def execute(query, params=(), fetch=None):
    """Universal query executor for both SQLite and PostgreSQL"""
    conn, db_type = get_conn()
    # Convert SQLite ? placeholders to PostgreSQL %s
    if db_type == "pg":
        query = query.replace("?", "%s")
    try:
        cur = conn.cursor()
        cur.execute(query, params)
        conn.commit()
        if fetch == "one":
            row = cur.fetchone()
            if row and db_type == "pg":
                cols = [desc[0] for desc in cur.description]
                return dict(zip(cols, row))
            return row
        elif fetch == "all":
            rows = cur.fetchall()
            if rows and db_type == "pg":
                cols = [desc[0] for desc in cur.description]
                return [dict(zip(cols, r)) for r in rows]
            return rows
        return None
    except Exception as e:
        conn.rollback()
        print(f"DB Error: {e}")
        return None
    finally:
        conn.close()

def executemany_safe(queries):
    """Run multiple queries safely"""
    conn, db_type = get_conn()
    try:
        cur = conn.cursor()
        for q, p in queries:
            if db_type == "pg":
                q = q.replace("?", "%s")
            try:
                cur.execute(q, p)
            except Exception as e:
                print(f"Query error (ignored): {e}")
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"DB Error: {e}")
    finally:
        conn.close()

# ── Init ──────────────────────────────────────────────────────────────

def init_db():
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
        # Add missing columns safely
        for col, definition in [
            ("bank",          "BIGINT DEFAULT 0"),
            ("last_work",     "TEXT"),
            ("last_crime",    "TEXT"),
            ("last_rob",      "TEXT"),
            ("last_interest", "TEXT"),
            ("last_game",     "TEXT"),
            ("last_heist",    "TEXT"),
            ("last_fish",     "TEXT"),
            ("last_mine",     "TEXT"),
            ("last_farm",     "TEXT"),
            ("married_to",    "BIGINT DEFAULT 0"),
        ]:
            try:
                cur.execute(f"ALTER TABLE players ADD COLUMN IF NOT EXISTS {col} {definition}")
            except Exception:
                pass
    else:
        import sqlite3
        cur.execute("""
            CREATE TABLE IF NOT EXISTS players (
                user_id       INTEGER PRIMARY KEY,
                username      TEXT,
                first_name    TEXT,
                chips         INTEGER DEFAULT 10000,
                bank          INTEGER DEFAULT 0,
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
                married_to    INTEGER DEFAULT 0,
                joined_at     TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS bj_games (
                game_id    TEXT PRIMARY KEY,
                chat_id    INTEGER,
                message_id INTEGER,
                host_id    INTEGER,
                state      TEXT DEFAULT 'waiting',
                bet        INTEGER,
                data       TEXT DEFAULT '{}',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS dice_challenges (
                challenge_id TEXT PRIMARY KEY,
                chat_id      INTEGER,
                challenger   INTEGER,
                challenged   INTEGER,
                bet          INTEGER,
                state        TEXT DEFAULT 'pending',
                created_at   TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS player_tools (
                user_id      INTEGER PRIMARY KEY,
                fishing_tool TEXT DEFAULT 'wooden_rod',
                mining_tool  TEXT DEFAULT 'stone_pickaxe',
                farming_tool TEXT DEFAULT 'bare_hands',
                owned_tools  TEXT DEFAULT '["wooden_rod","stone_pickaxe","bare_hands"]'
            )
        """)
        for col, definition in [
            ("bank", "INTEGER DEFAULT 0"), ("last_work", "TEXT"),
            ("last_crime", "TEXT"), ("last_rob", "TEXT"),
            ("last_interest", "TEXT"), ("last_game", "TEXT"),
            ("last_heist", "TEXT"), ("last_fish", "TEXT"),
            ("last_mine", "TEXT"), ("last_farm", "TEXT"),
            ("married_to", "INTEGER DEFAULT 0"),
        ]:
            try:
                cur.execute(f"ALTER TABLE players ADD COLUMN {col} {definition}")
            except Exception:
                pass

    conn.commit()
    conn.close()
    print(f"✅ DB ready ({'PostgreSQL' if db_type == 'pg' else 'SQLite'})")

def init_activities_db():
    pass  # Already handled in init_db

# ── Players ───────────────────────────────────────────────────────────

def get_player(user_id):
    return execute("SELECT * FROM players WHERE user_id=?", (user_id,), fetch="one")

def register_player(user_id, username, first_name):
    from config import Config
    execute("""
        INSERT INTO players (user_id, username, first_name, chips, age_ok)
        VALUES (?, ?, ?, ?, 1)
        ON CONFLICT (user_id) DO NOTHING
    """, (user_id, username or "unknown", first_name or "Player", Config.STARTING_CHIPS))

def update_chips(user_id, amount):
    execute("UPDATE players SET chips = chips + ? WHERE user_id=?", (amount, user_id))
    p = get_player(user_id)
    return p["chips"] if p else 0

def claim_daily(user_id, is_vip=False):
    from config import Config
    player = get_player(user_id)
    if not player:
        return False, 0, "Not registered."
    today = str(date.today())
    if player.get("last_daily") == today:
        return False, 0, "Already claimed today. Come back tomorrow!"
    bonus = Config.VIP_DAILY_BONUS if is_vip else Config.DAILY_BONUS
    execute("UPDATE players SET last_daily=?, chips=chips+? WHERE user_id=?",
            (today, bonus, user_id))
    return True, bonus, ""

def set_vip(user_id, status=1):
    execute("UPDATE players SET vip=? WHERE user_id=?", (status, user_id))

def get_leaderboard(limit=10):
    return execute(
        "SELECT user_id, first_name, username, chips, bank, vip FROM players ORDER BY (chips+bank) DESC LIMIT ?",
        (limit,), fetch="all") or []

# ── Bank ──────────────────────────────────────────────────────────────

def bank_deposit(user_id, amount):
    execute("UPDATE players SET chips=chips-?, bank=bank+? WHERE user_id=?", (amount, amount, user_id))

def bank_withdraw(user_id, amount):
    execute("UPDATE players SET bank=bank-?, chips=chips+? WHERE user_id=?", (amount, amount, user_id))

def claim_interest(user_id):
    p = get_player(user_id)
    if not p:
        return False, 0, "Not registered."
    if not p.get("bank") or p["bank"] <= 0:
        return False, 0, "No chips in bank! Deposit first with /deposit"
    today = str(date.today())
    if p.get("last_interest") == today:
        return False, 0, "Already claimed interest today. Come back tomorrow!"
    interest = max(1, int(p["bank"] * 0.03))
    execute("UPDATE players SET bank=bank+?, last_interest=? WHERE user_id=?",
            (interest, today, user_id))
    return True, interest, ""

# ── Cooldowns ─────────────────────────────────────────────────────────

def _check_cooldown(user_id, field, hours):
    p = get_player(user_id)
    if not p:
        return False, "Not registered."
    last = p.get(field)
    if last:
        last_dt   = datetime.fromisoformat(str(last)[:19])
        next_dt   = last_dt + timedelta(hours=hours)
        remaining = next_dt - datetime.now()
        if remaining.total_seconds() > 0:
            mins = int(remaining.total_seconds() // 60)
            hrs  = mins // 60
            mins = mins % 60
            if hrs > 0:
                return False, f"Wait *{hrs}h {mins}m* before doing this again."
            return False, f"Wait *{mins}m* before doing this again."
    return True, ""

def can_work(user_id):    return _check_cooldown(user_id, "last_work",   0.05)
def can_crime(user_id):   return _check_cooldown(user_id, "last_crime",  0.25)
def can_rob(user_id):     return _check_cooldown(user_id, "last_rob",    2)
def can_heist(user_id):   return _check_cooldown(user_id, "last_heist",  0.5)
def can_play_game(user_id): return _check_cooldown(user_id, "last_game", 0.0083)

def _set_ts(user_id, field):
    execute(f"UPDATE players SET {field}=? WHERE user_id=?",
            (datetime.now().isoformat()[:19], user_id))

def set_last_work(user_id):   _set_ts(user_id, "last_work")
def set_last_crime(user_id):  _set_ts(user_id, "last_crime")
def set_last_rob(user_id):    _set_ts(user_id, "last_rob")
def set_last_heist(user_id):  _set_ts(user_id, "last_heist")
def set_last_game(user_id):   _set_ts(user_id, "last_game")

# ── Marriage ──────────────────────────────────────────────────────────

def marry(user1, user2):
    execute("UPDATE players SET married_to=? WHERE user_id=?", (user2, user1))
    execute("UPDATE players SET married_to=? WHERE user_id=?", (user1, user2))

def divorce(user1, user2):
    execute("UPDATE players SET married_to=0 WHERE user_id=?", (user1,))
    execute("UPDATE players SET married_to=0 WHERE user_id=?", (user2,))

# ── Blackjack ─────────────────────────────────────────────────────────

def save_bj_game(game_id, chat_id, message_id, host_id, bet, data):
    execute("""
        INSERT INTO bj_games (game_id, chat_id, message_id, host_id, bet, state, data)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (game_id) DO UPDATE SET state=EXCLUDED.state, data=EXCLUDED.data
    """, (game_id, chat_id, message_id, host_id, bet, data.get("state","waiting"), json.dumps(data)))

def get_bj_game(game_id):
    row = execute("SELECT * FROM bj_games WHERE game_id=?", (game_id,), fetch="one")
    if row:
        if isinstance(row, dict):
            row["data"] = json.loads(row["data"])
        return row
    return None

def update_bj_game(game_id, data):
    execute("UPDATE bj_games SET state=?, data=? WHERE game_id=?",
            (data.get("state","waiting"), json.dumps(data), game_id))

def delete_bj_game(game_id):
    execute("DELETE FROM bj_games WHERE game_id=?", (game_id,))

# ── Dice ──────────────────────────────────────────────────────────────

def save_dice(challenge_id, chat_id, challenger, challenged, bet):
    execute("""
        INSERT INTO dice_challenges (challenge_id, chat_id, challenger, challenged, bet)
        VALUES (?, ?, ?, ?, ?)
    """, (challenge_id, chat_id, challenger, challenged, bet))

def get_dice(challenge_id):
    return execute("SELECT * FROM dice_challenges WHERE challenge_id=?",
                   (challenge_id,), fetch="one")

def update_dice_state(challenge_id, state):
    execute("UPDATE dice_challenges SET state=? WHERE challenge_id=?", (state, challenge_id))
