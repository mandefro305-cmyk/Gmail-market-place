from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from models import SessionLocal, Account, AccountStatus, TransactionType
from services.user_service import UserService
from services.account_service import AccountService

REGISTER_MANUAL_INPUT = 1
WITHDRAW_SELECT_METHOD, WITHDRAW_ENTER_AMOUNT, WITHDRAW_ENTER_DETAILS = range(20, 23)

async def start_register_gmail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = SessionLocal()
    try:
        available_tasks = AccountService.get_available_tasks(db)
        if not available_tasks:
            msg = "❌ **No task available!**\n\nThere are currently no tasks available. The admin has not added any emails yet. Please check back later!"
            if update.callback_query:
                await update.callback_query.edit_message_text(msg, parse_mode="Markdown")
            elif update.message:
                await update.message.reply_text(msg, parse_mode="Markdown")
            return ConversationHandler.END

        task = available_tasks[0]
        context.user_data["active_task_id"] = task.id

        fn_display = f"`{task.first_name}`" if task.first_name else ""
        ln_display = f"`{task.last_name}`" if task.last_name else "✖️"
        dob_display = f"`{task.dob_year}`" if task.dob_year else ""

        msg = (
            f"➕ **Gmail Creation Task Available**\n\n"
            f"Please register a new Gmail account on Google using these exact details:\n\n"
            f"First name: {fn_display}\n"
            f"Last name: {ln_display}\n"
            f"Email: `{task.email}`\n"
            f"Password: `{task.password}`\n"
            f"Recovery email: `{task.recovery_info or 'None'}`\n"
            f"Year of birth: {dob_display}\n\n"
            f"💵 **Payout Upon Approval:** **{task.creator_payout:.2f} ETB**\n\n"
            f"Once you have created the account, click the button below to confirm submission for review!\n"
            f"*(Or type /cancel to abort)*"
        )

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Confirm Account Created & Submit", callback_data=f"usr_submit_task_{task.id}")],
            [InlineKeyboardButton("🚫 Cancel Task", callback_data="usr_cancel_task")]
        ])

        if update.callback_query:
            await update.callback_query.edit_message_text(msg, parse_mode="Markdown", reply_markup=keyboard)
        elif update.message:
            await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=keyboard)

        return REGISTER_MANUAL_INPUT
    finally:
        db.close()

async def process_task_submission_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    if data == "usr_cancel_task":
        await query.edit_message_text("🚫 Task creation cancelled.")
        context.user_data.clear()
        return ConversationHandler.END

    if data.startswith("usr_submit_task_"):
        task_id = int(data.split("_")[3])
        user = query.from_user

        db = SessionLocal()
        try:
            account = AccountService.submit_task_completion(session=db, account_id=task_id, creator_id=user.id)
            await query.edit_message_text(
                f"✅ **Account Submitted for Review!**\n\n"
                f"📧 **Email:** `{account.email}`\n"
                f"💵 **Expected Payout:** {account.creator_payout:.2f} ETB\n"
                f"🆔 **Task ID:** `#{account.id}`\n\n"
                f"Status: ⏳ *Pending Admin Verification*",
                parse_mode="Markdown"
            )
        except ValueError as e:
            await query.edit_message_text(f"❌ Submission failed: {str(e)}")
        finally:
            db.close()
            context.user_data.clear()

    return ConversationHandler.END

async def process_manual_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    task_id = context.user_data.get("active_task_id")

    if not task_id:
        await update.message.reply_text("❌ No active task selected. Please select '➕ Register a new Gmail' from the menu.")
        return ConversationHandler.END

    db = SessionLocal()
    try:
        account = AccountService.submit_task_completion(session=db, account_id=task_id, creator_id=user.id)
        await update.message.reply_text(
            f"✅ **Account Submitted for Review!**\n\n"
            f"📧 **Email:** `{account.email}`\n"
            f"💵 **Expected Payout:** {account.creator_payout:.2f} ETB\n"
            f"🆔 **Task ID:** `#{account.id}`\n\n"
            f"Status: ⏳ *Pending Admin Verification*",
            parse_mode="Markdown"
        )
    except ValueError as e:
        await update.message.reply_text(f"❌ Submission failed: {str(e)}")
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
        msg += "• `/withdraw` - Cashout funds\n"
        msg += "• `/payouts` - View payout history\n"
        msg += "• `/deposit <amount>` - Deposit funds"

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("💳 Withdraw Cash", callback_data="wallet_withdraw")],
            [InlineKeyboardButton("💳 Payout History", callback_data="wallet_payouts")],
            [InlineKeyboardButton("➕ Deposit Balance", callback_data="wallet_deposit")]
        ])

        if update.callback_query:
            await update.callback_query.edit_message_text(msg, parse_mode="Markdown", reply_markup=keyboard)
        else:
            await update.effective_message.reply_text(msg, parse_mode="Markdown", reply_markup=keyboard)
    finally:
        db.close()

async def payout_history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()

    user = update.effective_user
    db = SessionLocal()
    try:
        withdrawals = UserService.get_user_withdrawals(db, user.id)
        if not withdrawals:
            msg = "📜 **Payout History**\n\nYou have no payout/withdrawal history yet."
            if update.callback_query:
                await update.callback_query.edit_message_text(msg, parse_mode="Markdown")
            else:
                await update.effective_message.reply_text(msg, parse_mode="Markdown")
            return

        msg = "📜 **Payout History**\n\n"
        for wd in withdrawals:
            status_str = {
                "PENDING": "⏳ Pending",
                "APPROVED": "✅ Approved",
                "REJECTED": f"❌ Rejected ({wd.rejection_reason or 'No reason'})"
            }.get(wd.status.value if hasattr(wd.status, 'value') else wd.status, wd.status)

            msg += (
                f"🆔 `#{wd.id}` | **{wd.amount:.2f} ETB** via **{wd.method}**\n"
                f"• Status: {status_str}\n"
                f"• Details: `{wd.account_details}`\n\n"
            )

        if update.callback_query:
            await update.callback_query.edit_message_text(msg, parse_mode="Markdown")
        else:
            await update.effective_message.reply_text(msg, parse_mode="Markdown")
    finally:
        db.close()

