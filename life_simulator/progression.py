from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from database import get_user, get_connection

def setup(bot):
    @bot.message_handler(func=lambda m: m.text == '🎯 مأموریت‌ها')
    def missions_menu(message):
        user = get_user(message.from_user.id)
        if not user: return

        # We can implement a dynamic mission system here later via DB
        # For now, it stays as placeholder text per original code
        text = """🎯 مأموریت‌های روزانه:
1️⃣ ۲ ساعت کار کن (جایزه: 100$)
2️⃣ یک غذا بخور (جایزه: 50$)
3️⃣ ورزش کن (جایزه: 20 XP)

این بخش با تکمیل اکشن‌ها خودکار بررسی می‌شود."""
        bot.send_message(message.chat.id, text)

    @bot.message_handler(func=lambda m: m.text == '🏆 دستاوردها')
    def achievements_menu(message):
        user = get_user(message.from_user.id)
        if not user: return

        achievements = []
        if user['job_id']: achievements.append("🏆 اولین شغل")
        if user['cash'] >= 1000000: achievements.append("🏆 اولین میلیون")

        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM houses WHERE user_id = ?", (user['id'],))
            h_c = cur.fetchone()[0]
            if h_c > 0: achievements.append("🏆 خرید اولین خانه")

            cur.execute("SELECT COUNT(*) FROM businesses WHERE owner_id = ?", (user['id'],))
            b_c = cur.fetchone()[0]
            if b_c > 0: achievements.append("🏆 تأسیس شرکت")

        text = "🏆 دستاوردهای شما:\n\n"
        if not achievements:
            text += "شما هنوز دستاوردی ندارید."
        else:
            for a in achievements:
                text += f"{a}\n"

        bot.send_message(message.chat.id, text)

    @bot.message_handler(func=lambda m: m.text == '🥇 رتبه‌بندی')
    def leaderboard_menu(message):
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT first_name, last_name, level, cash FROM users ORDER BY level DESC, cash DESC LIMIT 10")
            leaders = cur.fetchall()

        text = "🥇 برترین بازیکنان (Level / Cash):\n\n"
        for i, l in enumerate(leaders, 1):
            text += f"{i}. {l['first_name']} {l['last_name']} - Lvl: {l['level']} - ${l['cash']:,.2f}\n"

        bot.send_message(message.chat.id, text)

    @bot.message_handler(func=lambda m: m.text == '⚙️ تنظیمات')
    def settings_menu(message):
        user = get_user(message.from_user.id)
        if not user: return

        text = "⚙️ تنظیمات حساب کاربری\n\nدر اینجا می‌توانید مشخصات خود را ریست کنید."
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("شروع زندگی جدید (Prestige)", callback_data="settings_prestige"))
        bot.send_message(message.chat.id, text, reply_markup=markup)

    @bot.callback_query_handler(func=lambda call: call.data == 'settings_prestige')
    def do_prestige(call):
        user = get_user(call.from_user.id)
        if not user: return

        if user['level'] < 50:
            bot.answer_callback_query(call.id, "برای شروع زندگی جدید باید حداقل Level 50 باشید!", show_alert=True)
            return

        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("BEGIN IMMEDIATE")

            # Reset core stats but KEEP marriages and children (Family is persistent)
            cur.execute('''
                UPDATE users SET
                    cash = 1000,
                    level = 1,
                    xp = 0,
                    prestige = prestige + 1,
                    job_id = NULL
                WHERE id = ?
            ''', (user['id'],))

            # Wipe properties and businesses to simulate starting over materially
            cur.execute("DELETE FROM inventory WHERE user_id = ?", (user['id'],))
            cur.execute("DELETE FROM houses WHERE user_id = ?", (user['id'],))
            cur.execute("DELETE FROM vehicles WHERE user_id = ?", (user['id'],))
            cur.execute("DELETE FROM businesses WHERE owner_id = ?", (user['id'],))

            # Note: Skills, Friends, Family, Credit Score persist across prestige.
            conn.commit()

        bot.answer_callback_query(call.id, "تبریک! شما زندگی جدیدی را با یک امتیاز Prestige شروع کردید!", show_alert=True)
