#!/usr/bin/env python3
"""Entrypoint do digest: Gmail -> regras do config.yaml -> Telegram."""

import argparse
import re
import sys

from inbox import config, digest, telegram
from inbox.gmail import Gmail


def main() -> int:
    parser = argparse.ArgumentParser(description="Envia o digest da inbox para o Telegram.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostra o resultado no terminal sem enviar nada nem marcar e-mails.",
    )
    parser.add_argument(
        "--no-label",
        action="store_true",
        help="Envia mas não aplica a label — os mesmos e-mails voltam no próximo digest.",
    )
    args = parser.parse_args()

    cfg = config.load()
    gmail = Gmail(cfg)
    label_id = gmail.ensure_label(cfg.sent_label)

    by_category = digest.collect(gmail, cfg, label_id)

    if not by_category:
        print("Nenhum e-mail novo bateu com as regras.")
        if cfg.notify_when_empty and not args.dry_run:
            telegram.send(cfg.telegram_token, cfg.telegram_chat_id, digest.render_empty(cfg))
        return 0

    blocks = digest.render(cfg, by_category)

    if args.dry_run:
        print("\n--- PRÉVIA (nada foi enviado) ---\n")
        for block in blocks:
            print(re.sub(r"<[^>]+>", "", block), "\n")
        return 0

    telegram.send(cfg.telegram_token, cfg.telegram_chat_id, blocks)

    sent_ids = [m.id for messages in by_category.values() for m in messages]
    if not args.no_label:
        gmail.add_label(sent_ids, label_id)

    print(f"Enviados {len(sent_ids)} e-mails em {len(by_category)} categorias.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
