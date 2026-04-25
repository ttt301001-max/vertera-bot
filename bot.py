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
MANAGER_CHAT_ID = 699255285  # @tach_ttt
SPONSOR_PHONE_TKM = "+99363327177"
SPONSOR_PHONE_UZB = "+99363327177"
CATALOG_LINK = "https://t.me/Verteratkmbot/vertera_tkm"
REGISTER_LINK = "https://id.boss.vertera.org/register?ref=FEKMPTVL85&service=OS3_PARTNER"

client = OpenAI(api_key=OPENAI_API_KEY)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── Состояния ───────────────────────────────────────────────
SELECT_COUNTRY, SELECT_LANG, CHAT, ANKETA_NAME, ANKETA_PHONE, ANKETA_CITY, ANKETA_INTEREST, PARTNER_ID, PARTNER_MENU, PARTNER_CONTACTS_NAME, PARTNER_CONTACTS_PHONE = range(12)

user_histories = {}

# ─── Партнёрский раздел ──────────────────────────────────────
import json, pathlib

PARTNERS_FILE = pathlib.Path("/tmp/vertera_partners.json")

def partners_load() -> dict:
    """Загружает одобренных партнёров {user_id: {name, company_id, lang}}"""
    try:
        if PARTNERS_FILE.exists():
            return json.loads(PARTNERS_FILE.read_text())
    except Exception as e:
        logger.error(f"partners_load: {e}")
    return {}

def partners_save(data: dict):
    try:
        PARTNERS_FILE.write_text(json.dumps(data, ensure_ascii=False))
    except Exception as e:
        logger.error(f"partners_save: {e}")

def partner_add(user_id: int, name: str, company_id: str, lang: str):
    data = partners_load()
    data[str(user_id)] = {"name": name, "company_id": company_id, "lang": lang}
    partners_save(data)

def partner_remove(user_id: int):
    data = partners_load()
    data.pop(str(user_id), None)
    partners_save(data)

def is_partner(user_id: int) -> bool:
    return str(user_id) in partners_load()

def get_all_partners() -> dict:
    return partners_load()

# Pending requests {user_id: {name, company_id, lang, tg_username}}
PENDING_FILE = pathlib.Path("/tmp/vertera_pending.json")

def pending_load() -> dict:
    try:
        if PENDING_FILE.exists():
            return json.loads(PENDING_FILE.read_text())
    except Exception as e:
        logger.error(f"pending_load: {e}")
    return {}

def pending_save(data: dict):
    try:
        PENDING_FILE.write_text(json.dumps(data, ensure_ascii=False))
    except Exception as e:
        logger.error(f"pending_save: {e}")

def pending_add(user_id: int, info: dict):
    data = pending_load()
    data[str(user_id)] = info
    pending_save(data)

def pending_get(user_id: int) -> dict:
    return pending_load().get(str(user_id), {})

def pending_remove(user_id: int):
    data = pending_load()
    data.pop(str(user_id), None)
    pending_save(data)

# Contacts {partner_user_id: [{name, phone, status, note}]}
CONTACTS_FILE = pathlib.Path("/tmp/vertera_contacts.json")

def contacts_load(partner_id: int) -> list:
    try:
        if CONTACTS_FILE.exists():
            all_c = json.loads(CONTACTS_FILE.read_text())
            return all_c.get(str(partner_id), [])
    except Exception as e:
        logger.error(f"contacts_load: {e}")
    return []

def contacts_save_all(data: dict):
    try:
        CONTACTS_FILE.write_text(json.dumps(data, ensure_ascii=False))
    except Exception as e:
        logger.error(f"contacts_save: {e}")

def contact_add(partner_id: int, name: str, phone: str):
    try:
        all_c = {}
        if CONTACTS_FILE.exists():
            all_c = json.loads(CONTACTS_FILE.read_text())
        lst = all_c.get(str(partner_id), [])
        lst.append({"name": name, "phone": phone, "status": "новый"})
        all_c[str(partner_id)] = lst
        contacts_save_all(all_c)
    except Exception as e:
        logger.error(f"contact_add: {e}")

