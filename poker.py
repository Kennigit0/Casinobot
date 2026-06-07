"""poker.py — Texas Hold'em Poker
- /poker [min_bet] — start a table
- 2–6 players join via button
- Hole cards sent via DM (private)
- Community cards in group
- Fold / Check / Call / Raise buttons
- 60s timeout → auto-fold
"""
import random, threading, time
from itertools import combinations
from telebot import types
import database as db
import gems as gems_mod

_bot = None
active_tables = {}   # chat_id -> PokerTable state

SUITS  = ["♠️","♥️","♦️","♣️"]
RANKS  = ["2","3","4","5","6","7","8","9","10","J","Q","K","A"]
RANK_V = {r: i for i, r in enumerate(RANKS, 2)}  # 2=2 ... A=14

JOIN_TIME    = 60   # seconds to join
ACTION_TIME  = 60   # seconds per action
MIN_PLAYERS  = 2
MAX_PLAYERS  = 6

def fmt(n): return f"{n:,}"

# ── Deck ──────────────────────────────────────────────────────────────
def make_deck():
    deck = [(r, s) for s in SUITS for r in RANKS]
    random.shuffle(deck)
    return deck

def card_str(card):
    return f"{card[0]}{card[1]}"

def hand_str(cards):
    return " ".join(card_str(c) for c in cards)

# ── Hand evaluator ────────────────────────────────────────────────────
def hand_rank(cards):
    """Evaluate best 5-card hand from list of cards. Returns (rank, tiebreakers)"""
    best = max(combinations(cards, 5), key=_score_hand)
    return _score_hand(best)

def _score_hand(five):
    vals = sorted([RANK_V[c[0]] for c in five], reverse=True)
    suits = [c[1] for c in five]
    flush   = len(set(suits)) == 1
    unique  = sorted(set(vals), reverse=True)
    counts  = sorted([vals.count(v) for v in unique], reverse=True)

    straight = False
    if len(unique) == 5:
        if vals[0] - vals[4] == 4:
            straight = True
        # Wheel: A-2-3-4-5
        if unique == [14, 5, 4, 3, 2]:
            straight = True
            vals = [5, 4, 3, 2, 1]

    if straight and flush: return (8, vals)
    if counts[0] == 4:     return (7, vals)
    if counts[:2] == [3,2]: return (6, vals)
    if flush:               return (5, vals)
    if straight:            return (4, vals)
    if counts[0] == 3:     return (3, vals)
    if counts[:2] == [2,2]: return (2, vals)
    if counts[0] == 2:     return (1, vals)
    return (0, vals)

HAND_NAMES = {8:"Royal/Straight Flush",7:"Four of a Kind",6:"Full House",
              5:"Flush",4:"Straight",3:"Three of a Kind",2:"Two Pair",
              1:"One Pair",0:"High Card"}

# ── Table state ───────────────────────────────────────────────────────
def new_table(chat_id, host_id, min_bet):
    return {
        "chat_id":    chat_id,
        "host_id":    host_id,
        "min_bet":    min_bet,
        "phase":      "joining",    # joining|preflop|flop|turn|river|showdown
        "players":    [],           # [{"uid","name","chips","hole","bet","folded","allin"}]
        "deck":       [],
        "community":  [],
        "pot":        0,
        "cur_bet":    0,
        "acting":     0,            # index of current player
        "msg_id":     None,
        "small_blind_idx": 0,
        "raises_left": 3,           # max raises per round
        "acted":      set(),        # uids who acted this round
        "timer":      None,
    }

def get_player(table, uid):
    return next((p for p in table["players"] if p["uid"] == uid), None)

def active_players(table):
    return [p for p in table["players"] if not p.get("folded") and not p.get("allin")]

def all_acted(table):
    ap = active_players(table)
    if not ap: return True
    return all(p["uid"] in table["acted"] for p in ap)

