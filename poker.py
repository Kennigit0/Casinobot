"""poker.py — Texas Hold'em Poker (v2 - all bugs fixed)"""
import random, threading
from itertools import combinations
from telebot import types
import database as db

_bot = None
active_tables = {}

SUITS  = ["♠️","♥️","♦️","♣️"]
RANKS  = ["2","3","4","5","6","7","8","9","10","J","Q","K","A"]
RANK_V = {r: i for i, r in enumerate(RANKS, 2)}

JOIN_TIME   = 60
ACTION_TIME = 60
MIN_PLAYERS = 2
MAX_PLAYERS = 6

def fmt(n): return f"{n:,}"

# ── Deck ──────────────────────────────────────────────────────────────
def make_deck():
    deck = [(r,s) for s in SUITS for r in RANKS]
    random.shuffle(deck)
    return deck

def card_str(c): return f"{c[0]}{c[1]}"
def hand_str(cards): return " ".join(card_str(c) for c in cards)

# ── Hand evaluator ────────────────────────────────────────────────────
def hand_rank(cards):
    return max(_score_hand(h) for h in combinations(cards, 5))

def _score_hand(five):
    vals  = sorted([RANK_V[c[0]] for c in five], reverse=True)
    suits = [c[1] for c in five]
    flush = len(set(suits)) == 1
    uniq  = sorted(set(vals), reverse=True)
    cnts  = sorted([vals.count(v) for v in uniq], reverse=True)
    st    = False
    if len(uniq) == 5:
        if vals[0]-vals[4] == 4: st = True
        if uniq == [14,5,4,3,2]: st = True; vals = [5,4,3,2,1]
    if st and flush: return (8, vals)
    if cnts[0]==4:              return (7, vals)
    if cnts[:2]==[3,2]:         return (6, vals)
    if flush:                   return (5, vals)
    if st:                      return (4, vals)
    if cnts[0]==3:              return (3, vals)
    if cnts[:2]==[2,2]:         return (2, vals)
    if cnts[0]==2:              return (1, vals)
    return (0, vals)

HAND_NAMES = {8:"Straight Flush",7:"Four of a Kind",6:"Full House",
              5:"Flush",4:"Straight",3:"Three of a Kind",2:"Two Pair",
              1:"One Pair",0:"High Card"}

# ── Table helpers ─────────────────────────────────────────────────────
def new_table(chat_id, host_id, min_bet):
    return {"chat_id":chat_id,"host_id":host_id,"min_bet":min_bet,
            "phase":"joining","players":[],"deck":[],"community":[],
            "pot":0,"cur_bet":0,"current_uid":None,"raises_left":3,
            "acted":set(),"msg_id":None,"timer":None}

def get_pl(table, uid):
    return next((p for p in table["players"] if p["uid"]==uid), None)

def can_act(table):
    """Players who can still make betting decisions"""
    return [p for p in table["players"]
            if not p.get("folded") and not p.get("allin")]

def non_folded(table):
    return [p for p in table["players"] if not p.get("folded")]

def all_bets_equal(table):
    nf = non_folded(table)
    if not nf: return True
    cb = table["cur_bet"]
    return all(p["bet"]==cb or p.get("allin") for p in nf)

def all_have_acted(table):
    ca = can_act(table)
    return all(p["uid"] in table["acted"] for p in ca)

def next_actor(table):
    """Find next player UID who needs to act. Returns None if round over."""
    ca = can_act(table)
    if not ca: return None
    uids = [p["uid"] for p in ca]
    cur  = table["current_uid"]
    if cur in uids:
        start = (uids.index(cur)+1) % len(uids)
    else:
        start = 0
    for i in range(len(uids)):
        uid = uids[(start+i) % len(uids)]
        if uid not in table["acted"]:
            return uid
    return None  # all acted

