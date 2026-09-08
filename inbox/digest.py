"""Monta o digest: busca por categoria, deduplica e formata para o Telegram."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from .config import Config
from .gmail import Gmail, Message
from .telegram import escape

SNIPPET_CHARS = 110
BLOCK_LIMIT = 3800  # folga sobre o teto de 4096 do Telegram
SUBJECT_CHARS = 90

DIAS = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]


def _trim(text: str, limit: int) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def collect(gmail: Gmail, cfg: Config, sent_label_id: str) -> dict[str, list[Message]]:
    """Roda a query de cada categoria; um e-mail só entra na primeira que casar."""
    seen: set[str] = set()
    by_category: dict[str, list[Message]] = {}

    for category in cfg.categories:
        query = f"({category.query}) -label:{cfg.sent_label} newer_than:{cfg.lookback}"
        ids = [mid for mid in gmail.search(query, cfg.max_per_category * 2) if mid not in seen]
        if not ids:
            continue
        messages = gmail.fetch(ids)[: cfg.max_per_category]
        if not messages:
            continue
        seen.update(m.id for m in messages)
        by_category[category.name] = messages

    return by_category


def render(cfg: Config, by_category: dict[str, list[Message]]) -> list[str]:
    """Devolve blocos de HTML prontos, cada um abaixo do limite do Telegram.

    Uma categoria longa é quebrada em vários blocos (com "cont." no cabeçalho)
    em vez de ser truncada — nenhum e-mail some por causa do limite.
    """
    tz = ZoneInfo(cfg.timezone)
    now = datetime.now(tz)
    total = sum(len(v) for v in by_category.values())

    blocks = [
        f"📬 <b>Digest da inbox</b> · {DIAS[now.weekday()]} {now:%d/%m %H:%M}\n"
        f"<i>{total} e-mail{'s' if total != 1 else ''} em "
        f"{len(by_category)} categoria{'s' if len(by_category) != 1 else ''}</i>"
    ]

    emoji = {c.name: c.emoji for c in cfg.categories}
    for name, messages in by_category.items():
        icon = emoji.get(name, "•")
        head = f"{icon} <b>{escape(name)}</b> · {len(messages)}"
        parts: list[str] = []
        size = len(head)

        for m in messages:
            when = m.date.astimezone(tz).strftime("%H:%M") if m.date else ""
            meta = " · ".join(filter(None, [escape(_trim(m.sender_name, 32)), when]))
            item = (
                f'\n\n<a href="{m.link}">{escape(_trim(m.subject, SUBJECT_CHARS))}</a>\n'
                f"<i>{meta}</i>"
            )
            if m.snippet:
                item += f"\n{escape(_trim(m.snippet, SNIPPET_CHARS))}"

            if size + len(item) > BLOCK_LIMIT and parts:
                blocks.append(head + "".join(parts))
                head = f"{icon} <b>{escape(name)}</b> · cont."
                parts, size = [], len(head)

            parts.append(item)
            size += len(item)

        if parts:
            blocks.append(head + "".join(parts))

    return blocks


def render_empty(cfg: Config) -> list[str]:
    now = datetime.now(ZoneInfo(cfg.timezone))
    return [f"📭 <b>Nada novo</b> · {DIAS[now.weekday()]} {now:%d/%m %H:%M}"]
