FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libjpeg62-turbo libwebp7 libtiff6 && \
    rm -rf /var/lib/apt/lists/*

RUN useradd -m bot
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chown -R bot:bot /app
USER bot

CMD ["python", "-m", "bot.main"]
