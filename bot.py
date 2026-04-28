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
SELECT_COUNTRY, SELECT_LANG, CHAT, ANKETA_NAME, ANKETA_PHONE, ANKETA_CITY, ANKETA_INTEREST, PARTNER_ID, PARTNER_MENU, PARTNER_CONTACTS_NAME, PARTNER_CONTACTS_PHONE, ADMIN_MENU, PARTNER_QUIZ = range(13)

user_histories = {}

import json, pathlib

# ─── Партнёрская база данных ─────────────────────────────────
_PARTNERS_F  = pathlib.Path("/tmp/vrt_partners.json")
_PENDING_F   = pathlib.Path("/tmp/vrt_pending.json")
_CONTACTS_F  = pathlib.Path("/tmp/vrt_contacts.json")
_WEBINAR_F   = pathlib.Path("/tmp/vrt_webinar.json")
_NEWS_F      = pathlib.Path("/tmp/vrt_news.json")
_PROGRESS_F  = pathlib.Path("/tmp/vrt_progress.json")
_MKTPROG_F   = pathlib.Path("/tmp/vrt_mkt_progress.json")
_QUIZ_F      = pathlib.Path("/tmp/vrt_quiz.json")
_MKTPROG_F   = pathlib.Path("/tmp/vrt_mkt_progress.json")
_QUIZ_F      = pathlib.Path("/tmp/vrt_quiz.json")
_USERS_F     = pathlib.Path("/tmp/vrt_users.json")

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
# ─── Прогресс 7 дней ─────────────────────────────────────────

def user_register(uid: int, lang: str, country: str, name: str, uname: str):
    """Регистрирует пользователя при первом старте бота."""
    d = _jload(_USERS_F)
    if str(uid) not in d:
        d[str(uid)] = {"lang": lang, "country": country, "name": name, "uname": uname}
        _jsave(_USERS_F, d)

def users_get_all() -> dict:
    return _jload(_USERS_F)

async def user_register_sheets(uid: int, lang: str, country: str, name: str, uname: str):
    """Сохраняет нового пользователя в Google Sheets."""
    try:
        async with httpx.AsyncClient(follow_redirects=True) as c:
            await c.post(GOOGLE_SHEET_URL, json={
                "type":    "user",
                "user_id": str(uid),
                "lang":    lang,
                "country": country,
                "name":    name,
                "username": uname,
            }, timeout=10)
    except Exception as e:
        logger.error(f"user_register_sheets: {e}")

async def users_load_from_sheets():
    """Загружает всех пользователей из Sheets при старте."""
    try:
        async with httpx.AsyncClient(follow_redirects=True) as c:
            resp = await c.post(GOOGLE_SHEET_URL,
                                json={"type": "get_users"}, timeout=15)
            data = resp.json()
            if data.get("status") == "ok" and data.get("users"):
                d = _jload(_USERS_F)
                for u in data["users"]:
                    uid = str(u.get("user_id","")).strip()
                    if uid:
                        d[uid] = {
                            "lang":    u.get("lang","ru"),
                            "country": u.get("country","TKM"),
                            "name":    u.get("name",""),
                            "uname":   u.get("username",""),
                        }
                _jsave(_USERS_F, d)
                logger.info(f"✅ Загружено {len(data['users'])} пользователей из Sheets")
    except Exception as e:
        logger.error(f"users_load_from_sheets: {e}")

def progress_get(uid: int) -> int:
    """Возвращает текущий день партнёра (0 = не начал, 1-7 = день)."""
    d = _jload(_PROGRESS_F)
    return int(d.get(str(uid), {}).get("day", 0))

def progress_set(uid: int, day: int):
    """Устанавливает текущий день."""
    d = _jload(_PROGRESS_F)
    d[str(uid)] = {"day": day}
    _jsave(_PROGRESS_F, d)


def mkt_progress_get(uid):
    return int(_jload(_MKTPROG_F).get(str(uid), {}).get("day", 0))

def mkt_progress_set(uid, day):
    d = _jload(_MKTPROG_F); d[str(uid)] = {"day": day}; _jsave(_MKTPROG_F, d)

async def mkt_progress_sync(uid, day, name, uname):
    try:
        async with httpx.AsyncClient(follow_redirects=True) as c:
            await c.post(GOOGLE_SHEET_URL, json={"type":"mkt_progress","user_id":str(uid),"name":name,"username":uname,"day":day}, timeout=10)
    except Exception as e:
        logger.error(f"mkt_sync: {e}")

async def mkt_progress_load():
    try:
        async with httpx.AsyncClient(follow_redirects=True) as c:
            resp = await c.post(GOOGLE_SHEET_URL, json={"type":"get_mkt_progress"}, timeout=15)
            data = resp.json()
            if data.get("status") == "ok":
                d = _jload(_MKTPROG_F)
                for row in data.get("progress", []):
                    uid = str(row.get("user_id","")).strip()
                    if uid: d[uid] = {"day": int(row.get("day",0))}
                _jsave(_MKTPROG_F, d)
    except Exception as e:
        logger.error(f"mkt_load: {e}")

def quiz_get(uid):
    return _jload(_QUIZ_F).get(str(uid), {})

def quiz_set(uid, qname, score, total):
    d = _jload(_QUIZ_F)
    if str(uid) not in d: d[str(uid)] = {}
    d[str(uid)][qname] = {"score": score, "total": total}
    _jsave(_QUIZ_F, d)

async def quiz_sync(uid, qname, score, total, name, uname):
    try:
        async with httpx.AsyncClient(follow_redirects=True) as c:
            await c.post(GOOGLE_SHEET_URL, json={"type":"quiz_result","user_id":str(uid),"name":name,"username":uname,"quiz":qname,"score":score,"total":total}, timeout=10)
    except Exception as e:
        logger.error(f"quiz_sync: {e}")

async def quiz_load():
    try:
        async with httpx.AsyncClient(follow_redirects=True) as c:
            resp = await c.post(GOOGLE_SHEET_URL, json={"type":"get_quiz"}, timeout=15)
            data = resp.json()
            if data.get("status") == "ok":
                d = _jload(_QUIZ_F)
                for row in data.get("results", []):
                    uid = str(row.get("user_id","")).strip()
                    qn = row.get("quiz","")
                    if uid and qn:
                        if uid not in d: d[uid] = {}
                        d[uid][qn] = {"score": row.get("score",0), "total": row.get("total",0)}
                _jsave(_QUIZ_F, d)
    except Exception as e:
        logger.error(f"quiz_load: {e}")

async def progress_sync_to_sheets(uid: int, day: int, name: str, uname: str):
    """Сохраняет прогресс в Google Sheets."""
    try:
        async with httpx.AsyncClient(follow_redirects=True) as c:
            await c.post(GOOGLE_SHEET_URL, json={
                "type":     "progress",
                "user_id":  str(uid),
                "name":     name,
                "username": uname,
                "day":      day,
            }, timeout=10)
    except Exception as e:
        logger.error(f"progress_sync: {e}")

async def progress_load_from_sheets():
    """Загружает прогресс всех партнёров из Sheets при старте."""
    try:
        async with httpx.AsyncClient(follow_redirects=True) as c:
            resp = await c.post(GOOGLE_SHEET_URL,
                                json={"type": "get_progress"}, timeout=15)
            data = resp.json()
            if data.get("status") == "ok" and data.get("progress"):
                d = _jload(_PROGRESS_F)
                for row in data["progress"]:
                    uid = str(row.get("user_id", "")).strip()
                    day = int(row.get("day", 0))
                    if uid:
                        d[uid] = {"day": day}
                _jsave(_PROGRESS_F, d)
                logger.info(f"✅ Прогресс {len(data['progress'])} партнёров загружен")
    except Exception as e:
        logger.error(f"progress_load: {e}")

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
        "btn_quiz":         "🧪 Тесты",
        "btn_review_learn": "📖 Просмотреть обучение",
        "btn_review_mkt":   "📖 Просмотреть маркетинг",
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
        "btn_quiz":         "🧪 Testler",
        "btn_review_learn": "📖 Okuwы syn etmek",
        "btn_review_mkt":   "📖 Marketingi syn etmek",
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
        "btn_quiz":         "🧪 Testlar",
        "btn_review_learn": "📖 O'qitishni ko'rish",
        "btn_review_mkt":   "📖 Marketingni ko'rish",
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
         [p["btn_quiz"],     p["btn_contacts"]],
         [p["btn_webinar"],  p["btn_news"]],
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
async def load_all_on_start(app=None):
    """Загружает партнёров и прогресс из Google Sheets при старте."""
    await progress_load_from_sheets()

async def _load_partners_impl(app=None):
    """Загружает партнёров из Google Sheets в локальный кэш при старте."""
    try:
        # Используем POST с type=get_partners (обходим проблему с GET/403)
        async with httpx.AsyncClient(follow_redirects=True) as c:
            resp = await c.post(
                GOOGLE_SHEET_URL,
                json={"type": "get_partners"},
                timeout=15
            )
            data = resp.json()
            if data.get("status") == "ok" and data.get("partners"):
                existing = _jload(_PARTNERS_F)
                count = 0
                for p in data["partners"]:
                    uid = str(p.get("user_id", "")).strip()
                    if uid:
                        existing[uid] = {
                            "name": p.get("name", ""),
                            "cid":  p.get("company_id", ""),
                            "lang": p.get("lang", "ru"),
                        }
                        count += 1
                _jsave(_PARTNERS_F, existing)
                logger.info(f"✅ Загружено {count} партнёров из Google Sheets")
            else:
                logger.info(f"Sheets ответил: {data}")
    except Exception as e:
        logger.error(f"load_partners error: {e}")
    await progress_load_from_sheets()
    await mkt_progress_load()
    await quiz_load()
    await users_load_from_sheets()

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
    # Регистрируем пользователя в общей базе
    uname_r = f"@{user.username}" if user.username else str(user.id)
    user_register(user.id, lang, country, user.full_name or uname_r, uname_r)
    await user_register_sheets(user.id, lang, country, user.full_name or uname_r, uname_r)

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
    if text in NO:
        await update.message.reply_text(t["anketa_ok"], reply_markup=get_main_keyboard(lang))
        return CHAT
    if text in YES:
        await update.message.reply_text(t["anketa_start"], reply_markup=ReplyKeyboardRemove())
        return ANKETA_NAME

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

