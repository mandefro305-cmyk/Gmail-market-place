import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.isdigit()]
default_db = "/var/data/marketplace.db" if os.path.exists("/var/data") else "marketplace.db"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{default_db}")
