import logging
import json
import os
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import aiohttp
from dotenv import load_dotenv

load_dotenv()

# ─── Настройки ───────────────────────────────────────────────
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")
IQAIR_API_KEY   = os.getenv("IQAIR_API_KEY")

USERS_FILE = "users.json"

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── Тексты на двух языках ────────────────────────────────────
T = {
    "ru": {
        "welcome": "👋 Привет! Я бот погоды.\n\n📍 Укажи свой город — кнопка *Мой город*\n⏰ Выбери время рассылки — кнопка *Время рассылки*\n🌤 Узнай прогноз — кнопка *Погода*\n🌬 Качество воздуха — кнопка *Качество воздуха*",
        "choose_lang": "🌐 Выбери язык / Tilni tanlang:",
        "btn_weather": "🌤 Погода",
        "btn_city": "📍 Мой город",
        "btn_time": "⏰ Время рассылки",
        "btn_status": "📊 Статус",
        "btn_air": "🌬 Качество воздуха",
        "btn_lang": "🌐 Язык",
        "btn_location": "📍 Отправить мою геолокацию",
        "btn_cancel": "❌ Отмена",
        "ask_city": "📍 Как хочешь указать город?\n\n• Напиши название города (например: *Ташкент*)\n• Или нажми кнопку ниже чтобы отправить геолокацию",
        "ask_time": "⏰ В какое время присылать ежедневный прогноз?\nНапиши в формате *ЧЧ:ММ*, например: *07:30*",
        "city_saved": "✅ Город сохранён: *{}*\n\nТеперь выбери время рассылки — кнопка *Время рассылки*",
        "city_found": "✅ Город определён: *{}*\n\nТеперь выбери время рассылки — кнопка *Время рассылки*",
        "city_not_found": "❌ Город не найден. Попробуй ещё раз.",
        "detecting_city": "📍 Определяю твой город...",
        "city_error": "❌ Не удалось определить город. Попробуй ввести вручную.",
        "time_saved": "✅ Время рассылки установлено: *{}*\n\nКаждый день в {} я буду присылать прогноз! 🌤",
        "time_error": "❌ Неверный формат. Напиши время как *07:30*",
        "no_city": "❗ Сначала укажи город — кнопка *Мой город*",
        "loading_weather": "⏳ Получаю почасовой прогноз...",
        "loading_air": "⏳ Получаю данные о воздухе...",
        "weather_error": "❌ Не удалось получить прогноз.",
        "air_error": "❌ Не удалось получить данные о воздухе.",
        "coord_error": "❌ Не удалось определить координаты города.",
        "status": "📊 *Твои настройки:*\n\n📍 Город: *{}*\n⏰ Время рассылки: *{}*\n🌐 Язык: *{}*",
        "cancelled": "Отменено.",
        "use_buttons": "Используй кнопки меню внизу 👇",
        "forecast_title": "🕐 *Почасовой прогноз — {}*\n📍 {}\n",
        "forecast_footer": "🌡 Диапазон: *{}°C — {}°C*  💧 {}%",
        "air_title": "🌬 *Качество воздуха*\n📍 {}\n\nИндекс AQI: *{}*\nОценка: *{}*",
        "lang_changed": "✅ Язык изменён на Русский!",
        "not_set": "не задан",
        "not_set_time": "не задано",
        "aqi_1": "😊 Отлично", "aqi_2": "🙂 Хорошо", "aqi_3": "😐 Умеренно",
        "aqi_4": "😷 Плохо", "aqi_5": "🤢 Очень плохо", "aqi_6": "☠️ Опасно",
    },
    "uz": {
        "welcome": "👋 Salom! Men ob-havo botiman.\n\n📍 Shaharingizni kiriting — *Mening shahrim* tugmasi\n⏰ Yuborish vaqtini tanlang — *Yuborish vaqti* tugmasi\n🌤 Prognozni ko'ring — *Ob-havo* tugmasi\n🌬 Havo sifati — *Havo sifati* tugmasi",
        "choose_lang": "🌐 Выбери язык / Tilni tanlang:",
        "btn_weather": "🌤 Ob-havo",
        "btn_city": "📍 Mening shahrim",
        "btn_time": "⏰ Yuborish vaqti",
        "btn_status": "📊 Holat",
        "btn_air": "🌬 Havo sifati",
        "btn_lang": "🌐 Til",
        "btn_location": "📍 Joylashuvimni yuborish",
        "btn_cancel": "❌ Bekor qilish",
        "ask_city": "📍 Shaharni qanday ko'rsatmoqchisiz?\n\n• Shahar nomini yozing (masalan: *Toshkent*)\n• Yoki joylashuvni yuborish uchun tugmani bosing",
        "ask_time": "⏰ Kunlik prognoz qaysi vaqtda yuborilsin?\nFormat: *SS:DD*, masalan: *07:30*",
        "city_saved": "✅ Shahar saqlandi: *{}*\n\nEndi yuborish vaqtini tanlang — *Yuborish vaqti* tugmasi",
        "city_found": "✅ Shahar aniqlandi: *{}*\n\nEndi yuborish vaqtini tanlang — *Yuborish vaqti* tugmasi",
        "city_not_found": "❌ Shahar topilmadi. Qaytadan urinib ko'ring.",
        "detecting_city": "📍 Shahringiz aniqlanmoqda...",
        "city_error": "❌ Shaharni aniqlab bo'lmadi. Qo'lda kiriting.",
        "time_saved": "✅ Yuborish vaqti belgilandi: *{}*\n\nHar kuni {} da prognoz yuboraman! 🌤",
        "time_error": "❌ Noto'g'ri format. Vaqtni *07:30* ko'rinishida yozing",
        "no_city": "❗ Avval shaharni kiriting — *Mening shahrim* tugmasi",
        "loading_weather": "⏳ Soatlik prognoz yuklanmoqda...",
        "loading_air": "⏳ Havo ma'lumotlari yuklanmoqda...",
        "weather_error": "❌ Prognozni olib bo'lmadi.",
        "air_error": "❌ Havo ma'lumotlarini olib bo'lmadi.",
        "coord_error": "❌ Shahar koordinatalarini aniqlab bo'lmadi.",
        "status": "📊 *Sozlamalaringiz:*\n\n📍 Shahar: *{}*\n⏰ Yuborish vaqti: *{}*\n🌐 Til: *{}*",
        "cancelled": "Bekor qilindi.",
        "use_buttons": "Pastdagi tugmalardan foydalaning 👇",
        "forecast_title": "🕐 *Soatlik prognoz — {}*\n📍 {}\n",
        "forecast_footer": "🌡 Diapazon: *{}°C — {}°C*  💧 {}%",
        "air_title": "🌬 *Havo sifati*\n📍 {}\n\nAQI indeksi: *{}*\nBaho: *{}*",
        "lang_changed": "✅ Til O'zbekchaga o'zgartirildi!",
        "not_set": "kiritilmagan",
        "not_set_time": "belgilanmagan",
        "aqi_1": "😊 A'lo", "aqi_2": "🙂 Yaxshi", "aqi_3": "😐 O'rtacha",
        "aqi_4": "😷 Yomon", "aqi_5": "🤢 Juda yomon", "aqi_6": "☠️ Xavfli",
    }
}