# ══════════════════════════════════════════════════════════════
# 7 ДНЕЙ МАРКЕТИНГА
# ══════════════════════════════════════════════════════════════
MKT_DAYS = {
    1: {
        "ru": ("📊 *Маркетинг — День 1: Основные понятия*\n\n"
               "Прежде чем зарабатывать — нужно говорить на языке системы.\n\n"
               "📌 *PV (Personal Volume)* — баллы продукта. Каждый товар имеет ценность в PV. Все бонусы считаются именно через PV.\n\n"
               "📌 *UE* — единая расчётная валюта.\n• 1 UE = 15 манат (Туркменистан)\n• 1 UE = 10 000 сум (Узбекистан)\n\n"
               "📌 *ЛО (Личный объём)* — сумма PV твоих личных покупок за месяц.\n\n"
               "📌 *ГО (Групповой объём)* — суммарный PV всех покупок твоей команды.\n\n"
               "📌 *Клиент* — покупает для себя, менее 20 PV. Скидка 30%.\n\n"
               "📌 *Партнёр* — покупка от 20 PV. Получает бонусы и скидку 30%.\n\n"
               "📌 *Наставник* — партнёр, зарегистрировавший нового партнёра под свой ID.\n\n"
               "📌 *ID* — твой уникальный регистрационный номер в системе Vertera.\n\n"
               "✅ Понял основные понятия? Нажми кнопку ниже 👇"),
        "tk": ("📊 *Marketing — 1-nji gün: Esasy düşünjeler*\n\n"
               "📌 *PV* — önüm ballary. Ähli bonuslar PV arkaly hasaplanýar.\n\n"
               "📌 *UE* — ýeke hasaplaşyk walýutasy.\n• 1 UE = 15 manat (TKM)\n• 1 UE = 10 000 sum (UZB)\n\n"
               "📌 *ÝO* — şahsy satyn alyşlaryňyzyň aýlyk PV jemi.\n\n"
               "📌 *GO* — toparyňyzyň ähli satyn alyşlarynyň PV jemi.\n\n"
               "📌 *Müşderi* — 20 PV-den az. 30% arzanladyş.\n\n"
               "📌 *Hyzmatdaş* — 20 PV we ýokary. Bonuslar + 30% arzanladyş.\n\n"
               "📌 *Halypa* — täze hyzmatdaşy öz ID-si bilen hasaba alan.\n\n"
               "✅ Esasy düşünjeleri özleşdirdiňmi? Bas 👇"),
        "uz": ("📊 *Marketing — 1-kun: Asosiy tushunchalar*\n\n"
               "📌 *PV* — mahsulot ballari. Barcha bonuslar PV orqali hisoblanadi.\n\n"
               "📌 *UE* — yagona hisob valyutasi.\n• 1 UE = 15 manat (TKM)\n• 1 UE = 10 000 so'm (UZB)\n\n"
               "📌 *LO* — oylik shaxsiy xaridlaringizning PV yig'indisi.\n\n"
               "📌 *GO* — jamoangiz barcha xaridlarining umumiy PV-si.\n\n"
               "📌 *Mijoz* — 20 PV dan kam. 30% chegirma.\n\n"
               "📌 *Hamkor* — 20 PV va ko'proq. Bonuslar + 30% chegirma.\n\n"
               "📌 *Murabbiy* — yangi hamkorni o'z ID-si ostida ro'yxatdan o'tkazgan.\n\n"
               "✅ Asosiy tushunchalarni o'rgandingmi? Bos 👇"),
    },
    2: {
        "ru": ("📊 *Маркетинг — День 2: Активность*\n\n"
               "⚡ Главное правило: без активности — нет дохода!\n\n"
               "🔹 *Личная активность* — покупка от 20 PV. Открывает право на бонусы на 30 дней.\n\n"
               "🔹 *Лидерская активность* — покупка от 40 PV за месяц. Открывает дополнительные вознаграждения.\n\n"
               "🔹 *Бинарная активность* — минимум 2 лично приглашённых партнёра (по 1 в каждую ветку) с активностью 20 PV.\n\n"
               "📊 *Три уровня активности:*\n"
               "• Личная (20 PV) → базовый доход\n"
               "• Лидерская (40 PV) → доп. бонусы\n"
               "• Бинарная (2 партнёра 20 PV) → КББ\n\n"
               "💡 Делай покупку в начале месяца — не теряй активность!\n\n"
               "✅ Запомнил? Нажми кнопку ниже 👇"),
        "tk": ("📊 *Marketing — 2-nji gün: Işjeňlik*\n\n"
               "⚡ Esasy düzgün: işjeňliksiz — girdeji ýok!\n\n"
               "🔹 *Şahsy işjeňlik* — 20 PV-den satyn alyş. 30 gün bonus hukugy.\n\n"
               "🔹 *Lider işjeňligi* — aýda 40 PV-den satyn alyş. Goşmaça sylaglar.\n\n"
               "🔹 *Binar işjeňligi* — her şahada 1-den, 2 hyzmatdaş 20 PV ýerine ýetirmeli.\n\n"
               "📊 *Üç dereje:*\n• Şahsy (20 PV) → esasy\n• Lider (40 PV) → goşmaça\n• Binar (2×20 PV) → KBB\n\n"
               "✅ Ýatladyňmy? Bas 👇"),
        "uz": ("📊 *Marketing — 2-kun: Faollik*\n\n"
               "⚡ Asosiy qoida: faoliksiz — daromad yo'q!\n\n"
               "🔹 *Shaxsiy faollik* — 20 PV dan xarid. 30 kun bonus huquqi.\n\n"
               "🔹 *Lider faolligi* — oyda 40 PV dan xarid. Qo'shimcha mukofotlar.\n\n"
               "🔹 *Binar faolligi* — har tarmoqda 1 tadan, 2 hamkor 20 PV bajarishi.\n\n"
               "📊 *Uch daraja:*\n• Shaxsiy (20 PV) → asosiy\n• Lider (40 PV) → qo'shimcha\n• Binar (2×20 PV) → KBB\n\n"
               "✅ Esladingmi? Bos 👇"),
    },
    3: {
        "ru": ("📊 *Маркетинг — День 3: Бонус за приглашение (БЗП)*\n\n"
               "💰 *БЗП = 40%* от PV с каждой покупки партнёров первой линии\n\n"
               "📊 *Примеры:*\n• 20 PV → 8 UE = 120 манат\n• 40 PV → 16 UE = 240 манат\n• 100 PV → 40 UE = 600 манат\n• 200 PV → 80 UE = 1 200 манат\n\n"
               "✅ *Условие:* личная активность (20 PV). Бонус — моментально!\n\n"
               "⚠️ *Перелив:* если у наставника нет активности — БЗП уходит вверх через 24 часа.\n\n"
               "🔄 Бонус начисляется за ВСЕ покупки первой линии — первую и все последующие.\n\n"
               "💡 Больше активных партнёров в первой линии = больше пассивного дохода!\n\n"
               "✅ Понял БЗП? Нажми кнопку ниже 👇"),
        "tk": ("📊 *Marketing — 3-nji gün: Çakylyk bonusy (BZP)*\n\n"
               "💰 *BZP = 40%* birinji liniýadaky her satyn alşyndan\n\n"
               "📊 *Mysallar:*\n• 20 PV → 8 UE\n• 40 PV → 16 UE\n• 100 PV → 40 UE\n• 200 PV → 80 UE\n\n"
               "✅ *Şert:* şahsy işjeňlik (20 PV). Bonus — dessine!\n\n"
               "⚠️ *Geçirme:* halypada işjeňlik ýok bolsa — BZP 24 sagatdan soň ýokary geçirilýär.\n\n"
               "💡 Birinji liniýada näçe işjeň hyzmatdaş — BZP şonça köp!\n\n"
               "✅ BZP-ni düşündiňmi? Bas 👇"),
        "uz": ("📊 *Marketing — 3-kun: Taklif bonusi (BZP)*\n\n"
               "💰 *BZP = 40%* birinchi liniya har xarididan\n\n"
               "📊 *Misollar:*\n• 20 PV → 8 UE\n• 40 PV → 16 UE\n• 100 PV → 40 UE\n• 200 PV → 80 UE\n\n"
               "✅ *Shart:* shaxsiy faollik (20 PV). Bonus — darhol!\n\n"
               "⚠️ *Ko'chirish:* murabbiyda faollik yo'q bo'lsa — BZP 24 soatdan keyin yuqoriga o'tadi.\n\n"
               "💡 Birinchi liniyada qancha faol hamkor — BZP shuncha ko'p!\n\n"
               "✅ BZP ni tushundingmi? Bos 👇"),
    },
    4: {
        "ru": ("📊 *Маркетинг — День 4: Клубная система*\n\n"
               "🏆 *Клуб 120 → 55 UE/мес*\n• ЛО от 20 PV\n• Первая линия от 120 PV\n• 25% объёма — новые клиенты\n\n"
               "🏆 *Клуб 220 → 110 UE/мес*\n• ЛО от 20 PV\n• Первая линия от 200 PV\n• 25% объёма — новые клиенты\n\n"
               "🎁 *При выполнении обоих клубов:*\n• 100% кэшбэк на все покупки\n• Участие в розыгрыше смартфона!\n\n"
               "📌 *Кэшбэк* действует 90 дней. Сгорает через 3 месяца без использования.\n\n"
               "💡 Приглашай новичков — они дают 25% от нужного объёма!\n\n"
               "✅ Запомнил клубную систему? Нажми кнопку ниже 👇"),
        "tk": ("📊 *Marketing — 4-nji gün: Klub ulgamy*\n\n"
               "🏆 *Klub 120 → aýda 55 UE*\n• ÝO 20 PV-den\n• Birinji liniýa 120 PV-den\n• 25% — täze müşderiler\n\n"
               "🏆 *Klub 220 → aýda 110 UE*\n• ÝO 20 PV-den\n• Birinji liniýa 200 PV-den\n• 25% — täze müşderiler\n\n"
               "🎁 *Iki klub ýerine ýetirilende:*\n• 100% kэşbэk\n• Smartfon bäsleşigi!\n\n"
               "💡 Täze adamlary çagyr — olar gerekli göwrümiň 25%-ini berýär!\n\n"
               "✅ Klub ulgamyny ýatladyňmy? Bas 👇"),
        "uz": ("📊 *Marketing — 4-kun: Klub tizimi*\n\n"
               "🏆 *Klub 120 → oyda 55 UE*\n• LO 20 PV dan\n• Birinchi liniya 120 PV dan\n• 25% — yangi mijozlar\n\n"
               "🏆 *Klub 220 → oyda 110 UE*\n• LO 20 PV dan\n• Birinchi liniya 200 PV dan\n• 25% — yangi mijozlar\n\n"
               "🎁 *Ikkala klub bajarilganda:*\n• 100% keshbek\n• Smartfon qur'asi!\n\n"
               "💡 Yangi odamlarni taklif qil — ular kerakli hajmning 25% ini beradi!\n\n"
               "✅ Klub tizimini esladingmi? Bos 👇"),
    },
    5: {
        "ru": ("📊 *Маркетинг — День 5: Бинар и КББ*\n\n"
               "🌳 Каждый партнёр имеет 2 ветки: левая и правая.\n\n"
               "🔄 *1 цикл* = 40 PV слева + 40 PV справа → начисляется КББ\n\n"
               "💰 *КББ по статусам:*\n"
               "• GOLD (20%) → 8 UE/цикл (лимит 500 UE/нед)\n"
               "• PLATINUM (25%) → 10 UE/цикл (лимит 20 000 UE/нед)\n"
               "• PREMIUM (35%) → 14 UE/цикл (лимит 50 000 UE/нед)\n\n"
               "📌 *Лимиты PV с покупки:*\n• GOLD: до 20 PV\n• PLATINUM: до 100 PV\n• PREMIUM: без ограничений\n\n"
               "🔄 *Spillover:* вышестоящие могут размещать своих партнёров в твою структуру!\n\n"
               "✅ Понял бинар и КББ? Нажми кнопку ниже 👇"),
        "tk": ("📊 *Marketing — 5-nji gün: Binar we KBB*\n\n"
               "🌳 Her hyzmatdaşda 2 şaha: çep we sag.\n\n"
               "🔄 *1 sikl* = 40 PV çep + 40 PV sag → KBB hasaplanýar\n\n"
               "💰 *Status boýunça KBB:*\n• GOLD → 8 UE/sikl\n• PLATINUM → 10 UE/sikl\n• PREMIUM → 14 UE/sikl\n\n"
               "📌 *Satyn alyşdan PV çäkleri:*\n• GOLD: 20 PV\n• PLATINUM: 100 PV\n• PREMIUM: çäksiz\n\n"
               "✅ Binar we KBB-ni düşündiňmi? Bas 👇"),
        "uz": ("📊 *Marketing — 5-kun: Binar va KBB*\n\n"
               "🌳 Har hamkorning 2 tarmog'i: chap va o'ng.\n\n"
               "🔄 *1 sikl* = 40 PV chap + 40 PV o'ng → KBB hisoblanadi\n\n"
               "💰 *Status bo'yicha KBB:*\n• GOLD → 8 UE/sikl\n• PLATINUM → 10 UE/sikl\n• PREMIUM → 14 UE/sikl\n\n"
               "📌 *Xariddan PV chegaralari:*\n• GOLD: 20 PV\n• PLATINUM: 100 PV\n• PREMIUM: cheksiz\n\n"
               "✅ Binar va KBB ni tushundingmi? Bos 👇"),
    },
    6: {
        "ru": ("📊 *Маркетинг — День 6: Квалификации и БЗК*\n\n"
               "🏅 *Квалификации и выплаты:*\n"
               "• Гранат: ГО 400 PV → *150 UE/мес*\n"
               "• Рубин: ГО 800 PV → *233 UE/мес*\n"
               "• Изумруд: ГО 2 000 PV → *333 UE/мес*\n"
               "• Сапфир: ГОБ 5 000 PV → *500 UE/мес*\n"
               "• Бриллиант: ГОБ 15 000 PV → *500 UE/мес*\n"
               "• Красный Бриллиант 3К: ГОБ 65 000 PV → *500 UE + Бустер*\n\n"
               "🚀 *Бустер бонус:* +20% к КББ при первом достижении квалификации "
               "от Красный Бриллиант 3К. Единоразово!\n\n"
               "✅ Запомнил квалификации? Нажми кнопку ниже 👇"),
        "tk": ("📊 *Marketing — 6-njy gün: Derejeler we BZK*\n\n"
               "🏅 *Derejeler:*\n• Granat: GO 400 PV → *aýda 150 UE*\n"
               "• Rubin: GO 800 PV → *233 UE*\n• Zümrüt: GO 2000 PV → *333 UE*\n"
               "• Sapfir: GOB 5000 PV → *500 UE*\n• Brilliýant: GOB 15000 PV → *500 UE*\n\n"
               "🚀 *Buster bonus:* KBB-e +20%, ilkinji Gyzyl Brilliýant 3K-da. Bir gezek!\n\n"
               "✅ Derejelerý ýatladyňmy? Bas 👇"),
        "uz": ("📊 *Marketing — 6-kun: Malakalar va BZK*\n\n"
               "🏅 *Malakalar:*\n• Granat: GO 400 PV → *oyda 150 UE*\n"
               "• Rubin: GO 800 PV → *233 UE*\n• Zumrud: GO 2000 PV → *333 UE*\n"
               "• Zangori: GOB 5000 PV → *500 UE*\n• Brilliant: GOB 15000 PV → *500 UE*\n\n"
               "🚀 *Buster bonus:* KBB ga +20%, birinchi Qizil Brilliant 3K da. Bir marta!\n\n"
               "✅ Malakalarni esladingmi? Bos 👇"),
    },
    7: {
        "ru": ("📊 *Маркетинг — День 7: Бонус наставника*\n\n"
               "🎓 *БН* считается от КББ партнёров по дереву наставника.\n\n"
               "📊 *Глубина зависит от квалификации:*\n"
               "• Сапфир → 3 уровня\n• Выше → до 10 уровней\n\n"
               "Начисляется с партнёров с *равной или меньшей* квалификацией.\n\n"
               "💰 *Пример:* Ты Сапфир, партнёр 1 линии Сапфир → 10% от его КББ\n\n"
               "✅ *Условия:* статус Premium + квалификация Сапфир + личная активность\n"
               "Бонус начисляется после конца месяца.\n\n"
               "🏆 *Поздравляем! Ты изучил весь маркетинговый план Vertera!*\n"
               "Теперь пройди тест → нажми «🧪 Тесты» 💪"),
        "tk": ("📊 *Marketing — 7-nji gün: Halypa bonusy*\n\n"
               "🎓 *BN* halypanyň agaç bölümindäki KBB-den hasaplanýar.\n\n"
               "📊 *Derejeňize görä:*\n• Sapfir → 3 dereje\n• Ýokary → 10 derejä çenli\n\n"
               "Deň ýa-da az derejeli hyzmatdaşlardan hasaplanýar.\n\n"
               "✅ *Şertler:* Premium statusy + Sapfir derejesi + işjeňlik\n\n"
               "🏆 *Gutlaýarys! Vertera marketing meýilnamasyny doly öwrendiňiz!*\n"
               "Indi testi geç → «🧪 Testler» 💪"),
        "uz": ("📊 *Marketing — 7-kun: Murabbiy bonusi*\n\n"
               "🎓 *BN* murabbiy daraxti bo'yicha KBB dan hisoblanadi.\n\n"
               "📊 *Malakangizga qarab:*\n• Zangori → 3 daraja\n• Yuqori → 10 darajagacha\n\n"
               "Teng yoki past malakali hamkorlardan hisoblanadi.\n\n"
               "✅ *Shartlar:* Premium statusi + Zangori malakasi + faollik\n\n"
               "🏆 *Tabriklaymiz! Vertera marketing rejasini to'liq o'rgandingiz!*\n"
               "Endi testdan o'ting → «🧪 Testlar» 💪"),
    },
}

