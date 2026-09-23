from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from database import get_user, get_connection
from data import HOUSES, VEHICLES

def setup(bot):
    @bot.message_handler(func=lambda m: m.text == '🏠 املاک')
    def real_estate_menu(message):
        user = get_user(message.from_user.id)
        if not user: return

        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM houses WHERE user_id = ?", (user['id'],))
            my_houses = cur.fetchall()

        text = "🏠 املاک شما:\n\n"
        if not my_houses:
            text += "شما هیچ ملکی ندارید و احتمالاً بی‌خانمان هستید یا اجاره‌نشین."
        else:
            for h in my_houses:
                h_info = HOUSES.get(h['house_id'], {})
                text += f"▪️ {h_info.get('name', 'نامشخص')} - ارزش: ${h_info.get('price', 0):,.2f} - وضعیت: {h['condition']}%\n"

        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("خرید خانه", callback_data="buy_house_menu"))
        bot.send_message(message.chat.id, text, reply_markup=markup)

    @bot.callback_query_handler(func=lambda call: call.data == 'buy_house_menu')
    def buy_house_menu(call):
        markup = InlineKeyboardMarkup(row_width=1)
        for h_id, h_info in HOUSES.items():
            markup.add(InlineKeyboardButton(f"{h_info['name']} - ${h_info['price']:,.2f}", callback_data=f"buy_house_{h_id}"))
        bot.edit_message_text("یک خانه برای خرید انتخاب کنید:", call.message.chat.id, call.message.message_id, reply_markup=markup)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('buy_house_') and call.data != 'buy_house_menu')
    def buy_house_action(call):
        user = get_user(call.from_user.id)
        if not user: return

        h_id = call.data.replace('buy_house_', '')
        if h_id not in HOUSES: return

        house = HOUSES[h_id]
        from economy import modify_cash
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("BEGIN IMMEDIATE")
            if not modify_cash(user['id'], -house['price'], f"Bought house {house['name']}", cur, conn):
                bot.answer_callback_query(call.id, "پول نقد کافی ندارید!", show_alert=True)
                conn.rollback()
                return

            cur.execute("INSERT INTO houses (user_id, house_id) VALUES (?, ?)", (user['id'], h_id))
            conn.commit()

        bot.answer_callback_query(call.id, f"شما {house['name']} را خریدید!", show_alert=True)
        bot.delete_message(call.message.chat.id, call.message.message_id)

    @bot.message_handler(func=lambda m: m.text == '🚗 خودرو')
    def vehicles_menu(message):
        user = get_user(message.from_user.id)
        if not user: return

        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM vehicles WHERE user_id = ?", (user['id'],))
            my_cars = cur.fetchall()

        text = "🚗 وسایل نقلیه شما:\n\n"
        if not my_cars:
            text += "شما هیچ وسیله نقلیه‌ای ندارید."
        else:
            for c in my_cars:
                c_info = VEHICLES.get(c['vehicle_id'], {})
                text += f"▪️ {c_info.get('name', 'نامشخص')} - سوخت: {c['fuel']}% - وضعیت: {c['condition']}%\n"

        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("خرید خودرو", callback_data="buy_car_menu"))
        if my_cars:
            markup.add(InlineKeyboardButton("بنزین زدن", callback_data="refuel_car"))
        bot.send_message(message.chat.id, text, reply_markup=markup)

    @bot.callback_query_handler(func=lambda call: call.data == 'buy_car_menu')
    def buy_car_menu(call):
        markup = InlineKeyboardMarkup(row_width=1)
        for c_id, c_info in VEHICLES.items():
            markup.add(InlineKeyboardButton(f"{c_info['name']} - ${c_info['price']:,.2f}", callback_data=f"buy_car_{c_id}"))
        bot.edit_message_text("یک خودرو برای خرید انتخاب کنید:", call.message.chat.id, call.message.message_id, reply_markup=markup)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('buy_car_') and call.data != 'buy_car_menu')
    def buy_car_action(call):
        user = get_user(call.from_user.id)
        if not user: return

        c_id = call.data.replace('buy_car_', '')
        if c_id not in VEHICLES: return

        car = VEHICLES[c_id]
        from economy import modify_cash
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("BEGIN IMMEDIATE")
            if not modify_cash(user['id'], -car['price'], f"Bought vehicle {car['name']}", cur, conn):
                bot.answer_callback_query(call.id, "پول نقد کافی ندارید!", show_alert=True)
                conn.rollback()
                return

            cur.execute("INSERT INTO vehicles (user_id, vehicle_id) VALUES (?, ?)", (user['id'], c_id))
            conn.commit()

        bot.answer_callback_query(call.id, f"شما {car['name']} را خریدید!", show_alert=True)
        bot.delete_message(call.message.chat.id, call.message.message_id)

    @bot.callback_query_handler(func=lambda call: call.data == 'refuel_car')
    def refuel_car(call):
        user = get_user(call.from_user.id)
        if not user: return

        cost = 50 # flat cost for full tank for simplicity
        if user['cash'] < cost:
            bot.answer_callback_query(call.id, "پول کافی برای بنزین ندارید ($50).", show_alert=True)
            return

        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("UPDATE users SET cash = cash - ? WHERE id = ?", (cost, user['id']))
            cur.execute("UPDATE vehicles SET fuel = 100 WHERE user_id = ?", (user['id'],))

        bot.answer_callback_query(call.id, "باک بنزین تمام خودروهای شما پر شد!", show_alert=True)
