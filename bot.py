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
# ↓ Вставь числовой ID аккаунта @tach_ttt (узнать через @userinfobot)
MANAGER_CHAT_ID = 699255285  # @tach_ttt
SPONSOR_PHONE_TKM = "+99363327177"
SPONSOR_PHONE_UZB = "+99363327177"
CATALOG_LINK = "https://t.me/Verteratkmbot/vertera_tkm"
REGISTER_LINK = "https://id.boss.vertera.org/register?ref=FEKMPTVL85&service=OS3_PARTNER"

client = OpenAI(api_key=OPENAI_API_KEY)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── Состояния ───────────────────────────────────────────────
SELECT_COUNTRY, SELECT_LANG, CHAT, ANKETA_NAME, ANKETA_PHONE, ANKETA_CITY, ANKETA_INTEREST = range(7)

user_histories = {}

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
            ""
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
            ""
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
            ""
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
            ""
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
    return ReplyKeyboardMarkup(
        [[t["buy"], t["business"]],
         [t["catalog"], t["contact"]],
         [t["home"]]],
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


# ─── Onboarding цепочка ──────────────────────────────────────

ONBOARDING_MSG = {
    # День 0 — сразу после выбора языка
    "day0": {
        "ru": (
            "🌊 *Знакомьтесь — Vertera!*\n\n"
            "В основе всех наших продуктов — *ламинария* и *фукус*: "
            "бурые морские водоросли из экологически чистых морей.\n\n"
            "Они содержат более *140 биологически активных веществ*: "
            "йод, витамины, аминокислоты, полисахариды и антиоксиданты — "
            "всё в той форме, которую организм усваивает максимально.\n\n"
            "Vertera основана в 2014 году. Сегодня продукция компании "
            "представлена в 15+ странах мира. Все продукты прошли "
            "клинические исследования и сертифицированы 🌿"
        ),
        "tk": (
            "🌊 *Tanyşyň — Vertera!*\n\n"
            "Ähli önümlerimiziň esasyny *laminariýa* we *fukus* düzýär: "
            "ekologik taýdan arassa deňizlerden alynýan goňur suw ösümlikleri.\n\n"
            "Olar 140-dan gowrak biologiki işjeň madda öz içine alýar: "
            "ýod, witaminler, aminokislotalar, polisakaridler we antioksidantlar — "
            "bedeniň iň gowy özleşdirýän görnüşinde.\n\n"
            "Vertera 2014-nji ýylda esaslandyryldy. Häzir önümler "
            "dünýäniň 15+ ýurdunda bar. Ähli önümler kliniki synagdan geçdi 🌿"
        ),
        "uz": (
            "🌊 *Tanishing — Vertera!*\n\n"
            "Barcha mahsulotlarimizning asosini *laminaria* va *fukus* tashkil etadi: "
            "ekologik toza dengizlardan olinadigan jigarrang suv o'tlari.\n\n"
            "Ular 140 dan ortiq biologik faol modda o'z ichiga oladi: "
            "yod, vitaminlar, aminokislotalar, polisakaridlar va antioksidantlar — "
            "organizm eng yaxshi o'zlashtiradigan shaklda.\n\n"
            "Vertera 2014 yilda tashkil etilgan. Bugun mahsulotlar "
            "15+ mamlakatda mavjud. Barcha mahsulotlar klinik sinovdan o'tgan 🌿"
        ),
    },

    # Через 10 минут — каталог
    "day0_10min": {
        "ru": "🛍 *Вот что есть в нашем каталоге:*\n\n{catalog}",
        "tk": "🛍 *Biziň katalogymyzda bar bolan önümler:*\n\n{catalog}",
        "uz": "🛍 *Bizning katalogimizda mavjud mahsulotlar:*\n\n{catalog}",
    },

    # Через 1 час — технология PLASMA
    "day0_1h": {
        "ru": (
            "🔬 *Технология PLASMA — в чём секрет?*\n\n"
            "Все продукты Vertera созданы с применением запатентованной "
            "технологии *PLASMA* — это гидролизат бурых морских водорослей.\n\n"
            "Благодаря ей активные вещества водорослей переходят в "
            "наночастицы — они проникают в клетки напрямую, минуя "
            "пищеварительные барьеры.\n\n"
            "Результат: биодоступность в *3–5 раз выше*, чем у обычных "
            "продуктов из водорослей.\n\n"
            "Именно поэтому эффект ощущается быстро 💧"
        ),
        "tk": (
            "🔬 *PLASMA tehnologiýasy — syr näme?*\n\n"
            "Ähli Vertera önümleri patentlenen *PLASMA* tehnologiýasy "
            "bilen döredildi — bu goňur suw ösümlikleriniň gidrolizaty.\n\n"
            "Onuň kömegi bilen suw ösümlikleriniň işjeň maddalary "
            "nanozarryjalara öwrülýär — olar iýmit siňdiriş päsgelçiliklerini "
            "aşyp, öýjüklere göni aralaşýar.\n\n"
            "Netije: Biodostuplugy adaty önümlerden *3–5 esse ýokary*.\n\n"
            "Şonuň üçin täsir tiz duýulýar 💧"
        ),
        "uz": (
            "🔬 *PLASMA texnologiyasi — sir nimada?*\n\n"
            "Barcha Vertera mahsulotlari patentlangan *PLASMA* texnologiyasi "
            "asosida yaratilgan — bu jigarrang suv o'tlarining gidrolizati.\n\n"
            "Uning yordamida suv o'tlarining faol moddalari nanozarrachalarga "
            "aylanadi — ular hazm to'siqlarini chetlab, to'g'ridan-to'g'ri "
            "hujayralarga kiradi.\n\n"
            "Natija: Biodostuplik oddiy mahsulotlardan *3–5 marta yuqori*.\n\n"
            "Shuning uchun ta'sir tez seziladi 💧"
        ),
    },

    # Через 1 день — прогрев на бизнес
    "day1": {
        "ru": (
            "💼 *Vertera — это не просто продукт*\n\n"
            "Тысячи людей в СНГ уже строят стабильный доход, "
            "просто рекомендуя Vertera своим близким.\n\n"
            "Как это работает:\n"
            "• Попробовал сам → убедился в результате\n"
            "• Рассказал другу → он купил со скидкой 30%\n"
            "• Получил доход — и так по цепочке\n\n"
            "Никаких офисов, складов или вложений.\n"
            "Только рекомендации — и реальный результат 🌿\n\n"
            "Хотите узнать подробнее? Нажмите кнопку *«💼 Бизнес с Vertera»*"
        ),
        "tk": (
            "💼 *Vertera — bu diňe bir önüm däl*\n\n"
            "MDB-de müňlerçe adam öz ýakynlaryna Vertera maslahat bermek "
            "arkaly durnukly girdeji gazanýar.\n\n"
            "Bu nähili işleýär:\n"
            "• Özüň synap gör → netijä ynan\n"
            "• Dostuna aýt → ol 30% arzanladyş bilen satyn aldy\n"
            "• Girdeji al — şeýdip dowam edýär\n\n"
            "Hiç ofis, ammar ýa-da maýa goýum ýok.\n"
            "Diňe maslahatlar — we hakyky netije 🌿\n\n"
            "Giňişleýin bilmek isleýärsiňizmi? *«💼 Vertera bilen iş»* düwmesine basyň"
        ),
        "uz": (
            "💼 *Vertera — bu faqat mahsulot emas*\n\n"
            "MDHda minglab odamlar Verterani yaqinlariga tavsiya qilish "
            "orqali barqaror daromad topmoqda.\n\n"
            "Bu qanday ishlaydi:\n"
            "• O'zing sinab ko'r → natijaga ishon\n"
            "• Do'stingga ayt → u 30% chegirma bilan sotib oldi\n"
            "• Daromad ol — va shu zanjir davom etadi\n\n"
            "Hech ofis, ombor yoki sarmoya yo'q.\n"
            "Faqat tavsiyalar — va haqiqiy natija 🌿\n\n"
            "Batafsil bilmoqchimisiz? *«💼 Vertera bilan biznes»* tugmasini bosing"
        ),
    },
}

async def onboarding_job(context) -> None:
    """Отправляет одно сообщение из onboarding цепочки."""
    job   = context.job
    user_id  = job.data["user_id"]
    lang     = job.data["lang"]
    country  = job.data["country"]
    msg_key  = job.data["msg_key"]

    msg_data = ONBOARDING_MSG.get(msg_key, {})
    text = msg_data.get(lang, msg_data.get("ru", ""))

    # Для каталога подставляем список продуктов
    if msg_key == "day0_10min":
        catalog = get_catalog_text(lang, country)
        text = text.format(catalog=catalog)

    if not text:
        return

    lang_data = TEXTS.get(lang, TEXTS["ru"])
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=text,
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(
                [[lang_data["buy"], lang_data["business"]],
                 [lang_data["catalog"], lang_data["contact"]],
                 [lang_data.get("change_lang", "🌐 Сменить страну / язык")]],
                resize_keyboard=True
            )
        )
    except Exception as e:
        logger.error(f"Onboarding job error {user_id}/{msg_key}: {e}")

