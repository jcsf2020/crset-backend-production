import os, time, logging, httpx
from collections import deque, defaultdict

RATE_LIMIT_QTY = int(os.getenv('RATE_LIMIT_QTY', '5'))        # reqs
RATE_LIMIT_WINDOW = int(os.getenv('RATE_LIMIT_WINDOW', '60'))  # segundos

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

HCAPTCHA_SECRET = os.getenv('HCAPTCHA_SECRET')
RECAPTCHA_SECRET = os.getenv('RECAPTCHA_SECRET')

async def verify_captcha(token: str, remoteip: str | None = None) -> bool:
    # se não houver CAPTCHA configurado, considera OK
    if not (HCAPTCHA_SECRET or RECAPTCHA_SECRET):
        return True
    if not token:
        return False

    if HCAPTCHA_SECRET:
        data = {'secret': HCAPTCHA_SECRET, 'response': token}
        if remoteip:
            data['remoteip'] = remoteip
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post('https://hcaptcha.com/siteverify', data=data)
            ok = r.json().get('success') is True
            if not ok:
                logging.warning('hCaptcha fail: %s', r.text)
            return ok

    if RECAPTCHA_SECRET:
        data = {'secret': RECAPTCHA_SECRET, 'response': token}
        if remoteip:
            data['remoteip'] = remoteip
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post('https://www.google.com/recaptcha/api/siteverify', data=data)
            ok = r.json().get('success') is True
            if not ok:
                logging.warning('reCAPTCHA fail: %s', r.text)
            return ok

    return True
