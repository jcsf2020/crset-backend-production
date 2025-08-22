import os, logging
from typing import Optional, Any, Dict

try:
    from notion_client import AsyncClient  # pip install notion-client
except Exception:
    AsyncClient = None  # type: ignore

def _enabled() -> bool:
    if os.getenv("NOTION_ENABLED", "1").lower() in ("0","false","no"):
        return False
    return bool(os.getenv("NOTION_API_KEY") and os.getenv("NOTION_DATABASE_ID"))

def _clip(s: Optional[str], n: int = 1900) -> str:
    return (s or "")[:n]

async def create_lead_in_notion(
    name: str,
    email: str,
    message: str,
    *,
    score: Optional[int] = None,
    ip: Optional[str] = None,
    lead_id: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """Best-effort: cria uma página no Notion. Nunca levanta exceção."""
    if not _enabled():
        logging.info("Notion disabled or missing keys; skip.")
        return None
    if AsyncClient is None:
        logging.warning("notion-client indisponível no runtime; skip.")
        return None

    client = AsyncClient(auth=os.getenv("NOTION_API_KEY", ""))
    db_id = os.getenv("NOTION_DATABASE_ID", "")

    props: Dict[str, Any] = {
        "Name":   {"title":     [{"text": {"content": _clip(name, 200)}}]},
        "Email":  {"email":     email},
        "Message":{"rich_text": [{"text": {"content": _clip(message, 1900)}}]},
    }
    if score is not None:
        try: props["Score"] = {"number": int(score)}
        except Exception: props["Score"] = {"number": None}
    if ip:
        props["IP"] = {"rich_text": [{"text": {"content": _clip(ip, 100)}}]}
    if lead_id is not None:
        try: props["Lead ID"] = {"number": int(lead_id)}
        except Exception: props["Lead ID"] = {"number": None}

    # se existir um select "Status" no DB, marcamos "New" (Notion ignora se não existir)
    props["Status"] = {"select": {"name": "New"}}

    try:
        return await client.pages.create(parent={"database_id": db_id}, properties=props)
    except Exception as e:
        logging.warning("Notion create_lead_in_notion failed: %s", e)
        return None
