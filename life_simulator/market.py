from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from .database import get_user, get_connection, get_user_state

def setup(bot):
    @bot.message_handler(func=lambda m: m.text == '📈 بازار')
    def market_menu(message):
        text = "بازار اقتصاد جهانی مشترک تغییر میکند"

        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM market")
            items = cur.fetchall()

        markup = InlineKeyboardMarkup()
        if not items:
            text += "\n\nبازار خالی است."
        else:
            for item in items:
                trend = "📈" if item['current_price'] >= item['base_price'] else "📉"
                text += f"\n{item['item_id']}: ${item['current_price']:,.2f} {trend}"
                markup.add(
                    InlineKeyboardButton(f"خرید {item['item_id']}", callback_data=f"market_buy_{item['item_id']}"),
                    InlineKeyboardButton(f"فروش {item['item_id']}", callback_data=f"market_sell_{item['item_id']}")
                )

        bot.send_message(message.chat.id, text, reply_markup=markup)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('market_buy_'))
    def market_buy(call):
        item_id = call.data.replace('market_buy_', '')
        from .database import set_user_state
        set_user_state(call.from_user.id, "MARKET_BUY", {"item": item_id})
        bot.send_message(call.message.chat.id, f"تعداد {item_id} برای خرید را وارد کنید:")
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('market_sell_'))
    def market_sell(call):
        item_id = call.data.replace('market_sell_', '')
        from .database import set_user_state
        set_user_state(call.from_user.id, "MARKET_SELL", {"item": item_id})
        bot.send_message(call.message.chat.id, f"تعداد {item_id} برای فروش را وارد کنید:")
        bot.answer_callback_query(call.id)

    @bot.message_handler(func=lambda m: get_user_state(m.from_user.id)[0] in ["MARKET_BUY", "MARKET_SELL"])
    def process_market(message):
        from .database import get_user_state, set_user_state
        state, data = get_user_state(message.from_user.id)
        user = get_user(message.from_user.id)

        try:
            qty = int(message.text)
            if qty <= 0: raise ValueError
        except:
            bot.send_message(message.chat.id, "تعداد نامعتبر است.")
            set_user_state(user['tg_id'], "NONE")
            return

        item_id = data['item']

        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("BEGIN IMMEDIATE")
            try:
                cur.execute("SELECT * FROM market WHERE item_id = ?", (item_id,))
                item = cur.fetchone()
                if not item:
                    raise Exception("Item not found")

                total_price = item['current_price'] * qty

                if state == "MARKET_BUY":
                    from .economy import modify_cash
                    if not modify_cash(user['id'], -total_price, f"Bought {qty} {item_id}", cur, conn):
                        bot.send_message(message.chat.id, "پول کافی ندارید.")
                        conn.rollback()
                        set_user_state(user['tg_id'], "NONE")
                        return

                    # Add to inventory
                    cur.execute("SELECT * FROM inventory WHERE user_id = ? AND item_id = ?", (user['id'], item_id))
                    if cur.fetchone():
                        cur.execute("UPDATE inventory SET quantity = quantity + ? WHERE user_id = ? AND item_id = ?", (qty, user['id'], item_id))
                    else:
                        cur.execute("INSERT INTO inventory (user_id, item_id, quantity) VALUES (?, ?, ?)", (user['id'], item_id, qty))
                    # Adjust market (price goes up due to demand)
                    cur.execute("UPDATE market SET demand = demand + ?, current_price = current_price * 1.01 WHERE item_id = ?", (qty, item_id))
                    bot.send_message(message.chat.id, f"شما {qty} عدد {item_id} خریدید.")

                elif state == "MARKET_SELL":
                    cur.execute("SELECT * FROM inventory WHERE user_id = ? AND item_id = ?", (user['id'], item_id))
                    inv = cur.fetchone()
                    if not inv or inv['quantity'] < qty:
                        bot.send_message(message.chat.id, "موجودی کافی در انبار ندارید.")
                        conn.rollback()
                        set_user_state(user['tg_id'], "NONE")
                        return
                    from .economy import modify_cash
                    modify_cash(user['id'], total_price, f"Sold {qty} {item_id}", cur, conn)
                    cur.execute("UPDATE inventory SET quantity = quantity - ? WHERE user_id = ? AND item_id = ?", (qty, user['id'], item_id))
                    # Clean up zero inventory
                    cur.execute("DELETE FROM inventory WHERE quantity <= 0")
                    # Adjust market (price goes down due to supply)
                    cur.execute("UPDATE market SET supply = supply + ?, current_price = MAX(base_price * 0.1, current_price * 0.99) WHERE item_id = ?", (qty, item_id))
                    bot.send_message(message.chat.id, f"شما {qty} عدد {item_id} فروختید.")

                conn.commit()
            except Exception as e:
                conn.rollback()
                bot.send_message(message.chat.id, "خطا در پردازش تراکنش بازار.")

        set_user_state(user['tg_id'], "NONE")

    @bot.message_handler(func=lambda m: m.text == '🛒 فروشگاه')
    def shop_menu(message):
        user = get_user(message.from_user.id)
        if not user: return

        from .data import FOODS
        text = "🛒 فروشگاه روزمره\n\nبرای تامین نیازهای خود خرید کنید:"
        markup = InlineKeyboardMarkup(row_width=1)
        for f_id, f_info in FOODS.items():
            markup.add(InlineKeyboardButton(f"{f_info['name']} - ${f_info['price']}", callback_data=f"buy_food_{f_id}"))

        bot.send_message(message.chat.id, text, reply_markup=markup)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('buy_food_'))
    def buy_food(call):
        user = get_user(call.from_user.id)
        if not user: return

        f_id = call.data.replace('buy_food_', '')
        from .data import FOODS
        if f_id not in FOODS: return

        food = FOODS[f_id]
        if user['cash'] < food['price']:
            bot.answer_callback_query(call.id, "پول نقد کافی ندارید!", show_alert=True)
            return

        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                UPDATE users SET
                    cash = cash - ?,
                    hunger = MIN(100, hunger + ?),
                    health = MIN(100, MAX(0, health + ?)),
                    happiness = MIN(100, happiness + ?)
                WHERE id = ?
            """, (food['price'], food['hunger'], food['health'], food['happiness'], user['id']))

        bot.answer_callback_query(call.id, f"شما {food['name']} خوردید!", show_alert=True)
