import os
import subprocess
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


# --------------------- SPEED PROCESSOR ---------------------
def change_speed(input_path, output_path, speed):
    """
    FFmpeg দিয়ে অডিওর speed পরিবর্তন করে
    """
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-filter:a", f"atempo={speed}",
        output_path
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# --------------------- USER MENU ---------------------
def build_user_keyboard() -> types.ReplyKeyboardMarkup:
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(types.KeyboardButton("Select Model"), types.KeyboardButton("Plans"))
    kb.row(types.KeyboardButton("Usage"), types.KeyboardButton("Contact Admin"))
    kb.row(types.KeyboardButton("Our Website"))
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


# --------------------- MAIN USER HANDLERS ---------------------
def register_user_handlers(bot: telebot.TeleBot, db):
    client = FishAudioClient()

    # START
    @bot.message_handler(commands=["start"])
    def cmd_start(message: types.Message):
        db.ensure_user(message.from_user.id, message.from_user.username)
        bot.send_message(
            message.chat.id,
            "Welcome! Use the buttons below.",
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
        text = "Available Plans:\n\n"
        for p in PLANS:
            text += f"• {p['name']}: {p['credits']} credits — {p['price']} — {p['validity_days']} days\n"
        bot.send_message(message.chat.id, text)

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

    # MODEL CHOSEN
    @bot.callback_query_handler(func=lambda c: c.data.startswith("model:"))
    def model_chosen(callback):
        voice_id = callback.data.split(":", 1)[1]
        db.update_user_fields(callback.from_user.id, {"selected_model": voice_id})

        # Model name
        models = client.list_models()
        model_name = next((m.get("name") or m.get("id") for m in models if m.get("id") == voice_id), voice_id)

        # SPEED BUTTONS
        kb = types.InlineKeyboardMarkup()
        kb.row(
            types.InlineKeyboardButton("🐢 Slow", callback_data="speed:0.7"),
            types.InlineKeyboardButton("⚡ Normal", callback_data="speed:1.0"),
            types.InlineKeyboardButton("🚀 Fast", callback_data="speed:1.3"),
        )

        bot.send_message(
            callback.message.chat.id,
            f"✅ You selected: <b>{model_name}</b>\n\nChoose speaking speed:",
            reply_markup=kb,
            parse_mode="HTML"
        )

        bot.answer_callback_query(callback.id)

    # SPEED SELECTED
    @bot.callback_query_handler(func=lambda c: c.data.startswith("speed:"))
    def speed_selected(callback):
        speed = float(callback.data.split(":")[1])
        db.update_user_fields(callback.from_user.id, {"speed": speed})

        bot.send_message(callback.message.chat.id, "Speed selected! Now send text to convert into voice.")
        bot.answer_callback_query(callback.id)

    # TTS
    @bot.message_handler(content_types=['text'])
    def tts_entry(message):
        txt = message.text.strip()

        if txt in ("Select Model", "Plans", "Usage", "Contact Admin", "Our Website"):
            return

        if len(txt) > MAX_TTS_CHARS:
            return bot.send_message(message.chat.id, f"Text too long. Limit {MAX_TTS_CHARS} chars.")

        user = db.get_user(message.from_user.id)

        if user.get("credits") <= 0:
            return bot.send_message(message.chat.id, "❌ No credits left.")

        if REQUIRE_VALIDITY_FOR_TTS and not db.is_valid(message.from_user.id):
            return bot.send_message(message.chat.id, "❌ Validity expired.")

        model = user.get("selected_model")
        if not model:
            return bot.send_message(message.chat.id, "Please select a model first.")

        speed = user.get("speed", 1.0)

        try:
            audio_bytes = client.synthesize_text(txt, model, language="en", format_="opus")
        except Exception as e:
            return bot.send_message(message.chat.id, f"TTS error: {e}")

        # Save original
        user_dir = os.path.join(VOICES_DIR, str(message.from_user.id))
        os.makedirs(user_dir, exist_ok=True)
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        raw_path = os.path.join(user_dir, f"tts_{ts}.ogg")
        final_path = os.path.join(user_dir, f"tts_{ts}_speed.ogg")

        with open(raw_path, "wb") as f:
            f.write(audio_bytes)

        # Apply speed with FFmpeg
        change_speed(raw_path, final_path, speed)

        # Send final
        with open(final_path, "rb") as vf:
            bot.send_voice(message.chat.id, vf)

        db.store_voice(message.from_user.id, final_path)
        db.remove_credits(message.from_user.id, COST_PER_VOICE)

        bot.send_message(message.chat.id, f"Voice generated! 1 credit deducted. Remaining: {user.get('credits') - 1}")
