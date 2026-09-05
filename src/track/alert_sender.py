"""Alert delivery: Telegram bot + Discord webhook. All optional — a no-op
when tokens/webhooks are unconfigured (just logged instead)."""
from __future__ import annotations

import logging

import httpx

from config.settings import settings

log = logging.getLogger(__name__)


async def send_alert(text: str) -> bool:
    delivered = False
    async with httpx.AsyncClient(timeout=15.0) as client:
        if settings.telegram_bot_token and settings.telegram_chat_id:
            try:
                resp = await client.post(
                    f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
                    json={"chat_id": settings.telegram_chat_id, "text": text,
                          "parse_mode": "HTML", "disable_web_page_preview": True},
                )
                delivered = delivered or resp.status_code == 200
            except httpx.HTTPError as e:
                log.warning("telegram alert failed: %s", e)
        if settings.discord_webhook_url:
            try:
                resp = await client.post(settings.discord_webhook_url,
                                         json={"content": text})
                delivered = delivered or resp.status_code in (200, 204)
            except httpx.HTTPError as e:
                log.warning("discord alert failed: %s", e)
    if not delivered:
        log.info("ALERT (no channel configured): %s", text)
    return delivered
