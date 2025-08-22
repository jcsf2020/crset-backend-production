import logging
async def score_lead(name: str, email: str, message: str):
    logging.getLogger("crset").info("AI scoring: disabled (no-op)")
    return None, "ai_disabled"
