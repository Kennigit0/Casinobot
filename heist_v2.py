"""heist_v2.py — Complex Role-Based Heist System"""
import random, threading, time
import database as db
from telebot import types

_bot = None

# ── Active heists { chat_id: heist_state } ─────────────────────────────
active_heists = {}

# ── Roles ───────────────────────────────────────────────────────────────
ROLES = {
    "mastermind": {"name": "🧠 Mastermind",  "desc": "Plans the heist — solves math",         "bonus": 0.30},
    "hacker":     {"name": "💻 Hacker",       "desc": "Disables alarm — types code sequence",   "bonus": 0.25},
    "lockpick":   {"name": "🔓 Lockpick",     "desc": "Opens vault — unscrambles words",        "bonus": 0.20},
    "driver":     {"name": "🚗 Driver",        "desc": "Getaway car — reacts to signals",        "bonus": 0.15},
    "guard":      {"name": "🔫 Guard",         "desc": "Handles security — answers trivia",      "bonus": 0.10},
}

# ── Challenges ──────────────────────────────────────────────────────────
MATH_CHALLENGES = [
    ("47 x 3", "141"), ("15 x 12", "180"), ("234 + 567", "801"),
    ("1000 - 387", "613"), ("25 x 8", "200"), ("144 / 12", "12"),
    ("88 + 77", "165"), ("13 x 13", "169"), ("500 - 123", "377"),
    ("9 x 9 x 9", "729"),
]
WORD_CHALLENGES = [
    ("TEFAS", "SAFET", "FETAS", "safe"), ("TVAUL", "ALVUT", "LAVUT", "vault"),
    ("NAMEY", "YENOM", "MEONY", "money"), ("SACEH", "HACES", "EAHCS", "chase"),
    ("DIHER", "REHID", "HIRED", "heist"), ("KAPRES", "PARKS", "SPARKE", "spark"),
    ("REBBOR", "ROBBER", "BORBER", "robber"), ("CAEPSE", "ESCAPE", "PEACES", "escape"),
]
CODE_SEQUENCES = [
    "X7K2M", "B4N9R", "P3Q8T", "Z6W1Y", "H5J0L",
    "R2D4C", "T7M3K", "Q9B6N", "W1Z5P", "L8H2X",
]
TRIVIA_CHALLENGES = [
    ("Capital of Japan?", "tokyo"), ("How many sides in hexagon?", "6"),
    ("What is 15% of 200?", "30"), ("Planet closest to sun?", "mercury"),
    ("Chemical symbol for gold?", "au"), ("How many seconds in hour?", "3600"),
    ("Square root of 144?", "12"), ("How many continents?", "7"),
]
SPEED_SIGNALS = ["GOFAST", "DRIVE NOW", "MOVE OUT", "STEP ON IT", "PUNCH IT"]
DISABLE_CODES = ["DISABLE", "OVERRIDE", "BYPASS", "DEACTIVATE", "SHUTDOWN"]

def fmt(n): return f"{n:,}"

# ── Challenge generators ─────────────────────────────────────────────────
def get_math_challenge():
    q, a = random.choice(MATH_CHALLENGES)
    return {"type": "math", "question": f"🔢 *Math Challenge!*\n\nWhat is `{q}`?", "answer": a, "time": 20}

def get_word_challenge():
    opts = random.choice(WORD_CHALLENGES)
    scrambled = opts[random.randint(0, 2)]
    return {"type": "word", "question": f"🔤 *Word Challenge!*\n\nUnscramble: `{scrambled}`", "answer": opts[3], "time": 20}

def get_code_challenge():
    code = random.choice(CODE_SEQUENCES)
    return {"type": "code", "question": f"💻 *Hacker Challenge!*\n\nType this code exactly:\n`{code}`", "answer": code, "time": 15}

def get_trivia_challenge():
    q, a = random.choice(TRIVIA_CHALLENGES)
    return {"type": "trivia", "question": f"❓ *Trivia Challenge!*\n\n{q}", "answer": a, "time": 20}

def get_speed_challenge():
    signal = random.choice(SPEED_SIGNALS)
    return {"type": "speed", "question": f"⚡ *Speed Challenge!*\n\nFirst to type:\n`{signal}`", "answer": signal.lower(), "time": 10}

ROLE_CHALLENGES = {
    "mastermind": [get_math_challenge, get_math_challenge],
    "hacker":     [get_code_challenge, get_code_challenge],
    "lockpick":   [get_word_challenge, get_word_challenge, get_word_challenge],
    "driver":     [get_speed_challenge, get_speed_challenge, get_speed_challenge],
    "guard":      [get_trivia_challenge, get_trivia_challenge],
}