# Тексты партнёрского раздела
PARTNER_TEXTS = {
    "ru": {
        "btn":        "🤝 Я партнёр",
        "ask_id":     "🤝 Введите ваш ID из личного кабинета Vertera:",
        "wait":       "✅ Запрос отправлен! Ожидайте одобрения от администратора.",
        "approved":   "🎉 Вы одобрены как партнёр Vertera! Добро пожаловать в команду 🌿",
        "rejected":   "❌ Ваш запрос отклонён. Обратитесь к менеджеру: @tach_ttt",
        "menu_title": "🤝 Партнёрское меню",
        "btn_learn":  "📚 Обучение",
        "btn_market": "📊 Маркетинг",
        "btn_calc":   "🧮 Калькулятор дохода",
        "btn_contacts":"👥 Мои контакты",
        "btn_news":   "📣 Новости",
        "btn_back":   "🔙 Выйти из партнёрского меню",
        "learn_text": (
            "📚 *Обучение партнёра*\n\n"
            "*Шаг 1 — Изучи продукт*\n"
            "Попробуй все продукты сам. Только личный опыт убеждает.\n\n"
            "*Шаг 2 — Изучи систему*\n"
            "БЗП → Клубный бонус → КББ → БЗК\n"
            "Нажми «📊 Маркетинг» для подробного разбора.\n\n"
            "*Шаг 3 — Первые шаги*\n"
            "• Составь список из 20 знакомых\n"
            "• Расскажи о продукте 5 из них\n"
            "• Пригласи 2 в команду (левая и правая ветка)\n\n"
            "*Шаг 4 — Сопровождение*\n"
            "Добавляй клиентов в «👥 Мои контакты» и следи за их статусом 🌿"
        ),
        "market_text": (
            "📊 *Маркетинг Vertera*\n\n"
            "У вас 4 бонуса с первых дней:\n\n"
            "1️⃣ *БЗП* — 40% с покупки партнёра\n"
            "2️⃣ *Клубный бонус* — 55 или 110 UE за объём первой линии\n"
            "3️⃣ *КББ* — за каждый цикл 40+40 PV в ветках\n"
            "4️⃣ *БЗК* — разовая выплата за новый статус\n\n"
            "1 UE = 15 манат (TKM) / 10 000 сум (UZB)\n\n"
            "Задай вопрос боту — он объяснит любой бонус подробно 🌿"
        ),
        "calc_ask":   "🧮 Введите количество активных партнёров в вашей команде:",
        "contacts_empty": "👥 У вас пока нет контактов. Добавьте первого!",
        "contacts_add":   "➕ Добавить контакт",
        "contacts_ask_name": "👤 Введите имя контакта:",
        "contacts_ask_phone": "📞 Введите телефон контакта:",
        "contacts_saved": "✅ Контакт добавлен!",
        "news_text":  "📣 Новостей пока нет. Следите за обновлениями 🌿",
    },
    "tk": {
        "btn":        "🤝 Men hyzmatdaş",
        "ask_id":     "🤝 Vertera şahsy kabinetindäki ID-ňizi giriziň:",
        "wait":       "✅ Isleg iberildi! Administratoryň tassyklamagyna garaşyň.",
        "approved":   "🎉 Siz Vertera hyzmatdaşy hökmünde tassyklandyňyz! Topara hoş geldiňiz 🌿",
        "rejected":   "❌ Ýüz tutmanyňyz ret edildi. Menejer bilen habarlaşyň: @tach_ttt",
        "menu_title": "🤝 Hyzmatdaş menýusy",
        "btn_learn":  "📚 Okuw",
        "btn_market": "📊 Marketing",
        "btn_calc":   "🧮 Girdeji kalkulýatory",
        "btn_contacts":"👥 Meniň kontaktlarym",
        "btn_news":   "📣 Habarlar",
        "btn_back":   "🔙 Hyzmatdaş menýusyndan çyk",
        "learn_text": (
            "📚 *Hyzmatdaş okuwы*\n\n"
            "*Ädim 1 — Önümi öwren*\n"
            "Ähli önümleri özüň synap gör. Diňe şahsy tejribe ynandyrýar.\n\n"
            "*Ädim 2 — Ulgamy öwren*\n"
            "BZP → Klub bonusy → KBB → BZK\n"
            "Jikme-jik syn üçin «📊 Marketing» basyň.\n\n"
            "*Ädim 3 — Ilkinji ädimler*\n"
            "• 20 tanşyň sanawyny düz\n"
            "• Olaryň 5-ine önüm barada aýt\n"
            "• 2-sini topara çagyr (çep we sag şaha)\n\n"
            "*Ädim 4 — Goldaw*\n"
            "Müşderileri «👥 Meniň kontaktlarym»-a goş 🌿"
        ),
        "market_text": (
            "📊 *Vertera marketingi*\n\n"
            "Ilkinji günlerden 4 bonusyňyz bar:\n\n"
            "1️⃣ *BZP* — hyzmatdaşyň satyn alşyndan 40%\n"
            "2️⃣ *Klub bonusy* — birinji liniýanyň göwrümi üçin 55 ýa-da 110 UE\n"
            "3️⃣ *KBB* — şahalarda 40+40 PV her sikl üçin\n"
            "4️⃣ *BZK* — täze statusa ýetmek üçin bir gezek töleg\n\n"
            "1 UE = 15 manat (TKM) / 10 000 sum (UZB)\n\n"
            "Bota sorag ber — islendik bonusy düşündirer 🌿"
        ),
        "calc_ask":   "🧮 Toparyňyzdaky işjeň hyzmatdaşlaryň sanyny giriziň:",
        "contacts_empty": "👥 Heniz kontaktyňyz ýok. Birinjisini goşuň!",
        "contacts_add":   "➕ Kontakt goş",
        "contacts_ask_name": "👤 Kontaktyň adyny giriziň:",
        "contacts_ask_phone": "📞 Kontaktyň telefonyny giriziň:",
        "contacts_saved": "✅ Kontakt goşuldy!",
        "news_text":  "📣 Häzirlik habar ýok. Täzelenmeleri yzarlaň 🌿",
    },
    "uz": {
        "btn":        "🤝 Men hamkorman",
        "ask_id":     "🤝 Vertera shaxsiy kabinetingizdagi ID-ni kiriting:",
        "wait":       "✅ So'rov yuborildi! Administrator tasdiqlashini kuting.",
        "approved":   "🎉 Siz Vertera hamkori sifatida tasdiqlandi! Jamoaga xush kelibsiz 🌿",
        "rejected":   "❌ So'rovingiz rad etildi. Menejer bilan bog'laning: @tach_ttt",
        "menu_title": "🤝 Hamkorlik menyusi",
        "btn_learn":  "📚 O'qitish",
        "btn_market": "📊 Marketing",
        "btn_calc":   "🧮 Daromad kalkulyatori",
        "btn_contacts":"👥 Mening kontaktlarim",
        "btn_news":   "📣 Yangiliklar",
        "btn_back":   "🔙 Hamkorlik menyusidan chiqish",
        "learn_text": (
            "📚 *Hamkor o'qitish*\n\n"
            "*Qadam 1 — Mahsulotni o'rgan*\n"
            "Barcha mahsulotlarni o'zing sinab ko'r. Faqat shaxsiy tajriba ishontiradi.\n\n"
            "*Qadam 2 — Tizimni o'rgan*\n"
            "BZP → Klub bonusi → KBB → BZK\n"
            "Batafsil uchun «📊 Marketing» tugmasini bosing.\n\n"
            "*Qadam 3 — Birinchi qadamlar*\n"
            "• 20 tanishingizdan ro'yxat tuzing\n"
            "• Ulardan 5 tasiga mahsulot haqida ayting\n"
            "• 2 tasini jamoaga taklif qiling (chap va o'ng tarmoq)\n\n"
            "*Qadam 4 — Qo'llab-quvvatlash*\n"
            "Mijozlarni «👥 Mening kontaktlarim»ga qo'shing 🌿"
        ),
        "market_text": (
            "📊 *Vertera marketingi*\n\n"
            "Birinchi kunlardan 4 ta bonusingiz bor:\n\n"
            "1️⃣ *BZP* — hamkorning xarididan 40%\n"
            "2️⃣ *Klub bonusi* — birinchi liniya hajmi uchun 55 yoki 110 UE\n"
            "3️⃣ *KBB* — tarmoqlarda 40+40 PV har sikl uchun\n"
            "4️⃣ *BZK* — yangi statusga erishganda bir martalik to'lov\n\n"
            "1 UE = 15 manat (TKM) / 10 000 so'm (UZB)\n\n"
            "Botga savol ber — istalgan bonusni tushuntiradi 🌿"
        ),
        "calc_ask":   "🧮 Jamoangizdagi faol hamkorlar sonini kiriting:",
        "contacts_empty": "👥 Hali kontaktingiz yo'q. Birinchisini qo'shing!",
        "contacts_add":   "➕ Kontakt qo'shish",
        "contacts_ask_name": "👤 Kontakt ismini kiriting:",
        "contacts_ask_phone": "📞 Kontakt telefonini kiriting:",
        "contacts_saved": "✅ Kontakt qo'shildi!",
        "news_text":  "📣 Hozircha yangilik yo'q. Yangilanishlarni kuzating 🌿",
    },
}

def get_partner_keyboard(lang: str):
    pt = PARTNER_TEXTS[lang]
    return ReplyKeyboardMarkup(
        [
            [pt["btn_learn"],   pt["btn_market"]],
            [pt["btn_calc"],    pt["btn_contacts"]],
            [pt["btn_news"]],
            [pt["btn_back"]],
        ],
        resize_keyboard=True
    )


