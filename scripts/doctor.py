#!/usr/bin/env python3
"""Checkup do setup: valida credenciais, escopos e queries antes de ir pra nuvem.

    python scripts/doctor.py           # só valida, não envia nada
    python scripts/doctor.py --send    # também manda uma mensagem de teste

Por privacidade, mostra apenas a CONTAGEM de e-mails por categoria — nunca
remetentes ou assuntos.
"""

import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from inbox import config  # noqa: E402
from inbox.gmail import Gmail  # noqa: E402

OK, FAIL, WARN = "  ✅", "  ❌", "  ⚠️ "


def main() -> int:
    send_test = "--send" in sys.argv
    problems = 0

    print("\n1. Configuração")
    try:
        cfg = config.load()
    except SystemExit as exc:
        print(FAIL, exc)
        return 1
    print(OK, f"config.yaml: {len(cfg.categories)} categorias, lookback {cfg.lookback}")

    print("\n2. Gmail")
    try:
        gmail = Gmail(cfg)
        profile = gmail.service.users().getProfile(userId="me").execute()
        print(OK, f"autenticado como {profile['emailAddress']}")
        print(OK, f"{profile.get('messagesTotal', 0):,} mensagens na conta".replace(",", "."))
    except Exception as exc:  # noqa: BLE001
        print(FAIL, f"falha ao autenticar: {exc}")
        print("     Refaça: .venv/bin/python scripts/setup_oauth.py")
        return 1

    try:
        label_id = gmail.ensure_label(cfg.sent_label)
        print(OK, f'label "{cfg.sent_label}" pronta ({label_id})')
    except Exception as exc:  # noqa: BLE001
        print(FAIL, f"não consegui criar a label: {exc}")
        print("     O escopo precisa ser gmail.modify (não readonly).")
        problems += 1

    print("\n3. Suas queries")
    total = 0
    for category in cfg.categories:
        query = f"({category.query}) -label:{cfg.sent_label} newer_than:{cfg.lookback}"
        try:
            found = len(gmail.search(query, cfg.max_per_category))
        except Exception as exc:  # noqa: BLE001
            print(FAIL, f"{category.name}: query inválida — {exc}")
            problems += 1
            continue
        total += found
        mark = OK if found else WARN
        print(mark, f"{category.name}: {found} e-mail(s)")
    if total == 0:
        print(WARN, "nenhuma categoria retornou nada — amplie o lookback ou revise as queries")

    print("\n4. Telegram")
    base = f"https://api.telegram.org/bot{cfg.telegram_token}"
    me = requests.get(f"{base}/getMe", timeout=30).json()
    if not me.get("ok"):
        print(FAIL, f"token inválido: {me.get('description')}")
        return 1
    print(OK, f"bot @{me['result'].get('username')}")

    chat = requests.get(f"{base}/getChat", params={"chat_id": cfg.telegram_chat_id}, timeout=30).json()
    if not chat.get("ok"):
        print(FAIL, f"chat_id não acessível: {chat.get('description')}")
        print("     Mande uma mensagem para o bot e rode scripts/telegram_chat_id.py de novo.")
        problems += 1
    else:
        print(OK, f"chat acessível (id {cfg.telegram_chat_id})")

    if send_test:
        sent = requests.post(
            f"{base}/sendMessage",
            json={"chat_id": cfg.telegram_chat_id, "text": "✅ saas-inbox conectado."},
            timeout=30,
        ).json()
        print(OK if sent.get("ok") else FAIL, "mensagem de teste enviada"
              if sent.get("ok") else f"envio falhou: {sent.get('description')}")
        problems += 0 if sent.get("ok") else 1

    print("\n" + ("Tudo certo." if not problems else f"{problems} problema(s) acima."))
    if not problems:
        print("Próximo: .venv/bin/python run_digest.py --dry-run")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
