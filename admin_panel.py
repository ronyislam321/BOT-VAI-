from typing import Dict
import os
import telebot
from telebot import types
from config import DB_PATH


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


def build_submenu(kind: str):
    kb = types.InlineKeyboardMarkup()
    if kind == "credits":
        kb.add(types.InlineKeyboardButton(text="Add Credits", callback_data="admin:credits:add"))
        kb.add(types.InlineKeyboardButton(text="Remove Credits", callback_data="admin:credits:remove"))
        return kb
    if kind == "validity":
        kb.add(types.InlineKeyboardButton(text="Set Validity", callback_data="admin:validity:set"))
        kb.add(types.InlineKeyboardButton(text="Remove Validity", callback_data="admin:validity:remove"))
        return kb
    if kind == "admins":
        kb.add(types.InlineKeyboardButton(text="Add Admin", callback_data="admin:admins:add"))
        kb.add(types.InlineKeyboardButton(text="Remove Admin", callback_data="admin:admins:remove"))
        return kb
    kb.add(types.InlineKeyboardButton(text="Back", callback_data="admin:menu"))
    return kb


def build_user_list_keyboard(users, prefix: str):
    kb = types.InlineKeyboardMarkup()
    row = []
    for u in users:
        label = f"{u['id']} @{u.get('username') or ''}".strip()
        row.append(types.InlineKeyboardButton(text=label, callback_data=f"{prefix}:{u['id']}"))
        if len(row) == 2:
            kb.row(*row)
            row = []
    if row:
        kb.row(*row)
    kb.add(types.InlineKeyboardButton(text="Back", callback_data="admin:menu"))
    return kb


