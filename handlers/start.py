from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes
from models import SessionLocal, User
from services.user_service import UserService

MAIN_MENU_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("➕ Register a new Gmail")],
        [KeyboardButton("📋 My accounts"), KeyboardButton("💰 Balance")],
        [KeyboardButton("👥 My referrals"), KeyboardButton("⚙️ Settings")],
        [KeyboardButton("💬 Help")]
    ],
    resize_keyboard=True
)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db = SessionLocal()

    referred_by = None
    if context.args and context.args[0].isdigit():
        referred_by = int(context.args[0])

    try:
        UserService.get_or_create_user(
            session=db,
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            referred_by_id=referred_by
        )
    finally:
        db.close()

    welcome_text = (
        f"👋 Welcome to **Gmail Farmer Bot**, {user.first_name}!\n\n"
        "🌾 **Earn money by registering and providing Gmail accounts!**\n\n"
        "• Click **➕ Register a new Gmail** to get account creation details and tasks.\n"
        "• Check **📋 My accounts** to see your registered accounts & earnings.\n"
        "• Check **💰 Balance** to withdraw your funds.\n"
        "• Invite friends with **👥 My referrals** to earn bonuses!"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown", reply_markup=MAIN_MENU_KEYBOARD)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "💬 **Gmail Farmer Help & FAQ**\n\n"
        "**How does it work?**\n"
        "1. Click **➕ Register a new Gmail** to generate account registration parameters.\n"
        "2. Create the Gmail account using those credentials.\n"
        "3. Confirm completion to send it for verification.\n"
        "4. Once checked, earnings are added to your balance!\n\n"
        "**Support & Contact:**\n"
        "For any issues, contact `@GmailFarmerSupport`."
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def referrals_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    bot_username = (await context.bot.get_me()).username
    ref_link = f"https://t.me/{bot_username}?start={user.id}"

    db = SessionLocal()
    try:
        ref_count = db.query(User).filter(User.referred_by_id == user.id).count()
        text = (
            f"👥 **Referral Program**\n\n"
            f"Invite friends and earn **5%** commission on all earnings from accounts they register!\n\n"
            f"🔗 **Your Referral Link:**\n`{ref_link}`\n\n"
            f"📊 **Total Referrals Invited:** {ref_count}"
        )
        await update.message.reply_text(text, parse_mode="Markdown")
    finally:
        db.close()

async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "⚙️ **Settings**\n\n"
        "Language: 🇬🇧 English\n"
        "Notifications: Enabled ✅"
    )
    await update.message.reply_text(text, parse_mode="Markdown")
