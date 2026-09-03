# Gmail Marketplace Telegram Bot

A Telegram bot for Gmail farming and marketplace operations with support for ETB currency, Telebirr/CBE withdrawals, admin task management, and PostgreSQL / SQLite storage.

## Components
- `requirements.txt`: Python package dependencies (including `psycopg2-binary` for PostgreSQL).
- `config.py`: Environment variables and configuration settings.
- `models.py`: SQLAlchemy database models (User, Account, Transaction, WithdrawalRequest).
- `services/user_service.py`: User balance, referral, and withdrawal operations.
- `services/account_service.py`: Gmail account lifecycle management.
- `handlers/start.py`: Bot start, help, referrals, settings handlers.
- `handlers/seller.py`: Gmail task execution, submission, and payout withdrawal handlers.
- `handlers/buyer.py`: Marketplace browsing and buyer handlers.
- `handlers/admin.py`: Admin task creation wizard, submission approvals, withdrawal approvals.
- `main.py`: Main entry point and bot initialization.
- `Procfile`: Worker process definition for Railway deployments.

## Deployment on Railway (Python Worker + PostgreSQL)

1. **Create a Railway Project**:
   - Go to [Railway](https://railway.app/) and create a new project from your GitHub repository.

2. **Add PostgreSQL Service**:
   - In your Railway project canvas, click **+ New** -> **Database** -> **Add PostgreSQL**.

3. **Configure Environment Variables**:
   - In your Railway Python service settings, set the following environment variables under **Variables**:
     - `BOT_TOKEN`: Your Telegram Bot API Token from @BotFather.
     - `ADMIN_IDS`: Comma-separated list of admin Telegram IDs (e.g., `123456789,987654321`).
     - `DATABASE_URL`: `${{Postgres.DATABASE_URL}}` (Railway reference to attached PostgreSQL service).

4. **Start Command**:
   - Railway automatically uses the `Procfile` worker process command: `python main.py`.
