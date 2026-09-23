import threading
import time
import logging
from .config import BACKGROUND_TICK_RATE, DAILY_TICK_RATE
from .database import get_connection

def needs_decay_tick():
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            # Decay hunger, thirst, energy slightly every 15 mins
            cur.execute("""
                UPDATE users
                SET hunger = MAX(0, hunger - 5),
                    thirst = MAX(0, thirst - 8),
                    energy = MAX(0, energy - 2)
            """)

            # If hunger or thirst is 0, health decays
            cur.execute("""
                UPDATE users
                SET health = MAX(0, health - 5)
                WHERE hunger = 0 OR thirst = 0
            """)
            logging.info("Needs decay tick completed.")
    except Exception as e:
        logging.error(f"Error in needs_decay_tick: {e}")

def daily_economy_tick():
    try:
        with get_connection() as conn:
            cur = conn.cursor()

            # 1. Update Ages (1 day in game = 1 hour IRL)
            cur.execute("UPDATE users SET age_days = age_days + 1")
            # When age_days reaches 365, increase age by 1 year and subtract 365 from age_days
            cur.execute("UPDATE users SET age = age + 1, age_days = age_days - 365 WHERE age_days >= 365")

            # Age children
            cur.execute("UPDATE children SET age = age + 1 WHERE parent_id IN (SELECT id FROM users WHERE age_days = 0)")

            # 2. Business Income & Expenses
            cur.execute("SELECT owner_id, income_rate, expense_rate FROM businesses")
            businesses = cur.fetchall()
            from .economy import modify_cash
            for b in businesses:
                net = b['income_rate'] - b['expense_rate']
                modify_cash(b['owner_id'], net, "Daily Business Net Income", cur, conn)

            # 3. Bank Loan Interest & Deductions
            cur.execute("SELECT user_id, balance, loan_amount, loan_installment FROM bank_accounts WHERE loan_amount > 0 AND loan_installment > 0")
            loans = cur.fetchall()
            for l in loans:
                # deduct installment
                installment = l['loan_installment']
                if l['balance'] >= installment:
                    cur.execute("UPDATE bank_accounts SET balance = balance - ?, loan_amount = loan_amount - ? WHERE user_id = ?", (installment, installment, l['user_id']))
                else:
                    # Penalize credit score
                    cur.execute("UPDATE users SET credit_score = MAX(300, credit_score - 10) WHERE id = ?", (l['user_id'],))

            # Clean up paid loans
            cur.execute("UPDATE bank_accounts SET loan_installment = 0 WHERE loan_amount <= 0")

            logging.info("Daily economy tick completed.")
    except Exception as e:
        logging.error(f"Error in daily_economy_tick: {e}")

def _loop(bot):
    last_needs_tick = time.time()
    last_daily_tick = time.time()

    while True:
        now = time.time()

        if now - last_needs_tick >= BACKGROUND_TICK_RATE:
            needs_decay_tick()
            last_needs_tick = now

        if now - last_daily_tick >= DAILY_TICK_RATE:
            daily_economy_tick()
            last_daily_tick = now

        time.sleep(60) # Sleep 1 minute to prevent CPU hogging

def start_worker(bot):
    t = threading.Thread(target=_loop, args=(bot,), daemon=True)
    t.start()
    logging.info("Background worker started.")