def schedule_onboarding(context, user_id: int, lang: str, country: str):
    """Планирует всю цепочку onboarding сообщений."""
    base = f"onboard_{user_id}"

    # Отменяем старые jobs если были
    for key in ["day0_10min", "day0_1h", "day1"]:
        for job in context.job_queue.get_jobs_by_name(f"{base}_{key}"):
            job.schedule_removal()

    data_base = {"user_id": user_id, "lang": lang, "country": country}

    # Через 10 минут — каталог
    context.job_queue.run_once(
        onboarding_job, when=600,
        data={**data_base, "msg_key": "day0_10min"},
        name=f"{base}_day0_10min", chat_id=user_id, user_id=user_id,
    )
    # Через 1 час — технология
    context.job_queue.run_once(
        onboarding_job, when=3600,
        data={**data_base, "msg_key": "day0_1h"},
        name=f"{base}_day0_1h", chat_id=user_id, user_id=user_id,
    )
    # Через 1 день — бизнес
    context.job_queue.run_once(
        onboarding_job, when=86400,
        data={**data_base, "msg_key": "day1"},
        name=f"{base}_day1", chat_id=user_id, user_id=user_id,
    )


# ─── Напоминание после просмотра каталога/продуктов ──────────

CATALOG_REMINDER_MSG = {
    "ru": (
        "👀 *Вы смотрели наши продукты!*\n\n"
        "Если остались вопросы — я здесь 🌿\n\n"
        "Хотите узнать какой продукт подойдёт именно вам? "
        "Просто напишите мне или заполните анкету — "
        "наш менеджер подберёт лучший вариант и расскажет про скидку 30% 👇"
    ),
    "tk": (
        "👀 *Siz önümlerimize serediňiz!*\n\n"
        "Soraglaryňyz galan bolsa — men şu ýerde 🌿\n\n"
        "Haýsy önümiň size laýyk gelýändigini bilmek isleýärsiňizmi? "
        "Maňa ýazyň ýa-da anketa dolduryň — "
        "menejerimiz iň gowy görnüşi saýlar we 30% arzanladyş hakda aýdar 👇"
    ),
    "uz": (
        "👀 *Siz mahsulotlarimizga qaradingiz!*\n\n"
        "Savollar qolgan bo'lsa — men shu yerdaman 🌿\n\n"
        "Qaysi mahsulot aynan sizga mos kelishini bilmoqchimisiz? "
        "Menga yozing yoki anketa to'ldiring — "
        "menejerimiz eng yaxshi variantni tanlaydi va 30% chegirma haqida aytadi 👇"
    ),
}

