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


def _item(m: Message, tz: ZoneInfo, show_date: bool = False) -> str:
    """Um e-mail formatado: assunto clicável, remetente, horário e preview."""
    stamp = ""
    if m.date:
        local = m.date.astimezone(tz)
        stamp = local.strftime("%d/%m %H:%M") if show_date else local.strftime("%H:%M")
    meta = " · ".join(filter(None, [escape(_trim(m.sender_name, 32)), stamp]))
    item = (
        f'\n\n<a href="{m.link}">{escape(_trim(m.subject, SUBJECT_CHARS))}</a>\n'
        f"<i>{meta}</i>"
    )
    if m.snippet:
        item += f"\n{escape(_trim(m.snippet, SNIPPET_CHARS))}"
    return item


def _pack(head: str, items: list[str], cont: str) -> list[str]:
    """Agrupa itens sob um cabeçalho, abrindo novo bloco antes de estourar."""
    blocks, parts, size = [], [], len(head)
    for item in items:
        if size + len(item) > BLOCK_LIMIT and parts:
            blocks.append(head + "".join(parts))
            head, parts, size = cont, [], len(cont)
        parts.append(item)
        size += len(item)
    if parts:
        blocks.append(head + "".join(parts))
    return blocks


def render_results(cfg: Config, label: str, messages: list[Message]) -> list[str]:
    """Formata o resultado de uma busca sob demanda feita pelo bot."""
    tz = ZoneInfo(cfg.timezone)
    head = f"🔎 <b>{escape(label)}</b> · {len(messages)} encontrado(s)"
    show_date = "hoje" not in label
    return _pack(head, [_item(m, tz, show_date) for m in messages], "🔎 <b>cont.</b>")


def collect(
    gmail: Gmail,
    cfg: Config,
    sent_label_id: str = "",
    exclude_sent: bool = True,
    window: str = "",
) -> dict[str, list[Message]]:
    """Roda a query de cada categoria; um e-mail só entra na primeira que casar.

    `exclude_sent=False` ignora a label de controle — é o que o /hoje do bot usa,
    para mostrar o dia inteiro mesmo que algo já tenha sido enviado antes.
    """
    seen: set[str] = set()
    by_category: dict[str, list[Message]] = {}

    for category in cfg.categories:
        skip = f" -label:{cfg.sent_label}" if exclude_sent else ""
        period = window or f"newer_than:{cfg.lookback}"
        query = f"({category.query}){skip} {period}"
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
            item = _item(m, tz)
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
