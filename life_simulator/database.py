import sqlite3
import json
import logging
from contextlib import contextmanager

DB_PATH = 'life_simulator.db'

@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=20.0)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        logging.error("Database error: %s", e, exc_info=True)
        raise
    finally:
        conn.close()

def init_db():
    with get_connection() as conn:
        cur = conn.cursor()

        # User core
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tg_id INTEGER UNIQUE,
                state TEXT DEFAULT 'NONE',
                state_data TEXT DEFAULT '{}',                first_name TEXT,
                last_name TEXT,
                age INTEGER DEFAULT 18,
                age_days INTEGER DEFAULT 0,
                gender TEXT,
                city TEXT,
                job_id TEXT,
                cash REAL DEFAULT 1000,
                credit_score INTEGER DEFAULT 500,
                level INTEGER DEFAULT 1,
                xp INTEGER DEFAULT 0,
                energy REAL DEFAULT 100,
                health REAL DEFAULT 100,
                happiness REAL DEFAULT 100,
                hunger REAL DEFAULT 100,
                thirst REAL DEFAULT 100,
                married_to INTEGER,
                prestige INTEGER DEFAULT 0,
                banned INTEGER DEFAULT 0,
                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Skills
        cur.execute("""
            CREATE TABLE IF NOT EXISTS skills (
                user_id INTEGER PRIMARY KEY,
                programming INTEGER DEFAULT 0,
                management INTEGER DEFAULT 0,
                economy INTEGER DEFAULT 0,
                communication INTEGER DEFAULT 0,
                technical INTEGER DEFAULT 0,
                design INTEGER DEFAULT 0,
                knowledge INTEGER DEFAULT 0,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        """)

        # Bank Accounts
        cur.execute("""
            CREATE TABLE IF NOT EXISTS bank_accounts (
                user_id INTEGER PRIMARY KEY,
                balance REAL DEFAULT 0,
                loan_amount REAL DEFAULT 0,
                loan_installment REAL DEFAULT 0,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        """)

        # Inventory
        cur.execute("""
            CREATE TABLE IF NOT EXISTS inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                item_id TEXT,
                quantity INTEGER DEFAULT 1,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        """)

        # Houses
        cur.execute("""
            CREATE TABLE IF NOT EXISTS houses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                house_id TEXT,
                condition REAL DEFAULT 100,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        """)

        # Vehicles
        cur.execute("""
            CREATE TABLE IF NOT EXISTS vehicles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                vehicle_id TEXT,
                fuel REAL DEFAULT 100,
                condition REAL DEFAULT 100,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        """)

        # Businesses
        cur.execute("""
            CREATE TABLE IF NOT EXISTS businesses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id INTEGER,
                name TEXT,
                type TEXT,
                capital REAL DEFAULT 0,
                employees_count INTEGER DEFAULT 0,
                income_rate REAL DEFAULT 0,
                expense_rate REAL DEFAULT 0,
                FOREIGN KEY(owner_id) REFERENCES users(id)
            )
        """)

        # Business Partners
        cur.execute("""
            CREATE TABLE IF NOT EXISTS business_partners (
                business_id INTEGER,
                user_id INTEGER,
                share_percentage REAL,
                FOREIGN KEY(business_id) REFERENCES businesses(id),
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        """)

        # Friends & Relationships
        cur.execute("""
            CREATE TABLE IF NOT EXISTS relationships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id_1 INTEGER,
                user_id_2 INTEGER,
                relationship_type TEXT, -- friend, partner
                level INTEGER DEFAULT 0,
                FOREIGN KEY(user_id_1) REFERENCES users(id),
                FOREIGN KEY(user_id_2) REFERENCES users(id)
            )
        """)

        # Children
        cur.execute("""
            CREATE TABLE IF NOT EXISTS children (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_id INTEGER,
                name TEXT,
                age INTEGER DEFAULT 0,
                health REAL DEFAULT 100,
                education TEXT DEFAULT 'None',
                FOREIGN KEY(parent_id) REFERENCES users(id)
            )
        """)

        # Transactions (for logs and anti-cheat)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount REAL,
                type TEXT,
                description TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        """)

        # Market (dynamic prices)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS market (
                item_id TEXT PRIMARY KEY,
                base_price REAL,
                current_price REAL,
                supply INTEGER DEFAULT 1000,
                demand INTEGER DEFAULT 1000
            )
        """)

        # Economy History
        cur.execute("""
            CREATE TABLE IF NOT EXISTS economy_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                inflation_rate REAL,
                fuel_price_modifier REAL,
                food_price_modifier REAL,
                housing_price_modifier REAL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # News
        cur.execute("""
            CREATE TABLE IF NOT EXISTS news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Add index for faster queries
        cur.execute("CREATE INDEX IF NOT EXISTS idx_users_tg_id ON users(tg_id)")

def get_user(tg_id):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE tg_id = ?", (tg_id,))
        return cur.fetchone()

def create_user(tg_id):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("INSERT OR IGNORE INTO users (tg_id) VALUES (?)", (tg_id,))
        if cur.rowcount > 0:
            user_id = cur.lastrowid
            cur.execute("INSERT INTO skills (user_id) VALUES (?)", (user_id,))
            cur.execute("INSERT INTO bank_accounts (user_id) VALUES (?)", (user_id,))
        return get_user(tg_id)

def set_user_state(tg_id, state, state_data=None):
    if state_data is None:
        state_data = {}
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE users SET state = ?, state_data = ? WHERE tg_id = ?", (state, json.dumps(state_data), tg_id))

def get_user_state(tg_id):
    user = get_user(tg_id)
    if user:
        return user['state'], json.loads(user['state_data'])
    return None, {}