# ── Board render ──────────────────────────────────────────────────────
def render_board(table):
    phase    = table["phase"]
    pot      = table["pot"]
    cur_bet  = table["cur_bet"]
    community= table["community"]
    players  = table["players"]

    com_str = hand_str(community) if community else "_No cards yet_"
    phase_label = {"preflop":"Pre-Flop","flop":"Flop","turn":"Turn",
                   "river":"River","showdown":"Showdown"}.get(phase, phase.title())

    lines = [f"♠️ *Texas Hold'em — {phase_label}*\n",
             f"🃏 Community: {com_str}",
             f"💰 Pot: *{fmt(pot)}* | Current bet: *{fmt(cur_bet)}*\n"]

    for p in players:
        status = "💀 Folded" if p.get("folded") else ("🔒 All-in" if p.get("allin") else "🟢")
        bet_str = f" (bet: {fmt(p['bet'])})" if p["bet"] > 0 else ""
        lines.append(f"{status} *{p['name']}*{bet_str} — 💰{fmt(p['chips'])}")

    # Show current actor
    if phase not in ("joining","showdown"):
        ap = active_players(table)
        if ap:
            actor = ap[table["acting"] % len(ap)] if ap else None
            if actor:
                lines.append(f"\n⏳ *{actor['name']}'s turn* — {ACTION_TIME}s")

    return "\n".join(lines)

def action_markup(table, uid):
    ap = active_players(table)
    if not ap: return None
    actor = ap[table["acting"] % len(ap)]
    if actor["uid"] != uid: return None

    p       = get_player(table, uid)
    to_call = table["cur_bet"] - p["bet"]
    markup  = types.InlineKeyboardMarkup()

    fold_btn  = types.InlineKeyboardButton("❌ Fold",  callback_data=f"poker_fold_{uid}")
    if to_call <= 0:
        check_btn = types.InlineKeyboardButton("✅ Check", callback_data=f"poker_check_{uid}")
        raise_btn = types.InlineKeyboardButton(f"⬆️ Raise {fmt(table['min_bet'])}", callback_data=f"poker_raise_{uid}")
        markup.row(fold_btn, check_btn, raise_btn)
    else:
        call_amt  = min(to_call, p["chips"])
        call_btn  = types.InlineKeyboardButton(f"📞 Call {fmt(call_amt)}", callback_data=f"poker_call_{uid}")
        raise_btn = types.InlineKeyboardButton(f"⬆️ Raise {fmt(table['min_bet'])}", callback_data=f"poker_raise_{uid}")
        markup.row(fold_btn, call_btn, raise_btn)
    return markup

# ── Game flow ─────────────────────────────────────────────────────────
def start_game(chat_id):
    table = active_tables.get(chat_id)
    if not table or len(table["players"]) < MIN_PLAYERS:
        return

    # Deal cards
    table["deck"] = make_deck()
    for p in table["players"]:
        p["hole"]   = [table["deck"].pop(), table["deck"].pop()]
        p["bet"]    = 0
        p["folded"] = False
        p["allin"]  = False

    # Post blinds
    players = table["players"]
    sb_idx  = table["small_blind_idx"] % len(players)
    bb_idx  = (sb_idx + 1) % len(players)
    sb_amt  = table["min_bet"]
    bb_amt  = table["min_bet"] * 2

    for idx, amt in [(sb_idx, sb_amt), (bb_idx, bb_amt)]:
        p = players[idx]
        actual = min(amt, p["chips"])
        p["chips"] -= actual
        p["bet"]   += actual
        table["pot"] += actual

    table["cur_bet"] = bb_amt
    table["acting"]  = (bb_idx + 1) % len(players)
    table["phase"]   = "preflop"
    table["acted"]   = set()

    # Send hole cards via DM
    for p in players:
        try:
            _bot.send_message(p["uid"],
                f"🃏 *Your hole cards for the poker game:*\n\n"
                f"*{hand_str(p['hole'])}*\n\n"
                f"Good luck! 🍀")
        except:
            pass  # Player didn't start bot in DM

    # Update board
    _update_board(table)
    _start_action_timer(table)

def _update_board(table, markup=None):
    chat_id = table["chat_id"]
    text    = render_board(table)

    # Get markup for current actor
    if markup is None and table["phase"] not in ("joining","showdown"):
        ap = active_players(table)
        if ap:
            actor = ap[table["acting"] % len(ap)]
            markup = action_markup(table, actor["uid"])

    try:
        if table["msg_id"]:
            _bot.edit_message_text(text, chat_id, table["msg_id"],
                reply_markup=markup, parse_mode="Markdown")
        else:
            msg = _bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
            table["msg_id"] = msg.message_id
    except: pass

