import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from io import BytesIO
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
import os

# Логирование
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# Токен бота
TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    raise ValueError("Не найден токен бота! Установите переменную окружения BOT_TOKEN.")

# Путь к лог-файлу
USER_LOG_FILE = "/app/user_messages.txt"
OWNER_ID = 741409144

# Создаём файл заранее, если его нет
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
        text="Привет! Выберите действие:",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)
    )

# Функция парсинга последнего обновления
def get_latest_update_text():
    base_url = "https://dota1x6.com"
    updates_url = f"{base_url}/updates"

    response = requests.get(updates_url)
    if response.status_code != 200:
        return "Не удалось получить страницу обновлений."

    soup = BeautifulSoup(response.text, "html.parser")

    latest_update_link = soup.find("a", class_="update-item")  # замените на реальный класс ссылки
    if not latest_update_link or not latest_update_link.get("href"):
        return "Не удалось найти ссылку на последнее обновление."

    latest_url = base_url + latest_update_link.get("href")
    resp_update = requests.get(latest_url)
    if resp_update.status_code != 200:
        return "Не удалось получить текст последнего обновления."

    update_soup = BeautifulSoup(resp_update.text, "html.parser")
    update_block = update_soup.find("div", class_="update-content")  # замените на реальный класс текста
    if not update_block:
        return "Не удалось найти текст обновления."

    lines = []
    for element in update_block.find_all(recursive=False):
        text = element.get_text(strip=True)

        # Смайлики по картинкам
        imgs = element.find_all("img")
        for img in imgs:
            src = img.get("src", "")
            if "aghanims_shard.png" in src:
                text = f"🔹 {text}"
            elif "innate.png" in src:
                text = f"🔥 {text}"
            elif "ultimate_scepter.png" in src:
                text = f"🔮 {text}"

        # Категории
        if "Усиление" in text:
            text = f"🟢 {text} 🟢"
        elif "Ослабление" in text:
            text = f"🛑 {text} 🛑"
        elif "Эпический талант" in text:
            text = f"🟪 {text}"
        elif "Легендарный талант" in text:
            text = f"🟧 {text}"
        elif "Редкий талант" in text:
            text = f"🟦 {text}"

        lines.append(text)

    return "\n".join(lines)

# Обработка сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    text = update.message.text.strip()
    
    log_user_message(user, text)

    if text == "Обновления":
        update_text = get_latest_update_text()
        inline_keyboard = [
            [InlineKeyboardButton(
                "Все обновления",
                web_app=WebAppInfo(url="https://dota1x6.com/updates")
            )]
        ]
        await update.message.reply_text(
            update_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard)
        )
        return

    # Остальной функционал по статистике можно добавить здесь
    await update.message.reply_text("Функционал для этого текста пока не реализован.")

# /getlog
async def getlog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    log_user_message(user, "/getlog")

    if user.id != OWNER_ID:
        await update.message.reply_text("Нет доступа")
        return

    if not os.path.exists(USER_LOG_FILE):
        await update.message.reply_text("Файл логов пока пуст или не создан.")
        return

    try:
        with open(USER_LOG_FILE, "r", encoding="utf-8") as f:
            content = f.read()
        bio = BytesIO()
        bio.write(content.encode("utf-8"))
        bio.seek(0)
        await update.message.reply_document(document=bio, filename="user_messages.txt")
    except Exception as e:
        logging.error(f"Ошибка при отправке лога: {e}")
        await update.message.reply_text("Не удалось отправить лог-файл.")

# /previewlog
async def previewlog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    log_user_message(user, "/previewlog")

    if user.id != OWNER_ID:
        await update.message.reply_text("Нет доступа")
        return

    if not os.path.exists(USER_LOG_FILE):
        await update.message.reply_text("Файл логов пока пуст или не создан.")
        return

    try:
        with open(USER_LOG_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
        last_lines = "".join(lines[-50:]) if lines else "(пусто)"
        if len(last_lines) > 3500:
            last_lines = last_lines[-3500:]
        await update.message.reply_text(f"Последние строки лога:\n\n{last_lines}")
    except Exception as e:
        logging.error(f"Ошибка при previewlog: {e}")
        await update.message.reply_text("Не удалось прочитать лог.")

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("getlog", getlog))
    app.add_handler(CommandHandler("previewlog", previewlog))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logging.info("Бот запущен...")
    try:
        app.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        logging.error(f"Ошибка при запуске бота: {e}")
    finally:
        input("Нажмите Enter для выхода...")

if __name__ == "__main__":
    main()
