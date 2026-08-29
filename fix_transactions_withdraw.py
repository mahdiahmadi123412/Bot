import re

with open('newfile.py', 'r') as f:
    content = f.read()

# Make process_alliance_withdraw safe
old_withdraw = """        # ۱. کسر از خزانه در یک تراکنش مستقل
        with get_connection() as conn:
            conn.execute(f"UPDATE alliances SET {treasury_field} = {treasury_field} - ? WHERE id = ?", (amount, alliance['id']))

        # ۲. آپدیت کردن منابع کاربر بیرون از بلاک بالا برای جلوگیری از Deadlock
        user = get_user(user_id)
        if user:
            update_user(user_id, **{resource: user[resource] + amount})
            bot.send_message(message.chat.id, f"✅ مقدار {format_number(amount)} {resource} از خزانه برداشت شد.", reply_markup=main_menu(user_id))"""

new_withdraw = """        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("BEGIN IMMEDIATE")
            try:
                cur.execute(f"SELECT {treasury_field} FROM alliances WHERE id = ?", (alliance['id'],))
                treasury = cur.fetchone()
                if not treasury or treasury[0] < amount:
                    conn.rollback()
                    bot.send_message(message.chat.id, "❌ خزانه اتحاد این مقدار منبع را ندارد.")
                    return

                cur.execute(f"UPDATE alliances SET {treasury_field} = {treasury_field} - ? WHERE id = ?", (amount, alliance['id']))
                cur.execute(f"UPDATE users SET {resource} = {resource} + ? WHERE user_id = ?", (amount, user_id))
                conn.commit()
                bot.send_message(message.chat.id, f"✅ مقدار {format_number(amount)} {resource} از خزانه برداشت شد.", reply_markup=main_menu(user_id))
            except Exception as e:
                conn.rollback()
                logging.error("Exception occurred", exc_info=True)
                bot.send_message(message.chat.id, "❌ خطا در انجام تراکنش.")"""

content = content.replace(old_withdraw, new_withdraw)

with open('newfile.py', 'w') as f:
    f.write(content)
