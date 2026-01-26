import json
from typing import Dict

import telebot
from telebot import types

from config import DB_PATH, DEFAULT_MODELS


# -----------------------
# MENUS
# -----------------------
def build_admin_menu():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("Manage Credits", callback_data="admin:credits"))
    kb.add(types.InlineKeyboardButton("Manage Validity", callback_data="admin:validity"))

    # ✅ Direct by user id
    kb.add(types.InlineKeyboardButton("Credit by User ID", callback_data="admin:credit_by_id"))
    kb.add(types.InlineKeyboardButton("Validity by User ID", callback_data="admin:validity_by_id"))

    # ✅ Voice settings
    kb.add(types.InlineKeyboardButton("Change Default Voice", callback_data="admin:voice"))

    kb.add(types.InlineKeyboardButton("List Users", callback_data="admin:list_users"))
    kb.add(types.InlineKeyboardButton("List Premium Users", callback_data="admin:list_premium"))
    kb.add(types.InlineKeyboardButton("Broadcast", callback_data="admin:broadcast"))
    kb.add(types.InlineKeyboardButton("Download Data", callback_data="admin:download"))
    kb.add(types.InlineKeyboardButton("Manage Admins", callback_data="admin:admins"))
    return kb


def build_user_list_keyboard(users, prefix: str):
    kb = types.InlineKeyboardMarkup()
    for u in users:
        label = f"{u['id']} @{u.get('username') or 'unknown'}"
        kb.add(types.InlineKeyboardButton(label, callback_data=f"{prefix}:{u['id']}"))
    kb.add(types.InlineKeyboardButton("⬅ Back", callback_data="admin:menu"))
    return kb


# -----------------------
# VOICE MODELS (DB-stored)
# -----------------------
VOICE_MODELS_KEY = "VOICE_MODELS_JSON"
DEFAULT_VOICE_KEY = "DEFAULT_VOICE_ID"


def _short_id(s: str) -> str:
    s = s or ""
    return (s[:6] + "..." + s[-4:]) if len(s) > 12 else s


