import os
from datetime import datetime
import telebot
from telebot import types
from config import (
    ADMIN_CONTACT,
    WEBSITE_URL,
    COST_PER_VOICE,
    VOICES_DIR,
    REQUIRE_VALIDITY_FOR_TTS,
    MAX_TTS_CHARS
)
from fish_audio import FishAudioClient


def build_user_keyboard() -> types.ReplyKeyboardMarkup:
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(types.KeyboardButton("Select Model"), types.KeyboardButton("Plans"))
    kb.row(types.KeyboardButton("Usage"), types.KeyboardButton("Contact Admin"))
    kb.row(types.KeyboardButton("Our Website"))
    return kb


def build_speed_keyboard():
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton("🐢 Slow", callback_data="speed:0.7"),
        types.InlineKeyboardButton("⚡ Normal", callback_data="speed:1.0"),
        types.InlineKeyboardButton("🚀 Fast", callback_data="speed:1.3")
    )
    return kb


def build_models_keyboard(models):
    kb = types.InlineKeyboardMarkup()
    row = []

    for m in models:
        label = m.get("name") or m.get("id")
        btn = types.InlineKeyboardButton(
            text=label,
            callback_data=f"model:{m.get('id')}"
        )
        row.append(btn)

        if len(row) == 2:
            kb.row(*row)
            row = []

    if row:
        kb.row(*row)

    return kb



def register_user_handlers(bot: telebot.TeleBot, db):
    client = FishAudioClient()

    # START
    @bot.message_handler(commands=["start"])
    def cmd_start(message: types.Message):
        db.ensure_user(message.from_user.id, message.from_user.username)
        bot.send_message(
            message.chat.id,
            "Welcome! Use the buttons below.\n\n"
            "- Select Model\n- Plans\n- Usage\n- Contact Admin\n- Our Website",
            reply_markup=build_user_keyboard()
        )

    # CONTACT ADMIN
    @bot.message_handler(func=lambda m: m.text == "Contact Admin")
    def contact_admin(message):
        bot.send_message(message.chat.id, f"Contact admin: {ADMIN_CONTACT}")

    # WEBSITE
    @bot.message_handler(func=lambda m: m.text == "Our Website")
    def website(message):
        bot.send_message(message.chat.id, f"Website: {WEBSITE_URL}")

    # PLANS
    @bot.message_handler(func=lambda m: m.text == "Plans")
    def plans(message):
        from config import PLANS
        lines = ["Available plans:"]
        for p in PLANS:
            lines.append(
                f"• {p['name']}: {p['credits']} credits, {p['price']}, validity {p['validity_days']} days"
            )
        bot.send_message(message.chat.id, "\n".join(lines))

    # USAGE
    @bot.message_handler(func=lambda m: m.text == "Usage")
    def usage(message):
        user = db.get_user(message.from_user.id)
        exp = user.get("validity_expire_at") or "No validity"
        voices = db.list_user_voices(message.from_user.id)

        bot.send_message(
            message.chat.id,
            f"Status: {'Premium' if user.get('is_premium') else 'Normal'}\n"
            f"Credits: {user.get('credits')}\n"
            f"Validity: {exp}\n"
            f"Voices saved: {len(voices)}"
        )

    # SELECT MODEL
    @bot.message_handler(func=lambda m: m.text == "Select Model")
    def select_model(message):
        models = client.list_models()
        kb = build_models_keyboard(models)
        bot.send_message(message.chat.id, "Choose a model:", reply_markup=kb)

    # MODEL SELECTED → ASK SPEED
    @bot.callback_query_handler(func=lambda c: c.data.startswith("model:"))
    def model_chosen(callback):
        voice_id = callback.data.split(":", 1)[1]
        db.update_user_fields(callback.from_user.id, {"selected_model": voice_id})

        models = client.list_models()
        model_name = next(
            (m.get("name") or m.get("id") for m in models if m.get("id") == voice_id),
            voice_id
        )

        bot.send_message(
            callback.message.chat.id,
            f"✅ You selected: <b>{model_name}</b>\n\nChoose speaking speed:",
            reply_markup=build_speed_keyboard(),
            parse_mode="HTML"
        )
        bot.answer_callback_query(callback.id)

    # SPEED SELECTED
    @bot.callback_query_handler(func=lambda c: c.data.startswith("speed:"))
    def speed_chosen(callback):
        speed = float(callback.data.split(":")[1])
        db.update_user_fields(callback.from_user.id, {"selected_speed": speed})

        bot.send_message(
            callback.message.chat.id,
            f"🎤 Speed set: <b>{speed}</b>\nNow enter text to convert:",
            parse_mode="HTML"
        )
        bot.answer_callback_query(callback.id)

    # TTS ENTRY
    @bot.message_handler(content_types=["text"])
    def tts_entry(message):
        txt = message.text.strip()

        if txt in ("Select Model", "Plans", "Usage", "Contact Admin", "Our Website"):
            return

        if len(txt) > MAX_TTS_CHARS:
            return bot.send_message(message.chat.id, f"Text too long. Limit {MAX_TTS_CHARS} characters.")

        user = db.get_user(message.from_user.id)
        credits = user.get("credits")
        valid = db.is_valid(message.from_user.id)
        model = user.get("selected_model")
        speed = user.get("selected_speed", 1.0)

        if credits <= 0:
            return bot.send_message(message.chat.id, "❌ No credits. Contact admin.")

        if REQUIRE_VALIDITY_FOR_TTS and not valid:
            return bot.send_message(message.chat.id, "❌ Validity expired. Contact admin.")

        if not model:
            return bot.send_message(message.chat.id, "First select a model.")

        try:
            audio_bytes = client.synthesize_text(
                txt,
                model,
                language="en",
                format_="opus",
                speed=speed
            )
        except Exception as e:
            return bot.send_message(message.chat.id, f"TTS error: {e}")

        user_dir = os.path.join(VOICES_DIR, str(message.from_user.id))
        os.makedirs(user_dir, exist_ok=True)

        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        ogg_path = os.path.join(user_dir, f"tts_{ts}.ogg")

        with open(ogg_path, "wb") as f:
            f.write(audio_bytes)

        with open(ogg_path, "rb") as vf:
            bot.send_voice(message.chat.id, vf)

        db.store_voice(message.from_user.id, ogg_path)
        db.remove_credits(message.from_user.id, COST_PER_VOICE)

        bot.send_message(message.chat.id, f"Done! Speed={speed}, Remaining Credits={credits - 1}")
