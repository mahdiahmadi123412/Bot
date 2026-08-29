with open('newfile.py', 'r') as f:
    content = f.read()

# 1. Add pending_battles table
table_sql = """        cur.execute('''
            CREATE TABLE IF NOT EXISTS pending_battles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                battle_type TEXT,
                attacker_id INTEGER,
                defender_id INTEGER,
                chat_id INTEGER,
                execute_at INTEGER,
                extra_data TEXT
            )
        ''')"""

content = content.replace("        cur.execute('''\n            CREATE TABLE IF NOT EXISTS peace_treaties", table_sql + "\n\n        cur.execute('''\n            CREATE TABLE IF NOT EXISTS peace_treaties")

# 2. Fix process_alliance_war to insert into db instead of threading.Timer
timer_old1 = "    timer = threading.Timer(60.0, execute_alliance_war, args=[attacker_alliance['id'], target_alliance['id'], message.chat.id, target_alliance['leader_id']])\n    timer.start()"
timer_new1 = """    execute_at = int(time.time()) + 60
    with get_connection() as conn:
        conn.execute("INSERT INTO pending_battles (battle_type, attacker_id, defender_id, chat_id, execute_at, extra_data) VALUES (?, ?, ?, ?, ?, ?)",
                     ('alliance_war', attacker_alliance['id'], target_alliance['id'], message.chat.id, execute_at, str(target_alliance['leader_id'])))"""

content = content.replace(timer_old1, timer_new1)

# 3. Fix process_pvp_attack to insert into db
timer_old2 = "    timer = threading.Timer(60.0, execute_delayed_pvp, args=[attacker_id, defender_id, message.chat.id])\n    timer.start()"
timer_new2 = """    execute_at = int(time.time()) + 60
    with get_connection() as conn:
        conn.execute("INSERT INTO pending_battles (battle_type, attacker_id, defender_id, chat_id, execute_at) VALUES (?, ?, ?, ?, ?)",
                     ('pvp', attacker_id, defender_id, message.chat.id, execute_at))"""

content = content.replace(timer_old2, timer_new2)

# 4. Add the worker to background_jobs
worker_logic = """
            # Execute pending battles
            current_time = int(time.time())
            with get_connection() as conn:
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
                    cur.execute("DELETE FROM pending_battles WHERE id = ?", (pb['id'],))
"""

content = content.replace("            spawn_castles(3)", worker_logic + "\n            spawn_castles(3)")
content = content.replace("time.sleep(CASTLE_SPAWN_INTERVAL_HOURS * 3600)", "time.sleep(5)")

with open('newfile.py', 'w') as f:
    f.write(content)
