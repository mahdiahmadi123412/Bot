import re

with open('newfile.py', 'r') as f:
    content = f.read()

# Add upgrade_building_transaction
new_func = """def upgrade_building_transaction(user_id: int, building_column: str, cost: int, new_level: int) -> bool:
    with get_connection() as conn:
        cur = conn.cursor()
        # BEGIN IMMEDIATE ensures we acquire a lock before checking balances, preventing race conditions
        cur.execute("BEGIN IMMEDIATE")
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
            return False
"""

# We insert it after `update_building` function
content = content.replace("def get_army_units(user_id: int)", new_func + "\ndef get_army_units(user_id: int)")

# Replace logic in upgrade handler
old_handler = """            if user['coins'] < cost:
                bot.answer_callback_query(
                    call.id,
                    f"❌ سکه کافی نیست!\\n💰 موجودی: {format_number(user['coins'])}\\n💰 نیاز: {format_number(cost)}",
                    show_alert=True
                )
                return

            new_coins = user['coins'] - cost
            new_level = current_level + 1

            update_user(user_id, coins=new_coins)
            update_building(user_id, column, new_level)
            add_exp(user_id, cost // 2, chat_id)

            bot.answer_callback_query(
                call.id,
                f"✅ {BUILDING_NAMES[building]} ارتقا یافت!\\n📊 سطح جدید: {new_level}\\n💰 هزینه: {format_number(cost)} سکه",
                show_alert=True
            )"""

new_handler = """            new_level = current_level + 1
            if upgrade_building_transaction(user_id, column, cost, new_level):
                add_exp(user_id, cost // 2, chat_id)
                bot.answer_callback_query(
                    call.id,
                    f"✅ {BUILDING_NAMES[building]} ارتقا یافت!\\n📊 سطح جدید: {new_level}\\n💰 هزینه: {format_number(cost)} سکه",
                    show_alert=True
                )
            else:
                bot.answer_callback_query(
                    call.id,
                    f"❌ ارتقا ناموفق بود! احتمالاً سکه کافی ندارید.\\n💰 نیاز: {format_number(cost)}",
                    show_alert=True
                )"""

content = content.replace(old_handler, new_handler)

with open('newfile.py', 'w') as f:
    f.write(content)
