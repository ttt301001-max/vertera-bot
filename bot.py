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
SELECT_COUNTRY, SELECT_LANG, CHAT, ANKETA_NAME, ANKETA_PHONE, ANKETA_CITY, ANKETA_INTEREST, PARTNER_ID, PARTNER_MENU, PARTNER_CONTACTS_NAME, PARTNER_CONTACTS_PHONE, ADMIN_MENU = range(12)

user_histories = {}

import json, pathlib

# ─── Партнёрская база данных ─────────────────────────────────
_PARTNERS_F  = pathlib.Path("/tmp/vrt_partners.json")
_PENDING_F   = pathlib.Path("/tmp/vrt_pending.json")
_CONTACTS_F  = pathlib.Path("/tmp/vrt_contacts.json")
_WEBINAR_F   = pathlib.Path("/tmp/vrt_webinar.json")
_NEWS_F      = pathlib.Path("/tmp/vrt_news.json")

def _jload(p):
    try:
        return json.loads(p.read_text()) if p.exists() else {}
    except Exception:
        return {}

def _jsave(p, d):
    try:
        p.write_text(json.dumps(d, ensure_ascii=False))
    except Exception as e:
        logger.error(f"jsave {p}: {e}")

def is_partner(uid):        return str(uid) in _jload(_PARTNERS_F)
def partner_add(uid, name, cid, lang):
    d = _jload(_PARTNERS_F); d[str(uid)] = {"name":name,"cid":cid,"lang":lang}; _jsave(_PARTNERS_F, d)

async def partner_add_sheets(uid, name, cid, lang, uname, bot_instance=None):
    """Сохраняет партнёра в Google Sheets для постоянного хранения."""
    try:
        async with httpx.AsyncClient() as c:
            await c.post(GOOGLE_SHEET_URL, json={
                "type": "partner",
                "user_id": str(uid),
                "name": name,
                "company_id": cid,
                "lang": lang,
                "username": uname,
            }, timeout=10)
    except Exception as e:
        logger.error(f"partner_add_sheets: {e}")
def pending_add(uid, info):
    d = _jload(_PENDING_F);  d[str(uid)] = info;                                 _jsave(_PENDING_F,  d)
def pending_get(uid):        return _jload(_PENDING_F).get(str(uid), {})
def pending_del(uid):
    d = _jload(_PENDING_F);  d.pop(str(uid), None);                              _jsave(_PENDING_F,  d)
def contacts_get(uid):       return _jload(_CONTACTS_F).get(str(uid), [])
def news_save(text: str):
    """Сохраняет новость."""
    import datetime
    d = _jload(_NEWS_F)
    lst = d.get("list", [])
    lst.insert(0, {"text": text, "date": datetime.datetime.now().strftime("%d.%m.%Y %H:%M")})
    d["list"] = lst[:50]  # храним последние 50
    _jsave(_NEWS_F, d)

def news_get_latest() -> str:
    """Возвращает последнюю новость или пустую строку."""
    lst = _jload(_NEWS_F).get("list", [])
    if not lst:
        return ""
    return f"📅 {lst[0]['date']}\n\n{lst[0]['text']}"

def webinar_add(uid, name, text, uname):
    d = _jload(_WEBINAR_F)
    lst = d.get("list", [])
    lst.append({"uid": str(uid), "name": name, "text": text, "uname": uname,
                "date": __import__("datetime").datetime.now().strftime("%d.%m.%Y %H:%M")})
    d["list"] = lst
    _jsave(_WEBINAR_F, d)

def webinar_get_all():
    return _jload(_WEBINAR_F).get("list", [])

def contact_add(uid, name, phone):
    d = _jload(_CONTACTS_F); lst = d.get(str(uid), [])
    lst.append({"name": name, "phone": phone, "status": "новый"})
    d[str(uid)] = lst; _jsave(_CONTACTS_F, d)

