import os, logging
from typing import Optional, Dict

logger = logging.getLogger("crset")

async def score_lead(name: str, email: str, message: str) -> Optional[Dict]:
    """
    Se AI_SCORING=off/0/false/no -> não chama OpenAI e devolve None.
    Caso contrário tenta pontuar, mas nunca faz subir exceção (log e devolve None).
    """
    if os.getenv("AI_SCORING", "off").lower() in ("off","0","false","no"):
        return None
    try:
        # Se quiseres voltar a ligar depois, mete aqui o código do OpenAI.
        # Mantemos um 'pass' para não chamar nada por agora.
        pass
    except Exception as e:
        logger.warning("AI scoring falhou: %s", e)
    return None
