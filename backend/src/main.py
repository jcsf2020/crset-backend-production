import os, logging
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, EmailStr
from starlette.middleware.cors import CORSMiddleware
from emailer import send_email
from db import SessionLocal, Lead, init_db
from antispam import check_rate_limit, verify_captcha

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
    captcha: str | None = None  # opcional (ignorado se não houver SECRET)

class ChatIn(BaseModel):
    message: str

@app.on_event("startup")
def _startup():
    init_db()
    logger.info("Startup OK (env=%s, cors=%s)", ENV, CORS_ORIGINS)

@app.get("/health")
def health():
    return {"env": ENV, "status": "ok"}

@app.post("/api/chat")
def chat(body: ChatIn):
    return {"reply": "pong", "echo": {"message": body.message}}

@app.post("/api/contact")
async def contact(body: ContactIn, request: Request):
    # 0) Rate limit por IP e por email
    client_ip = (request.client.host if request.client else "unknown") or "unknown"
    ok, retry = check_rate_limit(f"ip:{client_ip}")
    if not ok:
        raise HTTPException(
            status_code=429,
            detail=f"Too many requests (IP). Try again in {retry}s",
            headers={"Retry-After": str(retry)},
        )
    ok, retry = check_rate_limit(f"email:{str(body.email).lower()}")
    if not ok:
        raise HTTPException(
            status_code=429,
            detail=f"Too many requests (email). Try again in {retry}s",
            headers={"Retry-After": str(retry)},
        )

    # 0.1) Verificação de CAPTCHA (se estiver configurado)
    if not await verify_captcha(body.captcha or "", client_ip):
        raise HTTPException(status_code=400, detail="Invalid captcha")

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

    # 2) Envia email
    html = f"""
    <h2>Novo Lead (CRSET)</h2>
    <p><b>Nome:</b> {body.name}</p>
    <p><b>Email:</b> {body.email}</p>
    <p><b>Mensagem:</b><br/>{body.message}</p>
    <p style="font-size:12px;color:#666">Lead ID: {lead_id}</p>
    """
    sent = False
    try:
        resp = await send_email(subject=f"Novo Lead: {body.name}", html=html)
        sent = bool(resp)
        print(f"EMAIL_SENT resp={resp}")
    except Exception as e:
        print(f"EMAIL_SEND_FAILED error={e}")

    return {"ok": True, "sent": sent, "lead_id": lead_id, "echo": body.model_dump()}