# ─── Тексты на разных языках ─────────────────────────────────
TEXTS = {
    "ru": {
        "welcome": "Добро пожаловать! 🌿\nЯ Вера — консультант компании *VERTERA*.\n\nПомогаю улучшить здоровье и создать дополнительный доход с помощью натуральных продуктов из морских водорослей.\n\nЧем могу помочь?",
        "buy": "🛒 Купить продукт",
        "business": "💼 Бизнес с Vertera",
        "catalog": "📖 Каталог",
        "contact": "📞 Связаться",
        "home": "🔙 Главная",
        "register_btn": "📋 Инструкция по регистрации",
        "catalog_text": "📖 Наш каталог продукции Vertera:\n{catalog_link}\n\nЕсть вопросы по продуктам? Спрашивай!",
        "contact_text": "📞 Свяжитесь с нашим менеджером:\n\nTelegram: {sponsor}\nТелефон: {phone}\n\nОтвечаем быстро! 🌿",
        "error_text": "Извините, произошла ошибка. Свяжитесь напрямую:\nTelegram: {sponsor}\nТелефон: {phone}",
        "anketa_yes": "✅ Да, заполнить анкету",
        "anketa_no": "❌ Нет, продолжить общение",
        "anketa_ok": "Хорошо, продолжаем! 😊 Задавайте любые вопросы.",
        "anketa_start": "Отлично! Анкета займёт 1 минуту 📝\n\n👤 Введите ваше имя и фамилию:",
        "anketa_phone": "📱 Введите ваш номер телефона:",
        "anketa_city": "🌍 Введите ваш город:",
        "anketa_interest": "💡 Что вас интересует?",
        "interest_product": "🛒 Интересует продукт",
        "interest_business": "💼 Интересует бизнес",
        "interest_both": "🌿 И то и другое",
        "anketa_done": "✅ Заявка принята!\n\nМенеджер свяжется с вами в ближайшее время 🌿\n\nИли сами: Telegram {sponsor} / {phone}",
    },
    "tk": {
        "welcome": "Hoş geldiňiz! 🌿\nMen Wera — *VERTERA* kompaniýasynyň maslahatçysy.\n\nDeňiz ösümliklerinden ýasalan tebigy önümler arkaly saglyk we goşmaça girdeji almaga kömek edýärin.\n\nSize nädip kömek edip bilerin?",
        "buy": "🛒 Önüm satyn almak",
        "business": "💼 Vertera bilen iş",
        "catalog": "📖 Katalog",
        "contact": "📞 Habarlaşmak",
        "home": "🔙 Baş sahypa",
        "register_btn": "📋 Hasaba alyş görkezmeleri",
        "catalog_text": "📖 Vertera önümlerimiziň katalogy:\n{catalog_link}\n\nÖnümler barada soraglaryňyz barmy? Soraň!",
        "contact_text": "📞 Menejerimiz bilen habarlaşyň:\n\nTelegram: {sponsor}\nTelefon: {phone}\n\nTiz jogap berýäris! 🌿",
        "error_text": "Ötünç soraýaryn, ýalňyşlyk ýüze çykdy. Göni habarlaşyň:\nTelegram: {sponsor}\nTelefon: {phone}",
        "anketa_yes": "✅ Hawa, anketa doldurmak",
        "anketa_no": "❌ Ýok, gürrüňdeşligi dowam etmek",
        "anketa_ok": "Bolýar, dowam edýäris! 😊 Islendik sorag beriň.",
        "anketa_start": "Ajaýyp! Anketa 1 minut alar 📝\n\n👤 Adyňyzy we familýaňyzy giriziň:",
        "anketa_phone": "📱 Telefon belgiňizi giriziň:",
        "anketa_city": "🌍 Şäheriňizi giriziň:",
        "anketa_interest": "💡 Sizi näme gyzyklandyrýar?",
        "interest_product": "🛒 Önüm gyzyklandyrýar",
        "interest_business": "💼 Iş gyzyklandyrýar",
        "interest_both": "🌿 Ikisi hem",
        "anketa_done": "✅ Arza kabul edildi!\n\nMenjerimiz ýakyn wagtda siz bilen habarlaşar 🌿\n\nÝa-da özüňiz: Telegram {sponsor} / {phone}",
    },
    "uz": {
        "welcome": "Xush kelibsiz! 🌿\nMen Vera — *VERTERA* kompaniyasining maslahatchisi.\n\nDengiz o'tlaridan tayyorlangan tabiiy mahsulotlar orqali sog'liq va qo'shimcha daromad olishga yordam beraman.\n\nQanday yordam bera olaman?",
        "buy": "🛒 Mahsulot sotib olish",
        "business": "💼 Vertera bilan biznes",
        "catalog": "📖 Katalog",
        "contact": "📞 Bog'lanish",
        "home": "🔙 Bosh sahifa",
        "register_btn": "📋 Ro'yxatdan o'tish",
        "catalog_text": "📖 Vertera mahsulotlari katalogi:\n{catalog_link}\n\nMahsulotlar haqida savollaringiz bormi? So'rang!",
        "contact_text": "📞 Menejerimiz bilan bog'laning:\n\nTelegram: {sponsor}\nTelefon: {phone}\n\nTez javob beramiz! 🌿",
        "error_text": "Kechirasiz, xatolik yuz berdi. To'g'ridan-to'g'ri bog'laning:\nTelegram: {sponsor}\nTelefon: {phone}",
        "anketa_yes": "✅ Ha, anketa to'ldirish",
        "anketa_no": "❌ Yo'q, suhbatni davom ettirish",
        "anketa_ok": "Yaxshi, davom etamiz! 😊 Istalgan savolni bering.",
        "anketa_start": "Ajoyib! Anketa 1 daqiqa oladi 📝\n\n👤 Ism va familiyangizni kiriting:",
        "anketa_phone": "📱 Telefon raqamingizni kiriting:",
        "anketa_city": "🌍 Shahringizni kiriting:",
        "anketa_interest": "💡 Sizni nima qiziqtiradi?",
        "interest_product": "🛒 Mahsulot qiziqtiradi",
        "interest_business": "💼 Biznes qiziqtiradi",
        "interest_both": "🌿 Ikkalasi ham",
        "anketa_done": "✅ Ariza qabul qilindi!\n\nMenejerimiz yaqin orada siz bilan bog'lanadi 🌿\n\nYoki o'zingiz: Telegram {sponsor} / {phone}",
    }
}

# ─── Инструкции по регистрации ───────────────────────────────
REG_INSTRUCTIONS = {
    "TKM": {
        "ru": (
            "📋 *Инструкция по регистрации (Туркменистан):*\n\n"
            "1️⃣ Перейдите по ссылке:\n{link}\n\n"
            "2️⃣ Заполните все поля формы\n\n"
            "3️⃣ Нажмите кнопку *«Зарегистрироваться»*\n\n"
            "4️⃣ На следующем шаге нажмите *«Пропустить»*\n\n"
            "5️⃣ На шаге с почтой тоже нажмите *«Пропустить»*\n\n"
            "6️⃣ Подождите *10 секунд* — появится кнопка, нажмите на неё\n\n"
            "7️⃣ Вы получите свой личный *ID-номер* 🎉\n\n"
            "8️⃣ Нажмите *«На главную»* — вы попадёте на страницу входа в личный кабинет\n\n"
            "Если возникнут трудности — напишите нам: {sponsor}"
        ),
        "tk": (
            "📋 *Hasaba alyş görkezmeleri (Türkmenistan):*\n\n"
            "1️⃣ Şu salga geçiň:\n{link}\n\n"
            "2️⃣ Formdaky ähli meýdançalary dolduryň\n\n"
            "3️⃣ *«Hasaba alyş»* düwmesine basyň\n\n"
            "4️⃣ Indiki ädimde *«Geçirmek»* düwmesine basyň\n\n"
            "5️⃣ Poçta ädiminde hem *«Geçirmek»* düwmesine basyň\n\n"
            "6️⃣ *10 sekunt* garaşyň — düwme peýda bolar, basyň\n\n"
            "7️⃣ Şahsy *ID belgiňizi* alarsyňyz 🎉\n\n"
            "8️⃣ *«Baş sahypa»* düwmesine basyň — şahsy otaga giriş sahypasyna geçersiňiz\n\n"
            "Kynçylyk çeksеňiz — bize ýazyň: {sponsor}"
        ),
    },
    "UZB": {
        "ru": (
            "📋 *Инструкция по регистрации (Узбекистан):*\n\n"
            "1️⃣ Перейдите по ссылке:\n{link}\n\n"
            "2️⃣ Заполните все поля формы\n\n"
            "3️⃣ Нажмите кнопку *«Зарегистрироваться»*\n\n"
            "4️⃣ Дождитесь *SMS с кодом* на ваш номер телефона\n\n"
            "5️⃣ Введите код из SMS\n\n"
            "6️⃣ Вы получите свой личный *ID-номер* 🎉\n\n"
            "7️⃣ Войдите в личный кабинет по номеру телефона\n\n"
            "Если возникнут трудности — напишите нам: {sponsor}"
        ),
        "uz": (
            "📋 *Ro'yxatdan o'tish ko'rsatmalari (O'zbekiston):*\n\n"
            "1️⃣ Quyidagi havolaga o'ting:\n{link}\n\n"
            "2️⃣ Formadagi barcha maydonlarni to'ldiring\n\n"
            "3️⃣ *«Ro'yxatdan o'tish»* tugmasini bosing\n\n"
            "4️⃣ Telefon raqamingizga *SMS-kod* kelishini kuting\n\n"
            "5️⃣ SMS-dan kodni kiriting\n\n"
            "6️⃣ Shaxsiy *ID-raqamingizni* olasiz 🎉\n\n"
            "7️⃣ Telefon raqami orqali shaxsiy kabinetga kiring\n\n"
            "Qiyinchilik bo'lsa — bizga yozing: {sponsor}"
        ),
    }
}