def _start_action_timer(table):
    if table.get("timer"):
        try: table["timer"].cancel()
        except: pass

    ap = active_players(table)
    if not ap: return

    actor = ap[table["acting"] % len(ap)]

    def timeout():
        t = active_tables.get(table["chat_id"])
        if not t: return
        ap2 = active_players(t)
        if not ap2: return
        act = ap2[t["acting"] % len(ap2)]
        if act["uid"] == actor["uid"]:
            act["folded"] = True
            t["acted"].add(act["uid"])
            try:
                _bot.send_message(t["chat_id"],
                    f"⏰ *{act['name']}* timed out — auto-folded!")
            except: pass
            _advance(t)

    timer = threading.Timer(ACTION_TIME, timeout)
    timer.daemon = True
    timer.start()
    table["timer"] = timer

def _advance(table):
    """Advance game: next player or next phase"""
    ap = active_players(table)
    remaining = [p for p in table["players"] if not p.get("folded")]

    # Only one player left
    if len(remaining) == 1:
        _end_game(table, remaining)
        return

    # Check if betting round is over
    if all_acted(table) and all(
        p["bet"] == table["cur_bet"] or p.get("allin") or p.get("folded")
        for p in table["players"]
    ):
        _next_phase(table)
        return

    # Move to next active player
    if ap:
        table["acting"] = (table["acting"] + 1) % len(ap)
        while ap[table["acting"] % len(ap)]["uid"] in table["acted"]:
            table["acting"] = (table["acting"] + 1) % len(ap)
            if all_acted(table):
                _next_phase(table)
                return

    _update_board(table)
    _start_action_timer(table)

def _next_phase(table):
    phase_order = ["preflop","flop","turn","river","showdown"]
    cur_idx = phase_order.index(table["phase"])

    if cur_idx >= len(phase_order) - 2:
        # River done → showdown
        _showdown(table)
        return

    next_phase = phase_order[cur_idx + 1]
    table["phase"]   = next_phase
    table["acted"]   = set()
    table["cur_bet"] = 0
    table["raises_left"] = 3

    # Reset bets for new round
    for p in table["players"]:
        p["bet"] = 0

    # Deal community cards
    if next_phase == "flop":
        table["deck"].pop()  # burn
        table["community"] = [table["deck"].pop() for _ in range(3)]
    elif next_phase in ("turn","river"):
        table["deck"].pop()  # burn
        table["community"].append(table["deck"].pop())

    # Reset acting to first active player after dealer
    ap = active_players(table)
    if ap:
        table["acting"] = 0

    try:
        _bot.send_message(table["chat_id"],
            f"📋 *{next_phase.title()}!* — {hand_str(table['community'])}")
    except: pass

    _update_board(table)
    _start_action_timer(table)

def _showdown(table):
    table["phase"] = "showdown"
    if table.get("timer"):
        try: table["timer"].cancel()
        except: pass

    remaining = [p for p in table["players"] if not p.get("folded")]
    _end_game(table, remaining)

def _end_game(table, winners_pool):
    if table.get("timer"):
        try: table["timer"].cancel()
        except: pass

    chat_id = table["chat_id"]

    # ALWAYS return remaining in-game chips to ALL players first
    for pl in table["players"]:
        if pl["chips"] > 0:
            db.update_chips(pl["uid"], pl["chips"])

    if len(winners_pool) == 1:
        winner = winners_pool[0]
        db.update_chips(winner["uid"], table["pot"])
        try:
            _bot.send_message(chat_id,
                f"🏆 *{winner['name']}* wins the pot of *{fmt(table['pot'])}* chips!\n"
                f"_(Everyone else folded)_")
        except: pass
    else:
        # Evaluate hands
        all_cards = {pl["uid"]: pl["hole"] + table["community"] for pl in winners_pool}
        scores    = {pl["uid"]: hand_rank(all_cards[pl["uid"]]) for pl in winners_pool}
        best      = max(scores.values())
        winners   = [pl for pl in winners_pool if scores[pl["uid"]] == best]

        share = table["pot"] // len(winners)
        lines = [f"🃏 *Showdown!*\n"]

        for pl in winners_pool:
            score = scores[pl["uid"]]
            hname = HAND_NAMES[score[0]]
            lines.append(f"• *{pl['name']}*: {hand_str(pl['hole'])} — _{hname}_")

        lines.append("")
        if len(winners) == 1:
            w = winners[0]
            db.update_chips(w["uid"], table["pot"])
            lines.append(f"🏆 *{w['name']}* wins *{fmt(table['pot'])}* chips!")
        else:
            for w in winners:
                db.update_chips(w["uid"], share)
            names = ", ".join(w["name"] for w in winners)
            lines.append(f"🤝 *Split pot!* {names} each get *{fmt(share)}* chips!")

        try:
            _bot.send_message(chat_id, "\n".join(lines))
        except: pass

    active_tables.pop(chat_id, None)

