"""minigames.py — Word Scramble, Complete the Word, Emoji Guess, Trivia"""
import random, threading
import database as db

_bot = None
active_games = {}
streaks = {}

WORD_REWARD   = 500
EMOJI_REWARD  = 800
TRIVIA_REWARD = 600
STREAK_BONUS  = 200
WRONG_PENALTY = 100

WORDS = [
    ("CASINO",    "C_S_N_"),
    ("JACKPOT",   "J_CK_OT"),
    ("DIAMOND",   "D_AM_ND"),
    ("GAMBLE",    "G_MB_E"),
    ("FORTUNE",   "F_RT_NE"),
    ("ROULETTE",  "R_UL_TTE"),
    ("WINNER",    "W_NN_R"),
    ("TREASURE",  "TR_AS_RE"),
    ("BETTING",   "B_TT_NG"),
    ("TOKENS",    "T_K_NS"),
    ("SPINNER",   "SP_NN_R"),
    ("BALANCE",   "B_L_NCE"),
    ("VICTORY",   "V_CT_RY"),
    ("MYSTERY",   "M_ST_RY"),
    ("CRYSTAL",   "CR_ST_L"),
    ("KINGDOM",   "K_NGD_M"),
    ("PHANTOM",   "PH_NT_M"),
    ("DRAGON",    "DR_G_N"),
    ("MACHINE",   "M_CH_NE"),
    ("GALAXY",    "G_L_XY"),
]

SCRAMBLES = [
    ("CHIPS",  "PSHCI"),
    ("DEALER", "ELADER"),
    ("SLOTS",  "TOLSS"),
    ("POKER",  "ROPEK"),
    ("BLUFF",  "FLBUF"),
    ("LUCKY",  "YCLKU"),
    ("VAULT",  "LAVUT"),
    ("COINS",  "SONIC"),
    ("BONUS",  "SUBNO"),
    ("PRIZE",  "IPRZE"),
    ("MONEY",  "YENOM"),
    ("JOKER",  "EROKJ"),
    ("REBEL",  "LBERE"),
    ("TORCH",  "RHTCO"),
    ("SWIFT",  "TWIFS"),
    ("BRAVE",  "EVRAB"),
    ("CROWN",  "NROWC"),
    ("FEAST",  "TSAEF"),
    ("GLOOM",  "MOOGL"),
    ("SPARK",  "PARKS"),
]

EMOJI_CLUES = [
    (("🍎📱",    "APPLE IPHONE"),  ["apple iphone","iphone","apple phone"]),
    (("🌙🚀👨",  "MAN ON MOON"),   ["man on moon","astronaut on moon","moon man"]),
    (("🎰💰🎉",  "JACKPOT WIN"),   ["jackpot","jackpot win","win jackpot"]),
    (("🐉🔥",    "FIRE DRAGON"),   ["fire dragon","dragon fire","dragon"]),
    (("💣🔢",    "NUMBER BOMB"),   ["number bomb","bomb"]),
    (("🃏♠️♥️", "CARD GAME"),     ["card game","cards","poker"]),
    (("🏆🥇🎖️", "FIRST PLACE"),   ["first place","winner","gold medal","champion"]),
    (("🎣🐟💰",  "FISHING REWARD"),["fishing reward","fishing","fish reward"]),
    (("💍👫",    "MARRY PLAYER"),  ["marry","marriage","married","marry player"]),
    (("🌑👾⭐",  "VOID ANCIENT"),  ["void ancient","ancient","void"]),
    (("🏦💰📈",  "BANK INTEREST"), ["bank interest","interest","bank"]),
    (("🔫💸😈",  "ROB PLAYER"),    ["rob player","rob","robbery"]),
    (("⚔️🐺❤️", "BOSS FIGHT"),    ["boss fight","boss","fight boss"]),
    (("🎁🎊💝",  "MYSTERY BOX"),   ["mystery box","gift","surprise"]),
    (("🌾🚜💰",  "FARM REWARD"),   ["farm reward","farming","farm"]),
    (("⛏️💎🪨", "MINING GEMS"),   ["mining gems","mining","mine gems","gems"]),
    (("🎲🎲💥",  "DOUBLE DICE"),   ["double dice","dice","double"]),
    (("👑🃏♠️",  "BLACKJACK WIN"), ["blackjack win","blackjack","bj win"]),
    (("🕵️💰🤝", "BLACK MARKET"),  ["black market","market","deal"]),
    (("🚂💰🎰",  "JACKPOT TRAIN"), ["jackpot train","train","jackpot"]),
]

