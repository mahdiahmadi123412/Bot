import re

with open('newfile.py', 'r') as f:
    content = f.read()

# 1. Fix get_connection() double commit issue
# In upgrade_building_transaction
old_upgrade = """        cur.execute("BEGIN IMMEDIATE")
        try:
            cur.execute("SELECT coins FROM users WHERE user_id = ?", (user_id,))
            user = cur.fetchone()
            if not user or user['coins'] < cost:
                conn.rollback()
                return False

            # Deduct coins and update building in same transaction
            cur.execute("UPDATE users SET coins = coins - ? WHERE user_id = ?", (cost, user_id))
            cur.execute(f"UPDATE buildings SET {building_column} = ? WHERE user_id = ?", (new_level, user_id))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            logging.error("Transaction failed", exc_info=True)
            return False"""

new_upgrade = """        cur.execute("BEGIN IMMEDIATE")
        try:
            cur.execute("SELECT coins FROM users WHERE user_id = ?", (user_id,))
            user = cur.fetchone()
            if not user or user['coins'] < cost:
                # Instead of committing or rolling back here, we can just raise an exception
                # or just use the connection's rollback and NOT return yet, but get_connection
                # context manager catches exceptions and rolls back.
                # However, if we return False, the context manager yields normally and calls commit().
                # That's fine if we did nothing, but if we did BEGIN IMMEDIATE, a commit is fine too.
                # Let's just return False, the context manager will commit the BEGIN IMMEDIATE which does nothing.
                return False

            # Deduct coins and update building in same transaction
            cur.execute("UPDATE users SET coins = coins - ? WHERE user_id = ?", (cost, user_id))
            cur.execute(f"UPDATE buildings SET {building_column} = ? WHERE user_id = ?", (new_level, user_id))
            # DO NOT conn.commit(), let get_connection do it
            return True
        except Exception as e:
            # Let get_connection handle rollback
            raise e"""

content = content.replace(old_upgrade, new_upgrade)

# In process_alliance_withdraw
old_withdraw = """            cur.execute("BEGIN IMMEDIATE")
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

new_withdraw = """            cur.execute("BEGIN IMMEDIATE")
            try:
                cur.execute(f"SELECT {treasury_field} FROM alliances WHERE id = ?", (alliance['id'],))
                treasury = cur.fetchone()
                if not treasury or treasury[0] < amount:
                    bot.send_message(message.chat.id, "❌ خزانه اتحاد این مقدار منبع را ندارد.")
                    return

                cur.execute(f"UPDATE alliances SET {treasury_field} = {treasury_field} - ? WHERE id = ?", (amount, alliance['id']))
                cur.execute(f"UPDATE users SET {resource} = {resource} + ? WHERE user_id = ?", (amount, user_id))
                # Commit handled by context manager
                bot.send_message(message.chat.id, f"✅ مقدار {format_number(amount)} {resource} از خزانه برداشت شد.", reply_markup=main_menu(user_id))
            except Exception as e:
                logging.error("Exception occurred", exc_info=True)
                bot.send_message(message.chat.id, "❌ خطا در انجام تراکنش.")
                raise e"""

content = content.replace(old_withdraw, new_withdraw)


# 2. Fix background jobs deadlock

old_bg = """            with get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT * FROM pending_battles WHERE execute_at <= ?", (current_time,))
                pending = cur.fetchall()
                for pb in pending:
                    pb = dict(pb)
                    try:
                        if pb['battle_type'] == 'pvp':
                            execute_delayed_pvp(pb['attacker_id'], pb['defender_id'], pb['chat_id'])
                        elif pb['battle_type'] == 'alliance_war':
                            execute_alliance_war(pb['attacker_id'], pb['defender_id'], pb['chat_id'], int(pb['extra_data']))
                    except Exception as e:
                        logging.error("Failed to execute pending battle", exc_info=True)
                    # Delete after execution
                    cur.execute("DELETE FROM pending_battles WHERE id = ?", (pb['id'],))"""


new_bg = """            # Fetch pending battles first
            pending_to_execute = []
            with get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT * FROM pending_battles WHERE execute_at <= ?", (current_time,))
                pending_to_execute = [dict(r) for r in cur.fetchall()]

            # Execute battles OUTSIDE the database context manager to prevent deadlocks
            for pb in pending_to_execute:
                try:
                    if pb['battle_type'] == 'pvp':
                        execute_delayed_pvp(pb['attacker_id'], pb['defender_id'], pb['chat_id'])
                    elif pb['battle_type'] == 'alliance_war':
                        execute_alliance_war(pb['attacker_id'], pb['defender_id'], pb['chat_id'], int(pb['extra_data']))
                except Exception as e:
                    logging.error("Failed to execute pending battle", exc_info=True)

                # Delete after execution in a separate transaction
                with get_connection() as conn:
                    conn.execute("DELETE FROM pending_battles WHERE id = ?", (pb['id'],))"""

content = content.replace(old_bg, new_bg)

with open('newfile.py', 'w') as f:
    f.write(content)
