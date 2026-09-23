from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from .database import get_user, get_connection
from .data import CITIES

def setup(bot):
    @bot.message_handler(func=lambda m: m.text == '🌍 شهر')
    def city_menu(message):
        user = get_user(message.from_user.id)
        if not user: return

        current_city = CITIES.get(user['city'], {}).get('name', 'نامشخص')
        text = f"🌍 شما اکنون در شهر {current_city} هستید.\nآیا می‌خواهید سفر کنید؟"

        markup = InlineKeyboardMarkup(row_width=1)
        for c_id, c_info in CITIES.items():
            if c_id != user['city']:
                markup.add(InlineKeyboardButton(f"سفر به {c_info['name']} (${c_info['travel_cost']})", callback_data=f"travel_{c_id}"))

        bot.send_message(message.chat.id, text, reply_markup=markup)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('travel_'))
    def travel_action(call):
        user = get_user(call.from_user.id)
        if not user: return

        c_id = call.data.replace('travel_', '')
        if c_id not in CITIES: return

        city = CITIES[c_id]
        if user['cash'] < city['travel_cost']:
            bot.answer_callback_query(call.id, "پول کافی برای سفر ندارید!", show_alert=True)
            return

        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("UPDATE users SET cash = cash - ?, city = ? WHERE id = ?", (city['travel_cost'], c_id, user['id']))

        bot.answer_callback_query(call.id, f"شما به {city['name']} سفر کردید!", show_alert=True)
        bot.delete_message(call.message.chat.id, call.message.message_id)