TRIVIA = [
    ("What is 7 x 8?",                        "56",          ["56"]),
    ("How many suits are in a deck of cards?", "4",           ["4","four"]),
    ("What color is a ruby?",                  "RED",         ["red"]),
    ("How many sides does a hexagon have?",    "6",           ["6","six"]),
    ("What is the capital of France?",         "PARIS",       ["paris"]),
    ("How many zeros in one million?",         "6",           ["6","six"]),
    ("What planet is closest to the sun?",     "MERCURY",     ["mercury"]),
    ("How many cards in a standard deck?",     "52",          ["52"]),
    ("What is 15% of 200?",                    "30",          ["30"]),
    ("How many hours in a day?",               "24",          ["24","twenty four"]),
    ("What is the square root of 144?",        "12",          ["12","twelve"]),
    ("How many players in a football team?",   "11",          ["11","eleven"]),
    ("What is 2 to the power of 10?",          "1024",        ["1024"]),
    ("How many continents are there?",         "7",           ["7","seven"]),
    ("What comes after a trillion?",           "QUADRILLION", ["quadrillion"]),
    ("How many months have 31 days?",          "7",           ["7","seven"]),
    ("What is 100 divided by 4?",              "25",          ["25","twenty five"]),
    ("How many bones in the human body?",      "206",         ["206"]),
    ("What is the chemical symbol for gold?",  "AU",          ["au","gold"]),
    ("How many seconds in an hour?",           "3600",        ["3600"]),
]

def fmt(n): return f"{n:,}"

def cancel_timer(chat_id):
    g = active_games.get(chat_id)
    if g and g.get("timer"):
        g["timer"].cancel()

def timeout_game(chat_id):
    game = active_games.pop(chat_id, None)
    if not game: return
    for uid in game.get("wrong", set()):
        streaks.pop(uid, None)
    _bot.send_message(chat_id,
        f"⏰ Time's up! Nobody got it.\n✅ Answer: *{game['answer']}*",
        parse_mode="Markdown")

def start_timer(chat_id, seconds=30):
    t = threading.Timer(seconds, timeout_game, args=[chat_id])
    t.start()
    return t

def _start_game(cid, game_dict, msg_text):
    cancel_timer(cid)
    game_dict["timer"] = start_timer(cid, 30)
    game_dict["wrong"] = set()
    active_games[cid]  = game_dict
    _bot.send_message(cid, msg_text, parse_mode="Markdown")

def _check_registered(message):
    p = db.get_player(message.from_user.id)
    if not p:
        _bot.reply_to(message, "❗ Send /start to register first!")
        return False
    return True

def _check_no_active(message):
    if message.chat.id in active_games:
        _bot.reply_to(message, "⚠️ A game is already running! Answer it first.")
        return False
    return True

def cmd_wordgame(message):
    cid = message.chat.id
    if not _check_registered(message) or not _check_no_active(message): return
    word, hint = random.choice(WORDS)
    _start_game(cid,
        {"type": "word", "answer": word, "reward": WORD_REWARD},
        f"🔤 *Complete the Word!*\n\n`{hint}`\n\n"
        f"💰 Reward: *{fmt(WORD_REWARD)} chips*  |  ❌ Wrong: -*{WRONG_PENALTY} chips*\n"
        f"⏳ 30 seconds!")

def cmd_scramble(message):
    cid = message.chat.id
    if not _check_registered(message) or not _check_no_active(message): return
    word, scrambled = random.choice(SCRAMBLES)
    _start_game(cid,
        {"type": "scramble", "answer": word, "reward": WORD_REWARD},
        f"🔀 *Word Scramble!*\n\nUnscramble: `{scrambled}`\n\n"
        f"💰 Reward: *{fmt(WORD_REWARD)} chips*  |  ❌ Wrong: -*{WRONG_PENALTY} chips*\n"
        f"⏳ 30 seconds!")

