import os, logging
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, EmailStr
from starlette.middleware.cors import CORSMiddleware
from emailer import send_email
from db import SessionLocal, Lead, init_db
from antispam import check_rate_limit  # <- sem verify_captcha
from ai import score_lead
from notion_integration import create_lead_in_notion

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("crset")

ENV = os.getenv("ENVIRONMENT", "development")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", FRONTEND_URL).split(",") if o.strip()]

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ContactIn(BaseModel):
    name: str
    email: EmailStr
    message: str
    captcha: str | None = None  # ignorado (bypass)

class ChatIn(BaseModel):
    message: str

@app.on_event("startup")
def _startup():
    init_db()
    logger.info("Startup OK (env=%s, cors=%s)", ENV, CORS_ORIGINS)
    logger.info("CAPTCHA BYPASS: ativo (nenhuma validação de captcha será feita)")

@app.get("/health")
def health():
    return {"env": ENV, "status": "ok"}

@app.post("/api/chat")
def chat(body: ChatIn):
    return {"reply": "pong", "echo": {"message": body.message}}

@app.post("/api/contact")
async def contact(body: ContactIn, request: Request):
    # 0) IP real (Railway/Cloudflare)
    fwd = request.headers.get("x-forwarded-for", "") or ""
    client_ip = (
        (fwd.split(",")[0].strip() if fwd else request.headers.get("cf-connecting-ip"))
        or (request.client.host if request.client else "unknown")
        or "unknown"
    )

    # 0.1) Rate limit
    ok, retry = check_rate_limit(f"ip:{client_ip}")
    if not ok:
        raise HTTPException(status_code=429, detail=f"Too many requests (IP). Try again in {retry}s", headers={"Retry-After": str(retry)})
    ok, retry = check_rate_limit(f"email:{str(body.email).lower()}")
    if not ok:
        raise HTTPException(status_code=429, detail=f"Too many requests (email). Try again in {retry}s", headers={"Retry-After": str(retry)})

    # >>> NADA DE CAPTCHA A PARTIR DAQUI <<<

    # 1) Grava lead
    db = SessionLocal()
    lead_id = None
    try:
        lead = Lead(name=body.name, email=str(body.email), message=body.message)
        db.add(lead)
        db.commit()
        db.refresh(lead)
        lead_id = lead.id
    finally:
        db.close()

    # 2) IA (best-effort)
    ai_result = await score_lead(body.name, str(body.email), body.message)
    ai_score = (ai_result or {}).get("score")
    ai_reason = (ai_result or {}).get("reason") or ""

    # 3) Notion (best-effort)
    try:
        _ = await create_lead_in_notion(
            body.name, str(body.email), body.message,
            score=ai_score, ip=client_ip, lead_id=lead_id,
        )
    except Exception as e:
        logger.warning("Notion best-effort failed: %s", e)

    # 4) Email
    parts = [
        "<h2>Novo Lead (CRSET)</h2>",
        f"<p><b>Nome:</b> {body.name}</p>",
        f"<p><b>Email:</b> {body.email}</p>",
        f"<p><b>Mensagem:</b><br/>{body.message}</p>",
        f'<p style="font-size:12px;color:#666">Lead ID: {lead_id} | IP: {client_ip}</p>',
    ]
    if ai_score is not None:
        parts.insert(1, f"<p><b>AI Score:</b> {ai_score} / 100</p>")
        if ai_reason:
            parts.insert(2, f"<p style='color:#555'><i>{ai_reason}</i></p>")
    html = "\n".join(parts)

    sent = False
    try:
        resp = await send_email(subject=f"Novo Lead: {body.name}", html=html)
        sent = bool(resp)
        logger.info("EMAIL_SENT resp=%s", resp)
    except Exception as e:
        logger.error("EMAIL_SEND_FAILED error=%s", e)

    return {"ok": True, "sent": sent, "lead_id": lead_id, "ai": ai_result or None, "echo": body.model_dump()}

# ===================== TEMP MAILTEST =====================
from fastapi import HTTPException as _HTTPException

@app.post("/__mailtest")
async def __mailtest():
    TO = os.getenv("CONTACT_TO_EMAIL","crsetsolutions@gmail.com")
    try:
        send_email(TO, "CRSET Mail Test", html="Teste de envio direto pelo backend (mailtest).")
        logger.info("MAILTEST: EMAIL_SENT to=%s", TO)
        return {"ok": True, "to": TO}
    except Exception as e:
        logger.exception("MAILTEST: failed: %s", e)
        raise _HTTPException(status_code=500, detail=f"mail_error: {e}")
# =========================================================
