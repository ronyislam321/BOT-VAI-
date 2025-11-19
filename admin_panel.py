# ==============================
#  ADMIN PANEL (PRO VERSION)
#  Fully Fixed – User List + Credits + Validity
# ==============================

from typing import Dict
import os
import telebot
from telebot import types
from config import DB_PATH


# ==============================
# MAIN ADMIN MENU
# ==============================
def build_admin_menu():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(text="Manage Credits", callback_data="admin:credits"))
    kb.add(types.InlineKeyboardButton(text="Manage Validity", callback_data="admin:validity"))
    kb.add(types.InlineKeyboardButton(text="List Users", callback_data="admin:list_users"))
    kb.add(types.InlineKeyboardButton(text="List Premium Users", callback_data="admin:list_premium"))
    kb.add(types.InlineKeyboardButton(text="Broadcast", callback_data="admin:broadcast"))
    kb.add(types.InlineKeyboardButton(text="Download Data", callback_data="admin:download"))
    kb.add(types.InlineKeyboardButton(text="Manage Admins", callback_data="admin:admins"))
    return kb


# ==============================
# USER LIST KEYBOARD
# ==============================
def build_user_list_keyboard(users, prefix: str):
    kb = types.InlineKeyboardMarkup()

    for u in users:
        label = f"{u['id']} @{u.get('username') or 'unknown'}"
        kb.add(types.InlineKeyboardButton(text=label, callback_data=f"{prefix}:{u['id']}"))

    kb.add(types.InlineKeyboardButton(text="⬅ Back", callback_data="admin:menu"))
    return kb


# ==============================
# REGISTER HANDLERS
# ==============================
def register_admin_handlers(bot: telebot.TeleBot, db):
    admin_steps: Dict[int, Dict] = {}

    def ensure_admin(uid: int):
        return db.is_admin(uid)

    # ADMIN COMMAND
    @bot.message_handler(commands=["admin"])
    def admin_cmd(message):
        if not ensure_admin(message.from_user.id):
            return

        bot.send_message(message.chat.id, "⚙️ Admin Panel", reply_markup=build_admin_menu())

    # ==============================
    # CALLBACK HANDLER
    # ==============================
    @bot.callback_query_handler(func=lambda c: c.data.startswith("admin:"))
    def cb(callback):
        uid = callback.from_user.id
        if not ensure_admin(uid):
            return bot.answer_callback_query(callback.id, "Unauthorized")

        parts = callback.data.split(":")
        action = parts[1]

        bot.answer_callback_query(callback.id)

        # ========= BACK TO MAIN MENU =========
        if action == "menu":
            bot.edit_message_reply_markup(callback.message.chat.id, callback.message.message_id, build_admin_menu())
            return

        # ========= MANAGE CREDITS =========
        if action == "credits":
            users = db.list_users(limit=200)
            kb = build_user_list_keyboard(users, "admin:credits:user")
            return bot.send_message(callback.message.chat.id, "Select a user:", reply_markup=kb)

        if action == "validity":
            users = db.list_users(limit=200)
            kb = build_user_list_keyboard(users, "admin:validity:user")
            return bot.send_message(callback.message.chat.id, "Select a user:", reply_markup=kb)

        # ========= USER SELECTED FOR CREDITS =========
        if action == "credits" and parts[2] == "user":
            user_id = int(parts[3])
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("Add Credits", callback_data=f"admin:credits:add:{user_id}"))
            kb.add(types.InlineKeyboardButton("Remove Credits", callback_data=f"admin:credits:remove:{user_id}"))
            kb.add(types.InlineKeyboardButton("⬅ Back", callback_data="admin:credits"))
            return bot.send_message(callback.message.chat.id, f"User ID: {user_id}\nChoose an action:", reply_markup=kb)

        # ========= USER SELECTED FOR VALIDITY =========
        if action == "validity" and parts[2] == "user":
            user_id = int(parts[3])
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("Set Validity", callback_data=f"admin:validity:set:{user_id}"))
            kb.add(types.InlineKeyboardButton("Remove Validity", callback_data=f"admin:validity:remove:{user_id}"))
            kb.add(types.InlineKeyboardButton("⬅ Back", callback_data="admin:validity"))
            return bot.send_message(callback.message.chat.id, f"User ID: {user_id}\nChoose an action:", reply_markup=kb)

        # ========= CREDIT ACTION =========
        if action == "credits" and parts[2] in ("add", "remove"):
            op = parts[2]
            target = int(parts[3])

            admin_steps[uid] = {"action": op, "target": target}
            return bot.send_message(callback.message.chat.id, "Send amount:")

        # ========= VALIDITY ACTION =========
        if action == "validity" and parts[2] == "set":
            target = int(parts[3])
            admin_steps[uid] = {"action": "set_validity", "target": target}
            return bot.send_message(callback.message.chat.id, "Send number of days:")

        if action == "validity" and parts[2] == "remove":
            target = int(parts[3])
            db.remove_validity(target)
            return bot.send_message(callback.message.chat.id, f"✔ Validity removed for {target}")

        # ========= LIST USERS =========
        if action == "list_users":
            users = db.list_users(limit=200)
            txt = "👥 Users:\n\n" + "\n".join(
                f"{u['id']} @{u.get('username')} | credits={u.get('credits')} | premium={u.get('is_premium')}"
                for u in users
            )
            return bot.send_message(callback.message.chat.id, txt)

        # ========= LIST PREMIUM USERS =========
        if action == "list_premium":
            users = db.list_premium_users(limit=200)
            txt = "⭐ Premium Users:\n\n" + "\n".join(
                f"{u['id']} @{u.get('username')} | credits={u.get('credits')} | exp={u.get('validity_expire_at')}"
                for u in users
            )
            return bot.send_message(callback.message.chat.id, txt)

        # ========= BROADCAST =========
        if action == "broadcast":
            admin_steps[uid] = {"action": "broadcast"}
            return bot.send_message(callback.message.chat.id, "Send broadcast text:")

        # ========= DOWNLOAD DB =========
        if action == "download":
            try:
                with open(DB_PATH, "rb") as f:
                    bot.send_document(callback.message.chat.id, f, caption="Database File")
            except:
                bot.send_message(callback.message.chat.id, "DB file not found!")

    # ==============================
    # HANDLE TYPED INPUT
    # ==============================
    @bot.message_handler(func=lambda m: m.from_user.id in admin_steps)
    def step_input(msg):
        uid = msg.from_user.id
        step = admin_steps.get(uid)

        if not step:
            return

        action = step["action"]
        target = step["target"]

        try:
            # ADD / REMOVE CREDITS
            if action in ("add", "remove"):
                amount = int(msg.text)
                if action == "add":
                    db.add_credits(target, amount)
                    bot.send_message(msg.chat.id, f"✔ Added {amount} credits to {target}")
                else:
                    db.remove_credits(target, amount)
                    bot.send_message(msg.chat.id, f"✔ Removed {amount} credits from {target}")

            # SET VALIDITY
            elif action == "set_validity":
                days = int(msg.text)
                db.set_validity(target, days)
                bot.send_message(msg.chat.id, f"✔ Validity set for {target} ({days} days)")

            # BROADCAST
            elif action == "broadcast":
                users = db.list_users(limit=20000)
                sent = 0
                for u in users:
                    try:
                        bot.send_message(u["id"], msg.text)
                        sent += 1
                    except:
                        pass
                bot.send_message(msg.chat.id, f"Broadcast sent to {sent} users")

        except Exception as e:
            bot.send_message(msg.chat.id, f"Error: {e}")

        finally:
            admin_steps.pop(uid, None)
