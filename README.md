# Gmail Marketplace Telegram Bot

A Telegram bot for Gmail farming and marketplace operations.

## Components
- `requirements.txt`: Python package dependencies.
- `config.py`: Environment variables and configuration settings.
- `models.py`: SQLAlchemy database models (User, Account, Transaction).
- `services/user_service.py`: User balance and account operations.
- `services/account_service.py`: Gmail account lifecycle management.
- `handlers/start.py`: Bot start, help, referrals, settings handlers.
- `handlers/seller.py`: Gmail registration and seller handlers.
- `handlers/buyer.py`: Marketplace browsing and buyer handlers.
- `handlers/admin.py`: Admin moderation and approval handlers.
- `main.py`: Main entry point and bot initialization.
