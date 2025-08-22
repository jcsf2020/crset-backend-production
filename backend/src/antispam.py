import os, time, logging
from collections import deque, defaultdict

RATE_LIMIT_QTY = int(os.getenv('RATE_LIMIT_QTY', '5'))
RATE_LIMIT_WINDOW = int(os.getenv('RATE_LIMIT_WINDOW', '60'))

_requests = defaultdict(deque)

def check_rate_limit(key: str):
    now = time.time()
    dq = _requests[key]
    while dq and now - dq[0] > RATE_LIMIT_WINDOW:
        dq.popleft()
    if len(dq) >= RATE_LIMIT_QTY:
        retry = max(1, int(RATE_LIMIT_WINDOW - (now - dq[0])))
        return False, retry
    dq.append(now)
    return True, 0

# BYPASS TOTAL (hard)
async def verify_captcha(token: str, remoteip: str | None = None) -> bool:
    logging.warning("CAPTCHA BYPASS ACTIVE (hard)")
    return True
