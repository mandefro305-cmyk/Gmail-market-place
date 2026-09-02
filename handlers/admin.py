from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, ConversationHandler, MessageHandler, filters
from config import ADMIN_IDS
from models import SessionLocal, Account, AccountStatus, WithdrawalRequest, WithdrawalStatus
from services.account_service import AccountService
from services.user_service import UserService

REVIEW_SET_PRICES, REVIEW_REJECT_REASON = range(10, 12)
ADMIN_REJECT_WD_REASON = 13
ADMIN_ADD_ACC_INPUT, ADMIN_ADD_ACC_PAYOUT, ADMIN_ADD_ACC_PRICE = range(14, 17)

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
        tasks_count = db.query(Account).filter(Account.status == AccountStatus.TASK_AVAILABLE).count()
        pending_count = db.query(Account).filter(Account.status == AccountStatus.PENDING_REVIEW).count()
        approved_count = db.query(Account).filter(Account.status == AccountStatus.APPROVED).count()
        sold_count = db.query(Account).filter(Account.status == AccountStatus.SOLD).count()

        pending_wd_count = db.query(WithdrawalRequest).filter(WithdrawalRequest.status == WithdrawalStatus.PENDING).count()

        msg = (
            "👑 **Admin Control Panel**\n\n"
            f"📋 **Available Creation Tasks:** {tasks_count}\n"
            f"⏳ **Pending Review Submissions:** {pending_count}\n"
            f"💳 **Pending Cashouts:** {pending_wd_count}\n"
            f"🛒 **Marketplace Inventory:** {approved_count}\n"
            f"💰 **Total Sold Accounts:** {sold_count}\n\n"
            "Select an action using the buttons below:"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Add Gmail Tasks / Emails", callback_data="adm_btn_add_acc")],
            [InlineKeyboardButton(f"⏳ Review Submissions ({pending_count})", callback_data="adm_btn_pending_acc")],
            [InlineKeyboardButton(f"💳 Review Cashouts ({pending_wd_count})", callback_data="adm_btn_pending_wd")],
            [InlineKeyboardButton("📊 Refresh Stats", callback_data="adm_btn_refresh_stats")]
        ])
        if update.callback_query:
            await update.callback_query.edit_message_text(msg, parse_mode="Markdown", reply_markup=keyboard)
        else:
            await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=keyboard)
    finally:
        db.close()

async def admin_refresh_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Refreshed stats!")
    await admin_panel_command(update, context)

async def start_add_account_conv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        msg = "❌ You are not authorized to use admin features."
        if update.callback_query:
            await update.callback_query.edit_message_text(msg)
        else:
            await update.message.reply_text(msg)
        return ConversationHandler.END

    msg = (
        "➕ **Add New Email / Creation Tasks**\n\n"
        "Please paste your email task templates below.\n"
        "You can send a single account or multiple accounts (one per line) in either format:\n"
        "• `email:password`\n"
        "• `email:password:recovery_email`\n\n"
        "*(Type /cancel to abort)*"
    )
    if update.callback_query:
        await update.callback_query.edit_message_text(msg, parse_mode="Markdown")
    else:
        await update.message.reply_text(msg, parse_mode="Markdown")

    return ADMIN_ADD_ACC_INPUT

async def process_add_account_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    lines = [line.strip() for line in text.split("\n") if line.strip()]

    parsed_accounts = []
    for line in lines:
        parts = line.split(":")
        if len(parts) >= 2:
            email = parts[0].strip()
            password = parts[1].strip()
            recovery = parts[2].strip() if len(parts) > 2 else None
            parsed_accounts.append((email, password, recovery))

    if not parsed_accounts:
        await update.message.reply_text(
            "❌ No valid email task lines recognized. Format must be `email:password` or `email:password:recovery`.\nPlease try again:",
            parse_mode="Markdown"
        )
        return ADMIN_ADD_ACC_INPUT

    context.user_data["add_acc_list"] = parsed_accounts
    await update.message.reply_text(
        f"✅ Received **{len(parsed_accounts)}** email task template(s).\n\n"
        f"Please enter the **Creator Payout in ETB** that regular users will earn upon task verification (e.g. `80`):",
        parse_mode="Markdown"
    )
    return ADMIN_ADD_ACC_PAYOUT

async def process_add_account_payout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text.replace('.', '', 1).isdigit():
        await update.message.reply_text("❌ Invalid payout amount. Please enter a valid number for creator payout in ETB (e.g., `80`):")
        return ADMIN_ADD_ACC_PAYOUT

    payout = float(text)
    context.user_data["add_acc_payout"] = payout

    await update.message.reply_text(
        f"💰 Creator Payout set to **{payout:.2f} ETB**.\n\n"
        f"Please enter the **Marketplace Selling Price in ETB** when sold to buyers (e.g. `250`):",
        parse_mode="Markdown"
    )
    return ADMIN_ADD_ACC_PRICE

async def cancel_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("🚫 Review cancelled.")
    return ConversationHandler.END

async def process_add_account_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text.replace('.', '', 1).isdigit():
        await update.message.reply_text("❌ Invalid selling price. Please enter a valid number for selling price in ETB (e.g., `250`):")
        return ADMIN_ADD_ACC_PRICE

    selling_price = float(text)
    accounts = context.user_data.get("add_acc_list", [])
    creator_payout = context.user_data.get("add_acc_payout", 0.0)

    db = SessionLocal()
    added_count = 0
    try:
        for email, password, recovery in accounts:
            AccountService.create_email_task(
                session=db,
                email=email,
                password=password,
                recovery_info=recovery,
                creator_payout=creator_payout,
                selling_price=selling_price,
                notes="Admin created task"
            )
            added_count += 1

        await update.message.reply_text(
            f"🎉 **Successfully created {added_count} email creation task(s)!**\n\n"
            f"💵 **User Payout:** {creator_payout:.2f} ETB\n"
            f"💲 **Store Price:** {selling_price:.2f} ETB\n\n"
            f"Normal users can now claim and create these emails in their bot menu!",
            parse_mode="Markdown"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Error adding tasks: {str(e)}")
    finally:
        db.close()
        context.user_data.clear()

    return ConversationHandler.END

admin_add_acc_conv_handler = ConversationHandler(
    entry_points=[
        CommandHandler("addaccount", start_add_account_conv),
        CallbackQueryHandler(start_add_account_conv, pattern="^adm_btn_add_acc$")
    ],
    states={
        ADMIN_ADD_ACC_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_add_account_input)],
        ADMIN_ADD_ACC_PAYOUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_add_account_payout)],
        ADMIN_ADD_ACC_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_add_account_price)]
    },
    fallbacks=[CommandHandler("cancel", cancel_review)],
    per_message=False
)

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
