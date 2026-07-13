# telegram-translate-bridge

Mirrors a Telegram news channel into another language in real time. I built it to repost [@AjaNews](https://t.me/AjaNews) (Al Jazeera's Arabic breaking news channel, which posts way more than their English ones) as English translations on [@englishaljazeera](https://t.me/englishaljazeera).

How it works: a user account listens to the source channel (bots can't read channels they don't admin, so this uses Telethon/MTProto) → each post gets translated by Gemini Flash (free tier covers the whole volume) → a bot posts the translation to the target channel. Photos and videos come along with translated captions.

## Setup

You need three sets of credentials:

1. `api_id` + `api_hash` from https://my.telegram.org (API development tools) — use the account that will do the listening, and make sure it joined the source channel
2. a bot token from @BotFather — add the bot as admin of your target channel with "post messages" permission
3. a free Gemini key from https://aistudio.google.com/apikey

Then:

```
cp .env.example .env   # fill in your values
pip install -r requirements.txt
python main.py
```

First run asks for the listener account's phone + login code, after that it reuses the session file. Don't commit `.env` or `*.session` (gitignored).

## Running 24/7

**Windows:** `run_bridge.bat` runs it in a restart loop and logs to `bridge.log`. Drop `start_hidden.vbs` into your Startup folder (`Win+R` → `shell:startup`) and it launches invisibly at every login.

**Linux/VPS:** copy the folder (with the `.session` file so you don't need to log in again) and run it under systemd:

```ini
[Unit]
Description=telegram translate bridge
After=network-online.target

[Service]
WorkingDirectory=/opt/bridge
ExecStart=/usr/bin/python3 main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

## Config

Everything is in `.env` — source channel, target channel, and model are all configurable, so this works for any channel pair and language direction (just adjust the prompt in `main.py`).

## Known limitations

- albums arrive as separate posts
- edits on the source channel aren't mirrored
- videos over 50MB are skipped (bot api upload cap)
