import os
import logging
import httpx
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler
)
from openai import OpenAI

# ─── Настройки ───────────────────────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN", "7146960065:AAEncOXgBeMjvUFGoX0f1QGr1_bHIDdK3gQ")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "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")
GOOGLE_SHEET_URL = os.getenv("GOOGLE_SHEET_URL", "https://script.google.com/macros/s/AKfycbzqwkgp8nSXxtSN1VB16QObhcOgqY4ye45-_Xmpc9OgAQnhQLAdL3EcjcSSg8zz05c/exec")

SPONSOR_USERNAME = "@tach_ttt"
SPONSOR_PHONE = "+99363327177"
CATALOG_LINK = "https://ponixs92.github.io/vertera-shop/"
REGISTER_LINK = "https://id.boss.vertera.org/register?ref=FEKMPTVL85&service=OS3_PARTNER"

client = OpenAI(api_key=OPENAI_API_KEY)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── Состояния ───────────────────────────────────────────────
CHAT, ANKETA_NAME, ANKETA_PHONE, ANKETA_CITY, ANKETA_INTEREST = range(5)

# ─── Системный промпт GPT ────────────────────────────────────
SYSTEM_PROMPT = """Ты — консультант компании Vertera в Туркменистане. Твоё имя — Вера.

О компании:
- Vertera — международная компания, производит натуральные продукты на основе морских водорослей
- Продукция: гели, детское питание, косметика, порошки для стирки
- Флагман: гель алоэ вера — укрепляет иммунитет, улучшает пищеварение, даёт энергию

Как купить со скидкой:
- Зарегистрировать личный кабинет и получить 30% скидку на всю продукцию
- Ссылка для регистрации: https://id.boss.vertera.org/register?ref=FEKMPTVL85&service=OS3_PARTNER

Бизнес-возможности:
- Зарабатывать можно рекомендуя продукт своему окружению
- Нужно попробовать продукт самому — тогда результат точно будет
- Первый шаг: пройти регистрацию и сделать первый заказ
- Контакт спонсора: +99363327177 (Telegram: @tach_ttt)

Правила общения:
- Отвечай дружелюбно, коротко и по делу
- Если человек спрашивает про продукты — расскажи и предложи каталог
- Если человек интересуется бизнесом — объясни и предложи зарегистрироваться
- Когда чувствуешь что человек заинтересован и готов — предложи заполнить анкету фразой содержащей слово "анкету"
- Не придумывай цены — говори что цены уточнит менеджер
- Отвечай на том языке на котором пишет пользователь (русский или туркменский)
"""

user_histories = {}

MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [["🛒 Купить продукт", "💼 Бизнес с Vertera"],
     ["📖 Каталог", "📞 Связаться"]],
    resize_keyboard=True
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_histories[user.id] = []
    await update.message.reply_text(
        f"Привет, {user.first_name}! 👋\n\n"
        "Я Вера — консультант компании *Vertera* 🌿\n\n"
        "Производим натуральные продукты на основе морских водорослей. "
        "Помогаю улучшить здоровье и зарабатывать рекомендуя продукт.\n\n"
        "Чем могу помочь?",
        parse_mode="Markdown",
        reply_markup=MAIN_KEYBOARD
    )
    return CHAT

