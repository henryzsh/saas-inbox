#!/usr/bin/env python3
"""Gera o refresh token do Google. Rode UMA VEZ, na sua máquina.

Uso:
    python scripts/setup_oauth.py client_secret.json
"""

import json
import sys
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from inbox.config import SCOPES  # noqa: E402

PORT = 8765


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1

    secret_file = Path(sys.argv[1])
    if not secret_file.exists():
        print(f"Arquivo não encontrado: {secret_file}")
        return 1

    flow = InstalledAppFlow.from_client_secrets_file(str(secret_file), SCOPES)

    print("\nAbra este endereço no navegador (pode ser no Windows, o WSL recebe o retorno):\n")
    creds = flow.run_local_server(
        port=PORT,
        open_browser=False,
        authorization_prompt_message="{url}\n",
        success_message="Pronto. Pode fechar esta aba e voltar ao terminal.",
    )

    if not creds.refresh_token:
        print(
            "\nO Google não devolveu refresh_token. Isso acontece quando a conta já "
            "autorizou este app antes.\nRevogue em https://myaccount.google.com/permissions "
            "e rode de novo."
        )
        return 1

    data = json.loads(secret_file.read_text())
    installed = data.get("installed") or data.get("web") or {}

    print("\n" + "=" * 70)
    print("Cole estes três valores no .env local E nos GitHub Secrets:")
    print("=" * 70)
    print(f"GOOGLE_CLIENT_ID={installed.get('client_id', '')}")
    print(f"GOOGLE_CLIENT_SECRET={installed.get('client_secret', '')}")
    print(f"GOOGLE_REFRESH_TOKEN={creds.refresh_token}")
    print("=" * 70)
    print("\nNão versione esses valores. O .gitignore já cobre .env e client_secret*.json.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
