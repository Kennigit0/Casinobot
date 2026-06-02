import os

class Config:
    BOT_TOKEN        = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN")
    ADMIN_IDS        = [1173060685]
    STARTING_CHIPS   = 10_000
    DAILY_BONUS      = 5_000
    VIP_DAILY_BONUS  = 25_000
    VIP_PRICE_STARS  = 150
    MIN_BET          = 100        # fallback only, dynamic 15% used in game
    MAX_BET          = 999_999_999
    GAME_COOLDOWN    = 30         # seconds between games
    WORK_COOLDOWN    = 0.05       # hours = 3 minutes
    CRIME_COOLDOWN   = 0.25       # hours = 15 minutes
    HEIST_COOLDOWN   = 0.5        # hours = 30 minutes
    ROB_COOLDOWN     = 2          # hours

    # Tool prices (new 3x prices)
    FISHING_TOOLS = {
        "wooden_rod":     {"name": "🪵 Wooden Rod",      "price": 0,         "wait": 30, "rare": 0.05, "bonus": 0.00, "level": 5},
        "basic_rod":      {"name": "🎣 Basic Rod",        "price": 15000,     "wait": 25, "rare": 0.10, "bonus": 0.10, "level": 10},
        "silver_rod":     {"name": "🥈 Silver Rod",       "price": 75000,     "wait": 20, "rare": 0.20, "bonus": 0.25, "level": 20},
        "golden_rod":     {"name": "🥇 Golden Rod",       "price": 300000,    "wait": 15, "rare": 0.35, "bonus": 0.50, "level": 30},
        "diamond_rod":    {"name": "💎 Diamond Rod",      "price": 1500000,   "wait": 10, "rare": 0.55, "bonus": 0.75, "level": 40},
        "magic_rod":      {"name": "🔮 Magic Rod",        "price": 6000000,   "wait": 7,  "rare": 0.75, "bonus": 1.00, "level": 50},
        "legendary_rod":  {"name": "⭐ Legendary Rod",    "price": 30000000,  "wait": 5,  "rare": 0.90, "bonus": 2.00, "level": 75},
    }
    MINING_TOOLS = {
        "stone_pickaxe":     {"name": "🪨 Stone Pickaxe",      "price": 0,        "wait": 30, "rare": 0.05, "bonus": 0.00, "level": 10},
        "iron_pickaxe":      {"name": "⚙️ Iron Pickaxe",       "price": 15000,    "wait": 25, "rare": 0.10, "bonus": 0.10, "level": 15},
        "silver_pickaxe":    {"name": "🥈 Silver Pickaxe",     "price": 75000,    "wait": 20, "rare": 0.20, "bonus": 0.25, "level": 20},
        "gold_pickaxe":      {"name": "🥇 Gold Pickaxe",       "price": 300000,   "wait": 15, "rare": 0.35, "bonus": 0.50, "level": 30},
        "diamond_pickaxe":   {"name": "💎 Diamond Pickaxe",    "price": 1500000,  "wait": 10, "rare": 0.55, "bonus": 0.75, "level": 40},
        "enchanted_pickaxe": {"name": "🔮 Enchanted Pickaxe",  "price": 6000000,  "wait": 7,  "rare": 0.75, "bonus": 1.00, "level": 50},
        "legendary_pickaxe": {"name": "⭐ Legendary Pickaxe",  "price": 30000000, "wait": 5,  "rare": 0.90, "bonus": 2.00, "level": 75},
    }
    FARMING_TOOLS = {
        "bare_hands":        {"name": "🤲 Bare Hands",        "price": 0,        "wait": 30, "bonus": 0.0,  "level": 15},
        "basic_hoe":         {"name": "🪚 Basic Hoe",         "price": 15000,    "wait": 25, "bonus": 0.10, "level": 20},
        "silver_hoe":        {"name": "🥈 Silver Hoe",        "price": 75000,    "wait": 20, "bonus": 0.25, "level": 25},
        "golden_hoe":        {"name": "🥇 Golden Hoe",        "price": 300000,   "wait": 15, "bonus": 0.50, "level": 35},
        "diamond_hoe":       {"name": "💎 Diamond Hoe",       "price": 1500000,  "wait": 10, "bonus": 0.75, "level": 45},
        "magic_tractor":     {"name": "🚜 Magic Tractor",     "price": 6000000,  "wait": 7,  "bonus": 1.00, "level": 55},
        "legendary_tractor": {"name": "⭐ Legendary Tractor", "price": 30000000, "wait": 5,  "bonus": 2.00, "level": 75},
    }
    ALL_TOOLS = {**FISHING_TOOLS, **MINING_TOOLS, **FARMING_TOOLS}

    # Level titles
    TITLES = {
        0:  "🥉 Beginner",
        5:  "🎣 Fisher",
        10: "⛏️ Miner",
        15: "🌾 Farmer",
        20: "🥈 Regular",
        30: "🥇 Pro",
        40: "💎 Elite",
        50: "🔮 Master",
        75: "⭐ Legend",
        100:"👑 Casino King",
    }

    # XP rewards
    XP_GAME_WIN  = 10
    XP_BJ_WIN    = 15
    XP_WORK      = 20
    XP_CRIME     = 35
    XP_HEIST     = 50
    XP_FISH      = 25
    XP_MINE      = 25
    XP_FARM      = 25
    XP_DAILY     = 15
