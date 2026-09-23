import threading
import time

# Rate limiting
_user_last_action = {}
_locks = {}

def get_user_lock(user_id):
    if user_id not in _locks:
        _locks[user_id] = threading.Lock()
    return _locks[user_id]

def check_rate_limit(user_id, cooldown=1.0):
    now = time.time()
    last = _user_last_action.get(user_id, 0)
    if now - last < cooldown:
        return False
    _user_last_action[user_id] = now
    return True
