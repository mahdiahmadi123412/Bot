from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from database import get_user, get_connection
from data import EDUCATION

def setup(bot):
    @bot.message_handler(func=lambda m: m.text == '🎓 تحصیل')
    def education_menu(message):
        user = get_user(message.from_user.id)
        if not user: return

        text = "🎓 مرکز آموزش و دانشگاه\nشما می‌توانید با پرداخت هزینه، مهارت‌های خود را ارتقا دهید یا مدرک بگیرید."

        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("آموزش برنامه‌نویسی", callback_data="edu_skill_programming"),
            InlineKeyboardButton("آموزش مدیریت", callback_data="edu_skill_management")
        )
        markup.add(
            InlineKeyboardButton("آموزش اقتصاد", callback_data="edu_skill_economy"),
            InlineKeyboardButton("آموزش ارتباطات", callback_data="edu_skill_communication")
        )
        markup.add(
            InlineKeyboardButton("آموزش فنی", callback_data="edu_skill_technical"),
            InlineKeyboardButton("آموزش طراحی", callback_data="edu_skill_design")
        )
        markup.add(InlineKeyboardButton("مطالعه عمومی (دانش)", callback_data="edu_skill_knowledge"))

        # New real degree programs logic
        text += "\n\nدوره‌های تحصیلی (باعث ارتقای شدید مهارت‌ها می‌شوند):"
        for edu_id, edu_info in EDUCATION.items():
            markup.add(InlineKeyboardButton(f"{edu_info['name']} (${edu_info['cost']:,.2f})", callback_data=f"edu_degree_{edu_id}"))

        bot.send_message(message.chat.id, text, reply_markup=markup)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('edu_skill_'))
    def handle_education(call):
        user = get_user(call.from_user.id)
        if not user: return

        skill = call.data.replace('edu_skill_', '')
        valid_skills = ['programming', 'management', 'economy', 'communication', 'technical', 'design', 'knowledge']
        if skill not in valid_skills:
            bot.answer_callback_query(call.id, "مهارت نامعتبر است.", show_alert=True)
            return

        cost = 500
        energy_cost = 20

        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("BEGIN IMMEDIATE")
            from economy import modify_cash
            if not modify_cash(user['id'], -cost, f"Education: {skill}", cur, conn):
                bot.answer_callback_query(call.id, f"هزینه آموزش ${cost} است. پول کافی ندارید.", show_alert=True)
                conn.rollback()
                return

            if user['energy'] < energy_cost:
                bot.answer_callback_query(call.id, "انرژی کافی برای آموزش ندارید!", show_alert=True)
                conn.rollback()
                return

            cur.execute(f"UPDATE skills SET {skill} = {skill} + 5 WHERE user_id = ?", (user['id'],))
            cur.execute("UPDATE users SET energy = energy - ?, xp = xp + 15 WHERE id = ?", (energy_cost, user['id']))
            conn.commit()

        bot.answer_callback_query(call.id, f"شما با موفقیت آموزش دیدید! مهارت شما افزایش یافت (-${cost}, -{energy_cost}⚡).", show_alert=True)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('edu_degree_'))
    def handle_degree(call):
        user = get_user(call.from_user.id)
        if not user: return

        degree_id = call.data.replace('edu_degree_', '')
        if degree_id not in EDUCATION: return

        degree = EDUCATION[degree_id]
        cost = degree['cost']
        energy_cost = 50

        if user['energy'] < energy_cost:
            bot.answer_callback_query(call.id, "برای ثبت‌نام در دوره تحصیلی انرژی زیادی نیاز دارید (حداقل ۵۰٪).", show_alert=True)
            return

        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("BEGIN IMMEDIATE")
            from economy import modify_cash

            # Allow free high school or costed degrees
            if cost > 0:
                if not modify_cash(user['id'], -cost, f"Degree: {degree['name']}", cur, conn):
                    bot.answer_callback_query(call.id, f"هزینه این دوره ${cost:,.2f} است. پول کافی ندارید.", show_alert=True)
                    conn.rollback()
                    return

            # Boost all skills by +10 and specific knowledge by +20
            cur.execute("""UPDATE skills SET
                knowledge = knowledge + 20,
                management = management + 10,
                economy = economy + 10,
                communication = communication + 10
                WHERE user_id = ?""", (user['id'],))
            cur.execute("UPDATE users SET energy = energy - ?, xp = xp + 100 WHERE id = ?", (energy_cost, user['id']))
            conn.commit()

        bot.answer_callback_query(call.id, f"شما با موفقیت دوره {degree['name']} را گذراندید و مهارت‌هایتان جهش پیدا کرد!", show_alert=True)
