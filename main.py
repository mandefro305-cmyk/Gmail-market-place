import logging
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from config import BOT_TOKEN
from models import init_db
from handlers.start import start_command, help_command, referrals_command, settings_command
from handlers.seller import register_conv_handler, my_accounts_command, balance_command, withdraw_command
from handlers.admin import admin_panel_command, list_pending_command, admin_review_conv_handler
from handlers.buyer import marketplace_command, deposit_command, buy_callback_handler

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

def create_application() -> Application:
    init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.Regex("^💬 Help$"), help_command))
    app.add_handler(CommandHandler("referrals", referrals_command))
    app.add_handler(MessageHandler(filters.Regex("^👥 My referrals$"), referrals_command))
    app.add_handler(CommandHandler("settings", settings_command))
    app.add_handler(MessageHandler(filters.Regex("^⚙️ Settings$"), settings_command))

    app.add_handler(register_conv_handler)
    app.add_handler(CommandHandler("my_accounts", my_accounts_command))
    app.add_handler(MessageHandler(filters.Regex("^📋 My accounts$"), my_accounts_command))
    app.add_handler(CommandHandler("balance", balance_command))
    app.add_handler(MessageHandler(filters.Regex("^💰 Balance$"), balance_command))
    app.add_handler(CommandHandler("withdraw", withdraw_command))

    app.add_handler(CommandHandler("admin", admin_panel_command))
    app.add_handler(CommandHandler("pending", list_pending_command))
    app.add_handler(admin_review_conv_handler)

    app.add_handler(CommandHandler("marketplace", marketplace_command))
    app.add_handler(CommandHandler("deposit", deposit_command))
    app.add_handler(CallbackQueryHandler(buy_callback_handler, pattern="^buy_acc_"))

    return app

def main():
    if BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN":
        logger.warning("BOT_TOKEN is not set. Please set BOT_TOKEN in environment variables or config.py.")

    app = create_application()
    logger.info("Starting Telegram Gmail Marketplace / Farmer Bot...")
    app.run_polling()

if __name__ == "__main__":
    main()
