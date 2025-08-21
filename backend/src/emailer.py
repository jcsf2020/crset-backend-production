import os, logging, httpx

RESEND_API_KEY = os.getenv("RESEND_API_KEY")
RESEND_FROM = os.getenv("RESEND_FROM", "onboarding@resend.dev")
CONTACT_TO_EMAIL = os.getenv("CONTACT_TO_EMAIL", "crsetsolutions@gmail.com")

async def send_email(subject: str, html: str) -> dict | None:
    if not RESEND_API_KEY:
        logging.warning("RESEND_API_KEY not set; skipping email.")
        return None

    payload = {
        "from": RESEND_FROM,
        "to": [CONTACT_TO_EMAIL],
        "subject": subject,
        "html": html,
    }
    headers = {"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"}

    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post("https://api.resend.com/emails", headers=headers, json=payload)
        # se der 4xx/5xx, lança exceção -> FastAPI devolve 502
        r.raise_for_status()
        logging.info("Resend response: %s", r.text)
        return r.json()