# ── Board render ──────────────────────────────────────────────────────
def render_board(table):
    phase = table["phase"]
    com   = hand_str(table["community"]) if table["community"] else "_none yet_"
    label = {"preflop":"Pre-Flop","flop":"Flop","turn":"Turn",
             "river":"River","showdown":"Showdown"}.get(phase, phase.title())
    lines = [f"♠️ *Texas Hold'em — {label}*\n",
             f"🃏 Community: {com}",
             f"💰 Pot: *{fmt(table['pot'])}* | Bet: *{fmt(table['cur_bet'])}*\n"]
    for p in table["players"]:
        icon = "💀" if p.get("folded") else ("🔒" if p.get("allin") else "🟢")
        bs   = f" (bet:{fmt(p['bet'])})" if p["bet"] else ""
        lines.append(f"{icon} *{p['name']}*{bs} — 💰{fmt(p['chips'])}")
    cur = table.get("current_uid")
    if cur and phase not in ("joining","showdown"):
        p2 = get_pl(table, cur)
        if p2 and not p2.get("folded"):
            lines.append(f"\n⏳ *{p2['name']}'s turn* — {ACTION_TIME}s")
    return "\n".join(lines)

def action_markup(table):
    uid = table.get("current_uid")
    if not uid: return None
    p = get_pl(table, uid)
    if not p or p.get("folded") or p.get("allin"): return None
    to_call = table["cur_bet"] - p["bet"]
    markup  = types.InlineKeyboardMarkup()
    fold_b  = types.InlineKeyboardButton("❌ Fold",  callback_data=f"poker_fold_{uid}")
    if to_call <= 0:
        chk_b = types.InlineKeyboardButton("✅ Check",  callback_data=f"poker_check_{uid}")
        rai_b = types.InlineKeyboardButton(f"⬆️ Raise +{fmt(table['min_bet'])}", callback_data=f"poker_raise_{uid}")
        markup.row(fold_b, chk_b, rai_b)
    else:
        call_amt = min(to_call, p["chips"])
        lbl = "All-In" if call_amt == p["chips"] else f"Call {fmt(call_amt)}"
        cal_b = types.InlineKeyboardButton(f"📞 {lbl}", callback_data=f"poker_call_{uid}")
        rai_b = types.InlineKeyboardButton(f"⬆️ Raise +{fmt(table['min_bet'])}", callback_data=f"poker_raise_{uid}")
        markup.row(fold_b, cal_b, rai_b)
    return markup

# ── Game flow ─────────────────────────────────────────────────────────
def start_game(chat_id):
    table = active_tables.get(chat_id)
    if not table or len(table["players"]) < MIN_PLAYERS: return
    table["deck"] = make_deck()
    for p in table["players"]:
        p["hole"]=[table["deck"].pop(),table["deck"].pop()]
        p["bet"]=0; p["folded"]=False; p["allin"]=False
    players = table["players"]
    sb_idx  = 0
    bb_idx  = 1 % len(players)
    for idx, amt in [(sb_idx, table["min_bet"]), (bb_idx, table["min_bet"]*2)]:
        p = players[idx]
        actual = min(amt, p["chips"])
        p["chips"] -= actual; p["bet"] += actual; table["pot"] += actual
    table["cur_bet"]     = table["min_bet"] * 2
    table["phase"]       = "preflop"
    table["acted"]       = set()
    table["raises_left"] = 3
    # First to act: player after BB (index 2, or wrap)
    ca = can_act(table)
    if ca:
        # Start with player after BB if possible
        after_bb = players[(bb_idx+1) % len(players)]
        table["current_uid"] = after_bb["uid"] if not after_bb.get("folded") else ca[0]["uid"]
    for p in players:
        try: _bot.send_message(p["uid"],
            f"🃏 *Your hole cards:*\n\n*{hand_str(p['hole'])}*\n\nGood luck! 🍀")
        except: pass
    _update_board(table)
    _start_timer(table)

def _update_board(table):
    chat_id = table["chat_id"]
    text    = render_board(table)
    markup  = action_markup(table) if table["phase"] not in ("joining","showdown") else None
    try:
        if table["msg_id"]:
            _bot.edit_message_text(text, chat_id, table["msg_id"],
                reply_markup=markup, parse_mode="Markdown")
        else:
            msg = _bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
            table["msg_id"] = msg.message_id
    except: pass

def _start_timer(table):
    if table.get("timer"):
        try: table["timer"].cancel()
        except: pass
    actor_uid = table.get("current_uid")
    if not actor_uid: return
    def timeout():
        t = active_tables.get(table["chat_id"])
        if not t or t.get("current_uid") != actor_uid: return
        p = get_pl(t, actor_uid)
        if p and not p.get("folded") and not p.get("allin"):
            p["folded"] = True
            t["acted"].add(actor_uid)
            try: _bot.send_message(t["chat_id"], f"⏰ *{p['name']}* timed out — auto-folded!")
            except: pass
            _advance(t)
    tmr = threading.Timer(ACTION_TIME, timeout)
    tmr.daemon = True; tmr.start()
    table["timer"] = tmr