def cmd_emojiguess(message):
    cid = message.chat.id
    if not _check_registered(message) or not _check_no_active(message): return
    (emojis, display), accepted = random.choice(EMOJI_CLUES)
    _start_game(cid,
        {"type": "emoji", "answer": display, "accepted": accepted, "reward": EMOJI_REWARD},
        f"🖼️ *What does this mean?*\n\n{emojis}\n\n"
        f"💰 Reward: *{fmt(EMOJI_REWARD)} chips*  |  ❌ Wrong: -*{WRONG_PENALTY} chips*\n"
        f"⏳ 30 seconds!")

def cmd_trivia(message):
    cid = message.chat.id
    if not _check_registered(message) or not _check_no_active(message): return
    question, display, accepted = random.choice(TRIVIA)
    _start_game(cid,
        {"type": "trivia", "answer": display, "accepted": accepted, "reward": TRIVIA_REWARD},
        f"❓ *Trivia Time!*\n\n{question}\n\n"
        f"💰 Reward: *{fmt(TRIVIA_REWARD)} chips*  |  ❌ Wrong: -*{WRONG_PENALTY} chips*\n"
        f"⏳ 30 seconds!")

def handle_answer(message):
    cid  = message.chat.id
    uid  = message.from_user.id
    name = message.from_user.first_name or "Player"
    game = active_games.get(cid)
    if not game: return

    wrong_set = game.setdefault("wrong_count", {})
    if wrong_set.get(uid, 0) >= 3:
        return

    guess   = message.text.strip().upper()
    correct = False

    if game["type"] in ("word", "scramble"):
        correct = guess == game["answer"]
    else:
        correct = guess.lower() in game["accepted"]

    if correct:
        cancel_timer(cid)
        active_games.pop(cid, None)

        streaks[uid] = streaks.get(uid, 0) + 1
        streak = streaks[uid]
        bonus  = STREAK_BONUS * (streak - 1) if streak > 1 else 0
        total  = game["reward"] + bonus

        db.update_chips(uid, total)
        db.add_xp(uid, 20)
        db.execute("UPDATE players SET minigame_wins=COALESCE(minigame_wins,0)+1 WHERE user_id=?", (uid,))
        if game["type"] == "trivia":
            db.execute("UPDATE players SET trivia_wins=COALESCE(trivia_wins,0)+1 WHERE user_id=?", (uid,))
        import gems as gems_mod
        gems_mod.check_achievements(uid, cid)

        streak_msg = f"\n🔥 *Streak x{streak}!* +{fmt(bonus)} bonus" if streak > 1 else ""
        _bot.send_message(cid,
            f"✅ *{name}* got it!\n"
            f"Answer: *{game['answer']}*\n"
            f"💰 +{fmt(total)} chips{streak_msg}\n"
            f"⭐ +20 XP", parse_mode="Markdown")

    else:
        wrong_set[uid] = wrong_set.get(uid, 0) + 1
        game["wrong"].add(uid)
        streaks.pop(uid, None)

        p = db.get_player(uid)
        if p and p["chips"] >= WRONG_PENALTY:   # FIXED: was p["balance"]
            db.update_chips(uid, -WRONG_PENALTY) # FIXED: was update_balance
            _bot.reply_to(message,
                f"❌ Wrong! -*{WRONG_PENALTY} chips*\n"
                f"Tries left: {3 - wrong_set[uid]}")
        else:
            _bot.reply_to(message,
                f"❌ Wrong! (Not enough chips to penalize)\n"
                f"Tries left: {3 - wrong_set[uid]}")

def register_minigames(bot_instance):
    global _bot
    _bot = bot_instance
    bot_instance.register_message_handler(cmd_wordgame,   commands=["wordgame"])
    bot_instance.register_message_handler(cmd_scramble,   commands=["scramble"])
    bot_instance.register_message_handler(cmd_emojiguess, commands=["emojiguess"])
    bot_instance.register_message_handler(cmd_trivia,     commands=["trivia"])
    bot_instance.register_message_handler(handle_answer,
        func=lambda m: m.chat.type in ("group", "supergroup")
                    and m.chat.id in active_games
                    and m.text
                    and not m.text.startswith("/"))
