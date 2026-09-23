from telebot.types import ReplyKeyboardMarkup, KeyboardButton
from database import get_user, set_user_state

def get_main_menu():
    markup = ReplyKeyboardMarkup(row_width=3, resize_keyboard=True)
    # rows of buttons
    markup.add(
        KeyboardButton('🏠 زندگی من'),
        KeyboardButton('💼 کار'),
        KeyboardButton('🎓 تحصیل')
    )
    markup.add(
        KeyboardButton('💰 اقتصاد'),
        KeyboardButton('🏦 بانک'),
        KeyboardButton('🏠 املاک')
    )
    markup.add(
        KeyboardButton('🚗 خودرو'),
        KeyboardButton('🏢 کسب‌وکار'),
        KeyboardButton('👥 دوستان')
    )
    markup.add(
        KeyboardButton('❤️ خانواده'),
        KeyboardButton('🛒 فروشگاه'),
        KeyboardButton('📈 بازار')
    )
    markup.add(
        KeyboardButton('🌍 شهر'),
        KeyboardButton('🎯 مأموریت‌ها'),
        KeyboardButton('🍔 نیازها')
    )
    markup.add(
        KeyboardButton('🏆 دستاوردها'),
        KeyboardButton('🥇 رتبه‌بندی'),
        KeyboardButton('⚙️ تنظیمات')
    )
    return markup

def setup(bot):
    @bot.message_handler(commands=['start'])
    def send_welcome(message):
        user = get_user(message.from_user.id)
        if not user:
            bot.send_message(message.chat.id, "سلام! به شبیه‌ساز زندگی خوش آمدید.\nبرای شروع، لطفاً روی دکمه زیر کلیک کنید یا /register را بفرستید.")
        else:
            bot.send_message(message.chat.id, "خوش برگشتی!", reply_markup=get_main_menu())
            set_user_state(message.from_user.id, "NONE")

    @bot.message_handler(func=lambda m: m.text == 'بازگشت به منوی اصلی')
    def back_to_main(message):
        set_user_state(message.from_user.id, "NONE")
        bot.send_message(message.chat.id, "به منوی اصلی برگشتید.", reply_markup=get_main_menu())

def get_cancel_markup():
    markup = ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    markup.add(KeyboardButton('بازگشت به منوی اصلی'))
    return markup