# ─── Тексты партнёрского раздела ─────────────────────────────
PT = {
    "ru": {
        "btn":          "🤝 Я партнёр",
        "ask_id":       "Введите ваш *ID* из личного кабинета Vertera:",
        "wait":         "✅ Запрос отправлен! Ожидайте одобрения от администратора.",
        "approved":     "🎉 Вы одобрены как партнёр Vertera! Добро пожаловать в команду 🌿",
        "rejected":     "❌ Запрос отклонён. Свяжитесь с менеджером: @tach_ttt",
        "already":      "🤝 Вы уже в команде! Открываю партнёрское меню...",
        "menu_title":   "🤝 Партнёрское меню — выберите раздел:",
        "btn_learn":    "📚 Обучение",
        "btn_market":   "📊 Маркетинг",
        "btn_webinar":  "📅 Записаться на вебинар",
        "webinar_ask":   "📅 *ZOOM-вебинар с наставником*\n\nВы можете записаться на вебинар с вышестоящим наставником и его командой.\n\nНа вебинаре:\n• Разбор маркетинга и бонусов\n• Ответы на вопросы\n• Знакомство с командой\n• Первые шаги в бизнесе\n\nВведите ваше *имя и удобное время* для записи:",
        "webinar_ok":    "✅ Заявка на вебинар отправлена! Менеджер свяжется с вами для подтверждения.",
        "r_contacts":    "👋 Привет! Вы уже обзвонили ваши контакты? Это ключевой шаг — расскажите знакомым о продукте Vertera 📞",
        "r_market":      "📊 Напоминание: вы изучили систему маркетинга Vertera? Нажмите «📊 Маркетинг» в меню партнёра для изучения 🌿",
        "r_product":     "🌿 Вы уже изучили все продукты Vertera? Зайдите в «📚 Обучение» и пройдите все шаги.",
        "r_try":         "🎁 Вы уже попробовали продукт лично? Личный опыт — лучший аргумент для вашей команды!",
        "btn_contacts": "👥 Мои контакты",
        "btn_news":     "📣 Новости",
        "btn_back":     "🔙 Выйти из меню партнёра",
        "calc_ask":     "Введите количество активных партнёров в вашей команде (число):",
        "c_empty":      "👥 Контактов пока нет. Добавьте первого!",
        "c_add":        "➕ Добавить контакт",
        "c_name":       "Введите *имя* контакта:",
        "c_phone":      "Введите *телефон* контакта:",
        "c_saved":      "✅ Контакт добавлен!",
        "news":         "📣 Новостей пока нет. Следите за обновлениями 🌿",
        "learn": (
            "📚 *Обучение партнёра*\n\n"
            "*Шаг 1 — Изучи продукт*\n"
            "Попробуй все продукты сам. Только личный опыт убеждает.\n\n"
            "*Шаг 2 — Изучи систему бонусов*\n"
            "БЗП → Клубный бонус → КББ → БЗК\n"
            "Нажми «📊 Маркетинг» для подробного разбора.\n\n"
            "*Шаг 3 — Первые шаги*\n"
            "• Составь список из 20 знакомых\n"
            "• Расскажи о продукте 5 из них\n"
            "• Пригласи 2 в команду (левая и правая ветка)\n\n"
            "*Шаг 4 — Веди контакты*\n"
            "Добавляй клиентов в «👥 Мои контакты» и следи за статусом 🌿"
        ),
        "market": (
            "📊 *Маркетинг Vertera*\n\n"
            "С первых дней доступны 4 бонуса:\n\n"
            "1️⃣ *БЗП* — 40% с каждой покупки партнёра\n"
            "2️⃣ *Клубный бонус* — 55 или 110 UE за объём первой линии\n"
            "3️⃣ *КББ* — бонус за каждый цикл 40+40 PV в ветках\n"
            "4️⃣ *БЗК* — разовая выплата за достижение нового статуса\n\n"
            "1 UE = 15 манат (TKM) / 10 000 сум (UZB)\n\n"
            "Задай вопрос боту — он объяснит любой бонус подробно 🌿"
        ),
    },
    "tk": {
        "btn":          "🤝 Men hyzmatdaş",
        "ask_id":       "Vertera şahsy kabinetindäki *ID*-ňizi giriziň:",
        "wait":         "✅ Isleg iberildi! Administratoryň tassyklamagyna garaşyň.",
        "approved":     "🎉 Siz Vertera hyzmatdaşy hökmünde tassyklandyňyz! 🌿",
        "rejected":     "❌ Isleg ret edildi. Menejer bilen habarlaşyň: @tach_ttt",
        "already":      "🤝 Siz eýýäm toparda! Hyzmatdaş menýusyny açýaryn...",
        "menu_title":   "🤝 Hyzmatdaş menýusy — bölüm saýlaň:",
        "btn_learn":    "📚 Okuw",
        "btn_market":   "📊 Marketing",
        "btn_webinar":  "📅 Webinara ýazylmak",
        "webinar_ask":   "📅 *Halypa bilen ZOOM-webinar*\n\nÝokary derejeli halypa we onuň topary bilen webinara ýazylyp bilersiňiz.\n\nWebinarda:\n• Marketing we bonuslary düşündirmek\n• Soraglara jogap bermek\n• Topar bilen tanyşmak\n• Işde ilkinji ädimler\n\nÝazylmak üçin *adyňyzy we amatly wagtyňyzy* giriziň:",
        "webinar_ok":    "✅ Webinar üçin ýüz tutma iberildi! Menejer tassyklamak üçin siz bilen habarlaşar.",
        "r_contacts":    "👋 Salam! Kontaktlaryňyzy jaňladyňyzmy? Bu esasy ädim — Vertera önümi barada tanşlaryňyza aýdyň 📞",
        "r_market":      "📊 Ýatlatma: Vertera marketing ulgamyny öwrediňizmi? Öwrenmek üçin hyzmatdaş menýusynda «📊 Marketing» basyň 🌿",
        "r_product":     "🌿 Ähli Vertera önümlerini öwrediňizmi? «📚 Okuw» bölümine giriň we ähli ädimlerden geçiň.",
        "r_try":         "🎁 Önümi şahsy synap gördüňizmi? Şahsy tejribe — toparyňyz üçin iň gowy delil!",
        "btn_contacts": "👥 Meniň kontaktlarym",
        "btn_news":     "📣 Habarlar",
        "btn_back":     "🔙 Hyzmatdaş menýusyndan çyk",
        "calc_ask":     "Toparyňyzdaky işjeň hyzmatdaşlaryň sanyny giriziň (san):",
        "c_empty":      "👥 Heniz kontakt ýok. Birinjisini goşuň!",
        "c_add":        "➕ Kontakt goş",
        "c_name":       "*Adyny* giriziň:",
        "c_phone":      "*Telefonyny* giriziň:",
        "c_saved":      "✅ Kontakt goşuldy!",
        "news":         "📣 Häzirlik habar ýok. Täzelenmeleri yzarlaň 🌿",
        "learn": (
            "📚 *Hyzmatdaş okuwы*\n\n"
            "*Ädim 1 — Önümi öwren*\n"
            "Ähli önümleri özüň synap gör. Diňe şahsy tejribe ynandyrýar.\n\n"
            "*Ädim 2 — Bonus ulgamyny öwren*\n"
            "BZP → Klub bonusy → KBB → BZK\n"
            "Jikme-jik üçin «📊 Marketing» saýlaň.\n\n"
            "*Ädim 3 — Ilkinji ädimler*\n"
            "• 20 tanşyň sanawyny düz\n"
            "• Olaryň 5-ine önüm barada aýt\n"
            "• 2-sini topara çagyr (çep we sag şaha)\n\n"
            "*Ädim 4 — Kontaktlary ýöret*\n"
            "Müşderileri «👥 Meniň kontaktlarym»-a goş 🌿"
        ),
        "market": (
            "📊 *Vertera marketingi*\n\n"
            "Ilkinji günden 4 bonus elýeterli:\n\n"
            "1️⃣ *BZP* — hyzmatdaşyň her satyn alşyndan 40%\n"
            "2️⃣ *Klub bonusy* — birinji liniýa göwrümi üçin 55 ýa-da 110 UE\n"
            "3️⃣ *KBB* — şahalarda 40+40 PV her sikl üçin bonus\n"
            "4️⃣ *BZK* — täze statusa ýetmek üçin bir gezek töleg\n\n"
            "1 UE = 15 manat (TKM) / 10 000 sum (UZB)\n\n"
            "Bota sorag ber — islendik bonusy düşündirer 🌿"
        ),
    },
    "uz": {
        "btn":          "🤝 Men hamkorman",
        "ask_id":       "Vertera shaxsiy kabinetingizdagi *ID*-ni kiriting:",
        "wait":         "✅ So'rov yuborildi! Administrator tasdiqlashini kuting.",
        "approved":     "🎉 Siz Vertera hamkori sifatida tasdiqlandi! 🌿",
        "rejected":     "❌ So'rov rad etildi. Menejer bilan bog'laning: @tach_ttt",
        "already":      "🤝 Siz allaqachon jamoasidasiz! Hamkorlik menyusini ochaman...",
        "menu_title":   "🤝 Hamkorlik menyusi — bo'limni tanlang:",
        "btn_learn":    "📚 O'qitish",
        "btn_market":   "📊 Marketing",
        "btn_webinar":  "📅 Vebinarga yozilish",
        "webinar_ask":   "📅 *Murabbiy bilan ZOOM-vebinar*\n\nYuqori darajadagi murabbiy va uning jamoasi bilan vebinarga yozilishingiz mumkin.\n\nVebinarda:\n• Marketing va bonuslarni tushuntirish\n• Savollarga javob berish\n• Jamoa bilan tanishish\n• Biznesda birinchi qadamlar\n\nYozilish uchun *ismingiz va qulay vaqtingizni* kiriting:",
        "webinar_ok":    "✅ Vebinar uchun ariza yuborildi! Menejer tasdiqlash uchun siz bilan bog'lanadi.",
        "r_contacts":    "👋 Salom! Kontaktlaringizni qo'ng'iroq qildingizmi? Bu asosiy qadam — tanishlaringizga Vertera mahsuloti haqida ayting 📞",
        "r_market":      "📊 Eslatma: Vertera marketing tizimini o'rgandingizmi? O'rganish uchun hamkor menyusida «📊 Marketing» tugmasini bosing 🌿",
        "r_product":     "🌿 Barcha Vertera mahsulotlarini o'rgandingizmi? «📚 O'qitish» bo'limiga kiring va barcha qadamlardan o'ting.",
        "r_try":         "🎁 Mahsulotni shaxsan sinab ko'rdingizmi? Shaxsiy tajriba — jamoangiz uchun eng yaxshi dalil!",
        "btn_contacts": "👥 Mening kontaktlarim",
        "btn_news":     "📣 Yangiliklar",
        "btn_back":     "🔙 Hamkorlik menyusidan chiqish",
        "calc_ask":     "Jamoangizdagi faol hamkorlar sonini kiriting (raqam):",
        "c_empty":      "👥 Hali kontakt yo'q. Birinchisini qo'shing!",
        "c_add":        "➕ Kontakt qo'shish",
        "c_name":       "*Ism*ini kiriting:",
        "c_phone":      "*Telefon*ini kiriting:",
        "c_saved":      "✅ Kontakt qo'shildi!",
        "news":         "📣 Hozircha yangilik yo'q. Yangilanishlarni kuzating 🌿",
        "learn": (
            "📚 *Hamkor o'qitish*\n\n"
            "*Qadam 1 — Mahsulotni o'rgan*\n"
            "Barcha mahsulotlarni o'zing sinab ko'r. Faqat shaxsiy tajriba ishontiradi.\n\n"
            "*Qadam 2 — Bonus tizimini o'rgan*\n"
            "BZP → Klub bonusi → KBB → BZK\n"
            "Batafsil uchun «📊 Marketing» tanlang.\n\n"
            "*Qadam 3 — Birinchi qadamlar*\n"
            "• 20 tanishdan ro'yxat tuzing\n"
            "• Ulardan 5 tasiga mahsulot haqida ayting\n"
            "• 2 tasini jamoaga taklif qiling (chap va o'ng tarmoq)\n\n"
            "*Qadam 4 — Kontaktlarni boshqaring*\n"
            "Mijozlarni «👥 Mening kontaktlarim»ga qo'shing 🌿"
        ),
        "market": (
            "📊 *Vertera marketingi*\n\n"
            "Birinchi kundan 4 ta bonus mavjud:\n\n"
            "1️⃣ *BZP* — hamkorning har xarididan 40%\n"
            "2️⃣ *Klub bonusi* — birinchi liniya hajmi uchun 55 yoki 110 UE\n"
            "3️⃣ *KBB* — tarmoqlarda 40+40 PV har sikl uchun bonus\n"
            "4️⃣ *BZK* — yangi statusga erishganda bir martalik to'lov\n\n"
            "1 UE = 15 manat (TKM) / 10 000 so'm (UZB)\n\n"
            "Botga savol ber — istalgan bonusni tushuntiradi 🌿"
        ),
    },
}