async def chat_with_gpt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text

    if text == "📖 Каталог":
        await update.message.reply_text(
            f"📖 Наш каталог продукции:\n{CATALOG_LINK}\n\nЕсть вопросы? Спрашивай!",
            reply_markup=MAIN_KEYBOARD
        )
        return CHAT

    if text == "📞 Связаться":
        await update.message.reply_text(
            f"📞 Свяжитесь с менеджером:\n\nTelegram: {SPONSOR_USERNAME}\nТелефон: {SPONSOR_PHONE}",
            reply_markup=MAIN_KEYBOARD
        )
        return CHAT

    if text == "🛒 Купить продукт":
        text = "Хочу купить продукт Vertera, расскажи подробнее"
    elif text == "💼 Бизнес с Vertera":
        text = "Расскажи про бизнес-возможности Vertera"

    if user.id not in user_histories:
        user_histories[user.id] = []

    user_histories[user.id].append({"role": "user", "content": text})
    if len(user_histories[user.id]) > 20:
        user_histories[user.id] = user_histories[user.id][-20:]

    try:
        await update.message.chat.send_action("typing")
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + user_histories[user.id],
            max_tokens=500,
            temperature=0.7
        )
        reply = response.choices[0].message.content
        user_histories[user.id].append({"role": "assistant", "content": reply})

        if "анкету" in reply.lower():
            await update.message.reply_text(reply, reply_markup=ReplyKeyboardMarkup(
                [["✅ Да, заполнить анкету"], ["❌ Нет, продолжить общение"]],
                resize_keyboard=True
            ))
        else:
            await update.message.reply_text(reply, reply_markup=MAIN_KEYBOARD)

    except Exception as e:
        logger.error(f"GPT error: {e}")
        await update.message.reply_text(
            f"Извините, ошибка. Свяжитесь напрямую:\nTelegram: {SPONSOR_USERNAME}\nТелефон: {SPONSOR_PHONE}",
            reply_markup=MAIN_KEYBOARD
        )
    return CHAT

async def start_anketa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ Нет, продолжить общение":
        await update.message.reply_text("Хорошо, продолжаем! 😊", reply_markup=MAIN_KEYBOARD)
        return CHAT
    await update.message.reply_text(
        "Отлично! Анкета займёт 1 минуту 📝\n\n👤 Введите ваше имя и фамилию:",
        reply_markup=ReplyKeyboardRemove()
    )
    return ANKETA_NAME

async def anketa_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text
    await update.message.reply_text("📱 Введите ваш номер телефона:")
    return ANKETA_PHONE

async def anketa_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["phone"] = update.message.text
    await update.message.reply_text("🌍 Введите ваш город:")
    return ANKETA_CITY

async def anketa_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["city"] = update.message.text
    await update.message.reply_text("💡 Что вас интересует?", reply_markup=ReplyKeyboardMarkup(
        [["🛒 Интересует продукт", "💼 Интересует бизнес"], ["🌿 И то и другое"]],
        resize_keyboard=True
    ))
    return ANKETA_INTEREST

async def anketa_interest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    context.user_data["interest"] = update.message.text

    name = context.user_data.get("name", "—")
    phone = context.user_data.get("phone", "—")
    city = context.user_data.get("city", "—")
    interest = context.user_data.get("interest", "—")
    username = f"@{user.username}" if user.username else str(user.id)

    try:
        async with httpx.AsyncClient() as http_client:
            await http_client.post(GOOGLE_SHEET_URL, json={
                "name": name, "phone": phone, "city": city,
                "interest": interest, "source": "Telegram Bot", "username": username
            }, timeout=10)
    except Exception as e:
        logger.error(f"Sheets error: {e}")

    try:
        await context.bot.send_message(
            chat_id="@tach_ttt",
            text=f"📥 Новая заявка Vertera!\n\n👤 {name}\n📱 {phone}\n🌍 {city}\n💡 {interest}\n🆔 {username}"
        )
    except Exception as e:
        logger.error(f"Sponsor notify error: {e}")

    await update.message.reply_text(
        "✅ Заявка принята!\n\nМенеджер свяжется с вами в ближайшее время 🌿\n\n"
        f"Или сами: Telegram {SPONSOR_USERNAME} / {SPONSOR_PHONE}",
        reply_markup=MAIN_KEYBOARD
    )
    return CHAT

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHAT: [
                MessageHandler(filters.Regex("^✅ Да, заполнить анкету$"), start_anketa),
                MessageHandler(filters.Regex("^❌ Нет, продолжить общение$"), start_anketa),
                MessageHandler(filters.TEXT & ~filters.COMMAND, chat_with_gpt),
            ],
            ANKETA_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, anketa_name)],
            ANKETA_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, anketa_phone)],
            ANKETA_CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, anketa_city)],
            ANKETA_INTEREST: [MessageHandler(filters.TEXT & ~filters.COMMAND, anketa_interest)],
        },
        fallbacks=[CommandHandler("start", start)],
        allow_reentry=True
    )
    app.add_handler(conv)
    logger.info("🤖 Vertera bot started!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
