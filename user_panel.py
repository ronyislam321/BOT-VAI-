import os
import shutil
import subprocess
from datetime import datetime
import telebot
from telebot import types
from config import ADMIN_CONTACT, WEBSITE_URL, COST_PER_VOICE, VOICES_DIR, REQUIRE_VALIDITY_FOR_TTS, FISH_AUDIO_MP3_BITRATE, MAX_TTS_CHARS
from fish_audio import FishAudioClient


def build_user_keyboard() -> types.ReplyKeyboardMarkup:
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    kb.row(types.KeyboardButton("Select Model"), types.KeyboardButton("Plans"))
    kb.row(types.KeyboardButton("Usage"), types.KeyboardButton("Contact Admin"))
    kb.row(types.KeyboardButton("Our Website"))
    return kb


def build_models_keyboard(models):
    kb = types.InlineKeyboardMarkup()
    row = []
    for m in models:
        label = m.get("name") or m.get("id")
        row.append(types.InlineKeyboardButton(text=label, callback_data=f"model:{m.get('id')}"))
        if len(row) == 2:
            kb.row(*row)
            row = []
    if row:
        kb.row(*row)
    return kb


def register_user_handlers(bot: telebot.TeleBot, db):
    client = FishAudioClient()

    @bot.message_handler(commands=["start"])
    def cmd_start(message: types.Message):
        db.ensure_user(message.from_user.id, message.from_user.username)
        text = (
            "Welcome! Use the buttons below.\n\n"
            "- Select Model\n"
            "- Plans\n"
            "- Usage\n"
            "- Contact Admin\n"
            "- Our Website"
        )
        bot.send_message(message.chat.id, text, reply_markup=build_user_keyboard())

    @bot.message_handler(func=lambda m: m.text == "Contact Admin")
    def contact_admin(message: types.Message):
        bot.send_message(message.chat.id, f"Contact admin: {ADMIN_CONTACT}")

    @bot.message_handler(func=lambda m: m.text == "Our Website")
    def website(message: types.Message):
        bot.send_message(message.chat.id, f"Website: {WEBSITE_URL}")

    @bot.message_handler(func=lambda m: m.text == "Plans")
    def plans(message: types.Message):
        from config import PLANS
        lines = ["Available plans:"]
        for p in PLANS:
            lines.append(f"• {p['name']}: {p['credits']} credits, {p['price']}, validity {p['validity_days']} days")
        bot.send_message(message.chat.id, "\n".join(lines))

    @bot.message_handler(func=lambda m: m.text == "Usage")
    def usage(message: types.Message):
        user = db.get_user(message.from_user.id)
        exp = user.get("validity_expire_at") or "No validity"
        voices = db.list_user_voices(message.from_user.id)
        bot.send_message(
            message.chat.id,
            f"Status: {'Premium' if user.get('is_premium') else 'Normal'}\n"
            f"Credits: {user.get('credits') or 0}\n"
            f"Validity: {exp}\n"
            f"Voices saved: {len(voices)}",
        )

    @bot.message_handler(func=lambda m: m.text == "Select Model")
    def select_model(message: types.Message):
        models = client.list_models()
        kb = build_models_keyboard(models)
        bot.send_message(message.chat.id, "Choose a model:", reply_markup=kb)

    @bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("model:"))
    def model_chosen(callback: types.CallbackQuery):
        voice_id = callback.data.split(":", 1)[1]
        db.update_user_fields(callback.from_user.id, {"selected_model": voice_id})
        bot.send_message(callback.message.chat.id, "Model selected. Now send text to generate voice.")
        bot.answer_callback_query(callback.id)

    @bot.message_handler(content_types=['text'])
    def tts_entry(message: types.Message):
        txt = (message.text or "").strip()

        # Ignore keyboard buttons
        if txt in ("Select Model", "Plans", "Usage", "Contact Admin", "Our Website"):
            return

        # Check character limit
        if len(txt) > MAX_TTS_CHARS:
            bot.send_message(message.chat.id, f"Text too long. Limit: {MAX_TTS_CHARS} characters.")
            return

        user = db.get_user(message.from_user.id)

        # PREMIUM CHECK
        credits = user.get("credits") or 0
        valid = db.is_valid(message.from_user.id)

        if credits <= 0:
            bot.send_message(message.chat.id, "❌ You have no credits. Please contact admin.")
            return

        if REQUIRE_VALIDITY_FOR_TTS and not valid:
            bot.send_message(message.chat.id, "❌ Your validity expired. Please contact admin.")
            return

        model = user.get("selected_model")
        if not model:
            bot.send_message(message.chat.id, "Please select a model first.")
            return

        # Generate TTS
        try:
            audio_bytes = client.synthesize_text(
                txt,
                model,
                language="en",
                format_="opus",
            )
        except Exception as e:
            bot.send_message(message.chat.id, f"TTS error: {e}")
            return

        # Save audio
        user_dir = os.path.join(VOICES_DIR, str(message.from_user.id))
        os.makedirs(user_dir, exist_ok=True)
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        ogg_path = os.path.join(user_dir, f"tts_{ts}.ogg")

        with open(ogg_path, "wb") as f:
            f.write(audio_bytes)

        with open(ogg_path, "rb") as vf:
            bot.send_voice(message.chat.id, vf)

        db.store_voice(message.from_user.id, ogg_path)

        # Deduct credit
        db.remove_credits(message.from_user.id, COST_PER_VOICE)

        bot.send_message(message.chat.id, f"Voice generated! 1 credit deducted. Remaining: {credits - 1}")