def get_partner_kb(lang):
    p = PT.get(lang, PT["ru"])
    return ReplyKeyboardMarkup(
        [[p["btn_learn"],    p["btn_market"]],
         [p["btn_contacts"], p["btn_webinar"]],
         [p["btn_news"]],
         [p["btn_back"]]],
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
    p = PT.get(lang, PT["ru"])
    return ReplyKeyboardMarkup(
        [[t["buy"],    t["business"]],
         [t["catalog"], t["contact"]],
         [t["home"],   p["btn"]]],
        resize_keyboard=True
    )

def get_phone(country: str) -> str:
    return SPONSOR_PHONE_TKM if country == "TKM" else SPONSOR_PHONE_UZB

# ─── /start — выбор страны ───────────────────────────────────
async def load_partners_from_sheets():
    """Загружает партнёров из Google Sheets в локальный кэш при старте."""
    try:
        async with httpx.AsyncClient() as c:
            resp = await c.get(
                GOOGLE_SHEET_URL,
                params={"action": "get_partners"},
                timeout=10
            )
            data = resp.json()
            if data.get("status") == "ok" and data.get("partners"):
                existing = _jload(_PARTNERS_F)
                for p in data["partners"]:
                    uid = str(p.get("user_id", ""))
                    if uid and uid not in existing:
                        existing[uid] = {
                            "name": p.get("name", ""),
                            "cid":  p.get("company_id", ""),
                            "lang": p.get("lang", "ru"),
                        }
                _jsave(_PARTNERS_F, existing)
                logger.info(f"Loaded {len(data['partners'])} partners from Sheets")
    except Exception as e:
        logger.error(f"load_partners_from_sheets: {e}")

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

    # Кнопка "Я партнёр"
    partner_btn_texts = [PT[l]["btn"] for l in PT]
    if text in partner_btn_texts:
        p = PT.get(lang, PT["ru"])
        if is_partner(user.id):
            await update.message.reply_text(p["already"], reply_markup=get_partner_kb(lang))
            return PARTNER_MENU
        await update.message.reply_text(p["ask_id"], parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())
        return PARTNER_ID

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
                "type":     "anketa",
                "country":  country,
                "lang":     lang,
                "name":     name,
                "phone":    user_phone,
                "city":     city,
                "interest": interest,
                "username": username,
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

# ─── Партнёрские хендлеры ────────────────────────────────────

async def partner_receive_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пользователь ввёл ID компании — отправляем запрос менеджеру."""
    lang    = context.user_data.get("lang", "ru")
    user    = update.effective_user
    cid     = update.message.text.strip()
    p       = PT.get(lang, PT["ru"])
    uname   = f"@{user.username}" if user.username else str(user.id)

    pending_add(user.id, {
        "name": user.full_name or uname,
        "cid":  cid,
        "lang": lang,
        "uname": uname,
        "uid":  user.id,
    })

    try:
        await context.bot.send_message(
            chat_id=MANAGER_CHAT_ID,
            text=(
                f"🤝 Новый запрос партнёра\n\n"
                f"👤 {user.full_name or uname}\n"
                f"🆔 Telegram: {uname}\n"
                f"🏢 ID Vertera: {cid}\n\n"
                f"Одобрить: /ap{user.id}\n"
                f"Отклонить: /rj{user.id}"
            )
        )
    except Exception as e:
        logger.error(f"partner notify: {e}")

    await update.message.reply_text(p["wait"], reply_markup=get_main_keyboard(lang))
    return CHAT


# Тексты маркетинга с PV
MARKET_FULL = {
    "ru": (
        "📊 *Маркетинг Vertera*\n\n"
        "*Что такое PV?*\n"
        "PV (Product Value) — это баллы продукта. Каждый товар имеет свою ценность в PV. "
        "Все бонусы в системе рассчитываются именно через PV — не через деньги напрямую.\n\n"
        "*Бонусы зависят от товарооборота команды:*\n"
        "Чем больше суммарный PV твоей команды — тем выше статус и тем больше бонусов ты получаешь. "
        "Это значит: твой доход растёт вместе с ростом команды автоматически.\n\n"
        "С первых дней доступны 4 бонуса:\n\n"
        "1️⃣ *БЗП* — 40% с каждой покупки партнёра\n"
        "2️⃣ *Клубный бонус* — 55 или 110 UE за объём первой линии\n"
        "3️⃣ *КББ* — бонус за каждый цикл 40+40 PV в ветках\n"
        "4️⃣ *БЗК* — разовая выплата за достижение нового статуса\n\n"
        "1 UE = 15 манат (TKM) / 10 000 сум (UZB)\n\n"
        "Задай вопрос боту — он объяснит любой бонус подробно 🌿"
    ),
    "tk": (
        "📊 *Vertera marketingi*\n\n"
        "*PV näme?*\n"
        "PV (Product Value) — önüm ballary. Her önümiň öz PV gymmaty bar. "
        "Ulgamdaky ähli bonuslar PV arkaly hasaplanýar.\n\n"
        "*Bonuslar toparyň haryt dolanyşygyna bagly:*\n"
        "Toparyňyzyň umumy PV-si näçe ýokary bolsa — status şonça ýokary we bonuslar şonça köp. "
        "Ýagny: girdejüňiz topar bilen bilelikde awtomatiki ösýär.\n\n"
        "Ilkinji günden 4 bonus elýeterli:\n\n"
        "1️⃣ *BZP* — hyzmatdaşyň her satyn alşyndan 40%\n"
        "2️⃣ *Klub bonusy* — birinji liniýa göwrümi üçin 55 ýa-da 110 UE\n"
        "3️⃣ *KBB* — şahalarda 40+40 PV her sikl üçin bonus\n"
        "4️⃣ *BZK* — täze statusa ýetmek üçin bir gezek töleg\n\n"
        "1 UE = 15 manat (TKM) / 10 000 sum (UZB)\n\n"
        "Bota sorag ber — islendik bonusy düşündirer 🌿"
    ),
    "uz": (
        "📊 *Vertera marketingi*\n\n"
        "*PV nima?*\n"
        "PV (Product Value) — mahsulot ballari. Har bir mahsulotning o'z PV qiymati bor. "
        "Tizimdagi barcha bonuslar PV orqali hisoblanadi.\n\n"
        "*Bonuslar jamoa tovar aylanmasiga bog'liq:*\n"
        "Jamoangiznig umumiy PV-si qanchalik yuqori bo'lsa — status shunchalik yuqori va bonuslar ko'proq. "
        "Ya'ni: daromadingiz jamoa bilan birga avtomatik o'sadi.\n\n"
        "Birinchi kundan 4 ta bonus mavjud:\n\n"
        "1️⃣ *BZP* — hamkorning har xarididan 40%\n"
        "2️⃣ *Klub bonusi* — birinchi liniya hajmi uchun 55 yoki 110 UE\n"
        "3️⃣ *KBB* — tarmoqlarda 40+40 PV har sikl uchun bonus\n"
        "4️⃣ *BZK* — yangi statusga erishganda bir martalik to'lov\n\n"
        "1 UE = 15 manat (TKM) / 10 000 so'm (UZB)\n\n"
        "Botga savol ber — istalgan bonusni tushuntiradi 🌿"
    ),
}

LEARN_FULL = {
    "ru": (
        "📚 *Обучение партнёра*\n\n"
        "*Шаг 1 — Изучи продукт*\n"
        "Попробуй все продукты сам. Только личный опыт убеждает.\n\n"
        "*Шаг 2 — Изучи систему бонусов*\n"
        "БЗП → Клубный бонус → КББ → БЗК\n"
        "Нажми «📊 Маркетинг» для подробного разбора.\n\n"
        "*Шаг 3 — Первые шаги*\n"
        "• Составь список из 20 знакомых\n"
        "• Расскажи о продукте 5 из них\n"
        "• Пригласи 2 в команду (левая и правая ветка)\n\n"
        "*Шаг 4 — Веди контакты*\n"
        "Добавляй клиентов в «👥 Мои контакты» и следи за статусом 🌿\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "📅 *ZOOM-вебинар с наставником*\n"
        "Хотите познакомиться с командой, задать вопросы и получить поддержку лично?\n"
        "Запишитесь на вебинар — нажмите кнопку ниже 👇"
    ),
    "tk": (
        "📚 *Hyzmatdaş okuwы*\n\n"
        "*Ädim 1 — Önümi öwren*\n"
        "Ähli önümleri özüň synap gör. Diňe şahsy tejribe ynandyrýar.\n\n"
        "*Ädim 2 — Bonus ulgamyny öwren*\n"
        "BZP → Klub bonusy → KBB → BZK\n"
        "Jikme-jik üçin «📊 Marketing» saýlaň.\n\n"
        "*Ädim 3 — Ilkinji ädimler*\n"
        "• 20 tanşyň sanawyny düz\n"
        "• Olaryň 5-ine önüm barada aýt\n"
        "• 2-sini topara çagyr (çep we sag şaha)\n\n"
        "*Ädim 4 — Kontaktlary ýöret*\n"
        "Müşderileri «👥 Meniň kontaktlarym»-a goş 🌿\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "📅 *Halypa bilen ZOOM-webinar*\n"
        "Topar bilen tanyşmak, sorag bermek we goldaw almak isleýärsiňizmi?\n"
        "Webinara ýazylyň — aşakdaky düwmä basyň 👇"
    ),
    "uz": (
        "📚 *Hamkor o'qitish*\n\n"
        "*Qadam 1 — Mahsulotni o'rgan*\n"
        "Barcha mahsulotlarni o'zing sinab ko'r. Faqat shaxsiy tajriba ishontiradi.\n\n"
        "*Qadam 2 — Bonus tizimini o'rgan*\n"
        "BZP → Klub bonusi → KBB → BZK\n"
        "Batafsil uchun «📊 Marketing» tanlang.\n\n"
        "*Qadam 3 — Birinchi qadamlar*\n"
        "• 20 tanishdan ro'yxat tuzing\n"
        "• Ulardan 5 tasiga mahsulot haqida ayting\n"
        "• 2 tasini jamoaga taklif qiling (chap va o'ng tarmoq)\n\n"
        "*Qadam 4 — Kontaktlarni boshqaring*\n"
        "Mijozlarni «👥 Mening kontaktlarim»ga qo'shing 🌿\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "📅 *Murabbiy bilan ZOOM-vebinar*\n"
        "Jamoa bilan tanishish, savol berish va yordam olishni xohlaysizmi?\n"
        "Vebinarga yoziling — quyidagi tugmani bosing 👇"
    ),
}

async def partner_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка кнопок внутри партнёрского меню."""
    lang = context.user_data.get("lang", "ru")
    user = update.effective_user
    text = update.message.text
    p    = PT.get(lang, PT["ru"])

    # Выход
    if text == p["btn_back"]:
        await update.message.reply_text(
            TEXTS[lang]["welcome"], parse_mode="Markdown",
            reply_markup=get_main_keyboard(lang)
        )
        return CHAT

    # Обучение — с предложением вебинара
    if text == p["btn_learn"]:
        learn_kb = ReplyKeyboardMarkup(
            [[p["btn_webinar"]], [p["btn_back"]]],
            resize_keyboard=True
        )
        await update.message.reply_text(
            LEARN_FULL.get(lang, LEARN_FULL["ru"]),
            parse_mode="Markdown",
            reply_markup=learn_kb
        )
        return PARTNER_MENU

    # Маркетинг — с PV и товарооборотом
    if text == p["btn_market"]:
        await update.message.reply_text(
            MARKET_FULL.get(lang, MARKET_FULL["ru"]),
            parse_mode="Markdown",
            reply_markup=get_partner_kb(lang)
        )
        return PARTNER_MENU

    # Вебинар — записаться
    if text == p.get("btn_webinar", ""):
        context.user_data["webinar_wait"] = True
        await update.message.reply_text(
            p.get("webinar_ask", "Введите имя и удобное время:"),
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardRemove()
        )
        return PARTNER_MENU

    if context.user_data.pop("webinar_wait", False):
        uname = f"@{user.username}" if user.username else str(user.id)
        # Сохраняем в локальный файл
        webinar_add(user.id, user.full_name or uname, text, uname)
        # Сохраняем в Google Sheets
        try:
            async with httpx.AsyncClient() as hc:
                await hc.post(GOOGLE_SHEET_URL, json={
                    "type":     "webinar",
                    "user_id":  str(user.id),
                    "name":     user.full_name or uname,
                    "username": uname,
                    "text":     text,
                    "lang":     lang,
                }, timeout=10)
        except Exception as e:
            logger.error(f"webinar sheets: {e}")
        try:
            await context.bot.send_message(
                chat_id=MANAGER_CHAT_ID,
                text=f"📅 Заявка на вебинар\n\n"
                     f"👤 {user.full_name or uname}\n"
                     f"🆔 {uname}\n"
                     f"📝 {text}"
            )
        except Exception as e:
            logger.error(f"webinar notify: {e}")
        await update.message.reply_text(
            p.get("webinar_ok", "✅ Заявка отправлена!"),
            reply_markup=get_partner_kb(lang)
        )
        return PARTNER_MENU

    # Контакты
    if text == p["btn_contacts"]:
        contacts = contacts_get(user.id)
        if not contacts:
            msg = p["c_empty"]
        else:
            lines = [f"👤 {c['name']} | 📞 {c['phone']} | {c['status']}" for c in contacts]
            msg   = "👥 *Ваши контакты:*\n\n" + "\n".join(lines)
        kb = ReplyKeyboardMarkup([[p["c_add"]], [p["btn_back"]]], resize_keyboard=True)
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=kb)
        return PARTNER_MENU

    if text == p["c_add"]:
        await update.message.reply_text(p["c_name"], parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())
        return PARTNER_CONTACTS_NAME

    # Новости — показываем последнюю из хранилища
    if text == p["btn_news"]:
        latest = news_get_latest()
        if latest:
            await update.message.reply_text(
                f"📰 *Последняя новость:*\n\n{latest}",
                parse_mode="Markdown",
                reply_markup=get_partner_kb(lang)
            )
        else:
            await update.message.reply_text(p["news"], reply_markup=get_partner_kb(lang))
        return PARTNER_MENU

    # Любой другой текст — остаёмся в меню
    await update.message.reply_text(p["menu_title"], reply_markup=get_partner_kb(lang))
    return PARTNER_MENU


