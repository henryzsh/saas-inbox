"""Carrega config.yaml + variáveis de ambiente, falhando cedo e com mensagem clara."""

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent

# Escopo: lê mensagens e aplica labels. Não permite exclusão permanente.
# Para criar filtros do Gmail no futuro, adicione:
#   https://www.googleapis.com/auth/gmail.settings.basic
SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


@dataclass
class Category:
    name: str
    query: str
    emoji: str = "•"


@dataclass
class Config:
    timezone: str = "America/Sao_Paulo"
    lookback: str = "2d"
    sent_label: str = "Digest/Enviado"
    max_per_category: int = 12
    notify_when_empty: bool = False
    categories: list[Category] = field(default_factory=list)

    client_id: str = ""
    client_secret: str = ""
    refresh_token: str = ""
    telegram_token: str = ""
    telegram_chat_id: str = ""


def _require(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(
            f"Variável de ambiente {name} não definida.\n"
            "Local: copie .env.example para .env e preencha.\n"
            "GitHub Actions: adicione em Settings > Secrets and variables > Actions."
        )
    return value


def load(path: Path | None = None) -> Config:
    load_dotenv(ROOT / ".env")
    raw = yaml.safe_load((path or ROOT / "config.yaml").read_text(encoding="utf-8"))

    categories = [
        Category(name=c["name"], query=c["query"].strip(), emoji=c.get("emoji", "•"))
        for c in raw.get("categories", [])
    ]
    if not categories:
        raise SystemExit("Nenhuma categoria definida em config.yaml.")

    return Config(
        timezone=raw.get("timezone", "America/Sao_Paulo"),
        lookback=str(raw.get("lookback", "2d")),
        sent_label=raw.get("sent_label", "Digest/Enviado"),
        max_per_category=int(raw.get("max_per_category", 12)),
        notify_when_empty=bool(raw.get("notify_when_empty", False)),
        categories=categories,
        client_id=_require("GOOGLE_CLIENT_ID"),
        client_secret=_require("GOOGLE_CLIENT_SECRET"),
        refresh_token=_require("GOOGLE_REFRESH_TOKEN"),
        telegram_token=_require("TELEGRAM_BOT_TOKEN"),
        telegram_chat_id=_require("TELEGRAM_CHAT_ID"),
    )
