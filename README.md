# new_bal_bot

Telegram survey bot using aiogram, SQLAlchemy and Alembic.

Environment variables (see `.env.example`):
- BOT_TOKEN - Telegram bot token
- DATABASE_URL - Async Postgres DSN, e.g. `postgresql+asyncpg://user:pass@localhost/dbname`

Setup

1. Create a virtualenv and install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Configure `.env` from `.env.example`.
3. Initialize alembic and run migrations (provided sample):

```bash
alembic upgrade head
```

4. Run the bot:

```bash
python main.py
```

Docker (recommended)

1. Create a `.env` file with `BOT_TOKEN`.
2. Start services:

```bash
docker-compose up --build
```

PGAdmin will be available at http://localhost:8080 (admin@local / admin). PostgreSQL listens on 5432.
