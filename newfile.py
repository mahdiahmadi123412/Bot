import json
import time
import random
import threading
import sqlite3
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import telebot
from telebot import types
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ============================================================
# 🛡️ تنظیمات اصلی ربات
# ============================================================
TOKEN = "7892171145:AAGPQUThtMfP6QXYPUyciYaU2RgGMh82M8Q"
DB_PATH = 'war_empire.db'

# 👑 آیدی عددی ادمین‌ها را اینجا وارد کنید
ADMIN_IDS = {
    5696269841,   # 👈 آیدی عددی مدیر اصلی
    987654321    # 👈 آیدی عددی مدیر دوم
}

BOT_USERNAME = "tyson_bx_bot"
EXCLUSIVE_CHAT_ID = None  # 👈 آیدی عددی گروه اختصاصی

# ضرایب بازی
BASE_PRODUCTION_COINS = 50
BASE_PRODUCTION_WOOD = 40
BASE_PRODUCTION_STONE = 35
BASE_PRODUCTION_FOOD = 60

PRODUCTION_INTERVAL_HOURS = 1
CASTLE_SPAWN_INTERVAL_HOURS = 3
WORLD_BOSS_INTERVAL_DAYS = 7
SEASON_DAYS = 30

# ============================================================
# 🗄️ اتصال به دیتابیس
# ============================================================
bot = telebot.TeleBot(TOKEN, parse_mode='HTML')



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

def add_column_if_not_exists(conn, table, column, col_type):
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    cols = [row[1] for row in cur.fetchall()]
    if column not in cols:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")

def init_db() -> None:
    with sqlite3.connect(DB_PATH, check_same_thread=False, timeout=20.0) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
    with get_connection() as conn:
        cur = conn.cursor()

        cur.execute("""

        CREATE TABLE IF NOT EXISTS message_owners (
            chat_id INTEGER,
            message_id INTEGER,
            user_id INTEGER,
            created_at INTEGER,
            PRIMARY KEY (chat_id, message_id)
        )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                empire_name TEXT UNIQUE,
                level INTEGER DEFAULT 1,
                exp INTEGER DEFAULT 0,
                coins INTEGER DEFAULT 500,
                wood INTEGER DEFAULT 400,
                stone INTEGER DEFAULT 350,
                food INTEGER DEFAULT 600,
                total_soldiers INTEGER DEFAULT 0,
                attack_power INTEGER DEFAULT 0,
                defense_power INTEGER DEFAULT 0,
                last_production INTEGER DEFAULT 0,
                last_castle_attack INTEGER DEFAULT 0,
                last_pvp_attack INTEGER DEFAULT 0,
                last_gacha INTEGER DEFAULT 0,
                season_points INTEGER DEFAULT 0,
                generals_json TEXT DEFAULT '[]',
                banned INTEGER DEFAULT 0,
                ban_reason TEXT DEFAULT '',
                alliance_id INTEGER,
                joined_at INTEGER DEFAULT 0,
                last_seen INTEGER DEFAULT 0
            )
        """)


        # اگر جدول از قبل وجود داشته و ستون empire_name ندارد، اضافه کن
        add_column_if_not_exists(conn, 'users', 'empire_name', 'TEXT')
        # این خط را اضافه کن:
        add_column_if_not_exists(conn, 'users', 'current_action', 'TEXT')
        add_column_if_not_exists(conn, 'users', 'action_data', 'TEXT')
        add_column_if_not_exists(conn, 'users', 'is_in_war', 'INTEGER')
        cur.execute('CREATE TABLE IF NOT EXISTS war_volunteers (user_id INTEGER PRIMARY KEY, alliance_id INTEGER, role TEXT)')
    


        # ساخت ایندکس یکتا برای اطمینان از یکتایی نام امپراتوری
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_empire_name ON users(empire_name)")


        cur.execute("""
            CREATE TABLE IF NOT EXISTS army_units (
                user_id INTEGER,
                unit_type TEXT,
                count INTEGER DEFAULT 0,
                level INTEGER DEFAULT 1,
                PRIMARY KEY (user_id, unit_type),
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS buildings (
                user_id INTEGER PRIMARY KEY,
                wall_level INTEGER DEFAULT 1,
                barracks_level INTEGER DEFAULT 1,
                farm_level INTEGER DEFAULT 1,
                sawmill_level INTEGER DEFAULT 1,
                quarry_level INTEGER DEFAULT 1,
                treasury_level INTEGER DEFAULT 1,
                storage_level INTEGER DEFAULT 1,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS castles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                soldiers INTEGER DEFAULT 20,
                reward_coins INTEGER DEFAULT 100,
                reward_wood INTEGER DEFAULT 80,
                reward_stone INTEGER DEFAULT 60,
                reward_food INTEGER DEFAULT 120,
                expires_at INTEGER DEFAULT 0,
                created_at INTEGER DEFAULT 0
            )
        """)
	
        cur.execute("""
            CREATE TABLE IF NOT EXISTS battles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                attacker_id INTEGER,
                defender_id INTEGER,
                attacker_units_json TEXT,
                defender_units_json TEXT,
                winner_id INTEGER,
                attacker_losses_json TEXT,
                defender_losses_json TEXT,
                coins_looted INTEGER DEFAULT 0,
                wood_looted INTEGER DEFAULT 0,
                stone_looted INTEGER DEFAULT 0,
                food_looted INTEGER DEFAULT 0,
                created_at INTEGER DEFAULT 0,
                FOREIGN KEY (attacker_id) REFERENCES users(user_id) ON DELETE SET NULL,
                FOREIGN KEY (defender_id) REFERENCES users(user_id) ON DELETE SET NULL
            )
        """)


        cur.execute('''
            CREATE TABLE IF NOT EXISTS peace_treaties (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alliance_1_id INTEGER,
                alliance_2_id INTEGER,
                created_at INTEGER
            )
        ''')

        cur.execute("""
            CREATE TABLE IF NOT EXISTS alliances (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                leader_id INTEGER,
                level INTEGER DEFAULT 1,
                treasury_coins INTEGER DEFAULT 0,
                treasury_wood INTEGER DEFAULT 0,
                treasury_stone INTEGER DEFAULT 0,
                treasury_food INTEGER DEFAULT 0,
                territory TEXT DEFAULT '{}',
                created_at INTEGER DEFAULT 0
            )
        """)

        # ======= این دو خط باید دقیقاً اینجا قرار بگیرن =======
        add_column_if_not_exists(conn, 'alliances', 'capacity', 'INTEGER DEFAULT 5')
        add_column_if_not_exists(conn, 'alliances', 'captures', 'INTEGER DEFAULT 0')
        # ===================================================

        cur.execute("""
            CREATE TABLE IF NOT EXISTS alliance_members (
                alliance_id INTEGER,
                user_id INTEGER,
                role TEXT DEFAULT 'member',
                joined_at INTEGER DEFAULT 0,
                PRIMARY KEY (alliance_id, user_id),
                FOREIGN KEY (alliance_id) REFERENCES alliances(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS market_offers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                seller_id INTEGER,
                item_type TEXT,
                quantity INTEGER,
                price_coins INTEGER,
                active INTEGER DEFAULT 1,
                created_at INTEGER DEFAULT 0,
                FOREIGN KEY (seller_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS bounties (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target_id INTEGER,
                issuer_id INTEGER,
                amount_coins INTEGER,
                active INTEGER DEFAULT 1,
                created_at INTEGER DEFAULT 0,
                FOREIGN KEY (target_id) REFERENCES users(user_id) ON DELETE CASCADE,
                FOREIGN KEY (issuer_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS world_boss (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                hp INTEGER,
                max_hp INTEGER,
                level INTEGER DEFAULT 1,
                active INTEGER DEFAULT 1,
                created_at INTEGER DEFAULT 0
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS boss_attacks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                boss_id INTEGER,
                user_id INTEGER,
                damage INTEGER,
                created_at INTEGER DEFAULT 0,
                FOREIGN KEY (boss_id) REFERENCES world_boss(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS generals (
                user_id INTEGER,
                general_id TEXT,
                name TEXT,
                bonus_type TEXT,
                bonus_value REAL,
                level INTEGER DEFAULT 1,
                PRIMARY KEY (user_id, general_id),
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                text TEXT,
                answered INTEGER DEFAULT 0,
                created_at INTEGER DEFAULT 0
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS group_settings (
                chat_id INTEGER PRIMARY KEY,
                alliance_id INTEGER,
                allow_spawn INTEGER DEFAULT 1,
                spam_level INTEGER DEFAULT 1
            )
        """)

        # جدول جدید برای تنظیمات کلی ربات
        cur.execute("""
            CREATE TABLE IF NOT EXISTS bot_settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)


init_db()

# ============================================================
# 🧰 توابع کمکی دیتابیس
# ============================================================
def get_user(user_id: int) -> Optional[Dict[str, Any]]:
    """دریافت اطلاعات کاربر و به‌روزرسانی خودکار تولید منابع"""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        if not row:
            return None
        user = dict(row)

    ensure_production(user_id, user)

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = dict(cur.fetchone())
        return user

def get_user_raw(user_id: int) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def set_war_lock(user_id: int, status: int):
    with get_connection() as conn:
        conn.execute("UPDATE users SET is_in_war = ? WHERE user_id = ?", (status, user_id))

def is_war_locked(user_id: int) -> bool:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT is_in_war FROM users WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        return bool(row and row['is_in_war'] == 1)

def get_user_by_empire_name(name: str) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE empire_name = ?", (name,))
        row = cur.fetchone()
        return dict(row) if row else None

def update_user(user_id: int, **kwargs) -> None:
    with get_connection() as conn:
        cur = conn.cursor()
        if kwargs:
            keys = ", ".join([f"{k} = ?" for k in kwargs.keys()])
            values = list(kwargs.values()) + [user_id]
            cur.execute(f"UPDATE users SET {keys} WHERE user_id = ?", values)

def get_buildings(user_id: int) -> Dict[str, Any]:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM buildings WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        if row:
            result = dict(row)
        else:
            cur.execute("INSERT OR IGNORE INTO buildings (user_id) VALUES (?)", (user_id,))
            result = {"user_id": user_id, "wall_level": 1, "barracks_level": 1, "farm_level": 1,
                      "sawmill_level": 1, "quarry_level": 1, "treasury_level": 1, "storage_level": 1}
        return result

def update_building(user_id: int, building: str, value: int) -> None:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(f"UPDATE buildings SET {building} = ? WHERE user_id = ?", (value, user_id))

def get_army_units(user_id: int) -> Dict[str, Dict[str, int]]:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT unit_type, count, level FROM army_units WHERE user_id = ?", (user_id,))
        rows = cur.fetchall()
        result = {}
        for r in rows:
            result[r['unit_type']] = {'count': r['count'], 'level': r['level']}
        return result

def update_army_unit(user_id: int, unit_type: str, count_delta: int = 0, level_delta: int = 0) -> None:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT count, level FROM army_units WHERE user_id = ? AND unit_type = ?", (user_id, unit_type))
        row = cur.fetchone()
        if row:
            new_count = max(0, row['count'] + count_delta)
            new_level = max(1, row['level'] + level_delta)
            cur.execute("UPDATE army_units SET count = ?, level = ? WHERE user_id = ? AND unit_type = ?",
                        (new_count, new_level, user_id, unit_type))
        else:
            cur.execute("INSERT INTO army_units (user_id, unit_type, count, level) VALUES (?, ?, ?, ?)",
                        (user_id, unit_type, max(0, count_delta), 1 + level_delta))

def get_alliance(user_id: int) -> Optional[Dict[str, Any]]:
    user = get_user(user_id)
    if not user or not user.get('alliance_id'):
        return None
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM alliances WHERE id = ?", (user['alliance_id'],))
        row = cur.fetchone()
        return dict(row) if row else None

def get_alliance_members(alliance_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT u.user_id, u.username, u.first_name, u.empire_name, u.level, am.role
            FROM alliance_members am
            JOIN users u ON u.user_id = am.user_id
            WHERE am.alliance_id = ?
        """, (alliance_id,))
        rows = cur.fetchall()
        return [dict(r) for r in rows]

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

def get_username_or_name(user: Dict[str, Any]) -> str:
    if user.get('empire_name'):
        return f"{user['empire_name']}"
    if user.get('username'):
        return f"@{user['username']}"
    return user.get('first_name', 'ناشناس')

def format_number(num: int) -> str:
    return f"{num:,}"

def now() -> int:
    return int(time.time())
# ============================================================
# 🌟 سیستم کسب تجربه (EXP) و ارتقای سطح
# ============================================================
def add_exp(user_id: int, amount: int, chat_id: int):
    user = get_user(user_id)
    if not user: return
    
    total_exp = user['exp'] + amount
    current_level = user['level']

    # We know that sum of req_exp from level 1 to L is roughly:
    # Total Required = 1000 * L * (L+1) / 2
    # So if we have total cumulative EXP, we can solve for L.
    # But since current level could be anything, it's easier to iterate safely or use math.
    import math

    # Calculate cumulative EXP up to current level
    # Base formula: cumulative_exp_for_level = 1000 * L * (L-1) / 2
    cumulative_exp = 500 * current_level * (current_level - 1)
    new_cumulative_exp = cumulative_exp + total_exp

    # Solve for new level: 500 * L^2 - 500 * L - new_cumulative_exp = 0
    # L = (500 + sqrt(250000 - 4*500*(-new_cumulative_exp))) / 1000
    # L = (1 + sqrt(1 + 8 * new_cumulative_exp / 1000)) / 2

    new_level = math.floor((1 + math.sqrt(1 + 8 * new_cumulative_exp / 1000)) / 2)
    new_level = max(current_level, new_level)

    new_req_cumulative = 500 * new_level * (new_level - 1)
    new_exp_remainder = int(new_cumulative_exp - new_req_cumulative)

    leveled_up = new_level > current_level

    update_user(user_id, exp=new_exp_remainder, level=new_level)
    if leveled_up:
        try: bot.send_message(chat_id, f"🎉 <b>تبریک فرمانده!</b> سطح امپراطوری شما به <b>{new_level}</b> ارتقا یافت!")
        except: pass

