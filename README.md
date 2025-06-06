# Woodway Searchbot

Telegram bot that serves wood species images using natural language queries. It indexes a mounted network share and leverages Google Gemini Flash to parse user text.

## Features
- Gemini Flash 2.5 via `google-generativeai` to extract keywords in English.
- Fuzzy search on an auto-refreshed index of images.
- Sends up to five random photos per keyword.
- Runs in Docker and polls Telegram 24/7.

## Setup
1. Copy `.env.example` to `.env` and fill in credentials.
2. Ensure the Windows share is accessible and mounted via SMB.
   On Windows, you can set `SHARE_PATH` to a drive letter like `P:`
   and the bot will automatically normalize it to `P:\`.
   The path must also be available inside the container. Map the share as a
   volume in `docker-compose.yml` and point `SHARE_PATH` to the container
   mount location, e.g.:

   ```yaml
   services:
     bot:
       volumes:
         - P:\\:/data/share:ro
   ```

   Then set `SHARE_PATH=/data/share` in `.env`.
3. Build and start with Docker Compose:

```bash
docker compose up -d
```

The service will create `index.json` in the container and update it every ten minutes by default.

## Image Formats
Supported extensions: `.jpg`, `.jpeg`, `.png`, `.webp`, `.bmp`, `.tif`.

## Testing
The project includes a comprehensive test suite for all bot components. You can run the tests in several ways:

### Running Tests Locally
To run tests locally, execute:

```bash
python -m unittest discover -s bot/tests
```

### Running Tests with Docker
To run tests in a Docker container, use the test-specific Docker Compose configuration:

```bash
docker compose -f docker-compose.test.yml up
```

### Test Structure
- `bot/tests/test_search.py`: Tests for the search functionality
- `bot/tests/test_config.py`: Tests for configuration loading
- `bot/tests/test_indexer.py`: Tests for the file indexer
- `bot/tests/test_handlers.py`: Tests for Telegram message handlers
- `bot/tests/test_gemini.py`: Tests for Gemini API client

The tests use mock objects to avoid making actual API calls during testing.

## Continuous Integration
This repository uses GitHub Actions to lint, format and test the code on every pull request. The `ci.yml` workflow installs dependencies with `uv` using the `--system` flag and installs `ruff` separately, runs `ruff` for linting and formatting checks, executes the unit tests and generates a signed SBOM.