# ── Heist state helpers ──────────────────────────────────────────────────
def new_heist(host_id, host_name, bet, chat_id):
    return {
        "host_id":    host_id,
        "bet":        bet,
        "chat_id":    chat_id,
        "phase":      "joining",   # joining → phase1 → phase2 → phase3 → phase4 → done
        "players":    {host_id: {"name": host_name, "role": None, "score": 0, "challenges_done": 0}},
        "roles_taken": set(),
        "phase_results": [],       # list of (phase_name, success_bool)
        "current_challenge": None,
        "challenge_answered": set(),
        "message_id": None,
        "timer": None,
        "special_event_active": False,
        "crew_history": set([host_id]),
    }

def cancel_timer(chat_id):
    h = active_heists.get(chat_id)
    if h and h.get("timer"):
        h["timer"].cancel()

def start_timer(chat_id, seconds, fn):
    t = threading.Timer(seconds, fn, args=[chat_id])
    t.start()
    return t

# ── Phase execution ──────────────────────────────────────────────────────
PHASE_NAMES = ["infiltration", "vault", "escape", "final"]
PHASE_DISPLAY = {
    "infiltration": "🔓 Phase 1 — Infiltration",
    "vault":        "💰 Phase 2 — Vault Access",
    "escape":       "🚗 Phase 3 — Escape",
    "final":        "🎯 Phase 4 — Final Stand",
}
PHASE_ROLES = {
    "infiltration": ["hacker", "mastermind"],
    "vault":        ["lockpick", "mastermind"],
    "escape":       ["driver", "guard"],
    "final":        ["guard", "hacker"],
}

def start_joining_phase(chat_id, message_id):
    h = active_heists.get(chat_id)
    if not h: return
    h["message_id"] = message_id
    markup = _role_markup(chat_id)
    _bot.send_message(chat_id,
        f"🔫 *HEIST STARTING!*\n\n"
        f"💰 Bet: *{fmt(h['bet'])}* chips each\n\n"
        f"*Pick your role:*\n"
        f"🧠 Mastermind — Math puzzles (+30% bonus)\n"
        f"💻 Hacker — Code sequences (+25% bonus)\n"
        f"🔓 Lockpick — Word scrambles (+20% bonus)\n"
        f"🚗 Driver — Speed reactions (+15% bonus)\n"
        f"🔫 Guard — Trivia questions (+10% bonus)\n\n"
        f"⏳ *45 seconds to join and pick role!*",
        parse_mode="Markdown", reply_markup=markup)
    h["timer"] = start_timer(chat_id, 45, begin_heist)

def _role_markup(chat_id):
    h = active_heists.get(chat_id)
    markup = types.InlineKeyboardMarkup(row_width=2)
    for role_id, role in ROLES.items():
        taken = role_id in h["roles_taken"]
        label = f"{role['name']} {'✅' if not taken else '🚫'}"
        markup.add(types.InlineKeyboardButton(label, callback_data=f"hv2_role_{chat_id}_{role_id}"))
    markup.add(types.InlineKeyboardButton("🔫 Join Heist", callback_data=f"hv2_join_{chat_id}"))
    return markup

def begin_heist(chat_id):
    h = active_heists.get(chat_id)
    if not h: return
    players = h["players"]
    if len(players) < 2:
        _bot.send_message(chat_id, "❌ Not enough crew members! Heist cancelled.")
        # Refund
        for uid in players:
            db.update_chips(uid, h["bet"])
        active_heists.pop(chat_id, None)
        return
    # Assign random role to players without one
    available = [r for r in ROLES if r not in h["roles_taken"]]
    for uid, p in players.items():
        if not p["role"]:
            if available:
                role = available.pop(0)
            else:
                role = random.choice(list(ROLES.keys()))
            p["role"] = role
            h["roles_taken"].add(role)
    names = ", ".join(p["name"] for p in players.values())
    roles_txt = "\n".join(f"  {ROLES[p['role']]['name']} — *{p['name']}*" for p in players.values())
    _bot.send_message(chat_id,
        f"🔫 *HEIST BEGINS!*\n\n"
        f"👥 Crew: {names}\n\n"
        f"*Roles:*\n{roles_txt}\n\n"
        f"⚙️ Starting Phase 1...",
        parse_mode="Markdown")
    time.sleep(2)
    run_phase(chat_id, "infiltration")

