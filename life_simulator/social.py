from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from .database import get_user, get_connection

def setup(bot):
    @bot.message_handler(func=lambda m: m.text == '👥 دوستان')
    def friends_menu(message):
        user = get_user(message.from_user.id)
        if not user: return

        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT u.first_name, u.last_name, r.level, r.relationship_type
                FROM relationships r
                JOIN users u ON (r.user_id_2 = u.id)
                WHERE r.user_id_1 = ? AND r.relationship_type = 'friend'
            """, (user['id'],))
            friends = cur.fetchall()

        text = "👥 لیست دوستان شما:\n\n"
        if not friends:
            text += "شما هیچ دوستی ندارید! سعی کنید با دیگر بازیکنان ارتباط برقرار کنید."
        else:
            for f in friends:
                text += f"▪️ {f['first_name']} {f['last_name']} - صمیمیت: {f['level']}/100\n"


        bot.send_message(message.chat.id, text, reply_markup=InlineKeyboardMarkup().add(
            InlineKeyboardButton("اضافه کردن دوست با ID", callback_data="social_add_friend")
        ))

    @bot.message_handler(func=lambda m: m.text == '❤️ خانواده')
    def family_menu(message):

        user = get_user(message.from_user.id)
        if not user: return

        with get_connection() as conn:
            cur = conn.cursor()
            partner = None
            if user['married_to']:
                cur.execute("SELECT first_name, last_name FROM users WHERE id = ?", (user['married_to'],))
                partner = cur.fetchone()

            cur.execute("SELECT * FROM children WHERE parent_id = ?", (user['id'],))
            children = cur.fetchall()

        text = "❤️ خانواده شما:\n\n"
        if partner:
            text += f"همسر: {partner['first_name']} {partner['last_name']}\n\n"
        else:
            text += "وضعیت تأهل: مجرد\n\n"

        text += "فرزندان:\n"
        if not children:
            text += "بدون فرزند"
        else:
            for c in children:
                text += f"👶 {c['name']} (سن: {c['age']}, سلامت: {c['health']}%)\n"


        bot.send_message(message.chat.id, text)

    @bot.callback_query_handler(func=lambda call: call.data == "social_add_friend")
    def ask_friend_id(call):
        from .database import set_user_state
        set_user_state(call.from_user.id, "SOCIAL_ADD_FRIEND")
        bot.send_message(call.message.chat.id, "لطفا Telegram ID کاربری که می‌خواهید با او دوست شوید را بفرستید:")
        bot.answer_callback_query(call.id)

    @bot.message_handler(func=lambda m: __import__('life_simulator.database', fromlist=['get_user_state']).get_user_state(m.from_user.id)[0] == "SOCIAL_ADD_FRIEND")
    def process_add_friend(message):
        from .database import get_user, set_user_state
        tg_id = message.from_user.id
        user = get_user(tg_id)

        try:
            target_tg_id = int(message.text)
        except:
            bot.send_message(message.chat.id, "ID نامعتبر است.")
            set_user_state(tg_id, "NONE")
            return

        target_user = get_user(target_tg_id)
        if not target_user:
            bot.send_message(message.chat.id, "این کاربر در ربات ثبت‌نام نکرده است.")
            set_user_state(tg_id, "NONE")
            return

        if target_user['id'] == user['id']:
            bot.send_message(message.chat.id, "شما نمی‌توانید با خودتان دوست شوید!")
            set_user_state(tg_id, "NONE")
            return

        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM relationships WHERE user_id_1 = ? AND user_id_2 = ?", (user['id'], target_user['id']))
            if cur.fetchone():
                bot.send_message(message.chat.id, "شما قبلاً با این شخص دوست هستید.")
            else:
                cur.execute("INSERT INTO relationships (user_id_1, user_id_2, relationship_type, level) VALUES (?, ?, 'friend', 10)", (user['id'], target_user['id']))
                cur.execute("INSERT INTO relationships (user_id_1, user_id_2, relationship_type, level) VALUES (?, ?, 'friend', 10)", (target_user['id'], user['id']))
                bot.send_message(message.chat.id, f"شما با موفقیت با {target_user['first_name']} دوست شدید!")

        set_user_state(tg_id, "NONE")