# ============================================================
# ⚙️ سیستم تولید خودکار منابع
# ============================================================
def ensure_production(user_id: int, user: Optional[Dict[str, Any]] = None) -> None:
    """بر اساس زمان سپری شده از آخرین تولید، منابع اضافه می‌کند"""
    if user is None:
        user = get_user_raw(user_id)
    if not user:
        return
    last_prod = user.get('last_production', 0)
    if last_prod == 0:
        update_user(user_id, last_production=now())
        return
    elapsed_hours = (now() - last_prod) / 3600
    if elapsed_hours < PRODUCTION_INTERVAL_HOURS:
        return
    intervals = int(elapsed_hours // PRODUCTION_INTERVAL_HOURS)
    if intervals <= 0:
        return
    buildings = get_buildings(user_id)
    coins_add = intervals * (BASE_PRODUCTION_COINS + buildings['treasury_level'] * 10)
    wood_add = intervals * (BASE_PRODUCTION_WOOD + buildings['sawmill_level'] * 8)
    stone_add = intervals * (BASE_PRODUCTION_STONE + buildings['quarry_level'] * 7)
    food_add = intervals * (BASE_PRODUCTION_FOOD + buildings['farm_level'] * 12)
    new_last = last_prod + int(intervals * PRODUCTION_INTERVAL_HOURS * 3600)
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            UPDATE users SET
            coins = coins + ?,
            wood = wood + ?,
            stone = stone + ?,
            food = food + ?,
            last_production = ?
            WHERE user_id = ?
        """, (coins_add, wood_add, stone_add, food_add, new_last, user_id))

# ============================================================
# 🎨 دکمه‌های شیشه‌ای (به‌همراه استایل بصری با ایموجی)
# ============================================================
def inline_btn(text: str, callback_data: str, *args, **kwargs) -> InlineKeyboardButton:
    """ساخت دکمه شیشه‌ای."""
    return InlineKeyboardButton(text=text, callback_data=callback_data)


def inline_row(*buttons: InlineKeyboardButton) -> List[InlineKeyboardButton]:
    return list(buttons)

def build_inline_keyboard(rows: List[List[InlineKeyboardButton]]) -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup()
    for row in rows:
        markup.add(*row)
    return markup

# ============================================================
# 🧮 داده‌های واحدهای نظامی و روابط تاکتیکی
# ============================================================
UNIT_TYPES = {
    'spearman': {'name': 'نیزه‌دار تازه‌کار', 'tier': 1, 'cost': {'coins': 20, 'wood': 10, 'stone': 2, 'food': 5},
                 'training_time': 60, 'attack': 10, 'defense': 8, 'bonus_vs': 'cavalry', 'weak_vs': 'ranged'},
    'swordsman': {'name': 'شمشیرزن زره‌پوش', 'tier': 1, 'cost': {'coins': 27, 'wood': 12, 'stone': 5, 'food': 6},
                  'training_time': 90, 'attack': 15, 'defense': 15, 'bonus_vs': 'infantry', 'weak_vs': 'ranged'},
    'heavy_axeman': {'name': 'گارد تبرزن سنگین', 'tier': 2, 'cost': {'coins': 50, 'wood': 25, 'stone': 12, 'food': 10},
                     'training_time': 180, 'attack': 25, 'defense': 18, 'bonus_vs': 'infantry', 'weak_vs': 'ranged'},
    'shieldbearer': {'name': 'سپرکوب سلطنتی', 'tier': 2, 'cost': {'coins': 60, 'wood': 20, 'stone': 20, 'food': 12},
                     'training_time': 240, 'attack': 10, 'defense': 45, 'bonus_vs': 'none', 'weak_vs': 'cavalry'},
    'archer': {'name': 'کماندار سبک', 'tier': 1, 'cost': {'coins': 22, 'wood': 15, 'stone': 2, 'food': 4},
               'training_time': 70, 'attack': 18, 'defense': 5, 'bonus_vs': 'infantry', 'weak_vs': 'cavalry'},
    'crossbowman': {'name': 'کمان‌پولادی‌زن', 'tier': 2, 'cost': {'coins': 55, 'wood': 30, 'stone': 7, 'food': 7},
                    'training_time': 160, 'attack': 30, 'defense': 8, 'bonus_vs': 'armored', 'weak_vs': 'cavalry'},
    'fire_thrower': {'name': 'نفت‌انداز آتش‌بار', 'tier': 2, 'cost': {'coins': 65, 'wood': 35, 'stone': 10, 'food': 9},
                     'training_time': 200, 'attack': 28, 'defense': 6, 'bonus_vs': 'group', 'weak_vs': 'cavalry'},
    'scout_rider': {'name': 'سوار دیده‌بان', 'tier': 1, 'cost': {'coins': 30, 'wood': 10, 'stone': 2, 'food': 12},
                    'training_time': 80, 'attack': 12, 'defense': 5, 'bonus_vs': 'ranged', 'weak_vs': 'spearman'},
    'heavy_knight': {'name': 'شوالیه سنگین‌اسلحه', 'tier': 2, 'cost': {'coins': 80, 'wood': 25, 'stone': 15, 'food': 20},
                     'training_time': 300, 'attack': 40, 'defense': 25, 'bonus_vs': 'ranged', 'weak_vs': 'spearman'},
    'war_beast': {'name': 'فیل جنگی', 'tier': 3, 'cost': {'coins': 175, 'wood': 75, 'stone': 50, 'food': 40},
                  'training_time': 600, 'attack': 55, 'defense': 40, 'bonus_vs': 'all', 'weak_vs': 'spearman'},
    'battering_ram': {'name': 'دژکوب', 'tier': 3, 'cost': {'coins': 150, 'wood': 125, 'stone': 25, 'food': 15},
                      'training_time': 500, 'attack': 20, 'defense': 50, 'bonus_vs': 'wall', 'weak_vs': 'melee'},
    'catapult': {'name': 'منجنیق سنگی', 'tier': 3, 'cost': {'coins': 200, 'wood': 150, 'stone': 75, 'food': 25},
                 'training_time': 700, 'attack': 60, 'defense': 10, 'bonus_vs': 'wall', 'weak_vs': 'cavalry'},
    'field_medic': {'name': 'طبیب جنگی', 'tier': 2, 'cost': {'coins': 75, 'wood': 25, 'stone': 10, 'food': 17},
                    'training_time': 250, 'attack': 5, 'defense': 10, 'bonus_vs': 'none', 'weak_vs': 'all'},
    'assassin': {'name': 'شکارچی سایه', 'tier': 3, 'cost': {'coins': 250, 'wood': 100, 'stone': 50, 'food': 30},
                 'training_time': 800, 'attack': 50, 'defense': 5, 'bonus_vs': 'general', 'weak_vs': 'none'},
}



# ============================================================
# 🏰 تولید قلعه‌های متروکه
# ============================================================
CASTLE_NAMES = [
    "قلعه متروکه کوهستان", "قلعه متروکه جنگل تاریک", "قلعه متروکه بیابان سوزان",
    "قلعه متروکه ساحل متروک", "قلعه متروکه دره یخ‌زده", "قلعه متروکه رودخانه خروشان",
    "قلعه متروکه تپه‌های مه‌آلود", "قلعه متروکه صخره‌های سرخ", "قلعه متروکه مرداب",
    "قلعه متروکه دروازه قدیمی"
]

def spawn_castles(count: int = 3) -> None:
    """ایجاد قلعه‌های متروکه تصادفی"""
    with get_connection() as conn:
        cur = conn.cursor()
        for _ in range(count):
            name = random.choice(CASTLE_NAMES)
            soldiers = random.randint(10, 50)
            reward_coins = random.randint(50, 200) + soldiers * 2
            reward_wood = random.randint(30, 120)
            reward_stone = random.randint(20, 80)
            reward_food = random.randint(60, 200)
            expires_at = int(time.time()) + CASTLE_SPAWN_INTERVAL_HOURS * 3600
            cur.execute("""
                INSERT INTO castles (name, soldiers, reward_coins, reward_wood, reward_stone, reward_food, expires_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (name, soldiers, reward_coins, reward_wood, reward_stone, reward_food, expires_at, int(time.time())))

def get_active_castles() -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM castles WHERE expires_at > ?", (int(time.time()),))
        rows = cur.fetchall()
        return [dict(r) for r in rows]

def get_castle(castle_id: int) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM castles WHERE id = ?", (castle_id,))
        row = cur.fetchone()
        return dict(row) if row else None

def delete_castle(castle_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM castles WHERE id = ?", (castle_id,))

# ============================================================
# ⚔️ محاسبات نبرد
# ============================================================
def calculate_army_power(user_id: int) -> int:
    units = get_army_units(user_id)
    total = 0
    for unit_type, data in units.items():
        if unit_type in UNIT_TYPES:
            count = data['count']
            attack = UNIT_TYPES[unit_type]['attack']
            total += count * attack
    return total

def calculate_army_defense(user_id: int) -> int:
    units = get_army_units(user_id)
    total = 0
    for unit_type, data in units.items():
        if unit_type in UNIT_TYPES:
            count = data['count']
            defense = UNIT_TYPES[unit_type]['defense']
            total += count * defense
    return total

def get_total_soldiers(user_id: int) -> int:
    units = get_army_units(user_id)
    return sum(data['count'] for data in units.values())

def update_army_power_fields(user_id: int) -> None:
    attack = calculate_army_power(user_id)
    defense = calculate_army_defense(user_id)
    total = get_total_soldiers(user_id)
    update_user(user_id, attack_power=attack, defense_power=defense, total_soldiers=total)


def simulate_battle(attacker_id: int, defender_id: int) -> Dict[str, Any]:
    """شبیه‌سازی نبرد و محاسبه تلفات بر اساس تاکتیک‌های ذخیره‌شده"""
    attacker = get_user_raw(attacker_id)
    defender = get_user_raw(defender_id)
    if not attacker or not defender:
        return {'winner': None, 'attacker_losses': {}, 'defender_losses': {}}

    # گرفتن تاکتیک‌ها از دیتابیس (در غیر این صورت پیش‌فرض)
    attacker_units = get_army_units(attacker_id)
    defender_units = get_army_units(defender_id)

    attacker_attack = calculate_army_power(attacker_id)
    attacker_defense = calculate_army_defense(attacker_id)
    defender_attack = calculate_army_power(defender_id)
    defender_defense = calculate_army_defense(defender_id)

    # Unit Tactical Relationship Calculations (Bonus vs / Weak vs)
    a_tactical_bonus = 0.0
    d_tactical_bonus = 0.0

    # Categorize units for attacker and defender
    a_cats = set(UNIT_TYPES[u_id].get('bonus_vs', '') for u_id in attacker_units if attacker_units[u_id]['count'] > 0 and UNIT_TYPES.get(u_id))
    d_cats = set(UNIT_TYPES[u_id].get('bonus_vs', '') for u_id in defender_units if defender_units[u_id]['count'] > 0 and UNIT_TYPES.get(u_id))

    # For every attacker unit
    for au_id, au_data in attacker_units.items():
        if au_data['count'] <= 0: continue
        u_info = UNIT_TYPES.get(au_id)
        if not u_info: continue

        bonus_target = u_info.get('bonus_vs')
        weak_target = u_info.get('weak_vs')

        # Check against defender units
        for du_id, du_data in defender_units.items():
            if du_data['count'] <= 0: continue
            d_info = UNIT_TYPES.get(du_id)
            if not d_info: continue

            # Use arbitrary string matching from unit type to determine class for basic logic (e.g. spearman vs cavalry)
            # 'cavalry', 'infantry', 'ranged'
            if bonus_target and bonus_target in du_id:
                a_tactical_bonus += 0.20 * (au_data['count'] / max(1, sum(u['count'] for u in attacker_units.values())))
            if weak_target and weak_target in du_id:
                a_tactical_bonus -= 0.20 * (au_data['count'] / max(1, sum(u['count'] for u in attacker_units.values())))

    for du_id, du_data in defender_units.items():
        if du_data['count'] <= 0: continue
        d_info = UNIT_TYPES.get(du_id)
        if not d_info: continue

        bonus_target = d_info.get('bonus_vs')
        weak_target = d_info.get('weak_vs')

        for au_id, au_data in attacker_units.items():
            if au_data['count'] <= 0: continue
            a_info = UNIT_TYPES.get(au_id)
            if not a_info: continue

            if bonus_target and bonus_target in au_id:
                d_tactical_bonus += 0.20 * (du_data['count'] / max(1, sum(u['count'] for u in defender_units.values())))
            if weak_target and weak_target in au_id:
                d_tactical_bonus -= 0.20 * (du_data['count'] / max(1, sum(u['count'] for u in defender_units.values())))

    attacker_attack = int(attacker_attack * (1 + a_tactical_bonus))
    defender_defense = int(defender_defense * (1 + d_tactical_bonus))

    # اعمال بونوس ژنرال‌ها به صورت صحیح
    attacker_generals = json.loads(attacker.get('generals_json') or '[]')
    defender_generals = json.loads(defender.get('generals_json') or '[]')
    
    # اگر نوع بونوس ژنرال شامل کلمه attack بود، به مهاجم اضافه شود
    a_bonus = sum(g.get('bonus_value', 0) for g in attacker_generals if 'attack' in g.get('bonus_type', ''))
    
    # اگر نوع بونوس ژنرال شامل defense یا heal بود، به مدافع اضافه شود
    d_bonus = sum(g.get('bonus_value', 0) for g in defender_generals if 'defense' in g.get('bonus_type', '') or 'heal' in g.get('bonus_type', ''))
    
    attacker_attack = int(attacker_attack * (1 + a_bonus))
    defender_defense = int(defender_defense * (1 + d_bonus))


    # محاسبه ضریب تصادفی
    random_factor_a = random.uniform(0.9, 1.1)
    random_factor_d = random.uniform(0.9, 1.1)
    total_power_a = (attacker_attack * random_factor_a + attacker_defense * 0.5)
    total_power_d = (defender_attack * random_factor_d + defender_defense * 0.5)

    total_power_a = max(1, int(total_power_a))
    total_power_d = max(1, int(total_power_d))

    attacker_win = total_power_a > total_power_d

    # محاسبه تلفات
    if attacker_win:
        # Loser (Defender) loses 20%-40%
        defender_loss_percent = random.uniform(0.20, 0.40)
        # Winner (Attacker) loses based on power ratio formula
        ratio = total_power_d / total_power_a
        attacker_loss_percent = max(0.01, min(0.20, 0.25 * ratio))
    else:
        # Loser (Attacker) loses 20%-40%
        attacker_loss_percent = random.uniform(0.20, 0.40)
        # Winner (Defender) loses based on power ratio formula
        ratio = total_power_a / total_power_d
        defender_loss_percent = max(0.01, min(0.20, 0.25 * ratio))

    attacker_losses = {}
    defender_losses = {}

    # قابلیت درمان (Medics/Heal Generals)
    a_heal_bonus = sum(g.get('bonus_value', 0) for g in attacker_generals if 'heal' in g.get('bonus_type', ''))
    if any('medic' in k for k in attacker_units.keys()):
        a_heal_bonus += 0.35

    d_heal_bonus = sum(g.get('bonus_value', 0) for g in defender_generals if 'heal' in g.get('bonus_type', ''))
    if any('medic' in k for k in defender_units.keys()):
        d_heal_bonus += 0.35

    for unit_type, data in attacker_units.items():
        loss = int(data['count'] * attacker_loss_percent)
        if a_heal_bonus > 0 and loss > 0:
            healed = int(loss * min(1.0, a_heal_bonus))
            loss -= healed
        if loss > 0:
            attacker_losses[unit_type] = loss

    for unit_type, data in defender_units.items():
        loss = int(data['count'] * defender_loss_percent)
        if d_heal_bonus > 0 and loss > 0:
            healed = int(loss * min(1.0, d_heal_bonus))
            loss -= healed
        if loss > 0:
            defender_losses[unit_type] = loss

    # اعمال تلفات به دیتابیس
    for unit_type, loss in attacker_losses.items():
        update_army_unit(attacker_id, unit_type, count_delta=-loss)
    for unit_type, loss in defender_losses.items():
        update_army_unit(defender_id, unit_type, count_delta=-loss)

    update_army_power_fields(attacker_id)
    update_army_power_fields(defender_id)

    # تعیین غنائم
    coins_looted = 0
    wood_looted = 0
    stone_looted = 0
    food_looted = 0
    if attacker_win:
        defender_res = get_user_raw(defender_id)
        if defender_res:
            coins_looted = min(defender_res['coins'], int(defender_res['coins'] * random.uniform(0.05, 0.15)))
            wood_looted = min(defender_res['wood'], int(defender_res['wood'] * random.uniform(0.05, 0.15)))
            stone_looted = min(defender_res['stone'], int(defender_res['stone'] * random.uniform(0.05, 0.15)))
            food_looted = min(defender_res['food'], int(defender_res['food'] * random.uniform(0.05, 0.15)))
            # کسر منابع از مدافع
            update_user(defender_id,
                        coins=defender_res['coins'] - coins_looted,
                        wood=defender_res['wood'] - wood_looted,
                        stone=defender_res['stone'] - stone_looted,
                        food=defender_res['food'] - food_looted)
            # افزودن به مهاجم
            attacker_res = get_user_raw(attacker_id)
            update_user(attacker_id,
                        coins=attacker_res['coins'] + coins_looted,
                        wood=attacker_res['wood'] + wood_looted,
                        stone=attacker_res['stone'] + stone_looted,
                        food=attacker_res['food'] + food_looted)

    # ثبت نبرد
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO battles (attacker_id, defender_id, attacker_units_json, defender_units_json,
                               winner_id, attacker_losses_json, defender_losses_json,
                               coins_looted, wood_looted, stone_looted, food_looted, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            attacker_id, defender_id,
            json.dumps(attacker_units), json.dumps(defender_units),
            attacker_id if attacker_win else defender_id,
            json.dumps(attacker_losses), json.dumps(defender_losses),
            coins_looted, wood_looted, stone_looted, food_looted, int(time.time())
        ))
        battle_id = cur.lastrowid
        return {
            'battle_id': battle_id,
            'winner': attacker_id if attacker_win else defender_id,
            'attacker_losses': attacker_losses,
            'defender_losses': defender_losses,
            'coins_looted': coins_looted,
            'wood_looted': wood_looted,
            'stone_looted': stone_looted,
            'food_looted': food_looted
        }

# ============================================================
# 👥 سیستم اتحادها
# ============================================================
def create_alliance(user_id: int, name: str) -> bool:
    user = get_user(user_id)
    if not user or user.get('alliance_id'):
        return False
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("INSERT INTO alliances (name, leader_id, created_at) VALUES (?, ?, ?)",
                    (name, user_id, int(time.time())))
        alliance_id = cur.lastrowid
        cur.execute("INSERT INTO alliance_members (alliance_id, user_id, role, joined_at) VALUES (?, ?, 'leader', ?)",
                    (alliance_id, user_id, int(time.time())))
    update_user(user_id, alliance_id=alliance_id)
    return True

def join_alliance(user_id: int, alliance_id: int) -> bool:
    user = get_user(user_id)
    if not user or user.get('alliance_id'):
        return False
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM alliances WHERE id = ?", (alliance_id,))
        if not cur.fetchone():
            return False
        cur.execute("INSERT OR IGNORE INTO alliance_members (alliance_id, user_id, role, joined_at) VALUES (?, ?, 'member', ?)",
                    (alliance_id, user_id, int(time.time())))
    update_user(user_id, alliance_id=alliance_id)
    return True

def donate_to_alliance(user_id: int, resource_type: str, amount: int) -> bool:
    user = get_user(user_id)
    alliance = get_alliance(user_id)
    if not user or not alliance:
        return False
    if resource_type not in ['coins', 'wood', 'stone', 'food']:
        return False
    if user[resource_type] < amount:
        return False
    # کسر از کاربر
    update_user(user_id, **{resource_type: user[resource_type] - amount})
    # افزودن به خزانه اتحاد
    with get_connection() as conn:
        cur = conn.cursor()
        treasury_field = f"treasury_{resource_type}"
        cur.execute(f"UPDATE alliances SET {treasury_field} = {treasury_field} + ? WHERE id = ?",
                    (amount, alliance['id']))
        return True

# ============================================================
# 🧙‍♂️ سیستم ژنرال‌ها (Gacha)
# ============================================================
GACHA_POOL = [
    {"id": "gen_ares", "name": "آرس", "bonus_type": "attack", "bonus_value": 0.20, "rarity": "legendary"},
    {"id": "gen_athena", "name": "آتنا", "bonus_type": "defense", "bonus_value": 0.20, "rarity": "legendary"},
    {"id": "gen_leonidas", "name": "لئونیداس", "bonus_type": "spearman_attack", "bonus_value": 0.25, "rarity": "epic"},
    {"id": "gen_ramses", "name": "رامسس", "bonus_type": "archer_attack", "bonus_value": 0.25, "rarity": "epic"},
    {"id": "gen_attila", "name": "آتیلا", "bonus_type": "cavalry_attack", "bonus_value": 0.25, "rarity": "epic"},
    {"id": "gen_sun_tzu", "name": "سان تزو", "bonus_type": "all_attack", "bonus_value": 0.10, "rarity": "rare"},
    {"id": "gen_hippocrates", "name": "بقراط", "bonus_type": "medic_heal", "bonus_value": 0.30, "rarity": "rare"},
    {"id": "gen_achilles", "name": "آخیلوس", "bonus_type": "attack", "bonus_value": 0.15, "rarity": "rare"},
    {"id": "gen_odysseus", "name": "اودیسه", "bonus_type": "scout_speed", "bonus_value": 0.50, "rarity": "rare"},
    {"id": "gen_caesar", "name": "سزار", "bonus_type": "all_attack", "bonus_value": 0.15, "rarity": "epic"},
]

def roll_gacha(user_id: int) -> Optional[Dict[str, Any]]:
    user = get_user(user_id)
    if not user:
        return None
    cost = 200
    if user['coins'] < cost:
        return None
    update_user(user_id, coins=user['coins'] - cost)
    # تعیین شانس
    r = random.random()
    if r < 0.02:
        rarity = 'legendary'
    elif r < 0.12:
        rarity = 'epic'
    elif r < 0.40:
        rarity = 'rare'
    else:
        rarity = 'common'
    pool = [g for g in GACHA_POOL if g['rarity'] == rarity] or GACHA_POOL
    selected = random.choice(pool)
    # ذخیره ژنرال
    generals = json.loads(user.get('generals_json') or '[]')
    # بررسی وجود
    for g in generals:
        if g['id'] == selected['id']:
            # ارتقاء سطح
            g['level'] = g.get('level', 1) + 1
            g['bonus_value'] += 0.05
            update_user(user_id, generals_json=json.dumps(generals))
            return selected
    generals.append({
        "id": selected['id'],
        "name": selected['name'],
        "bonus_type": selected['bonus_type'],
        "bonus_value": selected['bonus_value'],
        "level": 1,
        "rarity": selected['rarity']
    })
    update_user(user_id, generals_json=json.dumps(generals))
    return selected

# ============================================================
# 🏹 سیستم بازار سیاه و اقتصاد بازیکنان
# ============================================================
def create_market_offer(seller_id: int, item_type: str, quantity: int, price: int) -> bool:
    user = get_user(seller_id)
    if not user:
        return False
    if item_type not in ['coins', 'wood', 'stone', 'food']:
        return False
    if user[item_type] < quantity:
        return False
    update_user(seller_id, **{item_type: user[item_type] - quantity})
    with get_connection() as conn:
        conn.execute("INSERT INTO market_offers (seller_id, item_type, quantity, price_coins, created_at) VALUES (?, ?, ?, ?, ?)",
                     (seller_id, item_type, quantity, price, int(time.time())))
        return True

# ============================================================
# 💰 سیستم جایزه‌بگیر (Bounty)
# ============================================================
def place_bounty(target_id: int, issuer_id: int, amount: int) -> bool:
    issuer = get_user(issuer_id)
    if not issuer or issuer['coins'] < amount:
        return False
    update_user(issuer_id, coins=issuer['coins'] - amount)
    with get_connection() as conn:
        conn.execute("INSERT INTO bounties (target_id, issuer_id, amount_coins, created_at) VALUES (?, ?, ?, ?)",
                     (target_id, issuer_id, amount, int(time.time())))
        return True

def claim_bounty(bounty_id: int, hunter_id: int) -> bool:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM bounties WHERE id = ? AND active = 1", (bounty_id,))
        bounty = cur.fetchone()
        if not bounty:
            return False
        bounty = dict(bounty)

    hunter = get_user(hunter_id)
    target = get_user(bounty['target_id'])
    if not hunter or not target:
        return False

    # Simulate a full battle
    result = simulate_battle(hunter_id, target['user_id'])
    if result['winner'] == hunter_id:
        update_user(hunter_id, coins=hunter['coins'] + bounty['amount_coins'])
        with get_connection() as conn:
            conn.execute("UPDATE bounties SET active = 0 WHERE id = ?", (bounty_id,))
        return True
    return False

# ============================================================
# 🌋 سیستم باس جهانی و رویدادهای سراسری
# ============================================================
def spawn_world_boss(level: int = 1) -> None:
    hp = 10000 * (level ** 1.5)
    with get_connection() as conn:
        conn.execute("UPDATE world_boss SET active = 0 WHERE active = 1")
        conn.execute("INSERT INTO world_boss (name, hp, max_hp, level, active, created_at) VALUES (?, ?, ?, ?, 1, ?)",
                     (f"اهریمن سطح {level}", int(hp), int(hp), level, int(time.time())))

def get_active_world_boss() -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM world_boss WHERE active = 1 ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
        return dict(row) if row else None

def attack_world_boss(user_id: int, soldiers: int) -> Dict[str, Any]:
    boss = get_active_world_boss()
    if not boss:
        return {'success': False, 'message': 'باس فعالی وجود ندارد'}
    user = get_user(user_id)
    if not user or user['total_soldiers'] < soldiers:
        return {'success': False, 'message': 'سرباز کافی ندارید'}
    # محاسبه آسیب
    damage = soldiers * random.randint(8, 15)
    # فرض می‌کنیم از کل واحدها به نسبت کم می‌کنیم
    units = get_army_units(user_id)
    total = sum(u['count'] for u in units.values())
    if total > 0:
        ratio = soldiers / total
        for unit_type, data in units.items():
            loss = int(data['count'] * ratio * 0.05)
            if loss > 0:
                update_army_unit(user_id, unit_type, count_delta=-loss)
    update_army_power_fields(user_id)
    new_hp = max(0, boss['hp'] - damage)

    # کسر سربازان اعزامی (تلفات)
    with get_connection() as conn:
        cur = conn.cursor()
        if new_hp == 0:
            cur.execute("UPDATE world_boss SET hp = 0, active = 0 WHERE id = ?", (boss['id'],))
            cur.execute("INSERT INTO boss_attacks (boss_id, user_id, damage, created_at) VALUES (?, ?, ?, ?)",
                        (boss['id'], user_id, damage, int(time.time())))
            update_user(user_id, coins=user['coins'] + 10000, wood=user['wood'] + 5000)
            return {'success': True, 'damage': damage, 'new_hp': 0, 'max_hp': boss['max_hp'], 'killed': True}
        else:
            cur.execute("UPDATE world_boss SET hp = ? WHERE id = ?", (new_hp, boss['id']))
            cur.execute("INSERT INTO boss_attacks (boss_id, user_id, damage, created_at) VALUES (?, ?, ?, ?)",
                        (boss['id'], user_id, damage, int(time.time())))
            return {'success': True, 'damage': damage, 'new_hp': new_hp, 'max_hp': boss['max_hp'], 'killed': False}

# ============================================================
# 👑 پنل مدیریت (Admin Panel)
# ============================================================
def admin_main_menu() -> InlineKeyboardMarkup:
    rows = [
        [inline_btn("📊 آمار سرور", "admin_stats", "primary"), inline_btn("📨 ارسال پیام همگانی", "admin_broadcast", "primary")],
        [inline_btn("👤 مدیریت کاربر", "admin_user_manage", "primary"), inline_btn("💰 اقتصاد", "admin_economy", "success")],
        [inline_btn("⚔️ رویدادها", "admin_events", "success"), inline_btn("⚖️ تغییر موجودی", "admin_change_balance", "warning")],
        [inline_btn("🔨 بن کردن", "admin_ban", "danger"), inline_btn("🔓 آنبن کردن", "admin_unban", "success")],
        [inline_btn("🧹 پاکسازی", "admin_wipe", "danger"), inline_btn("📢 ثبت عضویت اجباری", "admin_force_join", "danger")],
        [inline_btn("❌ خروج", "admin_exit", "danger")]
    ]
    return build_inline_keyboard(rows)




def is_admin_user(user_id: int) -> bool:
    return user_id in ADMIN_IDS

# ============================================================
# 📊 منوی اصلی کاربر
# ============================================================
def main_menu(user_id: int) -> InlineKeyboardMarkup:
    rows = [
        [inline_btn("📊 موجودی من", "profile", "primary"), inline_btn("🏭 جمع آوری منابع", "collect_resources", "success")],
        [inline_btn("⚔️ حمله و غارت", "attack_menu", "danger"), inline_btn("🛒 بازار", "market_menu", "primary")],
        [inline_btn("🏰 ارتش و سربازان", "army_menu", "primary"),
 inline_btn("⬆️ ارتقای ساختمان‌ها", "building_menu", "success")],
        [inline_btn("👥 اتحاد", "alliance_menu", "primary"), inline_btn("🎁 ژنرال‌ها", "gacha_menu", "success")],
        [inline_btn("🌍 باس جهانی", "world_boss_menu", "danger"), inline_btn("📜 گزارش‌های جنگ", "battle_reports", "primary")],
        [inline_btn("🏆 رتبه‌بندی", "leaderboard", "warning"), inline_btn("💰 جایزه‌بگیر", "bounty_menu", "danger")],
    ]
    if is_admin_user(user_id):
        rows.append([inline_btn("👑 پنل مدیریت", "admin_panel", "danger")])
    return build_inline_keyboard(rows)
# -----------------------------------------------
# توابع سیستم عضویت اجباری
# -----------------------------------------------
def set_force_join_channel(channel_id: str) -> None:
    with get_connection() as conn:
        conn.execute("INSERT OR REPLACE INTO bot_settings (key, value) VALUES ('force_join', ?)", (channel_id,))

def get_force_join_channel() -> Optional[str]:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT value FROM bot_settings WHERE key = 'force_join'")
        row = cur.fetchone()
        return row['value'] if row else None

def check_user_joined(user_id: int) -> bool:
    """بررسی می‌کند آیا کاربر در کانال اجباری عضو هست یا نه"""
    channel = get_force_join_channel()
    if not channel:
        return True # اگر کانالی ثبت نشده بود، همه مجازند
    try:
        member = bot.get_chat_member(channel, user_id)
        if member.status in ['member', 'administrator', 'creator']:
            return True
    except Exception as e:
        # اگر ربات تو کانال ادمین نباشه خطا میده.
        pass
    return False

# -----------------------------------------------
# توابع مرحله‌ای (تغییر نام و تنظیم کانال)
# -----------------------------------------------
def process_change_empire_name(message):
    user_id = message.from_user.id
    new_name = message.text.strip()
    user = get_user(user_id)
    if not user or user['coins'] < 200:
        bot.send_message(message.chat.id, "❌ سکه کافی ندارید.")
        return
    if not new_name:
        bot.send_message(message.chat.id, "❌ نام نمی‌تواند خالی باشد.")
        return
        
    existing = get_user_by_empire_name(new_name)
    if existing and existing['user_id'] != user_id:
        bot.send_message(message.chat.id, "❌ این نام قبلاً استفاده شده است. لطفاً نام دیگری انتخاب کن:")
        set_user_state(user_id, 'process_change_empire_name')
        return
        
    # ثبت نام جدید و کسر سکه
    update_user(user_id, empire_name=new_name, coins=user['coins'] - 200)
    bot.send_message(message.chat.id, f"✅ نام امپراطوری شما با موفقیت به «{new_name}» تغییر یافت!\n💰 ۲۰۰ سکه کسر شد.", reply_markup=main_menu(user_id))

def process_admin_force_join(message):
    user_id = message.from_user.id
    if not is_admin_user(user_id): return
    text = message.text.strip()
    
    if text == 'لغو':
        with get_connection() as conn:
            conn.execute("DELETE FROM bot_settings WHERE key = 'force_join'")
            bot.send_message(message.chat.id, "✅ عضویت اجباری با موفقیت لغو و غیرفعال شد.")
            return
        
    if not text.startswith('@'):
        bot.send_message(message.chat.id, "❌ آیدی کانال حتماً باید با @ شروع شود (مثلاً @MyChannel). دوباره تلاش کن:")
        set_user_state(user_id, 'process_admin_force_join')
        return
        
    set_force_join_channel(text)
    bot.send_message(message.chat.id, f"✅ کانال {text} به عنوان عضویت اجباری ثبت شد.\n⚠️ فراموش نکن که ربات حتماً باید در این کانال **ادمین** باشه تا بتونه اعضا رو تشخیص بده!")

def clear_user_state(user_id: int):
    update_user(user_id, current_action=None, action_data=None)

def set_user_state(user_id: int, action: str, data: dict = None):
    import json
    data_str = json.dumps(data) if data else None
    update_user(user_id, current_action=action, action_data=data_str)

# ============================================================
# 🚀 هندلرهای دستوری و پیام
# ============================================================
@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id
    clear_user_state(user_id)

    
    if not check_user_joined(user_id):
        channel = get_force_join_channel()
        bot.send_message(message.chat.id, f"🛑 کاربر عزیز!\nبرای استفاده از ربات باید حتماً در کانال زیر عضو شوید:\n{channel}\n\nسپس دوباره /start را بفرستید.")
        return
        
    user = get_user_raw(user_id)
    if not user:
        with get_connection() as conn:
            conn.execute("""
                INSERT OR IGNORE INTO users (user_id, username, first_name, joined_at, last_production)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, message.from_user.username, message.from_user.first_name, int(time.time()), int(time.time())))

        get_buildings(user_id)
        user = get_user_raw(user_id)

    # اگر اسم امپراطوری نداشت، درخواست نام
    if not user.get('empire_name'):
        msg = bot.send_message(message.chat.id,
                               "🏰 <b>به دنیای مدیریت منابع خوش آمدی!</b>\n"
                               "برای شروع، نام امپراطوری خود را ارسال کن (یکتا):")
        set_user_state(user_id, 'process_empire_name')
        return

    # در غیر این صورت منوی اصلی را ارسال یا ویرایش کن
    text = (
        f"🏰 <b>به دنیای مدیریت منابع خوش آمدی فرمانده {user['empire_name']}!</b>\n\n"
        f"از منوی زیر امپراتوری خودت را مدیریت کن 👇\n"
        f"سکه: {format_number(user['coins'])} | چوب: {format_number(user['wood'])} | سنگ: {format_number(user['stone'])} | غذا: {format_number(user['food'])}\n"
        f"نیروی اولیه: {format_number(user['total_soldiers'])} سرباز\n"
    )
    bot.send_message(message.chat.id, text, reply_markup=main_menu(user_id))

def process_empire_name(message):
    user_id = message.from_user.id
    name = message.text.strip()
    if not name:
        bot.send_message(message.chat.id, "❌ نام نمی‌تواند خالی باشد. دوباره تلاش کن:")
        set_user_state(user_id, 'process_empire_name')
        return
    # بررسی یکتا بودن
    existing = get_user_by_empire_name(name)
    if existing and existing['user_id'] != user_id:
        bot.send_message(message.chat.id, "❌ این نام قبلاً استفاده شده است. لطفاً نام دیگری انتخاب کن:")
        set_user_state(user_id, 'process_empire_name')
        return
    # ذخیره نام
    update_user(user_id, empire_name=name)
    user = get_user(user_id)
    text = (
        f"🏰 <b>امپراطوری {user['empire_name']} با موفقیت ساخته شد!</b>\n\n"
        f"سکه: {format_number(user['coins'])} | چوب: {format_number(user['wood'])} | سنگ: {format_number(user['stone'])} | غذا: {format_number(user['food'])}\n"
        f"نیروی اولیه: {format_number(user['total_soldiers'])} سرباز\n"
        f"از منوی زیر امپراتوری خودت را مدیریت کن 👇"
    )
    try:
        # First send the success message with main menu
        bot.send_message(message.chat.id, text, reply_markup=main_menu(user_id))
    except Exception as e:
        print(f"Error in process_empire_name sending message: {e}")

@bot.message_handler(commands=['admin'])
def admin_command(message):
    user_id = message.from_user.id
    if not is_admin_user(user_id):
        bot.send_message(message.chat.id, "⛔️ شما دسترسی ادمین ندارید.")
        return
    bot.send_message(message.chat.id, "👑 <b>پنل مدیریت</b>", reply_markup=admin_main_menu())

# ============================================================
# 🖥️ توابع نمایش پروفایل و منوها (با قابلیت ویرایش همان پیام)
# ============================================================
def set_message_owner(chat_id: int, message_id: int, user_id: int):
    with get_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO message_owners (chat_id, message_id, user_id, created_at) VALUES (?, ?, ?, ?)",
            (chat_id, message_id, user_id, int(time.time()))
        )

def get_message_owner(chat_id: int, message_id: int):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT user_id FROM message_owners WHERE chat_id = ? AND message_id = ?", (chat_id, message_id))
        row = cur.fetchone()
        if row:
            return row['user_id']
    return None

def edit_or_send(chat_id, message_id, text, reply_markup, user_id):
    """اگر message_id داده شده باشد، پیام را ویرایش می‌کند، در غیر این صورت پیام جدید می‌فرستد.
    مالکیت پیام را نیز ثبت می‌کند."""
    if message_id:
        try:
            bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=reply_markup)
            set_message_owner(chat_id, message_id, user_id)
        except telebot.apihelper.ApiTelegramException as e:
            if "message is not modified" in str(e).lower():
                pass
            else:
                msg = bot.send_message(chat_id, text, reply_markup=reply_markup)
                set_message_owner(chat_id, msg.message_id, user_id)
        except Exception as e:
            # اگر ویرایش ناموفق بود، پیام جدید بفرست
            msg = bot.send_message(chat_id, text, reply_markup=reply_markup)
            set_message_owner(chat_id, msg.message_id, user_id)
    else:
        msg = bot.send_message(chat_id, text, reply_markup=reply_markup)
        set_message_owner(chat_id, msg.message_id, user_id)

def show_profile(chat_id: int, user_id: int, message_id: Optional[int] = None):
    # بقیه کدهای این تابع همون حالت قبلی باشه...
    user = get_user(user_id)
    if not user:
        return
    buildings = get_buildings(user_id)
    alliance = get_alliance(user_id)
    alliance_name = alliance['name'] if alliance else "ندارد"
    text = (
        f"📊 <b>پروفایل امپراتوری</b>\n"
        f"👤 {get_username_or_name(user)}\n"
        f"🏆 سطح: {user['level']} | تجربه: {format_number(user['exp'])}\n"
        f"👥 اتحاد: {alliance_name}\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"💰 سکه: {format_number(user['coins'])}\n"
        f"🪵 چوب: {format_number(user['wood'])}\n"
        f"🪨 سنگ: {format_number(user['stone'])}\n"
        f"🍖 غذا: {format_number(user['food'])}\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"⚔️ سربازان کل: {format_number(user['total_soldiers'])}\n"
        f"🗡️ قدرت حمله: {format_number(user['attack_power'])}\n"
        f"🛡️ قدرت دفاع: {format_number(user['defense_power'])}\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"🏰 سطح دیوار: {buildings['wall_level']}\n"
        f"🏗️ سطح سربازخانه: {buildings['barracks_level']}\n"
        f"🌾 سطح مزرعه: {buildings['farm_level']}\n"
        f"🪚 سطح کارخانه چوب: {buildings['sawmill_level']}\n"
        f"⛏️ سطح معدن سنگ: {buildings['quarry_level']}\n"
        f"🏦 سطح خزانه: {buildings['treasury_level']}\n"
        f"📦 سطح انبار: {buildings['storage_level']}\n"
    )
    
    # دکمه تغییر نام اینجا اضافه شده
    markup = build_inline_keyboard([
        [inline_btn("✏️ تغییر نام امپراطوری (۲۰۰ سکه)", "change_empire_name", "danger")],
        [inline_btn("🔄 به‌روزرسانی", "profile", "primary")],
        [inline_btn("🏠 بازگشت", "main_menu", "primary")]
    ])

    edit_or_send(chat_id, message_id, text, markup, user_id)



def show_resources(chat_id: int, user_id: int, message_id: Optional[int] = None):
    ensure_production(user_id)
    user = get_user(user_id)
    if not user:
        return
    text = (
        f"🏭 <b>منابع فعلی</b>\n"
        f"💰 سکه: {format_number(user['coins'])}\n"
        f"🪵 چوب: {format_number(user['wood'])}\n"
        f"🪨 سنگ: {format_number(user['stone'])}\n"
        f"🍖 غذا: {format_number(user['food'])}\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"تولید خودکار هر ساعت:\n"
        f"💰 سکه: {BASE_PRODUCTION_COINS + get_buildings(user_id)['treasury_level'] * 10}\n"
        f"🪵 چوب: {BASE_PRODUCTION_WOOD + get_buildings(user_id)['sawmill_level'] * 8}\n"
        f"🪨 سنگ: {BASE_PRODUCTION_STONE + get_buildings(user_id)['quarry_level'] * 7}\n"
        f"🍖 غذا: {BASE_PRODUCTION_FOOD + get_buildings(user_id)['farm_level'] * 12}\n"
    )
    markup = build_inline_keyboard([
        [inline_btn("🔄 به‌روزرسانی", "collect_resources", "primary")],
        [inline_btn("🏠 بازگشت", "main_menu", "info")]
    ])
    edit_or_send(chat_id, message_id, text, markup, user_id)

def show_army_menu(chat_id: int, user_id: int, message_id: Optional[int] = None):
    user = get_user(user_id)
    if not user:
        return
    units = get_army_units(user_id)
    text = f"🏰 <b>ارتش شما</b>\n\n"
    if not units:
        text += "هنوز هیچ واحدی استخدام نکرده‌اید.\n"
    else:
        for unit_type, data in units.items():
            info = UNIT_TYPES.get(unit_type)
            if info:
                text += (
                    f"• {info['name']} (سطح {data['level']}) — تعداد: {format_number(data['count'])}\n"
                    f"  🗡️ حمله: {info['attack']} | 🛡️ دفاع: {info['defense']}\n"
                )
    text += f"\n⚔️ کل قدرت حمله: {format_number(user['attack_power'])}\n"
    text += f"🛡️ کل قدرت دفاع: {format_number(user['defense_power'])}\n\n"
    text += "برای استخدام سرباز انتخاب کنید:\n"
    
    rows = []
    for unit_type, info in UNIT_TYPES.items():
        cost_str = f"💰 {info['cost']['coins']} | 🪵 {info['cost']['wood']} | 🪨 {info['cost']['stone']} | 🍖 {info['cost']['food']}"
        rows.append([inline_btn(f"➕ {info['name']} (🗡️{info['attack']} 🛡️{info['defense']})", f"recruit_{unit_type}", "success")])
        rows.append([inline_btn(cost_str, f"recruit_{unit_type}", "primary")])
    rows.append([inline_btn("🏠 بازگشت", "main_menu", "primary")])
    markup = build_inline_keyboard(rows)

    edit_or_send(chat_id, message_id, text, markup, user_id)


def show_building_menu(chat_id: int, user_id: int, message_id: Optional[int] = None):
    user = get_user(user_id)
    if not user:
        return

    buildings = get_buildings(user_id)

    # هزینه پایه هر ساختمان
    BUILDING_COSTS = {
        'wall': 200,
        'barracks': 300,
        'farm': 150,
        'sawmill': 180,
        'quarry': 170,
        'treasury': 250,
        'storage': 220
    }

    BUILDING_NAMES = {
        'wall': 'دیوار',
        'barracks': 'سربازخانه',
        'farm': 'مزرعه',
        'sawmill': 'کارخانه چوب',
        'quarry': 'معدن سنگ',
        'treasury': 'خزانه',
        'storage': 'انبار'
    }

    BUILDING_COLUMNS = {
        'wall': 'wall_level',
        'barracks': 'barracks_level',
        'farm': 'farm_level',
        'sawmill': 'sawmill_level',
        'quarry': 'quarry_level',
        'treasury': 'treasury_level',
        'storage': 'storage_level'
    }

    text = (
        "⬆️ <b>ارتقای ساختمان‌ها</b>\n\n"
        f"💰 موجودی سکه: <b>{format_number(user['coins'])}</b>\n"
        "━━━━━━━━━━━━━━━━\n"
    )

    rows = []

    for building, column in BUILDING_COLUMNS.items():
        level = int(buildings.get(column, 1))
        base_cost = BUILDING_COSTS[building]

        # هزینه بر اساس سطح فعلی
        cost = base_cost * level

        text += (
            f"🏗️ <b>{BUILDING_NAMES[building]}</b>\n"
            f"   📊 سطح فعلی: {level}\n"
            f"   💰 هزینه ارتقا: {format_number(cost)} سکه\n"
            "━━━━━━━━━━━━━━━━\n"
        )

        rows.append([
            inline_btn(
                f"⬆️ {BUILDING_NAMES[building]} | {format_number(cost)} 💰",
                f"upgrade_{building}",
                "success"
            )
        ])

    rows.append([
        inline_btn("🏠 بازگشت به منوی اصلی", "main_menu", "primary")
    ])

    markup = build_inline_keyboard(rows)

    edit_or_send(
        chat_id,
        message_id,
        text,
        markup,
        user_id
    )


def show_attack_menu(chat_id: int, user_id: int, message_id: Optional[int] = None):
    text = "⚔️ <b>حمله و غارت</b>\n\n"
    text += "انتخاب کنید:\n"
    rows = [
        [inline_btn("🏰 حمله به قلعه متروکه", "castle_list", "danger")],
        [inline_btn("👤 حمله به بازیکن (PvP)", "pvp_attack_prompt", "danger")],
        [inline_btn("🏠 بازگشت", "main_menu", "info")]
    ]
    markup = build_inline_keyboard(rows)
    edit_or_send(chat_id, message_id, text, markup, user_id)

def show_market_menu(chat_id: int, user_id: int, message_id: Optional[int] = None):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM market_offers WHERE active = 1 ORDER BY id DESC LIMIT 10")
        offers = cur.fetchall()
        text = "🛒 <b>بازار جهانی</b>\n\n"
        if offers:
            for o in offers:
                o = dict(o)
                if o['item_type'] == 'alliance':
                    cur.execute("SELECT name FROM alliances WHERE id=?", (o['quantity'],))
                    al_res = cur.fetchone()
                    al_name = al_res['name'] if al_res else "اتحاد نامشخص"
                    text += f"🏰 فروش اتحاد: {al_name} (آیدی آفر: {o['id']}) — {format_number(o['price_coins'])} سکه\n"
                else:
                    text += f"🔹 {o['item_type']} x{format_number(o['quantity'])} (آیدی آفر: {o['id']}) — {format_number(o['price_coins'])} سکه\n"
        else:
            text += "هیچ آفری فعال نیست.\n"
        rows = [
            [inline_btn("➕ ایجاد آفر فروش", "market_create", "success")],
            [inline_btn("🛍️ خرید آفر", "market_buy", "success")],
            [inline_btn("🛠 مدیریت آفرهای من", "market_manage", "warning")],
            [inline_btn("🏠 بازگشت", "main_menu", "primary")]
        ]
        markup = build_inline_keyboard(rows)
        edit_or_send(chat_id, message_id, text, markup, user_id)

def show_alliance_menu(chat_id: int, user_id: int, message_id: Optional[int] = None):
    user = get_user(user_id)
    alliance = get_alliance(user_id)
    text = "👥 <b>اتحاد</b>\n\n"
    if alliance:
        members = get_alliance_members(alliance['id'])
        capacity = alliance.get('capacity', 5)
        text += f"نام اتحاد: {alliance['name']}\n"
        text += f"سطح: {alliance['level']}\n"
        text += f"ظرفیت: {len(members)}/{capacity}\n"
        text += f"خزانه: سکه {format_number(alliance['treasury_coins'])} | چوب {format_number(alliance['treasury_wood'])} | سنگ {format_number(alliance['treasury_stone'])} | غذا {format_number(alliance['treasury_food'])}\n\n"
        text += "اعضای اتحاد:\n"
        for m in members[:10]:
            text += f"• {get_username_or_name(m)} (سطح {m['level']}) — نقش: {m['role']}\n"
            
        rows = [
            [inline_btn("💰 اهدا به خزانه", "alliance_donate", "success"), inline_btn("📤 برداشت از خزانه", "alliance_withdraw", "danger")],
            [inline_btn("💬 ارسال پیام به اتحاد", "alliance_chat", "primary"), inline_btn("🌍 نقشه مناطق", "alliance_territory", "primary")]
        ]
        if alliance['leader_id'] == user_id:
            rows.append([inline_btn("⚙️ تنظیم نقش اعضا", "alliance_roles", "warning"), inline_btn("⬆️ افزایش ظرفیت (2000 سکه)", "alliance_upgrade_capacity", "success")])
            rows.append([inline_btn("👢 اخراج عضو", "alliance_kick", "danger"), inline_btn("🛒 فروش اتحاد", "alliance_sell", "success")])
            rows.append([inline_btn("⚔️ جنگ قبیله‌ای", "alliance_war_prompt", "danger"), inline_btn("🕊 درخواست صلح", "alliance_peace_prompt", "success")])
            rows.append([inline_btn("💔 شکستن پیمان صلح", "alliance_break_peace", "danger")])
            rows.append([inline_btn("❌ انحلال اتحاد", "alliance_delete_req", "danger")])
        else:
            rows.append([inline_btn("🚪 خروج از اتحاد", "alliance_leave", "danger")])
        rows.append([inline_btn("📜 اتحادهای در صلح", "alliance_peace_list", "primary")])
            
        rows.append([inline_btn("🏠 بازگشت", "main_menu", "info")])
    else:
        text += "شما عضو هیچ اتحادی نیستید.\n"
        rows = [
            [inline_btn("➕ ساخت اتحاد (10,000 سکه)", "alliance_create", "success")],
            [inline_btn("📋 فهرست اتحادها", "alliance_list", "primary")],
            [inline_btn("🏠 بازگشت", "main_menu", "info")]
        ]
    markup = build_inline_keyboard(rows)
    edit_or_send(chat_id, message_id, text, markup, user_id)



def show_gacha_menu(chat_id: int, user_id: int, message_id: Optional[int] = None):
    user = get_user(user_id)
    generals = json.loads(user.get('generals_json') or '[]')
    text = "🎁 <b>ژنرال‌ها (Gacha)</b>\n\n"
    text += f"سکه شما: {format_number(user['coins'])}\n"
    text += "هر بار احضار ۲۰۰ سکه هزینه دارد.\n\n"
    if generals:
        text += "ژنرال‌های شما:\n"
        for g in generals:
            text += f"• {g['name']} (سطح {g.get('level', 1)}) — {g['bonus_type']} +{int(g['bonus_value']*100)}%\n"
    else:
        text += "هنوز ژنرالی احضار نکرده‌اید.\n"
    rows = [
        [inline_btn("🎲 احضار ژنرال (۲۰۰ سکه)", "gacha_roll", "danger")],
        [inline_btn("🏠 بازگشت", "main_menu", "info")]
    ]
    markup = build_inline_keyboard(rows)
    edit_or_send(chat_id, message_id, text, markup, user_id)

def show_world_boss_menu(chat_id: int, user_id: int, message_id: Optional[int] = None):
    boss = get_active_world_boss()
    text = "🌍 <b>باس جهانی</b>\n\n"
    if boss:
        text += f"🐉 {boss['name']}\n"
        text += f"❤️ جان: {format_number(boss['hp'])} / {format_number(boss['max_hp'])}\n"
        text += "با اعزام سرباز به باس آسیب بزنید.\n"
        rows = [
            [inline_btn("⚔️ اعزام ۱۰۰ سرباز", "boss_attack_100", "danger")],
            [inline_btn("⚔️ اعزام ۵۰۰ سرباز", "boss_attack_500", "danger")],
            [inline_btn("⚔️ اعزام ۱۰۰۰ سرباز", "boss_attack_1000", "danger")],
            [inline_btn("🏠 بازگشت", "main_menu", "info")]
        ]
    else:
        text += "در حال حاضر باس فعالی وجود ندارد.\n"
        rows = [[inline_btn("🏠 بازگشت", "main_menu", "info")]]
    markup = build_inline_keyboard(rows)
    edit_or_send(chat_id, message_id, text, markup, user_id)

def show_battle_reports(chat_id: int, user_id: int, message_id: Optional[int] = None):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT * FROM battles WHERE attacker_id = ? OR defender_id = ? ORDER BY id DESC LIMIT 5
        """, (user_id, user_id))
        battles = cur.fetchall()
        text = "📜 <b>گزارش‌های جنگ اخیر</b>\n\n"
        if not battles:
            text += "هنوز جنگی انجام نداده‌اید.\n"
        for b in battles:
            b = dict(b)
            winner = "شما" if b['winner_id'] == user_id else "دشمن"
            text += (
                f"⚔️ نبرد #{b['id']}\n"
                f"👤 شما: {b['attacker_id'] if b['attacker_id'] == user_id else b['defender_id']}\n"
                f"🏆 برنده: {winner}\n"
                f"💰 غنائم: {format_number(b['coins_looted'])} سکه، {format_number(b['wood_looted'])} چوب\n"
                f"🗡️ تلفات شما: {json.loads(b['attacker_losses_json']) if b['attacker_id'] == user_id else json.loads(b['defender_losses_json'])}\n"
                f"━━━━━━━━━━━━━━━━\n"
            )
        markup = build_inline_keyboard([[inline_btn("🏠 بازگشت", "main_menu", "info")]])
        edit_or_send(chat_id, message_id, text, markup, user_id)

def show_bounty_menu(chat_id: int, user_id: int, message_id: Optional[int] = None):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM bounties WHERE active = 1 ORDER BY id DESC LIMIT 10")
        bounties = cur.fetchall()
        text = "💰 <b>جایزه‌بگیر</b>\n\n"
        if bounties:
            for b in bounties:
                b = dict(b)
                target = get_user_raw(b['target_id'])
                if target:
                    text += f"🎯 {target['empire_name']} — جایزه: {format_number(b['amount_coins'])} سکه (آیدی: {b['id']})\n"
        else:
            text += "هیچ جایزه‌ای فعال نیست.\n"
        rows = [
            [inline_btn("🎯 قرار دادن جایزه", "bounty_place", "warning")],
            [inline_btn("⚔️ دریافت جایزه", "bounty_claim", "success")],
            [inline_btn("🛠 مدیریت جایزه‌های من", "bounty_manage", "warning")],
            [inline_btn("🏠 بازگشت", "main_menu", "primary")]
        ]
        markup = build_inline_keyboard(rows)
        edit_or_send(chat_id, message_id, text, markup, user_id)

def buy_market_offer(buyer_id: int, offer_id: int) -> bool:
    buyer = get_user(buyer_id)
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM market_offers WHERE id = ? AND active = 1", (offer_id,))
        offer = cur.fetchone()

    if not buyer or not offer or buyer['coins'] < offer['price_coins']:
        return False
    offer = dict(offer)
    
    # خرید اتحاد از بازار
    if offer['item_type'] == 'alliance':
        alliance_id = offer['quantity']
        if buyer.get('alliance_id'): 
            return False

        update_user(buyer_id, coins=buyer['coins'] - offer['price_coins'])
        seller = get_user_raw(offer['seller_id'])
        if seller: update_user(offer['seller_id'], coins=seller['coins'] + offer['price_coins'])
        
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("UPDATE alliances SET leader_id = ? WHERE id = ?", (buyer_id, alliance_id))
            cur.execute("UPDATE alliance_members SET role = 'member' WHERE alliance_id = ? AND user_id = ?", (alliance_id, offer['seller_id']))
            cur.execute("INSERT INTO alliance_members (alliance_id, user_id, role, joined_at) VALUES (?, ?, 'leader', ?)", (alliance_id, buyer_id, int(time.time())))
        update_user(buyer_id, alliance_id=alliance_id)
    else:
        # خرید منابع عادی
        update_user(buyer_id, coins=buyer['coins'] - offer['price_coins'])
        seller = get_user_raw(offer['seller_id'])
        if seller: update_user(offer['seller_id'], coins=seller['coins'] + offer['price_coins'])
        update_user(buyer_id, **{offer['item_type']: buyer[offer['item_type']] + offer['quantity']})

    with get_connection() as conn:
        conn.execute("UPDATE market_offers SET active = 0 WHERE id = ?", (offer_id,))
    return True

def process_recruit_quantity(message, unit_type):
    user_id = message.from_user.id
    try:
        count = int(message.text)
        if count <= 0: raise ValueError
    except:
        bot.send_message(message.chat.id, "❌ تعداد وارد شده نامعتبر است. فقط عدد ارسال کن!")
        return
    
    user = get_user(user_id)
    cost = UNIT_TYPES[unit_type]['cost']
    total_cost = {k: v * count for k, v in cost.items()}
    
    if (user['coins'] < total_cost['coins'] or user['wood'] < total_cost['wood'] or
        user['stone'] < total_cost['stone'] or user['food'] < total_cost['food']):
        bot.send_message(message.chat.id, "❌ منابع شما برای استخدام این تعداد سرباز کافی نیست.")
        return
        
    update_user(user_id,
                coins=user['coins'] - total_cost['coins'],
                wood=user['wood'] - total_cost['wood'],
                stone=user['stone'] - total_cost['stone'],
                food=user['food'] - total_cost['food'])
    update_army_unit(user_id, unit_type, count_delta=count)
    update_army_power_fields(user_id)
    add_exp(user_id, count * 10, message.chat.id)
    bot.send_message(message.chat.id, f"✅ تعداد {format_number(count)} {UNIT_TYPES[unit_type]['name']} با موفقیت استخدام شد.", reply_markup=main_menu(user_id))

def process_alliance_withdraw(message):
    try:
        parts = message.text.split()
        resource = parts[0].lower()
        amount = int(parts[1])
        user_id = message.from_user.id

        if is_war_locked(user_id):
            bot.send_message(message.chat.id, "❌ در حین جنگ نمی‌توانید تراکنش انجام دهید.")
            return

        alliance = get_alliance(user_id)
        if not alliance or resource not in ['coins', 'wood', 'stone', 'food']: return
        
        treasury_field = f"treasury_{resource}"
        if alliance[treasury_field] < amount:
            bot.send_message(message.chat.id, "❌ خزانه اتحاد این مقدار منبع را ندارد.")
            return
        
        with get_connection() as conn:
            conn.execute(f"UPDATE alliances SET {treasury_field} = {treasury_field} - ? WHERE id = ?", (amount, alliance['id']))
        
            user = get_user(user_id)
            update_user(user_id, **{resource: user[resource] + amount})
            bot.send_message(message.chat.id, f"✅ مقدار {format_number(amount)} {resource} از خزانه برداشت شد.", reply_markup=main_menu(user_id))
    except:
        bot.send_message(message.chat.id, "❌ فرمت نامعتبر است.")

def process_alliance_chat(message):
    user_id = message.from_user.id
    user = get_user(user_id)
    alliance = get_alliance(user_id)
    if not alliance: return
    
    members = get_alliance_members(alliance['id'])
    msg_text = f"📨 <b>پیام اتحاد از طرف {get_username_or_name(user)}:</b>\n\n{message.text}"
    
    count = 0
    for m in members:
        if m['user_id'] != user_id:
            try:
                bot.send_message(m['user_id'], msg_text, parse_mode='HTML')
                count += 1
            except:
                pass
    bot.send_message(message.chat.id, f"✅ پیام شما با موفقیت به {count} عضو اتحاد ارسال شد.", reply_markup=main_menu(user_id))

def process_alliance_roles(message):
    user_id = message.from_user.id
    alliance = get_alliance(user_id)
    if not alliance or alliance['leader_id'] != user_id: return
    try:
        parts = message.text.split(maxsplit=1)
        emp_name = parts[0]
        role = parts[1]
        target_user = get_user_by_empire_name(emp_name)
        if not target_user:
            bot.send_message(message.chat.id, "❌ کاربری با این نام پیدا نشد.")
            return
        
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM alliance_members WHERE user_id = ? AND alliance_id = ?", (target_user['user_id'], alliance['id']))
            if not cur.fetchone():
                bot.send_message(message.chat.id, "❌ این کاربر در اتحاد شما عضو نیست.")
                return
            
            if target_user['user_id'] == user_id:
                bot.send_message(message.chat.id, "❌ شما لیدر اتحاد هستید و نمی‌توانید نقش خود را تغییر دهید.")
                return
            
            conn.execute("UPDATE alliance_members SET role = ? WHERE user_id = ? AND alliance_id = ?", (role, target_user['user_id'], alliance['id']))
            bot.send_message(message.chat.id, f"✅ نقش امپراطوری {emp_name} با موفقیت به «{role}» تغییر یافت.", reply_markup=main_menu(user_id))
    except:
        bot.send_message(message.chat.id, "❌ فرمت نامعتبر است.")

def process_alliance_sell(message):
    try:
        price = int(message.text)
        if price <= 0: raise ValueError
        user_id = message.from_user.id
        alliance = get_alliance(user_id)
        if not alliance or alliance['leader_id'] != user_id: return
        with get_connection() as conn:
            conn.execute("INSERT INTO market_offers (seller_id, item_type, quantity, price_coins, created_at) VALUES (?, 'alliance', ?, ?, ?)", (user_id, alliance['id'], price, int(time.time())))
            bot.send_message(message.chat.id, "✅ اتحاد شما با موفقیت در بازار جهانی برای فروش قرار گرفت!", reply_markup=main_menu(user_id))
    except:
        bot.send_message(message.chat.id, "❌ قیمت نامعتبر است.")

def process_alliance_kick(message):
    user_id = message.from_user.id
    alliance = get_alliance(user_id)
    if not alliance or alliance['leader_id'] != user_id: return
    target_name = message.text.strip()
    target = get_user_by_empire_name(target_name)
    if not target or target['alliance_id'] != alliance['id']:
        bot.send_message(message.chat.id, "❌ این کاربر در اتحاد شما نیست.")
        return
    if target['user_id'] == user_id:
        bot.send_message(message.chat.id, "❌ نمی‌توانی خودت را اخراج کنی!")
        return
    with get_connection() as conn:
        conn.execute("DELETE FROM alliance_members WHERE user_id = ?", (target['user_id'],))
        conn.execute("UPDATE users SET alliance_id = NULL WHERE user_id = ?", (target['user_id'],))
        bot.send_message(message.chat.id, f"✅ کاربر {target_name} از اتحاد اخراج شد.", reply_markup=main_menu(user_id))



def get_alliance_by_name(name: str) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM alliances WHERE name = ?", (name,))
        row = cur.fetchone()
        return dict(row) if row else None

def process_alliance_war(message):
    attacker_id = message.from_user.id
    target_alliance_name = message.text.strip()

    attacker_alliance = get_alliance(attacker_id)
    if not attacker_alliance or attacker_alliance['leader_id'] != attacker_id:
        return

    target_alliance = get_alliance_by_name(target_alliance_name)
    if not target_alliance:
        bot.send_message(message.chat.id, "❌ اتحادی با این نام یافت نشد.")
        return

    if attacker_alliance['id'] == target_alliance['id']:
        bot.send_message(message.chat.id, "❌ نمی‌توانید به اتحاد خودتان حمله کنید!")
        return

    if is_in_peace(attacker_alliance['id'], target_alliance['id']):
        bot.send_message(message.chat.id, "❌ شما با این اتحاد در صلح هستید! برای حمله ابتدا باید پیمان صلح را بشکنید.")
        return

    # Clear old volunteers just in case
    with get_connection() as conn:
        conn.execute("DELETE FROM war_volunteers WHERE alliance_id IN (?, ?)", (attacker_alliance['id'], target_alliance['id']))

    markup = build_inline_keyboard([[inline_btn("⚔️ شرکت در جنگ", "join_war", "danger")]])

    # Broadcast to attacker
    att_members = get_alliance_members(attacker_alliance['id'])
    for m in att_members:
        set_war_lock(m['user_id'], 1)
        try: bot.send_message(m['user_id'], f"⚔️ لیدر اعلان جنگ علیه اتحاد {target_alliance_name} کرده است! شما 60 ثانیه فرصت دارید داوطلب شوید.", reply_markup=markup)
        except: pass

    # Broadcast to defender
    def_members = get_alliance_members(target_alliance['id'])
    for m in def_members:
        set_war_lock(m['user_id'], 1)
        try: bot.send_message(m['user_id'], f"⚠️ هشدار! اتحاد {attacker_alliance['name']} به ما اعلان جنگ داده است! 60 ثانیه برای اعزام نیرو و دفاع فرصت دارید.", reply_markup=markup)
        except: pass

    timer = threading.Timer(60.0, execute_alliance_war, args=[attacker_alliance['id'], target_alliance['id'], message.chat.id, target_alliance['leader_id']])
    timer.start()

def execute_alliance_war(att_alliance_id: int, def_alliance_id: int, att_chat_id: int, def_leader_id: int):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT user_id FROM war_volunteers WHERE alliance_id = ?", (att_alliance_id,))
        att_vols = [r['user_id'] for r in cur.fetchall()]
        cur.execute("SELECT user_id FROM war_volunteers WHERE alliance_id = ?", (def_alliance_id,))
        def_vols = [r['user_id'] for r in cur.fetchall()]

        # Free war locks
        conn.execute("UPDATE users SET is_in_war = 0 WHERE alliance_id IN (?, ?)", (att_alliance_id, def_alliance_id))
        conn.execute("DELETE FROM war_volunteers WHERE alliance_id IN (?, ?)", (att_alliance_id, def_alliance_id))

    att_total_attack = 0
    att_total_defense = 0
    att_users = []

    for uid in att_vols:
        u = get_user_raw(uid)
        if u:
            att_total_attack += u['attack_power']
            att_total_defense += u['defense_power']
            att_users.append(u)

    def_total_attack = 0
    def_total_defense = 0
    def_users = []

    for uid in def_vols:
        u = get_user_raw(uid)
        if u:
            def_total_attack += u['attack_power']
            def_total_defense += u['defense_power']
            def_users.append(u)

    report = "⚔️ <b>گزارش نبرد مجموع (Total War)</b>\n\n"
    report += f"⚔️ قدرت حمله مهاجمین: {format_number(att_total_attack)}\n"
    report += f"🛡 قدرت دفاع مدافعین: {format_number(def_total_defense)}\n"
    report += "\n━━━━━━━━━━━━━━━━\n"

    # Evaluate Winner
    winner_is_att = None
    if att_total_attack > def_total_defense:
        winner_is_att = True
    elif def_total_attack > att_total_defense:
        winner_is_att = False

    if winner_is_att is True:
        report += "🎉 <b>اتحاد مهاجم پیروز شد!</b>\n"
        with get_connection() as conn:
            conn.execute("UPDATE alliances SET level = level + 1 WHERE id = ?", (att_alliance_id,))

        # Distribute loot (basic algorithm: winner takes 10% of losers coins distributed proportionally)
        total_loot = sum([int(u['coins'] * 0.1) for u in def_users])
        for du in def_users:
            update_user(du['user_id'], coins=int(du['coins']*0.9))

        for au in att_users:
            add_exp(au['user_id'], 500, au['user_id'])
            if att_total_attack > 0:
                share = au['attack_power'] / att_total_attack
                my_loot = int(total_loot * share)
                update_user(au['user_id'], coins=au['coins'] + my_loot)

    elif winner_is_att is False:
        report += "🛡 <b>اتحاد مدافع با موفقیت دفاع کرد!</b>\n"
        with get_connection() as conn:
            conn.execute("UPDATE alliances SET level = level + 1 WHERE id = ?", (def_alliance_id,))

        total_loot = sum([int(u['coins'] * 0.1) for u in att_users])
        for au in att_users:
            update_user(au['user_id'], coins=int(au['coins']*0.9))

        for du in def_users:
            add_exp(du['user_id'], 500, du['user_id'])
            if def_total_defense > 0:
                share = du['defense_power'] / def_total_defense
                my_loot = int(total_loot * share)
                update_user(du['user_id'], coins=du['coins'] + my_loot)
    else:
        report += "🤝 <b>نبرد مساوی شد! (بدون غنیمت)</b>\n"

    # Broadcast report
    for uid in att_vols + def_vols:
        try: bot.send_message(uid, report)
        except: pass


def show_leaderboard(chat_id: int, user_id: int, message_id: Optional[int] = None):
    with get_connection() as conn:
        cur = conn.cursor()

        # 1. Top 5 Empires (Order by level DESC, attack_power DESC)
        cur.execute("SELECT user_id, empire_name, level, attack_power FROM users WHERE banned = 0 ORDER BY level DESC, attack_power DESC LIMIT 5")
        top_empires = cur.fetchall()

        # 2. User's own empire rank
        cur.execute("SELECT COUNT(*) + 1 FROM users WHERE banned = 0 AND (level > (SELECT level FROM users WHERE user_id = ?) OR (level = (SELECT level FROM users WHERE user_id = ?) AND attack_power > (SELECT attack_power FROM users WHERE user_id = ?)))", (user_id, user_id, user_id))
        user_rank = cur.fetchone()[0]

        # 3. Top 5 Alliances
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
            text += f"{i+1}. {emp['empire_name']} (سطح: {emp['level']} | قدرت حمله: {format_number(emp['attack_power'])})\n"

        text += "\n👥 <b>اتحادهای برتر:</b>\n"
        for i, al in enumerate(top_alliances):
            # count members
            cur.execute("SELECT COUNT(*) FROM alliance_members WHERE alliance_id = ?", (al['id'],))
            m_count = cur.fetchone()[0]
            text += f"{i+1}. {al['name']} (سطح: {al['level']} | اعضا: {m_count})\n"

        text += "\n━━━━━━━━━━━━━━━━\n"
        text += f"🏅 رتبه امپراطوری شما: {user_rank}\n"
        text += f"🎖 رتبه اتحاد شما: {alliance_rank_text}\n"

        markup = build_inline_keyboard([[inline_btn("🏠 بازگشت", "main_menu", "info")]])
        edit_or_send(chat_id, message_id, text, markup, user_id)


def is_in_peace(alliance_id_1: int, alliance_id_2: int) -> bool:
    if not alliance_id_1 or not alliance_id_2: return False
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM peace_treaties WHERE (alliance_1_id = ? AND alliance_2_id = ?) OR (alliance_1_id = ? AND alliance_2_id = ?)", (alliance_id_1, alliance_id_2, alliance_id_2, alliance_id_1))
        return bool(cur.fetchone())

def show_alliance_peace_list(chat_id: int, user_id: int, message_id: Optional[int] = None):
    alliance = get_alliance(user_id)
    if not alliance: return
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT alliance_1_id, alliance_2_id FROM peace_treaties WHERE alliance_1_id = ? OR alliance_2_id = ?", (alliance['id'], alliance['id']))
        treaties = cur.fetchall()

        text = "📜 <b>اتحادهای در صلح</b>\n\n"
        if not treaties:
            text += "شما با هیچ اتحادی پیمان صلح ندارید.\n"
        else:
            for t in treaties:
                other_id = t['alliance_2_id'] if t['alliance_1_id'] == alliance['id'] else t['alliance_1_id']
                cur.execute("SELECT name FROM alliances WHERE id = ?", (other_id,))
                row = cur.fetchone()
                if row:
                    text += f"🕊 {row['name']}\n"

    markup = build_inline_keyboard([[inline_btn("🏠 بازگشت", "main_menu", "info")]])
    edit_or_send(chat_id, message_id, text, markup, user_id)

def process_alliance_peace(message):
    req_user_id = message.from_user.id
    target_name = message.text.strip()

    req_alliance = get_alliance(req_user_id)
    if not req_alliance or req_alliance['leader_id'] != req_user_id: return

    target_alliance = get_alliance_by_name(target_name)
    if not target_alliance:
        bot.send_message(message.chat.id, "❌ اتحادی با این نام یافت نشد.")
        return

    if req_alliance['id'] == target_alliance['id']:
        bot.send_message(message.chat.id, "❌ نمی‌توانید با خودتان صلح کنید!")
        return

    if is_in_peace(req_alliance['id'], target_alliance['id']):
        bot.send_message(message.chat.id, "⚠️ شما از قبل با این اتحاد در صلح هستید.")
        return

    target_leader_id = target_alliance['leader_id']
    markup = build_inline_keyboard([
        [inline_btn("✅ پذیرش صلح", f"peace_accept_{req_alliance['id']}_{target_alliance['id']}", "success")],
        [inline_btn("❌ رد صلح", f"peace_reject_{req_alliance['id']}_{target_alliance['id']}", "danger")]
    ])

    try:
        bot.send_message(target_leader_id, f"🕊 لیدر اتحاد {req_alliance['name']} درخواست پیمان صلح داده است. آیا می‌پذیرید؟", reply_markup=markup)
        bot.send_message(message.chat.id, "✅ درخواست صلح برای لیدر اتحاد مقابل ارسال شد.")
    except:
        bot.send_message(message.chat.id, "❌ خطا در ارسال پیام به لیدر مقابل.")

def accept_peace_treaty(call_id: str, chat_id: int, user_id: int, req_alliance_id: int, target_alliance_id: int, message_id: int):
    target_alliance = get_alliance(user_id)
    if not target_alliance or target_alliance['id'] != target_alliance_id or target_alliance['leader_id'] != user_id:
        bot.answer_callback_query(call_id, "شما مجاز به این کار نیستید.", show_alert=True)
        return

    if not is_in_peace(req_alliance_id, target_alliance_id):
        with get_connection() as conn:
            conn.execute("INSERT INTO peace_treaties (alliance_1_id, alliance_2_id, created_at) VALUES (?, ?, ?)", (req_alliance_id, target_alliance_id, int(time.time())))

    bot.edit_message_text("✅ پیمان صلح برقرار شد.", chat_id=chat_id, message_id=message_id)

def process_alliance_break_peace(message):
    req_user_id = message.from_user.id
    target_name = message.text.strip()

    req_alliance = get_alliance(req_user_id)
    if not req_alliance or req_alliance['leader_id'] != req_user_id: return

    target_alliance = get_alliance_by_name(target_name)
    if not target_alliance:
        bot.send_message(message.chat.id, "❌ اتحادی با این نام یافت نشد.")
        return

    if is_in_peace(req_alliance['id'], target_alliance['id']):
        with get_connection() as conn:
            conn.execute("DELETE FROM peace_treaties WHERE (alliance_1_id = ? AND alliance_2_id = ?) OR (alliance_1_id = ? AND alliance_2_id = ?)", (req_alliance['id'], target_alliance['id'], target_alliance['id'], req_alliance['id']))
        bot.send_message(message.chat.id, f"💔 پیمان صلح با {target_name} شکسته شد.")
    else:
        bot.send_message(message.chat.id, "⚠️ شما با این اتحاد در صلح نیستید.")




@bot.message_handler(func=lambda m: m.text == "فعال" and m.chat.type in ['group', 'supergroup'])
def activate_group(message):
    if not is_admin_user(message.from_user.id):
        bot.reply_to(message, "⛔️ فقط ادمین مجاز به فعال‌سازی گروه است.")
        return
    exclusive_chat = get_exclusive_chat()
    if exclusive_chat is not None and exclusive_chat != message.chat.id:
        bot.reply_to(message, "⚠️ این ربات قبلاً در گروه دیگری فعال شده است.")
        return
    set_exclusive_chat(message.chat.id)
    bot.reply_to(message, "✅ این گروه به عنوان گروه اختصاصی ربات فعال شد.")


@bot.message_handler(func=lambda m: m.text.strip().lower() == "راهنما")
def game_guide(message):
    text = "📖 <b>راهنمای بازی امپراطوری</b>\n\n"
    text += "🏰 <b>ارتش و نبرد:</b>\nشما می‌توانید با استفاده از منابع خود، واحدهای مختلفی استخدام کنید. ارتش شما برای حمله به باس جهانی، تسخیر قلعه‌ها و نبردهای PvP استفاده می‌شود. تاکتیک‌ها کلید پیروزی هستند.\n\n"
    text += "👥 <b>اتحاد:</b>\nبا ساخت یا عضویت در اتحاد، می‌توانید در جنگ‌های قبیله‌ای (Clan Wars) شرکت کنید، از خزانه اشتراکی استفاده کرده و به کمک هم مناطق روی نقشه را تسخیر کنید.\n\n"
    text += "🛒 <b>بازار:</b>\nدر بازار می‌توانید منابع یا حتی اتحاد خود را به فروش بگذارید و منابع مورد نیازتان را بخرید.\n\n"
    text += "💰 <b>جایزه‌بگیر (Bounty):</b>\nمی‌توانید روی سر بازیکنان قوی جایزه بگذارید، و یا با شکست دادن آن‌ها جایزه‌ها را تصاحب کنید.\n\n"
    text += "🌍 <b>باس جهانی:</b>\nباس جهانی رویدادی است که در آن تمام بازیکنان می‌توانند با اعزام نیرو به آن آسیب وارد کنند و پاداش عظیم بگیرند."

    bot.send_message(message.chat.id, text)

@bot.message_handler(content_types=['text'])
def global_text_handler(message):
    user_id = message.from_user.id
    text = message.text.strip().lower()

    # Cancellation check
    if text in ['لغو', 'انصراف', '❌ لغو', 'cancel']:
        clear_user_state(user_id)
        bot.send_message(message.chat.id, "✅ عملیات لغو شد.", reply_markup=main_menu(user_id))
        return

    user = get_user(user_id)
    if not user or not user.get('current_action'):
        return

    action = user['current_action']
    data_str = user.get('action_data')

    import json
    action_data = {}
    if data_str:
        try:
            action_data = json.loads(data_str)
        except:
            pass

    # Clear state first so they don't get stuck if it crashes
    clear_user_state(user_id)

    # Route to appropriate function
    if action == 'process_change_empire_name':
        process_change_empire_name(message)
    elif action == 'process_admin_force_join':
        process_admin_force_join(message)
    elif action == 'process_empire_name':
        process_empire_name(message)
    elif action == 'process_broadcast':
        process_broadcast(message)
    elif action == 'process_admin_user_manage':
        process_admin_user_manage(message)
    elif action == 'process_admin_economy':
        process_admin_economy(message)
    elif action == 'process_admin_ban':
        process_admin_ban(message)
    elif action == 'process_admin_unban':
        process_admin_unban(message)
    elif action == 'process_admin_balance_step1':
        process_admin_balance_step1(message)
    elif action == 'process_admin_balance_step2':
        process_admin_balance_step2(message, action_data.get('arg'))
    elif action == 'process_admin_wipe':
        process_admin_wipe(message)
    elif action == 'process_recruit_quantity':
        process_recruit_quantity(message, action_data.get('arg'))
    elif action == 'process_market_create':
        process_market_create(message)
    elif action == 'process_market_buy':
        process_market_buy(message)
    elif action == 'process_pvp_attack':
        process_pvp_attack(message)
    elif action == 'process_alliance_war':
        process_alliance_war(message)
    elif action == 'process_alliance_peace':
        process_alliance_peace(message)
    elif action == 'process_alliance_break_peace':
        process_alliance_break_peace(message)
    elif action == 'process_alliance_create':
        process_alliance_create(message)
    elif action == 'process_alliance_withdraw':
        process_alliance_withdraw(message)
    elif action == 'process_alliance_chat':
        process_alliance_chat(message)
    elif action == 'process_alliance_roles':
        process_alliance_roles(message)
    elif action == 'process_alliance_sell':
        process_alliance_sell(message)
    elif action == 'process_alliance_kick':
        process_alliance_kick(message)
    elif action == 'process_alliance_donate':
        process_alliance_donate(message)
    elif action == 'process_bounty_place':
        process_bounty_place(message)
    elif action == 'process_bounty_claim':
        process_bounty_claim(message)
    else:
        # Unknown action
        pass


# ============================================================
# 🔘 هندلرهای کالبک
# ============================================================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call: types.CallbackQuery):
    try:
        user_id = call.from_user.id
        chat_id = call.message.chat.id
        data = call.data
                # بررسی عضویت اجباری برای کلیک دکمه‌ها
        if not check_user_joined(user_id):
            channel = get_force_join_channel()
            bot.answer_callback_query(call.id, "🛑 لطفاً ابتدا در کانال عضو شوید!", show_alert=True)
            bot.send_message(chat_id, f"🛑 برای استفاده از دکمه‌های ربات، باید در کانال زیر عضو شوید:\n{channel}")
            return

        # تغییر نام امپراطوری
        if data == 'change_empire_name':
            user = get_user(user_id)
            if user['coins'] < 200:
                bot.answer_callback_query(call.id, "❌ برای تغییر نام امپراطوری حداقل ۲۰۰ سکه نیاز داری!", show_alert=True)
                return
            msg = bot.send_message(chat_id, "✏️ برای تغییر نام امپراطوری به ۲۰۰ سکه نیاز دارید. اسم جدید را وارد کنید:")
            set_user_state(user_id, 'process_change_empire_name')
            return

        # فعال‌سازی عضویت اجباری توسط ادمین
        if data == 'admin_force_join' and is_admin_user(user_id):
            msg = bot.send_message(chat_id, "📢 آیدی کانال را برای عضویت اجباری وارد کنید (با @ شروع شود).\nبرای لغو عضویت اجباری، کلمه `لغو` را ارسال کنید:")
            set_user_state(user_id, 'process_admin_force_join')
            return
        message_id = call.message.message_id

        # بررسی مالکیت دکمه
        owner = get_message_owner(chat_id, message_id)
        if owner is not None and owner != user_id:
            bot.answer_callback_query(call.id, "⛔️ این دکمه مال شما نیست.", show_alert=True)
            return

        # 👑 پنل مدیریت
        if data == 'admin_panel' and is_admin_user(user_id):
            edit_or_send(chat_id, message_id, "👑 <b>پنل مدیریت</b>", admin_main_menu(), user_id)
            return
        if data == 'admin_stats' and is_admin_user(user_id):
            show_admin_stats(chat_id, message_id, user_id)
            return
        if data == 'admin_broadcast' and is_admin_user(user_id):
            msg = bot.send_message(chat_id, "📨 متن پیام همگانی را ارسال کنید:")
            set_user_state(user_id, 'process_broadcast')
            return
        if data == 'admin_user_manage' and is_admin_user(user_id):
            msg = bot.send_message(chat_id, "👤 نام امپراطوری کاربر را ارسال کنید:")
            set_user_state(user_id, 'process_admin_user_manage')
            return
        if data == 'admin_economy' and is_admin_user(user_id):
            msg = bot.send_message(chat_id, "💰 نام امپراطوری کاربر را بفرستید:")
            set_user_state(user_id, 'process_admin_economy')
            return
        if data == 'admin_events' and is_admin_user(user_id):
            spawn_castles(2)
            spawn_world_boss(1)
            bot.answer_callback_query(call.id, "✅ رویدادها ایجاد شدند")
            return
        if data == 'admin_ban' and is_admin_user(user_id):
            msg = bot.send_message(chat_id, "🔨 نام امپراطوری کاربر برای بن را بفرستید:")
            set_user_state(user_id, 'process_admin_ban')
            return
        if data == 'admin_unban' and is_admin_user(user_id):
            msg = bot.send_message(chat_id, "🔓 نام امپراطوری کاربر را برای خارج کردن از بن وارد کنید:")
            set_user_state(user_id, 'process_admin_unban')
            return
            
        if data == 'admin_change_balance' and is_admin_user(user_id):
            msg = bot.send_message(chat_id, "⚖️ نام امپراطوری کاربر را برای تغییر موجودی وارد کنید:")
            set_user_state(user_id, 'process_admin_balance_step1')
            return

        if data == 'admin_wipe' and is_admin_user(user_id):
            msg = bot.send_message(chat_id, "🧹 نام امپراطوری کاربر برای پاکسازی کامل را بفرستید:")
            set_user_state(user_id, 'process_admin_wipe')
            return
        if data == 'admin_exit' and is_admin_user(user_id):
            bot.delete_message(chat_id, message_id)
            with get_connection() as conn:
                conn.execute("DELETE FROM message_owners WHERE chat_id = ? AND message_id = ?", (chat_id, message_id))
            return

        # 🔄 بازگشت به منوی اصلی
        if data == 'main_menu':
            user = get_user(user_id)
            if not user:
                return
            text = (
                f"🏰 <b>منوی اصلی</b>\n"
                f"امپراطوری: {user['empire_name']}\n"
                f"سکه: {format_number(user['coins'])} | چوب: {format_number(user['wood'])} | سنگ: {format_number(user['stone'])} | غذا: {format_number(user['food'])}\n"
            )
            edit_or_send(chat_id, message_id, text, main_menu(user_id), user_id)
            return

        # 📊 پروفایل
        if data == 'profile':
            show_profile(chat_id, user_id, message_id)
            return

        # 🏭 منابع
        if data == 'collect_resources':
            show_resources(chat_id, user_id, message_id)
            return

        # 🏰 ارتش
        if data == 'army_menu':
            show_army_menu(chat_id, user_id, message_id)
            return

                # استخدام واحدها (اصلاح شده برای گرفتن تعداد)
        if data.startswith('recruit_'):
            unit_type = data.replace('recruit_', '')
            msg = bot.send_message(chat_id, "🔢 چند سرباز می‌خواهی استخدام کنی؟ (تعداد را به عدد بفرست):")
            set_user_state(user_id, 'process_recruit_quantity', {'arg': unit_type})
            return


        # ⬆️ ساختمان‌ها
        if data == 'building_menu':
            show_building_menu(chat_id, user_id, message_id)
            return
                          # ارتقای ساختمان‌ها (اصلاح باگ و کسر مستقیم از دیتابیس)
        if data.startswith('upgrade_'):
            building = data.replace('upgrade_', '', 1)

            BUILDING_COLUMNS = {
                'wall': 'wall_level', 'barracks': 'barracks_level', 'farm': 'farm_level',
                'sawmill': 'sawmill_level', 'quarry': 'quarry_level', 'treasury': 'treasury_level', 'storage': 'storage_level'
            }
            BUILDING_NAMES = {
                'wall': 'دیوار', 'barracks': 'سربازخانه', 'farm': 'مزرعه',
                'sawmill': 'کارخانه چوب', 'quarry': 'معدن سنگ', 'treasury': 'خزانه', 'storage': 'انبار'
            }
            BUILDING_COSTS = {
                'wall': 200, 'barracks': 300, 'farm': 150,
                'sawmill': 180, 'quarry': 170, 'treasury': 250, 'storage': 220
            }

            if building not in BUILDING_COLUMNS:
                bot.answer_callback_query(call.id, "❌ ساختمان نامعتبر است.", show_alert=True)
                return

            user = get_user(user_id)
            if not user:
                bot.answer_callback_query(call.id, "❌ اطلاعات کاربر پیدا نشد.", show_alert=True)
                return

            buildings = get_buildings(user_id)
            column = BUILDING_COLUMNS[building]
            current_level = int(buildings.get(column, 1))

            base_cost = BUILDING_COSTS[building]
            cost = base_cost * current_level

            if user['coins'] < cost:
                bot.answer_callback_query(
                    call.id,
                    f"❌ سکه کافی نیست!\n💰 موجودی: {format_number(user['coins'])}\n💰 نیاز: {format_number(cost)}",
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
                f"✅ {BUILDING_NAMES[building]} ارتقا یافت!\n📊 سطح جدید: {new_level}\n💰 هزینه: {format_number(cost)} سکه",
                show_alert=True
            )
            show_building_menu(chat_id, user_id, message_id)
            return

        # ⚔️ حمله
        if data == 'attack_menu':
            show_attack_menu(chat_id, user_id, message_id)
            return
        if data == 'castle_list':
            show_castle_list(chat_id, user_id, message_id)
            return
        if data.startswith('castle_attack_'):
            castle_id = int(data.replace('castle_attack_', ''))
            attack_castle(chat_id, user_id, castle_id, message_id)
            return
        if data == 'pvp_attack_prompt':
            msg = bot.send_message(chat_id, "⚔️ لطفاً نام امپراطوری حریف را برای حمله وارد کنید:")
            set_user_state(user_id, 'process_pvp_attack')
            return

        # 🛒 بازار

        if data == 'market_manage':
            with get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT * FROM market_offers WHERE seller_id = ? AND active = 1", (user_id,))
                my_offers = cur.fetchall()

            text = "🛠 <b>آفرهای شما در بازار</b>\n\n"
            rows = []
            if not my_offers:
                text += "شما هیچ آفر فعالی ندارید."
            else:
                text += "برای لغو هر آفر روی دکمه مربوطه کلیک کنید:\n"
                for o in my_offers:
                    o = dict(o)
                    if o['item_type'] == 'alliance':
                        label = f"لغو آفر فروش اتحاد (آیدی: {o['id']})"
                    else:
                        label = f"لغو آفر {o['item_type']} (آیدی: {o['id']})"
                    rows.append([inline_btn(label, f"market_cancel_{o['id']}", "danger")])

            rows.append([inline_btn("🏠 بازگشت", "market_menu", "primary")])
            edit_or_send(chat_id, message_id, text, build_inline_keyboard(rows), user_id)
            return

        if data.startswith('market_cancel_'):
            offer_id = int(data.replace('market_cancel_', ''))
            with get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT * FROM market_offers WHERE id = ? AND seller_id = ? AND active = 1", (offer_id, user_id))
                offer = cur.fetchone()

                if offer:
                    offer = dict(offer)
                    conn.execute("UPDATE market_offers SET active = 0 WHERE id = ?", (offer_id,))
                    if offer['item_type'] != 'alliance':
                        user = get_user_raw(user_id)
                        update_user(user_id, **{offer['item_type']: user[offer['item_type']] + offer['quantity']})

                    bot.answer_callback_query(call.id, "✅ آفر شما لغو شد و منابع/اتحاد بازگردانده شد.", show_alert=True)
                else:
                    bot.answer_callback_query(call.id, "❌ آفر یافت نشد یا از قبل لغو شده است.", show_alert=True)

            # Show market manage again
            call.data = 'market_manage'
            callback_handler(call)
            return

        if data == 'market_menu':
            show_market_menu(chat_id, user_id, message_id)
            return
        if data == 'market_create':
            msg = bot.send_message(chat_id, "برای ایجاد آفر فروش، فرمت زیر را ارسال کنید:\nنوع منبع (coins/wood/stone/food) | تعداد | قیمت سکه\nمثال: wood 100 500")
            set_user_state(user_id, 'process_market_create')
            return
        if data == 'market_buy':
            msg = bot.send_message(chat_id, "شناسه آفر را ارسال کنید:")
            set_user_state(user_id, 'process_market_buy')
            return

        # 👥 اتحاد
        if data == 'alliance_menu':
            show_alliance_menu(chat_id, user_id, message_id)
            return
        if data == 'alliance_create':
            msg = bot.send_message(chat_id, "نام اتحاد خود را ارسال کنید:")
            set_user_state(user_id, 'process_alliance_create')
            return
        if data == 'alliance_list':
            show_alliance_list(chat_id, user_id, message_id)
            return

        if data.startswith('alliance_join_'):
            alliance_id = int(data.replace('alliance_join_', ''))
            with get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT * FROM alliances WHERE id = ?", (alliance_id,))
                alliance = cur.fetchone()
            
                if not alliance:
                    bot.answer_callback_query(call.id, "❌ این اتحاد یافت نشد.", show_alert=True)
                    return
                
                members = get_alliance_members(alliance_id)
                if len(members) >= alliance.get('capacity', 5):
                    bot.answer_callback_query(call.id, "❌ ظرفیت این اتحاد پر شده است!", show_alert=True)
                    return
                
                if join_alliance(user_id, alliance_id):
                    bot.answer_callback_query(call.id, "✅ با موفقیت به اتحاد پیوستی!", show_alert=True)
                    show_alliance_menu(chat_id, user_id, message_id)
                else:
                    bot.answer_callback_query(call.id, "❌ شما قبلاً در یک اتحاد عضو شده‌اید.", show_alert=True)
                return

        if data == 'alliance_withdraw':
            msg = bot.send_message(chat_id, "📤 نوع منبع و مقدار را برای برداشت ارسال کنید (coins/wood/stone/food):\nمثال: coins 500")
            set_user_state(user_id, 'process_alliance_withdraw')
            return
            
        if data == 'alliance_chat':
            msg = bot.send_message(chat_id, "💬 پیام خود را بنویسید تا برای تمام اعضای اتحاد ارسال شود:")
            set_user_state(user_id, 'process_alliance_chat')
            return
        if data == 'alliance_peace_list':
            show_alliance_peace_list(chat_id, user_id, message_id)
            return

        if data == 'alliance_peace_prompt':
            alliance = get_alliance(user_id)
            if alliance and alliance['leader_id'] == user_id:
                bot.send_message(chat_id, "🕊 لطفاً نام اتحادی که می‌خواهید با آن صلح کنید را وارد کنید:")
                set_user_state(user_id, 'process_alliance_peace')
            return

        if data == 'alliance_break_peace':
            alliance = get_alliance(user_id)
            if alliance and alliance['leader_id'] == user_id:
                bot.send_message(chat_id, "💔 لطفاً نام اتحادی که می‌خواهید پیمان صلح با آن را بشکنید وارد کنید:")
                set_user_state(user_id, 'process_alliance_break_peace')
            return

        if data.startswith('peace_accept_'):
            parts = data.split('_')
            req_alliance_id = int(parts[2])
            target_alliance_id = int(parts[3])
            accept_peace_treaty(call.id, chat_id, user_id, req_alliance_id, target_alliance_id, message_id)
            return

        if data.startswith('peace_reject_'):
            bot.edit_message_text("❌ درخواست صلح رد شد.", chat_id=chat_id, message_id=message_id)
            return


        if data == 'join_war':
            alliance = get_alliance(user_id)
            if not alliance: return
            with get_connection() as conn:
                try:
                    conn.execute("INSERT INTO war_volunteers (user_id, alliance_id, role) VALUES (?, ?, 'member')", (user_id, alliance['id']))
                    bot.answer_callback_query(call.id, "✅ شما با موفقیت به عنوان داوطلب ثبت نام کردید!", show_alert=True)
                except sqlite3.IntegrityError:
                    bot.answer_callback_query(call.id, "⚠️ شما قبلاً داوطلب شده‌اید.", show_alert=True)
            return

        if data == 'alliance_war_prompt':
            alliance = get_alliance(user_id)
            if alliance and alliance['leader_id'] == user_id:
                bot.send_message(chat_id, "⚔️ جنگ قبیله‌ای!\nلطفاً نام اتحادی که می‌خواهید به آن حمله کنید را وارد کنید:")
                set_user_state(user_id, 'process_alliance_war')
            else:
                bot.answer_callback_query(call.id, "فقط لیدر می‌تواند اعلان جنگ کند.", show_alert=True)
            return

        if data == 'alliance_roles':
            msg = bot.send_message(chat_id, "⚙️ نام امپراطوری عضو مورد نظر و نقش او را وارد کن:\nمثال: MyEmpire ژنرال")
            set_user_state(user_id, 'process_alliance_roles')
            return
            
        if data == 'alliance_upgrade_capacity':
            user = get_user(user_id)
            alliance = get_alliance(user_id)
            if not alliance or alliance['leader_id'] != user_id: return
            
            if user['coins'] < 2000:
                bot.answer_callback_query(call.id, "❌ برای افزایش ظرفیت به 2000 سکه نیاز داری!", show_alert=True)
                return
                
            update_user(user_id, coins=user['coins'] - 2000)
            new_capacity = alliance.get('capacity', 5) + 1
            
            with get_connection() as conn:
                conn.execute("UPDATE alliances SET capacity = ? WHERE id = ?", (new_capacity, alliance['id']))
            
                bot.answer_callback_query(call.id, f"✅ ظرفیت اتحاد به {new_capacity} افزایش یافت!", show_alert=True)
                show_alliance_menu(chat_id, user_id, message_id)
                return

        if data == 'alliance_sell':
            msg = bot.send_message(chat_id, "🛒 قیمت فروش اتحاد را به سکه وارد کن:")
            set_user_state(user_id, 'process_alliance_sell')
            return

        if data == 'alliance_kick':
            msg = bot.send_message(chat_id, "👢 نام امپراطوری عضوی که می‌خواهی اخراج کنی را بفرست:")
            set_user_state(user_id, 'process_alliance_kick')
            return
            
        if data == 'alliance_leave':
            alliance = get_alliance(user_id)
            if alliance:
                if alliance['leader_id'] == user_id:
                    bot.answer_callback_query(call.id, "❌ لیدر نمی‌تواند خارج شود. ابتدا اتحاد را منحل کرده یا انتقال دهید.", show_alert=True)
                else:
                    with get_connection() as conn:
                        conn.execute("DELETE FROM alliance_members WHERE alliance_id = ? AND user_id = ?", (alliance['id'], user_id))
                        conn.execute("UPDATE users SET alliance_id = NULL WHERE user_id = ?", (user_id,))
                    bot.answer_callback_query(call.id, "✅ با موفقیت از اتحاد خارج شدید.", show_alert=True)
                    show_alliance_menu(chat_id, user_id, message_id)
            return

        if data == 'alliance_delete_req':
            markup = build_inline_keyboard([
                [inline_btn("بله، حذف کن", "alliance_delete_yes", "danger")],
                [inline_btn("خیر", "alliance_menu", "success")]
            ])
            edit_or_send(chat_id, message_id, "⚠️ آیا از انحلال کامل اتحاد مطمئن هستید؟ این کار غیرقابل بازگشت است!", markup, user_id)
            return
            
        if data == 'alliance_delete_yes':
            alliance = get_alliance(user_id)
            if alliance and alliance['leader_id'] == user_id:
                with get_connection() as conn:
                    # Clear orphaned data first
                    conn.execute("DELETE FROM market_offers WHERE item_type = 'alliance' AND quantity = ?", (alliance['id'],))
                    conn.execute("DELETE FROM peace_treaties WHERE alliance_1_id = ? OR alliance_2_id = ?", (alliance['id'], alliance['id']))
                    conn.execute("DELETE FROM alliance_members WHERE alliance_id = ?", (alliance['id'],))
                    conn.execute("UPDATE users SET alliance_id = NULL WHERE alliance_id = ?", (alliance['id'],))
                    conn.execute("DELETE FROM alliances WHERE id = ?", (alliance['id'],))
                edit_or_send(chat_id, message_id, "✅ اتحاد شما با موفقیت منحل شد.", build_inline_keyboard([[inline_btn("🏠 بازگشت", "main_menu", "info")]]), user_id)
            return

        if data == 'alliance_donate':
            msg = bot.send_message(chat_id, "نوع منبع و مقدار را ارسال کنید (coins/wood/stone/food):\nمثال: coins 500")
            set_user_state(user_id, 'process_alliance_donate')
            return
        if data == 'alliance_territory':
            show_alliance_territory(chat_id, user_id, message_id)
            return

        if data == 'territory_attack':
            show_territory_attack_menu(chat_id, user_id, message_id)
            return

        if data.startswith('attack_region_'):
            region_id = data.replace('attack_region_', '')
            user = get_user(user_id)
            alliance = get_alliance(user_id)
            
            if not alliance or region_id not in TERRITORY_REGIONS: 
                return
                
            units = get_army_units(user_id)
            if sum(u['count'] for u in units.values()) < 10:
                bot.answer_callback_query(call.id, "❌ فرمانده، برای حمله به منطقه حداقل ۱۰ سرباز نیاز داری!", show_alert=True)
                return

            region_data = TERRITORY_REGIONS[region_id]
            user_power = calculate_army_power(user_id)
            win_chance = user_power / max(1, user_power + region_data['defense'])
            
            if random.random() < win_chance:
                territory = json.loads(alliance.get('territory', '{}'))
                r_name = region_data['name']
                
                with get_connection() as conn:
                    cur = conn.cursor()
                    cur.execute("SELECT captures, level FROM alliances WHERE id = ?", (alliance['id'],))
                    al_data = cur.fetchone()
                
                    captures = (al_data['captures'] or 0) + 1
                    a_level = al_data['level']
                    req_captures = a_level * 5
                
                    if captures >= req_captures:
                        a_level += 1
                        captures = 0
                        reward = a_level * 5000
                        cur.execute("UPDATE alliances SET level = ?, captures = ?, treasury_coins = treasury_coins + ?, treasury_wood = treasury_wood + ?, treasury_stone = treasury_stone + ?, treasury_food = treasury_food + ? WHERE id = ?",
                                    (a_level, captures, reward, reward, reward, reward, alliance['id']))
                        text = f"🎉 <b>پیروزی سترگ!</b>\n\nمحافظان <b>{r_name}</b> شکست خوردند.\n⭐ <b>سطح اتحاد ارتقا یافت! (سطح {a_level})</b>\n💰 مقدار {format_number(reward)} از تمام منابع به عنوان پاداش لول‌آپ به خزانه واریز شد!"
                    else:
                        cur.execute("UPDATE alliances SET captures = ? WHERE id = ?", (captures, alliance['id']))
                        text = f"🎉 <b>پیروزی!</b>\n\nمحافظان <b>{r_name}</b> شکست خوردند.\nپیشرفت تا ارتقای سطح اتحاد: {captures}/{req_captures}"
                
                    if r_name in territory:
                        territory[r_name]['level'] += 1
                    else:
                        territory[r_name] = {'level': 1}
                    
                    cur.execute("UPDATE alliances SET territory = ? WHERE id = ?", (json.dumps(territory, ensure_ascii=False), alliance['id']))
                
                    for unit_type, u_data in units.items():
                        loss = int(u_data['count'] * 0.10)
                        if loss > 0: update_army_unit(user_id, unit_type, count_delta=-loss)
                    update_army_power_fields(user_id)
                    add_exp(user_id, 200, chat_id)
            else:
                for unit_type, u_data in units.items():
                    loss = int(u_data['count'] * 0.30)
                    if loss > 0: update_army_unit(user_id, unit_type, count_delta=-loss)
                update_army_power_fields(user_id)
                text = f"❌ <b>شکست سخت!</b>\n\nمحافظان <b>{region_data['name']}</b> بسیار قدرتمند بودند. ۳۰٪ از ارتش شما در این نبرد از بین رفت."
                
            edit_or_send(chat_id, message_id, text, build_inline_keyboard([[inline_btn("🏠 بازگشت به اتحاد", "alliance_menu")]]), user_id)
            return
        # ============================================================
        # پیش‌فرض
        bot.answer_callback_query(call.id)

    except Exception as e:
        import traceback
        traceback.print_exc()
        try:
            bot.answer_callback_query(call.id, "⚠️ خطایی رخ داد. لطفاً دوباره تلاش کنید.", show_alert=True)
        except:
            pass

# ============================================================
# 🏰 توابع حمله (ویرایش شده برای ویرایش همان پیام)
# ============================================================
def show_castle_list(chat_id: int, user_id: int, message_id: Optional[int] = None):
    castles = get_active_castles()
    text = "🏰 <b>قلعه‌های متروکه فعال</b>\n\n"
    if not castles:
        text += "در حال حاضر قلعه متروکه‌ای وجود ندارد.\n"
        rows = [[inline_btn("🏠 بازگشت", "main_menu", "info")]]
    else:
        for c in castles[:10]:
            text += (
                f"🏰 {c['name']}\n"
                f"👥 مدافعان: {c['soldiers']}\n"
                f"💰 غنائم: {c['reward_coins']} سکه، {c['reward_wood']} چوب، {c['reward_stone']} سنگ، {c['reward_food']} غذا\n"
                f"━━━━━━━━━━━━━━━━\n"
            )
        rows = []
        for c in castles[:10]:
            rows.append([inline_btn(f"⚔️ حمله به {c['name']}", f"castle_attack_{c['id']}", "danger")])
        rows.append([inline_btn("🏠 بازگشت", "main_menu", "primary")])
        
    # این خط جا افتاده بود
    markup = build_inline_keyboard(rows)
    edit_or_send(chat_id, message_id, text, markup, user_id)

def attack_castle(chat_id: int, user_id: int, castle_id: int, message_id: int):
    castle = get_castle(castle_id)
    if not castle:
        text = "❌ این قلعه دیگر وجود ندارد."
        edit_or_send(chat_id, message_id, text, build_inline_keyboard([
            [inline_btn("🏠 بازگشت", "main_menu", "info")]
        ]), user_id)
        return
    user = get_user(user_id)
    if not user:
        return
    if user['total_soldiers'] < 5:
        text = "❌ حداقل ۵ سرباز برای حمله نیاز دارید."
        edit_or_send(chat_id, message_id, text, build_inline_keyboard([
            [inline_btn("🏠 بازگشت", "main_menu", "info")]
        ]), user_id)
        return
    total_power = user['attack_power']
    castle_power = castle['soldiers'] * 10
    win_chance = total_power / (total_power + castle_power) if total_power + castle_power > 0 else 0.5
    if random.random() < win_chance:
        reward_coins = random.randint(castle['reward_coins'] // 2, castle['reward_coins'])
        reward_wood = random.randint(castle['reward_wood'] // 2, castle['reward_wood'])
        reward_stone = random.randint(castle['reward_stone'] // 2, castle['reward_stone'])
        reward_food = random.randint(castle['reward_food'] // 2, castle['reward_food'])
        update_user(user_id,
                    coins=user['coins'] + reward_coins,
                    wood=user['wood'] + reward_wood,
                    stone=user['stone'] + reward_stone,
                    food=user['food'] + reward_food,
                    last_castle_attack=int(time.time()))
        units = get_army_units(user_id)
        for unit_type, data in units.items():
            loss = int(data['count'] * 0.05)
            if loss > 0:
                update_army_unit(user_id, unit_type, count_delta=-loss)
        update_army_power_fields(user_id)
        delete_castle(castle_id)
        text = (f"🎉 <b>پیروزی!</b>\n"
                f"غنائم به دست آمده:\n"
                f"💰 {format_number(reward_coins)} سکه\n"
                f"🪵 {format_number(reward_wood)} چوب\n"
                f"🪨 {format_number(reward_stone)} سنگ\n"
                f"🍖 {format_number(reward_food)} غذا\n")
    else:
        units = get_army_units(user_id)
        for unit_type, data in units.items():
            loss = int(data['count'] * 0.15)
            if loss > 0:
                update_army_unit(user_id, unit_type, count_delta=-loss)
        update_army_power_fields(user_id)
        text = "❌ <b>شکست خوردید!</b> بخشی از نیروهایتان تلف شدند."
    edit_or_send(chat_id, message_id, text, build_inline_keyboard([
        [inline_btn("🏠 بازگشت", "main_menu", "info")]
    ]), user_id)

def process_pvp_attack(message):
    attacker_id = message.from_user.id
    target_empire_name = message.text.strip()

    attacker = get_user_raw(attacker_id)
    if attacker and now() - attacker['last_pvp_attack'] < 3600:
        remaining = 3600 - (now() - attacker['last_pvp_attack'])
        mins, secs = divmod(remaining, 60)
        bot.send_message(message.chat.id, f"⏳ فرمانده، نیروهای شما در حال استراحت هستند! لطفاً {mins} دقیقه و {secs} ثانیه دیگر برای حمله مجدد صبر کنید.")
        return

    target_user = get_user_by_empire_name(target_empire_name)
    if not target_user:
        bot.send_message(message.chat.id, "❌ کاربری با این نام یافت نشد.")
        return
        
    defender_id = target_user['user_id']
    if attacker_id == defender_id:
        bot.send_message(message.chat.id, "❌ نمی‌توانید به خودتان حمله کنید!")
        return
        

    target_alliance = get_alliance(defender_id)
    attacker_alliance = get_alliance(attacker_id)
    if target_alliance and attacker_alliance and is_in_peace(target_alliance['id'], attacker_alliance['id']):
        bot.send_message(message.chat.id, "❌ اتحاد شما با اتحاد این بازیکن در صلح است! نمی‌توانید حمله کنید.")
        return


    bot.send_message(message.chat.id, f"⏳ در حال آماده‌سازی نیروها برای حمله به {target_empire_name}...\nنبرد دقیقاً 1 دقیقه دیگر آغاز می‌شود!")

    try:
        bot.send_message(defender_id, f"⚠️ هشدار! امپراطوری {get_username_or_name(get_user_raw(attacker_id))} به شما اعلان جنگ داده است!\nنبرد دقیقاً 1 دقیقه دیگر آغاز می‌شود. نیروهای خود را آماده کنید!")
    except Exception as e:
        print(f"Failed to send warning to defender {defender_id}: {e}")

    set_war_lock(attacker_id, 1)
    set_war_lock(defender_id, 1)
    timer = threading.Timer(60.0, execute_delayed_pvp, args=[attacker_id, defender_id, message.chat.id])
    timer.start()

def execute_delayed_pvp(attacker_id: int, defender_id: int, chat_id: int):
    set_war_lock(attacker_id, 0)
    set_war_lock(defender_id, 0)
    update_user(attacker_id, last_pvp_attack=now())
    result = simulate_battle(attacker_id, defender_id)
    if result['winner'] is None:
        try:
            bot.send_message(chat_id, "❌ نبرد قابل انجام نیست.")
        except: pass
        return

    winner_name = get_username_or_name(get_user_raw(result['winner']))
    attacker_losses = ", ".join([f"{UNIT_TYPES[k]['name']}: {v}" for k, v in result['attacker_losses'].items()]) if result['attacker_losses'] else "بدون تلفات"
    defender_losses = ", ".join([f"{UNIT_TYPES[k]['name']}: {v}" for k, v in result['defender_losses'].items()]) if result['defender_losses'] else "بدون تلفات"

    text = (
        f"⚔️ <b>نتیجه نبرد</b>\n"
        f"👤 مهاجم: {get_username_or_name(get_user_raw(attacker_id))}\n"
        f"👤 مدافع: {get_username_or_name(get_user_raw(defender_id))}\n"
        f"🏆 برنده: {winner_name}\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"🗡️ تلفات مهاجم: {attacker_losses}\n"
        f"🛡️ تلفات مدافع: {defender_losses}\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"💰 سکه غارت شده: {format_number(result['coins_looted'])}\n"
        f"🪵 چوب غارت شده: {format_number(result['wood_looted'])}\n"
        f"🪨 سنگ غارت شده: {format_number(result['stone_looted'])}\n"
        f"🍖 غذای غارت شده: {format_number(result['food_looted'])}\n"
    )

    try:
        bot.send_message(chat_id, "⚔️ نبرد انجام شد!\n\n" + text)
    except: pass

    try:
        bot.send_message(defender_id, "⚔️ نبرد انجام شد!\n\n" + text)
    except: pass

def recruit_unit(chat_id: int, user_id: int, unit_type: str, message_id: int):
    if unit_type not in UNIT_TYPES:
        text = "❌ واحد نامعتبر است."
        edit_or_send(chat_id, message_id, text, build_inline_keyboard([
            [inline_btn("🏠 بازگشت", "main_menu", "info")]
        ]), user_id)
        return
    user = get_user(user_id)
    if not user:
        return
    cost = UNIT_TYPES[unit_type]['cost']
    if (user['coins'] < cost['coins'] or user['wood'] < cost['wood'] or
        user['stone'] < cost['stone'] or user['food'] < cost['food']):
        text = "❌ منابع کافی برای استخدام این واحد ندارید."
        edit_or_send(chat_id, message_id, text, build_inline_keyboard([
            [inline_btn("🏠 بازگشت", "main_menu", "info")]
        ]), user_id)
        return
    update_user(user_id,
                coins=user['coins'] - cost['coins'],
                wood=user['wood'] - cost['wood'],
                stone=user['stone'] - cost['stone'],
                food=user['food'] - cost['food'])
    update_army_unit(user_id, unit_type, count_delta=1)
    update_army_power_fields(user_id)
    text = f"✅ یک {UNIT_TYPES[unit_type]['name']} استخدام شد."
    edit_or_send(chat_id, message_id, text, build_inline_keyboard([
        [inline_btn("🏰 ارتش", "army_menu", "primary")],
        [inline_btn("🏠 بازگشت", "main_menu", "info")]
    ]), user_id)



# ============================================================
# 👥 توابع اتحاد (ویرایش همان پیام)
# ============================================================
def show_alliance_list(chat_id: int, user_id: int, message_id: Optional[int] = None):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM alliances ORDER BY id DESC LIMIT 10")
        alliances = cur.fetchall()
        text = "📋 <b>فهرست اتحادها</b>\n\n"
        if not alliances:
            text += "اتحادی وجود ندارد.\n"
        
        rows = []
        for a in alliances:
            a = dict(a)
            member_count = len(get_alliance_members(a['id']))
            capacity = a.get('capacity', 5)
            text += f"• {a['name']} (ظرفیت: {member_count}/{capacity})\n"
        
            # دکمه جوین فقط اگر ظرفیت پر نشده باشد ساخته می‌شود
            if member_count < capacity:
                rows.append([inline_btn(f"➕ عضویت در {a['name']}", f"alliance_join_{a['id']}", "success")])
            
        rows.append([inline_btn("🏠 بازگشت", "main_menu", "primary")])
        markup = build_inline_keyboard(rows)
        edit_or_send(chat_id, message_id, text, markup, user_id)



def show_alliance_territory(chat_id: int, user_id: int, message_id: Optional[int] = None):
    alliance = get_alliance(user_id)
    if not alliance:
        text = "❌ شما عضو اتحاد نیستید."
        edit_or_send(chat_id, message_id, text, build_inline_keyboard([
            [inline_btn("🏠 بازگشت", "main_menu", "info")]
        ]), user_id)
        return
    territory = json.loads(alliance.get('territory', '{}'))
    text = "🌍 <b>نقشه مناطق اتحاد</b>\n\n"
    if territory:
        for region, data in territory.items():
            text += f"📍 {region}: سطح {data.get('level', 1)}\n"
    else:
        text += "اتحاد شما هنوز منطقه‌ای فتح نکرده است.\n"
    rows = [
        [inline_btn("⚔️ حمله به منطقه", "territory_attack", "danger")],
        [inline_btn("🏠 بازگشت", "main_menu", "info")]
    ]
    markup = build_inline_keyboard(rows)
    edit_or_send(chat_id, message_id, text, markup, user_id)

# ============================================================
# 🗺️ نبرد مناطق اتحاد (Territory Wars)
# ============================================================
TERRITORY_REGIONS = {
    'region_1': {'name': 'روستای مرزی 🏕️', 'defense': 500},
    'region_2': {'name': 'دشت‌های حاصلخیز 🌾', 'defense': 2500},
    'region_3': {'name': 'کوهستان طلایی ⛰️', 'defense': 8000},
    'region_4': {'name': 'دره اژدها 🐉', 'defense': 20000}
}

def show_territory_attack_menu(chat_id: int, user_id: int, message_id: Optional[int] = None):
    alliance = get_alliance(user_id)
    if not alliance: return
    
    text = "🗺️ <b>مناطق قابل تسخیر</b>\n\n"
    text += "فرمانده! ارتش خود را برای تسخیر این مناطق اعزام کنید. در صورت پیروزی، سطح منطقه در اتحاد بالا می‌رود.\n\n"
    
    rows = []
    for r_id, r_data in TERRITORY_REGIONS.items():
        text += f"📍 <b>{r_data['name']}</b> (قدرت محافظان: {format_number(r_data['defense'])})\n"
        rows.append([inline_btn(f"⚔️ حمله به {r_data['name']}", f"attack_region_{r_id}")])
    
    rows.append([inline_btn("🏠 بازگشت به اتحاد", "alliance_menu")])
    edit_or_send(chat_id, message_id, text, build_inline_keyboard(rows), user_id)


# ============================================================
# 👑 توابع پنل مدیریت (ویرایش شده برای نام امپراطوری)
# ============================================================
def show_admin_stats(chat_id: int, message_id: int, user_id: int):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM users")
        total_users = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM users WHERE last_seen > ?", (int(time.time()) - 86400,))
        active_24h = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM alliances")
        total_alliances = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM battles WHERE created_at > ?", (int(time.time()) - 86400,))
        battles_24h = cur.fetchone()[0]
        cur.execute("SELECT SUM(coins) FROM users")
        total_coins = cur.fetchone()[0] or 0
        cur.execute("SELECT SUM(wood) FROM users")
        total_wood = cur.fetchone()[0] or 0
        cur.execute("SELECT SUM(stone) FROM users")
        total_stone = cur.fetchone()[0] or 0
        cur.execute("SELECT SUM(food) FROM users")
        total_food = cur.fetchone()[0] or 0
        text = (
            f"📊 <b>آمار سرور</b>\n"
            f"👥 کاربران کل: {total_users}\n"
            f"🟢 فعال ۲۴ ساعت: {active_24h}\n"
            f"👥 اتحادها: {total_alliances}\n"
            f"⚔️ نبردهای ۲۴ ساعت: {battles_24h}\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"💰 مجموع سکه: {format_number(total_coins)}\n"
            f"🪵 مجموع چوب: {format_number(total_wood)}\n"
            f"🪨 مجموع سنگ: {format_number(total_stone)}\n"
            f"🍖 مجموع غذا: {format_number(total_food)}\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"💵 تورم اقتصاد: {(total_coins / max(1, total_users)):.2f} سکه به ازای هر کاربر\n"
        )
        markup = build_inline_keyboard([[inline_btn("🔙 بازگشت", "admin_panel", "info")]])
        edit_or_send(chat_id, message_id, text, markup, user_id)

def process_broadcast(message):
    if not is_admin_user(message.from_user.id):
        return
    text = message.text
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT user_id FROM users")
        users = cur.fetchall()
        count = 0
        for u in users:
            try:
                bot.send_message(u[0], text)
                count += 1
                time.sleep(0.05)
            except:
                pass
        bot.send_message(message.chat.id, f"✅ پیام به {count} کاربر ارسال شد.")

def process_admin_user_manage(message):
    if not is_admin_user(message.from_user.id):
        return
    name = message.text.strip()
    user = get_user_by_empire_name(name)
    if not user:
        bot.send_message(message.chat.id, "❌ کاربری با این نام یافت نشد.")
        return
    text = (
        f"👤 <b>پروفایل کاربر {user['empire_name']}</b>\n"
        f"آیدی: {user['user_id']}\n"
        f"سطح: {user['level']}\n"
        f"سکه: {format_number(user['coins'])}\n"
        f"چوب: {format_number(user['wood'])}\n"
        f"سنگ: {format_number(user['stone'])}\n"
        f"غذا: {format_number(user['food'])}\n"
        f"سربازان: {format_number(user['total_soldiers'])}\n"
        f"اتحاد: {user.get('alliance_id', 'ندارد')}\n"
        f"بن: {'بله' if user['banned'] else 'خیر'}\n"
    )
    bot.send_message(message.chat.id, text)

def process_admin_economy(message):
    if not is_admin_user(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) < 3:
        bot.send_message(message.chat.id, "❌ فرمت صحیح: نام امپراطوری | منبع | مقدار\n"
                                          "منبع: coins/wood/stone/food\n"
                                          "مثال: MyEmpire coins 1000")
        return
    try:
        empire_name = parts[0]
        resource = parts[1]
        amount = int(parts[2])
        if resource not in ['coins', 'wood', 'stone', 'food']:
            bot.send_message(message.chat.id, "❌ منبع نامعتبر است.")
            return
        user = get_user_by_empire_name(empire_name)
        if not user:
            bot.send_message(message.chat.id, "❌ کاربر یافت نشد.")
            return
        update_user(user['user_id'], **{resource: user[resource] + amount})
        bot.send_message(message.chat.id, f"✅ {amount} {resource} به کاربر {user['empire_name']} اضافه شد.")
    except (ValueError, IndexError):
        bot.send_message(message.chat.id, "❌ فرمت نامعتبر است.")

def process_admin_ban(message):
    if not is_admin_user(message.from_user.id):
        return
    name = message.text.strip()
    user = get_user_by_empire_name(name)
    if not user:
        bot.send_message(message.chat.id, "❌ کاربر یافت نشد.")
        return
    update_user(user['user_id'], banned=1, ban_reason='توسط ادمین')
    bot.send_message(message.chat.id, f"✅ کاربر {user['empire_name']} بن شد.")
    
def process_admin_unban(message):
    if not is_admin_user(message.from_user.id):
        return
    name = message.text.strip()
    user = get_user_by_empire_name(name)
    if not user:
        bot.send_message(message.chat.id, "❌ کاربری با این نام یافت نشد.")
        return
    
    update_user(user['user_id'], banned=0, ban_reason='')
    bot.send_message(message.chat.id, f"✅ کاربر {user['empire_name']} با موفقیت آنبن شد.")

def process_admin_balance_step1(message):
    user_id = message.from_user.id
    if not is_admin_user(user_id):
        return
    name = message.text.strip()
    user = get_user_by_empire_name(name)
    if not user:
        bot.send_message(message.chat.id, "❌ کاربری با این نام یافت نشد.")
        return
        
    msg = bot.send_message(
        message.chat.id, 
        f"✅ کاربر {user['empire_name']} پیدا شد.\n"
        f"لطفاً فرمت تغییر موجودی را وارد کنید:\n"
        f"مثال افزایش: coins +100\n"
        f"مثال کاهش: food -50"
    )
    # پاس دادن آیدی کاربر به مرحله دوم
    set_user_state(user_id, 'process_admin_balance_step2', {'arg': user['user_id']})

def process_admin_balance_step2(message, target_user_id):
    if not is_admin_user(message.from_user.id):
        return
    try:
        parts = message.text.split()
        if len(parts) != 2:
            bot.send_message(message.chat.id, "❌ فرمت نامعتبر است. لطفاً دقیقاً مثل مثال وارد کنید (مثال: coins +100).")
            return
            
        resource = parts[0].lower()
        amount_str = parts[1]
        
        if resource not in ['coins', 'wood', 'stone', 'food']:
            bot.send_message(message.chat.id, "❌ منبع نامعتبر است (فقط coins, wood, stone, food).")
            return
            
        # پایتون به صورت خودکار علامت‌های + و - رو برای تبدیل به عدد تشخیص میده
        amount = int(amount_str) 
        
        target_user = get_user_raw(target_user_id)
        if not target_user:
            bot.send_message(message.chat.id, "❌ خطایی در یافتن کاربر رخ داد.")
            return
            
        # محاسبه موجودی جدید و جلوگیری از منفی شدن موجودی
        new_balance = target_user[resource] + amount
        if new_balance < 0:
            new_balance = 0 
            
        update_user(target_user_id, **{resource: new_balance})
        bot.send_message(message.chat.id, f"✅ موجودی {resource} کاربر {target_user['empire_name']} با موفقیت آپدیت شد.\nموجودی جدید: {format_number(new_balance)}")
        
    except ValueError:
        bot.send_message(message.chat.id, "❌ مقدار وارد شده عدد معتبری نیست.")





def process_broadcast(message):
    if not is_admin_user(message.from_user.id): return
    text = message.text.strip()
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT user_id FROM users")
        users = cur.fetchall()
    count = 0
    for u in users:
        try:
            bot.send_message(u['user_id'], f"📢 پیام مدیریت:\n\n{text}")
            count += 1
        except: pass
    bot.send_message(message.chat.id, f"✅ پیام به {count} نفر ارسال شد.")

def process_admin_user_manage(message):
    if not is_admin_user(message.from_user.id): return
    bot.send_message(message.chat.id, "این بخش در دست توسعه است.")

def process_admin_economy(message):
    if not is_admin_user(message.from_user.id): return
    bot.send_message(message.chat.id, "این بخش در دست توسعه است.")

def process_admin_wipe(message):
    if not is_admin_user(message.from_user.id):
        return
    name = message.text.strip()
    user = get_user_by_empire_name(name)
    if not user:
        bot.send_message(message.chat.id, "❌ کاربر یافت نشد.")
        return
    target_id = user['user_id']
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM army_units WHERE user_id = ?", (target_id,))
        cur.execute("DELETE FROM battles WHERE attacker_id = ? OR defender_id = ?", (target_id, target_id))
        cur.execute("DELETE FROM market_offers WHERE seller_id = ?", (target_id,))
        cur.execute("DELETE FROM bounties WHERE target_id = ? OR issuer_id = ?", (target_id, target_id))
        cur.execute("DELETE FROM boss_attacks WHERE user_id = ?", (target_id,))
        cur.execute("DELETE FROM generals WHERE user_id = ?", (target_id,))
        cur.execute("DELETE FROM tickets WHERE user_id = ?", (target_id,))
        cur.execute("UPDATE users SET coins = 500, wood = 400, stone = 350, food = 600, total_soldiers = 0, "
                    "attack_power = 0, defense_power = 0, level = 1, exp = 0, alliance_id = NULL, "
                    "generals_json = '[]' WHERE user_id = ?", (target_id,))
    bot.send_message(message.chat.id, f"✅ امپراتوری کاربر {user['empire_name']} به طور کامل پاکسازی شد.")

# ============================================================
# 🧾 هندلرهای مرحله‌ای (Next Step) - جایگزینی آیدی با نام امپراطوری
# ============================================================
def process_market_create(message):
    try:
        user_id = message.from_user.id
        if is_war_locked(user_id):
            bot.send_message(message.chat.id, "❌ در حین جنگ نمی‌توانید آفر ایجاد کنید.")
            return

        parts = message.text.split()
        if len(parts) != 3:
            bot.send_message(message.chat.id, "❌ فرمت صحیح: منبع تعداد قیمت\nمثال: wood 100 500")
            return
        item_type = parts[0]
        quantity = int(parts[1])
        price = int(parts[2])
        if item_type not in ['coins', 'wood', 'stone', 'food']:
            bot.send_message(message.chat.id, "❌ منبع نامعتبر است.")
            return
        if create_market_offer(message.from_user.id, item_type, quantity, price):
            bot.send_message(message.chat.id, "✅ آفر فروش ایجاد شد.")
        else:
            bot.send_message(message.chat.id, "❌ منابع کافی ندارید.")
    except (ValueError, IndexError):
        bot.send_message(message.chat.id, "❌ فرمت نامعتبر است.")

def process_market_buy(message):
    try:
        offer_id = int(message.text)
        if buy_market_offer(message.from_user.id, offer_id):
            bot.send_message(message.chat.id, "✅ خرید موفق بود.")
        else:
            bot.send_message(message.chat.id, "❌ خرید ناموفق بود.")
    except ValueError:
        bot.send_message(message.chat.id, "❌ شناسه آفر نامعتبر است.")

def process_alliance_create(message):
    name = message.text.strip()
    user_id = message.from_user.id
    user = get_user(user_id)
    
    if user['coins'] < 10000:
        bot.send_message(message.chat.id, "❌ برای ساخت اتحاد به 10,000 سکه نیاز دارید.")
        return
        
    if create_alliance(user_id, name):
        update_user(user_id, coins=user['coins'] - 10000)
        bot.send_message(message.chat.id, f"✅ اتحاد «{name}» ساخته شد و 10,000 سکه کسر شد.", reply_markup=main_menu(user_id))
    else:
        bot.send_message(message.chat.id, "❌ شما قبلاً عضو یک اتحاد هستید یا خطایی رخ داد.")

def process_alliance_donate(message):
    try:
        user_id = message.from_user.id
        if is_war_locked(user_id):
            bot.send_message(message.chat.id, "❌ در حین جنگ نمی‌توانید تراکنش انجام دهید.")
            return

        parts = message.text.split()
        if len(parts) != 2:
            bot.send_message(message.chat.id, "❌ فرمت: منبع مقدار\nمثال: coins 500")
            return
        resource = parts[0]
        amount = int(parts[1])
        if resource not in ['coins', 'wood', 'stone', 'food']:
            bot.send_message(message.chat.id, "❌ منبع نامعتبر است.")
            return
        if donate_to_alliance(message.from_user.id, resource, amount):
            bot.send_message(message.chat.id, f"✅ {amount} {resource} به خزانه اتحاد اهدا شد.")
        else:
            bot.send_message(message.chat.id, "❌ اهدا ناموفق بود.")
    except (ValueError, IndexError):
        bot.send_message(message.chat.id, "❌ فرمت نامعتبر است.")

def process_bounty_place(message):
    try:
        parts = message.text.split()
        if len(parts) != 2:
            bot.send_message(message.chat.id, "❌ فرمت: نام_امپراطوری مقدار_جایزه\nمثال: MyEmpire 1000")
            return
        empire_name = parts[0]
        amount = int(parts[1])
        target = get_user_by_empire_name(empire_name)
        if not target:
            bot.send_message(message.chat.id, "❌ کاربری با این نام یافت نشد.")
            return
        if place_bounty(target['user_id'], message.from_user.id, amount):
            bot.send_message(message.chat.id, "✅ جایزه روی سر هدف قرار گرفت.")
        else:
            bot.send_message(message.chat.id, "❌ سکه کافی ندارید یا خطا رخ داد.")
    except (ValueError, IndexError):
        bot.send_message(message.chat.id, "❌ فرمت نامعتبر است.")

def process_bounty_claim(message):
    try:
        bounty_id = int(message.text)
        if claim_bounty(bounty_id, message.from_user.id):
            bot.send_message(message.chat.id, "✅ جایزه دریافت شد.")
        else:
            bot.send_message(message.chat.id, "❌ دریافت ناموفق بود.")
    except ValueError:
        bot.send_message(message.chat.id, "❌ شناسه نامعتبر است.")

# ============================================================
# 🌍 سیستم گروه اختصاصی
# ============================================================
def set_exclusive_chat(chat_id: int) -> None:
    if EXCLUSIVE_CHAT_ID is not None:
        return
    with get_connection() as conn:
        conn.execute("INSERT OR REPLACE INTO bot_settings (key, value) VALUES ('exclusive_chat_id', ?)", (chat_id,))

def get_exclusive_chat() -> Optional[int]:
    if EXCLUSIVE_CHAT_ID is not None:
        return EXCLUSIVE_CHAT_ID
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT value FROM bot_settings WHERE key = 'exclusive_chat_id'")
        row = cur.fetchone()
        return int(row['value']) if row else None

@bot.message_handler(content_types=['new_chat_members'])
def on_new_chat_members(message):
    if bot.get_me().id not in [m.id for m in message.new_chat_members]:
        return
    adder_id = message.from_user.id
    exclusive_chat = get_exclusive_chat()
    chat_id = message.chat.id

    if exclusive_chat is None:
        if not is_admin_user(adder_id):
            try:
                bot.leave_chat(chat_id)
            except:
                pass
    else:
        if chat_id != exclusive_chat:
            try:
                bot.leave_chat(chat_id)
            except:
                pass



# ============================================================
# 🔄 به‌روزرسانی دوره‌ای و نخ پس‌زمینه
# ============================================================
def background_jobs():
    """نخ پس‌زمینه برای تولید قلعه و باس"""
    while True:
        try:
            spawn_castles(3)
            if not get_active_world_boss():
                spawn_world_boss(1)

            with get_connection() as conn:
                conn.execute("DELETE FROM message_owners WHERE created_at < ?", (int(time.time()) - 86400,))
        except Exception as e:
            print(f"Background error: {e}")
        time.sleep(CASTLE_SPAWN_INTERVAL_HOURS * 3600)

# ============================================================
# 🚀 اجرای ربات


# ============================================================
if __name__ == '__main__':
    print("🤖 ربات کوین لند روشن شد...")
    bg_thread = threading.Thread(target=background_jobs, daemon=True)
    bg_thread.start()
    bot.polling(none_stop=True, interval=0, timeout=20, long_polling_timeout=15)
