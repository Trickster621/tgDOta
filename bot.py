import logging
import requests
from datetime import datetime
from io import BytesIO
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
from bs4 import BeautifulSoup
import os

# Логирование
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# Токен бота
TOKEN = os.environ.get("BOT_TOKEN") or "ВАШ_ТОКЕН"

# Telegram ID владельца
OWNER_ID = 741409144

# Путь к лог-файлу
USER_LOG_FILE = "user_messages.txt"
if not os.path.exists(USER_LOG_FILE):
    open(USER_LOG_FILE, "w", encoding="utf-8").close()

def log_user_message(user, text):
    with open(USER_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now()} | ID: {user.id} | Имя: {user.first_name} | Сообщение: {text}\n")

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    log_user_message(user, "/start")
    reply_keyboard = [["Проверить статистику"], ["Обновления"]]
    await update.message.reply_text(
        text="Привет! Выберите опцию:",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)
    )

# Парсинг последнего обновления
def get_latest_update():
    url = "https://dota1x6.com/updates"
    resp = requests.get(url)
    if resp.status_code != 200:
        return None

    soup = BeautifulSoup(resp.text, "html.parser")
    # Ищем все td с bg-dark
    update_cells = soup.find_all("td", class_=lambda x: x and "bg-dark" in x)
    if not update_cells:
        return None

    latest_text = update_cells[0].get_text(strip=True)

    # Добавляем эмодзи по правилам
    # 🔹 — shrad, 🔥 — innate, 🔮 — ultimate
    # Здесь можно усложнить парсинг и искать img в td
    return latest_text

# Обработка сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    text = update.message.text.strip()
    log_user_message(user, text)

    if text == "Проверить статистику":
        await update.message.reply_text("Введите числовой Dota ID:")
        return

    if text == "Обновления":
        latest_update = get_latest_update()
        if not latest_update:
            await update.message.reply_text("Не удалось получить последнее обновление.")
            return
        inline_keyboard = [
            [InlineKeyboardButton("Все обновления", url="https://dota1x6.com/updates")]
        ]
        await update.message.reply_text(
            f"Последнее обновление:\n\n{latest_update}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard)
        )
        return

    if not text.isdigit():
        await update.message.reply_text("Пожалуйста, введите только числовой Dota ID.")
        return

    dota_id = text
    url = f"https://stats.dota1x6.com/api/v2/players/?playerId={dota_id}"
    try:
        response = requests.get(url)
        if response.status_code != 200:
            await update.message.reply_text("Не удалось получить данные с API.")
            return

        data = response.json().get("data")
        if not data:
            await update.message.reply_text("Игрок с таким ID не найден.")
            return

        match_count = data.get("matchCount", "неизвестно")
        avg_place = round(data.get("avgPlace", 0), 2)
        first_places = data.get("firstPlaces", "неизвестно")
        rating = data.get("rating", "неизвестно")

        msg = (
            f"Всего игр: {match_count}\n"
            f"Среднее место: {avg_place}\n"
            f"Первых мест: {first_places}\n"
            f"Рейтинг: {rating}"
        )
        await update.message.reply_text(msg)

    except Exception as e:
        logging.error(f"Ошибка при обработке ID {text}: {e}")
        await update.message.reply_text("Произошла ошибка при получении данных.")

# /getlog
async def getlog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    log_user_message(user, "/getlog")
    if user.id != OWNER_ID:
        await update.message.reply_text("Нет доступа")
        return
    with open(USER_LOG_FILE, "r", encoding="utf-8") as f:
        bio = BytesIO(f.read().encode("utf-8"))
    bio.seek(0)
    await update.message.reply_document(document=bio, filename="user_messages.txt")

# /previewlog
async def previewlog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    log_user_message(user, "/previewlog")
    if user.id != OWNER_ID:
        await update.message.reply_text("Нет доступа")
        return
    with open(USER_LOG_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()
    last_lines = "".join(lines[-50:]) if lines else "(пусто)"
    if len(last_lines) > 3500:
        last_lines = last_lines[-3500:]
    await update.message.reply_text(f"Последние строки лога:\n\n{last_lines}")

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("getlog", getlog))
    app.add_handler(CommandHandler("previewlog", previewlog))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logging.info("Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()
