from database import get_user, get_connection
from ui import get_main_menu

def setup(bot):
    @bot.message_handler(func=lambda m: m.text == '💰 اقتصاد')
    def economy_menu(message):
        user = get_user(message.from_user.id)
        if not user: return

        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM bank_accounts WHERE user_id = ?", (user['id'],))
            bank = cur.fetchone()

            # Simple global economy view
            cur.execute("SELECT * FROM economy_history ORDER BY id DESC LIMIT 1")
            eco = cur.fetchone()

            inflation = eco['inflation_rate'] if eco else 0

            text = f"""📊 وضعیت اقتصادی شما
نقدینگی: ${user['cash']:,.2f}
موجودی بانک: ${bank['balance']:,.2f}
اعتبار مالی (Credit Score): {user['credit_score']}/850

بدهی وام: ${bank['loan_amount']:,.2f}
قسط ماهانه: ${bank['loan_installment']:,.2f}

🌍 اقتصاد جهانی:
تورم: {inflation}%
"""
            bot.send_message(message.chat.id, text)

    def log_transaction(user_id, amount, tx_type, description):
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("INSERT INTO transactions (user_id, amount, type, description) VALUES (?, ?, ?, ?)",
                        (user_id, amount, tx_type, description))

def modify_cash(user_id, amount, description="", cur=None, conn=None):
    if cur is None or conn is None:
        with get_connection() as local_conn:
            local_cur = local_conn.cursor()
            local_cur.execute("BEGIN IMMEDIATE")
            try:
                local_cur.execute("SELECT cash FROM users WHERE id = ?", (user_id,))
                row = local_cur.fetchone()
                if not row or row['cash'] + amount < 0:
                    raise ValueError("Insufficient funds")
                local_cur.execute("UPDATE users SET cash = cash + ? WHERE id = ?", (amount, user_id))
                local_cur.execute("INSERT INTO transactions (user_id, amount, type, description) VALUES (?, ?, ?, ?)",
                            (user_id, amount, 'CASH', description))
                local_conn.commit()
                return True
            except Exception:
                local_conn.rollback()
                return False
    else:
        # Part of an existing transaction
        cur.execute("SELECT cash FROM users WHERE id = ?", (user_id,))
        row = cur.fetchone()
        if not row or row['cash'] + amount < 0:
            return False
        cur.execute("UPDATE users SET cash = cash + ? WHERE id = ?", (amount, user_id))
        cur.execute("INSERT INTO transactions (user_id, amount, type, description) VALUES (?, ?, ?, ?)",
                    (user_id, amount, 'CASH', description))
        return True