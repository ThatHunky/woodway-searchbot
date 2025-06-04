# Woodway Searchbot

Telegram bot that serves wood species images using natural language queries. It indexes a mounted network share and leverages Google Gemini Flash to parse user text.

## Features
- Gemini Flash 2.5 via `google-generativeai` to extract keywords in English.
- Fuzzy search on an auto-refreshed index of images.
- Sends up to five random photos per keyword.
- Runs in Docker and polls Telegram 24/7.

## Setup
1. Copy `.env.example` to `.env` and fill in credentials.
2. Ensure the Windows share is accessible and mapped via CIFS.
3. Build and start with Docker Compose:

```bash
docker compose up -d
```

The service will create `index.json` in the container and update it every ten minutes by default.

## Image Formats
Supported extensions: `.jpg`, `.jpeg`, `.png`, `.webp`, `.bmp`, `.tif`.
