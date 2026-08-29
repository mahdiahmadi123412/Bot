with open('newfile.py', 'r') as f:
    content = f.read()

# Fix show_leaderboard N+1
leaderboard_old = """        # 3. Top 5 Alliances
        cur.execute("SELECT id, name, level FROM alliances ORDER BY level DESC LIMIT 5")
        top_alliances = cur.fetchall()

        # 4. User's alliance rank
        user_alliance = get_alliance(user_id)
        alliance_rank_text = "شما در هیچ اتحادی نیستید."
        if user_alliance:
            all_id = user_alliance['id']
            # We need to get member counts per alliance for ranking, simpler to just rank by level, then member count if we use a subquery or we rank in python.
            cur.execute("SELECT COUNT(*) + 1 FROM alliances WHERE level > ?", (user_alliance['level'],))
            all_rank = cur.fetchone()[0]
            alliance_rank_text = str(all_rank)

        text = "🏆 <b>رتبه‌بندی سرور</b>\n\n"
        text += "👑 <b>امپراطوری‌های برتر:</b>\n"
        for i, emp in enumerate(top_empires):
            text += f"{i+1}. {emp['empire_name']} (سطح: {emp['level']} | قدرت حمله: {format_number(emp['attack_power'])})\\n"

        text += "\\n👥 <b>اتحادهای برتر:</b>\\n"
        for i, al in enumerate(top_alliances):
            # count members
            cur.execute("SELECT COUNT(*) FROM alliance_members WHERE alliance_id = ?", (al['id'],))
            m_count = cur.fetchone()[0]
            text += f"{i+1}. {al['name']} (سطح: {al['level']} | اعضا: {m_count})\\n"
"""

leaderboard_new = """        # 3. Top 5 Alliances with member count
        cur.execute('''
            SELECT a.id, a.name, a.level, COUNT(am.user_id) as member_count
            FROM alliances a
            LEFT JOIN alliance_members am ON a.id = am.alliance_id
            GROUP BY a.id
            ORDER BY a.level DESC LIMIT 5
        ''')
        top_alliances = cur.fetchall()

        # 4. User's alliance rank
        user_alliance = get_alliance(user_id)
        alliance_rank_text = "شما در هیچ اتحادی نیستید."
        if user_alliance:
            all_id = user_alliance['id']
            cur.execute("SELECT COUNT(*) + 1 FROM alliances WHERE level > ?", (user_alliance['level'],))
            all_rank = cur.fetchone()[0]
            alliance_rank_text = str(all_rank)

        text = "🏆 <b>رتبه‌بندی سرور</b>\\n\\n"
        text += "👑 <b>امپراطوری‌های برتر:</b>\\n"
        for i, emp in enumerate(top_empires):
            text += f"{i+1}. {emp['empire_name']} (سطح: {emp['level']} | قدرت حمله: {format_number(emp['attack_power'])})\\n"

        text += "\\n👥 <b>اتحادهای برتر:</b>\\n"
        for i, al in enumerate(top_alliances):
            text += f"{i+1}. {al['name']} (سطح: {al['level']} | اعضا: {al['member_count']})\\n"
"""
content = content.replace(leaderboard_old, leaderboard_new)

# Fix show_alliance_peace_list N+1
peace_old = """    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT alliance_1_id, alliance_2_id FROM peace_treaties WHERE alliance_1_id = ? OR alliance_2_id = ?", (alliance['id'], alliance['id']))
        treaties = cur.fetchall()

        text = "📜 <b>اتحادهای در صلح</b>\\n\\n"
        if not treaties:
            text += "شما با هیچ اتحادی پیمان صلح ندارید.\\n"
        else:
            for t in treaties:
                other_id = t['alliance_2_id'] if t['alliance_1_id'] == alliance['id'] else t['alliance_1_id']
                cur.execute("SELECT name FROM alliances WHERE id = ?", (other_id,))
                row = cur.fetchone()
                if row:
                    text += f"🕊 {row['name']}\\n"
"""

peace_new = """    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute('''
            SELECT a.name
            FROM peace_treaties pt
            JOIN alliances a ON (a.id = pt.alliance_1_id OR a.id = pt.alliance_2_id)
            WHERE (pt.alliance_1_id = ? OR pt.alliance_2_id = ?) AND a.id != ?
        ''', (alliance['id'], alliance['id'], alliance['id']))
        treaties = cur.fetchall()

        text = "📜 <b>اتحادهای در صلح</b>\\n\\n"
        if not treaties:
            text += "شما با هیچ اتحادی پیمان صلح ندارید.\\n"
        else:
            for t in treaties:
                text += f"🕊 {t['name']}\\n"
"""
content = content.replace(peace_old, peace_new)

with open('newfile.py', 'w') as f:
    f.write(content)
