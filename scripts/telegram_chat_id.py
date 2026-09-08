#!/usr/bin/env python3
"""Descobre seu TELEGRAM_CHAT_ID.

Uso:
    1. No Telegram, mande qualquer mensagem para o seu bot (ex.: "oi").
    2. python scripts/telegram_chat_id.py <BOT_TOKEN>
"""

import sys

import requests


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1

    token = sys.argv[1].strip()
    response = requests.get(f"https://api.telegram.org/bot{token}/getUpdates", timeout=30)
    payload = response.json()

    if not payload.get("ok"):
        print(f"Token recusado pelo Telegram: {payload.get('description')}")
        return 1

    chats = {}
    for update in payload.get("result", []):
        message = update.get("message") or update.get("channel_post") or {}
        chat = message.get("chat")
        if chat:
            chats[chat["id"]] = chat.get("title") or chat.get("first_name") or chat.get("username", "")

    if not chats:
        print("Nenhuma mensagem encontrada. Mande um 'oi' para o bot no Telegram e rode de novo.")
        return 1

    for chat_id, name in chats.items():
        print(f"TELEGRAM_CHAT_ID={chat_id}   ({name})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
