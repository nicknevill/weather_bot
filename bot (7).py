import logging
import json
import os
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import aiohttp

USERS_FILE = "users.json"

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ─── Хранилище пользователей ─────────────────────────────────
def load_users() -> dict:
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_users(users: dict):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

# ─── Иконка погоды ───────────────────────────────────────────
def weather_icon(desc: str) -> str:
    d = desc.lower()
    if "гроза" in d:                    return "⛈️"
    if "дождь" in d or "ливень" in d:   return "🌧️"
    if "снег" in d:                     return "❄️"
    if "туман" in d or "мгла" in d:     return "🌫️"
    if "пасмурн" in d:                  return "☁️"
    if "облач" in d:                    return "⛅"
    return "☀️"

# ─── Почасовой прогноз по названию города ────────────────────
async def get_hourly_forecast(city: str) -> str:
    url = (
        f"https://api.openweathermap.org/data/2.5/forecast"
        f"?q={city}&appid={WEATHER_API_KEY}&units=metric&lang=ru&cnt=40"
    )
    return await _build_forecast(url, city)

# ─── Почасовой прогноз по координатам ────────────────────────
async def get_hourly_forecast_by_coords(lat: float, lon: float) -> tuple:
    url = (
        f"https://api.openweathermap.org/data/2.5/forecast"
        f"?lat={lat}&lon={lon}&appid={WEATHER_API_KEY}&units=metric&lang=ru&cnt=40"
    )
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                return None, None
            data = await resp.json()
    city_name = data["city"]["name"]
    text = await _build_forecast_from_data(data, city_name)
    return city_name, text

async def _build_forecast(url: str, city_label: str) -> str:
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
    return await _build_forecast_from_data(data, city_label)

async def _build_forecast_from_data(data: dict, city_label: str) -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    now_hour = datetime.now().hour

    today_items = [
        item for item in data["list"]
        if item["dt_txt"].startswith(today)
        and datetime.strptime(item["dt_txt"], "%Y-%m-%d %H:%M:%S").hour >= now_hour
    ]
    if len(today_items) < 2:
        today_items = data["list"][:8]

    lines = [f"🕐 *Почасовой прогноз — {datetime.now().strftime('%d.%m.%Y')}*\n📍 {city_label}\n"]

    for item in today_items:
        dt = datetime.strptime(item["dt_txt"], "%Y-%m-%d %H:%M:%S")
        hour_str = dt.strftime("%H:%M")
        temp = round(item["main"]["temp"])
        feels = round(item["main"]["feels_like"])
        wind = round(item["wind"]["speed"])
        desc = item["weather"][0]["description"].capitalize()
        icon = weather_icon(desc)
        lines.append(
            f"🕐 *{hour_str}* — {icon} *{temp}°C* (ощущ. {feels}°C) · 💨 {wind} м/с\n"
            f"_{desc}_\n"
        )

    all_temps = [i["main"]["temp"] for i in today_items]
    humidity = round(sum(i["main"]["humidity"] for i in today_items) / len(today_items))
    lines.append("─────────────────")
    lines.append(f"🌡 Диапазон: *{round(min(all_temps))}°C — {round(max(all_temps))}°C*  💧 {humidity}%")
    return "\n".join(lines)

