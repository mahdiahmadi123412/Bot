from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from database import get_user, get_connection
from data import JOBS, CITIES

def setup(bot):
    @bot.message_handler(func=lambda m: m.text == '💼 کار')
    def jobs_menu(message):
        user = get_user(message.from_user.id)
        if not user: return

        markup = InlineKeyboardMarkup()
        if user['job_id']:
            job = JOBS.get(user['job_id'])
            if not job:
                # Fallback if job was removed
                with get_connection() as conn:
                    conn.cursor().execute("UPDATE users SET job_id = NULL WHERE id = ?", (user['id'],))
                bot.send_message(message.chat.id, "شما در حال حاضر بیکار هستید.", reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("جستجوی کار", callback_data="job_search")))
                return

            text = f"""💼 شغل فعلی: {job['name']}
💰 حقوق (روزانه): ${job['salary']:,.2f}
⏰ ساعت کاری: {job['hours']} ساعت
⚡ انرژی مصرفی: {job['energy_cost']}%
"""
            markup.add(InlineKeyboardButton("کار کردن (روزانه)", callback_data="job_work"))

            # Check for promotions
            promotion = job.get('promotion')
            if promotion and promotion in JOBS:
                markup.add(InlineKeyboardButton("درخواست ارتقا شغلی", callback_data=f"job_promote_{promotion}"))

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
                cur.execute("BEGIN IMMEDIATE")
                from economy import modify_cash

                city_mod = CITIES.get(user['city'], {}).get('salary_mod', 1.0)
                final_salary = job['salary'] * city_mod

                modify_cash(user['id'], final_salary, f"Salary from {job['name']}", cur, conn)

                # Deduct energy, add XP
                cur.execute("UPDATE users SET energy = energy - ?, xp = xp + 20 WHERE id = ?", (job['energy_cost'], user['id']))

                # Check level up
                cur.execute("SELECT xp, level FROM users WHERE id = ?", (user['id'],))
                xp, level = cur.fetchone()
                if xp >= level * 100:
                    cur.execute("UPDATE users SET level = level + 1, xp = 0 WHERE id = ?", (user['id'],))
                    bot.send_message(call.message.chat.id, f"🎉 تبریک! شما به Level {level + 1} ارتقا یافتید!")
                conn.commit()

            bot.answer_callback_query(call.id, f"شما کار کردید و ${final_salary:,.2f} درآمد کسب کردید.", show_alert=True)

            # Rebuild markup
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("کار کردن (روزانه)", callback_data="job_work"))
            promotion = job.get('promotion')
            if promotion and promotion in JOBS:
                markup.add(InlineKeyboardButton("درخواست ارتقا شغلی", callback_data=f"job_promote_{promotion}"))
            markup.add(InlineKeyboardButton("استعفا", callback_data="job_quit"))

            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=markup)

        elif action == "quit":
            with get_connection() as conn:
                cur = conn.cursor()
                cur.execute("UPDATE users SET job_id = NULL WHERE id = ?", (user['id'],))
            bot.answer_callback_query(call.id, "شما از کار خود استعفا دادید.", show_alert=True)
            bot.delete_message(call.message.chat.id, call.message.message_id)

        elif action == "promote":
            target_job_id = call.data.replace('job_promote_', '')
            if target_job_id not in JOBS: return
            target_job = JOBS[target_job_id]

            with get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT * FROM skills WHERE user_id = ?", (user['id'],))
                skills = cur.fetchone()

            reqs = target_job.get('req_skills', {})
            can_promote = True
            for s_name, s_req in reqs.items():
                if skills[s_name] < s_req:
                    can_promote = False
                    bot.answer_callback_query(call.id, f"برای ارتقا به مهارت {s_name} سطح {s_req} نیاز دارید.", show_alert=True)
                    return

            if user['level'] < target_job.get('req_level', 1):
                bot.answer_callback_query(call.id, f"برای این شغل باید Level {target_job['req_level']} باشید.", show_alert=True)
                return

            with get_connection() as conn:
                cur = conn.cursor()
                cur.execute("UPDATE users SET job_id = ? WHERE id = ?", (target_job_id, user['id']))

            bot.answer_callback_query(call.id, f"تبریک! شما به {target_job['name']} ارتقا یافتید!", show_alert=True)
            bot.delete_message(call.message.chat.id, call.message.message_id)

        elif action == "search":
            with get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT * FROM skills WHERE user_id = ?", (user['id'],))
                skills = cur.fetchone()

            # Find eligible jobs (only base jobs, no direct promotions to high level without starting low if we wanted, but we will just check skills and level)
            eligible = []
            for j_id, j_info in JOBS.items():
                reqs = j_info.get('req_skills', {})
                req_lvl = j_info.get('req_level', 1)

                can_apply = True
                if user['level'] < req_lvl:
                    can_apply = False

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

            # Sort by salary descending to show best jobs first
            eligible.sort(key=lambda x: x[1]['salary'], reverse=True)

            # Show top 10 jobs max
            markup = InlineKeyboardMarkup(row_width=1)
            for j_id, j_info in eligible[:10]:
                markup.add(InlineKeyboardButton(f"{j_info['name']} - ${j_info['salary']}", callback_data=f"job_apply_{j_id}"))

            bot.edit_message_text("شغل‌های در دسترس برای شما (10 مورد برتر):", call.message.chat.id, call.message.message_id, reply_markup=markup)

        elif action == "apply":
            job_id = call.data.replace('job_apply_', '')
            if job_id not in JOBS: return

            with get_connection() as conn:
                cur = conn.cursor()
                cur.execute("UPDATE users SET job_id = ? WHERE id = ?", (job_id, user['id']))

            bot.answer_callback_query(call.id, f"شما به عنوان {JOBS[job_id]['name']} استخدام شدید!", show_alert=True)
            bot.delete_message(call.message.chat.id, call.message.message_id)
