from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from database import get_user, get_connection
from config import ADMIN_IDS

def is_admin(user_id):
    return user_id in ADMIN_IDS

def setup(bot):
    @bot.message_handler(commands=['admin'])
    def admin_panel(message):
        if not is_admin(message.from_user.id):
            return

        text = "🛠️ پنل مدیریت شبیه‌ساز زندگی\n\nبرای انجام عملیات، یکی از گزینه‌های زیر را انتخاب کنید:"
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("آمار کلی", callback_data="admin_stats"),
            InlineKeyboardButton("تولید رویداد پول (News)", callback_data="admin_event")
        )
        markup.add(
            InlineKeyboardButton("اقتصاد جهانی (تورم)", callback_data="admin_economy")
        )
        bot.send_message(message.chat.id, text, reply_markup=markup)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('admin_'))
    def handle_admin(call):
        if not is_admin(call.from_user.id):
            return

        action = call.data.split('_')[1]

        if action == "stats":
            with get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM users")
                u_count = cur.fetchone()[0]
                cur.execute("SELECT SUM(cash) FROM users")
                total_cash = cur.fetchone()[0] or 0

            bot.send_message(call.message.chat.id, f"تعداد کاربران: {u_count}\nمجموع پول در گردش: ${total_cash:,.2f}")
            bot.answer_callback_query(call.id)

        elif action == "event":
            with get_connection() as conn:
                cur = conn.cursor()
                cur.execute("BEGIN IMMEDIATE")
                cur.execute("UPDATE users SET cash = cash + 500")
                cur.execute("INSERT INTO news (content) VALUES ('دولت به تمام شهروندان ۵۰۰ دلار یارانه پرداخت کرد!')")
                conn.commit()
            bot.send_message(call.message.chat.id, "رویداد جهانی اجرا شد: 500$ به تمام کاربران داده شد.")
            bot.answer_callback_query(call.id)

        elif action == "economy":
            with get_connection() as conn:
                cur = conn.cursor()
                cur.execute("BEGIN IMMEDIATE")
                cur.execute("INSERT INTO economy_history (inflation_rate, fuel_price_modifier, food_price_modifier, housing_price_modifier) VALUES (5.0, 1.1, 1.1, 1.2)")

                # Apply inflation to base market prices dynamically
                cur.execute("UPDATE market SET current_price = current_price * 1.05")
                conn.commit()

            bot.send_message(call.message.chat.id, "اقتصاد جهانی تغییر کرد (تورم ۵٪ بر بازار اعمال شد).")
            bot.answer_callback_query(call.id)