def _advance(table):
    if table.get("timer"):
        try: table["timer"].cancel()
        except: pass
    nf = non_folded(table)
    # Only one not-folded → they win
    if len(nf) == 1:
        _end_game(table, nf); return
    # If no one can act (all allin) → go to showdown directly
    ca = can_act(table)
    if not ca:
        _run_remaining_community(table); return
    # Check if round is over
    if all_have_acted(table) and all_bets_equal(table):
        _next_phase(table); return
    # Find next actor
    nxt = next_actor(table)
    if nxt is None:
        _next_phase(table); return
    table["current_uid"] = nxt
    _update_board(table)
    _start_timer(table)

def _run_remaining_community(table):
    """All players all-in — deal remaining community cards and showdown"""
    while len(table["community"]) < 5:
        table["deck"].pop()  # burn
        table["community"].append(table["deck"].pop())
    try: _bot.send_message(table["chat_id"],
        f"🔒 All players all-in! Community: {hand_str(table['community'])}")
    except: pass
    _showdown(table)

def _next_phase(table):
    order = ["preflop","flop","turn","river","showdown"]
    cur   = order.index(table["phase"])
    if cur >= len(order)-2:
        _showdown(table); return
    nxt = order[cur+1]
    table["phase"]=nxt; table["acted"]=set(); table["cur_bet"]=0; table["raises_left"]=3
    for p in table["players"]: p["bet"]=0
    if nxt == "flop":
        table["deck"].pop()
        table["community"] = [table["deck"].pop() for _ in range(3)]
    elif nxt in ("turn","river"):
        table["deck"].pop()
        table["community"].append(table["deck"].pop())
    try: _bot.send_message(table["chat_id"],
        f"📋 *{nxt.title()}!* — {hand_str(table['community'])}")
    except: pass
    # First to act: first non-folded non-allin player
    ca = can_act(table)
    table["current_uid"] = ca[0]["uid"] if ca else None
    _update_board(table)
    _start_timer(table)

def _showdown(table):
    table["phase"] = "showdown"
    if table.get("timer"):
        try: table["timer"].cancel()
        except: pass
    _end_game(table, non_folded(table))

def _end_game(table, pool):
    if table.get("timer"):
        try: table["timer"].cancel()
        except: pass
    chat_id = table["chat_id"]
    # Return remaining chips to ALL players
    for p in table["players"]:
        if p["chips"] > 0:
            db.update_chips(p["uid"], p["chips"])
    if len(pool) == 1:
        w = pool[0]
        db.update_chips(w["uid"], table["pot"])
        try: _bot.send_message(chat_id,
            f"🏆 *{w['name']}* wins *{fmt(table['pot'])}* chips!\n_(Everyone else folded)_")
        except: pass
    else:
        all_c  = {p["uid"]: p["hole"]+table["community"] for p in pool}
        scores = {p["uid"]: hand_rank(all_c[p["uid"]]) for p in pool}
        best   = max(scores.values())
        winners= [p for p in pool if scores[p["uid"]]==best]
        share  = table["pot"] // len(winners)
        lines  = ["🃏 *Showdown!*\n"]
        for p in pool:
            lines.append(f"• *{p['name']}*: {hand_str(p['hole'])} — _{HAND_NAMES[scores[p['uid']][0]]}_")
        lines.append("")
        if len(winners)==1:
            db.update_chips(winners[0]["uid"], table["pot"])
            lines.append(f"🏆 *{winners[0]['name']}* wins *{fmt(table['pot'])}* chips!")
        else:
            for w in winners: db.update_chips(w["uid"], share)
            lines.append(f"🤝 Split! {', '.join(w['name'] for w in winners)} each get *{fmt(share)}* chips!")
        try: _bot.send_message(chat_id, "\n".join(lines))
        except: pass
    active_tables.pop(chat_id, None)