MKT_DONE_BTN   = {"ru":"✅ День изучен! Далее","tk":"✅ Gün öwrenildi! Dowam et","uz":"✅ Kun o'rganildi! Davom etish"}
MKT_REPEAT_BTN = {"ru":"🔁 Повторить день","tk":"🔁 Güni gaýtala","uz":"🔁 Kunni takrorla"}
MKT_ALL_DONE   = {
    "ru":"🏆 Маркетинговый план пройден! Нажми «🧪 Тесты» для закрепления знаний",
    "tk":"🏆 Marketing meýilnamasy geçildi! Bilimi berkitmek üçin «🧪 Testler» bas",
    "uz":"🏆 Marketing rejasi o'tildi! Bilimni mustahkamlash uchun «🧪 Testlar» bos",
}
MKT_REVIEW_DAYS = {
    "ru":["📅 День 1 — Понятия","📅 День 2 — Активность","📅 День 3 — БЗП",
          "📅 День 4 — Клубы","📅 День 5 — Бинар","📅 День 6 — Квалификации","📅 День 7 — Наставник"],
    "tk":["📅 1-gün — Düşünjeler","📅 2-gün — Işjeňlik","📅 3-gün — BZP",
          "📅 4-gün — Klub","📅 5-gün — Binar","📅 6-gün — Derejeler","📅 7-gün — Halypa"],
    "uz":["📅 1-kun — Tushunchalar","📅 2-kun — Faollik","📅 3-kun — BZP",
          "📅 4-kun — Klublar","📅 5-kun — Binar","📅 6-kun — Malakalar","📅 7-kun — Murabbiy"],
}
LEARN_REVIEW_DAYS = {
    "ru":["📅 День 1 — Старт","📅 День 2 — Встреча","📅 День 3 — Контроль",
          "📅 День 4 — Аналитика","📅 День 5 — Результат","📅 День 6 — Масштаб","📅 День 7 — Фиксация"],
    "tk":["📅 1-gün — Başlangyç","📅 2-gün — Duşuşyk","📅 3-gün — Gözegçilik",
          "📅 4-gün — Analitika","📅 5-gün — Netije","📅 6-gün — Masştab","📅 7-gün — Berkitmek"],
    "uz":["📅 1-kun — Boshlash","📅 2-kun — Uchrashuv","📅 3-kun — Nazorat",
          "📅 4-kun — Tahlil","📅 5-kun — Natija","📅 6-kun — Masshtab","📅 7-kun — Mustahkamlash"],
}

# ══════════════════════════════════════════════════════════════
# ТЕСТЫ
# ══════════════════════════════════════════════════════════════
QUIZ_NAMES = {
    "products":  {"ru":"Продукты Vertera","tk":"Vertera önümleri","uz":"Vertera mahsulotlari"},
    "marketing": {"ru":"Маркетинг и бонусы","tk":"Marketing we bonuslar","uz":"Marketing va bonuslar"},
    "work":      {"ru":"Работа с новичками","tk":"Täze adamlar bilen iş","uz":"Yangilar bilan ishlash"},
}
QUIZ_ORDER = ["products","marketing","work"]

