import threading
import time
import logging

# Rate limiting
_user_last_action = {}
_locks = {}
_global_lock = threading.Lock()

def get_user_lock(user_id):
    with _global_lock:
        if user_id not in _locks:
            _locks[user_id] = threading.Lock()
        return _locks[user_id]

def check_rate_limit(user_id, cooldown=0.5):
    now = time.time()
    with _global_lock:
        last = _user_last_action.get(user_id, 0)
        if now - last < cooldown:
            logging.warning(f"Anti-Cheat: Rate limit triggered for user {user_id}.")
            return False
        _user_last_action[user_id] = now
        return True
