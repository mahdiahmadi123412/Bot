from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from database import get_user, get_connection

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
            markup = InlineKeyboardMarkup()
            for b in businesses:
                net = b['income_rate'] - b['expense_rate']
                text += f"▪️ {b['name']} ({b['type']})\n"
                text += f"   سرمایه: ${b['capital']:,.2f}\n"
                text += f"   کارمندان: {b['employees_count']}\n"
                text += f"   تولید و فروش روزانه: ${b['income_rate']:,.2f}\n"
                text += f"   هزینه روزانه (حقوق و مواد): ${b['expense_rate']:,.2f}\n"
                text += f"   سود خالص روزانه: ${net:,.2f}\n\n"
                markup.add(InlineKeyboardButton(f"مدیریت {b['name']}", callback_data=f"biz_manage_{b['id']}"))

            bot.send_message(message.chat.id, text, reply_markup=markup)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('biz_manage_'))
    def manage_business(call):
        b_id = call.data.replace('biz_manage_', '')
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("استخدام کارمند", callback_data=f"biz_hire_{b_id}"),
            InlineKeyboardButton("اخراج کارمند", callback_data=f"biz_fire_{b_id}")
        )
        markup.add(
            InlineKeyboardButton("سرمایه‌گذاری (افزایش تولید)", callback_data=f"biz_invest_{b_id}")
        )
        bot.send_message(call.message.chat.id, "پنل مدیریت شرکت:", reply_markup=markup)
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('biz_hire_'))
    def hire_employee(call):
        user = get_user(call.from_user.id)
        if not user: return
        b_id = call.data.replace('biz_hire_', '')

        cost_per_hire = 500
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("BEGIN IMMEDIATE")
            from economy import modify_cash
            if not modify_cash(user['id'], -cost_per_hire, f"Hiring fee for business {b_id}", cur, conn):
                bot.answer_callback_query(call.id, "هزینه استخدام (500$) را ندارید.", show_alert=True)
                conn.rollback()
                return

            # Real production logic: an employee adds flat salary cost, but multiplies base production slightly
            cur.execute("UPDATE businesses SET employees_count = employees_count + 1, income_rate = income_rate + 300, expense_rate = expense_rate + 200 WHERE id = ?", (b_id,))
            conn.commit()
        bot.answer_callback_query(call.id, "یک کارمند استخدام شد! تولید و هزینه‌ها افزایش یافت.", show_alert=True)
        bot.delete_message(call.message.chat.id, call.message.message_id)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('biz_fire_'))
    def fire_employee(call):
        user = get_user(call.from_user.id)
        if not user: return
        b_id = call.data.replace('biz_fire_', '')

        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT employees_count FROM businesses WHERE id = ?", (b_id,))
            b = cur.fetchone()
            if not b or b['employees_count'] <= 0:
                bot.answer_callback_query(call.id, "شرکت شما کارمندی ندارد!", show_alert=True)
                return

            cur.execute("UPDATE businesses SET employees_count = employees_count - 1, income_rate = income_rate - 300, expense_rate = expense_rate - 200 WHERE id = ?", (b_id,))
            conn.commit()

        bot.answer_callback_query(call.id, "یک کارمند اخراج شد. هزینه‌ها و تولید کاهش یافت.", show_alert=True)
        bot.delete_message(call.message.chat.id, call.message.message_id)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('biz_invest_'))
    def invest_business(call):
        user = get_user(call.from_user.id)
        if not user: return
        b_id = call.data.replace('biz_invest_', '')

        invest_amount = 50000
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("BEGIN IMMEDIATE")
            from economy import modify_cash
            if not modify_cash(user['id'], -invest_amount, f"Capital injection for business {b_id}", cur, conn):
                bot.answer_callback_query(call.id, "سرمایه کافی (50,000$) برای ارتقای تجهیزات ندارید.", show_alert=True)
                conn.rollback()
                return

            cur.execute("UPDATE businesses SET capital = capital + ?, income_rate = income_rate + 1500, expense_rate = expense_rate + 500 WHERE id = ?", (invest_amount, b_id))
            conn.commit()
        bot.answer_callback_query(call.id, "تجهیزات و تولید ارتقا یافت!", show_alert=True)
        bot.delete_message(call.message.chat.id, call.message.message_id)

    @bot.callback_query_handler(func=lambda call: call.data == 'biz_create')
    def create_business(call):
        user = get_user(call.from_user.id)
        if not user: return

        cost = 250000
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("BEGIN IMMEDIATE")
            from economy import modify_cash
            if not modify_cash(user['id'], -cost, "Created a business", cur, conn):
                bot.answer_callback_query(call.id, "پول کافی برای تأسیس شرکت ندارید!", show_alert=True)
                conn.rollback()
                return

            cur.execute("INSERT INTO businesses (owner_id, name, type, capital, income_rate, expense_rate) VALUES (?, ?, ?, ?, ?, ?)",
                        (user['id'], f"شرکت {user['last_name']}", "Technology", cost, 8400, 5200))
            conn.commit()

        bot.answer_callback_query(call.id, "شرکت شما با موفقیت تأسیس شد!", show_alert=True)
        bot.delete_message(call.message.chat.id, call.message.message_id)
