# 🎰 Telegram Casino Bot

A multiplayer casino bot for Telegram with virtual chips, group games, and VIP system.

## 🎮 Games
- **Slots** — Spin to win with 7 symbols and jackpots
- **Blackjack** — Multiplayer (up to 6 players) in group chats
- **Dice Duel** — 1v1 dice challenge between players
- **Roulette** — Color, number, odd/even, dozen bets

## 💰 Economy
- 10,000 starting chips for every new player
- Daily bonus (5,000 free / 25,000 VIP)
- Leaderboard
- VIP membership via Telegram Stars

---

## 🚀 Setup (5 Steps)

### Step 1 — Create your bot
1. Open Telegram → search `@BotFather`
2. Send `/newbot`
3. Follow instructions → copy your **BOT_TOKEN**

### Step 2 — Add bot to your group
1. Open your group → Add Members → search your bot
2. Make it an **Admin** (so it can send messages)

### Step 3 — Set up environment
```bash
cp .env.example .env
# Edit .env and paste your BOT_TOKEN
```

### Step 4 — Install & run locally (for testing)
```bash
pip install -r requirements.txt
python bot.py
```

### Step 5 — Deploy to Railway (free, always-on)
1. Push code to GitHub:
```bash
git init
git add .
git commit -m "casino bot"
git remote add origin https://github.com/YOUR_USERNAME/casino-bot.git
git push -u origin main
```

2. Go to [railway.app](https://railway.app)
3. New Project → Deploy from GitHub → select your repo
4. Add environment variable: `BOT_TOKEN = your_token`
5. Railway auto-detects Python and runs it ✅

---

## 📋 Commands

| Command | Description |
|---|---|
| `/start` | Register with age verification |
| `/balance` | Check your chips |
| `/daily` | Claim daily bonus |
| `/leaderboard` | Top 10 players |
| `/vip` | VIP info |
| `/terms` | Terms of service |
| `/slots [bet]` | Play slots |
| `/bj [bet]` | Start blackjack table |
| `/dice [bet]` | Reply to someone to challenge them |
| `/roulette [type] [value] [bet]` | Bet on roulette |

### Roulette examples:
```
/roulette color red 1000
/roulette color black 500
/roulette color green 200    (x14 payout!)
/roulette number 17 100      (x35 payout!)
/roulette odd_even odd 500
/roulette dozen 1st 1000
```

---

## 🗂 Project Structure
```
casino_bot/
├── bot.py              ← Main bot (all handlers)
├── database.py         ← SQLite database layer
├── config.py           ← Settings & constants
├── games/
│   ├── slots.py        ← Slot machine logic
│   ├── blackjack.py    ← Card game logic
│   ├── dice.py         ← Dice duel logic
│   └── roulette.py     ← Roulette logic
├── requirements.txt
├── Procfile            ← Railway deployment
└── .env.example        ← Environment template
```

---

## ⚠️ Legal Notice
- All chips are **virtual** with zero real-world monetary value
- This bot is for **entertainment only**
- Users must be **18+**
- Buying/selling chips for real money is **prohibited**

---

## 💡 Monetization
- **Telegram Stars** — sell VIP membership
- **Chip bundles** — sell virtual chips via Stars
- **Sponsored messages** — once you have 1000+ users