# ── Commands ──────────────────────────────────────────────────────────
def cmd_poker(message):
    p = db.get_player(message.from_user.id)
    if not p: _bot.reply_to(message, "❗ Register first with /start"); return
    if message.chat.type == "private":
        _bot.reply_to(message, "❌ Poker is a group game!"); return
    chat_id = message.chat.id
    if chat_id in active_tables:
        _bot.reply_to(message, "⚠️ A table is already active! Join it or wait."); return
    args = message.text.split()
    try: min_bet = int(args[1].replace(",","")) if len(args)>1 else 1000
    except: min_bet = 1000
    if min_bet < 100: _bot.reply_to(message, "❌ Minimum blind is 100 chips."); return
    uid = message.from_user.id
    p2  = db.get_player(uid)
    if p2["chips"] < min_bet*2:
        _bot.reply_to(message, f"❌ Need at least *{fmt(min_bet*2)}* chips."); return
    table  = new_table(chat_id, uid, min_bet)
    buy_in = min(p2["chips"], min_bet*20)
    db.update_chips(uid, -buy_in)
    table["players"].append({"uid":uid,"name":message.from_user.first_name,
                              "chips":buy_in,"hole":[],"bet":0,"folded":False,"allin":False})
    active_tables[chat_id] = table
    markup = types.InlineKeyboardMarkup()
    markup.row(types.InlineKeyboardButton("🃏 Join Table", callback_data=f"poker_join_{uid}_{min_bet}"),
               types.InlineKeyboardButton("▶️ Start Now",  callback_data=f"poker_start_{uid}"))
    msg = _bot.reply_to(message,
        f"♠️ *Texas Hold'em Poker*\n\n"
        f"💰 Blinds: *{fmt(min_bet)}* / *{fmt(min_bet*2)}*\n"
        f"👥 Players: *1/{MAX_PLAYERS}*\n"
        f"1. *{message.from_user.first_name}* — {fmt(buy_in)} chips\n\n"
        f"⚠️ *Hole cards sent via DM!* Start bot in DM first.\n"
        f"⏳ {JOIN_TIME}s to join...", reply_markup=markup)
    table["msg_id"] = msg.message_id
    def auto_start():
        t = active_tables.get(chat_id)
        if not t or t["phase"]!="joining": return
        if len(t["players"]) >= MIN_PLAYERS:
            start_game(chat_id)
        else:
            for pl in t["players"]: db.update_chips(pl["uid"], pl["chips"])
            active_tables.pop(chat_id, None)
            try: _bot.send_message(chat_id, "❌ Not enough players — chips refunded.")
            except: pass
    tmr = threading.Timer(JOIN_TIME, auto_start)
    tmr.daemon = True; tmr.start()
    table["join_timer"] = tmr

def cmd_pokercanel(message):
    uid = message.from_user.id
    # Check if host of any table
    for cid, table in list(active_tables.items()):
        if table["host_id"] == uid:
            for pl in table["players"]: db.update_chips(pl["uid"], pl["chips"])
            if table.get("timer"):
                try: table["timer"].cancel()
                except: pass
            active_tables.pop(cid, None)
            _bot.reply_to(message, "✅ Poker table cancelled — all chips refunded.")
            return
    _bot.reply_to(message, "❌ You don't have an active poker table.")

