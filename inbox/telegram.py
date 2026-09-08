"""Envio para o Telegram, respeitando o limite de 4096 caracteres por mensagem."""

from __future__ import annotations

import html

import requests

LIMIT = 4096
API = "https://api.telegram.org/bot{token}/sendMessage"


def escape(text: str) -> str:
    return html.escape(text or "", quote=False)


def chunk(blocks: list[str], limit: int = LIMIT) -> list[str]:
    """Agrupa blocos já formatados sem quebrar nenhum bloco no meio.

    Cada bloco é uma unidade fechada de HTML (uma categoria inteira ou um
    e-mail), então nunca cortamos uma tag pela metade.
    """
    messages: list[str] = []
    current = ""
    for block in blocks:
        if len(block) > limit:  # bloco isolado gigante: trunca com aviso
            block = block[: limit - 20].rstrip() + "\n…"
        candidate = f"{current}\n\n{block}" if current else block
        if len(candidate) > limit:
            messages.append(current)
            current = block
        else:
            current = candidate
    if current:
        messages.append(current)
    return messages


def send(token: str, chat_id: str, blocks: list[str]) -> None:
    for text in chunk(blocks):
        response = requests.post(
            API.format(token=token),
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=30,
        )
        if not response.ok:
            raise RuntimeError(f"Telegram recusou o envio ({response.status_code}): {response.text}")