def db_set_catalog_viewed(user_id: int):
    """Фиксируем что пользователь смотрел каталог/продукты."""
    try:
        with shelve.open(DB_PATH) as db:
            db[f"catalog_{user_id}"] = {"viewed": True, "acted": False}
    except Exception as e:
        logger.error(f"DB catalog_viewed error: {e}")

def db_set_catalog_acted(user_id: int):
    """Пользователь совершил действие — напоминание не нужно."""
    try:
        with shelve.open(DB_PATH) as db:
            db[f"catalog_{user_id}"] = {"viewed": True, "acted": True}
    except Exception as e:
        logger.error(f"DB catalog_acted error: {e}")

def db_catalog_needs_reminder(user_id: int) -> bool:
    """True если смотрел каталог но не совершил действие."""
    try:
        with shelve.open(DB_PATH) as db:
            data = db.get(f"catalog_{user_id}")
            return bool(data and data.get("viewed") and not data.get("acted"))
    except Exception as e:
        logger.error(f"DB catalog_reminder check: {e}")
        return False

async def send_catalog_reminder(context) -> None:
    """Job: напоминание через 2 часа после просмотра каталога без действий."""
    job = context.job
    user_id = job.data["user_id"]
    lang    = job.data["lang"]

    if not db_catalog_needs_reminder(user_id):
        return

    text = CATALOG_REMINDER_MSG.get(lang, CATALOG_REMINDER_MSG["ru"])
    lang_data = TEXTS.get(lang, TEXTS["ru"])
    keyboard = ReplyKeyboardMarkup(
        [[lang_data["anketa_yes"]], [lang_data["buy"]], [lang_data.get("change_lang", "")]],
        resize_keyboard=True
    )
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=text,
            parse_mode="Markdown",
            reply_markup=keyboard
        )
        logger.info(f"Catalog reminder sent to {user_id}")
    except Exception as e:
        logger.error(f"Catalog reminder error {user_id}: {e}")