async def partner_contacts_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "ru")
    p    = PT.get(lang, PT["ru"])
    context.user_data["c_name"] = update.message.text.strip()
    await update.message.reply_text(p["c_phone"], parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())
    return PARTNER_CONTACTS_PHONE


async def partner_contacts_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang  = context.user_data.get("lang", "ru")
    user  = update.effective_user
    p     = PT.get(lang, PT["ru"])
    name  = context.user_data.pop("c_name", "—")
    phone = update.message.text.strip()
    contact_add(user.id, name, phone)
    await update.message.reply_text(p["c_saved"], reply_markup=get_partner_kb(lang))
    return PARTNER_MENU


async def partner_approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/apXXXXX — одобрить партнёра."""
    if update.effective_user.id != MANAGER_CHAT_ID:
        return
    try:
        uid  = int(update.message.text.strip()[3:])
    except ValueError:
        await update.message.reply_text("Неверный формат."); return
    info = pending_get(uid)
    if not info:
        await update.message.reply_text("Запрос не найден."); return
    partner_add(uid, info.get("name",""), info.get("cid",""), info.get("lang","ru"))
    pending_del(uid)
    lang  = info.get("lang","ru")
    uname = info.get("uname","")
    p     = PT.get(lang, PT["ru"])
    # Сохраняем в Google Sheets (постоянное хранение)
    await partner_add_sheets(uid, info.get("name",""), info.get("cid",""), lang, uname)
    try:
        await context.bot.send_message(
            chat_id=uid, text=p["approved"],
            reply_markup=get_partner_kb(lang)
        )
        # Запускаем серию напоминаний
        schedule_partner_reminders(context, uid, lang)
    except Exception as e:
        logger.error(f"approve send: {e}")
    await update.message.reply_text(f"✅ {info.get('name')} одобрен как партнёр!")


async def partner_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/rjXXXXX — отклонить запрос."""
    if update.effective_user.id != MANAGER_CHAT_ID:
        return
    try:
        uid  = int(update.message.text.strip()[3:])
    except ValueError:
        await update.message.reply_text("Неверный формат."); return
    info = pending_get(uid)
    if not info:
        await update.message.reply_text("Запрос не найден."); return
    pending_del(uid)
    lang = info.get("lang","ru")
    p    = PT.get(lang, PT["ru"])
    try:
        await context.bot.send_message(chat_id=uid, text=p["rejected"])
    except Exception as e:
        logger.error(f"reject send: {e}")
    await update.message.reply_text(f"❌ Запрос от {info.get('name')} отклонён.")


