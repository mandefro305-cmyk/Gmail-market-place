from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from models import SessionLocal, TransactionType
from services.user_service import UserService
from services.account_service import AccountService

async def marketplace_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = SessionLocal()
    try:
        available = AccountService.get_available_marketplace_accounts(db)
        if not available:
            await update.message.reply_text("🛒 **Gmail Marketplace Store**\n\nNo Gmail accounts in stock right now. Please check back later!", parse_mode="Markdown")
            return

        await update.message.reply_text(f"🛒 **Gmail Marketplace Store** ({len(available)} available):\n", parse_mode="Markdown")

        for acc in available:
            domain = acc.email.split("@")[1] if "@" in acc.email else "gmail.com"
            prefix = acc.email.split("@")[0]
            masked_prefix = prefix[:2] + "***" if len(prefix) > 2 else prefix + "***"
            masked_email = f"{masked_prefix}@{domain}"

            text = (
                f"📧 **Stock:** `{masked_email}`\n"
                f"💲 **Price:** **{acc.selling_price:.2f} ETB**\n"
            )
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"🛒 Buy Account for {acc.selling_price:.2f} ETB", callback_data=f"buy_acc_{acc.id}")]
            ])
            await update.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)
    finally:
        db.close()

async def deposit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args

    if not args or not args[0].replace('.', '', 1).isdigit():
        await update.message.reply_text("Usage: `/deposit <amount>`\nExample: `/deposit 500`", parse_mode="Markdown")
        return

    amount = float(args[0])
    db = SessionLocal()
    try:
        UserService.get_or_create_user(db, user.id, user.username, user.first_name)
        updated_user = UserService.add_balance(
            session=db,
            user_id=user.id,
            amount=amount,
            tx_type=TransactionType.DEPOSIT,
            description="Balance deposit"
        )
        await update.message.reply_text(
            f"💳 **Deposit Completed!**\n\nAdded **{amount:.2f} ETB** to your balance.\nCurrent Balance: **{updated_user.balance:.2f} ETB**",
            parse_mode="Markdown"
        )
    except ValueError as e:
        await update.message.reply_text(f"❌ Deposit error: {str(e)}")
    finally:
        db.close()

async def buy_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    data = query.data

    if not data.startswith("buy_acc_"):
        return

    account_id = int(data.split("_")[2])

    db = SessionLocal()
    try:
        UserService.get_or_create_user(db, user.id, user.username, user.first_name)
        purchased = AccountService.purchase_account(
            session=db,
            buyer_id=user.id,
            account_id=account_id
        )

        credentials_text = (
            f"🎉 **Purchase Successful!**\n\n"
            f"Here are your Gmail credentials:\n\n"
            f"📧 **Email:** `{purchased.email}`\n"
            f"🔑 **Password:** `{purchased.password}`\n"
        )
        if purchased.recovery_info:
            credentials_text += f"📩 **Recovery Info:** `{purchased.recovery_info}`\n"
        if purchased.notes:
            credentials_text += f"📝 **Notes:** `{purchased.notes}`\n"

        await query.edit_message_text(credentials_text, parse_mode="Markdown")

    except ValueError as e:
        await query.edit_message_text(f"❌ Purchase failed: {str(e)}\n\nUse `/deposit <amount>` to top up your balance.", parse_mode="Markdown")
    finally:
        db.close()
