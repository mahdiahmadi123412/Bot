import re
import time
import io
import random
import threading
import sqlite3
import logging
from typing import Optional, List
import telebot
from PIL import Image, ImageDraw, ImageFont

# Assume newfile exposes ADMIN_IDS and get_connection


DB_PATH = 'war_empire.db'

from contextlib import contextmanager
@contextmanager
def get_connection():
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

# In-memory store for anti-flood: {chat_id: {user_id: [timestamp1, timestamp2, ...]}}
anti_flood_cache = {}

# In-memory store for captcha answers: {user_id: {'chat_id': chat_id, 'answer': answer, 'timer': timer_object}}
captcha_cache = {}

def add_column_if_not_exists(conn, table, column, col_type):
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    cols = [row[1] for row in cur.fetchall()]
    if column not in cols:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")

def init_group_db():
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS gm_settings (
                chat_id INTEGER PRIMARY KEY,
                lock_link INTEGER DEFAULT 0,
                lock_id INTEGER DEFAULT 0,
                max_warns INTEGER DEFAULT 3
            )
        """)

        add_column_if_not_exists(conn, 'gm_settings', 'lock_sticker', 'INTEGER DEFAULT 0')
        add_column_if_not_exists(conn, 'gm_settings', 'lock_gif', 'INTEGER DEFAULT 0')
        add_column_if_not_exists(conn, 'gm_settings', 'lock_voice', 'INTEGER DEFAULT 0')
        add_column_if_not_exists(conn, 'gm_settings', 'lock_video_note', 'INTEGER DEFAULT 0')
        add_column_if_not_exists(conn, 'gm_settings', 'lock_photo', 'INTEGER DEFAULT 0')
        add_column_if_not_exists(conn, 'gm_settings', 'lock_document', 'INTEGER DEFAULT 0')
        add_column_if_not_exists(conn, 'gm_settings', 'lock_forward', 'INTEGER DEFAULT 0')

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
        cur.execute("""
            CREATE TABLE IF NOT EXISTS gm_triggers (
                chat_id INTEGER,
                keyword TEXT,
                response TEXT,
                PRIMARY KEY (chat_id, keyword)
            )
        """)

def get_group_settings(chat_id: int) -> dict:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM gm_settings WHERE chat_id = ?", (chat_id,))
        row = cur.fetchone()
        if row:
            return dict(row)
        else:
            cur.execute("INSERT INTO gm_settings (chat_id) VALUES (?)", (chat_id,))
            return {'chat_id': chat_id, 'lock_link': 0, 'lock_id': 0, 'max_warns': 3,
                    'lock_sticker': 0, 'lock_gif': 0, 'lock_voice': 0, 'lock_video_note': 0,
                    'lock_photo': 0, 'lock_document': 0, 'lock_forward': 0}

def is_group_admin(bot, chat_id: int, user_id: int) -> bool:
    from newfile import ADMIN_IDS
    if user_id in ADMIN_IDS:
        return True
    try:
        member = bot.get_chat_member(chat_id, user_id)
        return member.status in ['creator', 'administrator']
    except Exception:
        return False

def generate_captcha_image(num1: int, num2: int, operator: str) -> io.BytesIO:
    img = Image.new('RGB', (200, 100), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    # Add some noise
    for _ in range(500):
        x = random.randint(0, 199)
        y = random.randint(0, 99)
        draw.point((x, y), fill=(random.randint(0,255), random.randint(0,255), random.randint(0,255)))

    for _ in range(5):
        x1, y1 = random.randint(0, 200), random.randint(0, 100)
        x2, y2 = random.randint(0, 200), random.randint(0, 100)
        draw.line((x1, y1, x2, y2), fill=(100, 100, 100), width=1)

    text = f"{num1} {operator} {num2} = ?"

    # Optional: use default font since we can't guarantee true type fonts exist without downloading
    font = ImageFont.load_default()

    draw.text((50, 40), text, fill=(0, 0, 0), font=font)

    bio = io.BytesIO()
    bio.name = 'captcha.jpeg'
    img.save(bio, 'JPEG')
    bio.seek(0)
    return bio

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
    timestamps = [ts for ts in timestamps if current_time - ts <= 3]
    timestamps.append(current_time)
    anti_flood_cache[chat_id][user_id] = timestamps

    if len(timestamps) > 5:
        try:
            bot.restrict_chat_member(chat_id, user_id, until_date=int(current_time) + 300, can_send_messages=False)
            if message_id:
                bot.delete_message(chat_id, message_id)
        except Exception:
            pass
        return True
    return False

def check_message_content(bot, message) -> bool:
    """Checks for links, IDs, blacklisted words, specific media, forwards, and triggers."""
    chat_id = message.chat.id
    user_id = message.from_user.id

    text = message.text or message.caption or ""

    # 4. Triggers (Auto-response) - Placed before admin check so admins can trigger them too
    if text:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT response FROM gm_triggers WHERE chat_id = ? AND keyword = ?", (chat_id, text.strip()))
            trigger = cur.fetchone()
            if trigger:
                bot.reply_to(message, trigger['response'])

    if is_group_admin(bot, chat_id, user_id):
        return False

    settings = get_group_settings(chat_id)

    # Forward check
    if settings.get('lock_forward') == 1 and (message.forward_from or message.forward_from_chat):
        try:
            bot.delete_message(chat_id, message.message_id)
            return True
        except: pass

    # Media checks
    ct = message.content_type
    if (ct == 'sticker' and settings.get('lock_sticker') == 1) or \
       (ct == 'animation' and settings.get('lock_gif') == 1) or \
       (ct == 'voice' and settings.get('lock_voice') == 1) or \
       (ct == 'video_note' and settings.get('lock_video_note') == 1) or \
       (ct == 'photo' and settings.get('lock_photo') == 1) or \
       (ct == 'document' and settings.get('lock_document') == 1):
        try:
            bot.delete_message(chat_id, message.message_id)
            return True
        except: pass

    # Text checks
    if not message.text and not message.caption:
        return False

    text = message.text or message.caption

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
    with get_connection() as conn:
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
    time_str = time_str.lower()
    if time_str.endswith('m'): return int(time_str[:-1]) * 60
    if time_str.endswith('h'): return int(time_str[:-1]) * 3600
    if time_str.endswith('d'): return int(time_str[:-1]) * 86400
    try: return int(time_str) * 60
    except: return 3600

def register_group_handlers(bot):
    init_group_db()

    # Captcha Start Handlers (PM only)
    @bot.message_handler(commands=['start'], func=lambda m: m.chat.type == 'private' and m.text.startswith('/start captcha_'))
    def captcha_start(message):
        user_id = message.from_user.id
        try:
            chat_id = int(message.text.split('captcha_')[1])
        except:
            return

        # Check if user needs to solve captcha
        try:
            member = bot.get_chat_member(chat_id, user_id)
            if not member.can_send_messages:
                op = random.choice(['+', '-'])
                num1 = random.randint(1, 15)
                num2 = random.randint(1, 15)

                # Ensure no negative answers for simplicity
                if op == '-' and num2 > num1:
                    num1, num2 = num2, num1

                answer = num1 + num2 if op == '+' else num1 - num2

                # Setup 2 minute expiry for solving
                timer = threading.Timer(120.0, lambda: captcha_cache.pop(user_id, None))
                timer.start()

                captcha_cache[user_id] = {'chat_id': chat_id, 'answer': answer, 'timer': timer}

                img_io = generate_captcha_image(num1, num2, op)
                bot.send_photo(message.chat.id, img_io, caption="لطفاً جواب معادله داخل عکس را به صورت عدد بفرستید:")
            else:
                bot.send_message(message.chat.id, "شما در این گروه نیازی به حل کپچا ندارید.")
        except Exception as e:
            logging.error("Captcha check failed", exc_info=True)

    @bot.message_handler(func=lambda m: m.chat.type == 'private' and m.from_user.id in captcha_cache)
    def captcha_answer(message):
        user_id = message.from_user.id
        cache = captcha_cache[user_id]

        try:
            user_answer = int(message.text.strip())
            if user_answer == cache['answer']:
                # Correct
                cache['timer'].cancel()
                bot.restrict_chat_member(cache['chat_id'], user_id,
                                         can_send_messages=True,
                                         can_send_media_messages=True,
                                         can_send_other_messages=True,
                                         can_add_web_page_previews=True)
                bot.send_message(user_id, "✅ کاپچا تایید شد! حالا می‌توانید در گروه چت کنید.")
                del captcha_cache[user_id]
            else:
                bot.send_message(user_id, "❌ جواب اشتباه است! دوباره تلاش کنید.")
        except ValueError:
            bot.send_message(user_id, "❌ لطفاً فقط یک عدد ارسال کنید.")
        except Exception as e:
            logging.error("Failed to unmute user after captcha", exc_info=True)

    # Auto delete service messages and handle new member captcha
    @bot.message_handler(content_types=['new_chat_members', 'left_chat_member'], func=lambda m: m.chat.type in ['group', 'supergroup'])
    def handle_service_messages(message):
        chat_id = message.chat.id

        if message.content_type == 'new_chat_members':
            bot_info = bot.get_me()
            for member in message.new_chat_members:
                if member.id == bot_info.id: continue
                if is_group_admin(bot, chat_id, member.id): continue

                try:
                    # Mute user
                    bot.restrict_chat_member(chat_id, member.id, can_send_messages=False)
                except Exception as e:
                    logging.error("Failed to mute new member", exc_info=True)

                try:
                    # Send Captcha prompt
                    name_or_id = f"@{member.username}" if member.username else member.first_name
                    text = f"{name_or_id} برای پیام دادن در گروه، باید به پی‌وی ربات رفته و کپچا را کامل کنید!"

                    markup = telebot.types.InlineKeyboardMarkup()
                    btn = telebot.types.InlineKeyboardButton("🔐 ورود به پی‌وی و حل کپچا", url=f"https://t.me/{bot_info.username}?start=captcha_{chat_id}")
                    markup.add(btn)

                    msg = bot.send_message(chat_id, text, reply_markup=markup)

                    # Delete service message + captcha prompt after 120 seconds
                    def cleanup(c_id, m_id, prompt_m_id):
                        try:
                            bot.delete_message(c_id, m_id)
                            bot.delete_message(c_id, prompt_m_id)
                        except: pass

                    threading.Timer(120.0, cleanup, args=[chat_id, message.message_id, msg.message_id]).start()

                except Exception as e:
                    logging.error("Failed to send captcha prompt", exc_info=True)
        else:
            try: bot.delete_message(chat_id, message.message_id)
            except: pass

    # Edit Catcher
    @bot.edited_message_handler(content_types=['text', 'photo', 'video', 'document', 'audio', 'animation'], func=lambda m: m.chat.type in ['group', 'supergroup'])
    def handle_edited_message(message):
        check_message_content(bot, message)

    admin_cmds = ('قفل', 'بازکردن', 'تنظیم اخطار', 'اخطار', 'حذف اخطار', 'افزودن کلمه', 'حذف کلمه', 'سکوت', 'بن', 'پاکسازی', 'پین', 'آنپین', 'یاد بگیر بگو')

    @bot.message_handler(func=lambda m: m.chat.type in ['group', 'supergroup'] and m.text and is_group_admin(bot, m.chat.id, m.from_user.id) and m.text.strip().lower().startswith(admin_cmds))
    def group_admin_commands(message):
        text = message.text.strip()
        chat_id = message.chat.id



        # قفل رسانه‌ها
        locks = {
            'استیکر': 'lock_sticker',
            'گیف': 'lock_gif',
            'ویس': 'lock_voice',
            'ویدیو مسیج': 'lock_video_note',
            'عکس': 'lock_photo',
            'فایل': 'lock_document',
            'فوروارد': 'lock_forward',
            'لینک': 'lock_link',
            'ایدی': 'lock_id',
            'آیدی': 'lock_id'
        }

        for k, v in locks.items():
            if text == f"قفل {k}":
                with get_connection() as conn:
                    conn.execute(f"UPDATE gm_settings SET {v} = 1 WHERE chat_id = ?", (chat_id,))
                bot.reply_to(message, f"✅ قفل {k} با موفقیت فعال شد.")
                return
            if text == f"بازکردن {k}":
                with get_connection() as conn:
                    conn.execute(f"UPDATE gm_settings SET {v} = 0 WHERE chat_id = ?", (chat_id,))
                bot.reply_to(message, f"✅ قفل {k} با موفقیت غیرفعال شد.")
                return

        # اخطار
        if text.startswith('تنظیم اخطار '):
            try: num = int(text.split()[-1])
            except: return
            with get_connection() as conn:
                conn.execute("UPDATE gm_settings SET max_warns = ? WHERE chat_id = ?", (num, chat_id))
            bot.reply_to(message, f"✅ سقف اخطار به {num} تغییر یافت.")
            return

        if text == 'اخطار' and message.reply_to_message:
            target_id = message.reply_to_message.from_user.id
            if is_group_admin(bot, chat_id, target_id): return

            with get_connection() as conn:
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
            with get_connection() as conn:
                conn.execute("DELETE FROM gm_warns WHERE chat_id = ? AND user_id = ?", (chat_id, target_id))
            bot.reply_to(message, "✅ اخطارهای کاربر پاک شد.")
            return

        # لیست سیاه
        if text.startswith('افزودن کلمه '):
            word = text.replace('افزودن کلمه ', '').strip()
            if word:
                with get_connection() as conn:
                    conn.execute("INSERT OR IGNORE INTO gm_blacklists (chat_id, word) VALUES (?, ?)", (chat_id, word))
                bot.reply_to(message, f"✅ کلمه «{word}» به لیست سیاه اضافه شد.")
            return

        if text.startswith('حذف کلمه '):
            word = text.replace('حذف کلمه ', '').strip()
            if word:
                with get_connection() as conn:
                    conn.execute("DELETE FROM gm_blacklists WHERE chat_id = ? AND word = ?", (chat_id, word))
                bot.reply_to(message, f"✅ کلمه «{word}» از لیست سیاه حذف شد.")
            return

        # سکوت زمان دار
        if text.startswith('سکوت ') and message.reply_to_message:
            target_id = message.reply_to_message.from_user.id
            if is_group_admin(bot, chat_id, target_id): return
            seconds = parse_time(text.split()[1])
            try:
                bot.restrict_chat_member(chat_id, target_id, until_date=int(time.time()) + seconds, can_send_messages=False)
                bot.reply_to(message, f"✅ کاربر برای {text.split()[1]} بی‌صدا شد.")
            except:
                bot.reply_to(message, "❌ خطا در بی‌صدا کردن کاربر.")
            return

        # بن زمان دار
        if text.startswith('بن ') and message.reply_to_message:
            target_id = message.reply_to_message.from_user.id
            if is_group_admin(bot, chat_id, target_id): return
            seconds = parse_time(text.split()[1])
            try:
                bot.ban_chat_member(chat_id, target_id, until_date=int(time.time()) + seconds)
                bot.reply_to(message, f"✅ کاربر برای {text.split()[1]} از گروه اخراج شد.")
            except:
                bot.reply_to(message, "❌ خطا در بن کردن کاربر.")
            return

        # پین و آنپین
        if text == 'پین' and message.reply_to_message:
            try:
                bot.pin_chat_message(chat_id, message.reply_to_message.message_id)
                bot.reply_to(message, "✅ پیام با موفقیت سنجاق شد.")
            except: pass
            return

        if text == 'آنپین' and message.reply_to_message:
            try:
                bot.unpin_chat_message(chat_id, message.reply_to_message.message_id)
                bot.reply_to(message, "✅ پیام از سنجاق برداشته شد.")
            except: pass
            return

        # یاد بگیر بگو
        if text.startswith('یاد بگیر بگو') and message.reply_to_message and message.reply_to_message.text:
            trigger_keyword = message.reply_to_message.text.strip()
            response = text.replace('یاد بگیر بگو', '').strip()

            with get_connection() as conn:
                if response:
                    conn.execute("INSERT OR REPLACE INTO gm_triggers (chat_id, keyword, response) VALUES (?, ?, ?)", (chat_id, trigger_keyword, response))
                    bot.reply_to(message, "✅ ربات کلمه را یاد گرفت.")
                else:
                    conn.execute("DELETE FROM gm_triggers WHERE chat_id = ? AND keyword = ?", (chat_id, trigger_keyword))
                    bot.reply_to(message, "✅ پاسخ ربات فراموش شد.")
            return

        # پاکسازی
        if text.startswith('پاکسازی '):
            try:
                count = int(text.split()[1])
                if 1 <= count <= 100:
                    msg_id = message.message_id
                    for i in range(count):
                        try: bot.delete_message(chat_id, msg_id - i)
                        except: pass
            except: pass
            return
