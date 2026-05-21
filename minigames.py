"""minigames.py — Word Scramble, Complete the Word, Emoji Guess"""
import random, threading
from datetime import datetime, timedelta
import database as db

_bot = None

# Active game per chat: { chat_id: { type, answer, reward, started_at, timer } }
active_games = {}

WORD_REWARD   = 500
EMOJI_REWARD  = 800
STREAK_BONUS  = 200   # bonus per streak win
streaks = {}          # { user_id: count }

# ── Word lists ─────────────────────────────────────────────────────────
WORDS = [
    ("CASINO",   "C_S_N_"),
    ("JACKPOT",  "J_CK_OT"),
    ("DIAMOND",  "D_AM_ND"),
    ("GAMBLE",   "G_MB_E"),
    ("FORTUNE",  "F_RT_NE"),
    ("ROULETTE", "R_UL_TTE"),
    ("WINNER",   "W_NN_R"),
    ("TREASURE", "TR_AS_RE"),
    ("BETTING",  "B_TT_NG"),
    ("TOKENS",   "T_K_NS"),
]

SCRAMBLES = [
    ("CHIPS",   "PSHCI"),
    ("DEALER",  "ELADER"),
    ("SLOTS",   "TOLSS"),
    ("POKER",   "ROPEK"),
    ("BLUFF",   "FLBUF"),
    ("LUCKY",   "YCLKU"),
    ("VAULT",   "LAVUT"),
    ("COINS",   "SONIC"),
    ("BONUS",   "SUBNO"),
    ("PRIZE",   "IPRZE"),
]

EMOJI_CLUES = [
    (("🍎📱",       "APPLE IPHONE"),  ["apple iphone","iphone","apple phone"]),
    (("🌙🚀👨",     "MAN ON MOON"),   ["man on moon","astronaut on moon"]),
    (("🎰💰🎉",     "JACKPOT WIN"),   ["jackpot","jackpot win","win jackpot"]),
    (("🐉🔥",       "FIRE DRAGON"),   ["fire dragon","dragon fire","dragon"]),
    (("💣🔢",       "NUMBER BOMB"),   ["number bomb","bomb"]),
    (("🃏♠️♥️",     "CARD GAME"),     ["card game","cards","poker"]),
    (("🏆🥇🎖️",    "FIRST PLACE"),   ["first place","winner","gold medal"]),
    (("🎣🐟💰",     "FISHING REWARD"),["fishing reward","fishing","fish reward"]),
    (("💍👫",       "MARRY PLAYER"),  ["marry","marriage","married","marry player"]),
    (("🌑👾⭐",     "VOID ANCIENT"),  ["void ancient","ancient","void"]),
]

# ── Helpers ────────────────────────────────────────────────────────────
def fmt(n): return f"{n:,}"

def cancel_timer(chat_id):
    game = active_games.get(chat_id)
    if game and game.get("timer"):
        game["timer"].cancel()

def timeout_game(chat_id):
    game = active_games.pop(chat_id, None)
    if not game: return
    _bot.send_message(chat_id,
        f"⏰ Time's up! Nobody got it.\n✅ Answer: *{game['answer']}*", parse_mode="Markdown")

def start_timer(chat_id, seconds=30):
    t = threading.Timer(seconds, timeout_game, args=[chat_id])
    t.start()
    return t

# ── Commands ───────────────────────────────────────────────────────────
def cmd_wordgame(message):
    cid = message.chat.id
    p   = db.get_player(message.from_user.id)
    if not p:
        _bot.reply_to(message, "❗ Send /start to register first!"); return
    if cid in active_games:
        _bot.reply_to(message, "⚠️ A game is already running! Answer it first."); return

    word, hint = random.choice(WORDS)
    cancel_timer(cid)
    timer = start_timer(cid, 30)
    active_games[cid] = {"type": "word", "answer": word, "reward": WORD_REWARD, "timer": timer}

    _bot.send_message(cid,
        f"🔤 *Complete the Word!*\n\n"
        f"`{hint}`\n\n"
        f"💰 Reward: *{fmt(WORD_REWARD)} chips*\n"
        f"⏳ 30 seconds — type your answer!", parse_mode="Markdown")