def run_phase(chat_id, phase_name):
    h = active_heists.get(chat_id)
    if not h: return
    h["phase"] = phase_name
    h["challenge_answered"] = set()
    phase_roles = PHASE_ROLES[phase_name]
    # get players in this phase
    phase_players = {uid: p for uid, p in h["players"].items() if p["role"] in phase_roles}
    if not phase_players:
        # skip phase
        next_phase(chat_id, phase_name, True)
        return
    h["phase_players"] = phase_players
    h["phase_scores"] = {uid: 0 for uid in phase_players}
    # Generate challenges for each player
    challenges = {}
    for uid, p in phase_players.items():
        role = p["role"]
        fns = ROLE_CHALLENGES.get(role, [get_trivia_challenge])
        challenges[uid] = [fn() for fn in fns]
    h["phase_challenges"] = challenges
    h["phase_challenge_idx"] = {uid: 0 for uid in phase_players}
    display = PHASE_DISPLAY[phase_name]
    roles_in = " & ".join(ROLES[r]["name"] for r in phase_roles if r in [p["role"] for p in phase_players.values()])
    _bot.send_message(chat_id,
        f"━━━━━━━━━━━━━━━\n"
        f"{display}\n"
        f"━━━━━━━━━━━━━━━\n\n"
        f"*Active roles:* {roles_in}\n\n"
        f"Each player will receive their challenge now!",
        parse_mode="Markdown")
    time.sleep(1)
    # Send first challenge to each player
    for uid in phase_players:
        send_next_challenge(chat_id, uid)
    # Check for special event
    if random.random() < 0.3:
        threading.Timer(random.randint(5, 10), trigger_special_event, args=[chat_id]).start()
    # Phase timeout
    total_challenges = sum(len(v) for v in challenges.values())
    h["timer"] = start_timer(chat_id, total_challenges * 25, lambda cid: phase_timeout(cid, phase_name))

def send_next_challenge(chat_id, uid):
    h = active_heists.get(chat_id)
    if not h: return
    idx = h["phase_challenge_idx"].get(uid, 0)
    challenges = h["phase_challenges"].get(uid, [])
    if idx >= len(challenges):
        return
    ch = challenges[idx]
    p = h["players"][uid]
    _bot.send_message(chat_id,
        f"{ch['question']}\n\n"
        f"👤 *{p['name']}* — answer in *{ch['time']}s*!\n"
        f"Challenge {idx+1}/{len(challenges)}",
        parse_mode="Markdown")

def phase_timeout(chat_id, phase_name):
    h = active_heists.get(chat_id)
    if not h or h["phase"] != phase_name: return
    _bot.send_message(chat_id, f"⏰ Time's up for {PHASE_DISPLAY[phase_name]}!")
    evaluate_phase(chat_id, phase_name)

def evaluate_phase(chat_id, phase_name):
    h = active_heists.get(chat_id)
    if not h: return
    phase_players = h.get("phase_players", {})
    scores = h.get("phase_scores", {})
    total_challenges = sum(len(h["phase_challenges"].get(uid, [])) for uid in phase_players)
    total_done = sum(scores.values())
    success = total_done >= total_challenges * 0.5
    pct = int(total_done / total_challenges * 100) if total_challenges > 0 else 0
    h["phase_results"].append((phase_name, success, pct))
    emoji = "✅" if success else "❌"
    _bot.send_message(chat_id,
        f"{emoji} *{PHASE_DISPLAY[phase_name]}* — {pct}% complete\n"
        f"{'Phase cleared!' if success else 'Phase failed!'}",
        parse_mode="Markdown")
    time.sleep(2)
    next_phase(chat_id, phase_name, success)

def next_phase(chat_id, phase_name, success):
    phases = PHASE_NAMES
    idx = phases.index(phase_name)
    if idx + 1 < len(phases):
        run_phase(chat_id, phases[idx + 1])
    else:
        finish_heist(chat_id)

