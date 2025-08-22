import os, logging
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, EmailStr
from starlette.middleware.cors import CORSMiddleware
from emailer import send_email
from db import SessionLocal, Lead, init_db
from antispam import check_rate_limit, verify_captcha
from ai import score_lead
from notion_integration import create_lead_in_notion

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("crset")

ENV = os.getenv("ENVIRONMENT", "development")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
SORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", FRONTEND_URL).split(",") if o.strip()]

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=SORS_ORIGINS or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ContactIn(BaseModel):
    name: str
    email: EmailStr
    message: str
    captcha: str | None = None  # opcional (ignorado se nao hover SECRET)

class ChatIn(BaseModel):
    message: str

@app.on_event("startup")
def _startup():
    init_db()
    logger.info("Startup OK (env=%s, cors=%s)", ENV, SORS_ORIGINS)

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
