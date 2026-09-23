import telebot
from .config import BOT_TOKEN
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

bot = telebot.TeleBot(BOT_TOKEN)

# Import and register handlers from other modules
from . import ui
from . import character
from . import economy
from . import bank
from . import jobs
from . import education
from . import assets
from . import market
from . import needs
from . import social
from . import business
from . import events
from . import progression
from . import admin
from . import worker

# Register UI handlers (we will pass the bot instance to setup functions in each module)
def setup_bot():
    ui.setup(bot)
    character.setup(bot)
    economy.setup(bot)
    bank.setup(bot)
    jobs.setup(bot)
    education.setup(bot)
    assets.setup(bot)
    market.setup(bot)
    needs.setup(bot)
    social.setup(bot)
    business.setup(bot)
    events.setup(bot)
    progression.setup(bot)
    admin.setup(bot)

    # Start background worker
    worker.start_worker(bot)

if __name__ == "__main__":
    setup_bot()
    from .database import init_db
    init_db()
    logging.info("Life Simulator Bot is starting...")
    bot.infinity_polling()
