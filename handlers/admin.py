from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, ConversationHandler, MessageHandler, filters
from config import ADMIN_IDS
from models import SessionLocal, Account, AccountStatus, WithdrawalRequest, WithdrawalStatus
from services.account_service import AccountService
from services.user_service import UserService

REVIEW_SET_PRICES, REVIEW_REJECT_REASON = range(10, 12)
ADMIN_REJECT_WD_REASON = 13

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

        pending_wd_count = db.query(WithdrawalRequest).filter(WithdrawalRequest.status == WithdrawalStatus.PENDING).count()

        msg = (
            "👑 **Admin Control Panel**\n\n"
            f"⏳ **Pending Accounts:** {pending_count}\n"
            f"💳 **Pending Withdrawals:** {pending_wd_count}\n"
            f"🛒 **Available in Market:** {approved_count}\n"
            f"💰 **Total Sold:** {sold_count}\n\n"
            "Commands:\n"
            "• `/pending` - Review pending seller submissions\n"
            "• `/withdrawals` - Review pending withdrawal requests\n"
            "• `/addaccount <email>:<password>:<price_in_etb>` - Directly insert an account to marketplace\n"
            "• `/addaccount <email>:<password>:<recovery>:<price_in_etb>`"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")
    finally:
        db.close()

async def add_account_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ You are not authorized to use admin features.")
        return

    args = context.args
    if not args:
        await update.message.reply_text(
            "Usage: `/addaccount <email>:<password>:<price_in_etb>` or `/addaccount <email>:<password>:<recovery>:<price_in_etb>`\n"
            "Example: `/addaccount user@gmail.com:pass123:300`",
            parse_mode="Markdown"
        )
        return

    raw_input = " ".join(args).strip()
    parts = raw_input.split(":")
    if len(parts) not in (3, 4):
        await update.message.reply_text("❌ Invalid format. Format must be `email:password:price` or `email:password:recovery:price`", parse_mode="Markdown")
        return

    if len(parts) == 3:
        email, password, price_str = parts[0].strip(), parts[1].strip(), parts[2].strip()
        recovery = None
    else:
        email, password, recovery, price_str = parts[0].strip(), parts[1].strip(), parts[2].strip(), parts[3].strip()

    try:
        selling_price = float(price_str)
    except ValueError:
        await update.message.reply_text("❌ Price must be a valid number.")
        return

    db = SessionLocal()
    try:
        account = AccountService.register_account(
            session=db,
            creator_id=user_id,
            email=email,
            password=password,
            recovery_info=recovery,
            notes="Directly added by Admin"
        )
        approved_acc = AccountService.approve_account(
            session=db,
            account_id=account.id,
            selling_price=selling_price,
            creator_payout=0.0
        )
        await update.message.reply_text(
            f"✅ **Account Added to Marketplace!**\n\n"
            f"📧 **Email:** `{approved_acc.email}`\n"
            f"💲 **Price:** {approved_acc.selling_price:.2f} ETB\n"
            f"🆔 **ID:** `{approved_acc.id}`",
            parse_mode="Markdown"
        )
    except ValueError as e:
        await update.message.reply_text(f"❌ Error adding account: {str(e)}")
    finally:
        db.close()

async def list_pending_withdrawals_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ You are not authorized to use admin features.")
        return

    db = SessionLocal()
    try:
        pending_wds = UserService.get_pending_withdrawals(db)
        if not pending_wds:
            await update.message.reply_text("✅ No pending withdrawal requests!")
            return

        for wd in pending_wds:
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ Approve Cashout", callback_data=f"adm_wd_app_{wd.id}"),
                    InlineKeyboardButton("❌ Reject & Refund", callback_data=f"adm_wd_rej_{wd.id}")
                ]
            ])
            text = (
                f"🆔 **Withdrawal ID:** `#{wd.id}`\n"
                f"👤 **User ID:** `{wd.user_id}`\n"
                f"💰 **Amount:** **{wd.amount:.2f} ETB**\n"
                f"💳 **Method:** **{wd.method}**\n"
                f"📝 **Account Details:** `{wd.account_details}`\n"
            )
            await update.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)
    finally:
        db.close()

