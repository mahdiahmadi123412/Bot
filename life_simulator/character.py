from .database import get_user, create_user, set_user_state, get_connection, get_user_state
from .ui import get_main_menu, get_cancel_markup
from .data import CITIES
import json

def setup(bot):
    @bot.message_handler(commands=['register'])
    def register_start(message):
        tg_id = message.from_user.id
        user = get_user(tg_id)
        if user and user['first_name']:
            bot.send_message(message.chat.id, "شما قبلاً ثبت‌نام کرده‌اید!", reply_markup=get_main_menu())
            return

        create_user(tg_id)
        set_user_state(tg_id, "REGISTER_FIRST_NAME")
        bot.send_message(message.chat.id, "لطفاً نام خود را وارد کنید:", reply_markup=get_cancel_markup())

    @bot.message_handler(func=lambda m: get_user_state(m.from_user.id)[0] == "REGISTER_FIRST_NAME")
    def register_first_name(message):
        tg_id = message.from_user.id
        name = message.text.strip()
        set_user_state(tg_id, "REGISTER_LAST_NAME", {"first_name": name})
        bot.send_message(message.chat.id, f"نام: {name}\nحالا نام خانوادگی خود را وارد کنید:")

    @bot.message_handler(func=lambda m: get_user_state(m.from_user.id)[0] == "REGISTER_LAST_NAME")
    def register_last_name(message):
        tg_id = message.from_user.id
        state, data = get_user_state(tg_id)
        last_name = message.text.strip()
        data['last_name'] = last_name
        set_user_state(tg_id, "REGISTER_GENDER", data)
        bot.send_message(message.chat.id, "جنسیت خود را بنویسید (مرد/زن):")

    @bot.message_handler(func=lambda m: get_user_state(m.from_user.id)[0] == "REGISTER_GENDER")
    def register_gender(message):
        tg_id = message.from_user.id
        state, data = get_user_state(tg_id)
        gender = message.text.strip()
        data['gender'] = gender

        city_names = ", ".join([v['name'] for k, v in CITIES.items()])
        set_user_state(tg_id, "REGISTER_CITY", data)
        bot.send_message(message.chat.id, f"شهر خود را از بین شهرهای زیر انتخاب کنید و بنویسید:\n{city_names}")

    @bot.message_handler(func=lambda m: get_user_state(m.from_user.id)[0] == "REGISTER_CITY")
    def register_city(message):
        tg_id = message.from_user.id
        state, data = get_user_state(tg_id)
        city_input = message.text.strip()

        selected_city_id = None
        for cid, cinfo in CITIES.items():
            if cinfo['name'] == city_input:
                selected_city_id = cid
                break

        if not selected_city_id:
            bot.send_message(message.chat.id, "شهر نامعتبر است. لطفاً دقیق بنویسید.")
            return

        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                UPDATE users
                SET first_name = ?, last_name = ?, gender = ?, city = ?, state = 'NONE', state_data = '{}'
                WHERE tg_id = ?
            """, (data['first_name'], data['last_name'], data['gender'], selected_city_id, tg_id))

        bot.send_message(message.chat.id, "ثبت‌نام شما با موفقیت انجام شد! 🎉", reply_markup=get_main_menu())

    @bot.message_handler(func=lambda m: m.text == '🏠 زندگی من')
    def my_life(message):
        tg_id = message.from_user.id
        user = get_user(tg_id)
        if not user or not user['first_name']:
            bot.send_message(message.chat.id, "ابتدا با /register ثبت نام کنید.")
            return

        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM bank_accounts WHERE user_id = ?", (user['id'],))
            bank = cur.fetchone()

            cur.execute("SELECT * FROM skills WHERE user_id = ?", (user['id'],))
            skills = cur.fetchone()

        from .data import JOBS
        job_name = JOBS.get(user['job_id'], {}).get('name', 'بیکار') if user['job_id'] else 'بیکار'
        city_name = CITIES.get(user['city'], {}).get('name', 'نامشخص') if user['city'] else 'نامشخص'

        text = f"""👤 {user['first_name']} {user['last_name']}
🎂 سن: {user['age']}
🏙 شهر: {city_name}
💼 شغل: {job_name}
⭐ Level: {user['level']} (XP: {user['xp']})

💰 نقد: ${user['cash']:,.2f}
🏦 بانک: ${bank['balance']:,.2f}
💳 اعتبار: {user['credit_score']}

❤️ سلامت: {user['health']}%
😊 شادی: {user['happiness']}%
⚡ انرژی: {user['energy']}%
🍔 گرسنگی: {user['hunger']}%
💧 تشنگی: {user['thirst']}%

🧠 مهارت‌ها:
💻 برنامه‌نویسی: {skills['programming']} | 📊 مدیریت: {skills['management']}
💰 اقتصاد: {skills['economy']} | 🗣 ارتباطات: {skills['communication']}
🔧 فنی: {skills['technical']} | 🎨 طراحی: {skills['design']}
📚 دانش: {skills['knowledge']}
"""
        bot.send_message(message.chat.id, text)