# ── Commands ──────────────────────────────────────────────────────────
def cmd_poker(message):
    p = db.get_player(message.from_user.id)
    if not p: _bot.reply_to(message, "❗ Register first with /start"); return
    if message.chat.type == "private":
        _bot.reply_to(message, "❌ Poker is a group game! Use it in a group."); return

    chat_id = message.chat.id
    if chat_id in active_tables:
        _bot.reply_to(message, "⚠️ A poker table is already active! Join it or wait."); return

    args = message.text.split()
    try: min_bet = int(args[1].replace(",","")) if len(args) > 1 else 1000
    except: min_bet = 1000
    if min_bet < 100:
        _bot.reply_to(message, "❌ Minimum bet is 100 chips."); return

    uid = message.from_user.id
    if p["chips"] < min_bet * 2:
        _bot.reply_to(message, f"❌ Need at least *{fmt(min_bet*2)}* chips to host."); return

    table = new_table(chat_id, uid, min_bet)
    # Host joins
    p2 = db.get_player(uid)
    buy_in = min(p2["chips"], min_bet * 20)  # max 20x blind buy-in
    db.update_chips(uid, -buy_in)
    table["players"].append({"uid": uid, "name": message.from_user.first_name,
                              "chips": buy_in, "hole": [], "bet": 0,
                              "folded": False, "allin": False})
    active_tables[chat_id] = table

    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("🃏 Join Table", callback_data=f"poker_join_{uid}_{min_bet}"),
        types.InlineKeyboardButton("▶️ Start Game", callback_data=f"poker_start_{uid}"),
    )

    msg = _bot.reply_to(message,
        f"♠️ *Poker Table — Texas Hold'em*\n\n"
        f"💰 Blind: *{fmt(min_bet)}* / *{fmt(min_bet*2)}*\n"
        f"👥 Players: *1/{MAX_PLAYERS}*\n"
        f"1. *{message.from_user.first_name}* — {fmt(buy_in)} chips\n\n"
        f"⚠️ Hole cards sent via *private DM*! Start the bot in DM first.\n"
        f"⏳ Joining for {JOIN_TIME}s...",
        reply_markup=markup)
    table["msg_id"] = msg.message_id

    # Auto-start after JOIN_TIME
    def auto_start():
        t = active_tables.get(chat_id)
        if t and t["phase"] == "joining" and len(t["players"]) >= MIN_PLAYERS:
            start_game(chat_id)
        elif t and t["phase"] == "joining":
            # Not enough players
            for pl in t["players"]:
                db.update_chips(pl["uid"], pl["chips"])
            active_tables.pop(chat_id, None)
            try: _bot.send_message(chat_id, "❌ Not enough players — table closed, chips refunded.")
            except: pass

    timer = threading.Timer(JOIN_TIME, auto_start)
    timer.daemon = True
    timer.start()
    table["join_timer"] = timer