# ─── Системный промпт GPT ────────────────────────────────────
def get_system_prompt(country: str, lang: str) -> str:
    country_name = "Туркменистан" if country == "TKM" else "Узбекистан"
    lang_instruction = {
        "ru": "Отвечай ТОЛЬКО на русском языке.",
        "tk": "Diňe türkmen dilinde jogap ber. (Отвечай только на туркменском)",
        "uz": "Faqat o'zbek tilida javob ber. (Отвечай только на узбекском)",
    }.get(lang, "Отвечай на русском языке.")

    return f"""Ты — Вера, профессиональный консультант компании VERTERA в {country_name}. {lang_instruction}

═══════════════════════════════
О КОМПАНИИ VERTERA
═══════════════════════════════
Vertera — международная компания, основана в 2005 году. Производит натуральные продукты и косметику из морских бурых водорослей. Миссия: заботиться о здоровье и повышать качество жизни людей во всём мире.
- 400 000+ активных партнёров, 47 стран, 40+ продуктов
- 7 клинических исследований
- Сертификаты ISO 22000:2018, Halal, Kosher, Vegan

Уникальность: состав водорослей идентичен плазме крови человека на 100% по минеральному составу. Патентованная технология Plasma Technology обеспечивает максимальную биодоступность веществ.

═══════════════════════════════
ПРОДУКТЫ VERTERA
═══════════════════════════════

🟢 VERTERA GEL — гель из ламинарии
— Детокс, иммунитет, ЖКТ, сердце и сосуды
— 6 клинических исследований, pH 7.9
— 50-100 г/сут за 30 мин до еды

🔵 VERTERA FORTE ORIGINAL — ламинария + фукус + дигидрокверцетин
— Усиленный детокс, антиоксидантная защита, pH 8.5

🔵 VERTERA FORTE со вкусами — Черная смородина, Вишня, Яблоко
— С адаптогенами (шиповник, эхинацея, солодка, элеутерококк), pH 5

💜 ANGIOLIVE ORIGINAL — ламинария + фукус + экстракт красного винограда
— Здоровье сосудов, сердца, вен, профилактика варикоза
— Клинически доказана, 90 г/сут

👶 УМНЫЙ РЕБЁНОК (Smart Kid) — детское питание
— Для детей от 3 лет, вкусы: яблоко, банан, груша
— 140+ полезных веществ, суточная норма йода

🦴 ARTROPLAST — здоровье суставов (хондроитин, глюкозамин)
🦴 HONDROFEROL — комплекс для суставов и связок

🌿 VERTERA SENSATION — 8 активаторов иммунитета
🔥 SLEEP&SLIM BOOSTER — ночной жиросжигатель
💪 SPORT&POWER BOOSTER — мужская сила, выработка тестостерона

💧 КОСМЕТИКА:
— Plasma Therapy — косметическая линия на основе Plasma Technology
— Seaweed Biomask for Face — маска для лица, омоложение и увлажнение
— Seaweed Body Oil — масло для тела, питание и упругость
— Hydrate Collagen — нативный коллаген для кожи, волос и суставов
— Thalasso Spa Gel — гель для обёртываний, против целлюлита
— True Vision — тоник для кожи вокруг глаз
— AngioLive Mask — маска для снятия отёков ног

═══════════════════════════════
КАК КУПИТЬ / БИЗНЕС
═══════════════════════════════
Покупка со скидкой 30%: нужно зарегистрировать личный кабинет — обратитесь к менеджеру.

Бизнес: рекомендовать продукт окружению → зарабатывать. Первый шаг — попробовать продукт самому.
Контакт спонсора: +99363327177 (Telegram: @tach_ttt)

═══════════════════════════════
ОБРАЗОВАНИЕ
═══════════════════════════════
Международная Академия Гомеостаза VERTERA:
— Курс «Талассонутрициология» (256 ч, диплом)
— Курс «Талассокосметология» (256 ч)
— Курс «Консультант по ЗОЖ» (256 ч)
— Курс «Детская нутрициология» (20 ч)

═══════════════════════════════
ПРАВИЛА
═══════════════════════════════
- Отвечай дружелюбно и по делу
- При вопросах о ценах: цены уточнит менеджер
- Когда человек готов к покупке или хочет узнать больше — предложи заполнить анкету, используй слово "анкету"
- Не придумывай факты
- ВАЖНО: продукты Vertera — натуральные ПРОДУКТЫ ПИТАНИЯ, НЕ лекарства. Никогда не говори "курс", "курс лечения", "лечит", "терапия", "дозировка". Говори только: "употреблять", "добавить в рацион", "ежедневное питание".
- ВАЖНО: никогда не давай медицинских советов
"""


def get_catalog_text(lang: str, country: str) -> str:

    nl = "\n"
    nn = "\n\n"

    gels_ru = (
        "🟢 *VERTERA GEL*\n"
        "Гель из ламинарии. Поддерживает иммунитет, улучшает работу ЖКТ, "
        "здоровье сердца и сосудов, способствует детоксикации. pH 7.9. "
        "Употреблять 50–100 г за 30 минут до еды.\n\n"
        "🔵 *VERTERA FORTE ORIGINAL*\n"
        "Ламинария + фукус + дигидрокверцетин. "
        "Усиленная антиоксидантная защита и детоксикация. pH 8.5.\n\n"
        "🔵 *VERTERA FORTE со вкусами*\n"
        "Ламинария и фукус с адаптогенами (шиповник, эхинацея, солодка, элеутерококк). "
        "Вкусы: чёрная смородина, вишня, яблоко. pH 5.\n\n"
        "💜 *ANGIOLIVE ORIGINAL*\n"
        "Ламинария + фукус + экстракт красного винограда. "
        "Поддержка здоровья сосудов, сердца, вен. "
        "Профилактика варикоза. Норма употребления — 90 г в день.\n\n"
        "👶 *УМНЫЙ РЕБЁНОК (Smart Kid)*\n"
        "Детское питание от 3 лет. Содержит более 140 полезных веществ "
        "и суточную норму йода. Вкусы: яблоко, банан, груша."
    )

    gels_tk = (
        "🟢 *VERTERA GEL*\n"
        "Laminariýadan gel. Immuniteti goldaýar, iýmit siňdirişi we "
        "ýürek-damar saglygyny gowulandyrýar, detoks edýär. pH 7.9. "
        "Nahardan 30 minut öň 50–100 g iýmek maslahat berilýär.\n\n"
        "🔵 *VERTERA FORTE ORIGINAL*\n"
        "Laminariýa + fukus + digidrokersetin. "
        "Güýçlendirilen antioksidant gorag we detoks. pH 8.5.\n\n"
        "🔵 *VERTERA FORTE (tagamly)*\n"
        "Laminariýa we fukus + adaptogenler (itburun, ehinaseýa, mäşebenlik, eleýterokok). "
        "Tagamlar: gara smorodina, alça, alma. pH 5.\n\n"
        "💜 *ANGIOLIVE ORIGINAL*\n"
        "Laminariýa + fukus + gyzyl üzüm ekstrakty. "
        "Damarlar we ýürek saglygyny goldaýar, warikozy öňüni alýar. "
        "Günde 90 g.\n\n"
        "👶 *AKYLLY ÇAGA (Smart Kid)*\n"
        "3 ýaşdan çagalar üçin iýmit. 140+ peýdaly madda we günlük ýod normasyny öz içine alýar. "
        "Tagamlar: alma, banan, armyt."
    )

    gels_uz = (
        "🟢 *VERTERA GEL*\n"
        "Laminariyadagi gel. Immunitetni qo'llab-quvvatlaydi, hazm qilishni, "
        "yurak va qon tomir sog'ligini yaxshilaydi, detoks qiladi. pH 7.9. "
        "Ovqatdan 30 daqiqa oldin 50–100 g iste'mol qilish tavsiya etiladi.\n\n"
        "🔵 *VERTERA FORTE ORIGINAL*\n"
        "Laminaria + fukus + digidrokvertsetin. "
        "Kuchaytirilgan antioksidant himoya va detoks. pH 8.5.\n\n"
        "🔵 *VERTERA FORTE (ta'mli)*\n"
        "Laminaria va fukus + adaptogenlar (itburun, exinaseya, miya o'ti, eleuterokokk). "
        "Ta'mlar: qora smorodina, gilos, olma. pH 5.\n\n"
        "💜 *ANGIOLIVE ORIGINAL*\n"
        "Laminaria + fukus + qizil uzum ekstrakti. "
        "Tomir va yurak sog'ligini qo'llab-quvvatlaydi, varikozning oldini oladi. "
        "Kuniga 90 g.\n\n"
        "👶 *AQLLI BOLA (Smart Kid)*\n"
        "3 yoshdan bolalar uchun oziq-ovqat. 140+ foydali modda "
        "va kunlik yod normasini o'z ichiga oladi. Ta'mlar: olma, banan, nok."
    )

    cosm_ru = (
        "💧 *PLASMA THERAPY*\n"
        "Инновационная косметическая линия на основе технологии Plasma. "
        "Омолаживает кожу, интенсивно увлажняет, восстанавливает упругость и эластичность. "
        "Изготовлена по запатентованной биотехнологии нового поколения.\n\n"
        "✨ *HYDRATE COLLAGEN*\n"
        "Высокомолекулярный нативный коллаген из кожи пресноводных рыб. "
        "Увлажняет кожу, сохраняет эластичность и упругость, предотвращает морщины. "
        "Укрепляет волосы, придаёт блеск и объём.\n\n"
        "🌿 *BIOMASK FOR FACE*\n"
        "Фитоводорослевая маска для лица. Интенсивное увлажнение и омоложение. "
        "Активизирует выработку собственных коллагена и эластина, "
        "стимулирует защитные функции кожи. Технология Plasma.\n\n"
        "🫧 *BODY OIL*\n"
        "Натуральное водорослевое масло для тела. Масла оливы, облепихи, шиповника, "
        "семян тыквы и льна с дигидрокверцетином. "
        "Повышает упругость кожи, обладает ранозаживляющим действием. "
        "Наносить лёгкими движениями на 10–15 минут."
    )

    cosm_tk = (
        "💧 *PLASMA THERAPY*\n"
        "Plasma tehnologiýasyna esaslanýan innowasiýon kosmetika hatary. "
        "Derini ýaşaldýar, çuňňur nemledýär, çeýeligini we berkligini dikeldýär.\n\n"
        "✨ *HYDRATE COLLAGEN*\n"
        "Süýdemsiz balyklaryň derisinden natiw kollagen. "
        "Derini nemledýär, çyşmaçylygyny saklaýar, gyryşyklary öňüni alýar. "
        "Saçlary berkidýär, ýalpyldawuklyk we göwrüm berýär.\n\n"
        "🌿 *BIOMASK FOR FACE*\n"
        "Ýüz üçin fitosuw ösümligi maskasy. Çuňňur nemlendirme we ýaşartma. "
        "Öz kollagen we elastin önümçiligini güýçlendirýär. Plasma tehnologiýasy.\n\n"
        "🫧 *BODY OIL*\n"
        "Tebigy suw ösümligi beden ýagy. Zeýtun, çaýkanly, itburun, garpyz "
        "we zygyr tohumlaryndan digidrokersetin bilen baýlaşdyrylan garyndy. "
        "Deriniň berkligini ýokarlandyrýar."
    )

    cosm_uz = (
        "💧 *PLASMA THERAPY*\n"
        "Plasma texnologiyasiga asoslangan innovatsion kosmetika liniyasi. "
        "Terini yoshartadi, intensiv namlantiradi, elastiklik va mustahkamlikni tiklaydi.\n\n"
        "✨ *HYDRATE COLLAGEN*\n"
        "Chuchuk baliqlar terisidan nativ kollagen. "
        "Terini namlantiradi, elastikligini saqlaydi, ajinlarning oldini oladi. "
        "Sochlarga mustahkamlik, porloqlik va hajm beradi.\n\n"
        "🌿 *BIOMASK FOR FACE*\n"
        "Yuz uchun fitosuvli niqob. Intensiv namlantirish va yoshartish. "
        "O'z kollagen va elastin ishlab chiqarishni faollashtiradi. Plasma texnologiyasi.\n\n"
        "🫧 *BODY OIL*\n"
        "Tabiiy suv o'simligi tana yog'i. Zaytun, temir yong'oq, itburun, "
        "oshqovoq urug'i va zigir yog'lari aralashmasi, digidrokvertsetin bilan boyitilgan. "
        "Teri elastikligini oshiradi, tiklovchi ta'sir ko'rsatadi."
    )

    sensation_ru = (
        "🌿 *VERTERA SENSATION*\n"
        "Уникальная рецептура с 8 натуральными активаторами иммунитета: "
        "ламинария, фукус, спирулина, экстракт чёрного тмина, бетулин и другие. "
        "Разработан на основе многолетних научных исследований. "
        "Технология микрокапсуляции обеспечивает максимальную биодоступность."
    )

    sensation_uz = (
        "🌿 *VERTERA SENSATION*\n"
        "8 ta tabiiy immunitet aktivatori bilan noyob formula: laminaria, fukus, "
        "spirulina, qora zira ekstrakti, betulin va boshqalar. "
        "Ko'p yillik ilmiy tadqiqotlar asosida ishlab chiqilgan. "
        "Mikrokapsulatsiya texnologiyasi maksimal biodostuplikni ta'minlaydi."
    )

    gels  = {"ru": gels_ru,  "tk": gels_tk,  "uz": gels_uz}
    cosm  = {"ru": cosm_ru,  "tk": cosm_tk,  "uz": cosm_uz}
    sens  = {"ru": sensation_ru, "uz": sensation_uz}

    headers = {
        "ru": ("📖 *Продукция Vertera*\n\n🧴 *ГЕЛИ:*\n\n",  "\n\n💄 *КОСМЕТИКА:*\n\n", "\n\n❓ Есть вопросы? Спрашивайте!"),
        "tk": ("📖 *Vertera önümleri*\n\n🧴 *GELLER:*\n\n", "\n\n💄 *KOSMETIKA:*\n\n", "\n\n❓ Soraglaryňyz barmy? Soraň!"),
        "uz": ("📖 *Vertera mahsulotlari*\n\n🧴 *GELLAR:*\n\n", "\n\n💄 *KOSMETIKA:*\n\n", "\n\n❓ Savollaringiz bormi? So'rang!"),
    }

    h_gel, h_cosm, h_foot = headers.get(lang, headers["ru"])
    result = h_gel + gels.get(lang, gels_ru) + h_cosm + cosm.get(lang, cosm_ru)

    if country == "UZB":
        s = sens.get(lang, sens.get("ru", ""))
        if s:
            result += "\n\n" + s

    return result + h_foot