# ─── Напоминания для партнёров ───────────────────────────────

async def send_partner_reminder(context) -> None:
    """Job: отправляет одно напоминание партнёру."""
    job     = context.job
    uid     = job.data["uid"]
    lang    = job.data["lang"]
    msg_key = job.data["msg_key"]
    p       = PT.get(lang, PT["ru"])
    text    = p.get(msg_key, "")
    if not text:
        return
    try:
        await context.bot.send_message(chat_id=uid, text=text)
    except Exception as e:
        logger.error(f"partner reminder {uid}/{msg_key}: {e}")

def schedule_partner_reminders(context, uid: int, lang: str):
    """Планирует серию напоминаний после одобрения партнёра."""
    base = f"prem_{uid}"
    # Через 1 день — обзвонил ли контакты?
    context.job_queue.run_once(
        send_partner_reminder, when=86400,
        data={"uid": uid, "lang": lang, "msg_key": "r_contacts"},
        name=f"{base}_contacts", chat_id=uid, user_id=uid
    )
    # Через 2 дня — изучил ли маркетинг?
    context.job_queue.run_once(
        send_partner_reminder, when=172800,
        data={"uid": uid, "lang": lang, "msg_key": "r_market"},
        name=f"{base}_market", chat_id=uid, user_id=uid
    )
    # Через 3 дня — изучил ли продукты?
    context.job_queue.run_once(
        send_partner_reminder, when=259200,
        data={"uid": uid, "lang": lang, "msg_key": "r_product"},
        name=f"{base}_product", chat_id=uid, user_id=uid
    )
    # Через 5 дней — попробовал ли продукт?
    context.job_queue.run_once(
        send_partner_reminder, when=432000,
        data={"uid": uid, "lang": lang, "msg_key": "r_try"},
        name=f"{base}_try", chat_id=uid, user_id=uid
    )

