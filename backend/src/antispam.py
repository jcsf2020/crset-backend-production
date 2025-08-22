import os, time, logging, httpx
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

# Kill-switch: por padrão DESLIGADO
CAPTCHA_ENABLED = False

HCAPTCHA_SECRET = os.getenv('HCAPTCHA_SECRET')
RECAPTCHA_SECRET = os.getenv('RECAPTCHA_SECRET')

def _looks_placeholder(s: str | None) -> bool:
    if not s: return False
    up = s.upper().strip()
    return any(up.startswith(p) for p in ('COLE_', 'PASTE_', 'PLACEHOLDER', 'YOUR_', 'TEST_'))

async def verify_captcha(token: str, remoteip: str | None = None) -> bool:
    # Desliga se kill-switch OFF
    if not CAPTCHA_ENABLED:
        return True

    # Ignora secrets “placeholder”
    secret_h = None if _looks_placeholder(HCAPTCHA_SECRET) else HCAPTCHA_SECRET
    secret_r = None if _looks_placeholder(RECAPTCHA_SECRET) else RECAPTCHA_SECRET

    # Se nenhum secret válido, considera OK
    if not (secret_h or secret_r):
        return True

    if not token:
        return False

    if secret_h:
        data = {'secret': secret_h, 'response': token}
        if remoteip: data['remoteip'] = remoteip
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post('https://hcaptcha.com/siteverify', data=data)
            ok = r.json().get('success') is True
            if not ok: logging.warning('hCaptcha fail: %s', r.text)
            return ok

    if secret_r:
        data = {'secret': secret_r, 'response': token}
        if remoteip: data['remoteip'] = remoteip
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post('https://www.google.com/recaptcha/api/siteverify', data=data)
            ok = r.json().get('success') is True
            if not ok: logging.warning('reCAPTCHA fail: %s', r.text)
            return ok

    return True

# Loga status (aparece no startup)
logging.getLogger("crset").info(
    "CAPTCHA status: enabled=%s, has_hcaptcha=%s, has_recaptcha=%s",
    CAPTCHA_ENABLED, bool(HCAPTCHA_SECRET), bool(RECAPTCHA_SECRET)
)