def get_main_keyboard(lang: str):
    t = TEXTS[lang]
    pt = PARTNER_TEXTS.get(lang, PARTNER_TEXTS["ru"])
    return ReplyKeyboardMarkup(
        [[t["buy"], t["business"]],
         [t["catalog"], t["contact"]],
         [t["home"], pt["btn"]]],
        resize_keyboard=True
    )

def get_phone(country: str) -> str:
    return SPONSOR_PHONE_TKM if country == "TKM" else SPONSOR_PHONE_UZB

# ─── /start — выбор страны ───────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "🌍 Выберите вашу страну / Choose your country:\n\nТуркменистан 🇹🇲 / O'zbekiston 🇺🇿",
        reply_markup=ReplyKeyboardMarkup(
            [["🇹🇲 Туркменистан", "🇺🇿 Узбекистан / O'zbekiston"]],
            resize_keyboard=True, one_time_keyboard=True
        )
    )
    return SELECT_COUNTRY

async def select_country(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if "Туркменистан" in text or "TKM" in text:
        context.user_data["country"] = "TKM"
        await update.message.reply_text(
            "🇹🇲 Diliňizi saýlaň / Выберите язык:",
            reply_markup=ReplyKeyboardMarkup(
                [["🇷🇺 Русский", "🇹🇲 Türkmen"]],
                resize_keyboard=True, one_time_keyboard=True
            )
        )
    else:
        context.user_data["country"] = "UZB"
        await update.message.reply_text(
            "🇺🇿 Tilni tanlang / Выберите язык:",
            reply_markup=ReplyKeyboardMarkup(
                [["🇷🇺 Русский", "🇺🇿 O'zbek"]],
                resize_keyboard=True, one_time_keyboard=True
            )
        )
    return SELECT_LANG

async def select_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    country = context.user_data.get("country", "TKM")

    if "Русский" in text:
        lang = "ru"
    elif "Türkmen" in text:
        lang = "tk"
    elif "O'zbek" in text or "Узбек" in text:
        lang = "uz"
    else:
        lang = "ru"

    context.user_data["lang"] = lang
    user = update.effective_user
    user_histories[user.id] = []

    t = TEXTS[lang]
    await update.message.reply_text(
        t["welcome"],
        parse_mode="Markdown",
        reply_markup=get_main_keyboard(lang)
    )
    return CHAT

# ─── Основной чат ────────────────────────────────────────────
async def chat_with_gpt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text
    lang = context.user_data.get("lang", "ru")
    country = context.user_data.get("country", "TKM")
    phone = get_phone(country)
    t = TEXTS[lang]

    # Кнопка главная
    if text in [t["home"], "🔙 Главная", "🔙 Baş sahypa", "🔙 Bosh sahifa"]:
        await update.message.reply_text(
            t["welcome"],
            parse_mode="Markdown",
            reply_markup=get_main_keyboard(lang)
        )
        return CHAT

    # Кнопка каталога — Mini App
    if text in [t["catalog"], "📖 Каталог", "📖 Katalog"]:
        mini_app_text = {
            "ru": "📖 Откройте наш каталог в Mini App:\n\n👉 https://t.me/Verteratkmbot/vertera_tkm\n\nТам все продукты с фото, описаниями и ценами 🌿",
            "tk": "📖 Katalogumuzy Mini App-da açyň:\n\n👉 https://t.me/Verteratkmbot/vertera_tkm\n\nOrada ähli önümler suratlar, beýanlar we bahalar bilen 🌿",
            "uz": "📖 Katalogimizni Mini App-da oching:\n\n👉 https://t.me/Verteratkmbot/vertera_tkm\n\nU yerda barcha mahsulotlar rasmlar, tavsiflar va narxlar bilan 🌿",
        }
        db_set_catalog_viewed(user.id)
        schedule_catalog_reminder(context, user.id, lang)
        await update.message.reply_text(
            mini_app_text.get(lang, mini_app_text["ru"]),
            reply_markup=get_main_keyboard(lang)
        )
        return CHAT

    # Кнопка связаться
    if text in [t["contact"], "📞 Связаться", "📞 Habarlaşmak", "📞 Bog'lanish"]:
        await update.message.reply_text(
            t["contact_text"].format(sponsor=SPONSOR_USERNAME, phone=phone),
            reply_markup=get_main_keyboard(lang)
        )
        return CHAT

    # Кнопка купить продукт
    if text in [t["buy"], "🛒 Купить продукт", "🛒 Önüm satyn almak", "🛒 Mahsulot sotib olish"]:
        try:
            country_label = "Туркменистан 🇹🇲" if country == "TKM" else "Узбекистан 🇺🇿"
            uname = f"@{user.username}" if user.username else str(user.id)
            await context.bot.send_message(
                chat_id=MANAGER_CHAT_ID,
                text=f"🛒 Интерес к покупке\n🌍 {country_label} | 🗣 {lang}\n👤 {user.full_name or uname} | 🆔 {uname}"
            )
        except Exception as e:
            logger.error(f"Buy notify: {e}")
        buy_menu = ReplyKeyboardMarkup(
            [[t["anketa_yes"]], [t["register_btn"]], [t["home"]]],
            resize_keyboard=True
        )
        buy_text = {
            "ru": (
                "🛒 *Купить продукт Vertera*\n\n"
                "Все продукты Vertera можно приобрести со скидкой 30% после регистрации личного кабинета.\n\n"
                "Чтобы сделать заказ — заполните анкету, наш менеджер свяжется с вами и поможет с выбором 🌿"
            ),
            "tk": (
                "🛒 *Vertera önümini satyn almak*\n\n"
                "Ähli Vertera önümlerini şahsy kabineti hasaba aldyranyňyzdan soň 30% arzanladyş bilen satyn alyp bilersiňiz.\n\n"
                "Sargyt etmek üçin — anketa dolduryň, menejerimiz siz bilen habarlaşar 🌿"
            ),
            "uz": (
                "🛒 *Vertera mahsulotini sotib olish*\n\n"
                "Barcha Vertera mahsulotlarini shaxsiy kabinetni ro\'yxatdan o\'tkazganingizdan so\'ng 30% chegirma bilan sotib olish mumkin.\n\n"
                "Buyurtma berish uchun — anketa to\'ldiring, menejerimiz siz bilan bog\'lanadi 🌿"
            ),
        }
        await update.message.reply_text(
            buy_text.get(lang, buy_text["ru"]),
            parse_mode="Markdown",
            reply_markup=buy_menu
        )
        return CHAT

    # Кнопка бизнес
    if text in [t["business"], "💼 Бизнес с Vertera", "💼 Vertera bilen iş", "💼 Vertera bilan biznes"]:
        try:
            country_label = "Туркменистан 🇹🇲" if country == "TKM" else "Узбекистан 🇺🇿"
            uname = f"@{user.username}" if user.username else str(user.id)
            await context.bot.send_message(
                chat_id=MANAGER_CHAT_ID,
                text=f"💼 Интерес к бизнесу\n🌍 {country_label} | 🗣 {lang}\n👤 {user.full_name or uname} | 🆔 {uname}"
            )
        except Exception as e:
            logger.error(f"Biz notify: {e}")
        business_menu = ReplyKeyboardMarkup(
            [
                ["📊 Узнать больше о доходе"],
                [t["anketa_yes"]],
                [t["register_btn"]],
                [t["home"]],
            ],
            resize_keyboard=True
        )
        business_text = {
            "ru": (
                "💼 *Бизнес с Vertera*\n\n"
                "Vertera — это не просто продукт, это возможность создать стабильный доход.\n\n"
                "Как это работает:\n"
                "• Попробуйте продукт сами и убедитесь в результате\n"
                "• Рекомендуйте его своему окружению\n"
                "• Получайте доход с каждой продажи\n\n"
                "Первый шаг — зарегистрировать личный кабинет и попробовать продукт. "
                "Мы поможем на каждом этапе 🌿"
            ),
            "tk": (
                "💼 *Vertera bilen iş*\n\n"
                "Vertera — bu diňe bir önüm däl, durnukly girdeji döretmek mümkinçiligi.\n\n"
                "Bu nähili işleýär:\n"
                "• Önümi özüňiz synap görüň we netijäni duýuň\n"
                "• Töweregiňizdäkilere maslahat beriň\n"
                "• Her satuwdan girdeji alyň\n\n"
                "Ilkinji ädim — şahsy kabinetini hasaba alyp, önümi synap görmek. "
                "Her tapgyrda kömek ederis 🌿"
            ),
            "uz": (
                "💼 *Vertera bilan biznes*\n\n"
                "Vertera — bu faqat mahsulot emas, barqaror daromad yaratish imkoniyati.\n\n"
                "Bu qanday ishlaydi:\n"
                "• Mahsulotni o\'zingiz sinab ko\'ring va natijani his qiling\n"
                "• Atrofingizlarga tavsiya qiling\n"
                "• Har bir sotuvdan daromad oling\n\n"
                "Birinchi qadam — shaxsiy kabinetni ro\'yxatdan o\'tkazish va mahsulotni sinab ko\'rish. "
                "Har bosqichda yordam beramiz 🌿"
            ),
        }
        await update.message.reply_text(
            business_text.get(lang, business_text["ru"]),
            parse_mode="Markdown",
            reply_markup=business_menu
        )
        return CHAT

    # Кнопка инструкция регистрации
    if text == t.get("register_btn"):
        reg_text = REG_INSTRUCTIONS.get(country, {}).get(lang)
        if not reg_text:
            reg_text = REG_INSTRUCTIONS.get(country, {}).get("ru", "")
        if reg_text:
            await update.message.reply_text(
                reg_text.format(link=REGISTER_LINK, sponsor=SPONSOR_USERNAME),
                parse_mode="Markdown",
                reply_markup=get_main_keyboard(lang)
            )
            return CHAT

    # Запрос регистрации
    reg_keywords = ["регистрац", "зарегистрир", "личный кабинет", "register", "hasaba", "ro'yxat", "ID"]
    if any(kw.lower() in text.lower() for kw in reg_keywords):
        reg_text = REG_INSTRUCTIONS.get(country, {}).get(lang)
        if not reg_text:
            reg_text = REG_INSTRUCTIONS.get(country, {}).get("ru", "")
        if reg_text:
            await update.message.reply_text(
                reg_text.format(link=REGISTER_LINK, sponsor=SPONSOR_USERNAME),
                parse_mode="Markdown",
                reply_markup=get_main_keyboard(lang)
            )
            return CHAT

    # ── Кнопки да/нет анкеты (проверяем текстом, без Regex) ─
    YES = [
        "✅ Да, заполнить анкету",
        "✅ Hawa, anketa doldurmak",
        "✅ Ha, anketa to'ldirish",
        t.get("anketa_yes", ""),
    ]
    NO = [
        "❌ Нет, продолжить общение",
        "❌ Ýok, gürrüňdeşligi dowam etmek",
        "❌ Yo'q, suhbatni davom ettirish",
        t.get("anketa_no", ""),
    ]
    if text in YES:
        return await start_anketa(update, context)
    if text in NO:
        await update.message.reply_text(t["anketa_ok"], reply_markup=get_main_keyboard(lang))
        return CHAT

    # Кнопка Узнать больше о доходе
    if text in ["📊 Узнать больше о доходе", "📊 Girdeji barada has köp", "📊 Daromad haqida ko'proq"]:
        detail = {
            "ru": (
                "📊 *Как вы будете зарабатывать?*\n\n"
                "На первых порах у вас будет *4 бонуса*, которые помогут зарабатывать:\n\n"
                "1️⃣ *БЗП — Бонус за приглашение*\n"
                "40% с каждой покупки вашего партнёра. "
                "Пригласил — он купил — ты получил бонус сразу.\n\n"
                "2️⃣ *Клубный бонус*\n"
                "Когда твоя первая линия достигает нужного объёма — "
                "получаешь фиксированную выплату (55 или 110 UE). "
                "Выполнил условие — получил.\n\n"
                "3️⃣ *КББ — Командный бинарный бонус*\n"
                "Строишь две ветки. Накопилось по 40 PV в каждой — "
                "цикл закрылся, бонус начислен. "
                "Чем активнее команда, тем больше циклов.\n\n"
                "4️⃣ *БЗК — Бонус за квалификацию*\n"
                "Единовременная выплата при достижении нового статуса. "
                "Растёшь — получаешь награду за каждый новый уровень.\n\n"
                "Хотите узнать больше — нажмите кнопку *«📞 Связаться»* 🌿"
            ),
            "tk": (
                "📊 *Siz nähili gazanarsyňyz?*\n\n"
                "Başlangyjynda size gazanmaga kömek etjek *4 bonus* bar:\n\n"
                "1️⃣ *BZP — Çakylyk bonusy*\n"
                "Hyzmatdaşyňyzyň her satyn alşyndan 40%. "
                "Adam çagyr, ol satyn alsyn — bonus dessine geýdi.\n\n"
                "2️⃣ *Klub bonusy*\n"
                "Birinji liniýaň zerur göwrüme ýetende — "
                "kesgitli töleg alýarsyň (55 ýa-da 110 UE). "
                "Şerti ýerine getirdiň — aldyň.\n\n"
                "3️⃣ *KBB — Topar binar bonusy*\n"
                "Iki şaha gurýarsyň. Her birinde 40 PV toplananda — "
                "sikl ýapylýar, bonus hasaplanýar. "
                "Topar näçe işjeň bolsa, sikl şonça köp.\n\n"
                "4️⃣ *BZK — Derejä ýetmek bonusy*\n"
                "Täze statusa ýetileninde bir gezek töleg. "
                "Gurluşda ösýärsiň — her täze dereje üçin sylag.\n\n"
                "Köpräk bilmek isleýärsiňizmi — *«📞 Habarlaşmak»* düwmesine basyň 🌿"
            ),
            "uz": (
                "📊 *Siz qanday daromad olasiz?*\n\n"
                "Dastlabki bosqichda sizga yordam beradigan *4 bonus* bor:\n\n"
                "1️⃣ *BZP — Taklif bonusi*\n"
                "Hamkoringizning har xarididan 40%. "
                "Odam taklif qil, u sotib olsin — bonus darhol keladi.\n\n"
                "2️⃣ *Klub bonusi*\n"
                "Birinchi liniyangiz kerakli hajmga yetganda — "
                "belgilangan to'lov olasiz (55 yoki 110 UE). "
                "Shartni bajarding — oldingiz.\n\n"
                "3️⃣ *KBB — Jamoa binar bonusi*\n"
                "Ikki tarmoq qurasan. Har birida 40 PV to'planganda — "
                "sikl yopiladi, bonus hisoblanadi. "
                "Jamoa qanchalik faol bo'lsa, sikl shunchalik ko'p.\n\n"
                "4️⃣ *BZK — Malaka bonusi*\n"
                "Yangi statusga erishilganda bir martalik to'lov. "
                "O'sasan — har yangi daraja uchun mukofot.\n\n"
                "Ko'proq bilmoqchimisiz — *«📞 Bog'lanish»* tugmasini bosing 🌿"
            ),
        }
        await update.message.reply_text(
            detail.get(lang, detail["ru"]),
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(
                [[t["anketa_yes"]], [t["register_btn"]], [t["contact"]], [t["home"]]],
                resize_keyboard=True
            )
        )
        return CHAT

    # GPT
    if user.id not in user_histories:
        user_histories[user.id] = []

    user_histories[user.id].append({"role": "user", "content": text})
    if len(user_histories[user.id]) > 20:
        user_histories[user.id] = user_histories[user.id][-20:]

    try:
        await update.message.chat.send_action("typing")
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": get_system_prompt(country, lang)}] + user_histories[user.id],
            max_tokens=600,
            temperature=0.7
        )
        reply = response.choices[0].message.content
        user_histories[user.id].append({"role": "assistant", "content": reply})

        if "анкету" in reply.lower() or "anketa" in reply.lower() or "anketa" in reply.lower():
            await update.message.reply_text(reply, reply_markup=ReplyKeyboardMarkup(
                [[t["anketa_yes"]], [t["anketa_no"]]],
                resize_keyboard=True
            ))
        else:
            await update.message.reply_text(reply, reply_markup=get_main_keyboard(lang))

    except Exception as e:
        logger.error(f"GPT error: {e}")
        await update.message.reply_text(
            t["error_text"].format(sponsor=SPONSOR_USERNAME, phone=phone),
            reply_markup=get_main_keyboard(lang)
        )
    return CHAT

