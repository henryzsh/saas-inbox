# saas-inbox

Digest da sua caixa do Gmail, filtrado pelas **suas** regras, entregue no Telegram.

Roda no GitHub Actions (grátis, não precisa do seu PC ligado). O estado — o que já
foi enviado — mora no próprio Gmail, como a label `Digest/Enviado`. Nada de banco
nem de arquivo de estado: se você remover a label de um e-mail, ele volta no
próximo digest.

```
Gmail API ──> config.yaml (regras) ──> agrupa por categoria ──> Telegram
     ^                                                              |
     └──────────── aplica label "Digest/Enviado" <──────────────────┘
```

---

## Setup

São três etapas: Google, Telegram e GitHub. ~20 minutos, uma vez só.

### 1. Google Cloud (acesso ao Gmail)

1. Crie um projeto em <https://console.cloud.google.com/projectcreate>.
2. Ative a Gmail API: **APIs & Services → Library → Gmail API → Enable**.
3. **Tela de consentimento** (agora chamada *Google Auth Platform*):

   Em **Audience**, escolha **External**. Depois vá em **Data access** e adicione o
   escopo `https://www.googleapis.com/auth/gmail.modify`.

   Para publicar em produção, a página **Branding** precisa estar completa — e é
   aqui que quase todo mundo trava com o erro *"A configuração de OAuth do
   aplicativo está incompleta"*. O botão **Publish** só libera com **todos** estes
   campos preenchidos:

   | Campo | Valor |
   |---|---|
   | App name | ⚠️ **não pode conter "Gmail" nem "Google"** — use `Inbox Digest` |
   | User support email | seu e-mail |
   | Developer contact email | seu e-mail |
   | **Authorized domain** | `henryzsh.github.io` — **preencha este primeiro** |
   | **Application home page** | `https://henryzsh.github.io/saas-inbox/` |
   | **Privacy policy link** | `https://henryzsh.github.io/saas-inbox/privacy.html` |
   | Terms of service | pode deixar vazio |

   > A ordem importa: o *Authorized domain* precisa ser salvo **antes** das URLs,
   > senão os campos de home page e privacidade são recusados.

   As duas páginas exigidas já estão prontas em [`docs/`](docs/). Para colocá-las no
   ar de graça: **Settings → Pages → Source: Deploy from a branch → branch `main`,
   pasta `/docs` → Save**. Em ~1 minuto elas respondem nas URLs acima. Confirme que
   abrem no navegador antes de voltar ao console do Google.

   Feito isso, volte em **Audience → Publish app**.

   > ⚠️ **Não deixe em "Testing".** Nesse modo o refresh token **expira em 7 dias**
   > e a automação quebra toda semana. Publicado, o token dura indefinidamente.
   > Como você é o único usuário, o Google mostra uma vez a tela "o Google não
   > verificou este app" — clique em **Avançado → Ir para (app)**. Verificação
   > formal só é exigida para distribuir a terceiros.

4. **Credentials → Create credentials → OAuth client ID → Desktop app**.
   Baixe o JSON como `client_secret.json` na raiz deste projeto.

5. Gere o refresh token:

   ```bash
   python -m venv .venv && .venv/bin/pip install -r requirements.txt
   .venv/bin/python scripts/setup_oauth.py client_secret.json
   ```

   O script imprime uma URL. Abra no navegador (pode ser no Windows — o WSL
   recebe o retorno em `localhost:8765`), autorize, e ele devolve os três valores
   `GOOGLE_*` para você guardar.

### 2. Telegram (entrega)

1. No Telegram, fale com [@BotFather](https://t.me/BotFather) → `/newbot` → escolha
   nome e username. Ele devolve o `TELEGRAM_BOT_TOKEN`.
2. Mande um "oi" para o seu bot recém-criado (o Telegram não deixa um bot iniciar
   conversa com você).
3. Descubra o chat id:

   ```bash
   .venv/bin/python scripts/telegram_chat_id.py <BOT_TOKEN>
   ```

### 3. Rodar

Local, para testar:

```bash
cp .env.example .env      # preencha com os 5 valores
.venv/bin/python run_digest.py --dry-run   # prévia no terminal, não envia nada
.venv/bin/python run_digest.py             # envia de verdade
```

Na nuvem: em **Settings → Secrets and variables → Actions**, crie os 5 secrets
(`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REFRESH_TOKEN`,
`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`). O workflow roda 08:00 e 18:00 (horário
de Brasília) e também sob demanda pela aba **Actions → Run workflow**.

---

## Definindo o que chega

Tudo em [`config.yaml`](config.yaml). Cada categoria tem um nome, um emoji e uma
`query` — que aceita **a mesma sintaxe da barra de busca do Gmail**:

```yaml
categories:
  - name: Financeiro
    emoji: "💰"
    query: "is:unread (from:nubank OR subject:(fatura OR boleto))"
```

Operadores úteis: `from:` `to:` `subject:` `label:` `category:primary|social|promotions`
`is:unread` `is:starred` `has:attachment` `newer_than:2d` `-termo` (exclui)
`(a OR b)` `"frase exata"`.

Dica: monte a query na barra de busca do Gmail até o resultado ficar certo, depois
copie para o YAML.

Duas regras de comportamento que valem lembrar:

- **A ordem importa.** Um e-mail que casa com duas categorias entra só na primeira
  da lista — nunca aparece duplicado.
- **A query é sempre combinada** com `-label:Digest/Enviado newer_than:<lookback>`,
  então você não precisa se preocupar com repetição nem com e-mails antigos.

## Comandos

| Comando | O que faz |
|---|---|
| `run_digest.py --dry-run` | Mostra a prévia no terminal. Não envia, não marca nada. |
| `run_digest.py --no-label` | Envia mas não marca — os mesmos e-mails voltam no próximo. Útil ao ajustar o formato. |
| `run_digest.py` | Envia e marca. |

## Estrutura

```
config.yaml              suas regras — o arquivo que você edita
run_digest.py            entrypoint
inbox/config.py          carrega YAML + env, valida cedo
inbox/gmail.py           OAuth, busca, leitura em lote (só cabeçalhos), labels
inbox/digest.py          aplica as regras, deduplica, formata
inbox/telegram.py        envio + divisão no limite de 4096 caracteres
scripts/setup_oauth.py   gera o refresh token (rodar uma vez)
scripts/telegram_chat_id.py
docs/                    home page + política de privacidade (GitHub Pages)
.github/workflows/digest.yml
```

## Notas

- O digest lê apenas **cabeçalhos e o snippet** (`format=metadata`), nunca baixa o
  corpo dos e-mails. É rápido e barato em cota.
- O escopo `gmail.modify` permite ler e etiquetar, mas **não** exclui nada
  permanentemente.
- Cotas do Gmail são generosas (1 bilhão de unidades/dia); um digest destes gasta
  algumas centenas.

## Próximos passos possíveis

- **Inventário de inscrições**: varrer os últimos meses procurando o cabeçalho
  `List-Unsubscribe` (já capturado em `inbox/gmail.py`), ranquear remetentes por
  volume e devolver a lista com o link de descadastro de cada um.
- **Botões de ação** no Telegram (arquivar, silenciar remetente) via webhook —
  "silenciar" pode criar um filtro de verdade no Gmail, adicionando o escopo
  `gmail.settings.basic`.
