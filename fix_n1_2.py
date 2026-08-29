with open('newfile.py', 'r') as f:
    content = f.read()

# Fix N+1 in show_alliance_list
old_al = """        rows = []
        for a in alliances:
            a = dict(a)
            member_count = len(get_alliance_members(a['id']))
            capacity = a.get('capacity', 5)
            text += f"• {a['name']} (ظرفیت: {member_count}/{capacity})\\n"

            # دکمه جوین فقط اگر ظرفیت پر نشده باشد ساخته می‌شود
            if member_count < capacity:
                rows.append([inline_btn(f"➕ عضویت در {a['name']}", f"alliance_join_{a['id']}", "success")])
"""

new_al = """        rows = []
        for a in alliances:
            a = dict(a)
            # Use query to get member count instead of N+1
            cur.execute("SELECT COUNT(*) FROM alliance_members WHERE alliance_id = ?", (a['id'],))
            member_count = cur.fetchone()[0]
            capacity = a.get('capacity', 5)
            text += f"• {a['name']} (ظرفیت: {member_count}/{capacity})\\n"

            if member_count < capacity:
                rows.append([inline_btn(f"➕ عضویت در {a['name']}", f"alliance_join_{a['id']}", "success")])
"""

content = content.replace(old_al, new_al)

# Fix N+1 in show_battle_reports
old_br = """        for b in battles:
            b = dict(b)
            winner = "شما" if b['winner_id'] == user_id else "دشمن"

            my_losses = json.loads(b['attacker_losses_json']) if b['attacker_id'] == user_id else json.loads(b['defender_losses_json'])
            losses_str = ", ".join([f"{UNIT_TYPES[k]['name']}: {v}" for k, v in my_losses.items()]) if my_losses else "بدون تلفات"

            opp_id = b['defender_id'] if b['attacker_id'] == user_id else b['attacker_id']
            opp_user = get_user_raw(opp_id)
            opp_name = get_username_or_name(opp_user) if opp_user else "نامشخص"
"""

new_br = """        # Optimize by grabbing opponent names upfront
        opp_ids = []
        for b in battles:
            opp_ids.append(b['defender_id'] if b['attacker_id'] == user_id else b['attacker_id'])

        opp_names = {}
        if opp_ids:
            placeholders = ','.join(['?']*len(opp_ids))
            cur.execute(f"SELECT user_id, empire_name, username, first_name FROM users WHERE user_id IN ({placeholders})", opp_ids)
            for row in cur.fetchall():
                row_dict = dict(row)
                opp_names[row_dict['user_id']] = get_username_or_name(row_dict)

        for b in battles:
            b = dict(b)
            winner = "شما" if b['winner_id'] == user_id else "دشمن"

            my_losses = json.loads(b['attacker_losses_json']) if b['attacker_id'] == user_id else json.loads(b['defender_losses_json'])
            losses_str = ", ".join([f"{UNIT_TYPES[k]['name']}: {v}" for k, v in my_losses.items()]) if my_losses else "بدون تلفات"

            opp_id = b['defender_id'] if b['attacker_id'] == user_id else b['attacker_id']
            opp_name = opp_names.get(opp_id, "نامشخص")
"""

content = content.replace(old_br, new_br)

with open('newfile.py', 'w') as f:
    f.write(content)