# ─── Анкета ──────────────────────────────────────────────────
async def start_anketa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "ru")
    t = TEXTS[lang]
    if update.message.text == t["anketa_no"]:
        await update.message.reply_text(t["anketa_ok"], reply_markup=get_main_keyboard(lang))
        return CHAT
    await update.message.reply_text(t["anketa_start"], reply_markup=ReplyKeyboardRemove())
    return ANKETA_NAME

async def anketa_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "ru")
    context.user_data["name"] = update.message.text
    await update.message.reply_text(TEXTS[lang]["anketa_phone"])
    return ANKETA_PHONE

async def anketa_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "ru")
    context.user_data["phone_user"] = update.message.text
    await update.message.reply_text(TEXTS[lang]["anketa_city"])
    return ANKETA_CITY

async def anketa_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "ru")
    t = TEXTS[lang]
    context.user_data["city"] = update.message.text
    await update.message.reply_text(t["anketa_interest"], reply_markup=ReplyKeyboardMarkup(
        [[t["interest_product"], t["interest_business"]], [t["interest_both"]]],
        resize_keyboard=True
    ))
    return ANKETA_INTEREST

async def anketa_interest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    lang = context.user_data.get("lang", "ru")
    country = context.user_data.get("country", "TKM")
    phone = get_phone(country)
    t = TEXTS[lang]

    context.user_data["interest"] = update.message.text

    name = context.user_data.get("name", "—")
    user_phone = context.user_data.get("phone_user", "—")
    city = context.user_data.get("city", "—")
    interest = context.user_data.get("interest", "—")
    username = f"@{user.username}" if user.username else str(user.id)
    country_label = "Туркменистан 🇹🇲" if country == "TKM" else "Узбекистан 🇺🇿"

    try:
        async with httpx.AsyncClient() as http_client:
            await http_client.post(GOOGLE_SHEET_URL, json={
                "name": name, "phone": user_phone, "city": city,
                "interest": interest,
                "source": f"Telegram Bot Vertera | {country_label} | {lang}",
                "username": username
            }, timeout=10)
    except Exception as e:
        logger.error(f"Sheets error: {e}")

    try:
        await context.bot.send_message(
            chat_id=MANAGER_CHAT_ID,
            text=(
                f"📥 Новая заявка Vertera!\n\n"
                f"🌍 Страна: {country_label}\n"
                f"🗣 Язык: {lang}\n"
                f"👤 {name}\n"
                f"📱 {user_phone}\n"
                f"🏙 {city}\n"
                f"💡 {interest}\n"
                f"🆔 {username}"
            )
        )
    except Exception as e:
        logger.error(f"Sponsor notify error: {e}")

    await update.message.reply_text(
        t["anketa_done"].format(sponsor=SPONSOR_USERNAME, phone=phone),
        reply_markup=get_main_keyboard(lang)
    )
    return CHAT

