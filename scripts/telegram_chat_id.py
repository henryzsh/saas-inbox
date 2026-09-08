#!/usr/bin/env python3
"""Descobre seu TELEGRAM_CHAT_ID.

Uso:
    python scripts/telegram_chat_id.py            # lê TELEGRAM_BOT_TOKEN do .env
    python scripts/telegram_chat_id.py <TOKEN>

O script valida o token, mostra o link do seu bot e fica aguardando você mandar
uma mensagem para ele. Assim que a mensagem chega, imprime o chat id.
"""

import os
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from inbox.config import ROOT  # noqa: E402

API = "https://api.telegram.org/bot{token}/{method}"
WAIT_SECONDS = 180


def call(token: str, method: str, **params) -> dict:
    response = requests.get(API.format(token=token, method=method), params=params, timeout=40)
    return response.json()


def describe(chat: dict) -> str:
    kind = {"private": "conversa privada", "group": "grupo", "supergroup": "supergrupo",
            "channel": "canal"}.get(chat.get("type"), chat.get("type", "?"))
    name = chat.get("title") or " ".join(
        filter(None, [chat.get("first_name"), chat.get("last_name")])
    ) or chat.get("username", "")
    return f"{kind}: {name}".strip()


def main() -> int:
    token = (sys.argv[1] if len(sys.argv) > 1 else "").strip()
    if not token:
        load_dotenv(ROOT / ".env")
        token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        print("Token não informado. Passe como argumento ou defina TELEGRAM_BOT_TOKEN no .env.")
        return 1

    # 1. O token é válido?
    me = call(token, "getMe")
    if not me.get("ok"):
        print(f"Token recusado pelo Telegram: {me.get('description')}")
        print("Confira se copiou o token inteiro do @BotFather (formato 123456789:AAE...).")
        return 1
    username = me["result"].get("username", "")
    print(f"Bot: @{username}  ({me['result'].get('first_name', '')})")

    # 2. Um webhook ativo faz o getUpdates devolver sempre vazio.
    hook = call(token, "getWebhookInfo")
    if hook.get("ok") and hook["result"].get("url"):
        print(f"\n⚠️  Há um webhook ativo ({hook['result']['url']}).")
        print("Enquanto ele existir, getUpdates volta vazio. Remova com:")
        print(f"    curl 'https://api.telegram.org/bot<TOKEN>/deleteWebhook'")
        return 1

    print(f"\nAbra https://t.me/{username} e mande qualquer mensagem (ex.: 'oi').")
    print("Aguardando", end="", flush=True)

    # 3. Long polling até a mensagem aparecer.
    offset = None
    deadline = time.time() + WAIT_SECONDS
    while time.time() < deadline:
        params = {"timeout": 25}
        if offset is not None:
            params["offset"] = offset
        payload = call(token, "getUpdates", **params)

        if not payload.get("ok"):
            print(f"\nTelegram respondeu com erro: {payload.get('description')}")
            return 1

        updates = payload.get("result", [])
        chats = {}
        for update in updates:
            message = (
                update.get("message")
                or update.get("edited_message")
                or update.get("channel_post")
                or {}
            )
            if chat := message.get("chat"):
                chats[chat["id"]] = describe(chat)

        if chats:
            print("\n\n" + "=" * 60)
            print("Adicione ao .env (e crie o secret de mesmo nome no GitHub):")
            print("=" * 60)
            for chat_id, label in chats.items():
                print(f"TELEGRAM_CHAT_ID={chat_id}   # {label}")
            print("=" * 60)
            return 0

        if updates:
            offset = updates[-1]["update_id"] + 1
        print(".", end="", flush=True)

    print("\n\nNenhuma mensagem chegou em 3 minutos.")
    print(f"Confirme que você mandou a mensagem para @{username} — e não para outro bot.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
