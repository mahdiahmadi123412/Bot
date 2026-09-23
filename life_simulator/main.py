import logging
import telebot
from telebot import apihelper
apihelper.ENABLE_MIDDLEWARE = True
from config import BOT_TOKEN
from database import init_db
import ui
import character
import economy
import bank
import jobs
import education
import assets
import market
import needs
import social
import business
import events
import progression
import admin
import worker

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

bot = telebot.TeleBot(BOT_TOKEN)

# Rate limiting middleware
@bot.middleware_handler(update_types=['message'])
def rate_limit_middleware(bot_instance, message):
    from security import check_rate_limit
    if not check_rate_limit(message.from_user.id, cooldown=0.5):
        bot.send_message(message.chat.id, "لطفاً آهسته‌تر پیام بفرستید! (Rate Limit)")
        raise telebot.apihelper.ApiException('Rate Limited', None, None)

@bot.middleware_handler(update_types=['callback_query'])
def rate_limit_callback_middleware(bot_instance, call):
    from security import check_rate_limit
    if not check_rate_limit(call.from_user.id, cooldown=0.5):
        bot.answer_callback_query(call.id, "لطفاً آهسته‌تر کلیک کنید! (Rate Limit)", show_alert=True)
        raise telebot.apihelper.ApiException('Rate Limited', None, None)

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

if __name__ == "__main__":
    logging.info("Initializing Database...")
    init_db()

    logging.info("Setting up Bot Handlers...")
    setup_bot()

    logging.info("Starting Background Worker...")
    worker.start_worker(bot)

    logging.info("Life Simulator Bot is now running!")
    bot.infinity_polling(skip_pending=True, timeout=30, long_polling_timeout=30)