def cmd_scramble(message):
    cid = message.chat.id
    p   = db.get_player(message.from_user.id)
    if not p:
        _bot.reply_to(message, "❗ Send /start to register first!"); return
    if cid in active_games:
        _bot.reply_to(message, "⚠️ A game is already running! Answer it first."); return

    word, scrambled = random.choice(SCRAMBLES)
    cancel_timer(cid)
    timer = start_timer(cid, 30)
    active_games[cid] = {"type": "scramble", "answer": word, "reward": WORD_REWARD, "timer": timer}

    _bot.send_message(cid,
        f"🔀 *Word Scramble!*\n\n"
        f"Unscramble this: `{scrambled}`\n\n"
        f"💰 Reward: *{fmt(WORD_REWARD)} chips*\n"
        f"⏳ 30 seconds — type your answer!", parse_mode="Markdown")


def cmd_emojiguess(message):
    cid = message.chat.id
    p   = db.get_player(message.from_user.id)
    if not p:
        _bot.reply_to(message, "❗ Send /start to register first!"); return
    if cid in active_games:
        _bot.reply_to(message, "⚠️ A game is already running! Answer it first."); return

    (emojis, display), accepted = random.choice(EMOJI_CLUES)
    cancel_timer(cid)
    timer = start_timer(cid, 30)
    active_games[cid] = {"type": "emoji", "answer": display, "accepted": accepted, "reward": EMOJI_REWARD, "timer": timer}

    _bot.send_message(cid,
        f"🖼️ *What does this mean?*\n\n"
        f"{emojis}\n\n"
        f"💰 Reward: *{fmt(EMOJI_REWARD)} chips*\n"
        f"⏳ 30 seconds — type your answer!", parse_mode="Markdown")


# ── Answer listener ────────────────────────────────────────────────────
def handle_answer(message):
    cid  = message.chat.id
    uid  = message.from_user.id
    name = message.from_user.first_name or "Player"
    game = active_games.get(cid)
    if not game: return

    guess = message.text.strip().upper()
    correct = False

    if game["type"] in ("word", "scramble"):
        correct = guess == game["answer"]
    elif game["type"] == "emoji":
        correct = guess.lower() in game["accepted"]

    if not correct: return

    cancel_timer(cid)
    active_games.pop(cid, None)

    # Streak tracking
    streaks[uid] = streaks.get(uid, 0) + 1
    streak = streaks[uid]
    bonus  = STREAK_BONUS * (streak - 1) if streak > 1 else 0
    total  = game["reward"] + bonus

    db.update_chips(uid, total)
    db.add_xp(uid, 20)

    streak_msg = f"\n🔥 *Streak x{streak}!* +{fmt(bonus)} bonus chips" if streak > 1 else ""
    _bot.send_message(cid,
        f"✅ *{name}* got it!\n"
        f"Answer: *{game['answer']}*\n"
        f"💰 +{fmt(game['reward'])} chips{streak_msg}\n"
        f"⭐ +20 XP", parse_mode="Markdown")


# ── Register ───────────────────────────────────────────────────────────
def register_minigames(bot_instance):
    global _bot
    _bot = bot_instance
    bot_instance.register_message_handler(cmd_wordgame,   commands=["wordgame"])
    bot_instance.register_message_handler(cmd_scramble,   commands=["scramble"])
    bot_instance.register_message_handler(cmd_emojiguess, commands=["emojiguess"])
    bot_instance.register_message_handler(handle_answer,
        func=lambda m: m.chat.type in ("group","supergroup") and m.chat.id in active_games and m.text and not m.text.startswith("/"))
