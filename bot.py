import logging
import requests
from io import BytesIO
from bs4 import BeautifulSoup
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, WebAppInfo
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

# Файл логов
USER_LOG_FILE = "/app/user_messages.txt"
if not os.path.exists(USER_LOG_FILE):
    open(USER_LOG_FILE, "w", encoding="utf-8").close()

OWNER_ID = 741409144  # Telegram ID владельца

def log_user_message(user, text):
    with open(USER_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{user.id} | {user.username} | {text}\n")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    log_user_message(user, "/start")

    keyboard = [["Проверить статистику", "Обновления"]]
    await update.message.reply_text(
        "Привет! Выберите действие:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(k, callback_data=k)] for k in keyboard[0]])
    )

async def updates_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправка последнего обновления"""
    user = update.message.from_user
    log_user_message(user, "/updates")

    try:
        url = "https://dota1x6.com/updates"
        response = requests.get(url)
        soup = BeautifulSoup(response.text, "html.parser")

        # Ищем блок последнего обновления
        latest_block = soup.select_one(".updates__item")
        if not latest_block:
            await update.message.reply_text("Не удалось найти последнее обновление.")
            return

        # Текст изменений
        text_lines = []
        for li in latest_block.select("li"):
            line_text = li.get_text(strip=True)

            # Проверка картинок для смайликов
            imgs = li.find_all("img")
            for img in imgs:
                src = img.get("src", "")
                if "aghanims_shard.png" in src:
                    line_text = "🔹 " + line_text
                elif "innate.png" in src:
                    line_text = "🔥 " + line_text
                elif "ultimate_scepter.png" in src:
                    line_text = "🔮 " + line_text

            text_lines.append(line_text)

        full_text = "\n".join(text_lines)
        if not full_text:
            full_text = latest_block.get_text(strip=True)

        # Скачиваем изображения из блока
        images = []
        for img in latest_block.find_all("img"):
            img_url = img.get("src")
            try:
                img_resp = requests.get(img_url)
                bio = BytesIO()
                bio.write(img_resp.content)
                bio.seek(0)
                images.append(InputMediaPhoto(bio))
            except:
                continue

        # Отправляем текст и изображения
        if images:
            await update.message.reply_media_group(images)
        await update.message.reply_text(full_text)

        # Кнопка "Все обновления"
        inline_keyboard = [
            [InlineKeyboardButton("Все обновления", web_app=WebAppInfo(url=url))]
        ]
        await update.message.reply_text("Все обновления:", reply_markup=InlineKeyboardMarkup(inline_keyboard))

    except Exception as e:
        logging.error(f"Ошибка при получении обновлений: {e}")
        await update.message.reply_text("Произошла ошибка при получении обновлений.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Простой эхо для любых текстовых сообщений
    user = update.message.from_user
    log_user_message(user, update.message.text)
    await update.message.reply_text("Используйте кнопки для действий.")

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("updates", updates_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logging.info("Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()
