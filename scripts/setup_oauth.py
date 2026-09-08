#!/usr/bin/env python3
"""Gera o refresh token do Google. Rode UMA VEZ, na sua máquina.

Usa GOOGLE_CLIENT_ID e GOOGLE_CLIENT_SECRET do .env:
    python scripts/setup_oauth.py

Ou, se preferir, o JSON baixado do console:
    python scripts/setup_oauth.py client_secret.json
"""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from google_auth_oauthlib.flow import InstalledAppFlow

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from inbox.config import ROOT, SCOPES  # noqa: E402

PORT = 8765


def flow_from_env() -> InstalledAppFlow:
    load_dotenv(ROOT / ".env")
    client_id = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()

    if not client_id or not client_secret:
        raise SystemExit(
            "GOOGLE_CLIENT_ID e/ou GOOGLE_CLIENT_SECRET não encontrados no .env.\n"
            "Pegue os dois em: console.cloud.google.com > APIs & Services > Credentials\n"
            "> (seu OAuth client) — ou passe o JSON baixado como argumento."
        )

    return InstalledAppFlow.from_client_config(
        {
            "installed": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["http://localhost"],
            }
        },
        SCOPES,
    )


def flow_from_file(path: Path) -> InstalledAppFlow:
    if not path.exists():
        raise SystemExit(f"Arquivo não encontrado: {path}")
    return InstalledAppFlow.from_client_secrets_file(str(path), SCOPES)


def main() -> int:
    if len(sys.argv) > 1:
        if sys.argv[1] in ("-h", "--help"):
            print(__doc__)
            return 0
        flow = flow_from_file(Path(sys.argv[1]))
    else:
        flow = flow_from_env()

    print("\nAbra este endereço no navegador (pode ser no Windows — o WSL recebe o retorno):\n")
    creds = flow.run_local_server(
        port=PORT,
        open_browser=False,
        authorization_prompt_message="{url}\n",
        success_message="Pronto. Pode fechar esta aba e voltar ao terminal.",
        # offline + consent garantem que o refresh_token venha mesmo se você
        # já tiver autorizado este app antes.
        access_type="offline",
        prompt="consent",
    )

    if not creds.refresh_token:
        print(
            "\nO Google não devolveu refresh_token.\n"
            "Revogue o acesso em https://myaccount.google.com/permissions e rode de novo."
        )
        return 1

    print("\n" + "=" * 72)
    print("Adicione esta linha ao seu .env e crie o secret de mesmo nome no GitHub:")
    print("=" * 72)
    print(f"GOOGLE_REFRESH_TOKEN={creds.refresh_token}")
    print("=" * 72)
    print("\nNão versione este valor. O .gitignore já cobre o .env.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
