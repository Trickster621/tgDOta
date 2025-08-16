import logging
import requests
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

# Токен из переменной окружения
TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    raise ValueError("Не найден токен бота! Установите переменную окружения BOT_TOKEN.")

# Путь к лог-файлу
USER_LOG_FILE = "/app/user_messages.txt"

# Telegram ID владельца
OWNER_ID = 741409144

# Создаём файл заранее, если его нет
if not os.path.exists(USER_LOG_FILE):
    open(USER_LOG_FILE, "w", encoding="utf-8").close()

def log_user_message(user, text):
    """Сохраняем данные пользователя и сообщение в файл"""
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

# Обработка сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    text = update.message.text.strip()
    
    log_user_message(user, text)

    if text == "Проверить статистику":
        await update.message.reply_text("Введите числовой Dota ID:")
        return

    if text == "Обновления":
        await send_latest_update(update)
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

# Функция отправки последнего обновления
async def send_latest_update(update: Update):
    try:
        url = "https://dota1x6.com/updates"
        response = requests.get(url)
        if response.status_code != 200:
            await update.message.reply_text("Не удалось получить обновления с сайта.")
            return

        # Пример простого парсинга последнего обновления (можно заменить на BeautifulSoup)
        # Берём текст последнего обновления
        data = response.text
        # Здесь можно обработать HTML и найти последнее обновление
        # Для примера просто вставим текст-заглушку:
        latest_update = (
            "🟢 Усиления: Новый герой получил бонус к урону.\n"
            "🛑 Ослабления: Сократилось здоровье у некоторых юнитов.\n"
            "🟪 Эпические таланты обновлены.\n"
            "🟧 Легендарные таланты добавлены.\n"
            "🟦 Редкие таланты исправлены."
        )

        # Кнопка «Все обновления»
        inline_keyboard = [
            [InlineKeyboardButton("Все обновления", web_app=WebAppInfo(url=url))]
        ]
        reply_markup = InlineKeyboardMarkup(inline_keyboard)

        await update.message.reply_text(latest_update, reply_markup=reply_markup)

    except Exception as e:
        logging.error(f"Ошибка при получении последнего обновления: {e}")
        await update.message.reply_text("Произошла ошибка при получении последнего обновления.")

# /getlog — присылает файл только владельцу
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

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("getlog", getlog))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logging.info("Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()
