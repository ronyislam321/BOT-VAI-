from typing import Dict
import telebot
from telebot import types
from config import DB_PATH


def build_admin_menu():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("Manage Credits", callback_data="admin:credits"))
    kb.add(types.InlineKeyboardButton("Manage Validity", callback_data="admin:validity"))
    kb.add(types.InlineKeyboardButton("List Users", callback_data="admin:list_users"))
    kb.add(types.InlineKeyboardButton("List Premium Users", callback_data="admin:list_premium"))
    kb.add(types.InlineKeyboardButton("Broadcast", callback_data="admin:broadcast"))
    kb.add(types.InlineKeyboardButton("Download Data", callback_data="admin:download"))
    return kb


def build_user_list_keyboard(users, prefix: str):
    kb = types.InlineKeyboardMarkup()
    for u in users:
        label = f"{u['id']} @{u.get('username') or 'unknown'}"
        kb.add(types.InlineKeyboardButton(label, callback_data=f"{prefix}:{u['id']}"))
    kb.add(types.InlineKeyboardButton("⬅ Back", callback_data="admin:menu"))
    return kb


def register_admin_handlers(bot: telebot.TeleBot, db):
    admin_steps: Dict[int, Dict] = {}

    def ensure_admin(uid: int):
        return db.is_admin(uid)

    # -------- ADMIN COMMAND --------
    @bot.message_handler(commands=["admin"])
    def admin_cmd(message):
        if not ensure_admin(message.from_user.id):
            return bot.send_message(message.chat.id, "❌ You are not an admin.")

        bot.send_message(message.chat.id, "⚙️ Admin Panel", reply_markup=build_admin_menu())

    # -------- INLINE BUTTON HANDLER --------
    @bot.callback_query_handler(func=lambda c: c.data.startswith("admin:"))
    def cb(callback):
        uid = callback.from_user.id
        if not ensure_admin(uid):
            return bot.answer_callback_query(callback.id)

        bot.answer_callback_query(callback.id)
        parts = callback.data.split(":")
        section = parts[1]

        # MAIN MENU
        if section == "menu":
            return bot.edit_message_reply_markup(callback.message.chat.id, callback.message.message_id, build_admin_menu())

        # CREDITS → SHOW ALL USERS
        if section == "credits" and len(parts) == 2:
            users = db.list_users(limit=500)
            kb = build_user_list_keyboard(users, "admin:credits:user")
            return bot.send_message(callback.message.chat.id, "Select a user:", reply_markup=kb)

        # VALIDITY → SHOW ALL USERS
        if section == "validity" and len(parts) == 2:
            users = db.list_users(limit=500)
            kb = build_user_list_keyboard(users, "admin:validity:user")
            return bot.send_message(callback.message.chat.id, "Select a user:", reply_markup=kb)

        # CREDIT USER SELECTED
        if section == "credits" and parts[2] == "user":
            user_id = int(parts[3])
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("Add Credits", callback_data=f"admin:credits:add:{user_id}"))
            kb.add(types.InlineKeyboardButton("Remove Credits", callback_data=f"admin:credits:remove:{user_id}"))
            kb.add(types.InlineKeyboardButton("⬅ Back", callback_data="admin:credits"))
            return bot.send_message(callback.message.chat.id, f"User {user_id}\nChoose action:", reply_markup=kb)

        # VALIDITY USER SELECTED
        if section == "validity" and parts[2] == "user":
            user_id = int(parts[3])
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("Set Validity", callback_data=f"admin:validity:set:{user_id}"))
            kb.add(types.InlineKeyboardButton("Remove Validity", callback_data=f"admin:validity:remove:{user_id}"))
            kb.add(types.InlineKeyboardButton("⬅ Back", callback_data="admin:validity"))
            return bot.send_message(callback.message.chat.id, f"User {user_id}\nChoose action:", reply_markup=kb)

        # ASK CREDIT AMOUNT
        if section == "credits" and parts[2] in ("add", "remove"):
            admin_steps[uid] = {"action": parts[2], "target": int(parts[3])}
            return bot.send_message(callback.message.chat.id, "Send credit amount:")

        # ASK VALIDITY DAYS
        if section == "validity" and parts[2] == "set":
            admin_steps[uid] = {"action": "set_validity", "target": int(parts[3])}
            return bot.send_message(callback.message.chat.id, "Send number of days:")

        # REMOVE VALIDITY
        if section == "validity" and parts[2] == "remove":
            target = int(parts[3])
            db.remove_validity(target)
            return bot.send_message(callback.message.chat.id, f"✔ Removed validity for {target}")

        # LIST USERS
        if section == "list_users":
            users = db.list_users()
            text = "\n".join([f"{u['id']} @{u.get('username')} | credits={u.get('credits')}" for u in users])
            return bot.send_message(callback.message.chat.id, text or "No users found")

        # LIST PREMIUM USERS
        if section == "list_premium":
            users = db.list_premium_users()
            text = "\n".join([
                f"{u['id']} credits={u.get('credits')} exp={u.get('validity_expire_at')}"
                for u in users
            ])
            return bot.send_message(callback.message.chat.id, text or "No premium users")

        # BROADCAST
        if section == "broadcast":
            admin_steps[uid] = {"action": "broadcast"}
            return bot.send_message(callback.message.chat.id, "Send broadcast message:")

        # DOWNLOAD DB
        if section == "download":
            try:
                with open(DB_PATH, "rb") as f:
                    return bot.send_document(callback.message.chat.id, f)
            except:
                return bot.send_message(callback.message.chat.id, "DB not found!")

    # STEP HANDLER FOR ADMIN ACTIONS
    @bot.message_handler(func=lambda m: m.from_user.id in admin_steps)
    def step_handler(msg):
        uid = msg.from_user.id
        step = admin_steps.pop(uid, None)
        if not step:
            return

        action = step["action"]
        target = step.get("targ
