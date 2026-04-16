import os
import logging
import httpx
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler
)
from openai import OpenAI

# ─── Настройки ───────────────────────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN", "7146960065:AAEncOXgBeMjvUFGoX0f1QGr1_bHIDdK3gQ")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GOOGLE_SHEET_URL = os.getenv("GOOGLE_SHEET_URL", "https://script.google.com/macros/s/AKfycbzqwkgp8nSXxtSN1VB16QObhcOgqY4ye45-_Xmpc9OgAQnhQLAdL3EcjcSSg8zz05c/exec")

SPONSOR_USERNAME = "@tach_ttt"
SPONSOR_PHONE = "+99363327177"
CATALOG_LINK = "https://t.me/Verteratkmbot/vertera_tkm"
REGISTER_LINK = "https://id.boss.vertera.org/register?ref=FEKMPTVL85&service=OS3_PARTNER"

client = OpenAI(api_key=OPENAI_API_KEY)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CHAT, ANKETA_NAME, ANKETA_PHONE, ANKETA_CITY, ANKETA_INTEREST = range(5)

SYSTEM_PROMPT = """Ты — Вера, профессиональный консультант компании VERTERA в Туркменистане. Ты глубоко знаешь продукты и бизнес компании.

═══════════════════════════════
О КОМПАНИИ VERTERA
═══════════════════════════════
Vertera — международная компания, основана в 2005 году. Производит натуральные продукты питания и косметику из морских бурых водорослей (ламинария и фукус), добываемых в Белом море (Россия). Миссия: заботиться о здоровье и повышать качество жизни людей во всём мире.

Факты о компании:
- 400 000+ активных партнёров
- 47 стран присутствия
- 40+ продуктов для здоровья и красоты
- 7 клинических исследований, подтвердивших эффективность гелей
- Сертификаты ISO 22000:2018, Halal, Kosher, Vegan Society
- Производство в России, Тверская область

Уникальность продуктов: водоросли на 100% идентичны по минеральному составу плазме крови человека. Содержат 140+ полезных веществ. Патентованные технологии Plasma Technology и PRO-MAX обеспечивают максимальную биодоступность — обычные водоросли усваиваются лишь на 10-15%, продукты Vertera — на максимум.

═══════════════════════════════
ОСНОВНЫЕ ПРОДУКТЫ
═══════════════════════════════

🟢 VERTERA GEL (Базовый гель из ламинарии)
— Детокс, иммунитет, ЖКТ, сердце и сосуды
— 6 клинических исследований
— Дозировка: 50-100 г/сут за 30 мин до еды
— pH 7.9, окислительно-восстановительный потенциал от -50
— Стартовая программа: 1-й месяц

🔵 VERTERA FORTE ORIGINAL (Ламинария + фукус + дигидрокверцетин)
— Усиленный детокс, антиоксидантная защита
— pH 8.5
— Стартовая программа: 1-й месяц

🔵 VERTERA FORTE со вкусами (Черная смородина, Вишня, Яблоко)
— С растительными адаптогенами (шиповник, эхинацея, солодка, элеутерококк)
— pH 5
— 2-й этап: курс 2-3-й месяц

💜 ANGIOLIVE ORIGINAL (Ламинария + фукус + экстракт красного винограда)
— Для здоровья сосудов, сердца, вен, профилактики варикоза
— Клинически доказанная эффективность
— 90 г/сут независимо от приёма пищи

🟡 PLASMA HOMEOFOOD (Ферментированный гидрогель Plasma)
— Новейшая биотехнология Plasma Technology
— Пребиотик, иммунитет, омоложение, антиоксидант
— 1 пауч-пакет в день

🟡 PLASMAX (Капсулы — лиофилизат)
— Аналог Plasma Homeofood в удобной форме
— 2 капсулы 2 раза в день

🟢 PRO-MAX LAMINARIA — водорослевое премиум-питание, повышенный йод (до 10 000 мкг), для утреннего приёма
🟣 PRO-MAX FUCUS — богат фукоиданом, для вечернего приёма, здоровье сосудов

👶 УМНЫЙ РЕБЁНОК (Smart Kid) — детское питание с гидролизатом ламинарии
— Для детей от 3 лет, вкусы: яблоко, банан, груша
— 140+ полезных веществ, суточная норма йода
— Одобрено НИИ детского питания

💊 ЛИОФИЛИЗАТЫ в капсулах: Vertera Gel, Vertera Forte, AngioLive — удобная форма для путешествий
— 3-4 капсулы утром и вечером за 30 мин до еды

🦴 ARTROPLAST — для здоровья суставов (хондроитин, глюкозамин)
🦴 HONDROFEROL — комплекс для суставов и связок

💊 FITO SOLUTION (5 комплексов): Antihelmix, Visionormix, Hepanormix, Balancemix, Arthronormix

🌿 VERTERA SENSATION — 8 натуральных активаторов иммунитета
🔥 SLEEP&SLIM BOOSTER — ночной жиросжигатель
💪 SPORT&POWER BOOSTER — для выработки тестостерона, мужская сила

💧 КОСМЕТИКА: Seaweed biomask for face, Thalasso spa gel (обёртывания), Seaweed body oil, Hydrate collagen, True Vision (тоник для глаз), AngioLive Mask

═══════════════════════════════
ОБРАЗОВАТЕЛЬНАЯ ПЛАТФОРМА
═══════════════════════════════
Международная Академия Гомеостаза VERTERA предлагает курсы:
- Курс «Талассонутрициология» — 256 учебных часов, диплом о профессиональной переподготовке
- Курс «Талассокосметология» — 256 часов, квалификация «Косметик-эстетист»
- Курс «Консультант по ЗОЖ» — 256 часов
- Курс «Детская нутрициология» — 20 часов
- Пакет 2 в 1 и 3 в 1 — максимальные компетенции

═══════════════════════════════
КАК КУПИТЬ / СТАТЬ ПАРТНЁРОМ
═══════════════════════════════
Покупка со скидкой: зарегистрировать личный кабинет → получить 30% скидку на всю продукцию.
Ссылка регистрации: https://id.boss.vertera.org/register?ref=FEKMPTVL85&service=OS3_PARTNER

Бизнес: рекомендовать продукт своему окружению → зарабатывать. Нужно попробовать самому — результат будет точно.
Первый шаг: регистрация и первый заказ.
Контакт спонсора: +99363327177 (Telegram: @tach_ttt)

═══════════════════════════════
ПРАВИЛА ОБЩЕНИЯ
═══════════════════════════════
- Отвечай дружелюбно, профессионально, по делу
- Отвечай на том языке, на котором пишет пользователь (русский или туркменский)
- Когда спрашивают о конкретном продукте — давай подробную информацию из базы знаний
- Если спрашивают цены — объясни что цены уточнит менеджер, так как зависят от страны и курса
- Когда чувствуешь что человек готов сделать заказ или узнать больше — предложи заполнить анкету фразой содержащей слово "анкету"
- Никогда не придумывай факты сверх того, что знаешь
- Ты консультант Vertera в Туркменистане — помогаешь людям улучшить здоровье и заработать
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
        "Я Вера — консультант компании *VERTERA* 🌿\n\n"
        "Производим натуральные продукты из морских водорослей с клинически доказанной эффективностью. "
        "Помогаю улучшить здоровье и создать дополнительный доход.\n\n"
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
            f"📖 Наш каталог продукции Vertera:\n{CATALOG_LINK}\n\nЕсть вопросы по продуктам? Спрашивай!",
            reply_markup=MAIN_KEYBOARD
        )
        return CHAT

    if text == "📞 Связаться":
        await update.message.reply_text(
            f"📞 Свяжитесь с нашим менеджером:\n\nTelegram: {SPONSOR_USERNAME}\nТелефон: {SPONSOR_PHONE}\n\nОтвечаем быстро! 🌿",
            reply_markup=MAIN_KEYBOARD
        )
        return CHAT

    if text == "🛒 Купить продукт":
        text = "Хочу купить продукт Vertera. Расскажи подробнее о продуктах и как сделать заказ со скидкой."
    elif text == "💼 Бизнес с Vertera":
        text = "Расскажи подробно про бизнес-возможности Vertera — как зарабатывать, первые шаги."

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
            max_tokens=600,
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
            f"Извините, произошла ошибка. Свяжитесь напрямую:\nTelegram: {SPONSOR_USERNAME}\nТелефон: {SPONSOR_PHONE}",
            reply_markup=MAIN_KEYBOARD
        )
    return CHAT

async def start_anketa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ Нет, продолжить общение":
        await update.message.reply_text("Хорошо, продолжаем! 😊 Задавайте любые вопросы.", reply_markup=MAIN_KEYBOARD)
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
                "interest": interest, "source": "Telegram Bot Vertera TKM", "username": username
            }, timeout=10)
    except Exception as e:
        logger.error(f"Sheets error: {e}")

    try:
        await context.bot.send_message(
            chat_id="@tach_ttt",
            text=(
                f"📥 Новая заявка Vertera TKM!\n\n"
                f"👤 {name}\n"
                f"📱 {phone}\n"
                f"🌍 {city}\n"
                f"💡 {interest}\n"
                f"🆔 {username}"
            )
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
    logger.info("🤖 Vertera TKM bot started!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
