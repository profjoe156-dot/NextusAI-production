import hmac

from fastapi import APIRouter, HTTPException, Request, Response, status
from telegram import Update

from app.observability import TELEGRAM_UPDATES

router = APIRouter(tags=["webhooks"])


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def telegram_webhook(request: Request) -> Response:
    provided = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    expected = request.app.state.settings.telegram_webhook_secret.get_secret_value()
    if not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=403, detail="Invalid webhook secret")
    payload = await request.json()
    telegram = request.app.state.telegram
    update = Update.de_json(payload, telegram.bot)
    if update is not None:
        await telegram.update_queue.put(update)
        TELEGRAM_UPDATES.inc()
    return Response(status_code=status.HTTP_202_ACCEPTED)
