import sqlite3
import json
import os
from datetime import datetime, date, timedelta

DB_PATH = os.environ.get("DB_PATH", "casino.db")

def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS players (
            user_id      INTEGER PRIMARY KEY,
            username     TEXT,
            first_name   TEXT,
            chips        INTEGER DEFAULT 10000,
            bank         INTEGER DEFAULT 0,
            vip          INTEGER DEFAULT 0,
            age_ok       INTEGER DEFAULT 0,
            last_daily   TEXT,
            last_work    TEXT,
            last_crime   TEXT,
            last_rob     TEXT,
            last_interest TEXT,
            married_to   INTEGER DEFAULT 0,
            joined_at    TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    for col, definition in [
        ("bank",          "INTEGER DEFAULT 0"),
        ("last_work",     "TEXT"),
        ("last_crime",    "TEXT"),
        ("last_rob",      "TEXT"),
        ("last_interest", "TEXT"),
        ("married_to",    "INTEGER DEFAULT 0"),
    ]:
        try:
            c.execute(f"ALTER TABLE players ADD COLUMN {col} {definition}")
        except Exception:
            pass
    c.execute("""
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
    c.execute("""
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
    conn.commit()
    conn.close()

def get_player(user_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM players WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def register_player(user_id, username, first_name):
    from config import Config
    conn = get_conn()
    conn.execute("""
        INSERT OR IGNORE INTO players (user_id, username, first_name, chips, age_ok)
        VALUES (?, ?, ?, ?, 1)
    """, (user_id, username or "unknown", first_name or "Player", Config.STARTING_CHIPS))
    conn.commit()
    conn.close()

def update_chips(user_id, amount):
    conn = get_conn()
    conn.execute("UPDATE players SET chips = chips + ? WHERE user_id=?", (amount, user_id))
    conn.commit()
    row = conn.execute("SELECT chips FROM players WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    return row["chips"] if row else 0

def claim_daily(user_id, is_vip=False):
    from config import Config
    player = get_player(user_id)
    if not player:
        return False, 0, "Not registered."
    today = str(date.today())
    if player["last_daily"] == today:
        return False, 0, "Already claimed today. Come back tomorrow!"
    bonus = Config.VIP_DAILY_BONUS if is_vip else Config.DAILY_BONUS
    conn = get_conn()
    conn.execute("UPDATE players SET last_daily=?, chips=chips+? WHERE user_id=?", (today, bonus, user_id))
    conn.commit()
    conn.close()
    return True, bonus, ""

def set_vip(user_id, status=1):
    conn = get_conn()
    conn.execute("UPDATE players SET vip=? WHERE user_id=?", (status, user_id))
    conn.commit()
    conn.close()

def get_leaderboard(limit=10):
    conn = get_conn()
    rows = conn.execute(
        "SELECT user_id, first_name, username, chips, bank, vip FROM players ORDER BY (chips+bank) DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def bank_deposit(user_id, amount):
    conn = get_conn()
    conn.execute("UPDATE players SET chips=chips-?, bank=bank+? WHERE user_id=?", (amount, amount, user_id))
    conn.commit()
    conn.close()

def bank_withdraw(user_id, amount):
    conn = get_conn()
    conn.execute("UPDATE players SET bank=bank-?, chips=chips+? WHERE user_id=?", (amount, amount, user_id))
    conn.commit()
    conn.close()

def claim_interest(user_id):
    p = get_player(user_id)
    if not p:
        return False, 0, "Not registered."
    if not p["bank"] or p["bank"] <= 0:
        return False, 0, "No chips in bank! Deposit first with /deposit"
    today = str(date.today())
    if p.get("last_interest") == today:
        return False, 0, "Already claimed interest today. Come back tomorrow!"
    interest = max(1, int(p["bank"] * 0.03))
    conn = get_conn()
    conn.execute("UPDATE players SET bank=bank+?, last_interest=? WHERE user_id=?", (interest, today, user_id))
    conn.commit()
    conn.close()
    return True, interest, ""

def _check_cooldown(user_id, field, hours):
    p = get_player(user_id)
    if not p:
        return False, "Not registered."
    last = p.get(field)
    if last:
        last_dt   = datetime.fromisoformat(last)
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

def can_work(user_id):   return _check_cooldown(user_id, "last_work",  1)
def can_crime(user_id):  return _check_cooldown(user_id, "last_crime", 2)
def can_rob(user_id):    return _check_cooldown(user_id, "last_rob",   2)

def _set_timestamp(user_id, field):
    conn = get_conn()
    conn.execute(f"UPDATE players SET {field}=? WHERE user_id=?", (datetime.now().isoformat(), user_id))
    conn.commit()
    conn.close()

def set_last_work(user_id):  _set_timestamp(user_id, "last_work")
def set_last_crime(user_id): _set_timestamp(user_id, "last_crime")
def set_last_rob(user_id):   _set_timestamp(user_id, "last_rob")

def marry(user1, user2):
    conn = get_conn()
    conn.execute("UPDATE players SET married_to=? WHERE user_id=?", (user2, user1))
    conn.execute("UPDATE players SET married_to=? WHERE user_id=?", (user1, user2))
    conn.commit()
    conn.close()

def divorce(user1, user2):
    conn = get_conn()
    conn.execute("UPDATE players SET married_to=0 WHERE user_id=?", (user1,))
    conn.execute("UPDATE players SET married_to=0 WHERE user_id=?", (user2,))
    conn.commit()
    conn.close()

def save_bj_game(game_id, chat_id, message_id, host_id, bet, data):
    conn = get_conn()
    conn.execute("""
        INSERT OR REPLACE INTO bj_games (game_id, chat_id, message_id, host_id, bet, state, data)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (game_id, chat_id, message_id, host_id, bet, data.get("state", "waiting"), json.dumps(data)))
    conn.commit()
    conn.close()

def get_bj_game(game_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM bj_games WHERE game_id=?", (game_id,)).fetchone()
    conn.close()
    if row:
        d = dict(row)
        d["data"] = json.loads(d["data"])
        return d
    return None

def update_bj_game(game_id, data):
    conn = get_conn()
    conn.execute("UPDATE bj_games SET state=?, data=? WHERE game_id=?",
                 (data.get("state", "waiting"), json.dumps(data), game_id))
    conn.commit()
    conn.close()

def delete_bj_game(game_id):
    conn = get_conn()
    conn.execute("DELETE FROM bj_games WHERE game_id=?", (game_id,))
    conn.commit()
    conn.close()

def save_dice(challenge_id, chat_id, challenger, challenged, bet):
    conn = get_conn()
    conn.execute("""
        INSERT INTO dice_challenges (challenge_id, chat_id, challenger, challenged, bet)
        VALUES (?, ?, ?, ?, ?)
    """, (challenge_id, chat_id, challenger, challenged, bet))
    conn.commit()
    conn.close()

def get_dice(challenge_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM dice_challenges WHERE challenge_id=?", (challenge_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def update_dice_state(challenge_id, state):
    conn = get_conn()
    conn.execute("UPDATE dice_challenges SET state=? WHERE challenge_id=?", (state, challenge_id))
    conn.commit()
    conn.close()
