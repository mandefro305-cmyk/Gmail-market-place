from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, ConversationHandler, MessageHandler, filters
from config import ADMIN_IDS
from models import SessionLocal, Account, AccountStatus
from services.account_service import AccountService

REVIEW_SET_PRICES, REVIEW_REJECT_REASON = range(10, 12)

def is_admin(user_id: int) -> bool:
    if not ADMIN_IDS:
        return False
    return user_id in ADMIN_IDS

async def admin_panel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ You are not authorized to use admin features.")
        return

    db = SessionLocal()
    try:
        pending_count = db.query(Account).filter(Account.status == AccountStatus.PENDING_REVIEW).count()
        approved_count = db.query(Account).filter(Account.status == AccountStatus.APPROVED).count()
        sold_count = db.query(Account).filter(Account.status == AccountStatus.SOLD).count()

        msg = (
            "👑 **Admin Control Panel**\n\n"
            f"⏳ **Pending Accounts:** {pending_count}\n"
            f"🛒 **Available in Market:** {approved_count}\n"
            f"💰 **Total Sold:** {sold_count}\n\n"
            "Use /pending to review pending Gmail accounts."
        )
        await update.message.reply_text(msg, parse_mode="Markdown")
    finally:
        db.close()

async def list_pending_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ You are not authorized to use admin features.")
        return

    db = SessionLocal()
    try:
        pending = AccountService.get_pending_accounts(db)
        if not pending:
            await update.message.reply_text("✅ No pending Gmail accounts to review!")
            return

        for acc in pending:
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ Approve & Price", callback_data=f"adm_approve_{acc.id}"),
                    InlineKeyboardButton("❌ Reject", callback_data=f"adm_reject_{acc.id}")
                ]
            ])
            text = (
                f"🆔 **Account ID:** `{acc.id}`\n"
                f"📧 **Email:** `{acc.email}`\n"
                f"🔑 **Password:** `{acc.password}`\n"
                f"📩 **Recovery:** `{acc.recovery_info or 'N/A'}`\n"
                f"📝 **Notes:** `{acc.notes or 'None'}`\n"
                f"👤 **Creator ID:** `{acc.creator_id}`\n"
            )
            await update.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)
    finally:
        db.close()

async def review_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    if not is_admin(user_id):
        await query.edit_message_text("❌ Unauthorized.")
        return ConversationHandler.END

    data = query.data
    if data.startswith("adm_approve_"):
        account_id = int(data.split("_")[2])
        context.user_data["review_acc_id"] = account_id
        await query.edit_message_text(
            f"✅ **Approving Account #{account_id}**\n\n"
            f"Please enter selling price and creator payout separated by space.\n"
            f"Example: `10.0 0.20` (Sell price $10.00, Creator payout $0.20):",
            parse_mode="Markdown"
        )
        return REVIEW_SET_PRICES

    elif data.startswith("adm_reject_"):
        account_id = int(data.split("_")[2])
        context.user_data["review_acc_id"] = account_id
        await query.edit_message_text(
            f"❌ **Rejecting Account #{account_id}**\n\n"
            f"Please enter the reason for rejection:",
            parse_mode="Markdown"
        )
        return REVIEW_REJECT_REASON

    return ConversationHandler.END

async def process_review_prices(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    account_id = context.user_data.get("review_acc_id")

    parts = text.split()
    if len(parts) != 2:
        await update.message.reply_text("❌ Invalid input format. Please enter selling price and creator payout (e.g., `10.0 0.20`):", parse_mode="Markdown")
        return REVIEW_SET_PRICES

    try:
        selling_price = float(parts[0])
        creator_payout = float(parts[1])
    except ValueError:
        await update.message.reply_text("❌ Invalid numbers. Please enter numbers like `10.0 0.20`:")
        return REVIEW_SET_PRICES

    db = SessionLocal()
    try:
        account = AccountService.approve_account(
            session=db,
            account_id=account_id,
            selling_price=selling_price,
            creator_payout=creator_payout
        )
        await update.message.reply_text(
            f"🎉 Account #{account.id} (`{account.email}`) APPROVED!\n"
            f"• Selling Price: ${selling_price:.2f}\n"
            f"• Creator Payout: ${creator_payout:.2f} (Credited to creator balance)",
            parse_mode="Markdown"
        )

        try:
            await context.bot.send_message(
                chat_id=account.creator_id,
                text=f"🎉 **Account Approved!**\n\nYour submitted account `{account.email}` was approved! **${creator_payout:.2f}** credited to your balance.",
                parse_mode="Markdown"
            )
        except Exception:
            pass

    except ValueError as e:
        await update.message.reply_text(f"❌ Approval error: {str(e)}")
    finally:
        db.close()
        context.user_data.clear()

    return ConversationHandler.END

async def process_review_rejection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reason = update.message.text.strip()
    account_id = context.user_data.get("review_acc_id")

    db = SessionLocal()
    try:
        account = AccountService.reject_account(session=db, account_id=account_id, reason=reason)
        await update.message.reply_text(
            f"❌ Account #{account.id} (`{account.email}`) REJECTED with reason: {reason}",
            parse_mode="Markdown"
        )

        try:
            await context.bot.send_message(
                chat_id=account.creator_id,
                text=f"❌ **Account Registration Rejected**\n\nYour account `{account.email}` was rejected.\nReason: {reason}",
                parse_mode="Markdown"
            )
        except Exception:
            pass

    except ValueError as e:
        await update.message.reply_text(f"❌ Rejection error: {str(e)}")
    finally:
        db.close()
        context.user_data.clear()

    return ConversationHandler.END

async def cancel_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("🚫 Review cancelled.")
    return ConversationHandler.END

admin_review_conv_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(review_callback_handler, pattern="^adm_")],
    states={
        REVIEW_SET_PRICES: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_review_prices)],
        REVIEW_REJECT_REASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_review_rejection)]
    },
    fallbacks=[CommandHandler("cancel", cancel_review)],
    per_message=False
)
