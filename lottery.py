"""lottery.py — Daily Lottery System
- Players buy tickets for 5,000 chips each (max 10/day)
- Jackpot grows with every ticket sold
- Draw happens daily at midnight (UTC)
- Winner announced in all registered group chats
"""
import random
import threading
import time
from datetime import datetime, timedelta
from telebot import types
import database as db

_bot        = None
TICKET_PRICE = 5_000
MAX_TICKETS  = 10
MIN_JACKPOT  = 100_000   # jackpot never goes below this

def fmt(n): return f"{n:,}"

# ── DB init ───────────────────────────────────────────────────────────
def init_lottery_db():
    db.execute("""
        CREATE TABLE IF NOT EXISTS lottery_tickets (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            draw_date TEXT NOT NULL,
            tickets INTEGER DEFAULT 0,
            UNIQUE(user_id, draw_date)
        )
    """ if db.get_conn()[1] == "pg" else """
        CREATE TABLE IF NOT EXISTS lottery_tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            draw_date TEXT NOT NULL,
            tickets INTEGER DEFAULT 0,
            UNIQUE(user_id, draw_date)
        )
    """)
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
    return int(row[0]) if row else MIN_JACKPOT

def add_to_jackpot(amount):
    db.execute("""
        INSERT INTO lottery_state (key, value) VALUES ('jackpot', ?)
        ON CONFLICT (key) DO UPDATE SET value = CAST(CAST(value AS BIGINT) + ? AS TEXT)
    """, (str(amount), amount))

def reset_jackpot():
    db.execute("UPDATE lottery_state SET value=? WHERE key='jackpot'", (str(MIN_JACKPOT),))

def get_draw_date():
    return datetime.utcnow().strftime("%Y-%m-%d")

# ── Ticket helpers ────────────────────────────────────────────────────
def get_tickets_today(user_id):
    today = get_draw_date()
    row = db.execute(
        "SELECT tickets FROM lottery_tickets WHERE user_id=? AND draw_date=?",
        (user_id, today), fetch="one"
    )
    return row[0] if row else 0

def buy_tickets(user_id, count):
    today = get_draw_date()
    db.execute("""
        INSERT INTO lottery_tickets (user_id, draw_date, tickets) VALUES (?, ?, ?)
        ON CONFLICT (user_id, draw_date) DO UPDATE SET tickets = tickets + ?
    """, (user_id, today, count, count))

def get_all_tickets_today():
    today = get_draw_date()
    rows = db.execute(
        "SELECT user_id, tickets FROM lottery_tickets WHERE draw_date=?",
        (today,), fetch="all"
    )
    return rows or []

def get_total_tickets_today():
    rows = get_all_tickets_today()
    return sum(r[1] for r in rows)

