import re
import time
import sqlite3
import logging
from typing import Optional, List
import telebot

DB_PATH = 'war_empire.db'

from contextlib import contextmanager

@contextmanager
def gm_get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=20.0)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

# We get ADMIN_IDS by importing it dynamically when needed to avoid circular import, or just redefining it if it's small,
# but since the prompt says "با ایمپورت کردن متغیر ADMIN_IDS از فایل اصلی", we will import locally inside functions.


# In-memory store for anti-flood: {chat_id: {user_id: [timestamp1, timestamp2, ...]}}
anti_flood_cache = {}

def init_group_db():
    with gm_get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS gm_settings (
                chat_id INTEGER PRIMARY KEY,
                lock_link INTEGER DEFAULT 0,
                lock_id INTEGER DEFAULT 0,
                max_warns INTEGER DEFAULT 3
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS gm_blacklists (
                chat_id INTEGER,
                word TEXT,
                PRIMARY KEY (chat_id, word)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS gm_warns (
                chat_id INTEGER,
                user_id INTEGER,
                warn_count INTEGER DEFAULT 0,
                PRIMARY KEY (chat_id, user_id)
            )
        """)

def get_group_settings(chat_id: int) -> dict:
    with gm_get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM gm_settings WHERE chat_id = ?", (chat_id,))
        row = cur.fetchone()
        if row:
            return dict(row)
        else:
            cur.execute("INSERT INTO gm_settings (chat_id) VALUES (?)", (chat_id,))
            return {'chat_id': chat_id, 'lock_link': 0, 'lock_id': 0, 'max_warns': 3}

def is_group_admin(bot, chat_id: int, user_id: int) -> bool:
    from newfile import ADMIN_IDS
    if user_id in ADMIN_IDS:
        return True
    try:
        member = bot.get_chat_member(chat_id, user_id)
        return member.status in ['creator', 'administrator']
    except Exception as e:
        return False

def check_anti_flood(bot, chat_id: int, user_id: int, message_id: int = None) -> bool:
    """Returns True if flood detected and handled, False otherwise."""
    if is_group_admin(bot, chat_id, user_id):
        return False

    current_time = time.time()

    if chat_id not in anti_flood_cache:
        anti_flood_cache[chat_id] = {}
    if user_id not in anti_flood_cache[chat_id]:
        anti_flood_cache[chat_id][user_id] = []

    timestamps = anti_flood_cache[chat_id][user_id]
    # Filter out timestamps older than 3 seconds
    timestamps = [ts for ts in timestamps if current_time - ts <= 3]
    timestamps.append(current_time)
    anti_flood_cache[chat_id][user_id] = timestamps

    if len(timestamps) > 5:
        # Mute for 5 minutes (300 seconds)
        try:
            bot.restrict_chat_member(chat_id, user_id, until_date=int(current_time) + 300, can_send_messages=False)
            # Silent mute as requested
            bot.delete_message(chat_id, message_id) # needs message id
        except Exception:
            pass
        return True
    return False

def check_message_content(bot, message) -> bool:
    """Checks for links, IDs, and blacklisted words. Returns True if deleted."""
    if not message.text and not message.caption:
        return False

    text = message.text or message.caption
    chat_id = message.chat.id
    user_id = message.from_user.id

    if is_group_admin(bot, chat_id, user_id):
        return False

    settings = get_group_settings(chat_id)

    # 1. Lock Link
    if settings.get('lock_link') == 1:
        if re.search(r'(http|https)://[^\s]+|t\.me/[^\s]+', text, re.IGNORECASE):
            try:
                bot.delete_message(chat_id, message.message_id)
                return True
            except: pass

    # 2. Lock ID
    if settings.get('lock_id') == 1:
        if re.search(r'@[a-zA-Z0-9_]+', text):
            try:
                bot.delete_message(chat_id, message.message_id)
                return True
            except: pass

    # 3. Blacklist
    with gm_get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT word FROM gm_blacklists WHERE chat_id = ?", (chat_id,))
        words = [r['word'] for r in cur.fetchall()]

    for w in words:
        if w.lower() in text.lower():
            try:
                bot.delete_message(chat_id, message.message_id)
                return True
            except: pass

    return False

def parse_time(time_str: str) -> int:
    """Parses e.g. 2h, 1d, 30m into seconds"""
    time_str = time_str.lower()
    if time_str.endswith('m'): return int(time_str[:-1]) * 60
    if time_str.endswith('h'): return int(time_str[:-1]) * 3600
    if time_str.endswith('d'): return int(time_str[:-1]) * 86400
    try: return int(time_str) * 60
    except: return 3600

def register_group_handlers(bot):
    init_group_db()

    # 1. Auto delete service messages
    @bot.message_handler(content_types=['new_chat_members', 'left_chat_member'], func=lambda m: m.chat.type in ['group', 'supergroup'])
    def delete_service_messages(message):
        try: bot.delete_message(message.chat.id, message.message_id)
        except: pass

    # 2. Edit Catcher
    @bot.edited_message_handler(content_types=['text', 'photo', 'video', 'document', 'audio', 'animation'], func=lambda m: m.chat.type in ['group', 'supergroup'])
    def handle_edited_message(message):
        check_message_content(bot, message)

    # 3. Text Message Interceptor (for Flood and Content Checks)
    # We use a custom filter to inspect every group message before typical commands process
    # But wait, telebot executes handlers in order of registration. If we register this FIRST with continue_handling=True, it will work.
    # Unfortunately, telebot's default decorators don't easily do a "middleware" without a class unless we just match everything.

    # Actually, we can hook it into the main text handler or write a catch-all that does not stop propagation if possible, but telebot stops at first match.
    # We will register specific admin commands here, and for flood/content, we will add a note to the user to insert a check in the global handler.
    # OR we can use the Telebot middleware feature if available, but a simpler way is just command handlers.

    # Let's register the admin commands
    @bot.message_handler(func=lambda m: m.chat.type in ['group', 'supergroup'] and m.text and is_group_admin(bot, m.chat.id, m.from_user.id) and m.text.strip().lower().startswith(('قفل', 'بازکردن', 'تنظیم اخطار', 'اخطار', 'حذف اخطار', 'افزودن کلمه', 'حذف کلمه', 'سکوت', 'بن', 'پاکسازی')))
    def group_admin_commands(message):
        text = message.text.strip().lower()
        chat_id = message.chat.id

        # قفل لینک
        if text == 'قفل لینک':
            with gm_get_connection() as conn:
                conn.execute("UPDATE gm_settings SET lock_link = 1 WHERE chat_id = ?", (chat_id,))
            bot.reply_to(message, "✅ قفل لینک فعال شد.")
            return

        if text == 'بازکردن لینک':
            with gm_get_connection() as conn:
                conn.execute("UPDATE gm_settings SET lock_link = 0 WHERE chat_id = ?", (chat_id,))
            bot.reply_to(message, "✅ قفل لینک غیرفعال شد.")
            return

        # قفل آیدی
        if text == 'قفل ایدی' or text == 'قفل آیدی':
            with gm_get_connection() as conn:
                conn.execute("UPDATE gm_settings SET lock_id = 1 WHERE chat_id = ?", (chat_id,))
            bot.reply_to(message, "✅ قفل آیدی فعال شد.")
            return

        if text == 'بازکردن ایدی' or text == 'بازکردن آیدی':
            with gm_get_connection() as conn:
                conn.execute("UPDATE gm_settings SET lock_id = 0 WHERE chat_id = ?", (chat_id,))
            bot.reply_to(message, "✅ قفل آیدی غیرفعال شد.")
            return

        # اخطار
        if text.startswith('تنظیم اخطار '):
            try:
                num = int(text.split()[2] if 'اخطار' in text.split()[1] else text.split()[2]) # simple split logic: تنظیم اخطار 3
            except:
                try: num = int(text.split()[2])
                except: return
            with gm_get_connection() as conn:
                conn.execute("UPDATE gm_settings SET max_warns = ? WHERE chat_id = ?", (num, chat_id))
            bot.reply_to(message, f"✅ سقف اخطار به {num} تغییر یافت.")
            return

        if text == 'اخطار' and message.reply_to_message:
            target_id = message.reply_to_message.from_user.id
            if is_group_admin(bot, chat_id, target_id):
                bot.reply_to(message, "❌ نمی‌توانید به ادمین اخطار دهید.")
                return

            with gm_get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT warn_count FROM gm_warns WHERE chat_id = ? AND user_id = ?", (chat_id, target_id))
                row = cur.fetchone()
                warns = row['warn_count'] + 1 if row else 1
                cur.execute("INSERT OR REPLACE INTO gm_warns (chat_id, user_id, warn_count) VALUES (?, ?, ?)", (chat_id, target_id, warns))

                settings = get_group_settings(chat_id)
                if warns >= settings['max_warns']:
                    try:
                        bot.ban_chat_member(chat_id, target_id)
                        bot.reply_to(message, f"🚫 کاربر سقف اخطار ({warns}/{settings['max_warns']}) را پر کرد و از گروه اخراج شد.")
                        cur.execute("DELETE FROM gm_warns WHERE chat_id = ? AND user_id = ?", (chat_id, target_id))
                    except:
                        bot.reply_to(message, "❌ خطا در اخراج کاربر (ربات ادمین نیست؟)")
                else:
                    bot.reply_to(message, f"⚠️ یک اخطار ثبت شد. ({warns}/{settings['max_warns']})")
            return

        if text == 'حذف اخطار' and message.reply_to_message:
            target_id = message.reply_to_message.from_user.id
            with gm_get_connection() as conn:
                conn.execute("DELETE FROM gm_warns WHERE chat_id = ? AND user_id = ?", (chat_id, target_id))
            bot.reply_to(message, "✅ اخطارهای کاربر پاک شد.")
            return

        # لیست سیاه
        if text.startswith('افزودن کلمه '):
            word = message.text[12:].strip()
            if word:
                with gm_get_connection() as conn:
                    conn.execute("INSERT OR IGNORE INTO gm_blacklists (chat_id, word) VALUES (?, ?)", (chat_id, word))
                bot.reply_to(message, f"✅ کلمه «{word}» به لیست سیاه اضافه شد.")
            return

        if text.startswith('حذف کلمه '):
            word = message.text[9:].strip()
            if word:
                with gm_get_connection() as conn:
                    conn.execute("DELETE FROM gm_blacklists WHERE chat_id = ? AND word = ?", (chat_id, word))
                bot.reply_to(message, f"✅ کلمه «{word}» از لیست سیاه حذف شد.")
            return

        # سکوت زمان دار
        if text.startswith('سکوت ') and message.reply_to_message:
            target_id = message.reply_to_message.from_user.id
            if is_group_admin(bot, chat_id, target_id):
                bot.reply_to(message, "❌ نمی‌توانید ادمین را بی‌صدا کنید.")
                return
            time_str = text.split()[1]
            seconds = parse_time(time_str)
            try:
                bot.restrict_chat_member(chat_id, target_id, until_date=int(time.time()) + seconds, can_send_messages=False)
                bot.reply_to(message, f"✅ کاربر برای {time_str} بی‌صدا شد.")
            except:
                bot.reply_to(message, "❌ خطا در بی‌صدا کردن کاربر.")
            return

        # بن زمان دار
        if text.startswith('بن ') and message.reply_to_message:
            target_id = message.reply_to_message.from_user.id
            if is_group_admin(bot, chat_id, target_id):
                bot.reply_to(message, "❌ نمی‌توانید ادمین را اخراج کنید.")
                return
            time_str = text.split()[1]
            seconds = parse_time(time_str)
            try:
                bot.ban_chat_member(chat_id, target_id, until_date=int(time.time()) + seconds)
                bot.reply_to(message, f"✅ کاربر برای {time_str} از گروه اخراج شد.")
            except:
                bot.reply_to(message, "❌ خطا در بن کردن کاربر.")
            return

        # پاکسازی
        if text.startswith('پاکسازی '):
            try:
                count = int(text.split()[1])
                if count > 100 or count < 1:
                    bot.reply_to(message, "❌ تعداد باید بین ۱ تا ۱۰۰ باشد.")
                    return
            except:
                return

            # Telebot lacks bulk delete, we must loop
            deleted = 0
            msg_id = message.message_id
            for i in range(count):
                try:
                    bot.delete_message(chat_id, msg_id - i)
                    deleted += 1
                except:
                    pass
            msg = bot.send_message(chat_id, f"✅ {deleted} پیام پاکسازی شد.")
            import threading
            threading.Timer(5.0, lambda: bot.delete_message(chat_id, msg.message_id)).start()
            return
