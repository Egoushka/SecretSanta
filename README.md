# Secret Santa Bot

## Local setup

1. Create a virtual environment and install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Configure environment variables (or use a `.env` file):

- `BOT_TOKEN` - Telegram bot token
- `DATABASE_URL` - SQLAlchemy database URL (PostgreSQL recommended)
- `LOG_LEVEL` - optional, default `INFO`
- `LOG_PATH` - optional, default `logs/telegram_bot.log`

3. Run migrations and start the bot:

```bash
alembic upgrade head
python main.py
```

## Migrations

Alembic uses `DATABASE_URL` for both offline and online migrations.

- Upgrade: `alembic upgrade head`
- Create revision: `alembic revision -m "your message" --autogenerate`

## Running tests

```bash
pytest
```

## Docker

```bash
docker build -t secretsanta .
docker run --env BOT_TOKEN=... --env DATABASE_URL=... secretsanta
```

## Upgrade flow (Pro plan)

- `/upgrade` in a group generates a token.
- `/activate <token>` enables Pro manually for now.

This keeps payments decoupled and allows you to validate demand before automating checkout.
