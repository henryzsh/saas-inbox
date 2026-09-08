"""Traduz o que você digita no Telegram para uma query do Gmail.

    "email da vercel"        -> from:vercel               (hoje)
    "vercel semana"          -> from:vercel               (últimos 7 dias)
    "nubank ontem"           -> from:nubank               (ontem)
    "from:x is:unread"       -> passa direto, sem tradução
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# Operadores do Gmail: se o texto já usa um, o usuário sabe o que quer.
GMAIL_OPS = (
    "from", "to", "cc", "bcc", "subject", "label", "category", "has", "is",
    "filename", "after", "before", "older_than", "newer_than", "older", "newer",
    "larger", "smaller", "in", "list", "deliveredto", "rfc822msgid", "size",
)
RAW_QUERY = re.compile(rf"\b({'|'.join(GMAIL_OPS)}):", re.IGNORECASE)

# Palavras que só dão forma à frase e não ajudam a filtrar.
STOPWORDS = {
    "email", "emails", "e", "mail", "mails", "mensagem", "mensagens", "msg",
    "da", "de", "do", "das", "dos", "no", "na", "nos", "nas", "em", "com",
    "me", "meu", "meus", "minha", "minhas", "manda", "mandar", "mostra",
    "mostrar", "ver", "vê", "quero", "queria", "lista", "listar", "traz",
    "trazer", "busca", "buscar", "procura", "procurar", "pega", "pegar",
    "um", "uma", "uns", "umas", "o", "a", "os", "as", "que", "tem", "todos",
    "todas", "por", "favor", "pra", "para", "sobre", "recebi", "chegou",
    # sobras de período, caso a palavra apareça repetida
    "hoje", "ontem", "semana", "mes", "mês", "tudo", "sempre", "dia", "dias",
}

RELATIVE_DAYS = re.compile(r"^(\d{1,3})\s*d(ias?)?$")


@dataclass
class Query:
    gmail: str          # query pronta para a Gmail API
    label: str          # descrição legível, usada no cabeçalho da resposta
    fallback: str = ""  # query mais ampla, se a principal não achar nada


def _period(tokens: list[str], tz: ZoneInfo) -> tuple[str, str, list[str]]:
    """Extrai o período dos tokens. O padrão, sem nada dito, é hoje."""
    today = datetime.now(tz).date()
    rest = list(tokens)

    def take(word: str) -> bool:
        if word in rest:
            rest.remove(word)
            return True
        return False

    if take("ontem"):
        start = today - timedelta(days=1)
        return f"after:{start:%Y/%m/%d} before:{today:%Y/%m/%d}", "ontem", rest
    if take("semana") or take("7d"):
        return "newer_than:7d", "últimos 7 dias", rest
    if take("mes") or take("mês") or take("30d"):
        return "newer_than:30d", "últimos 30 dias", rest
    if take("tudo") or take("sempre"):
        return "", "todo o histórico", rest

    for token in list(rest):
        if match := RELATIVE_DAYS.match(token):
            rest.remove(token)
            days = int(match.group(1))
            return f"newer_than:{days}d", f"últimos {days} dias", rest

    take("hoje")
    return f"after:{today:%Y/%m/%d}", "hoje", rest


def parse(text: str, timezone: str = "America/Sao_Paulo") -> Query | None:
    """Devolve a Query, ou None se não sobrar nenhum termo de busca."""
    text = text.strip()
    tz = ZoneInfo(timezone)

    # Já é sintaxe do Gmail: respeita e só garante um recorte de tempo.
    if RAW_QUERY.search(text):
        has_window = re.search(r"\b(after|before|newer_than|older_than|newer|older):", text, re.I)
        window = "" if has_window else f" newer_than:1d"
        return Query(gmail=f"({text}){window}", label="busca avançada")

    tokens = re.findall(r"[\w@.\-]+", text.lower())
    period, period_label, tokens = _period(tokens, tz)
    terms = [t for t in tokens if t not in STOPWORDS and len(t) > 1]

    if not terms:
        return None

    joined = " OR ".join(terms) if len(terms) > 1 else terms[0]
    pretty = ", ".join(terms)

    # Primeiro tenta por remetente — é o que "email da vercel" quer dizer.
    # Se não achar nada, o chamador tenta o fallback, que busca em qualquer lugar.
    return Query(
        gmail=f"from:({joined}) {period}".strip(),
        label=f"{pretty} · {period_label}",
        fallback=f"({' '.join(terms)}) {period}".strip(),
    )
