with open('newfile.py', 'r') as f:
    content = f.read()

bg_old = """            spawn_castles(3)
            if not get_active_world_boss():
                spawn_world_boss(1)"""

bg_new = """            # Only spawn castles occasionally, not every 5 seconds!
            with get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT created_at FROM castles ORDER BY id DESC LIMIT 1")
                row = cur.fetchone()
                if not row or (int(time.time()) - row['created_at']) > (CASTLE_SPAWN_INTERVAL_HOURS * 3600):
                    spawn_castles(3)

            if not get_active_world_boss():
                spawn_world_boss(1)"""

content = content.replace(bg_old, bg_new)

with open('newfile.py', 'w') as f:
    f.write(content)
