import telebot
from telebot import types
from config import ADMIN_IDS
import time


def register_admin_handlers(bot, db):

    # ---------- ADMIN PANEL BUTTON ----------
    @bot.message_handler(commands=["admin"])
    def admin_panel(message):
        if message.from_user.id not in ADMIN_IDS:
            return bot.send_message(message.chat.id, "❌ You are not an admin.")

        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        kb.row(types.KeyboardButton("Manage Users"))
        kb.row(types.KeyboardButton("Broadcast Message"))
        kb.row(types.KeyboardButton("Back"))

        bot.send_message(
            message.chat.id,
            "🔐 <b>Admin Panel</b>\nChoose an option:",
            reply_markup=kb,
            parse_mode="HTML"
        )

    # ---------- ADMIN: BROADCAST ----------
    @bot.message_handler(func=lambda m: m.text == "Broadcast Message")
    def ask_broadcast_text(message):
        if message.from_user.id not in ADMIN_IDS:
            return

        msg = bot.send_message(message.chat.id, "📝 Send the message you want to broadcast to all users:")
        bot.register_next_step_handler(msg, do_broadcast, db)

    def do_broadcast(message, db):
        if message.from_user.id not in ADMIN_IDS:
            return

        text = message.text.strip()
        users = db.list_all_users()
        sent = 0
        failed = 0

        bot.send_message(message.chat.id, f"⏳ Broadcasting to {len(users)} users...")

        for u in users:
            uid = int(u["id"])
            try:
                bot.send_message(uid, f"📢 <b>Broadcast Message</b>:\n\n{text}", parse_mode="HTML")
                sent += 1
                time.sleep(0.05)  # prevent flood-limit
            except:
                failed += 1

        bot.send_message(
            message.chat.id,
            f"✅ Broadcast Completed!\n\n"
            f"📨 Sent: {sent}\n"
            f"❌ Failed: {failed}"
        )

    # ---------- ADMIN: BACK BUTTON ----------
    @bot.message_handler(func=lambda m: m.text == "Back")
    def back_to_normal(message):
        bot.send_message(message.chat.id, "Returned to user mode.", reply_markup=types.ReplyKeyboardRemove())

    # ---------- MANAGE USERS (Placeholder for now) ----------
    @bot.message_handler(func=lambda m: m.text == "Manage Users")
    def manage_users(message):
        if message.from_user.id not in ADMIN_IDS:
            return

        users = db.list_all_users()
        count = len(users)

        bot.send_message(message.chat.id, f"👥 Total users: {count}")