QUIZ_DATA = {
    "products": [
        {"q":{"ru":"Что является основным компонентом Vertera Gel?","tk":"Vertera Gel-iň esasy düzümi näme?","uz":"Vertera Gel ning asosiy tarkibi nima?"},
         "o":{"ru":["А) Спирулина","Б) Ламинария","В) Хлорелла"],"tk":["A) Spirulina","B) Laminariýa","C) Hlorella"],"uz":["A) Spirulina","B) Laminaria","V) Xlorella"]},
         "a":1,"e":{"ru":"Vertera Gel создан на основе ламинарии — бурой морской водоросли.","tk":"Vertera Gel laminariýa esasynda döredildi.","uz":"Vertera Gel laminaria asosida yaratilgan."}},
        {"q":{"ru":"Какой pH у Vertera Forte Original?","tk":"Vertera Forte Original-yň pH-y näçe?","uz":"Vertera Forte Original ning pH darajasi qancha?"},
         "o":{"ru":["А) 5.0","Б) 7.9","В) 8.5"],"tk":["A) 5.0","B) 7.9","C) 8.5"],"uz":["A) 5.0","B) 7.9","V) 8.5"]},
         "a":2,"e":{"ru":"Vertera Forte Original имеет pH 8.5.","tk":"Vertera Forte Original pH 8.5.","uz":"Vertera Forte Original pH 8.5."}},
        {"q":{"ru":"С какого возраста можно употреблять Умный ребёнок?","tk":"Akylly çagany haçandan ulanyp bolýar?","uz":"Aqlli bolani necha yoshdan iste'mol qilish mumkin?"},
         "o":{"ru":["А) с 1 года","Б) с 3 лет","В) с 6 лет"],"tk":["A) 1 ýaşdan","B) 3 ýaşdan","C) 6 ýaşdan"],"uz":["A) 1 yoshdan","B) 3 yoshdan","V) 6 yoshdan"]},
         "a":1,"e":{"ru":"Умный ребёнок для детей от 3 лет.","tk":"Akylly çaga 3 ýaşdan.","uz":"Aqlli bola 3 yoshdan."}},
        {"q":{"ru":"Сколько клинических исследований прошёл Vertera Gel?","tk":"Vertera Gel näçe kliniki syndan geçdi?","uz":"Vertera Gel nechta klinik tadqiqotdan o'tgan?"},
         "o":{"ru":["А) 3","Б) 6","В) 10"],"tk":["A) 3","B) 6","C) 10"],"uz":["A) 3","B) 6","V) 10"]},
         "a":1,"e":{"ru":"Vertera Gel прошёл 6 клинических исследований.","tk":"Vertera Gel 6 syndan geçdi.","uz":"Vertera Gel 6 ta tadqiqotdan o'tgan."}},
        {"q":{"ru":"Какой продукт направлен на здоровье сосудов?","tk":"Haýsy önüm damar saglygy üçin?","uz":"Qaysi mahsulot tomir salomatligi uchun?"},
         "o":{"ru":["А) Vertera Gel","Б) AngioLive","В) Smart Kid"],"tk":["A) Vertera Gel","B) AngioLive","C) Smart Kid"],"uz":["A) Vertera Gel","B) AngioLive","V) Smart Kid"]},
         "a":1,"e":{"ru":"AngioLive с экстрактом красного винограда для здоровья сосудов.","tk":"AngioLive damar saglygy üçin.","uz":"AngioLive tomir salomatligi uchun."}},
        {"q":{"ru":"Какая технология используется в косметике Vertera?","tk":"Vertera kosmetikasynda haýsy tehnologiýa?","uz":"Vertera kosmetikasida qaysi texnologiya?"},
         "o":{"ru":["А) Nano Tech","Б) Plasma Technology","В) Bio Matrix"],"tk":["A) Nano Tech","B) Plasma Technology","C) Bio Matrix"],"uz":["A) Nano Tech","B) Plasma Technology","V) Bio Matrix"]},
         "a":1,"e":{"ru":"Vertera использует Plasma Technology.","tk":"Vertera Plasma Technology ulanýar.","uz":"Vertera Plasma Technology dan foydalanadi."}},
        {"q":{"ru":"Сколько полезных веществ в Умном ребёнке?","tk":"Akylly çagada näçe peýdaly madda?","uz":"Aqlli bolada qancha foydali modda?"},
         "o":{"ru":["А) 50+","Б) 100+","В) 140+"],"tk":["A) 50+","B) 100+","C) 140+"],"uz":["A) 50+","B) 100+","V) 140+"]},
         "a":2,"e":{"ru":"Умный ребёнок содержит 140+ полезных веществ.","tk":"Akylly çaga 140+ madda.","uz":"Aqlli bola 140+ foydali modda."}},
    ],
    "marketing": [
        {"q":{"ru":"Сколько % составляет БЗП?","tk":"BZP näçe göterim?","uz":"BZP necha foiz?"},
         "o":{"ru":["А) 20%","Б) 30%","В) 40%"],"tk":["A) 20%","B) 30%","C) 40%"],"uz":["A) 20%","B) 30%","V) 40%"]},
         "a":2,"e":{"ru":"БЗП = 40% от PV покупки партнёров первой линии.","tk":"BZP = 40%.","uz":"BZP = 40%."}},
        {"q":{"ru":"Минимальный ЛО для личной активности?","tk":"Şahsy işjeňlik üçin minimal ÝO?","uz":"Shaxsiy faollik uchun minimal LO?"},
         "o":{"ru":["А) 10 PV","Б) 20 PV","В) 40 PV"],"tk":["A) 10 PV","B) 20 PV","C) 40 PV"],"uz":["A) 10 PV","B) 20 PV","V) 40 PV"]},
         "a":1,"e":{"ru":"Личная активность = покупка от 20 PV.","tk":"Şahsy işjeňlik = 20 PV.","uz":"Shaxsiy faollik = 20 PV."}},
        {"q":{"ru":"Сколько UE даёт Клуб 220?","tk":"Klub 220 näçe UE berýär?","uz":"Klub 220 necha UE beradi?"},
         "o":{"ru":["А) 55 UE","Б) 100 UE","В) 110 UE"],"tk":["A) 55 UE","B) 100 UE","C) 110 UE"],"uz":["A) 55 UE","B) 100 UE","V) 110 UE"]},
         "a":2,"e":{"ru":"Клуб 220 = 110 UE в месяц.","tk":"Klub 220 = 110 UE aýda.","uz":"Klub 220 = 110 UE oyda."}},
        {"q":{"ru":"PV для закрытия 1 цикла КББ с каждой стороны?","tk":"KBB 1 siklini ýapmak üçin her tarapdan?","uz":"KBB 1 siklini yopish uchun har tomondan?"},
         "o":{"ru":["А) 20 PV","Б) 40 PV","В) 100 PV"],"tk":["A) 20 PV","B) 40 PV","C) 100 PV"],"uz":["A) 20 PV","B) 40 PV","V) 100 PV"]},
         "a":1,"e":{"ru":"1 цикл = 40 PV слева + 40 PV справа.","tk":"1 sikl = 40 PV çep + 40 PV sag.","uz":"1 sikl = 40 PV chap + 40 PV o'ng."}},
        {"q":{"ru":"КББ со статусом PREMIUM за 1 цикл?","tk":"PREMIUM statusy bilen KBB 1 sikl üçin?","uz":"PREMIUM statusi bilan KBB 1 sikl uchun?"},
         "o":{"ru":["А) 8 UE","Б) 10 UE","В) 14 UE"],"tk":["A) 8 UE","B) 10 UE","C) 14 UE"],"uz":["A) 8 UE","B) 10 UE","V) 14 UE"]},
         "a":2,"e":{"ru":"PREMIUM = 35% = 14 UE за цикл.","tk":"PREMIUM = 14 UE sikl üçin.","uz":"PREMIUM = 14 UE sikl uchun."}},
        {"q":{"ru":"БЗК с квалификацией Сапфир?","tk":"Sapfir derejeli BZK?","uz":"Zangori malakali BZK?"},
         "o":{"ru":["А) 150 UE","Б) 333 UE","В) 500 UE"],"tk":["A) 150 UE","B) 333 UE","C) 500 UE"],"uz":["A) 150 UE","B) 333 UE","V) 500 UE"]},
         "a":2,"e":{"ru":"Сапфир и выше = 500 UE в месяц.","tk":"Sapfir we ýokary = 500 UE aýda.","uz":"Zangori va yuqori = 500 UE oyda."}},
        {"q":{"ru":"1 UE в Туркменистане?","tk":"Türkmenistanda 1 UE?","uz":"Turkmanistonda 1 UE?"},
         "o":{"ru":["А) 10 манат","Б) 15 манат","В) 20 манат"],"tk":["A) 10 manat","B) 15 manat","C) 20 manat"],"uz":["A) 10 manat","B) 15 manat","V) 20 manat"]},
         "a":1,"e":{"ru":"1 UE = 15 манат (TKM), 10 000 сум (UZB).","tk":"1 UE = 15 manat (TKM).","uz":"1 UE = 15 manat (TKM)."}},
    ],
    "work": [
        {"q":{"ru":"Сколько приглашений нужно в День 1?","tk":"1-nji günde näçe çakylyk?","uz":"1-kunda nechta taklif?"},
         "o":{"ru":["А) 1","Б) 3","В) 10"],"tk":["A) 1","B) 3","C) 10"],"uz":["A) 1","B) 3","V) 10"]},
         "a":1,"e":{"ru":"День 1: отправить минимум 3 приглашения.","tk":"1-nji gün: azyndan 3 çakylyk.","uz":"1-kun: kamida 3 ta taklif."}},
        {"q":{"ru":"Что означает правило 72 часов?","tk":"72 sagat düzgüni näme?","uz":"72 soat qoidasi nima?"},
         "o":{"ru":["А) Отдыхать 72 часа","Б) Действовать в первые 72 часа","В) Звонить каждые 72 часа"],"tk":["A) 72 sagat dynç al","B) Ilkinji 72 sagatda hereket et","C) 72 sagatdan bir jaň et"],"uz":["A) 72 soat dam ol","B) Birinchi 72 soatda harakat qil","V) Har 72 soatda qo'ngiroq qil"]},
         "a":1,"e":{"ru":"72 часа: если не действуешь — человек 'остывает'.","tk":"72 sagat: hereket etmeseň adam 'sowuýar'.","uz":"72 soat: harakat qilmasang odam 'soviydi'."}},
        {"q":{"ru":"Формула конверсии в работе с новичками?","tk":"Konwersiýa formulasy?","uz":"Konversiya formulasi?"},
         "o":{"ru":["А) 5 сообщений = 1 встреча","Б) 10 сообщений = 3 ответа = 1 встреча","В) 20 сообщений = 1 партнёр"],"tk":["A) 5 habar = 1 duşuşyk","B) 10 habar = 3 jogap = 1 duşuşyk","C) 20 habar = 1 hyzmatdaş"],"uz":["A) 5 xabar = 1 uchrashuv","B) 10 xabar = 3 javob = 1 uchrashuv","V) 20 xabar = 1 hamkor"]},
         "a":1,"e":{"ru":"10 сообщений = 3 ответа = 1 встреча.","tk":"10 habar = 3 jogap = 1 duşuşyk.","uz":"10 xabar = 3 javob = 1 uchrashuv."}},
        {"q":{"ru":"Что делать на первой встрече?","tk":"Ilkinji duşuşykda näme?","uz":"Birinchi uchrashuvda nima?"},
         "o":{"ru":["А) Всё подробно объяснить","Б) Не обучать — показывать результаты","В) Рассказать о всех продуктах"],"tk":["A) Jikme-jik düşündirmek","B) Öwretme — netijeleri görkez","C) Ähli önümler hakda"],"uz":["A) Hamma narsani tushuntirish","B) O'rgatma — natijalarni ko'rsat","V) Barcha mahsulotlar haqida"]},
         "a":1,"e":{"ru":"Правило: не обучай — показывай результаты, систему, продукт.","tk":"Düzgün: öwretme — görkez.","uz":"Qoida: o'rgatma — ko'rsat."}},
        {"q":{"ru":"В какой день фиксируем первый результат?","tk":"Ilkinji netijäni haýsy günde?","uz":"Birinchi natijani qaysi kunda?"},
         "o":{"ru":["А) День 3","Б) День 5","В) День 7"],"tk":["A) 3-nji gün","B) 5-nji gün","C) 7-nji gün"],"uz":["A) 3-kun","B) 5-kun","V) 7-kun"]},
         "a":1,"e":{"ru":"День 5 — создать веру через первый результат.","tk":"5-nji gün — ilkinji netije.","uz":"5-kun — birinchi natija."}},
    ],
}

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

