import telebot
from telebot import types
from config import ADMIN_IDS
import time


def register_admin_handlers(bot, db):

    # ---------------- ADMIN PANEL BUTTON ----------------
    @bot.message_handler(commands=["admin"])
    def admin_panel(message):
        if message.from_user.id not in ADMIN_IDS:
            return bot.send_message(message.chat.id, "❌ You are not an admin.")

        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        kb.row("📊 User List")
        kb.row("📢 Broadcast")
        kb.row("⬅ Back")

        bot.send_message(
            message.chat.id,
            "<b>🔐 Admin Panel</b>\nChoose an option:",
            reply_markup=kb,
            parse_mode="HTML"
        )

    # ---------------- USER LIST ----------------
    @bot.message_handler(func=lambda m: m.text == "📊 User List")
    def show_users(message):
        if message.from_user.id not in ADMIN_IDS:
            return

        users = db.list_all_users()
        text = f"👥 <b>Total Users:</b> {len(users)}\n\n"

        for u in users[:50]:   # first 50 only
            username = u["username"] or "No username"
            text += f"🆔 {u['id']} — @{username}\n"

        bot.send_message(message.chat.id, text, parse_mode="HTML")

    # ---------------- ASK BROADCAST ----------------
    @bot.message_handler(func=lambda m: m.text == "📢 Broadcast")
    def ask_broadcast(message):
        if message.from_user.id not in ADMIN_IDS:
            return

        msg = bot.send_message(message.chat.id, "📝 Send the message to broadcast:")
        bot.register_next_step_handler(msg, do_broadcast, db)

    def do_broadcast(message, db):
        if message.from_user.id not in ADMIN_IDS:
            return

        text = message.text.strip()
        users = db.list_all_users()

        bot.send_message(message.chat.id, f"⏳ Sending to {len(users)} users...")

        sent = 0
        failed = 0

        for u in users:
            try:
                bot.send_message(u["id"], f"📢 <b>Broadcast</b>:\n{text}", parse_mode="HTML")
                sent += 1
                time.sleep(0.05)
            except:
                failed += 1

        bot.send_message(
            message.chat.id,
            f"✅ <b>Done!</b>\n📨 Sent: {sent}\n❌ Failed: {failed}",
            parse_mode="HTML"
        )

    # ---------------- BACK BUTTON ----------------
    @bot.message_handler(func=lambda m: m.text == "⬅ Back")
    def back_btn(message):
        bot.send_message(message.chat.id, "Back to user panel.", reply_markup=types.ReplyKeyboardRemove())
