FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=5000
EXPOSE 5000

# urlopen levanta exceção em qualquer status que não seja 2xx, então um 503
# do /health já faz o python sair com erro e o container ficar unhealthy.
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT}/health', timeout=4)"

CMD ["sh", "-c", "gunicorn run:app --bind 0.0.0.0:${PORT}"]
