# Telegram channel translation bridge
# listens to a source channel with a user account (telethon),
# translates with Gemini and reposts to my channel through a bot

import asyncio
import io
import logging
import os
import time

import requests
from dotenv import load_dotenv
from telethon import TelegramClient, events

load_dotenv()

API_ID = int(os.environ["TG_API_ID"])
API_HASH = os.environ["TG_API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]
SOURCE_CHANNEL = os.environ.get("SOURCE_CHANNEL", "AjaNews")
TARGET_CHANNEL = os.environ.get("TARGET_CHANNEL", "@englishaljazeera")
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")

ATTRIBUTION = "\n\nvia @AjaNews"
MAX_MEDIA_BYTES = 50 * 1024 * 1024  # bot api won't take uploads over 50mb

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("bridge")

PROMPT = (
    "Translate this Arabic newsflash into natural English news-wire style. "
    "Keep it concise and faithful to the original. Transliterate names using "
    "standard English press spellings (e.g., Netanyahu, Hezbollah, al-Sisi). "
    "Output ONLY the translation, with no preamble, quotes, or commentary.\n\n"
)


def translate(arabic_text: str) -> str:
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    )
    body = {
        "contents": [{"parts": [{"text": PROMPT + arabic_text}]}],
        "generationConfig": {"temperature": 0.2},
    }
    for attempt in range(6):
        try:
            resp = requests.post(url, json=body, timeout=60)
        except requests.exceptions.ConnectionError:
            # network flap (e.g. just woke from sleep) - wait for it to settle
            wait = 10 * (attempt + 1)
            log.warning("network error reaching gemini, retrying in %ss", wait)
            time.sleep(wait)
            continue
        if resp.status_code == 429:
            # free tier allows 10 req/min, back off and retry
            wait = 15 * (attempt + 1)
            log.warning("gemini rate limit, sleeping %ss", wait)
            time.sleep(wait)
            continue
        resp.raise_for_status()
        parts = resp.json()["candidates"][0]["content"]["parts"]
        return "".join(p.get("text", "") for p in parts).strip()
    raise RuntimeError("gemini kept rate limiting")


def bot_api(method: str, data: dict, files: dict | None = None) -> None:
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    for attempt in range(3):
        resp = requests.post(url, data=data, files=files, timeout=120)
        if resp.status_code == 429:
            retry_after = resp.json().get("parameters", {}).get("retry_after", 5)
            log.warning("bot api rate limit, sleeping %ss", retry_after)
            time.sleep(retry_after + 1)
            continue
        if not resp.ok:
            log.error("bot api %s failed: %s", method, resp.text[:300])
        resp.raise_for_status()
        return
    raise RuntimeError("bot api kept rate limiting")


def post_text(text: str) -> None:
    bot_api("sendMessage", {"chat_id": TARGET_CHANNEL, "text": text[:4096]})


def post_media(kind: str, blob: bytes, filename: str, caption: str) -> None:
    method, field = {
        "photo": ("sendPhoto", "photo"),
        "video": ("sendVideo", "video"),
    }[kind]
    bot_api(
        method,
        {"chat_id": TARGET_CHANNEL, "caption": caption[:1024]},
        files={field: (filename, io.BytesIO(blob))},
    )


client = TelegramClient("bridge_session", API_ID, API_HASH)


@client.on(events.NewMessage(chats=SOURCE_CHANNEL))
async def handler(event):
    msg = event.message
    text = (msg.text or "").strip()

    english = ""
    if text:
        try:
            english = await asyncio.to_thread(translate, text)
        except Exception:
            log.exception("translation failed for msg %s, skipping", msg.id)
            return
        english += ATTRIBUTION

    try:
        if msg.photo:
            blob = await msg.download_media(bytes)
            await asyncio.to_thread(post_media, "photo", blob, "photo.jpg", english)
        elif msg.video and (msg.file.size or 0) <= MAX_MEDIA_BYTES:
            blob = await msg.download_media(bytes)
            await asyncio.to_thread(post_media, "video", blob, "video.mp4", english)
        elif english:
            await asyncio.to_thread(post_text, english)
        else:
            log.info("msg %s: no text + unsupported media, skipped", msg.id)
            return
        log.info("posted msg %s: %s", msg.id, english[:80].replace("\n", " "))
    except Exception:
        log.exception("posting failed for msg %s", msg.id)


if __name__ == "__main__":
    client.start()  # asks for phone + code on first run, then uses the session file
    log.info("listening to %s -> %s", SOURCE_CHANNEL, TARGET_CHANNEL)
    client.run_until_disconnected()
