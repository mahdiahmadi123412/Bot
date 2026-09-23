from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from .database import get_user, get_connection

def setup(bot):
    @bot.message_handler(func=lambda m: m.text == '📈 بازار')
    def market_menu(message):
        text = "📈 بازار اقتصاد جهانی مشترک\n\nقیمت اقلام با توجه به عرضه و تقاضا تغییر می‌کند."

        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM market")
            items = cur.fetchall()

        if not items:
            text += "\n\nبازار در حال حاضر خالی است."
        else:
            for item in items:
                trend = "📈" if item['current_price'] > item['base_price'] else "📉"
                text += f"\n{item['item_id']}: ${item['current_price']:,.2f} {trend} (عرضه: {item['supply']})"

        bot.send_message(message.chat.id, text)

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
