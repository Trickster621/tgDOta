import logging
import requests
from datetime import datetime
from io import BytesIO
from bs4 import BeautifulSoup
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
import os

# Логирование
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# Токен
TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    raise ValueError("Не найден токен бота! Установите переменную окружения BOT_TOKEN.")

# Путь к лог-файлу
USER_LOG_FILE = "/app/user_messages.txt"

# Telegram ID владельца
OWNER_ID = 741409144

# Создаём файл заранее
if not os.path.exists(USER_LOG_FILE):
    open(USER_LOG_FILE, "w", encoding="utf-8").close()

def log_user_message(user, text):
    with open(USER_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(
            f"{datetime.now()} | ID: {user.id} | "
            f"Имя: {user.first_name} | Фамилия: {user.last_name} | "
            f"Username: @{user.username} | Сообщение: {text}\n"
        )

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    log_user_message(user, "/start")

    reply_keyboard = [["Проверить статистику", "Обновления"]]
    await update.message.reply_text(
        "Привет! Выберите действие:",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)
    )

# Обновления
async def updates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    log_user_message(user, "Обновления")

    url = "https://dota1x6.com/updates"
    try:
        response = requests.get(url)
        if response.status_code != 200:
            await update.message.reply_text("Не удалось получить данные с сайта.")
            return

        soup = BeautifulSoup(response.text, "html.parser")
        # Берём последний блок обновления
        last_update = soup.select_one(".update-item")  # корректировать под реальный селектор сайта
        if not last_update:
            await update.message.reply_text("Не удалось найти последнее обновление.")
            return

        # Преобразуем текст
        text = last_update.get_text(separator="\n").strip()

        # Inline-кнопка для всех обновлений
        inline_keyboard = [
            [InlineKeyboardButton("Все обновления", url="https://dota1x6.com/updates")]
        ]
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard)
        )
    except Exception as e:
        logging.error(f"Ошибка при получении обновлений: {e}")
        await update.message.reply_text("Произошла ошибка при получении обновлений.")

# Обработка сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user = update.message.from_user
    log_user_message(user, text)

    if text == "Проверить статистику":
        await update.message.reply_text("Введите числовой Dota ID:")
        return
    elif text == "Обновления":
        await updates(update, context)
        return
    else:
        await update.message.reply_text("Неизвестная команда. Используйте кнопки ниже.")

# /getlog
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
    await update.message.reply_text(f"Последние строки лога:\n\n{last_lines}")

# main
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
