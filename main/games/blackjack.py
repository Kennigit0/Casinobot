import random
import uuid

SUITS  = ["♠", "♥", "♦", "♣"]
VALUES = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]

def card_points(value):
    if value in ("J", "Q", "K"):
        return 10
    if value == "A":
        return 11
    return int(value)

def new_deck():
    deck = [{"v": v, "s": s} for s in SUITS for v in VALUES]
    random.shuffle(deck)
    return deck

def card_str(card):
    return f"{card['v']}{card['s']}"

def hand_str(hand):
    return " ".join(card_str(c) for c in hand)

def hand_score(hand):
    score = sum(card_points(c["v"]) for c in hand)
    aces  = sum(1 for c in hand if c["v"] == "A")
    while score > 21 and aces:
        score -= 10
        aces  -= 1
    return score

def is_bust(hand):
    return hand_score(hand) > 21

def is_blackjack(hand):
    return len(hand) == 2 and hand_score(hand) == 21

# ── Game state helpers ──────────────────────────────────────────────

def new_game(host_id, bet, chat_id):
    game_id = str(uuid.uuid4())[:8]
    deck    = new_deck()
    return {
        "game_id":       game_id,
        "chat_id":       chat_id,
        "state":         "waiting",   # waiting → playing → dealer → done
        "bet":           bet,
        "host_id":       host_id,
        "players":       [],          # list of {uid, name, hand, status}
        "dealer_hand":   [],
        "deck":          deck,
        "current_idx":   0,
    }

def add_player(game, uid, name):
    if any(p["uid"] == uid for p in game["players"]):
        return False
    if len(game["players"]) >= 6:
        return False
    game["players"].append({
        "uid":    uid,
        "name":   name,
        "hand":   [],
        "status": "waiting",  # waiting → playing → stand / bust / bj
    })
    return True

def deal_cards(game):
    deck = game["deck"]
    # Deal 2 cards to each player and dealer
    for _ in range(2):
        for p in game["players"]:
            p["hand"].append(deck.pop())
        game["dealer_hand"].append(deck.pop())
    game["state"]       = "playing"
    game["current_idx"] = 0
    # Check for instant blackjacks
    for p in game["players"]:
        if is_blackjack(p["hand"]):
            p["status"] = "bj"
    advance_turn(game)

def current_player(game):
    idx = game["current_idx"]
    players = game["players"]
    if idx < len(players):
        return players[idx]
    return None

def advance_turn(game):
    """Move to next player who isn't done. If all done, move to dealer phase."""
    while game["current_idx"] < len(game["players"]):
        p = game["players"][game["current_idx"]]
        if p["status"] in ("waiting",):
            p["status"] = "playing"
            return
        game["current_idx"] += 1
    # All players done — dealer plays
    play_dealer(game)

def hit(game, uid):
    p = next((x for x in game["players"] if x["uid"] == uid), None)
    if not p or p["status"] != "playing":
        return False
    p["hand"].append(game["deck"].pop())
    if is_bust(p["hand"]):
        p["status"] = "bust"
        game["current_idx"] += 1
        advance_turn(game)
    return True

def stand(game, uid):
    p = next((x for x in game["players"] if x["uid"] == uid), None)
    if not p or p["status"] != "playing":
        return False
    p["status"] = "stand"
    game["current_idx"] += 1
    advance_turn(game)
    return True

def play_dealer(game):
    game["state"] = "dealer"
    deck = game["deck"]
    while hand_score(game["dealer_hand"]) < 17:
        game["dealer_hand"].append(deck.pop())
    game["state"] = "done"

def resolve(game):
    """Returns list of {uid, name, result, chips_change}"""
    bet         = game["bet"]
    dealer_score = hand_score(game["dealer_hand"])
    dealer_bust  = is_bust(game["dealer_hand"])
    results = []

    for p in game["players"]:
        uid    = p["uid"]
        name   = p["name"]
        pscore = hand_score(p["hand"])

        if p["status"] == "bust":
            results.append({"uid": uid, "name": name, "result": "💥 Bust", "chips": -bet})
        elif p["status"] == "bj":
            results.append({"uid": uid, "name": name, "result": "🃏 Blackjack!", "chips": int(bet * 1.5)})
        elif dealer_bust:
            results.append({"uid": uid, "name": name, "result": "🎉 Dealer bust, you win!", "chips": bet})
        elif pscore > dealer_score:
            results.append({"uid": uid, "name": name, "result": "✅ Win!", "chips": bet})
        elif pscore == dealer_score:
            results.append({"uid": uid, "name": name, "result": "🤝 Push (tie)", "chips": 0})
        else:
            results.append({"uid": uid, "name": name, "result": "❌ Loss", "chips": -bet})

    return results

def game_board(game, hide_dealer=True):
    lines = ["🃏 *Blackjack Table*\n"]

    # Dealer hand
    if hide_dealer and game["state"] not in ("done", "dealer"):
        d_display = f"{card_str(game['dealer_hand'][0])} 🂠"
    else:
        d_display = hand_str(game["dealer_hand"])
        if not hide_dealer or game["state"] == "done":
            d_display += f"  _(score: {hand_score(game['dealer_hand'])})_"

    lines.append(f"🎩 Dealer: {d_display}")
    lines.append("")

    for p in game["players"]:
        score  = hand_score(p["hand"])
        status = p["status"]
        emoji  = {"playing": "👉", "stand": "✋", "bust": "💥", "bj": "🃏", "waiting": "⏳"}.get(status, "")
        lines.append(f"{emoji} *{p['name']}*: {hand_str(p['hand'])}  _(score: {score})_")

    return "\n".join(lines)