# ─── main ─────────────────────────────────────────────────────

# ─── Партнёрские хендлеры ────────────────────────────────────

async def partner_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Нажали кнопку 'Я партнёр'."""
    lang = context.user_data.get("lang", "ru")
    user = update.effective_user
    pt = PARTNER_TEXTS.get(lang, PARTNER_TEXTS["ru"])

    # Если уже партнёр — сразу в меню
    if is_partner(user.id):
        await update.message.reply_text(
            pt["menu_title"],
            reply_markup=get_partner_keyboard(lang)
        )
        return PARTNER_MENU

    # Иначе — просим ID
    await update.message.reply_text(
        pt["ask_id"],
        reply_markup=ReplyKeyboardRemove()
    )
    return PARTNER_ID

async def partner_receive_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получили ID компании от пользователя."""
    lang    = context.user_data.get("lang", "ru")
    user    = update.effective_user
    company_id = update.message.text.strip()
    pt = PARTNER_TEXTS.get(lang, PARTNER_TEXTS["ru"])

    # Сохраняем pending
    uname = f"@{user.username}" if user.username else str(user.id)
    pending_add(user.id, {
        "name": user.full_name or uname,
        "company_id": company_id,
        "lang": lang,
        "tg_username": uname,
        "tg_id": user.id,
    })

    # Уведомляем менеджера с инлайн-кнопками текстом
    try:
        await context.bot.send_message(
            chat_id=MANAGER_CHAT_ID,
            text=(
                f"🤝 Запрос на доступ партнёра\n\n"
                f"👤 {user.full_name or uname}\n"
                f"🆔 {uname}\n"
                f"🏢 ID компании: {company_id}\n\n"
                f"Чтобы одобрить: /approve_{user.id}\n"
                f"Чтобы отклонить: /reject_{user.id}"
            )
        )
    except Exception as e:
        logger.error(f"partner notify: {e}")

    await update.message.reply_text(
        pt["wait"],
        reply_markup=get_main_keyboard(lang)
    )
    return CHAT