def register_admin_handlers(bot: telebot.TeleBot, db):
    admin_steps: Dict[int, Dict] = {}

    def ensure_admin(user_id: int) -> bool:
        return db.is_admin(user_id)

    @bot.message_handler(commands=["admin"])
    def admin_cmd(message: types.Message):
        if not ensure_admin(message.from_user.id):
            return
        bot.send_message(message.chat.id, "Admin Panel", reply_markup=build_admin_menu())

    @bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("admin:"))
    def admin_callbacks(callback: types.CallbackQuery):
        if not ensure_admin(callback.from_user.id):
            bot.answer_callback_query(callback.id)
            return
        parts = callback.data.split(":")
        action = parts[1]
        if action == "menu":
            bot.edit_message_reply_markup(callback.message.chat.id, callback.message.message_id, reply_markup=build_admin_menu())
        elif action == "credits":
            # Show users as buttons for quick selection
            if len(parts) == 2:
                users = db.list_users(limit=100)
                kb = build_user_list_keyboard(users, prefix="admin:credits:user")
                bot.send_message(callback.message.chat.id, "Select user to manage credits:", reply_markup=kb)
            elif parts[2] == "user":
                target_id = int(parts[3])
                admin_steps[callback.from_user.id] = {"action": None, "target_user": target_id}
                kb = types.InlineKeyboardMarkup()
                kb.add(types.InlineKeyboardButton(text="Add Credits", callback_data=f"admin:credits:do:add:{target_id}"))
                kb.add(types.InlineKeyboardButton(text="Remove Credits", callback_data=f"admin:credits:do:remove:{target_id}"))
                kb.add(types.InlineKeyboardButton(text="Back", callback_data="admin:credits"))
                bot.send_message(callback.message.chat.id, f"Selected user {target_id}. Choose an action:", reply_markup=kb)
            elif parts[2] == "do":
                op = parts[3]
                target_id = int(parts[4])
                if op == "add":
                    admin_steps[callback.from_user.id] = {"action": "add_credits", "target_user": target_id}
                    bot.send_message(callback.message.chat.id, "Reply with amount to add")
                elif op == "remove":
                    admin_steps[callback.from_user.id] = {"action": "remove_credits", "target_user": target_id}
                    bot.send_message(callback.message.chat.id, "Reply with amount to remove")
        elif action == "validity":
            # Show users as buttons for quick selection
            if len(parts) == 2:
                users = db.list_users(limit=100)
                kb = build_user_list_keyboard(users, prefix="admin:validity:user")
                bot.send_message(callback.message.chat.id, "Select user to manage validity:", reply_markup=kb)
            elif parts[2] == "user":
                target_id = int(parts[3])
                admin_steps[callback.from_user.id] = {"action": None, "target_user": target_id}
                kb = types.InlineKeyboardMarkup()
                kb.add(types.InlineKeyboardButton(text="Set Validity", callback_data=f"admin:validity:do:set:{target_id}"))
                kb.add(types.InlineKeyboardButton(text="Remove Validity", callback_data=f"admin:validity:do:remove:{target_id}"))
                kb.add(types.InlineKeyboardButton(text="Back", callback_data="admin:validity"))
                bot.send_message(callback.message.chat.id, f"Selected user {target_id}. Choose an action:", reply_markup=kb)
            elif parts[2] == "do":
                op = parts[3]
                target_id = int(parts[4])
                if op == "set":
                    admin_steps[callback.from_user.id] = {"action": "set_validity", "target_user": target_id}
                    bot.send_message(callback.message.chat.id, "Reply with days to set")
                elif op == "remove":
                    # Perform removal immediately without extra typing
                    db.remove_validity(target_id)
                    bot.send_message(callback.message.chat.id, f"Validity removed: {target_id}")
        elif action == "list_users":
            users = db.list_users(limit=50)
            lines = ["Users:"]
            for u in users:
                lines.append(f"{u['id']} @{u.get('username')} credits={u.get('credits')} premium={u.get('is_premium')}")
            bot.send_message(callback.message.chat.id, "\n".join(lines) if lines else "No users")
        elif action == "list_premium":
            users = db.list_premium_users(limit=50)
            lines = ["Premium Users:"]
            for u in users:
                lines.append(f"{u['id']} @{u.get('username')} credits={u.get('credits')} exp={u.get('validity_expire_at')}")
            bot.send_message(callback.message.chat.id, "\n".join(lines) if lines else "No premium users")
        elif action == "broadcast":
            admin_steps[callback.from_user.id] = {"action": "broadcast"}
            bot.send_message(callback.message.chat.id, "Send broadcast text now")
        elif action == "download":
            # Send the raw SQLite database file directly
            try:
                path = DB_PATH
                if not os.path.isfile(path):
                    bot.send_message(callback.message.chat.id, f"Database file not found: {path}")
                else:
                    with open(path, "rb") as f:
                        bot.send_document(callback.message.chat.id, f, caption=f"Database: {os.path.basename(path)}")
            except Exception as e:
                bot.send_message(callback.message.chat.id, f"Download failed: {e}")
        elif action == "admins":
            if len(parts) == 2:
                bot.send_message(callback.message.chat.id, "Admins Menu", reply_markup=build_submenu("admins"))
            elif parts[2] == "add":
                admin_steps[callback.from_user.id] = {"action": "add_admin"}
                bot.send_message(callback.message.chat.id, "Reply: user_id")
            elif parts[2] == "remove":
                admin_steps[callback.from_user.id] = {"action": "remove_admin"}
                bot.send_message(callback.message.chat.id, "Reply: user_id")
        bot.answer_callback_query(callback.id)

    # Only handle admin step replies when a step is active for this user
    @bot.message_handler(func=lambda m: admin_steps.get(m.from_user.id) is not None, content_types=['text'])
    def admin_steps_handler(message: types.Message):
        step = admin_steps.get(message.from_user.id)
        if not step or not ensure_admin(message.from_user.id):
            return
        act = step.get("action")
        try:
            if act in ("add_credits", "remove_credits"):
                user_id = int(step.get("target_user") or 0)
                amount = int(message.text.strip())
                db.ensure_user(user_id, None)
                if act == "add_credits":
                    db.add_credits(user_id, amount)
                    bot.send_message(message.chat.id, f"Credits added: {user_id} +{amount}")
                    try:
                        bot.send_message(user_id, f"You received {amount} voice credits. Enjoy!")
                    except Exception:
                        pass
                else:
                    db.remove_credits(user_id, amount)
                    bot.send_message(message.chat.id, f"Credits removed: {user_id} -{amount}")
            elif act == "set_validity":
                user_id = int(step.get("target_user") or 0)
                days = int(message.text.strip())
                db.set_validity(user_id, days)
                bot.send_message(message.chat.id, f"Validity set: {user_id} {days} days")
                try:
                    bot.send_message(user_id, f"Your premium validity is set for {days} days.")
                except Exception:
                    pass
            elif act == "broadcast":
                users = db.list_users(limit=10000)
                sent = 0
                for u in users:
                    try:
                        bot.send_message(u["id"], message.text)
                        sent += 1
                    except Exception:
                        pass
                bot.send_message(message.chat.id, f"Broadcast sent to {sent} users")
            elif act == "add_admin":
                user_id = int(message.text.strip())
                db.add_admin(user_id)
                bot.send_message(message.chat.id, f"Admin added: {user_id}")
            elif act == "remove_admin":
                user_id = int(message.text.strip())
                db.remove_admin(user_id)
                bot.send_message(message.chat.id, f"Admin removed: {user_id}")
        except Exception as e:
            bot.send_message(message.chat.id, f"Error: {e}")
        finally:
            admin_steps.pop(message.from_user.id, None)