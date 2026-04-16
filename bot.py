
# (Shortened header imports unchanged)
import os
import logging
import httpx
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler
)
from openai import OpenAI

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GOOGLE_SHEET_URL = os.getenv("GOOGLE_SHEET_URL", "")

SPONSOR_USERNAME = "@tach_ttt"
SPONSOR_PHONE_TKM = "+99363327177"
SPONSOR_PHONE_UZB = "+99363327177"

client = OpenAI(api_key=OPENAI_API_KEY)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SELECT_COUNTRY, SELECT_LANG, CHAT, ANKETA_NAME, ANKETA_PHONE, ANKETA_CITY, ANKETA_INTEREST = range(7)
user_histories = {}

TEXTS = {
    "ru": {
        "welcome": "Добро пожаловать! 🌿",
        "buy": "🛒 Купить продукт",
        "business": "💼 Бизнес с Vertera",
        "catalog": "📖 Каталог",
        "contact": "📞 Связаться",
        "register_btn": "📋 Инструкция по регистрации",
        "anketa_yes": "✅ Да, заполнить анкету",
        "anketa_no": "❌ Нет, продолжить",
    }
}

def get_main_keyboard(lang):
    t = TEXTS[lang]
    return ReplyKeyboardMarkup(
        [[t["buy"], t["business"]],
         [t["catalog"], t["contact"]],
         ["🔙 Главная"]],
        resize_keyboard=True
    )

def get_phone(country):
    return SPONSOR_PHONE_TKM if country == "TKM" else SPONSOR_PHONE_UZB

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Выберите страну",
        reply_markup=ReplyKeyboardMarkup(
            [["🇹🇲 Туркменистан", "🇺🇿 Узбекистан"]],
            resize_keyboard=True))
    return SELECT_COUNTRY

async def select_country(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["country"] = "TKM"
    await update.message.reply_text("Выберите язык",
        reply_markup=ReplyKeyboardMarkup([["Русский"]], resize_keyboard=True))
    return SELECT_LANG

async def select_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["lang"] = "ru"
    await update.message.reply_text(TEXTS["ru"]["welcome"], reply_markup=get_main_keyboard("ru"))
    return CHAT

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    t = TEXTS["ru"]

    if text == "🔙 Главная":
        await update.message.reply_text(t["welcome"], reply_markup=get_main_keyboard("ru"))
        return CHAT

    if text == t["business"]:
        await update.message.reply_text(
            "💼 Бизнес с Vertera\n\n"
            "Это возможность зарабатывать, рекомендуя натуральные продукты.\n\n"
            "Вы начинаете с использования продукта, затем делитесь результатом и получаете доход.\n\n"
            "Выберите действие:",
            reply_markup=ReplyKeyboardMarkup(
                [
                    [t["anketa_yes"]],
                    [t["register_btn"]],
                    ["🔙 Главная"]
                ],
                resize_keyboard=True
            )
        )
        return CHAT

    if text == t["register_btn"]:
        await update.message.reply_text(
            "📋 Инструкция по регистрации:\n1. Перейдите по ссылке\n2. Заполните данные\n3. Получите ID",
            reply_markup=get_main_keyboard("ru")
        )
        return CHAT

    await update.message.reply_text("Напишите вопрос", reply_markup=get_main_keyboard("ru"))
    return CHAT

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            SELECT_COUNTRY: [MessageHandler(filters.TEXT, select_country)],
            SELECT_LANG: [MessageHandler(filters.TEXT, select_lang)],
            CHAT: [MessageHandler(filters.TEXT, chat)],
        },
        fallbacks=[CommandHandler("start", start)],
    )

    app.add_handler(conv)
    app.run_polling()

if __name__ == "__main__":
    main()
