import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_USERNAME = "@tach_ttt"
ADMIN_PHONE = "+99363327177"
REGISTER_LINK = "https://id.boss.vertera.org/register?ref=FEKMPTVL85&service=OS3_PARTNER"
CATALOG_LINK = "https://tach-ttt.github.io/vertera-shop/"  # замени на свою ссылку GitHub Pages

# ─── KEYBOARDS ────────────────────────────────────────────

def kb_main():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 Хочу купить продукт", callback_data="buy")],
        [InlineKeyboardButton("💼 Хочу строить бизнес", callback_data="business")],
        [InlineKeyboardButton("📖 Каталог продукции", callback_data="catalog")],
        [InlineKeyboardButton("📞 Связаться с менеджером", callback_data="contact")],
    ])

def kb_buy():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Как получить скидку 30%", callback_data="discount")],
        [InlineKeyboardButton("📦 Как сделать первый заказ", callback_data="first_order")],
        [InlineKeyboardButton("📖 Каталог продукции", callback_data="catalog")],
        [InlineKeyboardButton("📞 Позвонить менеджеру", callback_data="contact")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="start")],
    ])

def kb_business():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 Стать партнёром", url=REGISTER_LINK)],
        [InlineKeyboardButton("💰 Как зарабатывать", callback_data="earn")],
        [InlineKeyboardButton("👣 Первые шаги партнёра", callback_data="first_steps")],
        [InlineKeyboardButton("📞 Написать наставнику", callback_data="contact")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="start")],
    ])

def kb_back():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ На главную", callback_data="start")],
    ])

def kb_contact():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💬 Написать в Telegram", url=f"https://t.me/tach_ttt")],
        [InlineKeyboardButton("📞 Позвонить", url=f"tel:{ADMIN_PHONE}")],
        [InlineKeyboardButton("⬅️ На главную", callback_data="start")],
    ])

# ─── TEXTS ────────────────────────────────────────────────

TEXTS = {
    "start": (
        "🌿 *Добро пожаловать в Vertera!*\n\n"
        "Мы производим натуральные продукты на основе морских водорослей "
        "для здоровья, красоты и долголетия.\n\n"
        "Выбери, что тебя интересует 👇"
    ),
    "buy": (
        "🛒 *Хочу купить продукт*\n\n"
        "Отличный выбор! У нас есть продукты для:\n"
        "• Детокса и иммунитета\n"
        "• Суставов и сосудов\n"
        "• Красоты и косметики\n"
        "• Детского питания\n\n"
        "Что тебя интересует? 👇"
    ),
    "discount": (
        "🎁 *Скидка 30% на всю продукцию*\n\n"
        "Чтобы покупать продукцию Vertera со скидкой *30%*, нужно:\n\n"
        "1️⃣ Зарегистрировать личный кабинет в компании\n"
        "2️⃣ Получить статус клиента\n"
        "3️⃣ Делать заказы по партнёрской цене\n\n"
        "Это *бесплатно* и занимает 5 минут!\n\n"
        "📞 Напишите нам — мы поможем зарегистрироваться и сделать первый заказ."
    ),
    "first_order": (
        "📦 *Как сделать первый заказ*\n\n"
        "Всё очень просто:\n\n"
        "1️⃣ Свяжитесь с нашим менеджером\n"
        "2️⃣ Выберите продукты из каталога\n"
        "3️⃣ Зарегистрируйте личный кабинет (получите скидку 30%)\n"
        "4️⃣ Оформите и оплатите заказ\n"
        "5️⃣ Получите продукцию!\n\n"
        f"📞 Позвоните или напишите: *{ADMIN_PHONE}*"
    ),
    "catalog": (
        "📖 *Каталог продукции Vertera*\n\n"
        "В нашем каталоге вы найдёте:\n"
        "• 🌿 Гели на основе ламинарии\n"
        "• 👶 Детское питание\n"
        "• ✨ Косметика Plasma Therapy\n"
        "• 💪 ArtroPlast для суставов\n\n"
        "Нажмите кнопку ниже, чтобы открыть каталог 👇"
    ),
    "business": (
        "💼 *Бизнес с Vertera*\n\n"
        "Vertera — это возможность построить собственный бизнес "
        "на рекомендации натуральных продуктов, которые реально работают.\n\n"
        "Выбери, что тебя интересует 👇"
    ),
    "earn": (
        "💰 *Как зарабатывать с Vertera*\n\n"
        "Всё основано на *личном результате*:\n\n"
        "1️⃣ Попробуй продукт сам — получи результат\n"
        "2️⃣ Рекомендуй своему окружению\n"
        "3️⃣ Люди покупают через твой кабинет — ты получаешь доход\n\n"
        "💡 Чем больше людей ты приводишь — тем выше твой статус и доход.\n\n"
        "Это не продажи — это *рекомендации* тому, кому действительно нужна помощь."
    ),
    "first_steps": (
        "👣 *Первые шаги партнёра Vertera*\n\n"
        "Всего 3 шага:\n\n"
        "1️⃣ *Регистрация* — пройди по ссылке ниже и создай личный кабинет партнёра\n\n"
        "2️⃣ *Первый заказ* — позвони или напиши менеджеру, сделай первый заказ и попробуй продукт\n\n"
        "3️⃣ *Результат* — используй продукт, получи результат и начни рекомендовать\n\n"
        f"📞 Контакт: *{ADMIN_PHONE}*\n\n"
        "👇 Нажми кнопку, чтобы зарегистрироваться"
    ),
    "contact": (
        "📞 *Связаться с менеджером*\n\n"
        "Мы всегда рады ответить на ваши вопросы!\n\n"
        f"💬 Telegram: *{ADMIN_USERNAME}*\n"
        f"📱 Телефон: *{ADMIN_PHONE}*\n\n"
        "Нажмите кнопку ниже 👇"
    ),
}

