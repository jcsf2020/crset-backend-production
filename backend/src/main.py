import os, logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, EmailStr
from starlette.middleware.cors import CORSMiddleware
from emailer import send_email

logging.basicConfig(level=logging.INFO)

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

class ChatIn(BaseModel):
    message: str

@app.get("/health")
def health():
    return {"env": ENV, "status": "ok"}

@app.post("/api/chat")
def chat(body: ChatIn):
    return {"reply":"pong","echo":{"message":body.message}}

@app.post("/api/contact")
async def contact(body: ContactIn):
    html = f"""
    <h2>Novo Lead (CRSET)</h2>
    <p><b>Nome:</b> {body.name}</p>
    <p><b>Email:</b> {body.email}</p>
    <p><b>Mensagem:</b><br/>{body.message}</p>
    """
    try:
        resp = await send_email(subject=f"Novo Lead: {body.name}", html=html)
    except Exception as e:
        logging.exception("Email send failed")
        raise HTTPException(status_code=502, detail="Email send failed")

    return {"ok": True, "sent": bool(resp), "echo": body.model_dump()}
