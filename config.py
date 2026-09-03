import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()]

default_db = "/var/data/marketplace.db" if os.path.exists("/var/data") else "marketplace.db"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{default_db}")

# Railway and Heroku provide PostgreSQL connection URLs starting with postgres://
# SQLAlchemy 1.4+ requires postgresql://
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
