from fastapi import APIRouter, Request
from bot.telegram_bot import process_update

router = APIRouter()

@router.post("/webhook/telegram")
async def telegram_webhook(request: Request):
    data = await request.json()
    await process_update(data)
    return {"ok": True}