# ─── Главное меню ─────────────────────────────────────────────
def main_menu():
    keyboard = [
        [KeyboardButton("🌤 Погода"), KeyboardButton("📍 Мой город")],
        [KeyboardButton("⏰ Время рассылки"), KeyboardButton("📊 Статус")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ─── Команды бота ─────────────────────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привет! Я бот погоды.\n\n"
        "📍 Укажи свой город — кнопка *Мой город*\n"
        "⏰ Выбери время рассылки — кнопка *Время рассылки*\n"
        "🌤 Узнай прогноз — кнопка *Погода*",
        reply_markup=main_menu(),
        parse_mode="Markdown"
    )

async def cmd_setcity(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["awaiting"] = "city"
    keyboard = [
        [KeyboardButton("📍 Отправить мою геолокацию", request_location=True)],
        [KeyboardButton("❌ Отмена")]
    ]
    markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text(
        "📍 Как хочешь указать город?\n\n"
        "• Напиши название города (например: *Ташкент*)\n"
        "• Или нажми кнопку ниже чтобы отправить геолокацию",
        parse_mode="Markdown",
        reply_markup=markup
    )

async def cmd_settime(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["awaiting"] = "time"
    await update.message.reply_text(
        "⏰ В какое время присылать ежедневный прогноз?\n"
        "Напиши в формате *ЧЧ:ММ*, например: *07:30*",
        parse_mode="Markdown"
    )

async def cmd_weather(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    users = load_users()
    uid = str(update.effective_user.id)
    info = users.get(uid, {})
    city = info.get("city")
    if not city:
        await update.message.reply_text("❗ Сначала укажи город — кнопка *Мой город*", parse_mode="Markdown")
        return
    await update.message.reply_text("⏳ Получаю почасовой прогноз...")
    lat = info.get("lat")
    lon = info.get("lon")
    if lat and lon:
        _, text = await get_hourly_forecast_by_coords(lat, lon)
    else:
        text = await get_hourly_forecast(city)
    if text:
        await update.message.reply_text(text, parse_mode="Markdown")
    else:
        await update.message.reply_text("❌ Не удалось получить прогноз.")

async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    users = load_users()
    uid = str(update.effective_user.id)
    info = users.get(uid, {})
    city = info.get("city", "не задан")
    send_time = info.get("send_time", "не задано")
    await update.message.reply_text(
        f"📊 *Твои настройки:*\n\n"
        f"📍 Город: *{city}*\n"
        f"⏰ Время рассылки: *{send_time}*",
        parse_mode="Markdown"
    )

# ─── Обработка геолокации ─────────────────────────────────────
async def handle_location(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    lat = update.message.location.latitude
    lon = update.message.location.longitude
    await update.message.reply_text("📍 Определяю твой город...")
    city_name, text = await get_hourly_forecast_by_coords(lat, lon)
    if city_name is None:
        await update.message.reply_text("❌ Не удалось определить город. Попробуй ввести вручную.")
        return
    uid = str(update.effective_user.id)
    users = load_users()
    users.setdefault(uid, {})["city"] = city_name
    users[uid]["lat"] = lat
    users[uid]["lon"] = lon
    save_users(users)
    ctx.user_data["awaiting"] = None
    await update.message.reply_text(
        f"✅ Город определён: *{city_name}*\n\nТеперь выбери время рассылки — кнопка *Время рассылки*",
        parse_mode="Markdown",
        reply_markup=main_menu()
    )

# ─── Обработка текста и кнопок ───────────────────────────────
async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    awaiting = ctx.user_data.get("awaiting")
    text = update.message.text.strip()
    uid = str(update.effective_user.id)
    users = load_users()

    # Кнопки главного меню
    if text == "🌤 Погода":
        await cmd_weather(update, ctx)
        return
    if text == "📍 Мой город":
        await cmd_setcity(update, ctx)
        return
    if text == "⏰ Время рассылки":
        await cmd_settime(update, ctx)
        return
    if text == "📊 Статус":
        await cmd_status(update, ctx)
        return
    if text == "❌ Отмена":
        ctx.user_data["awaiting"] = None
        await update.message.reply_text("Отменено.", reply_markup=main_menu())
        return

    if awaiting == "city":
        result = await get_hourly_forecast(text)
        if result is None:
            await update.message.reply_text("❌ Город не найден. Попробуй ещё раз.")
            return
        users.setdefault(uid, {})["city"] = text
        users[uid].pop("lat", None)
        users[uid].pop("lon", None)
        save_users(users)
        ctx.user_data["awaiting"] = None
        await update.message.reply_text(
            f"✅ Город сохранён: *{text}*\n\nТеперь выбери время рассылки — кнопка *Время рассылки*",
            parse_mode="Markdown",
            reply_markup=main_menu()
        )
    elif awaiting == "time":
        try:
            datetime.strptime(text, "%H:%M")
        except ValueError:
            await update.message.reply_text("❌ Неверный формат. Напиши время как *07:30*", parse_mode="Markdown")
            return
        users.setdefault(uid, {})["send_time"] = text
        save_users(users)
        ctx.user_data["awaiting"] = None
        await update.message.reply_text(
            f"✅ Время рассылки установлено: *{text}*\n\nКаждый день в {text} я буду присылать прогноз! 🌤",
            parse_mode="Markdown",
            reply_markup=main_menu()
        )
    else:
        await update.message.reply_text(
            "Используй кнопки меню внизу 👇",
            reply_markup=main_menu()
        )

# ─── Планировщик ─────────────────────────────────────────────
async def send_daily_weather(app: Application):
    users = load_users()
    now = datetime.now().strftime("%H:%M")
    for uid, info in users.items():
        if info.get("send_time") == now and info.get("city"):
            lat = info.get("lat")
            lon = info.get("lon")
            if lat and lon:
                _, text = await get_hourly_forecast_by_coords(lat, lon)
            else:
                text = await get_hourly_forecast(info["city"])
            if text:
                try:
                    await app.bot.send_message(chat_id=int(uid), text=text, parse_mode="Markdown")
                except Exception as e:
                    logger.warning(f"Не удалось отправить {uid}: {e}")

async def post_init(app: Application):
    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_daily_weather, "interval", minutes=1, args=[app])
    scheduler.start()
    logger.info("Планировщик запущен!")

# ─── Запуск ───────────────────────────────────────────────────
def main():
    app = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .post_init(post_init)
        .build()
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.LOCATION, handle_location))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("Бот запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()
