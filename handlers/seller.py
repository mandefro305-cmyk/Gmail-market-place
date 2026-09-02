import random
import string
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from models import SessionLocal, AccountStatus, TransactionType
from services.user_service import UserService
from services.account_service import AccountService

REGISTER_MANUAL_INPUT = 1

FIRST_NAMES = ["Alex", "Jordan", "Taylor", "Morgan", "Sam", "Chris", "Pat", "Riley", "Casey", "Dakota"]
LAST_NAMES = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez"]

def generate_random_credentials():
    first_name = random.choice(FIRST_NAMES)
    last_name = random.choice(LAST_NAMES)
    rand_num = random.randint(1000, 9999)
    email = f"{first_name.lower()}{last_name.lower()}{rand_num}@gmail.com"
    password = "".join(random.choices(string.ascii_letters + string.digits, k=10)) + "!"
    birth_year = random.randint(1990, 2002)
    payout = round(random.uniform(0.15, 0.23), 2)
    return {
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "password": password,
        "birth_year": birth_year,
        "payout": payout
    }

async def start_register_gmail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    details = generate_random_credentials()
    context.user_data["gen_task"] = details

    msg = (
        "➕ **Register a New Gmail Account**\n\n"
        "Please create a Gmail account using the following details:\n\n"
        f"👤 **First name:** `{details['first_name']}`\n"
        f"👤 **Last name:** `{details['last_name']}`\n"
        f"📧 **Email:** `{details['email']}`\n"
        f"🔑 **Password:** `{details['password']}`\n"
        f"📅 **Year of birth:** `{details['birth_year']}`\n\n"
        f"💰 **Payout upon approval:** **${details['payout']:.2f}**\n\n"
        "After creating the account, click **Confirm Created Account** below or click **Manual Custom Entry** to enter custom credentials."
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Confirm Created Account", callback_data="sub_confirm_gen")],
        [InlineKeyboardButton("🔄 Generate New Details", callback_data="sub_regen_task")],
        [InlineKeyboardButton("✏️ Manual Custom Entry", callback_data="sub_manual_entry")]
    ])

    if update.callback_query:
        await update.callback_query.edit_message_text(msg, parse_mode="Markdown", reply_markup=keyboard)
    elif update.message:
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=keyboard)

async def task_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "sub_regen_task":
        await start_register_gmail(update, context)
        return ConversationHandler.END

    elif data == "sub_confirm_gen":
        task = context.user_data.get("gen_task")
        if not task:
            await query.edit_message_text("❌ Task expired. Please click **➕ Register a new Gmail** again.", parse_mode="Markdown")
            return ConversationHandler.END

        user = query.from_user
        db = SessionLocal()
        try:
            UserService.get_or_create_user(db, user.id, user.username, user.first_name)
            account = AccountService.register_account(
                session=db,
                creator_id=user.id,
                email=task["email"],
                password=task["password"],
                recovery_info=None,
                notes=f"Generated Task Payout target: ${task['payout']:.2f}"
            )
            await query.edit_message_text(
                f"✅ **Account Sent for Review!**\n\n"
                f"📧 **Email:** `{account.email}`\n"
                f"🆔 **ID:** `{account.id}`\n"
                f"💰 **Expected Payout:** ${task['payout']:.2f}\n\n"
                f"Status: ⏳ *Pending Verification*",
                parse_mode="Markdown"
            )
        except ValueError as e:
            await query.edit_message_text(f"❌ Registration failed: {str(e)}")
        finally:
            db.close()
            context.user_data.clear()

        return ConversationHandler.END

    elif data == "sub_manual_entry":
        await query.edit_message_text(
            "✏️ **Manual Gmail Entry**\n\n"
            "Please send the account details in format:\n"
            "`email:password:recovery_email` or `email:password`\n\n"
            "*(Type /cancel to abort)*",
            parse_mode="Markdown"
        )
        return REGISTER_MANUAL_INPUT

    return ConversationHandler.END

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
                status_emoji = {
                    AccountStatus.PENDING_REVIEW: "⏳ Pending Review",
                    AccountStatus.APPROVED: f"✅ Approved (${acc.creator_payout:.2f})",
                    AccountStatus.REJECTED: f"❌ Rejected ({acc.rejection_reason or 'No reason'})",
                    AccountStatus.SOLD: f"💰 Sold (${acc.creator_payout:.2f})"
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
        msg += f"Available Balance: **${db_user.balance:.2f}**\n\n"
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
        await update.message.reply_text("Usage: `/withdraw <amount>`\nExample: `/withdraw 5.00`", parse_mode="Markdown")
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
        await update.message.reply_text(f"✅ Cashout request of **${amount:.2f}** processed successfully!", parse_mode="Markdown")
    except ValueError as e:
        await update.message.reply_text(f"❌ Cashout failed: {str(e)}")
    finally:
        db.close()

register_conv_handler = ConversationHandler(
    entry_points=[
        CommandHandler("register", start_register_gmail),
        MessageHandler(filters.Regex("^➕ Register a new Gmail$"), start_register_gmail),
        CallbackQueryHandler(task_callback_handler, pattern="^sub_")
    ],
    states={
        REGISTER_MANUAL_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_manual_input)]
    },
    fallbacks=[CommandHandler("cancel", cancel_register)],
    per_message=False
)
