import logging
async def create_lead_in_notion(name, email, message, score=None, ip=None, lead_id=None):
    logging.getLogger("crset").info("Notion: disabled (no-op)")
    return None
