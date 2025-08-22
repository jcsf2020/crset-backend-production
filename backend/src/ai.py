import os, json, re, logging
from typing import Optional, Dict, Any

# Usa o cliente assíncrono para não bloquear o endpoint
try:
    from openai import AsyncOpenAI
except Exception:  # lib não instalada ainda ou ambiente sem import
    AsyncOpenAI = None  # type: ignore

MODEL = os.getenv("LEAD_SCORE_MODEL", "gpt-4o-mini")

def _enabled() -> bool:
    flag = os.getenv("AI_SCORING_ENABLED", "1")
    return flag not in ("0", "false", "False") and bool(os.getenv("OPENAI_API_KEY"))

async def score_lead(name: str, email: str, message: str) -> Optional[Dict[str, Any]]:
    """
    Retorna: {"score": int 0..100, "reason": str} ou None se desativado/sem chave.
    Nunca levanta exceção para não quebrar o /api/contact.
    """
    if not _enabled():
        logging.info("AI scoring desativado ou sem OPENAI_API_KEY; skip.")
        return None
    if AsyncOpenAI is None:
        logging.warning("Pacote openai indisponível; skip scoring.")
        return None

    client = AsyncOpenAI()
    prompt = (
        "Você é um assistente de qualificação de leads B2B. "
        "Dado nome, email e mensagem, devolva um JSON com:\n"
        '{"score": 0-100, "reason": "texto curto explicando"}.\n'
        "Critérios (peso): intenção de compra/urgência (40), adequação ao ICP (30), clareza/objetivo (20), contato empresarial (10).\n"
        "Apenas o JSON, sem texto extra."
    )
    try:
        resp = await client.chat.completions.create(
            model=MODEL,
            temperature=0.2,
            messages=[
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": f"Nome: {name}\nEmail: {email}\nMensagem: {message}\nResponda somente JSON."
                },
            ],
            max_tokens=200,
        )
        text = (resp.choices[0].message.content or "").strip()
        data = None
        # tenta JSON direto
        try:
            data = json.loads(text)
        except Exception:
            # tenta extrair o primeiro bloco {...}
            m = re.search(r"\{.*\}", text, flags=re.S)
            if m:
                data = json.loads(m.group(0))
        if not isinstance(data, dict):
            data = {"score": 50, "reason": "fallback"}
        score = int(float(data.get("score", 50)))
        score = max(0, min(100, score))
        reason = str(data.get("reason", ""))[:500]
        return {"score": score, "reason": reason}
    except Exception as e:
        logging.exception("AI scoring falhou: %s", e)
        return None