# ── Commands ──────────────────────────────────────────────────────────
def cmd_lottery(message):
    p = db.get_player(message.from_user.id)
    if not p: _bot.reply_to(message, "❗ Register first with /start"); return

    uid          = message.from_user.id
    args         = message.text.split()
    jackpot      = get_jackpot()
    my_tickets   = get_tickets_today(uid)
    total_tickets= get_total_tickets_today()

    # /lottery buy [amount]
    if len(args) >= 2 and args[1].lower() == "buy":
        count = int(args[2]) if len(args) >= 3 and args[2].isdigit() else 1
        count = max(1, min(count, MAX_TICKETS - my_tickets))

        if my_tickets >= MAX_TICKETS:
            _bot.reply_to(message,
                f"🎟️ You already have *{my_tickets}* tickets today!\n"
                f"Max is *{MAX_TICKETS}* per day. Come back tomorrow!"); return

        cost = count * TICKET_PRICE
        if p["chips"] < cost:
            _bot.reply_to(message,
                f"❌ Not enough chips!\nNeed: *{fmt(cost)}* | Have: *{fmt(p['chips'])}*"); return

        db.update_chips(uid, -cost)
        buy_tickets(uid, count)
        add_to_jackpot(int(cost * 0.8))   # 80% of ticket sales go to jackpot

        new_jackpot  = get_jackpot()
        new_tickets  = my_tickets + count
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🎟️ Buy More", callback_data=f"lottery_buy_1"))
        _bot.reply_to(message,
            f"🎟️ *Bought {count} ticket{'s' if count > 1 else ''}!*\n\n"
            f"💸 Paid: *{fmt(cost)}* chips\n"
            f"🎫 Your tickets today: *{new_tickets}/{MAX_TICKETS}*\n"
            f"💰 Current jackpot: *{fmt(new_jackpot)}* chips\n\n"
            f"🕛 Draw happens at midnight UTC — good luck! 🍀",
            reply_markup=markup)
        return

    # /lottery — show status
    now      = datetime.utcnow()
    midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    diff     = midnight - now
    hrs      = int(diff.total_seconds() // 3600)
    mins     = int((diff.total_seconds() % 3600) // 60)

    win_chance = f"{(my_tickets/total_tickets*100):.1f}%" if total_tickets > 0 and my_tickets > 0 else "0%"

    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("🎟️ Buy 1 — 5,000", callback_data="lottery_buy_1"),
        types.InlineKeyboardButton("🎟️ Buy 5 — 25,000", callback_data="lottery_buy_5"),
    )
    markup.row(
        types.InlineKeyboardButton("🎟️ Buy 10 — 50,000", callback_data="lottery_buy_10"),
        types.InlineKeyboardButton("📊 Leaderboard", callback_data="lottery_lb"),
    )

    _bot.reply_to(message,
        f"🎰 *Daily Lottery*\n\n"
        f"💰 Jackpot: *{fmt(jackpot)}* chips\n"
        f"🎫 Your tickets: *{my_tickets}/{MAX_TICKETS}*\n"
        f"🎟️ Total tickets sold: *{total_tickets}*\n"
        f"🍀 Your win chance: *{win_chance}*\n\n"
        f"⏰ Next draw in: *{hrs}h {mins}m*\n"
        f"🎟️ Ticket price: *{fmt(TICKET_PRICE)}* chips",
        reply_markup=markup)

def cb_lottery(call):
    uid = call.from_user.id
    p   = db.get_player(uid)
    if not p: _bot.answer_callback_query(call.id, "Register first! /start"); return

    data = call.data

    if data == "lottery_lb":
        rows = get_all_tickets_today()
        rows_sorted = sorted(rows, key=lambda x: x[1], reverse=True)[:10]
        total = sum(r[1] for r in rows_sorted)
        lines = ["📊 *Lottery Leaderboard*\n"]
        medals = ["🥇","🥈","🥉"]
        for i, (uid2, tix) in enumerate(rows_sorted):
            player = db.get_player(uid2)
            name   = player["first_name"] if player else "Unknown"
            pct    = f"{tix/total*100:.1f}%" if total > 0 else "0%"
            medal  = medals[i] if i < 3 else f"{i+1}."
            lines.append(f"{medal} *{name}* — {tix} tickets ({pct})")
        _bot.answer_callback_query(call.id)
        _bot.send_message(call.message.chat.id, "\n".join(lines))
        return

    # Buy tickets via button
    count = int(data.split("_")[-1])
    my_tickets = get_tickets_today(uid)
    can_buy    = min(count, MAX_TICKETS - my_tickets)

    if can_buy <= 0:
        _bot.answer_callback_query(call.id, f"You already have {my_tickets}/{MAX_TICKETS} tickets today!", show_alert=True)
        return

    cost = can_buy * TICKET_PRICE
    if p["chips"] < cost:
        _bot.answer_callback_query(call.id, f"Not enough chips! Need {fmt(cost)}", show_alert=True)
        return

    db.update_chips(uid, -cost)
    buy_tickets(uid, can_buy)
    add_to_jackpot(int(cost * 0.8))

    new_jackpot = get_jackpot()
    new_tickets = my_tickets + can_buy
    _bot.answer_callback_query(call.id, f"✅ Bought {can_buy} ticket(s)! Jackpot: {fmt(new_jackpot)}", show_alert=True)

    # Refresh the message
    jackpot      = get_jackpot()
    total_tickets= get_total_tickets_today()
    win_chance   = f"{(new_tickets/total_tickets*100):.1f}%" if total_tickets > 0 else "0%"
    now          = datetime.utcnow()
    midnight     = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    diff         = midnight - now
    hrs          = int(diff.total_seconds() // 3600)
    mins_left    = int((diff.total_seconds() % 3600) // 60)

    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("🎟️ Buy 1 — 5,000", callback_data="lottery_buy_1"),
        types.InlineKeyboardButton("🎟️ Buy 5 — 25,000", callback_data="lottery_buy_5"),
    )
    markup.row(
        types.InlineKeyboardButton("🎟️ Buy 10 — 50,000", callback_data="lottery_buy_10"),
        types.InlineKeyboardButton("📊 Leaderboard", callback_data="lottery_lb"),
    )
    try:
        _bot.edit_message_text(
            f"🎰 *Daily Lottery*\n\n"
            f"💰 Jackpot: *{fmt(jackpot)}* chips\n"
            f"🎫 Your tickets: *{new_tickets}/{MAX_TICKETS}*\n"
            f"🎟️ Total tickets sold: *{total_tickets}*\n"
            f"🍀 Your win chance: *{win_chance}*\n\n"
            f"⏰ Next draw in: *{hrs}h {mins_left}m*\n"
            f"🎟️ Ticket price: *{fmt(TICKET_PRICE)}* chips",
            call.message.chat.id, call.message.message_id,
            reply_markup=markup, parse_mode="Markdown"
        )
    except: pass

# ── Draw logic ────────────────────────────────────────────────────────
def run_draw():
    """Pick a weighted random winner and announce"""
    rows = get_all_tickets_today()
    if not rows:
        print("🎟️ Lottery draw: no tickets sold today, skipping")
        reset_jackpot()
        return

    jackpot = get_jackpot()

    # Weighted random — more tickets = higher chance
    pool = []
    for user_id, tickets in rows:
        pool.extend([user_id] * tickets)

    winner_id = random.choice(pool)
    winner    = db.get_player(winner_id)
    winner_name = winner["first_name"] if winner else "Unknown"

    # Pay winner
    db.update_chips(winner_id, jackpot)
    db.add_xp(winner_id, 100)

    total_tickets = sum(r[1] for r in rows)
    winner_tickets = next((r[1] for r in rows if r[0] == winner_id), 0)

    # Announce in all groups
    msg = (
        f"🎰 *LOTTERY DRAW RESULTS!*\n\n"
        f"🏆 Winner: *{winner_name}*\n"
        f"💰 Jackpot won: *{fmt(jackpot)}* chips!\n"
        f"🎫 Winning tickets: *{winner_tickets}* / {total_tickets} total\n"
        f"🍀 Odds: *{winner_tickets/total_tickets*100:.1f}%*\n\n"
        f"🎟️ New lottery starting now!\n"
        f"Buy tickets with /lottery"
    )

    groups = db.execute("SELECT chat_id FROM groups", fetch="all")
    if groups:
        for (chat_id,) in groups:
            try: _bot.send_message(chat_id, msg)
            except: pass

    reset_jackpot()
    print(f"🎰 Lottery draw done! Winner: {winner_name} won {fmt(jackpot)} chips")

# ── Scheduler ─────────────────────────────────────────────────────────
def start_scheduler():
    def loop():
        while True:
            now     = datetime.utcnow()
            midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            wait    = (midnight - now).total_seconds()
            time.sleep(wait)
            try:
                run_draw()
            except Exception as e:
                print(f"Lottery draw error: {e}")

    t = threading.Thread(target=loop, daemon=True)
    t.start()
    print("✅ Lottery scheduler started")

# ── Register ──────────────────────────────────────────────────────────
def register_lottery(bot_instance):
    global _bot
    _bot = bot_instance
    init_lottery_db()
    start_scheduler()
    bot_instance.register_message_handler(cmd_lottery, commands=["lottery"])
    bot_instance.register_callback_query_handler(
        cb_lottery,
        func=lambda c: c.data.startswith("lottery_")
    )
