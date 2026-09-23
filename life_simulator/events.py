import random
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from database import get_user, get_connection
from data import CITIES, RANDOM_EVENTS

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

        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("BEGIN IMMEDIATE")

            # Check fuel if they own a vehicle, otherwise purely cash
            cur.execute("SELECT * FROM vehicles WHERE user_id = ?", (user['id'],))
            vehicle = cur.fetchone()

            from economy import modify_cash
            if not modify_cash(user['id'], -city['travel_cost'], f"Traveled to {city['name']}", cur, conn):
                bot.answer_callback_query(call.id, "پول کافی برای سفر ندارید!", show_alert=True)
                conn.rollback()
                return

            if vehicle:
                if vehicle['fuel'] < 20:
                    bot.answer_callback_query(call.id, "بنزین کافی برای سفر با ماشین شخصی را ندارید (حداقل ۲۰٪)!", show_alert=True)
                    conn.rollback()
                    return
                cur.execute("UPDATE vehicles SET fuel = fuel - 20 WHERE id = ?", (vehicle['id'],))

            cur.execute("UPDATE users SET city = ? WHERE id = ?", (c_id, user['id']))
            conn.commit()

        bot.answer_callback_query(call.id, f"شما به {city['name']} سفر کردید!", show_alert=True)
        bot.delete_message(call.message.chat.id, call.message.message_id)

        # Trigger random travel event (25% chance)
        if random.random() < 0.25:
            trigger_random_event(bot, call.message.chat.id, user['id'])

    @bot.message_handler(func=lambda m: m.text == '🎲 رویدادهای تصادفی')
    def random_event_btn(message):
        bot.send_message(message.chat.id, "رویدادهای تصادفی در حین بازی (مانند سفر یا گذر زمان) به طور خودکار رخ می‌دهند.")

def trigger_random_event(bot, chat_id, user_id):
    ev = random.choice(RANDOM_EVENTS)
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("BEGIN IMMEDIATE")

        try:
            if ev['type'] == 'cash':
                from economy import modify_cash
                modify_cash(user_id, ev['amount'], "Random Event", cur, conn)
            elif ev['type'] == 'health':
                cur.execute("UPDATE users SET health = MIN(100, MAX(0, health + ?)) WHERE id = ?", (ev['amount'], user_id))

            conn.commit()
            bot.send_message(chat_id, f"🎲 **رویداد تصادفی!**\n\n{ev['text']}", parse_mode="Markdown")
        except Exception as e:
            conn.rollback()
