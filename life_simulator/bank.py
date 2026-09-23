from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from .database import get_user, get_connection, set_user_state, get_user_state
from .economy import modify_cash

def setup(bot):
    @bot.message_handler(func=lambda m: m.text == '🏦 بانک')
    def bank_menu(message):
        user = get_user(message.from_user.id)
        if not user: return

        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM bank_accounts WHERE user_id = ?", (user['id'],))
            bank = cur.fetchone()

        max_loan = (user['credit_score'] / 850) * 50000

        text = f"""🏦 بانک مرکزی
موجودی: ${bank['balance']:,.2f}
وام فعال: ${bank['loan_amount']:,.2f}

سقف وام مجاز شما بر اساس اعتبار ({user['credit_score']}): ${max_loan:,.2f}
"""
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("واریز به بانک", callback_data="bank_deposit"),
            InlineKeyboardButton("برداشت از بانک", callback_data="bank_withdraw")
        )
        markup.add(
            InlineKeyboardButton("درخواست وام", callback_data="bank_loan"),
            InlineKeyboardButton("پرداخت اقساط", callback_data="bank_pay")
        )
        bot.send_message(message.chat.id, text, reply_markup=markup)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('bank_'))
    def handle_bank_actions(call):
        tg_id = call.from_user.id
        user = get_user(tg_id)
        if not user: return

        action = call.data.split('_')[1]

        if action == "deposit":
            set_user_state(tg_id, "BANK_DEPOSIT")
            bot.send_message(call.message.chat.id, "مبلغی که می‌خواهید به بانک واریز کنید را وارد کنید:")

        elif action == "withdraw":
            set_user_state(tg_id, "BANK_WITHDRAW")
            bot.send_message(call.message.chat.id, "مبلغی که می‌خواهید از بانک برداشت کنید را وارد کنید:")

        elif action == "loan":
            max_loan = (user['credit_score'] / 850) * 50000
            set_user_state(tg_id, "BANK_LOAN")
            bot.send_message(call.message.chat.id, f"سقف وام: ${max_loan:,.2f}\nمبلغ وام درخواستی را وارد کنید:")

        elif action == "pay":
            with get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT loan_amount FROM bank_accounts WHERE user_id = ?", (user['id'],))
                loan = cur.fetchone()[0]
            if loan <= 0:
                bot.send_message(call.message.chat.id, "شما بدهی بانکی ندارید.")
            else:
                set_user_state(tg_id, "BANK_PAY_LOAN")
                bot.send_message(call.message.chat.id, f"کل بدهی: ${loan:,.2f}\nمبلغ پرداختی را وارد کنید:")

        bot.answer_callback_query(call.id)

    @bot.message_handler(func=lambda m: get_user_state(m.from_user.id)[0] in ["BANK_DEPOSIT", "BANK_WITHDRAW", "BANK_LOAN", "BANK_PAY_LOAN"])
    def process_bank_input(message):
        tg_id = message.from_user.id
        user = get_user(tg_id)
        state, _ = get_user_state(tg_id)


        import math
        try:
            amount = float(message.text)
            if amount <= 0 or math.isnan(amount): raise ValueError
        except:

            bot.send_message(message.chat.id, "مبلغ نامعتبر است.")
            set_user_state(tg_id, "NONE")
            return

        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM bank_accounts WHERE user_id = ?", (user['id'],))
            bank = cur.fetchone()

            if state == "BANK_DEPOSIT":
                cur.execute("BEGIN IMMEDIATE")
                from .economy import modify_cash
                if not modify_cash(user['id'], -amount, "Bank Deposit", cur, conn):
                    bot.send_message(message.chat.id, "موجودی نقد کافی نیست.")
                    conn.rollback()
                else:
                    cur.execute("UPDATE bank_accounts SET balance = balance + ? WHERE user_id = ?", (amount, user['id']))
                    bot.send_message(message.chat.id, f"مبلغ ${amount:,.2f} به حساب بانکی واریز شد.")
                    conn.commit()

            elif state == "BANK_WITHDRAW":
                if bank['balance'] < amount:
                    bot.send_message(message.chat.id, "موجودی بانک کافی نیست.")
                else:
                    cur.execute("BEGIN IMMEDIATE")
                    from .economy import modify_cash
                    modify_cash(user['id'], amount, "Bank Withdrawal", cur, conn)
                    cur.execute("UPDATE bank_accounts SET balance = balance - ? WHERE user_id = ?", (amount, user['id']))
                    bot.send_message(message.chat.id, f"مبلغ ${amount:,.2f} از حساب بانکی برداشت شد.")
                    conn.commit()

            elif state == "BANK_LOAN":
                max_loan = (user['credit_score'] / 850) * 50000
                if amount > max_loan:
                    bot.send_message(message.chat.id, "مبلغ درخواستی بیشتر از سقف مجاز است.")
                else:
                    installment = amount * 1.1 / 12  # 10% interest over 12 months
                    cur.execute("UPDATE bank_accounts SET loan_amount = loan_amount + ?, loan_installment = loan_installment + ? WHERE user_id = ?", (amount * 1.1, installment, user['id']))
                    cur.execute("UPDATE bank_accounts SET balance = balance + ? WHERE user_id = ?", (amount, user['id']))
                    bot.send_message(message.chat.id, f"وام به مبلغ ${amount:,.2f} با موفقیت دریافت شد.\nقسط ماهانه: ${installment:,.2f}")

            elif state == "BANK_PAY_LOAN":
                if bank['loan_amount'] < amount:
                    amount = bank['loan_amount']

                if bank['balance'] < amount:
                    bot.send_message(message.chat.id, "موجودی بانک برای پرداخت این مبلغ کافی نیست.")
                else:
                    cur.execute("UPDATE bank_accounts SET balance = balance - ?, loan_amount = loan_amount - ? WHERE user_id = ?", (amount, amount, user['id']))
                    # if paid off completely, remove installment
                    cur.execute("UPDATE bank_accounts SET loan_installment = 0 WHERE loan_amount <= 0 AND user_id = ?", (user['id'],))
                    # Increase credit score slightly
                    cur.execute("UPDATE users SET credit_score = MIN(850, credit_score + 5) WHERE id = ?", (user['id'],))
                    bot.send_message(message.chat.id, f"مبلغ ${amount:,.2f} بابت وام پرداخت شد و اعتبار مالی شما افزایش یافت.")

        set_user_state(tg_id, "NONE")