async def withdrawal_review_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    if not is_admin(user_id):
        await query.edit_message_text("❌ Unauthorized.")
        return ConversationHandler.END

    data = query.data
    if data.startswith("adm_wd_app_"):
        wd_id = int(data.split("_")[3])
        db = SessionLocal()
        try:
            req = UserService.approve_withdrawal(db, wd_id)
            await query.edit_message_text(
                f"✅ **Withdrawal #{req.id} APPROVED!**\n\n"
                f"👤 User: `{req.user_id}`\n"
                f"💰 Amount: {req.amount:.2f} ETB\n"
                f"💳 Method: {req.method}\n"
                f"📝 Details: `{req.account_details}`",
                parse_mode="Markdown"
            )
            try:
                await context.bot.send_message(
                    chat_id=req.user_id,
                    text=f"🎉 **Withdrawal Approved!**\n\nYour cashout request of **{req.amount:.2f} ETB** via **{req.method}** has been processed and sent to `{req.account_details}`.",
                    parse_mode="Markdown"
                )
            except Exception:
                pass
        except ValueError as e:
            await query.edit_message_text(f"❌ Error approving withdrawal: {str(e)}")
        finally:
            db.close()
        return ConversationHandler.END

    elif data.startswith("adm_wd_rej_"):
        wd_id = int(data.split("_")[3])
        context.user_data["review_wd_id"] = wd_id
        await query.edit_message_text(
            f"❌ **Rejecting Withdrawal #{wd_id}**\n\nPlease enter the reason for rejection (the amount will be refunded to user balance):",
            parse_mode="Markdown"
        )
        return ADMIN_REJECT_WD_REASON

    return ConversationHandler.END

async def process_withdrawal_rejection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reason = update.message.text.strip()
    wd_id = context.user_data.get("review_wd_id")

    db = SessionLocal()
    try:
        req = UserService.reject_withdrawal(db, wd_id, reason=reason)
        await update.message.reply_text(
            f"❌ Withdrawal #{req.id} REJECTED and **{req.amount:.2f} ETB** refunded to user balance.\nReason: {reason}",
            parse_mode="Markdown"
        )
        try:
            await context.bot.send_message(
                chat_id=req.user_id,
                text=f"❌ **Withdrawal Rejected**\n\nYour cashout request of **{req.amount:.2f} ETB** was rejected.\nReason: {reason}\n\n*The amount has been refunded back to your balance.*",
                parse_mode="Markdown"
            )
        except Exception:
            pass
    except ValueError as e:
        await update.message.reply_text(f"❌ Error rejecting withdrawal: {str(e)}")
    finally:
        db.close()
        context.user_data.clear()

    return ConversationHandler.END

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
            f"Please enter selling price and creator payout in ETB separated by space.\n"
            f"Example: `500 100` (Sell price 500 ETB, Creator payout 100 ETB):",
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
        await update.message.reply_text("❌ Invalid input format. Please enter selling price and creator payout in ETB (e.g., `500 100`):", parse_mode="Markdown")
        return REVIEW_SET_PRICES

    try:
        selling_price = float(parts[0])
        creator_payout = float(parts[1])
    except ValueError:
        await update.message.reply_text("❌ Invalid numbers. Please enter numbers like `500 100`:")
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
            f"• Selling Price: {selling_price:.2f} ETB\n"
            f"• Creator Payout: {creator_payout:.2f} ETB (Credited to creator balance)",
            parse_mode="Markdown"
        )

        try:
            await context.bot.send_message(
                chat_id=account.creator_id,
                text=f"🎉 **Account Approved!**\n\nYour submitted account `{account.email}` was approved! **{creator_payout:.2f} ETB** credited to your balance.",
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

admin_wd_review_conv_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(withdrawal_review_callback_handler, pattern="^adm_wd_")],
    states={
        ADMIN_REJECT_WD_REASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_withdrawal_rejection)]
    },
    fallbacks=[CommandHandler("cancel", cancel_review)],
    per_message=False
)

admin_review_conv_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(review_callback_handler, pattern="^adm_(approve|reject)_")],
    states={
        REVIEW_SET_PRICES: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_review_prices)],
        REVIEW_REJECT_REASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_review_rejection)]
    },
    fallbacks=[CommandHandler("cancel", cancel_review)],
    per_message=False
)