async def partner_approve_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/approve_<user_id> — менеджер одобряет партнёра."""
    text = update.message.text.strip()
    if str(update.effective_user.id) != str(MANAGER_CHAT_ID):
        return
    try:
        target_id = int(text.split("_")[1])
    except (IndexError, ValueError):
        return
    info = pending_get(target_id)
    if not info:
        await update.message.reply_text("Запрос не найден.")
        return
    partner_add(target_id, info.get("name",""), info.get("company_id",""), info.get("lang","ru"))
    pending_remove(target_id)
    lang = info.get("lang", "ru")
    pt = PARTNER_TEXTS.get(lang, PARTNER_TEXTS["ru"])
    try:
        await context.bot.send_message(
            chat_id=target_id,
            text=pt["approved"],
            reply_markup=get_partner_keyboard(lang)
        )
    except Exception as e:
        logger.error(f"approve send: {e}")
    await update.message.reply_text(f"✅ Партнёр {info.get('name')} одобрен!")

async def partner_reject_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/reject_<user_id> — менеджер отклоняет запрос."""
    text = update.message.text.strip()
    if str(update.effective_user.id) != str(MANAGER_CHAT_ID):
        return
    try:
        target_id = int(text.split("_")[1])
    except (IndexError, ValueError):
        return
    info = pending_get(target_id)
    if not info:
        await update.message.reply_text("Запрос не найден.")
        return
    pending_remove(target_id)
    lang = info.get("lang", "ru")
    pt = PARTNER_TEXTS.get(lang, PARTNER_TEXTS["ru"])
    try:
        await context.bot.send_message(chat_id=target_id, text=pt["rejected"])
    except Exception as e:
        logger.error(f"reject send: {e}")
    await update.message.reply_text(f"❌ Запрос от {info.get('name')} отклонён.")

async def partner_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопок партнёрского меню."""
    lang = context.user_data.get("lang", "ru")
    country = context.user_data.get("country", "TKM")
    text = update.message.text
    pt = PARTNER_TEXTS.get(lang, PARTNER_TEXTS["ru"])

    # Выход из партнёрского меню
    if text == pt["btn_back"]:
        await update.message.reply_text(
            TEXTS[lang]["welcome"],
            parse_mode="Markdown",
            reply_markup=get_main_keyboard(lang)
        )
        return CHAT

    # Обучение
    if text == pt["btn_learn"]:
        await update.message.reply_text(
            pt["learn_text"],
            parse_mode="Markdown",
            reply_markup=get_partner_keyboard(lang)
        )
        return PARTNER_MENU

    # Маркетинг
    if text == pt["btn_market"]:
        await update.message.reply_text(
            pt["market_text"],
            parse_mode="Markdown",
            reply_markup=get_partner_keyboard(lang)
        )
        return PARTNER_MENU

    # Калькулятор дохода
    if text == pt["btn_calc"]:
        context.user_data["awaiting_calc"] = True
        await update.message.reply_text(
            pt["calc_ask"],
            reply_markup=ReplyKeyboardRemove()
        )
        return PARTNER_MENU

    if context.user_data.get("awaiting_calc"):
        context.user_data.pop("awaiting_calc", None)
        try:
            n = int(text.strip())
            ue_per = 40
            total_ue = n * ue_per
            manat = total_ue * 15
            sum_uz = total_ue * 10000
            result = (
                f"🧮 *Расчёт дохода*\n\n"
                f"Активных партнёров: {n}\n"
                f"Ориентировочный БЗП: ~{total_ue} UE/мес\n"
                f"• TKM: ~{manat:,} манат\n"
                f"• UZB: ~{sum_uz:,} сум\n\n"
                f"_Это только БЗП. С бинаром и клубным бонусом доход выше_ 🌿"
            )
            await update.message.reply_text(
                result, parse_mode="Markdown",
                reply_markup=get_partner_keyboard(lang)
            )
        except ValueError:
            await update.message.reply_text(
                "Введите число, например: 10",
                reply_markup=get_partner_keyboard(lang)
            )
        return PARTNER_MENU

    # Контакты
    if text == pt["btn_contacts"]:
        user = update.effective_user
        contacts = contacts_load(user.id)
        if not contacts:
            msg = pt["contacts_empty"]
        else:
            lines = [f"👤 {c['name']} | 📞 {c['phone']} | {c['status']}" for c in contacts]
            msg = "👥 *Ваши контакты:*\n\n" + "\n".join(lines)
        kb = ReplyKeyboardMarkup(
            [[pt["contacts_add"]], [pt["btn_back"]]],
            resize_keyboard=True
        )
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=kb)
        return PARTNER_MENU

    if text == pt["contacts_add"]:
        await update.message.reply_text(
            pt["contacts_ask_name"],
            reply_markup=ReplyKeyboardRemove()
        )
        return PARTNER_CONTACTS_NAME

    # Новости
    if text == pt["btn_news"]:
        await update.message.reply_text(
            pt["news_text"],
            reply_markup=get_partner_keyboard(lang)
        )
        return PARTNER_MENU

    return PARTNER_MENU

async def partner_contacts_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "ru")
    pt = PARTNER_TEXTS.get(lang, PARTNER_TEXTS["ru"])
    context.user_data["new_contact_name"] = update.message.text.strip()
    await update.message.reply_text(pt["contacts_ask_phone"], reply_markup=ReplyKeyboardRemove())
    return PARTNER_CONTACTS_PHONE

async def partner_contacts_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang    = context.user_data.get("lang", "ru")
    user    = update.effective_user
    pt      = PARTNER_TEXTS.get(lang, PARTNER_TEXTS["ru"])
    name    = context.user_data.pop("new_contact_name", "—")
    phone   = update.message.text.strip()
    contact_add(user.id, name, phone)
    await update.message.reply_text(
        pt["contacts_saved"],
        reply_markup=get_partner_keyboard(lang)
    )
    return PARTNER_MENU

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # Паттерны кнопки "Я партнёр" на всех языках
    partner_btn_filter = filters.Regex(
        r"^(🤝 Я партнёр|🤝 Men hyzmatdaş|🤝 Men hamkorman)$"
    )

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            SELECT_COUNTRY: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_country)],
            SELECT_LANG: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_lang)],
            CHAT: [
                MessageHandler(partner_btn_filter, partner_entry),
                MessageHandler(filters.TEXT & ~filters.COMMAND, chat_with_gpt),
            ],
            PARTNER_ID: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, partner_receive_id),
            ],
            PARTNER_MENU: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, partner_menu_handler),
            ],
            PARTNER_CONTACTS_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, partner_contacts_name),
            ],
            PARTNER_CONTACTS_PHONE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, partner_contacts_phone),
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

    # Команды одобрения/отклонения от менеджера
    app.add_handler(MessageHandler(
        filters.Regex(r"^/approve_\d+$") & filters.TEXT,
        partner_approve_cmd
    ))
    app.add_handler(MessageHandler(
        filters.Regex(r"^/reject_\d+$") & filters.TEXT,
        partner_reject_cmd
    ))
    logger.info("🤖 Vertera bot started!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
