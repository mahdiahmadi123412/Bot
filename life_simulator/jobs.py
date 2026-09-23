from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from .database import get_user, get_connection
from .data import JOBS

def setup(bot):
    @bot.message_handler(func=lambda m: m.text == '💼 کار')
    def jobs_menu(message):
        user = get_user(message.from_user.id)
        if not user: return

        markup = InlineKeyboardMarkup()
        if user['job_id']:
            job = JOBS.get(user['job_id'])
            text = f"""💼 شغل فعلی: {job['name']}
💰 حقوق (روزانه): ${job['salary']:,.2f}
⏰ ساعت کاری: {job['hours']} ساعت
⚡ انرژی مصرفی: {job['energy_cost']}%
"""
            markup.add(InlineKeyboardButton("کار کردن (روزانه)", callback_data="job_work"))
            markup.add(InlineKeyboardButton("استعفا", callback_data="job_quit"))
        else:
            text = "شما در حال حاضر بیکار هستید."
            markup.add(InlineKeyboardButton("جستجوی کار", callback_data="job_search"))

        bot.send_message(message.chat.id, text, reply_markup=markup)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('job_'))
    def handle_jobs(call):
        user = get_user(call.from_user.id)
        if not user: return
        action = call.data.split('_')[1]

        if action == "work":
            if not user['job_id']:
                bot.answer_callback_query(call.id, "شما بیکار هستید!")
                return

            job = JOBS[user['job_id']]
            if user['energy'] < job['energy_cost']:
                bot.answer_callback_query(call.id, "انرژی کافی برای کار ندارید!", show_alert=True)
                return

            with get_connection() as conn:
                cur = conn.cursor()
                # Deduct energy, add cash, add XP
                cur.execute("""
                    UPDATE users SET
                        energy = energy - ?,
                        cash = cash + ?,
                        xp = xp + 20
                    WHERE id = ?
                """, (job['energy_cost'], job['salary'], user['id']))
                # Check level up
                cur.execute("SELECT xp, level FROM users WHERE id = ?", (user['id'],))
                xp, level = cur.fetchone()
                if xp >= level * 100:
                    cur.execute("UPDATE users SET level = level + 1, xp = 0 WHERE id = ?", (user['id'],))
                    bot.send_message(call.message.chat.id, f"🎉 تبریک! شما به Level {level + 1} ارتقا یافتید!")

            bot.answer_callback_query(call.id, f"شما کار کردید و ${job['salary']:,.2f} درآمد کسب کردید.", show_alert=True)
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=InlineKeyboardMarkup().add(
                InlineKeyboardButton("کار کردن (روزانه)", callback_data="job_work"),
                InlineKeyboardButton("استعفا", callback_data="job_quit")
            ))

        elif action == "quit":
            with get_connection() as conn:
                cur = conn.cursor()
                cur.execute("UPDATE users SET job_id = NULL WHERE id = ?", (user['id'],))
            bot.answer_callback_query(call.id, "شما از کار خود استعفا دادید.", show_alert=True)
            bot.delete_message(call.message.chat.id, call.message.message_id)

        elif action == "search":
            with get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT * FROM skills WHERE user_id = ?", (user['id'],))
                skills = cur.fetchone()

            # Find eligible jobs
            eligible = []
            for j_id, j_info in JOBS.items():
                reqs = j_info.get('req_skills', {})
                can_apply = True
                for s_name, s_req in reqs.items():
                    if skills[s_name] < s_req:
                        can_apply = False
                        break
                if can_apply:
                    eligible.append((j_id, j_info))

            if not eligible:
                bot.send_message(call.message.chat.id, "متاسفانه مهارت‌های شما برای هیچ شغلی کافی نیست. باید تحصیل کنید یا مهارت بیاموزید.")
                bot.answer_callback_query(call.id)
                return

            markup = InlineKeyboardMarkup(row_width=1)
            for j_id, j_info in eligible:
                markup.add(InlineKeyboardButton(f"{j_info['name']} - ${j_info['salary']}", callback_data=f"job_apply_{j_id}"))

            bot.edit_message_text("شغل‌های در دسترس برای شما:", call.message.chat.id, call.message.message_id, reply_markup=markup)

        elif action == "apply":
            job_id = call.data.replace('job_apply_', '')
            if job_id not in JOBS: return

            with get_connection() as conn:
                cur = conn.cursor()
                cur.execute("UPDATE users SET job_id = ? WHERE id = ?", (job_id, user['id']))

            bot.answer_callback_query(call.id, f"شما به عنوان {JOBS[job_id]['name']} استخدام شدید!", show_alert=True)
            bot.delete_message(call.message.chat.id, call.message.message_id)
