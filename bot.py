import os
import json
import subprocess
import asyncio
import time
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ContextTypes, filters
)
from dotenv import load_dotenv
import os

load_dotenv()
TOKEN = os.getenv("TOKEN")

# ================= CONFIG =================
TOKEN = os.getenv("TOKEN")  # REQUIRED

OWNER_ID = 1446327942
OWNER_USERNAME = "@Iamidiotbro"
SUPPORT_GROUP_LINK = "https://t.me/voicechangersupport"

FREE_LIMIT = 5
FLOOD_SECONDS = 10

USER_DATA_FILE = "user_data.json"
PREMIUM_FILE = "premium_users.json"

last_action_time = {}

# ================= HELPERS =================
def load_json(path):
    if not os.path.exists(path):
        return {}
    with open(path, "r") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

# ================= PREMIUM =================
def is_premium(uid):
    premium = load_json(PREMIUM_FILE)
    if str(uid) in premium:
        return datetime.fromisoformat(premium[str(uid)]) >= datetime.now()
    return False

def add_premium(uid, days):
    premium = load_json(PREMIUM_FILE)
    premium[str(uid)] = (datetime.now() + timedelta(days=days)).isoformat()
    save_json(PREMIUM_FILE, premium)

def remove_premium(uid):
    premium = load_json(PREMIUM_FILE)
    premium.pop(str(uid), None)
    save_json(PREMIUM_FILE, premium)

def reset_free(uid):
    users = load_json(USER_DATA_FILE)
    if str(uid) in users:
        users[str(uid)]["used"] = 0
        save_json(USER_DATA_FILE, users)

# ================= FLOOD =================
def flood_ok(uid):
    now = time.time()
    last = last_action_time.get(uid, 0)
    if now - last < FLOOD_SECONDS:
        return False
    last_action_time[uid] = now
    return True

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.message.from_user.id)
    users = load_json(USER_DATA_FILE)
    users.setdefault(uid, {"used": 0, "total": 0})
    save_json(USER_DATA_FILE, users)

    await update.message.reply_text(
        "🎤 *Voice Changer Bot*\n\n"
        f"🎁 Free: {FREE_LIMIT} conversions\n"
        "💎 Premium: Unlimited\n\n"
        "💎 Premium Plans:\n"
        "₹50 → 3 days\n₹100 → 10 days\n₹200 → 20 days\n₹300 → 30 days\n\n"
        f"👤 Owner: {OWNER_USERNAME}\n"
        f"👥 Support Group: [Join Here]({SUPPORT_GROUP_LINK})\n\n"
        "⚠ Entertainment only\n"
        "🚫 No impersonation / illegal use\n\n"
        "📜 /terms | /privacy",
        parse_mode="Markdown"
    )

# ================= VOICE =================
async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id

    if not flood_ok(uid):
        await update.message.reply_text("⏳ Please wait before sending another voice.")
        return

    users = load_json(USER_DATA_FILE)
    users.setdefault(str(uid), {"used": 0, "total": 0})

    if not is_premium(uid):
        if users[str(uid)]["used"] >= FREE_LIMIT:
            buttons = [
                [InlineKeyboardButton("💎 Buy Premium", url=f"https://t.me/{OWNER_USERNAME.strip('@')}")],
                [InlineKeyboardButton("👥 Support Group", url=SUPPORT_GROUP_LINK)]
            ]
            await update.message.reply_text(
                "❌ *Free limit reached!*\nUpgrade to Premium 💎",
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode="Markdown"
            )
            return
        users[str(uid)]["used"] += 1

    users[str(uid)]["total"] += 1
    save_json(USER_DATA_FILE, users)

    voice = update.message.voice
    in_f = f"in_{voice.file_id}.ogg"
    out_f = f"out_{voice.file_id}.ogg"

    file = await context.bot.get_file(voice.file_id)
    await file.download_to_drive(in_f)

    await update.message.reply_text("🎧 Converting voice...")

    cmd = [
        "ffmpeg", "-i", in_f,
        "-af",
        "highpass=f=80,lowpass=f=7500,"
        "asetrate=44100*1.3,aresample=24000,"
        "equalizer=f=300:width=200:g=3,"
        "equalizer=f=900:width=300:g=2",
        "-ac", "1", "-c:a", "libopus",
        out_f, "-y"
    ]

    try:
        subprocess.run(cmd, check=True)
        with open(out_f, "rb") as f:
            await update.message.reply_voice(f)
    except:
        await update.message.reply_text("❌ Conversion failed.")

    for f in (in_f, out_f):
        if os.path.exists(f):
            os.remove(f)

# ================= PREMIUM EXPIRY =================
async def premium_expiry_loop(app):
    while True:
        premium = load_json(PREMIUM_FILE)
        now = datetime.now()

        for uid, expiry in list(premium.items()):
            exp = datetime.fromisoformat(expiry)

            if 0 <= (exp - now).days < 1:
                try:
                    await app.bot.send_message(
                        int(uid),
                        "⏰ Your Premium expires tomorrow! Renew soon 💎"
                    )
                except:
                    pass

            if exp < now:
                premium.pop(uid)
                save_json(PREMIUM_FILE, premium)

        await asyncio.sleep(3600)

# ================= ADMIN =================
async def addpremium_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != OWNER_ID:
        return
    try:
        uid = int(context.args[0])
        days = int(context.args[1])
        add_premium(uid, days)
        expiry = (datetime.now() + timedelta(days=days)).strftime("%d %b %Y")

        await update.message.reply_text("✅ Premium added")

        await context.bot.send_message(
            uid,
            f"🎉 Premium Activated!\n⏳ {days} days\n📅 Expires: {expiry}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👥 Support Group", url=SUPPORT_GROUP_LINK)]
            ])
        )
    except:
        await update.message.reply_text("Usage: /addpremium <user_id> <days>")

async def dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != OWNER_ID:
        return
    users = load_json(USER_DATA_FILE)
    premium = load_json(PREMIUM_FILE)

    total_users = len(users)
    premium_users = len(premium)
    free_users = total_users - premium_users
    total_uses = sum(u["total"] for u in users.values())

    await update.message.reply_text(
        f"📊 Admin Dashboard\n\n"
        f"👥 Users: {total_users}\n"
        f"💎 Premium: {premium_users}\n"
        f"🎁 Free: {free_users}\n"
        f"🎧 Total conversions: {total_uses}"
    )

# ================= TERMS & PRIVACY =================
async def terms(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📜 Terms of Service\n\n"
        "• Entertainment only\n"
        "• No illegal use\n"
        "• No refunds after premium activation"
    )

async def privacy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔐 Privacy Policy\n\n"
        "• Voice files are deleted after processing\n"
        "• Only user ID & usage count stored\n"
        "• No data sharing"
    )

# ================= MAIN =================
async def on_startup(app):
    asyncio.create_task(premium_expiry_loop(app))

def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addpremium", addpremium_cmd))
    app.add_handler(CommandHandler("dashboard", dashboard))
    app.add_handler(CommandHandler("terms", terms))
    app.add_handler(CommandHandler("privacy", privacy))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))

    app.post_init = on_startup
    app.run_polling()

if __name__ == "__main__":
    main()