# 7 дней обучения
DAYS = {
    1: {
        "ru": (
            "🚀 *День 1 — Старт и снятие страха*\n\n"
            "⚡ Помни: *Правило 72 часов* — если не действуешь 3 дня, ты \"остываешь\"!\n\n"
            "*Цель:* начать действовать в первые часы\n\n"
            "*Твои задания сегодня:*\n"
            "1️⃣ Составить список контактов — минимум 30 человек\n"
            "2️⃣ Отправить 3 приглашения\n\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "📲 *Скрипты приглашений (3 варианта):*\n\n"
            "✅ *Вариант 1 — Нейтральный:*\n"
            "_Привет! Я сейчас запускаю новый проект, хочу показать тебе идею. Давай встретимся на кофе, займет 20 минут. Когда тебе удобно?_\n\n"
            "✅ *Вариант 2 — Через интерес:*\n"
            "_Привет! Сейчас разбираюсь в одной интересной теме, связанной с доходом и новым рынком. Хочу тебе показать, думаю тебе зайдет. Когда сможем пересечься на 15–20 минут?_\n\n"
            "✅ *Вариант 3 — Через личный контакт:*\n"
            "_Привет! Есть тема, которую хочу с тобой обсудить лично. Сейчас начал новое направление, и ты один из первых, кому хочу показать. Давай увидимся?_\n\n"
            "🧠 *Правило №1:* \"Я не продаю — я приглашаю\"\n\n"
            "✅ Выполнил задания? Нажми кнопку ниже чтобы перейти к Дню 2 👇"
        ),
        "tk": (
            "🚀 *1-nji gün — Başlangyç*\n\n"
            "⚡ Ýatla: *72 sagat düzgüni* — 3 günde hereket etmeseň \"sowuýarsyň\"!\n\n"
            "*Maksat:* ilkinji sagatlarda hereket etmek\n\n"
            "*Şu günki tabşyryklar:*\n"
            "1️⃣ Kontakt sanawy düzmek — azyndan 30 adam\n"
            "2️⃣ 3 çakylyk ibermek\n\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "📲 *Çakylyk skriptleri (3 görnüş):*\n\n"
            "✅ *1-nji görnüş — Bitarap:*\n"
            "_Salam! Men häzir täze taslamany işe girizýärin, saňa bir pikir görkezmek isleýärin. Kofe içmäge duşuşaly, 20 minut alar. Haçan amatlydyr?_\n\n"
            "✅ *2-nji görnüş — Gyzyklanma arkaly:*\n"
            "_Salam! Häzir girdeji bilen bagly gyzykly bir tema öwrenýärin. Saňa görkezmek isleýärin. 15–20 minuta duşuşyp bolarmy?_\n\n"
            "✅ *3-nji görnüş — Şahsy kontakt:*\n"
            "_Salam! Seniň bilen şahsy maslahatlaşmak isleýän bir zat bar. Täze ugur başladym, ilki görkezmek isleýänlerimiň biri sensiň. Duşuşalymy?_\n\n"
            "🧠 *Düzgün №1:* \"Men satmaýaryn — men çagyrýaryn\"\n\n"
            "✅ Tabşyryklary ýerine ýetirdiňmi? 2-nji güne geçmek üçin aşakdaky düwmä bas 👇"
        ),
        "uz": (
            "🚀 *1-kun — Boshlash*\n\n"
            "⚡ Eslab qo'y: *72 soat qoidasi* — 3 kunda harakat qilmasang \"soviysan\"!\n\n"
            "*Maqsad:* birinchi soatlarda harakat boshlash\n\n"
            "*Bugungi vazifalar:*\n"
            "1️⃣ Kontaktlar ro'yxatini tuzish — kamida 30 kishi\n"
            "2️⃣ 3 ta taklif yuborish\n\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "📲 *Taklif skriptlari (3 variant):*\n\n"
            "✅ *1-variant — Neytral:*\n"
            "_Salom! Men hozir yangi loyihani ishga tushiryapman, senga bir g'oya ko'rsatmoqchiman. Kofe ichishga uchrashaylik, 20 daqiqa oladi. Qachon qulay?_\n\n"
            "✅ *2-variant — Qiziqish orqali:*\n"
            "_Salom! Daromad bilan bog'liq qiziqarli mavzuni o'rganmoqdaman. Senga ko'rsatmoqchiman. 15–20 daqiqaga uchrashamizmi?_\n\n"
            "✅ *3-variant — Shaxsiy kontakt:*\n"
            "_Salom! Sen bilan shaxsan gaplashmoqchi bo'lgan narsam bor. Yangi yo'nalish boshladim, birinchi ko'rsatmoqchi bo'lganlarimdan biri sensen. Uchrashaylikmi?_\n\n"
            "🧠 *Qoida №1:* \"Men sotmayapman — men taklif qilyapman\"\n\n"
            "✅ Vazifalarni bajardingmi? 2-kunga o'tish uchun quyidagi tugmani bos 👇"
        ),
    },
    2: {
        "ru": (
            "🤝 *День 2 — Первая встреча*\n\n"
            "*Задача:* не перегрузить, а зажечь интерес\n\n"
            "*Твои задания сегодня:*\n"
            "1️⃣ Провести 1–2 встречи (ты + наставник)\n"
            "2️⃣ Показать: результаты, систему, продукт\n\n"
            "*Инструменты:*\n"
            "• Презентация (PDF / телефон)\n"
            "• Короткое видео до 5 минут\n"
            "• История успеха наставника\n\n"
            "💡 *Правило встречи:* не обучай — показывай. Пусть говорит наставник!\n\n"
            "✅ Провёл встречи? Нажми ниже чтобы перейти к Дню 3 👇"
        ),
        "tk": (
            "🤝 *2-nji gün — Ilkinji duşuşyk*\n\n"
            "*Wezipe:* artykmaç ýüklemek däl, gyzyklanma döretmek\n\n"
            "*Şu günki tabşyryklar:*\n"
            "1️⃣ 1–2 duşuşyk geçirmek (sen + halypa)\n"
            "2️⃣ Görkezmek: netijeleri, ulgamy, önümi\n\n"
            "*Gurallar:*\n"
            "• Prezentasiýa (PDF / telefon)\n"
            "• Gysga wideo (5 minut çenli)\n"
            "• Halypanyň üstünlik taryhy\n\n"
            "💡 *Duşuşyk düzgüni:* öwretme — görkez. Halypa gürlesin!\n\n"
            "✅ Duşuşyklary geçirdiňmi? 3-nji güne geçmek üçin bas 👇"
        ),
        "uz": (
            "🤝 *2-kun — Birinchi uchrashuv*\n\n"
            "*Vazifa:* haddan tashqari yuklamaslik, qiziqish uyg'otish\n\n"
            "*Bugungi vazifalar:*\n"
            "1️⃣ 1–2 ta uchrashuv o'tkazish (sen + murabbiy)\n"
            "2️⃣ Ko'rsatish: natijalar, tizim, mahsulot\n\n"
            "*Vositalar:*\n"
            "• Taqdimot (PDF / telefon)\n"
            "• Qisqa video 5 daqiqagacha\n"
            "• Murabbiyning muvaffaqiyat tarixi\n\n"
            "💡 *Uchrashuv qoidasi:* o'rgatma — ko'rsat. Murabbiy gapirsin!\n\n"
            "✅ Uchrashuvlarni o'tkazdingmi? 3-kunga o'tish uchun bos 👇"
        ),
    },
    3: {
        "ru": (
            "🔄 *День 3 — Контроль и масштаб*\n\n"
            "*Задача:* закрепить действие\n\n"
            "*Твои задания сегодня:*\n"
            "1️⃣ Разбор: что получилось, где был страх?\n"
            "2️⃣ Отправить ещё 5 сообщений\n"
            "3️⃣ Добавить новых людей в свою воронку\n\n"
            "*Инструменты:*\n"
            "• Чек-лист ошибок\n"
            "• Скрипт ответов на \"нет\":\n"
            "_\"Понимаю, что сейчас не лучшее время. Можно просто покажу информацию, займёт 5 минут?\"_\n\n"
            "💡 Каждое \"нет\" — это шаг к \"да\"!\n\n"
            "✅ Сделал задания? Нажми ниже чтобы перейти к Дню 4 👇"
        ),
        "tk": (
            "🔄 *3-nji gün — Gözegçilik we masştab*\n\n"
            "*Wezipe:* hereket berkitmek\n\n"
            "*Şu günki tabşyryklar:*\n"
            "1️⃣ Derňew: näme boldy, nirede gorkudy?\n"
            "2️⃣ Ýene 5 habar ibermek\n"
            "3️⃣ Täze adamlary goşmak\n\n"
            "*Gurallar:*\n"
            "• Ýalňyşlyklar sanawy\n"
            "• \"Ýok\" jogabyna skript:\n"
            "_\"Häzir amatly wagtyň däldigini düşünýärin. Diňe 5 minuta maglumat görkezsemdim?\"_\n\n"
            "💡 Her \"ýok\" — \"hawa\"a ýakynlaşmak!\n\n"
            "✅ Tabşyryklary ýerine ýetirdiňmi? 4-nji güne geç 👇"
        ),
        "uz": (
            "🔄 *3-kun — Nazorat va masshtab*\n\n"
            "*Vazifa:* harakatni mustahkamlash\n\n"
            "*Bugungi vazifalar:*\n"
            "1️⃣ Tahlil: nima bo'ldi, qayerda qo'rqdingi?\n"
            "2️⃣ Yana 5 ta xabar yuborish\n"
            "3️⃣ Yangi odamlarni qo'shish\n\n"
            "*Vositalar:*\n"
            "• Xatolar ro'yxati\n"
            "• \"Yo'q\" javobiga skript:\n"
            "_\"Tushunaman, hozir qulay vaqt emas. Shunchaki 5 daqiqada ma'lumot ko'rsatsam bo'ladimi?\"_\n\n"
            "💡 Har bir \"yo'q\" — \"ha\"ga yaqinlashish!\n\n"
            "✅ Vazifalarni bajardingmi? 4-kunga o'tish uchun bos 👇"
        ),
    },
    4: {
        "ru": (
            "📊 *День 4 — Аналитика*\n\n"
            "*Задача:* научить думать как предприниматель\n\n"
            "*Твои задания сегодня:*\n"
            "1️⃣ Посчитай: сколько написал / сколько ответили / сколько пришли\n"
            "2️⃣ Пойми свою конверсию\n"
            "3️⃣ Отправь мини-отчёт наставнику\n\n"
            "📈 *Формула успеха:*\n"
            "10 сообщений = 3 ответа = 1 встреча\n"
            "Это нормально! Главное — объём.\n\n"
            "💡 Не оценивай результат эмоциями — смотри на цифры!\n\n"
            "✅ Сделал анализ? Нажми ниже чтобы перейти к Дню 5 👇"
        ),
        "tk": (
            "📊 *4-nji gün — Analitika*\n\n"
            "*Wezipe:* telekeçi ýaly pikirlenmegi öwrenmek\n\n"
            "*Şu günki tabşyryklar:*\n"
            "1️⃣ Sana: näçe ýazdyň / näçesi jogap berdi / näçesi geldi\n"
            "2️⃣ Öz konwersiýaňy düşün\n"
            "3️⃣ Halypanyňa mini-hasabat iber\n\n"
            "📈 *Üstünlik formulasy:*\n"
            "10 habar = 3 jogap = 1 duşuşyk\n"
            "Bu kadaly! Esasy — mukdar.\n\n"
            "💡 Netijäni duýgy bilen däl — sanlar bilen baha ber!\n\n"
            "✅ Derňewi etdiňmi? 5-nji güne geçmek üçin bas 👇"
        ),
        "uz": (
            "📊 *4-kun — Tahlil*\n\n"
            "*Vazifa:* tadbirkor kabi fikrlashni o'rganish\n\n"
            "*Bugungi vazifalar:*\n"
            "1️⃣ Hisobla: nechta yozdim / nechtasi javob berdi / nechtasi keldi\n"
            "2️⃣ O'z konversiyangni tushun\n"
            "3️⃣ Murabbiyingga mini-hisobot yubor\n\n"
            "📈 *Muvaffaqiyat formulasi:*\n"
            "10 xabar = 3 javob = 1 uchrashuv\n"
            "Bu normal! Asosiysi — hajm.\n\n"
            "💡 Natijani his-tuyg'u bilan emas — raqamlar bilan baho ber!\n\n"
            "✅ Tahlil qildingmi? 5-kunga o'tish uchun bos 👇"
        ),
    },
    5: {
        "ru": (
            "🏆 *День 5 — Личный результат*\n\n"
            "*Задача:* создать веру через первый результат\n\n"
            "*Твои задания сегодня:*\n"
            "1️⃣ Зафиксируй первый результат (продажа / регистрация / отзыв на продукт)\n"
            "2️⃣ Напиши 5 людям:\n"
            "_\"Я начал, уже есть первые результаты, давай покажу\"_\n\n"
            "*Инструменты:*\n"
            "• Скрипт \"результат\"\n"
            "• Фото / скриншот / отзыв\n\n"
            "💡 Люди верят людям, а не словам. Покажи результат!\n\n"
            "✅ Есть первый результат? Нажми ниже чтобы перейти к Дню 6 👇"
        ),
        "tk": (
            "🏆 *5-nji gün — Şahsy netije*\n\n"
            "*Wezipe:* ilkinji netije arkaly ynamy döretmek\n\n"
            "*Şu günki tabşyryklar:*\n"
            "1️⃣ Ilkinji netijäni bellemek (satyş / hasaba alyş / önüm synlary)\n"
            "2️⃣ 5 adama ýaz:\n"
            "_\"Başladym, eýýäm ilkinji netijeler bar, görkezeýin\"_\n\n"
            "*Gurallar:*\n"
            "• \"Netije\" skripti\n"
            "• Surat / ekran suraty / syn\n\n"
            "💡 Adamlar adamlara ynanýar. Netijäni görkez!\n\n"
            "✅ Ilkinji netije barmy? 6-njy güne geçmek üçin bas 👇"
        ),
        "uz": (
            "🏆 *5-kun — Shaxsiy natija*\n\n"
            "*Vazifa:* birinchi natija orqali ishonch yaratish\n\n"
            "*Bugungi vazifalar:*\n"
            "1️⃣ Birinchi natijani qayd et (sotuv / ro'yxat / mahsulot sharhi)\n"
            "2️⃣ 5 kishiga yoz:\n"
            "_\"Boshladim, allaqachon birinchi natijalar bor, ko'rsatay\"_\n\n"
            "*Vositalar:*\n"
            "• \"Natija\" skripti\n"
            "• Rasm / skrinshot / sharh\n\n"
            "💡 Odamlar odamlarga ishonadi. Natijani ko'rsat!\n\n"
            "✅ Birinchi natija bormi? 6-kunga o'tish uchun bos 👇"
        ),
    },
    6: {
        "ru": (
            "📈 *День 6 — Масштабирование*\n\n"
            "*Задача:* выйти из зоны \"один на один\"\n\n"
            "*Твои задания сегодня:*\n"
            "1️⃣ Назначить минимум 2 встречи\n"
            "2️⃣ Подключить наставника к встречам\n"
            "3️⃣ Использовать Zoom / групповые встречи\n\n"
            "*Инструменты:*\n"
            "• Готовый Zoom\n"
            "• Афиша встречи\n"
            "• Ссылка на презентацию\n\n"
            "💡 Один в поле не воин. Наставник умножает твои результаты!\n\n"
            "✅ Провёл встречи с наставником? Нажми ниже чтобы перейти к Дню 7 👇"
        ),
        "tk": (
            "📈 *6-njy gün — Masştablaşdyrmak*\n\n"
            "*Wezipe:* \"biri-biri bilen\" zonasyndan çykmak\n\n"
            "*Şu günki tabşyryklar:*\n"
            "1️⃣ Azyndan 2 duşuşyk bellemek\n"
            "2️⃣ Halypany duşuşyklara birikdirmek\n"
            "3️⃣ Zoom / toparlaýyn duşuşyklar\n\n"
            "*Gurallar:*\n"
            "• Taýýar Zoom\n"
            "• Duşuşyk afişasy\n"
            "• Prezentasiýa baglanyşygy\n\n"
            "💡 Bir adam sährada söweşiji däl. Halypa netijäňi artdyrýar!\n\n"
            "✅ Halypa bilen duşuşyklary geçirdiňmi? 7-nji güne geç 👇"
        ),
        "uz": (
            "📈 *6-kun — Masshtablash*\n\n"
            "*Vazifa:* \"yakka-yakka\" zonasidan chiqish\n\n"
            "*Bugungi vazifalar:*\n"
            "1️⃣ Kamida 2 ta uchrashuv belgilash\n"
            "2️⃣ Murabbiyni uchrashuvlarga ulash\n"
            "3️⃣ Zoom / guruhli uchrashuvlar\n\n"
            "*Vositalar:*\n"
            "• Tayyor Zoom\n"
            "• Uchrashuv afishasi\n"
            "• Taqdimot havolasi\n\n"
            "💡 Bitta odam dalada jangchi emas. Murabbiy natijangni ko'paytiradi!\n\n"
            "✅ Murabbiy bilan uchrashuvlarni o'tkazdingmi? 7-kunga o'tish uchun bos 👇"
        ),
    },
    7: {
        "ru": (
            "🎉 *День 7 — Фиксация результата!*\n\n"
            "*Задача:* закрепить успех и мотивацию\n\n"
            "*Твои задания сегодня:*\n"
            "1️⃣ Запиши видео:\n"
            "   • что сделал за 7 дней\n"
            "   • что получилось\n"
            "   • сколько заработал / людей подключил\n"
            "2️⃣ Выложи в чат / соцсети\n\n"
            "📹 *Скрипт для видео:*\n"
            "_\"Я начал 7 дней назад… вот мой результат…\"_\n\n"
            "🏆 Ты прошёл первые 7 дней! Это только начало.\n"
            "Теперь повторяй цикл с удвоенной силой 💪\n\n"
            "🌿 Свяжись с наставником для следующего шага!"
        ),
        "tk": (
            "🎉 *7-nji gün — Netijäni berkitmek!*\n\n"
            "*Wezipe:* üstünligi we höwesi berkitmek\n\n"
            "*Şu günki tabşyryklar:*\n"
            "1️⃣ Wideo ýaz:\n"
            "   • 7 günde näme etdiň\n"
            "   • näme alyndy\n"
            "   • näçe gazandyň / näçe adam birikdirdiň\n"
            "2️⃣ Çata / sosial ulgamlara goý\n\n"
            "📹 *Wideo üçin skript:*\n"
            "_\"Men 7 gün ozal başladym… ine meniň netijem…\"_\n\n"
            "🏆 Ilkinji 7 günden geçdiň! Bu diňe başlangyç.\n"
            "Indi güýç bilen gaýtala 💪\n\n"
            "🌿 Indiki ädim üçin halypaň bilen habarlaş!"
        ),
        "uz": (
            "🎉 *7-kun — Natijani mustahkamlash!*\n\n"
            "*Vazifa:* muvaffaqiyat va motivatsiyani mustahkamlash\n\n"
            "*Bugungi vazifalar:*\n"
            "1️⃣ Video yoz:\n"
            "   • 7 kunda nima qilding\n"
            "   • nima natija olding\n"
            "   • qancha ishladim / necha kishi ulanding\n"
            "2️⃣ Chat / ijtimoiy tarmoqlarga joylashtir\n\n"
            "📹 *Video uchun skript:*\n"
            "_\"Men 7 kun oldin boshladim… mana mening natijam…\"_\n\n"
            "🏆 Birinchi 7 kunni o'tdingiz! Bu faqat boshlanish.\n"
            "Endi ikki karra kuch bilan takrorla 💪\n\n"
            "🌿 Keyingi qadam uchun murabbiy bilan bog'lan!"
        ),
    },
}