# ─── Меню администратора ─────────────────────────────────────

ADMIN_KB = ReplyKeyboardMarkup(
    [["👥 Список партнёров",  "📋 Заявки на вебинар"],
     ["📰 Добавить новость",  "🎥 Отправить кружок"],
     ["📣 Рассылка партнёрам","🔙 Выход из админ-меню"]],
    resize_keyboard=True
)

async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/admin — открыть меню администратора."""
    if update.effective_user.id != MANAGER_CHAT_ID:
        return
    await update.message.reply_text(
        "👑 *Меню администратора*\n\nВыберите действие:",
        parse_mode="Markdown",
        reply_markup=ADMIN_KB
    )
    return ADMIN_MENU

async def admin_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает кнопки admin-меню (только для менеджера)."""
    if update.effective_user.id != MANAGER_CHAT_ID:
        await update.message.reply_text(
            TEXTS[context.user_data.get("lang","ru")]["welcome"],
            parse_mode="Markdown",
            reply_markup=get_main_keyboard(context.user_data.get("lang","ru"))
        )
        return CHAT
    text = update.message.text

    if text == "🔙 Выход из админ-меню":
        await update.message.reply_text(
            "Вышли из меню администратора.",
            reply_markup=ReplyKeyboardRemove()
        )
        return CHAT

    # Список одобренных партнёров
    if text == "👥 Список партнёров":
        partners = _jload(_PARTNERS_F)
        if not partners:
            await update.message.reply_text("Партнёров пока нет.", reply_markup=ADMIN_KB)
            return ADMIN_MENU
        lines = []
        for uid, info in partners.items():
            lines.append(f"• {info.get('name','—')} | ID: {info.get('cid','—')} | {info.get('lang','—')} | tg: {uid}")
        msg = f"👥 *Партнёры ({len(lines)}):*\n\n" + "\n".join(lines)
        # Разбиваем если длинный
        if len(msg) > 3500:
            chunks = [lines[i:i+20] for i in range(0, len(lines), 20)]
            for chunk in chunks:
                await update.message.reply_text("\n".join(chunk), reply_markup=ADMIN_KB)
        else:
            await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=ADMIN_KB)
        return ADMIN_MENU

    # Заявки на вебинар
    if text == "📋 Заявки на вебинар":
        webinars = webinar_get_all()
        if not webinars:
            await update.message.reply_text("Заявок на вебинар пока нет.", reply_markup=ADMIN_KB)
            return ADMIN_MENU
        lines = []
        for w in webinars:
            lines.append(
                f"• {w.get('date','—')} | {w.get('name','—')} | {w.get('uname','—')}\n"
                f"  📝 {w.get('text','—')}"
            )
        msg = f"📋 *Заявки на вебинар ({len(lines)}):*\n\n" + "\n\n".join(lines)
        # Разбиваем если слишком длинный
        if len(msg) > 4000:
            for i in range(0, len(lines), 10):
                chunk = "\n\n".join(lines[i:i+10])
                await update.message.reply_text(chunk, reply_markup=ADMIN_KB)
        else:
            await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=ADMIN_KB)
        return ADMIN_MENU

    # Новость — сохраняем и сразу отправляем всем партнёрам
    if text == "📰 Добавить новость":
        context.user_data["admin_news"] = True
        await update.message.reply_text(
            "📰 Введите текст новости — она сохранится и сразу придёт всем партнёрам:",
            reply_markup=ReplyKeyboardRemove()
        )
        return ADMIN_MENU

    if context.user_data.pop("admin_news", False):
        news_save(text)
        partners = _jload(_PARTNERS_F)
        sent = failed = 0
        for uid, info in partners.items():
            lang_p = info.get("lang", "ru")
            header = {"ru": "📰 *Новости Vertera:*", "tk": "📰 *Vertera habarlary:*", "uz": "📰 *Vertera yangiliklari:*"}.get(lang_p, "📰 *Новости Vertera:*")
            try:
                await context.bot.send_message(
                    chat_id=int(uid),
                    text=f"{header}\n\n{text}",
                    parse_mode="Markdown"
                )
                sent += 1
            except Exception:
                failed += 1
        await update.message.reply_text(
            f"✅ Новость опубликована! Отправлено: {sent} партнёрам | Ошибок: {failed}",
            reply_markup=ADMIN_KB
        )
        return ADMIN_MENU

    # Рассылка
    if text == "📣 Рассылка партнёрам":
        context.user_data["admin_broadcast"] = True
        await update.message.reply_text(
            "✏️ Введите текст рассылки — он уйдёт всем партнёрам:",
            reply_markup=ReplyKeyboardRemove()
        )
        return ADMIN_MENU

    if context.user_data.pop("admin_broadcast", False):
        partners = _jload(_PARTNERS_F)
        sent = failed = 0
        for uid in partners:
            try:
                await context.bot.send_message(
                    chat_id=int(uid),
                    text=f"📣 *Сообщение от команды Vertera:*\n\n{text}",
                    parse_mode="Markdown"
                )
                sent += 1
            except Exception:
                failed += 1
        await update.message.reply_text(
            f"✅ Рассылка завершена! Отправлено: {sent} | Ошибок: {failed}",
            reply_markup=ADMIN_KB
        )
        return ADMIN_MENU

    # Кружок
    if text == "🎥 Отправить кружок":
        context.user_data["admin_circle"] = True
        await update.message.reply_text(
            "🎥 Отправьте видео-кружок — я перешлю всем партнёрам:",
            reply_markup=ReplyKeyboardRemove()
        )
        return ADMIN_MENU

    await update.message.reply_text("Выберите действие из меню:", reply_markup=ADMIN_KB)
    return ADMIN_MENU

