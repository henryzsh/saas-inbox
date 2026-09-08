FROM python:3.12-slim

WORKDIR /app

# Dependências primeiro: essa camada só é reconstruída quando elas mudam.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY inbox/ ./inbox/
COPY bot.py run_digest.py config.yaml ./

# Não roda como root: o bot só precisa de rede.
RUN useradd --create-home --uid 10001 app && chown -R app:app /app
USER app

# -u mantém os logs sem buffer, para o docker logs mostrar em tempo real.
CMD ["python", "-u", "bot.py"]