DAYS_DONE_BTN = {
    "ru": "✅ Задание выполнено! Перейти дальше",
    "tk": "✅ Tabşyryk ýerine ýetirildi! Dowam et",
    "uz": "✅ Vazifa bajarildi! Davom etish",
}
DAYS_REPEAT_BTN = {
    "ru": "🔁 Повторить задание дня",
    "tk": "🔁 Günüň tabşyrygyny gaýtala",
    "uz": "🔁 Kun vazifasini takrorla",
}
DAYS_ALL_DONE = {
    "ru": "🏆 Вы прошли все 7 дней обучения! Продолжайте в том же духе 💪",
    "tk": "🏆 Siz 7 günlük okuwdan geçdiňiz! Şol ruhy bilen dowam ediň 💪",
    "uz": "🏆 Siz 7 kunlik o'qitishni tugatdingiz! Shu ruhda davom eting 💪",
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

    # Обучение — показываем текущий день
    if text == p["btn_learn"]:
        day = progress_get(user.id)
        if day == 0:
            # Первый вход — запускаем День 1
            progress_set(user.id, 1)
            await progress_sync_to_sheets(user.id, 1, user.full_name or "", f"@{user.username}" if user.username else str(user.id))
            day = 1
        if day > 7:
            review_btn = p.get("btn_review_learn","📖 Просмотреть обучение")
            kb = ReplyKeyboardMarkup([[review_btn],[p["btn_back"]]],resize_keyboard=True)
            await update.message.reply_text(DAYS_ALL_DONE.get(lang, DAYS_ALL_DONE["ru"]), reply_markup=kb)
            return PARTNER_MENU
        day_text = DAYS[day].get(lang, DAYS[day]["ru"])
        done_btn = DAYS_DONE_BTN.get(lang, DAYS_DONE_BTN["ru"])
        repeat_btn = DAYS_REPEAT_BTN.get(lang, DAYS_REPEAT_BTN["ru"])
        learn_kb = ReplyKeyboardMarkup(
            [[done_btn], [p["btn_webinar"]], [repeat_btn], [p["btn_back"]]],
            resize_keyboard=True
        )
        await update.message.reply_text(day_text, parse_mode="Markdown", reply_markup=learn_kb)
        return PARTNER_MENU

    # Кнопка "Задание выполнено"
    done_btns = list(DAYS_DONE_BTN.values())
    if text in done_btns:
        day = progress_get(user.id)
        if day >= 7:
            progress_set(user.id, 8)
            await progress_sync_to_sheets(user.id, 8, user.full_name or "", f"@{user.username}" if user.username else str(user.id))
            await update.message.reply_text(DAYS_ALL_DONE.get(lang, DAYS_ALL_DONE["ru"]), reply_markup=get_partner_kb(lang))
            return PARTNER_MENU
        new_day = day + 1
        progress_set(user.id, new_day)
        await progress_sync_to_sheets(user.id, new_day, user.full_name or "", f"@{user.username}" if user.username else str(user.id))
        # Уведомляем менеджера
        uname = f"@{user.username}" if user.username else str(user.id)
        try:
            await context.bot.send_message(
                chat_id=MANAGER_CHAT_ID,
                text=f"✅ Партнёр завершил День {day}\n\n👤 {user.full_name or uname}\n🆔 {uname}\n➡️ Переходит к Дню {new_day}"
            )
        except Exception as e:
            logger.error(f"progress notify: {e}")
        if new_day > 7:
            await update.message.reply_text(DAYS_ALL_DONE.get(lang, DAYS_ALL_DONE["ru"]), reply_markup=get_partner_kb(lang))
        else:
            day_text = DAYS[new_day].get(lang, DAYS[new_day]["ru"])
            done_btn = DAYS_DONE_BTN.get(lang, DAYS_DONE_BTN["ru"])
            repeat_btn = DAYS_REPEAT_BTN.get(lang, DAYS_REPEAT_BTN["ru"])
            learn_kb = ReplyKeyboardMarkup(
                [[done_btn], [p["btn_webinar"]], [repeat_btn], [p["btn_back"]]],
                resize_keyboard=True
            )
            congrats = {
                "ru": f"🎉 День {day} пройден! Открывается День {new_day}:",
                "tk": f"🎉 {day}-nji gün geçildi! {new_day}-nji gün açylýar:",
                "uz": f"🎉 {day}-kun o'tildi! {new_day}-kun ochilmoqda:",
            }
            await update.message.reply_text(congrats.get(lang, congrats["ru"]), reply_markup=learn_kb)
            await update.message.reply_text(day_text, parse_mode="Markdown", reply_markup=learn_kb)
        return PARTNER_MENU

    # Кнопка "Повторить задание дня"
    repeat_btns = list(DAYS_REPEAT_BTN.values())
    if text in repeat_btns:
        day = progress_get(user.id)
        if day == 0:
            day = 1
        if day > 7:
            await update.message.reply_text(DAYS_ALL_DONE.get(lang, DAYS_ALL_DONE["ru"]), reply_markup=get_partner_kb(lang))
            return PARTNER_MENU
        day_text = DAYS[day].get(lang, DAYS[day]["ru"])
        done_btn = DAYS_DONE_BTN.get(lang, DAYS_DONE_BTN["ru"])
        repeat_btn = DAYS_REPEAT_BTN.get(lang, DAYS_REPEAT_BTN["ru"])
        learn_kb = ReplyKeyboardMarkup(
            [[done_btn], [p["btn_webinar"]], [repeat_btn], [p["btn_back"]]],
            resize_keyboard=True
        )
        await update.message.reply_text(day_text, parse_mode="Markdown", reply_markup=learn_kb)
        return PARTNER_MENU

    # Маркетинг — 7 дней с прогрессом
    if text == p["btn_market"]:
        day = mkt_progress_get(user.id)
        uname = f"@{user.username}" if user.username else str(user.id)
        if day == 0:
            mkt_progress_set(user.id, 1)
            await mkt_progress_sync(user.id, 1, user.full_name or "", uname)
            day = 1
        if day > 7:
            kb = ReplyKeyboardMarkup([[p.get("btn_review_mkt","📖 Просмотреть маркетинг")],[p["btn_back"]]],resize_keyboard=True)
            await update.message.reply_text(MKT_ALL_DONE.get(lang,MKT_ALL_DONE["ru"]),reply_markup=kb)
            return PARTNER_MENU
        mkt_kb = ReplyKeyboardMarkup([[MKT_DONE_BTN.get(lang,MKT_DONE_BTN["ru"])],[MKT_REPEAT_BTN.get(lang,MKT_REPEAT_BTN["ru"])],[p["btn_back"]]],resize_keyboard=True)
        await update.message.reply_text(MKT_DAYS[day].get(lang,MKT_DAYS[day]["ru"]),parse_mode="Markdown",reply_markup=mkt_kb)
        return PARTNER_MENU

    # Кнопка "День маркетинга изучен"
    if text in list(MKT_DONE_BTN.values()):
        day = mkt_progress_get(user.id)
        uname = f"@{user.username}" if user.username else str(user.id)
        new_day = day + 1
        mkt_progress_set(user.id, new_day)
        await mkt_progress_sync(user.id, new_day, user.full_name or "", uname)
        try:
            await context.bot.send_message(chat_id=MANAGER_CHAT_ID,
                text=f"📊 Партнёр прошёл маркетинг День {day}\n👤 {user.full_name or uname}\n🆔 {uname}")
        except Exception as e:
            logger.error(f"mkt notify: {e}")
        if new_day > 7:
            kb = ReplyKeyboardMarkup([[p.get("btn_review_mkt","📖 Просмотреть маркетинг")],[p["btn_back"]]],resize_keyboard=True)
            await update.message.reply_text(MKT_ALL_DONE.get(lang,MKT_ALL_DONE["ru"]),reply_markup=kb)
        else:
            mkt_kb = ReplyKeyboardMarkup([[MKT_DONE_BTN.get(lang,MKT_DONE_BTN["ru"])],[MKT_REPEAT_BTN.get(lang,MKT_REPEAT_BTN["ru"])],[p["btn_back"]]],resize_keyboard=True)
            ctext = {"ru":f"🎉 День {day} пройден! Открывается День {new_day}:","tk":f"🎉 {day}-nji gün geçildi! {new_day}-nji gün:","uz":f"🎉 {day}-kun o'tildi! {new_day}-kun:"}
            await update.message.reply_text(ctext.get(lang,ctext["ru"]),reply_markup=mkt_kb)
            await update.message.reply_text(MKT_DAYS[new_day].get(lang,MKT_DAYS[new_day]["ru"]),parse_mode="Markdown",reply_markup=mkt_kb)
        return PARTNER_MENU

    # Кнопка "Повторить день маркетинга"
    if text in list(MKT_REPEAT_BTN.values()):
        day = max(1, mkt_progress_get(user.id))
        if day > 7: day = 7
        mkt_kb = ReplyKeyboardMarkup([[MKT_DONE_BTN.get(lang,MKT_DONE_BTN["ru"])],[MKT_REPEAT_BTN.get(lang,MKT_REPEAT_BTN["ru"])],[p["btn_back"]]],resize_keyboard=True)
        await update.message.reply_text(MKT_DAYS[day].get(lang,MKT_DAYS[day]["ru"]),parse_mode="Markdown",reply_markup=mkt_kb)
        return PARTNER_MENU

    # Кнопка "Просмотреть маркетинг"
    if text == p.get("btn_review_mkt",""):
        days_list = MKT_REVIEW_DAYS.get(lang,MKT_REVIEW_DAYS["ru"])
        kb = ReplyKeyboardMarkup([[d] for d in days_list]+[[p["btn_back"]]],resize_keyboard=True)
        txt = {"ru":"📖 Выберите день маркетинга:","tk":"📖 Marketing gününi saýlaň:","uz":"📖 Marketing kunini tanlang:"}
        await update.message.reply_text(txt.get(lang,txt["ru"]),reply_markup=kb)
        context.user_data["reviewing_mkt"] = True
        return PARTNER_MENU

    # Просмотр дня маркетинга
    if context.user_data.get("reviewing_mkt"):
        days_list = MKT_REVIEW_DAYS.get(lang,MKT_REVIEW_DAYS["ru"])
        if text in days_list:
            idx = days_list.index(text)+1
            kb = ReplyKeyboardMarkup([[d] for d in days_list]+[[p["btn_back"]]],resize_keyboard=True)
            await update.message.reply_text(MKT_DAYS[idx].get(lang,MKT_DAYS[idx]["ru"]),parse_mode="Markdown",reply_markup=kb)
            return PARTNER_MENU
        elif text == p["btn_back"]:
            context.user_data.pop("reviewing_mkt",None)

    # Кнопка "Просмотреть обучение"
    if text == p.get("btn_review_learn",""):
        days_list = LEARN_REVIEW_DAYS.get(lang,LEARN_REVIEW_DAYS["ru"])
        kb = ReplyKeyboardMarkup([[d] for d in days_list]+[[p["btn_back"]]],resize_keyboard=True)
        txt = {"ru":"📖 Выберите день обучения:","tk":"📖 Okuw gününi saýlaň:","uz":"📖 O'qitish kunini tanlang:"}
        await update.message.reply_text(txt.get(lang,txt["ru"]),reply_markup=kb)
        context.user_data["reviewing_learn"] = True
        return PARTNER_MENU

    # Просмотр дня обучения
    if context.user_data.get("reviewing_learn"):
        days_list = LEARN_REVIEW_DAYS.get(lang,LEARN_REVIEW_DAYS["ru"])
        if text in days_list:
            idx = days_list.index(text)+1
            kb = ReplyKeyboardMarkup([[d] for d in days_list]+[[p["btn_back"]]],resize_keyboard=True)
            await update.message.reply_text(DAYS[idx].get(lang,DAYS[idx]["ru"]),parse_mode="Markdown",reply_markup=kb)
            return PARTNER_MENU
        elif text == p["btn_back"]:
            context.user_data.pop("reviewing_learn",None)

    # Тесты — главное меню тестов
    if text == p.get("btn_quiz",""):
        results = quiz_get(user.id)
        rows = []
        for qkey in QUIZ_ORDER:
            qname = QUIZ_NAMES[qkey].get(lang,QUIZ_NAMES[qkey]["ru"])
            res = results.get(qkey)
            label = f"{'✅' if res and res['score']==res['total'] else '📝' if res else '🎯'} {qname}{f' ({res[chr(115)+chr(99)+chr(111)+chr(114)+chr(101)]}/{res[chr(116)+chr(111)+chr(116)+chr(97)+chr(108)]})' if res else ''}"
            rows.append([label])
        rows.append([p["btn_back"]])
        kb = ReplyKeyboardMarkup(rows,resize_keyboard=True)
        txt = {"ru":"🧪 *Тесты*\n\nВыберите тест:","tk":"🧪 *Testler*\n\nTesti saýlaň:","uz":"🧪 *Testlar*\n\nTestni tanlang:"}
        await update.message.reply_text(txt.get(lang,txt["ru"]),parse_mode="Markdown",reply_markup=kb)
        context.user_data["in_quiz_menu"] = True
        return PARTNER_MENU

    # Выбор конкретного теста
    if context.user_data.get("in_quiz_menu"):
        for qkey in QUIZ_ORDER:
            qname = QUIZ_NAMES[qkey].get(lang,QUIZ_NAMES[qkey]["ru"])
            if qname in text:
                context.user_data.pop("in_quiz_menu",None)
                context.user_data["quiz_key"] = qkey
                import random
                qs = QUIZ_DATA[qkey].copy()
                random.shuffle(qs)
                context.user_data["quiz_qs"]    = qs
                context.user_data["quiz_q"]     = 0
                context.user_data["quiz_score"]  = 0
                return await _quiz_send_question(update, context, lang)
        if text == p["btn_back"]:
            context.user_data.pop("in_quiz_menu",None)

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
    context.user_data.pop("reviewing_mkt",None)
    context.user_data.pop("reviewing_learn",None)
    context.user_data.pop("in_quiz_menu",None)
    await update.message.reply_text(p["menu_title"], reply_markup=get_partner_kb(lang))
    return PARTNER_MENU



# ─── Quiz функции ────────────────────────────────────────────

async def _quiz_send_question(update, context, lang):
    qs  = context.user_data.get("quiz_qs",[])
    idx = context.user_data.get("quiz_q",0)
    if idx >= len(qs):
        return await _quiz_finish(update, context, lang)
    q   = qs[idx]
    qt  = q["q"].get(lang, q["q"]["ru"])
    ops = q["o"].get(lang, q["o"]["ru"])
    p   = PT.get(lang, PT["ru"])
    kb  = ReplyKeyboardMarkup([[ops[0]],[ops[1]],[ops[2]],[p["btn_back"]]],resize_keyboard=True)
    total = len(qs)
    hdr = {"ru":f"🧪 Вопрос {idx+1}/{total}","tk":f"🧪 {idx+1}/{total} sorag","uz":f"🧪 {idx+1}/{total} savol"}
    await update.message.reply_text(f"{hdr.get(lang,hdr['ru'])}\n\n{qt}",parse_mode="Markdown",reply_markup=kb)
    return PARTNER_QUIZ

async def _quiz_finish(update, context, lang):
    score  = context.user_data.get("quiz_score",0)
    qkey   = context.user_data.get("quiz_key","")
    total  = len(context.user_data.get("quiz_qs",[]))
    user   = update.effective_user
    uname  = f"@{user.username}" if user.username else str(user.id)
    p      = PT.get(lang, PT["ru"])
    quiz_set(user.id, qkey, score, total)
    await quiz_sync(user.id, qkey, score, total, user.full_name or "", uname)
    pct    = int(score/total*100) if total else 0
    emoji  = "🏆" if pct==100 else "✅" if pct>=70 else "📝"
    comm_ru = "Отлично! Вы отлично знаете тему!" if pct==100 else "Хороший результат!" if pct>=70 else "Рекомендуем повторить материал."
    comm_tk = "Ajayyp!" if pct==100 else "Gowy netije!" if pct>=70 else "Materialy gaytalamagy maslahat beryaris."
    comm_uz = "Zor!" if pct==100 else "Yaxshi natija!" if pct>=70 else "Materialni takrorlashni tavsiya etamiz."
    rtext = {
        "ru": f"{emoji} *Тест завершён!*\n\nПравильных: {score}/{total} ({pct}%)\n\n{comm_ru}",
        "tk": f"{emoji} *Test tamamlandy!*\n\nDogry: {score}/{total} ({pct}%)\n\n{comm_tk}",
        "uz": f"{emoji} *Test yakunlandi!*\n\nTogri: {score}/{total} ({pct}%)\n\n{comm_uz}",
    }
    retry = {"ru":"🔁 Пройти заново","tk":"🔁 Täzeden geç","uz":"🔁 Qayta o'tish"}
    kb = ReplyKeyboardMarkup([[retry.get(lang,retry["ru"])],[p.get("btn_quiz","🧪 Тесты")],[p["btn_back"]]],resize_keyboard=True)
    await update.message.reply_text(rtext.get(lang,rtext["ru"]),parse_mode="Markdown",reply_markup=kb)
    for k in ["quiz_key","quiz_q","quiz_qs","quiz_score"]:
        context.user_data.pop(k,None)
    return PARTNER_MENU

async def partner_quiz_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang  = context.user_data.get("lang","ru")
    user  = update.effective_user
    text  = update.message.text
    p     = PT.get(lang, PT["ru"])

    # Следующий вопрос
    next_btn = {"ru":"➡️ Следующий","tk":"➡️ Indiki","uz":"➡️ Keyingi"}
    if text == next_btn.get(lang,next_btn["ru"]):
        return await _quiz_send_question(update, context, lang)

    # Повторить тест
    retry = {"ru":"🔁 Пройти заново","tk":"🔁 Täzeden geç","uz":"🔁 Qayta o'tish"}
    if text == retry.get(lang,retry["ru"]):
        qkey = context.user_data.get("quiz_key","")
        if qkey:
            import random
            qs = QUIZ_DATA[qkey].copy(); random.shuffle(qs)
            context.user_data["quiz_qs"]   = qs
            context.user_data["quiz_q"]    = 0
            context.user_data["quiz_score"] = 0
            return await _quiz_send_question(update, context, lang)

    # Выход
    if text == p["btn_back"] or text == p.get("btn_quiz",""):
        for k in ["quiz_key","quiz_q","quiz_qs","quiz_score"]:
            context.user_data.pop(k,None)
        if text == p.get("btn_quiz",""):
            results = quiz_get(user.id)
            rows = []
            for qkey in QUIZ_ORDER:
                qname = QUIZ_NAMES[qkey].get(lang,QUIZ_NAMES[qkey]["ru"])
                res = results.get(qkey)
                label = f"{'✅' if res and res['score']==res['total'] else '📝' if res else '🎯'} {qname}"
                if res: label += f" ({res['score']}/{res['total']})"
                rows.append([label])
            rows.append([p["btn_back"]])
            kb = ReplyKeyboardMarkup(rows,resize_keyboard=True)
            txt = {"ru":"🧪 *Тесты*\n\nВыберите тест:","tk":"🧪 *Testler*\n\nTesti saýlaň:","uz":"🧪 *Testlar*\n\nTestni tanlang:"}
            await update.message.reply_text(txt.get(lang,txt["ru"]),parse_mode="Markdown",reply_markup=kb)
            context.user_data["in_quiz_menu"] = True
            return PARTNER_MENU
        await update.message.reply_text(p["menu_title"],reply_markup=get_partner_kb(lang))
        return PARTNER_MENU

    # Проверяем ответ
    qs  = context.user_data.get("quiz_qs",[])
    idx = context.user_data.get("quiz_q",0)
    if idx >= len(qs):
        return await _quiz_finish(update, context, lang)
    q   = qs[idx]
    ops = q["o"].get(lang, q["o"]["ru"])
    ans = q["a"]
    exp = q["e"].get(lang, q["e"]["ru"])
    chosen = None
    for i, opt in enumerate(ops):
        if text == opt:
            chosen = i; break
    if chosen is None:
        return await _quiz_send_question(update, context, lang)
    is_ok = (chosen == ans)
    if is_ok:
        context.user_data["quiz_score"] = context.user_data.get("quiz_score",0)+1
        fb = {"ru":f"✅ *Правильно!*\n\n{exp}","tk":f"✅ *Dogry!*\n\n{exp}","uz":f"✅ *Togri!*\n\n{exp}"}
    else:
        fb = {"ru":f"❌ *Неправильно.*\nПравильный ответ: {ops[ans]}\n\n{exp}",
              "tk":f"❌ *Yalnysh.*\nDogry jogap: {ops[ans]}\n\n{exp}",
              "uz":f"❌ *Notogri.*\nTogri javob: {ops[ans]}\n\n{exp}"}
    context.user_data["quiz_q"] = idx+1
    next_btn2 = {"ru":"➡️ Следующий","tk":"➡️ Indiki","uz":"➡️ Keyingi"}
    kb = ReplyKeyboardMarkup([[next_btn2.get(lang,next_btn2["ru"])]],resize_keyboard=True)
    await update.message.reply_text(fb.get(lang,fb["ru"]),parse_mode="Markdown",reply_markup=kb)
    return PARTNER_QUIZ

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
     ["📣 Рассылка партнёрам","📢 Пост всем пользователям"],
     ["🔙 Выход из админ-меню"]],
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

    # Пост всем пользователям бота
    if text == "📢 Пост всем пользователям":
        context.user_data["admin_post_all"] = True
        all_users = users_get_all()
        partners  = _jload(_PARTNERS_F)
        total = len(all_users)
        await update.message.reply_text(
            f"📢 *Пост всем пользователям* ({total} чел., партнёров: {len(partners)})\n\n"
            f"Отправьте:\n"
            f"• *Текст* — просто напишите сообщение (поддерживается Markdown)\n"
            f"• *Фото с подписью* — прикрепите картинку и добавьте текст в подписи\n"
            f"• *Фото без текста* — просто отправьте картинку",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardRemove()
        )
        return ADMIN_MENU

    if context.user_data.pop("admin_post_all", False):
        all_users = users_get_all()
        sent = failed = 0
        for uid in all_users:
            try:
                await context.bot.send_message(
                    chat_id=int(uid),
                    text=text,
                    parse_mode="Markdown"
                )
                sent += 1
            except Exception:
                failed += 1
        await update.message.reply_text(
            f"✅ Пост отправлен!\n\n"
            f"📤 Доставлено: {sent}\n"
            f"❌ Ошибок: {failed}\n"
            f"📊 Всего: {sent + failed}",
            reply_markup=ADMIN_KB
        )
        return ADMIN_MENU

    await update.message.reply_text("Выберите действие из меню:", reply_markup=ADMIN_KB)
    return ADMIN_MENU