def trigger_special_event(chat_id):
    h = active_heists.get(chat_id)
    if not h or h["phase"] == "done": return
    events = [
        ("🚨 *ALARM TRIGGERED!* Someone must type `DISABLE` in 10 seconds!", "disable"),
        ("👮 *POLICE ENCOUNTER!* Bribe them — first to type `BRIBE` wins!", "bribe"),
        ("💣 *VAULT TRAP!* Type `DEFUSE` to save the heist!", "defuse"),
    ]
    event_txt, event_key = random.choice(events)
    h["special_event"] = event_key
    h["special_event_active"] = True
    h["special_event_done"] = False
    _bot.send_message(chat_id, event_txt, parse_mode="Markdown")
    def event_timeout():
        h2 = active_heists.get(chat_id)
        if h2 and h2.get("special_event_active") and not h2.get("special_event_done"):
            h2["special_event_active"] = False
            h2["phase_results"].append(("special", False, 0))
            _bot.send_message(chat_id, "💀 Nobody responded! -20% reward penalty added.")
    threading.Timer(10, event_timeout).start()

def finish_heist(chat_id):
    h = active_heists.pop(chat_id, None)
    if not h: return
    cancel_timer(chat_id)
    results  = h["phase_results"]
    players  = h["players"]
    bet      = h["bet"]
    # Calculate success rate
    phase_results = [(r[0], r[1], r[2]) for r in results if r[0] in PHASE_NAMES]
    special_fails = sum(1 for r in results if r[0] == "special" and not r[1])
    phases_passed = sum(1 for _, success, _ in phase_results if success)
    total_phases  = len(phase_results)
    avg_pct       = sum(r[2] for r in phase_results) / total_phases if total_phases else 0
    # Reward multiplier
    if phases_passed == total_phases:
        multiplier = 2.0
        result_txt = "🎉 *PERFECT HEIST!* Full reward!"
    elif phases_passed >= total_phases * 0.75:
        multiplier = 1.5
        result_txt = "✅ *HEIST SUCCESSFUL!* 75% reward."
    elif phases_passed >= total_phases * 0.5:
        multiplier = 1.0
        result_txt = "⚠️ *PARTIAL SUCCESS!* 50% reward."
    elif phases_passed >= 1:
        multiplier = 0.4
        result_txt = "😬 *BARELY ESCAPED!* 20% reward."
    else:
        multiplier = 0.0
        result_txt = "💀 *HEIST FAILED!* Caught by police!"
    # Special event penalty
    multiplier = max(0, multiplier - (special_fails * 0.2))
    lines = [f"🏁 *HEIST COMPLETE!*\n\n{result_txt}\n"]
    lines.append(f"📊 Phases: {phases_passed}/{total_phases} cleared")
    lines.append(f"💯 Avg completion: {avg_pct:.0f}%\n")
    for uid, p in players.items():
        role     = p["role"] or "guard"
        role_bonus = ROLES[role]["bonus"]
        if multiplier > 0:
            base    = bet * multiplier
            bonus   = base * role_bonus
            reward  = int(base + bonus)
            db.update_chips(uid, reward)
            db.add_win(uid)
            lines.append(f"✅ *{p['name']}* ({ROLES[role]['name']})\n   +{fmt(reward)} chips")
        else:
            db.add_loss(uid)
            lines.append(f"❌ *{p['name']}* — Lost {fmt(bet)} chips")
    _bot.send_message(chat_id, "\n".join(lines), parse_mode="Markdown")
    # Set cooldown for all players
    for uid in players:
        db.set_activity_time(uid, "last_heist")

# ── Answer handler ───────────────────────────────────────────────────────
def handle_heist_answer(message):
    chat_id = message.chat.id
    uid     = message.from_user.id
    h       = active_heists.get(chat_id)
    if not h or h["phase"] not in PHASE_NAMES: return
    text = message.text.strip()
    # Check special event
    if h.get("special_event_active") and not h.get("special_event_done"):
        if text.upper() == h.get("special_event", "").upper():
            h["special_event_done"] = True
            h["special_event_active"] = False
            _bot.reply_to(message, f"✅ *{message.from_user.first_name}* saved the heist! Event neutralized.", parse_mode="Markdown")
            return
    # Check phase challenge
    if uid not in h.get("phase_players", {}): return
    idx        = h["phase_challenge_idx"].get(uid, 0)
    challenges = h["phase_challenges"].get(uid, [])
    if idx >= len(challenges): return
    ch = challenges[idx]
    if text.lower() == ch["answer"].lower():
        h["phase_scores"][uid] = h["phase_scores"].get(uid, 0) + 1
        h["phase_challenge_idx"][uid] = idx + 1
        _bot.reply_to(message, f"✅ Correct!", parse_mode="Markdown")
        # Send next challenge or mark done
        if idx + 1 < len(challenges):
            send_next_challenge(chat_id, uid)
        else:
            _bot.send_message(chat_id, f"🎯 *{message.from_user.first_name}* completed all challenges!", parse_mode="Markdown")
            # Check if all players done
            all_done = all(
                h["phase_challenge_idx"].get(u, 0) >= len(h["phase_challenges"].get(u, []))
                for u in h["phase_players"]
            )
            if all_done:
                cancel_timer(chat_id)
                evaluate_phase(chat_id, h["phase"])