def cb_poker(call):
    uid  = call.from_user.id
    data = call.data
    cid  = call.message.chat.id
    p    = db.get_player(uid)

    if not p:
        _bot.answer_callback_query(call.id, "Register first! /start"); return

    # ── Join ──────────────────────────────────────────────────────────
    if data.startswith("poker_join_"):
        table = active_tables.get(cid)
        if not table or table["phase"] != "joining":
            _bot.answer_callback_query(call.id, "Table not open!"); return
        if any(pl["uid"] == uid for pl in table["players"]):
            _bot.answer_callback_query(call.id, "Already at the table!"); return
        if len(table["players"]) >= MAX_PLAYERS:
            _bot.answer_callback_query(call.id, "Table is full!"); return

        min_bet = table["min_bet"]
        buy_in  = min(p["chips"], min_bet * 20)
        if buy_in < min_bet * 2:
            _bot.answer_callback_query(call.id,
                f"Need at least {fmt(min_bet*2)} chips!", show_alert=True); return

        db.update_chips(uid, -buy_in)
        table["players"].append({"uid": uid, "name": call.from_user.first_name,
                                  "chips": buy_in, "hole": [], "bet": 0,
                                  "folded": False, "allin": False})
        _bot.answer_callback_query(call.id, f"Joined! Buy-in: {fmt(buy_in)} chips")

        # Update join message
        plist = "\n".join(f"{i+1}. *{pl['name']}* — {fmt(pl['chips'])} chips"
                          for i, pl in enumerate(table["players"]))
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("🃏 Join Table", callback_data=f"poker_join_{table['host_id']}_{min_bet}"),
            types.InlineKeyboardButton("▶️ Start Game", callback_data=f"poker_start_{table['host_id']}"),
        )
        try:
            _bot.edit_message_text(
                f"♠️ *Poker Table — Texas Hold'em*\n\n"
                f"💰 Blind: *{fmt(min_bet)}* / *{fmt(min_bet*2)}*\n"
                f"👥 Players: *{len(table['players'])}/{MAX_PLAYERS}*\n"
                f"{plist}\n\n"
                f"⚠️ Hole cards sent via *DM*!\n"
                f"⏳ Joining...",
                cid, call.message.message_id,
                reply_markup=markup, parse_mode="Markdown")
        except: pass
        return

    # ── Start ─────────────────────────────────────────────────────────
    if data.startswith("poker_start_"):
        host_id = int(data.split("_")[-1])
        if uid != host_id:
            _bot.answer_callback_query(call.id, "Only the host can start!", show_alert=True); return
        table = active_tables.get(cid)
        if not table or table["phase"] != "joining":
            _bot.answer_callback_query(call.id, "Game already started!"); return
        if len(table["players"]) < MIN_PLAYERS:
            _bot.answer_callback_query(call.id, f"Need at least {MIN_PLAYERS} players!", show_alert=True); return
        if table.get("join_timer"):
            try: table["join_timer"].cancel()
            except: pass
        _bot.answer_callback_query(call.id, "Starting game!")
        start_game(cid)
        return

    # ── Game actions ──────────────────────────────────────────────────
    table = active_tables.get(cid)
    if not table or table["phase"] in ("joining","showdown"):
        _bot.answer_callback_query(call.id, "No active game!"); return

    ap = active_players(table)
    if not ap:
        _bot.answer_callback_query(call.id, "No active players!"); return

    actor = ap[table["acting"] % len(ap)]
    if uid != actor["uid"]:
        _bot.answer_callback_query(call.id, "It's not your turn!", show_alert=True); return

    plr     = get_player(table, uid)
    to_call = table["cur_bet"] - plr["bet"]

    if data.startswith("poker_fold_"):
        plr["folded"] = True
        table["acted"].add(uid)
        _bot.answer_callback_query(call.id, "Folded!")
        remaining = [p for p in table["players"] if not p.get("folded")]
        if len(remaining) == 1:
            _end_game(table, remaining); return

    elif data.startswith("poker_check_"):
        if to_call > 0:
            _bot.answer_callback_query(call.id, f"Must call {fmt(to_call)} first!", show_alert=True); return
        table["acted"].add(uid)
        _bot.answer_callback_query(call.id, "Checked!")

    elif data.startswith("poker_call_"):
        actual = min(to_call, plr["chips"])
        plr["chips"] -= actual
        plr["bet"]   += actual
        table["pot"] += actual
        if plr["chips"] == 0:
            plr["allin"] = True
        table["acted"].add(uid)
        _bot.answer_callback_query(call.id, f"Called {fmt(actual)}!")

    elif data.startswith("poker_raise_"):
        if table["raises_left"] <= 0:
            _bot.answer_callback_query(call.id, "Max raises reached!", show_alert=True); return
        raise_amt = table["cur_bet"] + table["min_bet"]
        total_needed = raise_amt - plr["bet"]
        if plr["chips"] < total_needed:
            # All-in
            actual = plr["chips"]
            plr["chips"] = 0
            plr["bet"]  += actual
            table["pot"] += actual
            table["cur_bet"] = plr["bet"]
            plr["allin"] = True
        else:
            plr["chips"]    -= total_needed
            plr["bet"]      += total_needed
            table["pot"]    += total_needed
            table["cur_bet"] = plr["bet"]
        table["raises_left"] -= 1
        table["acted"] = {uid}  # Others need to act again
        _bot.answer_callback_query(call.id, f"Raised to {fmt(table['cur_bet'])}!")

    _advance(table)

# ── Register ──────────────────────────────────────────────────────────
def register_poker(bot_instance):
    global _bot
    _bot = bot_instance
    bot_instance.register_message_handler(cmd_poker, commands=["poker"])
    bot_instance.register_callback_query_handler(
        cb_poker, func=lambda c: c.data.startswith("poker_"))
    print("✅ Poker loaded")