async def start_withdrawal_conv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db = SessionLocal()
    try:
        db_user = UserService.get_or_create_user(db, user.id, user.username, user.first_name)
        if db_user.balance <= 0:
            msg = "❌ Your balance is 0.00 ETB. You cannot perform a withdrawal."
            if update.callback_query:
                await update.callback_query.edit_message_text(msg)
            else:
                await update.message.reply_text(msg)
            return ConversationHandler.END

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📱 Telebirr", callback_data="wd_method_Telebirr")],
            [InlineKeyboardButton("🏦 CBE (Commercial Bank of Ethiopia)", callback_data="wd_method_CBE")]
        ])
        msg = f"💳 **Cashout Request**\n\nAvailable Balance: **{db_user.balance:.2f} ETB**\n\nPlease select your preferred withdrawal method:"
        if update.callback_query:
            await update.callback_query.edit_message_text(msg, parse_mode="Markdown", reply_markup=keyboard)
        else:
            await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=keyboard)
        return WITHDRAW_SELECT_METHOD
    finally:
        db.close()

async def process_withdrawal_method(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if not data.startswith("wd_method_"):
        return ConversationHandler.END

    method = data.split("_")[2]
    context.user_data["withdraw_method"] = method

    await query.edit_message_text(
        f"Selected Method: **{method}**\n\nPlease enter the amount in ETB you wish to withdraw:\n*(Type /cancel to abort)*",
        parse_mode="Markdown"
    )
    return WITHDRAW_ENTER_AMOUNT

async def process_withdrawal_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text.replace('.', '', 1).isdigit():
        await update.message.reply_text("❌ Please enter a valid number for the withdrawal amount:")
        return WITHDRAW_ENTER_AMOUNT

    amount = float(text)
    if amount <= 0:
        await update.message.reply_text("❌ Amount must be greater than zero. Please enter a valid amount:")
        return WITHDRAW_ENTER_AMOUNT

    user = update.effective_user
    db = SessionLocal()
    try:
        db_user = UserService.get_or_create_user(db, user.id, user.username, user.first_name)
        if db_user.balance < amount:
            await update.message.reply_text(
                f"❌ Insufficient balance! Your current balance is **{db_user.balance:.2f} ETB**.\nPlease enter a valid amount:",
                parse_mode="Markdown"
            )
            return WITHDRAW_ENTER_AMOUNT
    finally:
        db.close()

    context.user_data["withdraw_amount"] = amount
    method = context.user_data.get("withdraw_method")

    if method == "Telebirr":
        prompt = "📱 Please enter your **Telebirr Phone Number** (e.g. `0912345678`):"
    else:
        prompt = "🏦 Please enter your **CBE Account Number and Account Holder Name** (e.g. `1000123456789 - Abebe Bikila`):"

    await update.message.reply_text(prompt, parse_mode="Markdown")
    return WITHDRAW_ENTER_DETAILS

async def process_withdrawal_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    details = update.message.text.strip()
    method = context.user_data.get("withdraw_method")
    amount = context.user_data.get("withdraw_amount")
    user = update.effective_user

    db = SessionLocal()
    try:
        req = UserService.create_withdrawal_request(
            session=db,
            user_id=user.id,
            amount=amount,
            method=method,
            account_details=details
        )
        await update.message.reply_text(
            f"✅ **Withdrawal Request Submitted!**\n\n"
            f"🆔 **Request ID:** `#{req.id}`\n"
            f"💰 **Amount:** {amount:.2f} ETB\n"
            f"💳 **Method:** {method}\n"
            f"📝 **Account Details:** `{details}`\n\n"
            f"Status: ⏳ *Pending Admin Approval*",
            parse_mode="Markdown"
        )
    except ValueError as e:
        await update.message.reply_text(f"❌ Withdrawal error: {str(e)}")
    finally:
        db.close()
        context.user_data.clear()

    return ConversationHandler.END

async def cancel_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("🚫 Withdrawal cancelled.")
    return ConversationHandler.END

withdraw_conv_handler = ConversationHandler(
    entry_points=[
        CommandHandler("withdraw", start_withdrawal_conv),
        CallbackQueryHandler(start_withdrawal_conv, pattern="^wallet_withdraw$")
    ],
    states={
        WITHDRAW_SELECT_METHOD: [CallbackQueryHandler(process_withdrawal_method, pattern="^wd_method_")],
        WITHDRAW_ENTER_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_withdrawal_amount)],
        WITHDRAW_ENTER_DETAILS: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_withdrawal_details)]
    },
    fallbacks=[CommandHandler("cancel", cancel_withdrawal)],
    per_message=False
)

register_conv_handler = ConversationHandler(
    entry_points=[
        CommandHandler("register", start_register_gmail),
        MessageHandler(filters.Regex("^➕ Register a new Gmail$"), start_register_gmail)
    ],
    states={
        REGISTER_MANUAL_INPUT: [
            CallbackQueryHandler(process_task_submission_callback, pattern="^usr_(submit|cancel)_task"),
            MessageHandler(filters.TEXT & ~filters.COMMAND, process_manual_input)
        ]
    },
    fallbacks=[CommandHandler("cancel", cancel_register)],
    per_message=False
)
