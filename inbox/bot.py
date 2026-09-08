"""Bot do Telegram: você pergunta, ele busca no Gmail e responde.

Responde APENAS ao chat definido em TELEGRAM_CHAT_ID — sem isso, qualquer
pessoa que descobrisse o bot poderia ler a sua caixa de entrada.
"""

from __future__ import annotations

import logging
import re
import time
import unicodedata
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

from . import digest, parser, telegram
from .config import Config
from .gmail import Gmail

log = logging.getLogger("bot")

API = "https://api.telegram.org/bot{token}/{method}"
MAX_RESULTS = 15
POLL_TIMEOUT = 25

AJUDA = """👋 <b>Como usar</b>

Escreva o que você procura. O padrão é <b>hoje</b>:

<code>email da vercel</code>
<code>nubank ontem</code>
<code>github semana</code>
<code>amazon 3d</code>

<b>Períodos:</b> hoje · ontem · semana · mes · <code>7d</code> · tudo

<b>Comandos</b>
/hoje — resumo do dia por categoria
/naolidos — tudo que não foi lido
/ajuda — esta mensagem

Também aceito a sintaxe do Gmail direto:
<code>from:vercel.com is:unread</code>
<code>subject:fatura semana</code>"""


# Quem manda "oi" quer descobrir o que dá para fazer, não buscar remetente "oi".
SAUDACOES = {
    "oi", "ola", "opa", "eae", "e ai", "hey", "hi", "hello", "alo",
    "bom dia", "boa tarde", "boa noite", "teste", "test", "?", "menu",
    "comandos", "help", "ajuda", "como funciona", "o que voce faz",
}


def _normalize(text: str) -> str:
    """minúsculas, sem acento e sem pontuação — para casar saudações."""
    plain = unicodedata.normalize("NFKD", text.lower())
    plain = "".join(c for c in plain if not unicodedata.combining(c))
    return re.sub(r"[^\w\s]", "", plain).strip()


class Bot:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.gmail = Gmail(cfg)
        self.chat_id = str(cfg.telegram_chat_id)

    # -- transporte ---------------------------------------------------------

    def _call(self, method: str, **params):
        response = requests.get(
            API.format(token=self.cfg.telegram_token, method=method),
            params=params,
            timeout=POLL_TIMEOUT + 15,
        )
        return response.json()

    def _reply(self, blocks: list[str]) -> None:
        telegram.send(self.cfg.telegram_token, self.chat_id, blocks)

    def _typing(self) -> None:
        try:
            self._call("sendChatAction", chat_id=self.chat_id, action="typing")
        except requests.RequestException:
            pass

    # -- lógica -------------------------------------------------------------

    def _fetch(self, query: str) -> list:
        ids = self.gmail.search(query, MAX_RESULTS)
        return self.gmail.fetch(ids) if ids else []

    def handle(self, text: str) -> list[str]:
        text = text.strip()
        command = text.lower().split()[0] if text else ""

        if command in ("/start", "/ajuda", "/help"):
            return [AJUDA]

        if _normalize(text) in SAUDACOES:
            return [AJUDA]

        if command == "/hoje":
            today = datetime.now(ZoneInfo(self.cfg.timezone)).date()
            found = digest.collect(
                self.gmail, self.cfg, exclude_sent=False, window=f"after:{today:%Y/%m/%d}"
            )
            return digest.render(self.cfg, found) if found else digest.render_empty(self.cfg)

        if command == "/naolidos":
            messages = self._fetch("is:unread")
            return (
                digest.render_results(self.cfg, "não lidos", messages)
                if messages
                else ["📭 Nada não lido."]
            )

        query = parser.parse(text, self.cfg.timezone)
        if query is None:
            return ["🤔 Não entendi o que buscar. Tente <code>email da vercel</code> ou /ajuda."]

        try:
            messages = self._fetch(query.gmail)
            # "email da vercel" busca por remetente; se não achar, amplia.
            if not messages and query.fallback:
                messages = self._fetch(query.fallback)
        except Exception as exc:  # noqa: BLE001
            log.exception("busca falhou")
            return [f"⚠️ A busca falhou: <code>{telegram.escape(str(exc)[:200])}</code>"]

        if not messages:
            return [
                f"📭 Nada encontrado para <b>{telegram.escape(query.label)}</b>.\n\n"
                "Tente ampliar o período: <code>"
                f"{telegram.escape(query.label.split(' · ')[0])} semana</code>  ·  /ajuda"
            ]
        return digest.render_results(self.cfg, query.label, messages)

    # -- loop ---------------------------------------------------------------

    def run(self) -> None:
        me = self._call("getMe")
        if not me.get("ok"):
            raise SystemExit(f"Token do Telegram inválido: {me.get('description')}")
        log.info("bot @%s no ar, respondendo apenas ao chat %s",
                 me["result"].get("username"), self.chat_id)

        offset = None
        while True:
            try:
                params = {"timeout": POLL_TIMEOUT}
                if offset is not None:
                    params["offset"] = offset
                payload = self._call("getUpdates", **params)
            except requests.RequestException as exc:
                log.warning("rede instável (%s), tentando de novo em 5s", exc)
                time.sleep(5)
                continue

            if not payload.get("ok"):
                log.error("getUpdates: %s", payload.get("description"))
                time.sleep(5)
                continue

            for update in payload.get("result", []):
                offset = update["update_id"] + 1
                message = update.get("message") or update.get("edited_message") or {}
                text = message.get("text", "")
                sender = str(message.get("chat", {}).get("id", ""))

                if not text:
                    continue
                if sender != self.chat_id:
                    log.warning("ignorando mensagem do chat não autorizado %s", sender)
                    continue

                log.info("consulta: %r", text)
                self._typing()
                try:
                    self._reply(self.handle(text))
                except Exception:  # noqa: BLE001
                    log.exception("falha ao responder")
                    try:
                        self._reply(["⚠️ Deu erro aqui. Veja o log do bot."])
                    except Exception:  # noqa: BLE001
                        pass
