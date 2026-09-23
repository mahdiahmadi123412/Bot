from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from .database import get_user, get_connection

def setup(bot):
    @bot.message_handler(func=lambda m: m.text == '🍔 نیازها')
    def needs_menu(message):
        user = get_user(message.from_user.id)
        if not user: return

        text = f"""🍔 وضعیت جسمی و روحی:

❤️ سلامت: {user['health']}%
😊 شادی: {user['happiness']}%
⚡ انرژی: {user['energy']}%
🍔 گرسنگی: {user['hunger']}%
💧 تشنگی: {user['thirst']}%

می‌توانید استراحت کنید، ورزش کنید یا به تفریح بپردازید.
"""
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("خوابیدن (بازیابی انرژی)", callback_data="need_sleep"),
            InlineKeyboardButton("نوشیدن آب", callback_data="need_water")
        )
        markup.add(
            InlineKeyboardButton("ورزش (سلامتی و شادی)", callback_data="need_sport"),
            InlineKeyboardButton("مراجعه به پزشک", callback_data="need_doctor")
        )
        markup.add(InlineKeyboardButton("تفریح (بازیابی شادی)", callback_data="need_fun"))

        bot.send_message(message.chat.id, text, reply_markup=markup)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('need_'))
    def handle_needs(call):
        user = get_user(call.from_user.id)
        if not user: return

        action = call.data.split('_')[1]

        with get_connection() as conn:
            cur = conn.cursor()

            if action == "sleep":
                if user['energy'] >= 100:
                    bot.answer_callback_query(call.id, "شما خسته نیستید.", show_alert=True)
                    return
                # Sleeping restores energy but uses hunger/thirst
                cur.execute("UPDATE users SET energy = 100, hunger = MAX(0, hunger - 20), thirst = MAX(0, thirst - 30) WHERE id = ?", (user['id'],))
                bot.answer_callback_query(call.id, "شما استراحت کردید و انرژی کامل گرفتید.", show_alert=True)

            elif action == "water":
                cost = 2
                if user['cash'] < cost:
                    bot.answer_callback_query(call.id, "پول کافی ندارید.", show_alert=True)
                    return
                cur.execute("UPDATE users SET cash = cash - ?, thirst = 100 WHERE id = ?", (cost, user['id']))
                bot.answer_callback_query(call.id, "شما آب نوشیدید.", show_alert=True)

            elif action == "sport":
                if user['energy'] < 30:
                    bot.answer_callback_query(call.id, "انرژی برای ورزش ندارید.", show_alert=True)
                    return
                cur.execute("UPDATE users SET energy = energy - 30, health = MIN(100, health + 10), happiness = MIN(100, happiness + 15), thirst = MAX(0, thirst - 20), xp = xp + 5 WHERE id = ?", (user['id'],))
                bot.answer_callback_query(call.id, "شما ورزش کردید! سلامتی و شادی افزایش یافت.", show_alert=True)

            elif action == "doctor":
                cost = 200
                if user['cash'] < cost:
                    bot.answer_callback_query(call.id, f"هزینه درمان ${cost} است. پول ندارید.", show_alert=True)
                    return
                if user['health'] >= 100:
                    bot.answer_callback_query(call.id, "شما در سلامت کامل هستید.", show_alert=True)
                    return
                cur.execute("UPDATE users SET cash = cash - ?, health = 100 WHERE id = ?", (cost, user['id']))
                bot.answer_callback_query(call.id, "شما درمان شدید و سلامتی خود را بازیافتید.", show_alert=True)

            elif action == "fun":
                cost = 50
                if user['cash'] < cost:
                    bot.answer_callback_query(call.id, f"هزینه تفریح ${cost} است. پول ندارید.", show_alert=True)
                    return
                cur.execute("UPDATE users SET cash = cash - ?, happiness = 100 WHERE id = ?", (cost, user['id']))
                bot.answer_callback_query(call.id, "شما تفریح کردید و روحیه‌تان عالی شد!", show_alert=True)
