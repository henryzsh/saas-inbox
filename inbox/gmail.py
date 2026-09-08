"""Cliente Gmail: busca, leitura em lote de cabeçalhos e aplicação de labels."""

from __future__ import annotations

import email.utils
from dataclasses import dataclass
from datetime import datetime, timezone as dt_timezone

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from .config import SCOPES, Config

TOKEN_URI = "https://oauth2.googleapis.com/token"

# A API do Gmail aceita até 100 requests por batch; 50 dá margem confortável.
BATCH_SIZE = 50

HEADERS = ["From", "Subject", "Date", "List-Unsubscribe"]


@dataclass
class Message:
    id: str
    thread_id: str
    sender_name: str
    sender_email: str
    subject: str
    snippet: str
    date: datetime | None
    unsubscribe: str | None

    @property
    def link(self) -> str:
        return f"https://mail.google.com/mail/u/0/#all/{self.id}"


def _parse_sender(raw: str) -> tuple[str, str]:
    name, addr = email.utils.parseaddr(raw)
    return (name or addr.split("@")[0] or "?"), addr


def _parse_date(raw: str) -> datetime | None:
    try:
        parsed = email.utils.parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        return None
    # Alguns remetentes mandam Date sem offset; assume UTC para não quebrar.
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt_timezone.utc)


class Gmail:
    def __init__(self, cfg: Config):
        creds = Credentials(
            token=None,
            refresh_token=cfg.refresh_token,
            client_id=cfg.client_id,
            client_secret=cfg.client_secret,
            token_uri=TOKEN_URI,
            scopes=SCOPES,
        )
        creds.refresh(Request())
        self.service = build("gmail", "v1", credentials=creds, cache_discovery=False)

    # -- labels -------------------------------------------------------------

    def ensure_label(self, name: str) -> str:
        """Devolve o id da label, criando-a (e os níveis pai) se necessário."""
        existing = {
            label["name"]: label["id"]
            for label in self.service.users().labels().list(userId="me").execute().get("labels", [])
        }
        if name in existing:
            return existing[name]

        # "Digest/Enviado" exige que "Digest" exista antes.
        parts = name.split("/")
        label_id = ""
        for depth in range(1, len(parts) + 1):
            path = "/".join(parts[:depth])
            if path in existing:
                label_id = existing[path]
                continue
            created = (
                self.service.users()
                .labels()
                .create(
                    userId="me",
                    body={
                        "name": path,
                        "labelListVisibility": "labelShow",
                        "messageListVisibility": "show",
                    },
                )
                .execute()
            )
            existing[path] = label_id = created["id"]
        return label_id

    # -- leitura ------------------------------------------------------------

    def search(self, query: str, limit: int) -> list[str]:
        result = (
            self.service.users()
            .messages()
            .list(userId="me", q=query, maxResults=min(limit, 500))
            .execute()
        )
        return [m["id"] for m in result.get("messages", [])][:limit]

    def fetch(self, message_ids: list[str]) -> list[Message]:
        """Busca só os cabeçalhos (format=metadata) em lote — rápido e barato."""
        collected: dict[str, Message] = {}
        errors: list[Exception] = []

        def collect(request_id, response, error):
            if error is not None:
                errors.append(error)
                return
            headers = {
                h["name"].lower(): h["value"]
                for h in response.get("payload", {}).get("headers", [])
            }
            name, addr = _parse_sender(headers.get("from", ""))
            collected[response["id"]] = Message(
                id=response["id"],
                thread_id=response.get("threadId", response["id"]),
                sender_name=name,
                sender_email=addr,
                subject=headers.get("subject", "(sem assunto)"),
                snippet=response.get("snippet", ""),
                date=_parse_date(headers.get("date", "")),
                unsubscribe=headers.get("list-unsubscribe"),
            )

        for start in range(0, len(message_ids), BATCH_SIZE):
            batch = self.service.new_batch_http_request(callback=collect)
            for message_id in message_ids[start : start + BATCH_SIZE]:
                batch.add(
                    self.service.users().messages().get(
                        userId="me",
                        id=message_id,
                        format="metadata",
                        metadataHeaders=HEADERS,
                    )
                )
            batch.execute()

        if errors and not collected:
            raise errors[0]

        # Preserva a ordem devolvida pela busca (mais recente primeiro).
        return [collected[mid] for mid in message_ids if mid in collected]

    # -- escrita ------------------------------------------------------------

    def add_label(self, message_ids: list[str], label_id: str) -> None:
        for start in range(0, len(message_ids), 900):  # batchModify aceita 1000 ids
            self.service.users().messages().batchModify(
                userId="me",
                body={"ids": message_ids[start : start + 900], "addLabelIds": [label_id]},
            ).execute()