# ─── Хранилище ───────────────────────────────────────────────
def load_users() -> dict:
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_users(users: dict):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def get_lang(uid: str) -> str:
    users = load_users()
    return users.get(uid, {}).get("lang", "ru")

def t(uid: str, key: str) -> str:
    return T[get_lang(uid)][key]

# ─── Меню ────────────────────────────────────────────────────
def main_menu(uid: str):
    lang = get_lang(uid)
    keyboard = [
        [KeyboardButton(T[lang]["btn_weather"]), KeyboardButton(T[lang]["btn_city"])],
        [KeyboardButton(T[lang]["btn_time"]),    KeyboardButton(T[lang]["btn_status"])],
        [KeyboardButton(T[lang]["btn_air"]),     KeyboardButton(T[lang]["btn_lang"])],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def lang_menu():
    keyboard = [
        [KeyboardButton("🇷🇺 Русский"), KeyboardButton("🇺🇿 O'zbekcha")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

# ─── Иконка погоды ───────────────────────────────────────────
def weather_icon(desc: str) -> str:
    d = desc.lower()
    if "гроза" in d or "thunderstorm" in d: return "⛈️"
    if "дождь" in d or "rain" in d:         return "🌧️"
    if "снег" in d or "snow" in d:          return "❄️"
    if "туман" in d or "fog" in d:          return "🌫️"
    if "пасмурн" in d or "overcast" in d:   return "☁️"
    if "облач" in d or "cloud" in d:        return "⛅"
    return "☀️"

# ─── Качество воздуха (IQair) ────────────────────────────────
def aqi_label(aqi: int, uid: str) -> str:
    if aqi <= 50:  return t(uid, "aqi_1")
    if aqi <= 100: return t(uid, "aqi_2")
    if aqi <= 150: return t(uid, "aqi_3")
    if aqi <= 200: return t(uid, "aqi_4")
    if aqi <= 300: return t(uid, "aqi_5")
    return t(uid, "aqi_6")

async def get_air_quality(lat: float, lon: float, uid: str) -> str:
    url = f"https://api.airvisual.com/v2/nearest_city?lat={lat}&lon={lon}&key={IQAIR_API_KEY}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
    if data.get("status") != "success":
        return None
    pollution = data["data"]["current"]["pollution"]
    aqi = pollution["aqius"]
    city = data["data"]["city"]
    return t(uid, "air_title").format(city, aqi, aqi_label(aqi, uid))

# ─── Прогноз ─────────────────────────────────────────────────
async def get_hourly_forecast(city: str, uid: str) -> str:
    url = f"https://api.openweathermap.org/data/2.5/forecast?q={city}&appid={WEATHER_API_KEY}&units=metric&lang=ru&cnt=40"
    return await _build_forecast(url, city, uid)

async def get_hourly_forecast_by_coords(lat: float, lon: float, uid: str = "0") -> tuple:
    url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={WEATHER_API_KEY}&units=metric&lang=ru&cnt=40"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                return None, None
            data = await resp.json()
    city_name = data["city"]["name"]
    return city_name, await _build_forecast_from_data(data, city_name, uid)

async def _build_forecast(url: str, city_label: str, uid: str) -> str:
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
    return await _build_forecast_from_data(data, city_label, uid)

async def _build_forecast_from_data(data: dict, city_label: str, uid: str) -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    now_hour = datetime.now().hour
    today_items = [
        item for item in data["list"]
        if item["dt_txt"].startswith(today)
        and datetime.strptime(item["dt_txt"], "%Y-%m-%d %H:%M:%S").hour >= now_hour
    ]
    if len(today_items) < 2:
        today_items = data["list"][:8]

    lines = [t(uid, "forecast_title").format(datetime.now().strftime("%d.%m.%Y"), city_label)]
    for item in today_items:
        dt = datetime.strptime(item["dt_txt"], "%Y-%m-%d %H:%M:%S")
        temp  = round(item["main"]["temp"])
        feels = round(item["main"]["feels_like"])
        wind  = round(item["wind"]["speed"])
        desc  = item["weather"][0]["description"].capitalize()
        icon  = weather_icon(desc)
        lines.append(f"🕐 *{dt.strftime('%H:%M')}* — {icon} *{temp}°C* (ощущ. {feels}°C) · 💨 {wind} м/с\n_{desc}_\n")

    all_temps = [i["main"]["temp"] for i in today_items]
    humidity  = round(sum(i["main"]["humidity"] for i in today_items) / len(today_items))
    lines.append("─────────────────")
    lines.append(t(uid, "forecast_footer").format(round(min(all_temps)), round(max(all_temps)), humidity))
    return "\n".join(lines)

# ─── Handlers ────────────────────────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    await update.message.reply_text(T["ru"]["choose_lang"], reply_markup=lang_menu())

async def cmd_setcity(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    ctx.user_data["awaiting"] = "city"
    keyboard = [
        [KeyboardButton(t(uid, "btn_location"), request_location=True)],
        [KeyboardButton(t(uid, "btn_cancel"))]
    ]
    await update.message.reply_text(
        t(uid, "ask_city"), parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    )

async def cmd_settime(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    ctx.user_data["awaiting"] = "time"
    await update.message.reply_text(t(uid, "ask_time"), parse_mode="Markdown")

async def cmd_weather(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    users = load_users()
    info  = users.get(uid, {})
    city  = info.get("city")
    if not city:
        await update.message.reply_text(t(uid, "no_city"), parse_mode="Markdown")
        return
    await update.message.reply_text(t(uid, "loading_weather"))
    lat, lon = info.get("lat"), info.get("lon")
    if lat and lon:
        _, text = await get_hourly_forecast_by_coords(lat, lon, uid)
    else:
        text = await get_hourly_forecast(city, uid)
    await update.message.reply_text(text if text else t(uid, "weather_error"), parse_mode="Markdown")

async def cmd_air(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid   = str(update.effective_user.id)
    users = load_users()
    info  = users.get(uid, {})
    city  = info.get("city")
    if not city:
        await update.message.reply_text(t(uid, "no_city"), parse_mode="Markdown")
        return
    lat, lon = info.get("lat"), info.get("lon")
    if not lat or not lon:
        url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={WEATHER_API_KEY}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    d = await resp.json()
                    lat, lon = d["coord"]["lat"], d["coord"]["lon"]
    if not lat or not lon:
        await update.message.reply_text(t(uid, "coord_error"))
        return
    await update.message.reply_text(t(uid, "loading_air"))
    text = await get_air_quality(lat, lon, uid)
    await update.message.reply_text(text if text else t(uid, "air_error"), parse_mode="Markdown")

async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid   = str(update.effective_user.id)
    users = load_users()
    info  = users.get(uid, {})
    city  = info.get("city", t(uid, "not_set"))
    send_time = info.get("send_time", t(uid, "not_set_time"))
    lang_name = "Русский" if get_lang(uid) == "ru" else "O'zbekcha"
    await update.message.reply_text(t(uid, "status").format(city, send_time, lang_name), parse_mode="Markdown")

async def cmd_lang(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    await update.message.reply_text(T["ru"]["choose_lang"], reply_markup=lang_menu())

async def handle_location(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    lat = update.message.location.latitude
    lon = update.message.location.longitude
    await update.message.reply_text(t(uid, "detecting_city"))
    city_name, text = await get_hourly_forecast_by_coords(lat, lon, uid)
    if not city_name:
        await update.message.reply_text(t(uid, "city_error"))
        return
    users = load_users()
    users.setdefault(uid, {}).update({"city": city_name, "lat": lat, "lon": lon})
    save_users(users)
    ctx.user_data["awaiting"] = None
    await update.message.reply_text(t(uid, "city_found").format(city_name), parse_mode="Markdown", reply_markup=main_menu(uid))

async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid     = str(update.effective_user.id)
    awaiting = ctx.user_data.get("awaiting")
    text    = update.message.text.strip()
    users   = load_users()
    lang    = get_lang(uid)

    # Выбор языка
    if text == "🇷🇺 Русский":
        users.setdefault(uid, {})["lang"] = "ru"
        save_users(users)
        await update.message.reply_text(T["ru"]["lang_changed"], reply_markup=main_menu(uid))
        await update.message.reply_text(T["ru"]["welcome"], parse_mode="Markdown", reply_markup=main_menu(uid))
        return
    if text == "🇺🇿 O'zbekcha":
        users.setdefault(uid, {})["lang"] = "uz"
        save_users(users)
        await update.message.reply_text(T["uz"]["lang_changed"], reply_markup=main_menu(uid))
        await update.message.reply_text(T["uz"]["welcome"], parse_mode="Markdown", reply_markup=main_menu(uid))
        return

    # Кнопки меню (оба языка)
    if text in (T["ru"]["btn_weather"], T["uz"]["btn_weather"]):
        await cmd_weather(update, ctx); return
    if text in (T["ru"]["btn_city"], T["uz"]["btn_city"]):
        await cmd_setcity(update, ctx); return
    if text in (T["ru"]["btn_time"], T["uz"]["btn_time"]):
        await cmd_settime(update, ctx); return
    if text in (T["ru"]["btn_status"], T["uz"]["btn_status"]):
        await cmd_status(update, ctx); return
    if text in (T["ru"]["btn_air"], T["uz"]["btn_air"]):
        await cmd_air(update, ctx); return
    if text in (T["ru"]["btn_lang"], T["uz"]["btn_lang"]):
        await cmd_lang(update, ctx); return
    if text in (T["ru"]["btn_cancel"], T["uz"]["btn_cancel"]):
        ctx.user_data["awaiting"] = None
        await update.message.reply_text(t(uid, "cancelled"), reply_markup=main_menu(uid)); return

    if awaiting == "city":
        result = await get_hourly_forecast(text, uid)
        if result is None:
            await update.message.reply_text(t(uid, "city_not_found")); return
        users.setdefault(uid, {}).update({"city": text})
        users[uid].pop("lat", None); users[uid].pop("lon", None)
        save_users(users)
        ctx.user_data["awaiting"] = None
        await update.message.reply_text(t(uid, "city_saved").format(text), parse_mode="Markdown", reply_markup=main_menu(uid))

    elif awaiting == "time":
        try:
            datetime.strptime(text, "%H:%M")
        except ValueError:
            await update.message.reply_text(t(uid, "time_error"), parse_mode="Markdown"); return
        users.setdefault(uid, {})["send_time"] = text
        save_users(users)
        ctx.user_data["awaiting"] = None
        await update.message.reply_text(t(uid, "time_saved").format(text, text), parse_mode="Markdown", reply_markup=main_menu(uid))
    else:
        await update.message.reply_text(t(uid, "use_buttons"), reply_markup=main_menu(uid))

# ─── Планировщик ─────────────────────────────────────────────
async def send_daily_weather(app: Application):
    users = load_users()
    now = datetime.now().strftime("%H:%M")
    for uid, info in users.items():
        if info.get("send_time") == now and info.get("city"):
            lat, lon = info.get("lat"), info.get("lon")
            if lat and lon:
                _, text = await get_hourly_forecast_by_coords(lat, lon, uid)
            else:
                text = await get_hourly_forecast(info["city"], uid)
            if text:
                try:
                    await app.bot.send_message(chat_id=int(uid), text=text, parse_mode="Markdown")
                except Exception as e:
                    logger.warning(f"Ошибка {uid}: {e}")

async def post_init(app: Application):
    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_daily_weather, "interval", minutes=1, args=[app])
    scheduler.start()
    logger.info("Планировщик запущен!")

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.LOCATION, handle_location))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    logger.info("Бот запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()
