from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from .database import get_user, get_connection, get_user_state

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


        markup = InlineKeyboardMarkup()
        if partner:
            markup.add(InlineKeyboardButton("به دنیا آوردن فرزند", callback_data="family_have_child"))
        else:
            markup.add(InlineKeyboardButton("پیشنهاد ازدواج", callback_data="family_propose"))

        bot.send_message(message.chat.id, text, reply_markup=markup)

    @bot.callback_query_handler(func=lambda call: call.data == "social_add_friend")
    def ask_friend_id(call):
        from .database import set_user_state
        set_user_state(call.from_user.id, "SOCIAL_ADD_FRIEND")
        bot.send_message(call.message.chat.id, "لطفا Telegram ID کاربری که می‌خواهید با او دوست شوید را بفرستید:")
        bot.answer_callback_query(call.id)

    @bot.message_handler(func=lambda m: get_user_state(m.from_user.id)[0] == "SOCIAL_ADD_FRIEND")
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
                bot.send_message(message.chat.id, "شما قبلاً با این شخص دوست هستید یا درخواست داده‌اید.")
            else:
                markup = InlineKeyboardMarkup()
                markup.add(
                    InlineKeyboardButton("پذیرفتن", callback_data=f"social_accept_friend_{user['id']}"),
                    InlineKeyboardButton("رد کردن", callback_data=f"social_reject_friend_{user['id']}")
                )
                try:
                    bot.send_message(target_user['tg_id'], f"👥 کاربر {user['first_name']} به شما درخواست دوستی داده است.", reply_markup=markup)
                    bot.send_message(message.chat.id, f"درخواست دوستی برای {target_user['first_name']} ارسال شد.")
                except Exception:
                    bot.send_message(message.chat.id, "خطا در ارسال پیام به این کاربر.")

        set_user_state(tg_id, "NONE")

    @bot.callback_query_handler(func=lambda call: call.data.startswith('social_accept_friend_'))
    def accept_friend(call):
        from .database import get_user
        target_user_id = int(call.data.replace('social_accept_friend_', ''))
        user = get_user(call.from_user.id)

        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("INSERT INTO relationships (user_id_1, user_id_2, relationship_type, level) VALUES (?, ?, 'friend', 10)", (user['id'], target_user_id))
            cur.execute("INSERT INTO relationships (user_id_1, user_id_2, relationship_type, level) VALUES (?, ?, 'friend', 10)", (target_user_id, user['id']))

        bot.edit_message_text("شما درخواست دوستی را پذیرفتید.", call.message.chat.id, call.message.message_id)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('social_reject_friend_'))
    def reject_friend(call):
        bot.edit_message_text("شما درخواست دوستی را رد کردید.", call.message.chat.id, call.message.message_id)

    @bot.callback_query_handler(func=lambda call: call.data == "family_propose")
    def family_propose(call):
        from .database import set_user_state
        set_user_state(call.from_user.id, "FAMILY_PROPOSE")
        bot.send_message(call.message.chat.id, "برای ازدواج، باید Telegram ID فرد مورد نظر را وارد کنید:")
        bot.answer_callback_query(call.id)

    @bot.message_handler(func=lambda m: get_user_state(m.from_user.id)[0] == "FAMILY_PROPOSE")
    def process_propose(message):
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
            bot.send_message(message.chat.id, "این کاربر پیدا نشد.")
            set_user_state(tg_id, "NONE")
            return

        if target_user['married_to'] or user['married_to']:
            bot.send_message(message.chat.id, "یکی از شما در حال حاضر متاهل هستید!")
            set_user_state(tg_id, "NONE")
            return

        with get_connection() as conn:
            cur = conn.cursor()
            markup = InlineKeyboardMarkup()
            markup.add(
                InlineKeyboardButton("بله 💍", callback_data=f"family_accept_propose_{user['id']}"),
                InlineKeyboardButton("خیر 💔", callback_data=f"family_reject_propose_{user['id']}")
            )
            try:
                bot.send_message(target_user['tg_id'], f"💍 کاربر {user['first_name']} به شما پیشنهاد ازدواج داده است!", reply_markup=markup)
                bot.send_message(message.chat.id, f"پیشنهاد ازدواج برای {target_user['first_name']} ارسال شد.")
            except Exception:
                bot.send_message(message.chat.id, "خطا در ارسال پیام به این کاربر.")

        set_user_state(tg_id, "NONE")

    @bot.callback_query_handler(func=lambda call: call.data.startswith('family_accept_propose_'))
    def accept_propose(call):
        from .database import get_user
        target_user_id = int(call.data.replace('family_accept_propose_', ''))
        user = get_user(call.from_user.id)

        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("UPDATE users SET married_to = ? WHERE id = ?", (target_user_id, user['id']))
            cur.execute("UPDATE users SET married_to = ? WHERE id = ?", (user['id'], target_user_id))

        bot.edit_message_text("تبریک! شما ازدواج کردید 💍", call.message.chat.id, call.message.message_id)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('family_reject_propose_'))
    def reject_propose(call):
        bot.edit_message_text("شما پیشنهاد ازدواج را رد کردید.", call.message.chat.id, call.message.message_id)

    @bot.callback_query_handler(func=lambda call: call.data == "family_have_child")
    def family_have_child(call):
        from .database import get_user, set_user_state
        tg_id = call.from_user.id
        user = get_user(tg_id)

        if not user['married_to']:
            bot.answer_callback_query(call.id, "شما مجرد هستید!", show_alert=True)
            return

        set_user_state(tg_id, "FAMILY_CHILD_NAME")
        bot.send_message(call.message.chat.id, "اسم فرزند جدید خود را بنویسید 👶:")
        bot.answer_callback_query(call.id)

    @bot.message_handler(func=lambda m: get_user_state(m.from_user.id)[0] == "FAMILY_CHILD_NAME")
    def process_child_name(message):
        from .database import get_user, set_user_state
        tg_id = message.from_user.id
        user = get_user(tg_id)
        child_name = message.text.strip()

        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("INSERT INTO children (parent_id, name, age) VALUES (?, ?, 0)", (user['id'], child_name))
            bot.send_message(message.chat.id, f"تبریک! فرزند شما {child_name} به دنیا آمد!")
        set_user_state(tg_id, "NONE")
