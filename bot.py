import logging
import requests
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

# Логирование
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# Макет токена
TOKEN = "8486854020:AAFsauLPBLKNe2_IP5brpeytH4TUAF8AB6A"

# Файл для хранения сообщений пользователей
USER_LOG_FILE = r"G:\1111x6\user_messages.txt"

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

    reply_keyboard = [["Проверить статистику"]]
    await update.message.reply_text(
        text="Привет!",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)
    )

# обработка сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    text = update.message.text.strip()
    
    log_user_message(user, text)  # логируем любое сообщение пользователя

    if text == "Проверить статистику":
        await update.message.reply_text("Введите числовой Dota ID:")
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

        # Mini App кнопка для просмотра истории игр
        player_url = f"https://dota1x6.com/players/{dota_id}"
        inline_keyboard = [
            [InlineKeyboardButton(
                "Посмотреть историю игр",
                web_app=WebAppInfo(url=player_url)
            )]
        ]
        await update.message.reply_text(
            "Вы можете посмотреть историю игр:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard)
        )

    except Exception as e:
        logging.error(f"Ошибка при обработке ID {text}: {e}")
        await update.message.reply_text("Произошла ошибка при получении данных.")

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logging.info("Бот запущен...")
    try:
        app.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        logging.error(f"Ошибка при запуске бота: {e}")
    finally:
        input("Нажмите Enter для выхода...")  # окно не закроется сразу

if __name__ == "__main__":
    main()