def register_admin_handlers(bot: telebot.TeleBot, db):
    admin_steps: Dict[int, Dict] = {}

    def ensure_admin(uid: int):
        return db.is_admin(uid)

    # Safe wrappers (won't crash even if db doesn't have settings methods)
    def db_get_setting(key: str, default: str = "") -> str:
        try:
            return db.get_setting(key, default)
        except Exception:
            return default

    def db_set_setting(key: str, value: str) -> bool:
        try:
            db.set_setting(key, value)
            return True
        except Exception:
            return False

    def get_voice_models():
        raw = db_get_setting(VOICE_MODELS_KEY, "")
        if raw:
            try:
                models = json.loads(raw)
                if isinstance(models, list) and models:
                    # basic sanitize
                    fixed = []
                    for m in models:
                        if isinstance(m, dict) and m.get("name") and m.get("id"):
                            fixed.append({"name": str(m["name"]), "id": str(m["id"])})
                    if fixed:
                        return fixed
            except Exception:
                pass
        # fallback
        return DEFAULT_MODELS

    def save_voice_models(models) -> bool:
        try:
            payload = json.dumps(models, ensure_ascii=False)
        except Exception:
            return False
        return db_set_setting(VOICE_MODELS_KEY, payload)

    def build_voice_keyboard(models):
        kb = types.InlineKeyboardMarkup()

        # Select default voice
        for m in (models or [])[:10]:
            name = m.get("name", "Voice")
            vid = m.get("id", "")
            kb.add(types.InlineKeyboardButton(f"🎙 {name}", callback_data=f"admin:voice:set:{vid}"))

        # Manage button IDs
        kb.add(types.InlineKeyboardButton("🛠 Edit Button Voice IDs", callback_data="admin:voice_manage"))
        kb.add(types.InlineKeyboardButton("✍ Set by ID (custom)", callback_data="admin:voice:custom"))
        kb.add(types.InlineKeyboardButton("⬅ Back", callback_data="admin:menu"))
        return kb

    def build_voice_manage_keyboard(models):
        kb = types.InlineKeyboardMarkup()
        for i, m in enumerate((models or [])[:10]):
            name = m.get("name", f"Voice{i+1}")
            vid = m.get("id", "")
            kb.add(types.InlineKeyboardButton(f"✏️ {name} ({_short_id(vid)})", callback_data=f"admin:voice_edit:{i}"))
        kb.add(types.InlineKeyboardButton("♻️ Reset to defaults", callback_data="admin:voice_reset"))
        kb.add(types.InlineKeyboardButton("⬅ Back", callback_data="admin:voice"))
        return kb

    # -----------------------
    # ADMIN CMD
    # -----------------------
    @bot.message_handler(commands=["admin"])
    def admin_cmd(message):
        if not ensure_admin(message.from_user.id):
            return
        bot.send_message(message.chat.id, "⚙️ Admin Panel", reply_markup=build_admin_menu())

    # -----------------------
    # CALLBACKS
    # -----------------------
    @bot.callback_query_handler(func=lambda c: (c.data or "").startswith("admin:"))
    def cb(callback):
        uid = callback.from_user.id
        if not ensure_admin(uid):
            return bot.answer_callback_query(callback.id)

        bot.answer_callback_query(callback.id)
        parts = (callback.data or "").split(":")
        if len(parts) < 2:
            return

        section = parts[1]

        # -----------------------
        # MAIN MENU
        # -----------------------
        if section == "menu":
            return bot.edit_message_reply_markup(
                callback.message.chat.id,
                callback.message.message_id,
                build_admin_menu()
            )

        # -----------------------
        # VOICE MENU
        # -----------------------
        if section == "voice" and len(parts) == 2:
            models = get_voice_models()
            fallback = models[0]["id"] if models else ""
            current = db_get_setting(DEFAULT_VOICE_KEY, fallback)
            text = (
                "🎛 <b>Default Voice Settings</b>\n\n"
                f"Current voice id:\n<code>{current}</code>\n\n"
                "Select a voice:"
            )
            return bot.send_message(callback.message.chat.id, text, reply_markup=build_voice_keyboard(models))

        # admin:voice:set:<voice_id>
        if section == "voice" and len(parts) >= 4 and parts[2] == "set":
            voice_id = parts[3].strip()
            if not voice_id:
                return bot.send_message(callback.message.chat.id, "❌ Invalid Voice ID")

            ok = db_set_setting(DEFAULT_VOICE_KEY, voice_id)
            if not ok:
                return bot.send_message(callback.message.chat.id, "❌ DB settings missing. db.py তে get_setting/set_setting লাগবে।")

            return bot.send_message(callback.message.chat.id, f"✅ Default voice updated:\n<code>{voice_id}</code>")

        # admin:voice:custom
        if section == "voice" and len(parts) >= 3 and parts[2] == "custom":
            admin_steps[uid] = {"action": "set_voice_custom", "target": 0}
            return bot.send_message(callback.message.chat.id, "Send new Voice ID:")

        # admin:voice_manage
        if section == "voice_manage":
            models = get_voice_models()
            return bot.send_message(
                callback.message.chat.id,
                "🛠 <b>Edit Button Voice IDs</b>\nSelect which button to edit:",
                reply_markup=build_voice_manage_keyboard(models)
            )

        # admin:voice_reset
        if section == "voice_reset":
            ok = save_voice_models(DEFAULT_MODELS)
            if not ok:
                return bot.send_message(callback.message.chat.id, "❌ DB settings missing. db.py তে get_setting/set_setting লাগবে।")
            return bot.send_message(callback.message.chat.id, "✅ Voice buttons reset to DEFAULT_MODELS.")

        # admin:voice_edit:<index>
        if section == "voice_edit" and len(parts) >= 3:
            try:
                idx = int(parts[2])
            except Exception:
                return bot.send_message(callback.message.chat.id, "❌ Invalid selection.")

            models = get_voice_models()
            if idx < 0 or idx >= len(models):
                return bot.send_message(callback.message.chat.id, "❌ Invalid selection.")

            name = models[idx].get("name", "Voice")
            current_id = models[idx].get("id", "")
            admin_steps[uid] = {"action": "edit_voice_button_id", "target": idx}
            return bot.send_message(
                callback.message.chat.id,
                f"✏️ <b>{name}</b>\nCurrent id: <code>{current_id}</code>\n\nSend new Voice ID:"
            )

        # -----------------------
        # DIRECT: CREDIT BY USER ID
        # -----------------------
        if section == "credit_by_id":
            admin_steps[uid] = {"action": "credit_by_id", "target": 0}
            return bot.send_message(callback.message.chat.id, "Send: user_id credits\nExample: 123456 50")

        # -----------------------
        # DIRECT: VALIDITY BY USER ID
        # -----------------------
        if section == "validity_by_id":
            admin_steps[uid] = {"action": "validity_by_id", "target": 0}
            return bot.send_message(callback.message.chat.id, "Send: user_id days\nExample: 123456 30")

        # -----------------------
        # CREDITS → SHOW USERS
        # -----------------------
        if section == "credits" and len(parts) == 2:
            users = db.list_users(limit=200)
            kb = build_user_list_keyboard(users, "admin:credits:user")
            return bot.send_message(callback.message.chat.id, "Select a user:", reply_markup=kb)

        # -----------------------
        # VALIDITY → SHOW USERS
        # -----------------------
        if section == "validity" and len(parts) == 2:
            users = db.list_users(limit=200)
            kb = build_user_list_keyboard(users, "admin:validity:user")
            return bot.send_message(callback.message.chat.id, "Select a user:", reply_markup=kb)

        # -----------------------
        # SELECTED USER FOR CREDITS
        # admin:credits:user:<id>
        # -----------------------
        if section == "credits" and len(parts) >= 4 and parts[2] == "user":
            user_id = int(parts[3])
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("Add Credits", callback_data=f"admin:credits:add:{user_id}"))
            kb.add(types.InlineKeyboardButton("Remove Credits", callback_data=f"admin:credits:remove:{user_id}"))
            kb.add(types.InlineKeyboardButton("⬅ Back", callback_data="admin:credits"))
            return bot.send_message(callback.message.chat.id, f"User {user_id}\nChoose action:", reply_markup=kb)

        # -----------------------
        # SELECTED USER FOR VALIDITY
        # admin:validity:user:<id>
        # -----------------------
        if section == "validity" and len(parts) >= 4 and parts[2] == "user":
            user_id = int(parts[3])
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("Set Validity", callback_data=f"admin:validity:set:{user_id}"))
            kb.add(types.InlineKeyboardButton("Remove Validity", callback_data=f"admin:validity:remove:{user_id}"))
            kb.add(types.InlineKeyboardButton("⬅ Back", callback_data="admin:validity"))
            return bot.send_message(callback.message.chat.id, f"User {user_id}\nChoose action:", reply_markup=kb)

        # -----------------------
        # CREDIT AMOUNT INPUT
        # admin:credits:add:<id> / admin:credits:remove:<id>
        # -----------------------
        if section == "credits" and len(parts) >= 4 and parts[2] in ("add", "remove"):
            admin_steps[uid] = {"action": parts[2], "target": int(parts[3])}
            return bot.send_message(callback.message.chat.id, "Send credit amount:")

        # -----------------------
        # VALIDITY INPUT
        # admin:validity:set:<id>
        # -----------------------
        if section == "validity" and len(parts) >= 4 and parts[2] == "set":
            admin_steps[uid] = {"action": "set_validity", "target": int(parts[3])}
            return bot.send_message(callback.message.chat.id, "Send number of days:")

        if section == "validity" and len(parts) >= 4 and parts[2] == "remove":
            target = int(parts[3])
            db.remove_validity(target)
            return bot.send_message(callback.message.chat.id, f"✔ Removed validity for {target}")

        # -----------------------
        # LIST USERS
        # -----------------------
        if section == "list_users":
            users = db.list_users()
            text = "\n".join([f"{u['id']} @{u.get('username')} | credits={u.get('credits')}" for u in users])
            return bot.send_message(callback.message.chat.id, text or "No users")

        # -----------------------
        # LIST PREMIUM
        # -----------------------
        if section == "list_premium":
            users = db.list_premium_users()
            text = "\n".join([f"{u['id']} credits={u.get('credits')} exp={u.get('validity_expire_at')}" for u in users])
            return bot.send_message(callback.message.chat.id, text or "No premium users")

        # -----------------------
        # BROADCAST
        # -----------------------
        if section == "broadcast":
            admin_steps[uid] = {"action": "broadcast", "target": 0}
            return bot.send_message(callback.message.chat.id, "Send broadcast message:")

        # -----------------------
        # DOWNLOAD DB
        # -----------------------
        if section == "download":
            try:
                with open(DB_PATH, "rb") as f:
                    return bot.send_document(callback.message.chat.id, f)
            except Exception:
                return bot.send_message(callback.message.chat.id, "DB not found!")

        # -----------------------
        # MANAGE ADMINS (placeholder)
        # -----------------------
        if section == "admins":
            return bot.send_message(callback.message.chat.id, "Admins management not added here yet.")

    # -----------------------
    # STEP HANDLER
    # -----------------------
    @bot.message_handler(func=lambda m: m.from_user.id in admin_steps)
    def step_handler(msg):
        uid = msg.from_user.id
        step = admin_steps.pop(uid, None)
        if not step:
            return

        action = step.get("action")
        target = step.get("target", 0)

        try:
            # Custom default voice id
            if action == "set_voice_custom":
                voice_id = (msg.text or "").strip()
                if len(voice_id) < 10:
                    return bot.send_message(msg.chat.id, "❌ Invalid Voice ID")

                ok = db_set_setting(DEFAULT_VOICE_KEY, voice_id)
                if not ok:
                    return bot.send_message(msg.chat.id, "❌ DB settings missing. db.py তে get_setting/set_setting লাগবে।")

                return bot.send_message(msg.chat.id, f"✅ Default voice updated:\n<code>{voice_id}</code>")

            # Edit button voice id (Marie/Daisy mapping)
            if action == "edit_voice_button_id":
                new_id = (msg.text or "").strip()
                if len(new_id) < 10:
                    return bot.send_message(msg.chat.id, "❌ Invalid Voice ID")

                models = get_voice_models()
                idx = int(target)
                if idx < 0 or idx >= len(models):
                    return bot.send_message(msg.chat.id, "❌ Invalid selection")

                models[idx]["id"] = new_id
                ok = save_voice_models(models)
                if not ok:
                    return bot.send_message(msg.chat.id, "❌ DB settings missing. db.py তে get_setting/set_setting লাগবে।")

                return bot.send_message(
                    msg.chat.id,
                    f"✅ Updated <b>{models[idx].get('name','Voice')}</b> id:\n<code>{new_id}</code>"
                )

            # Direct credit by user id (format: "user_id credits")
            if action == "credit_by_id":
                parts = (msg.text or "").strip().split()
                if len(parts) != 2:
                    return bot.send_message(msg.chat.id, "❌ Format: user_id credits\nExample: 123456 50")
                user_id = int(parts[0])
                amount = int(parts[1])
                db.add_credits(user_id, amount)
                return bot.send_message(msg.chat.id, f"✔ Added {amount} credits to {user_id}")

            # Direct validity by user id (format: "user_id days")
            if action == "validity_by_id":
                parts = (msg.text or "").strip().split()
                if len(parts) != 2:
                    return bot.send_message(msg.chat.id, "❌ Format: user_id days\nExample: 123456 30")
                user_id = int(parts[0])
                days = int(parts[1])
                db.set_validity(user_id, days)
                return bot.send_message(msg.chat.id, f"✔ Validity set: {days} days for {user_id}")

            # Credit add/remove (selected user)
            if action == "add":
                amount = int(msg.text)
                db.add_credits(int(target), amount)
                return bot.send_message(msg.chat.id, f"✔ Added {amount} credits to {target}")

            if action == "remove":
                amount = int(msg.text)
                db.remove_credits(int(target), amount)
                return bot.send_message(msg.chat.id, f"✔ Removed {amount} credits from {target}")

            # Validity set
            if action == "set_validity":
                days = int(msg.text)
                db.set_validity(int(target), days)
                return bot.send_message(msg.chat.id, f"✔ Validity set for {target}")

            # Broadcast
            if action == "broadcast":
                import time

                users = db.list_users(limit=100000)
                sent = 0
                failed = 0

                for u in users:
                    uid2 = u.get("id")
                    if not uid2:
                        continue
                    try:
                        bot.send_message(uid2, msg.text)
                        sent += 1
                        time.sleep(0.05)  # ~20 msg/sec safe
                    except Exception:
                        failed += 1
                        time.sleep(0.2)

                return bot.send_message(
                    msg.chat.id,
                    f"📣 Broadcast finished.\n✅ Sent: {sent}\n❌ Failed: {failed}"
                )

        except Exception as e:
            bot.send_message(msg.chat.id, f"❌ Error: {e}")
