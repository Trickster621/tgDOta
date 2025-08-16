import logging
import requests
from datetime import datetime
from io import BytesIO
from bs4 import BeautifulSoup
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
import os

# Логирование
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# Токен бота
TOKEN = os.environ.get("BOT_TOKEN") or "ВАШ_НОВЫЙ_ТОКЕН"

# Telegram ID владельца
OWNER_ID = 741409144

# Путь к лог-файлу
USER_LOG_FILE = "user_messages.txt"
if not os.path.exists(USER_LOG_FILE):
    open(USER_LOG_FILE, "w", encoding="utf-8").close()

def log_user_message(user, text):
    with open(USER_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now()} | ID: {user.id} | Имя: {user.first_name} | "
                f"Фамилия: {user.last_name} | Username: @{user.username} | Сообщение: {text}\n")

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    log_user_message(user, "/start")
    reply_keyboard = [["Проверить статистику", "Обновления"]]
    await update.message.reply_text(
        "Привет! Выберите действие:",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)
    )

# Обработка сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    text = update.message.text.strip()
    log_user_message(user, text)

    if text == "Проверить статистику":
        await update.message.reply_text("Введите числовой Dota ID:")
        return

    if text == "Обновления":
        await send_last_update(update)
        return

    if not text.isdigit():
        await update.message.reply_text("Неизвестная команда. Используйте кнопки ниже.")
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

        msg = (f"Всего игр: {match_count}\n"
               f"Среднее место: {avg_place}\n"
               f"Первых мест: {first_places}\n"
               f"Рейтинг: {rating}")
        await update.message.reply_text(msg)

        # Mini App кнопка
        player_url = f"https://dota1x6.com/players/{dota_id}"
        inline_keyboard = [
            [InlineKeyboardButton("Посмотреть историю игр", web_app=WebAppInfo(url=player_url))]
        ]
        await update.message.reply_text(
            "Вы можете посмотреть историю игр:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard)
        )

    except Exception as e:
        logging.error(f"Ошибка при обработке ID {text}: {e}")
        await update.message.reply_text("Произошла ошибка при получении данных.")

# Последнее обновление
async def send_last_update(update: Update):
    try:
        url = "https://dota1x6.com/updates"
        response = requests.get(url)
        if response.status_code != 200:
            await update.message.reply_text("Не удалось получить последние обновления.")
            return

        soup = BeautifulSoup(response.text, "html.parser")
        # Берем первую строчку обновления
        first_update = soup.find("td") or soup.find("div", class_="update-row")
        if not first_update:
            await update.message.reply_text("Не удалось найти последнее обновление.")
            return

        text_update = first_update.get_text(strip=True)
        await update.message.reply_text(f"Последнее обновление:\n\n{text_update}")

    except Exception as e:
        logging.error(f"Ошибка при получении обновлений: {e}")
        await update.message.reply_text("Произошла ошибка при получении обновлений.")

# Логи владельцу
async def getlog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    log_user_message(user, "/getlog")

    if user.id != OWNER_ID:
        await update.message.reply_text("Нет доступа")
        return

    if not os.path.exists(USER_LOG_FILE):
        await update.message.reply_text("Файл логов пуст.")
        return

    with open(USER_LOG_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    bio = BytesIO()
    bio.write(content.encode("utf-8"))
    bio.seek(0)
    await update.message.reply_document(document=bio, filename="user_messages.txt")

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
