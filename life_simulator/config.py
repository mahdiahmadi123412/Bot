import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
ADMIN_IDS = [int(id_str) for id_str in os.getenv("ADMIN_IDS", "123456789").split(",") if id_str.strip()]

# Game loop settings
BACKGROUND_TICK_RATE = 15 * 60  # 15 minutes in seconds for minor ticks (needs decay)
DAILY_TICK_RATE = 60 * 60       # 1 hour in seconds for major ticks (1 day in-game)
