from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from .database import get_user, get_connection

def setup(bot):
    @bot.message_handler(func=lambda m: m.text == '🏢 کسب‌وکار')
    def business_menu(message):
        user = get_user(message.from_user.id)
        if not user: return

        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM businesses WHERE owner_id = ?", (user['id'],))
            businesses = cur.fetchall()

        if not businesses:
            text = "شما هیچ کسب‌وکاری ندارید. می‌توانید با پرداخت $250,000 یک شرکت تأسیس کنید."
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("تأسیس شرکت ($250,000)", callback_data="biz_create"))
            bot.send_message(message.chat.id, text, reply_markup=markup)
        else:
            text = "🏢 شرکت‌های شما:\n\n"
            for b in businesses:
                net = b['income_rate'] - b['expense_rate']
                text += f"▪️ {b['name']} ({b['type']})\n"
                text += f"   سرمایه: ${b['capital']:,.2f}\n"
                text += f"   کارمندان: {b['employees_count']}\n"
                text += f"   درآمد خالص روزانه: ${net:,.2f}\n\n"

            # Simple interaction
            bot.send_message(message.chat.id, text)

    @bot.callback_query_handler(func=lambda call: call.data == 'biz_create')
    def create_business(call):
        user = get_user(call.from_user.id)
        if not user: return

        cost = 250000
        if user['cash'] < cost:
            bot.answer_callback_query(call.id, "پول کافی برای تأسیس شرکت ندارید!", show_alert=True)
            return

        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("UPDATE users SET cash = cash - ? WHERE id = ?", (cost, user['id']))
            cur.execute("INSERT INTO businesses (owner_id, name, type, capital, income_rate, expense_rate) VALUES (?, ?, ?, ?, ?, ?)",
                        (user['id'], f"شرکت {user['last_name']}", "Technology", cost, 8400, 5200))

        bot.answer_callback_query(call.id, "شرکت شما با موفقیت تأسیس شد!", show_alert=True)
        bot.delete_message(call.message.chat.id, call.message.message_id)