async def admin_circle_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получаем кружок от admin и рассылаем партнёрам."""
    if update.effective_user.id != MANAGER_CHAT_ID:
        return
    if not context.user_data.pop("admin_circle", False):
        return
    if not update.message.video_note:
        await update.message.reply_text("Это не кружок. Попробуйте снова.", reply_markup=ADMIN_KB)
        return
    partners = _jload(_PARTNERS_F)
    sent, failed = 0, 0
    fid = update.message.video_note.file_id
    for uid in partners:
        try:
            await context.bot.send_video_note(chat_id=int(uid), video_note=fid)
            sent += 1
        except Exception:
            failed += 1
    await update.message.reply_text(
        f"✅ Кружок отправлен! Отправлено: {sent} | Ошибок: {failed}",
        reply_markup=ADMIN_KB
    )
    return ADMIN_MENU

# ─── main ─────────────────────────────────────────────────────
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CommandHandler("admin", admin_cmd),
        ],
        states={
            SELECT_COUNTRY:        [MessageHandler(filters.TEXT & ~filters.COMMAND, select_country)],
            SELECT_LANG:           [MessageHandler(filters.TEXT & ~filters.COMMAND, select_lang)],
            CHAT:                  [MessageHandler(filters.TEXT & ~filters.COMMAND, chat_with_gpt)],
            PARTNER_ID:            [MessageHandler(filters.TEXT & ~filters.COMMAND, partner_receive_id)],
            PARTNER_MENU:          [MessageHandler(filters.TEXT & ~filters.COMMAND, partner_menu_handler)],
            PARTNER_CONTACTS_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, partner_contacts_name)],
            PARTNER_CONTACTS_PHONE:[MessageHandler(filters.TEXT & ~filters.COMMAND, partner_contacts_phone)],
            ANKETA_NAME:           [MessageHandler(filters.TEXT & ~filters.COMMAND, anketa_name)],
            ANKETA_PHONE:          [MessageHandler(filters.TEXT & ~filters.COMMAND, anketa_phone)],
            ANKETA_CITY:           [MessageHandler(filters.TEXT & ~filters.COMMAND, anketa_city)],
            ANKETA_INTEREST:       [MessageHandler(filters.TEXT & ~filters.COMMAND, anketa_interest)],
            ADMIN_MENU:            [
                MessageHandler(filters.VIDEO_NOTE, admin_circle_handler),
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_handler),
            ],
        },
        fallbacks=[CommandHandler("start", start)],
        allow_reentry=True
    )
    app.add_handler(conv)

    # /apXXXXX и /rjXXXXX — одобрение/отклонение вне ConversationHandler
    app.add_handler(MessageHandler(filters.Regex(r"^/ap[0-9]+$"), partner_approve))
    app.add_handler(MessageHandler(filters.Regex(r"^/rj[0-9]+$"), partner_reject))

    logger.info("🤖 Vertera bot started!")

    # Загружаем партнёров из Google Sheets при старте
    import asyncio
    asyncio.get_event_loop().run_until_complete(load_partners_from_sheets())

    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