def schedule_catalog_reminder(context, user_id: int, lang: str):
    """Ставит напоминание через 2 часа."""
    job_name = f"cat_remind_{user_id}"
    # Отменяем старый job если был
    for job in context.job_queue.get_jobs_by_name(job_name):
        job.schedule_removal()
    context.job_queue.run_once(
        send_catalog_reminder,
        when=7200,  # 2 часа
        data={"user_id": user_id, "lang": lang},
        name=job_name,
        chat_id=user_id,
        user_id=user_id,
    )

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

    # День 0 — сразу отправляем первое сообщение о компании
    day0_text = ONBOARDING_MSG["day0"].get(lang, ONBOARDING_MSG["day0"]["ru"])
    await update.message.reply_text(
        day0_text,
        parse_mode="Markdown",
        reply_markup=get_main_keyboard(lang)
    )

    # Запускаем остальные сообщения цепочки
    schedule_onboarding(context, user.id, lang, country)

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

    # Кнопка каталога
    if text in [t["catalog"], "📖 Каталог", "📖 Katalog"]:
        catalog_text = get_catalog_text(lang, country)
        await update.message.reply_text(
            catalog_text,
            parse_mode="Markdown",
            reply_markup=get_main_keyboard(lang)
        )
        # Фиксируем просмотр и ставим напоминание через 2 часа
        db_set_catalog_viewed(user.id)
        schedule_catalog_reminder(context, user.id, lang)
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
        # Фиксируем интерес — напоминание не нужно
        db_set_catalog_acted(user.id)
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
        db_set_catalog_acted(user.id)
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
    user = update.effective_user
    # Каталог просмотрен с действием — не напоминать
    db_set_catalog_acted(user.id)
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
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            SELECT_COUNTRY: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_country)],
            SELECT_LANG: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_lang)],
            CHAT: [
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