# ── Commands ─────────────────────────────────────────────────────────────
def cmd_heist2(message):
    chat_id = message.chat.id
    uid     = message.from_user.id
    if message.chat.type not in ("group", "supergroup"):
        _bot.reply_to(message, "❌ Heist only works in groups!"); return
    p = db.get_player(uid)
    if not p: _bot.reply_to(message, "❗ /start first"); return
    if chat_id in active_heists:
        _bot.reply_to(message, "⚠️ A heist is already in progress!"); return
    ok, msg = db.can_heist(uid)
    if not ok: _bot.reply_to(message, f"⏰ {msg}"); return
    args = message.text.split()
    if len(args) < 2:
        _bot.reply_to(message, "Usage: `/heist2 [bet]`", parse_mode="Markdown"); return
    try: bet = int(args[1].replace(",", ""))
    except: _bot.reply_to(message, "❌ Invalid bet."); return
    if p["chips"] < bet:
        _bot.reply_to(message, f"❌ Not enough chips! You have *{fmt(p['chips'])}*", parse_mode="Markdown"); return
    if bet < 100:
        _bot.reply_to(message, "❌ Minimum bet is 100 chips."); return
    db.update_chips(uid, -bet)
    h = new_heist(uid, message.from_user.first_name, bet, chat_id)
    active_heists[chat_id] = h
    sent = _bot.send_message(chat_id, "🔫 Setting up heist...", parse_mode="Markdown")
    start_joining_phase(chat_id, sent.message_id)

# ── Callbacks ─────────────────────────────────────────────────────────────
def cb_heist2(call):
    data    = call.data
    uid     = call.from_user.id
    name    = call.from_user.first_name
    if data.startswith("hv2_join_"):
        chat_id = int(data.split("_")[2])
        h = active_heists.get(chat_id)
        if not h: _bot.answer_callback_query(call.id, "Heist not found!"); return
        if uid in h["players"]: _bot.answer_callback_query(call.id, "Already in crew!"); return
        p = db.get_player(uid)
        if not p: _bot.answer_callback_query(call.id, "Register first! /start"); return
        if p["chips"] < h["bet"]: _bot.answer_callback_query(call.id, f"Need {fmt(h['bet'])} chips!"); return
        db.update_chips(uid, -h["bet"])
        h["players"][uid] = {"name": name, "role": None, "score": 0, "challenges_done": 0}
        _bot.answer_callback_query(call.id, "✅ Joined! Now pick your role.")
        _bot.send_message(chat_id, f"👤 *{name}* joined the crew!", parse_mode="Markdown")

    elif data.startswith("hv2_role_"):
        parts   = data.split("_")
        chat_id = int(parts[2])
        role_id = parts[3]
        h = active_heists.get(chat_id)
        if not h: _bot.answer_callback_query(call.id, "Heist not found!"); return
        if uid not in h["players"]: _bot.answer_callback_query(call.id, "Join the heist first!"); return
        if role_id in h["roles_taken"]: _bot.answer_callback_query(call.id, "Role already taken!"); return
        # Remove old role
        old_role = h["players"][uid].get("role")
        if old_role: h["roles_taken"].discard(old_role)
        h["players"][uid]["role"] = role_id
        h["roles_taken"].add(role_id)
        _bot.answer_callback_query(call.id, f"✅ You are now {ROLES[role_id]['name']}!")
        _bot.send_message(chat_id,
            f"*{name}* picked {ROLES[role_id]['name']}!", parse_mode="Markdown")

# ── Register ──────────────────────────────────────────────────────────────
def register_heist2(bot_instance):
    global _bot
    _bot = bot_instance
    bot_instance.register_message_handler(cmd_heist2, commands=["heist2"])
    bot_instance.register_callback_query_handler(
        cb_heist2,
        func=lambda c: c.data.startswith("hv2_")
    )
    bot_instance.register_message_handler(
        handle_heist_answer,
        func=lambda m: m.chat.type in ("group", "supergroup")
                    and m.chat.id in active_heists
                    and active_heists[m.chat.id]["phase"] in PHASE_NAMES
                    and m.text
                    and not m.text.startswith("/")
    )
    print("✅ Heist V2 loaded")
