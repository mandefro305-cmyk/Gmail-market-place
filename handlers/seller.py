from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from models import SessionLocal, AccountStatus, TransactionType
from services.user_service import UserService
from services.account_service import AccountService

REGISTER_MANUAL_INPUT = 1

async def start_register_gmail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "➕ **Submit Gmail Account Details**\n\n"
        "Please send the account details in format:\n"
        "`email:password:recovery_email` or `email:password`\n\n"
        "*(Type /cancel to abort)*"
    )

    if update.callback_query:
        await update.callback_query.edit_message_text(msg, parse_mode="Markdown")
    elif update.message:
        await update.message.reply_text(msg, parse_mode="Markdown")

    return REGISTER_MANUAL_INPUT

async def process_manual_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    parts = text.split(":")
    if len(parts) < 2:
        await update.message.reply_text("❌ Invalid format. Please send as `email:password` or `email:password:recovery`:", parse_mode="Markdown")
        return REGISTER_MANUAL_INPUT

    email = parts[0].strip()
    password = parts[1].strip()
    recovery = parts[2].strip() if len(parts) > 2 else None

    user = update.effective_user
    db = SessionLocal()
    try:
        UserService.get_or_create_user(db, user.id, user.username, user.first_name)
        account = AccountService.register_account(
            session=db,
            creator_id=user.id,
            email=email,
            password=password,
            recovery_info=recovery
        )
        await update.message.reply_text(
            f"✅ **Account Registered!**\n\n"
            f"📧 **Email:** `{account.email}`\n"
            f"🆔 **Registration ID:** `{account.id}`\n\n"
            f"Status: ⏳ *Pending Review*",
            parse_mode="Markdown"
        )
    except ValueError as e:
        await update.message.reply_text(f"❌ Registration failed: {str(e)}")
    finally:
        db.close()
        context.user_data.clear()

    return ConversationHandler.END

async def cancel_register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("🚫 Registration cancelled.")
    return ConversationHandler.END

async def my_accounts_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db = SessionLocal()
    try:
        db_user = UserService.get_or_create_user(db, user.id, user.username, user.first_name)
        registered = db_user.registered_accounts
        bought = db_user.bought_accounts

        msg = "📋 **My Accounts**\n\n"

        if registered:
            msg += "🌾 **Registered Accounts:**\n"
            for acc in registered:
                payout_str = f" ({acc.creator_payout:.2f} ETB)" if acc.creator_payout is not None else ""
                status_emoji = {
                    AccountStatus.PENDING_REVIEW: "⏳ Pending Review",
                    AccountStatus.APPROVED: f"✅ Approved{payout_str}",
                    AccountStatus.REJECTED: f"❌ Rejected ({acc.rejection_reason or 'No reason'})",
                    AccountStatus.SOLD: f"💰 Sold{payout_str}"
                }.get(acc.status, acc.status)
                msg += f"• `{acc.email}` - {status_emoji}\n"
            msg += "\n"

        if bought:
            msg += "🛒 **Purchased Accounts:**\n"
            for acc in bought:
                msg += f"• `{acc.email}` | Pass: `{acc.password}`\n"
            msg += "\n"

        if not registered and not bought:
            msg += "You have not registered or purchased any accounts yet."

        await update.message.reply_text(msg, parse_mode="Markdown")
    finally:
        db.close()

async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db = SessionLocal()
    try:
        db_user = UserService.get_or_create_user(db, user.id, user.username, user.first_name)

        msg = f"💰 **Balance & Wallet**\n\n"
        msg += f"Available Balance: **{db_user.balance:.2f} ETB**\n\n"
        msg += "Select cashout / deposit options below or use commands:\n"
        msg += "• `/withdraw <amount>` - Cashout funds\n"
        msg += "• `/deposit <amount>` - Deposit funds"

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("💳 Withdraw Cash", callback_data="wallet_withdraw")],
            [InlineKeyboardButton("➕ Deposit Balance", callback_data="wallet_deposit")]
        ])

        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=keyboard)
    finally:
        db.close()

async def withdraw_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args
    if not args or not args[0].replace('.', '', 1).isdigit():
        await update.message.reply_text("Usage: `/withdraw <amount>`\nExample: `/withdraw 100`", parse_mode="Markdown")
        return

    amount = float(args[0])
    db = SessionLocal()
    try:
        UserService.deduct_balance(
            session=db,
            user_id=user.id,
            amount=amount,
            tx_type=TransactionType.WITHDRAWAL,
            description="User cashout request"
        )
        await update.message.reply_text(f"✅ Cashout request of **{amount:.2f} ETB** processed successfully!", parse_mode="Markdown")
    except ValueError as e:
        await update.message.reply_text(f"❌ Cashout failed: {str(e)}")
    finally:
        db.close()

register_conv_handler = ConversationHandler(
    entry_points=[
        CommandHandler("register", start_register_gmail),
        MessageHandler(filters.Regex("^➕ Register a new Gmail$"), start_register_gmail)
    ],
    states={
        REGISTER_MANUAL_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_manual_input)]
    },
    fallbacks=[CommandHandler("cancel", cancel_register)],
    per_message=False
)