def cb_poker(call):
    uid  = call.from_user.id
    data = call.data
    cid  = call.message.chat.id
    p    = db.get_player(uid)
    if not p: _bot.answer_callback_query(call.id, "Register first!"); return

    if data.startswith("poker_join_"):
        table = active_tables.get(cid)
        if not table or table["phase"]!="joining":
            _bot.answer_callback_query(call.id, "Table not open!"); return
        if any(pl["uid"]==uid for pl in table["players"]):
            _bot.answer_callback_query(call.id, "Already at the table!"); return
        if len(table["players"]) >= MAX_PLAYERS:
            _bot.answer_callback_query(call.id, "Table full!"); return
        min_bet = table["min_bet"]
        buy_in  = min(p["chips"], min_bet*20)
        if buy_in < min_bet*2:
            _bot.answer_callback_query(call.id, f"Need {fmt(min_bet*2)} chips!", show_alert=True); return
        db.update_chips(uid, -buy_in)
        table["players"].append({"uid":uid,"name":call.from_user.first_name,
                                  "chips":buy_in,"hole":[],"bet":0,"folded":False,"allin":False})
        _bot.answer_callback_query(call.id, f"Joined! Buy-in: {fmt(buy_in)}")
        plist = "\n".join(f"{i+1}. *{pl['name']}* — {fmt(pl['chips'])} chips"
                          for i,pl in enumerate(table["players"]))
        markup = types.InlineKeyboardMarkup()
        markup.row(types.InlineKeyboardButton("🃏 Join Table", callback_data=f"poker_join_{table['host_id']}_{min_bet}"),
                   types.InlineKeyboardButton("▶️ Start Now",  callback_data=f"poker_start_{table['host_id']}"))
        try:
            _bot.edit_message_text(
                f"♠️ *Texas Hold'em Poker*\n\n"
                f"💰 Blinds: *{fmt(min_bet)}* / *{fmt(min_bet*2)}*\n"
                f"👥 Players: *{len(table['players'])}/{MAX_PLAYERS}*\n"
                f"{plist}\n\n⏳ Joining...",
                cid, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
        except: pass
        return

    if data.startswith("poker_start_"):
        host_id = int(data.split("_")[-1])
        if uid != host_id:
            _bot.answer_callback_query(call.id, "Only the host can start!", show_alert=True); return
        table = active_tables.get(cid)
        if not table or table["phase"]!="joining":
            _bot.answer_callback_query(call.id, "Game already started!"); return
        if len(table["players"]) < MIN_PLAYERS:
            _bot.answer_callback_query(call.id, f"Need {MIN_PLAYERS}+ players!", show_alert=True); return
        if table.get("join_timer"):
            try: table["join_timer"].cancel()
            except: pass
        _bot.answer_callback_query(call.id, "Starting!")
        start_game(cid); return

    # Game actions
    table = active_tables.get(cid)
    if not table or table["phase"] in ("joining","showdown"):
        _bot.answer_callback_query(call.id, "No active game!"); return
    if table.get("current_uid") != uid:
        _bot.answer_callback_query(call.id, "It's not your turn!", show_alert=True); return
    plr     = get_pl(table, uid)
    if not plr:
        _bot.answer_callback_query(call.id, "You're not in this game!"); return
    to_call = table["cur_bet"] - plr["bet"]

    if data.startswith("poker_fold_"):
        plr["folded"] = True; table["acted"].add(uid)
        _bot.answer_callback_query(call.id, "Folded!")

    elif data.startswith("poker_check_"):
        if to_call > 0:
            _bot.answer_callback_query(call.id, f"Must call {fmt(to_call)} first!", show_alert=True); return
        table["acted"].add(uid)
        _bot.answer_callback_query(call.id, "Checked!")

    elif data.startswith("poker_call_"):
        actual = min(to_call, plr["chips"])
        plr["chips"]-=actual; plr["bet"]+=actual; table["pot"]+=actual
        if plr["chips"]==0: plr["allin"]=True
        table["acted"].add(uid)
        _bot.answer_callback_query(call.id, f"Called {fmt(actual)}!")

    elif data.startswith("poker_raise_"):
        if table["raises_left"] <= 0:
            _bot.answer_callback_query(call.id, "Max raises reached!", show_alert=True); return
        new_bet      = table["cur_bet"] + table["min_bet"]
        total_needed = new_bet - plr["bet"]
        if total_needed <= 0: total_needed = table["min_bet"]
        actual = min(total_needed, plr["chips"])
        plr["chips"]-=actual; plr["bet"]+=actual; table["pot"]+=actual
        table["cur_bet"] = plr["bet"]
        if plr["chips"]==0: plr["allin"]=True
        table["raises_left"] -= 1
        table["acted"] = {uid}  # everyone else needs to act again
        _bot.answer_callback_query(call.id, f"Raised! New bet: {fmt(table['cur_bet'])}")

    _advance(table)

def register_poker(bot_instance):
    global _bot
    _bot = bot_instance
    bot_instance.register_message_handler(cmd_poker,       commands=["poker"])
    bot_instance.register_message_handler(cmd_pokercanel,  commands=["pokercanel","cancelpoker"])
    bot_instance.register_callback_query_handler(
        cb_poker, func=lambda c: c.data.startswith("poker_"))
    print("✅ Poker loaded")