# ─── HANDLERS ─────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    # Notify admin about new user
    try:
        await context.bot.send_message(
            chat_id=ADMIN_USERNAME,
            text=f"🔔 *Новый пользователь!*\n"
                 f"👤 Имя: {user.full_name}\n"
                 f"🔗 Username: @{user.username or 'нет'}\n"
                 f"🆔 ID: {user.id}",
            parse_mode="Markdown"
        )
    except Exception:
        pass

    await update.message.reply_text(
        TEXTS["start"],
        parse_mode="Markdown",
        reply_markup=kb_main()
    )

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user = update.effective_user

    if data == "start":
        await query.edit_message_text(
            TEXTS["start"], parse_mode="Markdown", reply_markup=kb_main()
        )

    elif data == "buy":
        await query.edit_message_text(
            TEXTS["buy"], parse_mode="Markdown", reply_markup=kb_buy()
        )

    elif data == "business":
        await query.edit_message_text(
            TEXTS["business"], parse_mode="Markdown", reply_markup=kb_business()
        )

    elif data == "discount":
        await query.edit_message_text(
            TEXTS["discount"], parse_mode="Markdown", reply_markup=kb_contact()
        )

    elif data == "first_order":
        await query.edit_message_text(
            TEXTS["first_order"], parse_mode="Markdown", reply_markup=kb_contact()
        )

    elif data == "catalog":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🌿 Открыть каталог", url=CATALOG_LINK)],
            [InlineKeyboardButton("⬅️ На главную", callback_data="start")],
        ])
        await query.edit_message_text(
            TEXTS["catalog"], parse_mode="Markdown", reply_markup=kb
        )

    elif data == "earn":
        await query.edit_message_text(
            TEXTS["earn"], parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🚀 Зарегистрироваться", url=REGISTER_LINK)],
                [InlineKeyboardButton("📞 Написать наставнику", callback_data="contact")],
                [InlineKeyboardButton("⬅️ Назад", callback_data="business")],
            ])
        )

    elif data == "first_steps":
        await query.edit_message_text(
            TEXTS["first_steps"], parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🚀 Зарегистрироваться партнёром", url=REGISTER_LINK)],
                [InlineKeyboardButton("📞 Написать менеджеру", callback_data="contact")],
                [InlineKeyboardButton("⬅️ Назад", callback_data="business")],
            ])
        )

    elif data == "contact":
        # Notify admin that someone wants to contact
        try:
            await context.bot.send_message(
                chat_id=ADMIN_USERNAME,
                text=f"🔥 *Горячий лид!*\n"
                     f"👤 {user.full_name}\n"
                     f"🔗 @{user.username or 'нет'}\n"
                     f"📱 Хочет связаться с менеджером",
                parse_mode="Markdown"
            )
        except Exception:
            pass
        await query.edit_message_text(
            TEXTS["contact"], parse_mode="Markdown", reply_markup=kb_contact()
        )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Используй кнопки меню для навигации.\n"
        "Нажми /start чтобы начать заново.",
        reply_markup=kb_main()
    )

# ─── MAIN ─────────────────────────────────────────────────

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Bot started...")
    app.run_polling()

if __name__ == "__main__":
    main()
