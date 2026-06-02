"""lottery.py — Daily Lottery System"""
import random, threading, time
from datetime import datetime, timedelta
from telebot import types
import database as db

_bot         = None
TICKET_PRICE = 5_000
MAX_TICKETS  = 10
MIN_JACKPOT  = 100_000

def fmt(n): return f"{n:,}"

def _row_val(row, key, idx):
    """Safe access for dict (PostgreSQL) or tuple (SQLite) rows"""
    if row is None: return None
    return row[key] if isinstance(row, dict) else row[idx]

# ── DB init ───────────────────────────────────────────────────────────
def init_lottery_db():
    is_pg = db.get_conn()[1] == "pg"
    db.execute("""
        CREATE TABLE IF NOT EXISTS lottery_tickets (
            id """ + ("SERIAL" if is_pg else "INTEGER") + """ PRIMARY KEY,
            user_id BIGINT NOT NULL,
            draw_date TEXT NOT NULL,
            tickets INTEGER DEFAULT 0
        )
    """)
    # Add unique index separately (safe if already exists)
    try:
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_lottery_user_date ON lottery_tickets (user_id, draw_date)")
    except: pass

    db.execute("""
        CREATE TABLE IF NOT EXISTS lottery_state (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    # Seed jackpot if not set
    existing = db.execute("SELECT value FROM lottery_state WHERE key='jackpot'", fetch="one")
    if not existing:
        db.execute("INSERT INTO lottery_state (key, value) VALUES (?, ?)", ("jackpot", str(MIN_JACKPOT)))
    print("✅ Lottery loaded")

# ── Jackpot helpers ───────────────────────────────────────────────────
def get_jackpot():
    row = db.execute("SELECT value FROM lottery_state WHERE key='jackpot'", fetch="one")
    if not row: return MIN_JACKPOT
    return int(_row_val(row, "value", 0))

def add_to_jackpot(amount):
    current = get_jackpot()
    db.execute("UPDATE lottery_state SET value=? WHERE key='jackpot'", (str(current + amount),))

def reset_jackpot():
    db.execute("UPDATE lottery_state SET value=? WHERE key='jackpot'", (str(MIN_JACKPOT),))

def get_draw_date():
    return datetime.now(timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%d")

# ── Ticket helpers ────────────────────────────────────────────────────
def get_tickets_today(user_id):
    today = get_draw_date()
    row   = db.execute(
        "SELECT tickets FROM lottery_tickets WHERE user_id=? AND draw_date=?",
        (user_id, today), fetch="one"
    )
    if not row: return 0
    return int(_row_val(row, "tickets", 0))

def buy_tickets(user_id, count):
    today    = get_draw_date()
    existing = db.execute(
        "SELECT tickets FROM lottery_tickets WHERE user_id=? AND draw_date=?",
        (user_id, today), fetch="one"
    )
    if existing:
        db.execute(
            "UPDATE lottery_tickets SET tickets=tickets+? WHERE user_id=? AND draw_date=?",
            (count, user_id, today)
        )
    else:
        db.execute(
            "INSERT INTO lottery_tickets (user_id, draw_date, tickets) VALUES (?,?,?)",
            (user_id, today, count)
        )

def get_all_tickets_today():
    today = get_draw_date()
    rows  = db.execute(
        "SELECT user_id, tickets FROM lottery_tickets WHERE draw_date=?",
        (today,), fetch="all"
    ) or []
    return [(_row_val(r,"user_id",0), _row_val(r,"tickets",1)) for r in rows]

def get_tickets_for_date(date_str):
    """Get all tickets for a specific draw date"""
    rows = db.execute(
        "SELECT user_id, tickets FROM lottery_tickets WHERE draw_date=?",
        (date_str,), fetch="all"
    ) or []
    return [(_row_val(r,"user_id",0), _row_val(r,"tickets",1)) for r in rows]

def get_total_tickets_today():
    return sum(t for _, t in get_all_tickets_today())

# ── Commands ──────────────────────────────────────────────────────────
def cmd_lottery(message):
    p = db.get_player(message.from_user.id)
    if not p: _bot.reply_to(message, "❗ Register first with /start"); return

    uid  = message.from_user.id
    args = message.text.split()

    # /lottery buy [amount]
    if len(args) >= 2 and args[1].lower() == "buy":
        count = int(args[2]) if len(args) >= 3 and args[2].isdigit() else 1
        _do_buy(message, uid, p, count)
        return

    # /lottery — show status
    _show_lottery(message, uid)

def _show_lottery(message, uid, edit=False, call=None):
    jackpot       = get_jackpot()
    my_tickets    = get_tickets_today(uid)
    total_tickets = get_total_tickets_today()
    now           = datetime.now(timezone.utc).replace(tzinfo=None)
    midnight      = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    diff          = midnight - now
    hrs           = int(diff.total_seconds() // 3600)
    mins          = int((diff.total_seconds() % 3600) // 60)
    win_chance    = f"{my_tickets/total_tickets*100:.1f}%" if total_tickets > 0 and my_tickets > 0 else "0%"

    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("🎟️ Buy 1 — 5,000",    callback_data="lottery_buy_1"),
        types.InlineKeyboardButton("🎟️ Buy 5 — 25,000",   callback_data="lottery_buy_5"),
    )
    markup.row(
        types.InlineKeyboardButton("🎟️ Buy 10 — 50,000",  callback_data="lottery_buy_10"),
        types.InlineKeyboardButton("📊 Leaderboard",       callback_data="lottery_lb"),
    )
    text = (
        f"🎰 *Daily Lottery*\n\n"
        f"💰 Jackpot: *{fmt(jackpot)}* chips\n"
        f"🎫 Your tickets: *{my_tickets}/{MAX_TICKETS}*\n"
        f"🎟️ Total tickets sold: *{total_tickets}*\n"
        f"🍀 Your win chance: *{win_chance}*\n\n"
        f"⏰ Next draw in: *{hrs}h {mins}m*\n"
        f"🎟️ Ticket price: *{fmt(TICKET_PRICE)}* chips"
    )
    if edit and call:
        try:
            _bot.edit_message_text(text, call.message.chat.id,
                call.message.message_id, reply_markup=markup, parse_mode="Markdown")
        except: pass
    else:
        _bot.reply_to(message, text, reply_markup=markup)

def _do_buy(message_or_call, uid, p, count, is_callback=False):
    my_tickets = get_tickets_today(uid)
    can_buy    = min(count, MAX_TICKETS - my_tickets)

    if can_buy <= 0:
        msg = f"You already have {my_tickets}/{MAX_TICKETS} tickets today!"
        if is_callback: _bot.answer_callback_query(message_or_call.id, msg, show_alert=True)
        else: _bot.reply_to(message_or_call, f"🎟️ {msg}")
        return

    cost = can_buy * TICKET_PRICE
    if p["chips"] < cost:
        msg = f"Not enough chips! Need {fmt(cost)}"
        if is_callback: _bot.answer_callback_query(message_or_call.id, msg, show_alert=True)
        else: _bot.reply_to(message_or_call, f"❌ {msg}")
        return

    db.update_chips(uid, -cost)
    buy_tickets(uid, can_buy)
    add_to_jackpot(int(cost * 0.8))

    new_tickets = my_tickets + can_buy
    new_jackpot = get_jackpot()

    if is_callback:
        _bot.answer_callback_query(message_or_call.id,
            f"✅ Bought {can_buy} ticket(s)! Jackpot: {fmt(new_jackpot)}", show_alert=True)
        _show_lottery(None, uid, edit=True, call=message_or_call)
    else:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🎟️ Buy More", callback_data="lottery_buy_1"))
        _bot.reply_to(message_or_call,
            f"🎟️ *Bought {can_buy} ticket{'s' if can_buy > 1 else ''}!*\n\n"
            f"💸 Paid: *{fmt(cost)}* chips\n"
            f"🎫 Your tickets today: *{new_tickets}/{MAX_TICKETS}*\n"
            f"💰 Jackpot: *{fmt(new_jackpot)}* chips\n\n"
            f"🕛 Draw at midnight UTC — good luck! 🍀", reply_markup=markup)

def cb_lottery(call):
    uid = call.from_user.id
    p   = db.get_player(uid)
    if not p: _bot.answer_callback_query(call.id, "Register first! /start"); return

    if call.data == "lottery_lb":
        rows = get_all_tickets_today()
        total = sum(t for _, t in rows)
        rows_sorted = sorted(rows, key=lambda x: x[1], reverse=True)[:10]
        lines  = ["📊 *Lottery Leaderboard*\n"]
        medals = ["🥇","🥈","🥉"]
        for i, (uid2, tix) in enumerate(rows_sorted):
            pl   = db.get_player(uid2)
            name = pl["first_name"] if pl else "Unknown"
            pct  = f"{tix/total*100:.1f}%" if total > 0 else "0%"
            lines.append(f"{medals[i] if i < 3 else f'{i+1}.'} *{name}* — {tix} tickets ({pct})")
        _bot.answer_callback_query(call.id)
        _bot.send_message(call.message.chat.id, "\n".join(lines))
        return

    count = int(call.data.split("_")[-1])
    _do_buy(call, uid, p, count, is_callback=True)

# ── Draw logic ────────────────────────────────────────────────────────
def run_draw():
    # Draw happens after midnight — tickets were bought on PREVIOUS day
    yesterday = (datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=1)).strftime("%Y-%m-%d")
    rows = get_tickets_for_date(yesterday)
    if not rows:
        reset_jackpot()
        print(f"🎟️ No tickets sold for {yesterday}, jackpot reset")
        return

    jackpot = get_jackpot()
    pool    = []
    for uid, tickets in rows:
        pool.extend([uid] * int(tickets))

    winner_id     = random.choice(pool)
    winner        = db.get_player(winner_id)
    winner_name   = winner["first_name"] if winner else "Unknown"
    total_tickets = sum(t for _, t in rows)
    winner_tickets= next((t for u, t in rows if u == winner_id), 0)

    db.update_chips(winner_id, jackpot)
    db.add_xp(winner_id, 100)

    msg = (
        f"🎰 *LOTTERY DRAW RESULTS!*\n\n"
        f"🏆 Winner: *{winner_name}*\n"
        f"💰 Jackpot won: *{fmt(jackpot)}* chips!\n"
        f"🎫 Winning tickets: *{winner_tickets}* / {total_tickets} total\n"
        f"🍀 Odds: *{winner_tickets/total_tickets*100:.1f}%*\n\n"
        f"🎟️ New lottery starting now! /lottery"
    )
    for cid in db.get_groups():
        try: _bot.send_message(cid, msg)
        except Exception as e: print(f"Lottery announce error {cid}: {e}")

    reset_jackpot()
    # Save last winner
    winner_val = f"{winner_name}|{jackpot}|{yesterday}"
    existing = db.execute("SELECT key FROM lottery_state WHERE key='last_winner'", fetch="one")
    if existing:
        db.execute("UPDATE lottery_state SET value=? WHERE key='last_winner'", (winner_val,))
    else:
        db.execute("INSERT INTO lottery_state (key,value) VALUES ('last_winner',?)", (winner_val,))
    print(f"🎰 Lottery: {winner_name} won {fmt(jackpot)} chips")

# ── Scheduler ─────────────────────────────────────────────────────────
def start_scheduler():
    def loop():
        last_draw_date = None
        while True:
            try:
                now  = datetime.now(timezone.utc).replace(tzinfo=None)
                today = now.strftime("%Y-%m-%d")
                # Draw at midnight UTC (00:00-00:02 window)
                is_draw_time = now.hour == 0 and now.minute < 2
                if is_draw_time and last_draw_date != today:
                    last_draw_date = today
                    # Double-check using DB last_winner date
                    row = db.execute("SELECT value FROM lottery_state WHERE key='last_winner'", fetch="one")
                    last_val = _row_val(row, "value", 0) if row else ""
                    last_date = last_val.split("|")[-1] if "|" in str(last_val) else ""
                    if last_date != today:
                        print(f"🎰 Running lottery draw for {today}")
                        run_draw()
            except Exception as e:
                print(f"Lottery scheduler error: {e}")
            time.sleep(60)  # check every minute — survives restarts
    threading.Thread(target=loop, daemon=True).start()
    print("✅ Lottery scheduler started (checks every 60s)")

# ── Register ──────────────────────────────────────────────────────────
def register_lottery(bot_instance):
    global _bot
    _bot = bot_instance
    init_lottery_db()
    start_scheduler()
    bot_instance.register_message_handler(cmd_lottery, commands=["lottery"])
    bot_instance.register_callback_query_handler(
        cb_lottery, func=lambda c: c.data.startswith("lottery_"))

def cmd_lastlottery(message):
    row = db.execute("SELECT value FROM lottery_state WHERE key='last_winner'", fetch="one")
    if not row:
        _bot.reply_to(message, "🎟️ No lottery has been drawn yet!"); return
    val  = _row_val(row, "value", 0)
    parts = val.split("|")
    if len(parts) < 3:
        _bot.reply_to(message, "🎟️ No lottery has been drawn yet!"); return
    name, jackpot, date = parts[0], int(parts[1]), parts[2]
    _bot.reply_to(message,
        f"🎰 *Last Lottery Winner*\n\n"
        f"🏆 Winner: *{name}*\n"
        f"💰 Jackpot: *{fmt(jackpot)}* chips\n"
        f"📅 Date: *{date}* (UTC)\n\n"
        f"🎟️ Buy tickets for today\'s draw: /lottery")

def cmd_drawlottery(message):
    """Admin only - manually trigger lottery draw"""
    from config import Config
    if message.from_user.id not in Config.ADMIN_IDS:
        _bot.reply_to(message, "❌ Admin only!"); return
    _bot.reply_to(message, "🎰 Running lottery draw now...")
    try:
        run_draw()
        _bot.reply_to(message, "✅ Draw complete! Check /lastlottery")
    except Exception as e:
        _bot.reply_to(message, f"❌ Draw error: {e}")