async def admin_photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получаем фото от admin и рассылаем всем пользователям или партнёрам."""
    if update.effective_user.id != MANAGER_CHAT_ID:
        return
    if not context.user_data.get("admin_post_all") and not context.user_data.get("admin_broadcast"):
        return

    is_all = context.user_data.pop("admin_post_all", False)
    context.user_data.pop("admin_broadcast", False)

    photo   = update.message.photo[-1]  # берём максимальное разрешение
    file_id = photo.file_id
    caption = update.message.caption or ""

    recipients = users_get_all() if is_all else _jload(_PARTNERS_F)
    sent = failed = 0
    for uid in recipients:
        try:
            await context.bot.send_photo(
                chat_id=int(uid),
                photo=file_id,
                caption=caption,
                parse_mode="Markdown"
            )
            sent += 1
        except Exception:
            failed += 1

    label = "всем пользователям" if is_all else "партнёрам"
    await update.message.reply_text(
        f"✅ Пост с фото отправлен {label}!\n\n"
        f"📤 Доставлено: {sent}\n"
        f"❌ Ошибок: {failed}",
        reply_markup=ADMIN_KB
    )
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
    app = Application.builder().token(BOT_TOKEN).post_init(_load_partners_impl).build()

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
            PARTNER_QUIZ:          [MessageHandler(filters.TEXT & ~filters.COMMAND, partner_quiz_handler)],
            ADMIN_MENU:            [
                MessageHandler(filters.PHOTO, admin_photo_handler),
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
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
