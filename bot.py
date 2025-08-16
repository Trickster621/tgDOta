import logging
import requests
from datetime import datetime
from io import BytesIO
from bs4 import BeautifulSoup
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
import os
import asyncio
import subprocess
import sys
from playwright.async_api import async_playwright

# --- Конфигурация логирования ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__) # Используем именованный логгер

# --- Конфигурация бота ---
TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    logger.error("Переменная окружения BOT_TOKEN не установлена!")
    # В продакшене бот не запустится без токена, но для локального тестирования можно раскомментировать:
    # TOKEN = "ВАШ_ТЕЛЕГРАМ_ТОКЕН"

OWNER_ID = 741409144 # Замените на ваш Telegram ID

# --- Логирование сообщений пользователей ---
USER_LOG_FILE = "user_messages.txt"
if not os.path.exists(USER_LOG_FILE):
    try:
        with open(USER_LOG_FILE, "w", encoding="utf-8") as f:
            pass # Создаем пустой файл
        logger.info(f"Создан файл логов: {USER_LOG_FILE}")
    except Exception as e:
        logger.error(f"Не удалось создать файл логов {USER_LOG_FILE}: {e}")

def log_user_message(user, text):
    """Сохраняем данные пользователя и сообщение в файл"""
    try:
        with open(USER_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(
                f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | "
                f"ID: {user.id} | Имя: {user.first_name} | "
                f"Фамилия: {user.last_name or 'N/A'} | "
                f"Username: @{user.username or 'N/A'} | Сообщение: {text}\n"
            )
    except Exception as e:
        logger.error(f"Ошибка при записи в лог-файл: {e}")

# --- Инициализация Playwright ---
async def install_playwright_browsers():
    """
    Устанавливает браузеры для Playwright.
    Выполняется один раз при запуске приложения.
    """
    logger.info("Проверка и установка браузеров Playwright...")
    try:
        # Команда для установки Chromium
        cmd = [sys.executable, "-m", "playwright", "install", "chromium", "--with-deps"]
        logger.info(f"Выполнение команды: {' '.join(cmd)}")
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        if process.returncode == 0:
            logger.info("Playwright Chromium установлен успешно или уже был установлен.")
            if stdout:
                logger.debug(f"Playwright install stdout: {stdout.decode()}")
        else:
            logger.error(f"Ошибка установки Playwright. Код возврата: {process.returncode}")
            if stderr:
                logger.error(f"Playwright install stderr: {stderr.decode()}")
            # Не останавливаем запуск, возможно, браузер уже есть
    except Exception as e:
        logger.error(f"Неожиданная ошибка при установке браузеров Playwright: {e}", exc_info=True)

# --- Обработчики команд и сообщений ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    log_user_message(user, "/start")
    reply_keyboard = [["Проверить статистику", "Обновления"]]
    await update.message.reply_text(
        text="Привет! Выберите действие:",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    user = update.effective_user
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

    # Обработка ввода Dota ID
    dota_id = text
    url = f"https://stats.dota1x6.com/api/v2/players/?playerId={dota_id}"
    logger.info(f"Запрос к API для ID {dota_id}")
    
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status() # Проверка на HTTP ошибки
        
        data = response.json().get("data")
        if not data:
            await update.message.reply_text("Игрок с таким ID не найден.")
            return

        match_count = data.get("matchCount", "N/A")
        avg_place = round(data.get("avgPlace", 0), 2)
        first_places = data.get("firstPlaces", "N/A")
        rating = data.get("rating", "N/A")

        msg = (
            f"📊 *Статистика игрока {dota_id}*:\n"
            f"Всего игр: {match_count}\n"
            f"Среднее место: {avg_place}\n"
            f"Первых мест: {first_places}\n"
            f"Рейтинг: {rating}"
        )
        await update.message.reply_text(msg, parse_mode='Markdown')

        # Кнопка Mini App
        player_url = f"https://dota1x6.com/players/{dota_id}"
        inline_keyboard = [
            [InlineKeyboardButton("Посмотреть историю игр", web_app=WebAppInfo(url=player_url))]
        ]
        await update.message.reply_text(
            "Вы можете посмотреть историю игр:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard)
        )

    except requests.exceptions.Timeout:
        logger.error(f"Таймаут при запросе к API для ID {dota_id}")
        await update.message.reply_text("⚠️ Превышено время ожидания ответа от API.")
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка сети при запросе к API для ID {dota_id}: {e}")
        await update.message.reply_text("⚠️ Ошибка подключения к API.")
    except ValueError as e: # Ошибки парсинга JSON
        logger.error(f"Ошибка парсинга JSON от API для ID {dota_id}: {e}")
        await update.message.reply_text("⚠️ Получены некорректные данные от API.")
    except Exception as e:
        logger.error(f"Неожиданная ошибка при обработке ID {dota_id}: {e}", exc_info=True)
        await update.message.reply_text("⚠️ Произошла ошибка при получении данных.")

async def send_last_update(update: Update):
    """Получает и отправляет последнее обновление с сайта dota1x6.com/updates"""
    logger.info("Пользователь запросил последние обновления.")
    status_message = await update.message.reply_text("🔍 Ищу последние обновления...")

    try:
        url = "https://dota1x6.com/updates"
        
        # --- Получение и рендеринг главной страницы обновлений ---
        logger.info(f"Запуск Playwright для {url}")
        async with async_playwright() as p:
            # Запуск браузера
            browser = await p.chromium.launch(
                headless=True,
                # args=['--no-sandbox'] # Часто требуется в Docker-контейнерах
            )
            logger.debug("Браузер запущен.")
            
            page = await browser.new_page()
            logger.debug(f"Переход на {url}")
            
            # Переход на страницу и ожидание загрузки
            await page.goto(url, wait_until='networkidle', timeout=30000)
            logger.debug("Страница загружена, жду выполнения JS...")
            
            # Дополнительное ожидание для полной загрузки контента
            await page.wait_for_timeout(5000)
            
            # Получение отрендеренного HTML
            html_content = await page.content()
            logger.debug(f"HTML получен, длина: {len(html_content)} символов.")
            await browser.close()

        # --- Парсинг списка обновлений ---
        logger.debug("Парсинг HTML списка обновлений...")
        soup = BeautifulSoup(html_content, "html.parser")

        # Проверка, загрузилась ли страница корректно
        if "You need to enable JavaScript" in html_content:
            logger.warning("Страница обновлений всё ещё показывает заглушку JavaScript.")
            # Можно попробовать увеличить wait_for_timeout или использовать wait_for_selector
            # для ожидания конкретного элемента
        
        # Поиск контейнера с обновлениями
        # Структура может быть разной, пробуем несколько вариантов
        updates_container = None
        # Часто обновления находятся внутри <main>, <div id="root">, или <div> с определенным классом
        potential_containers = [
            soup.find("div", id="root"), # React app часто здесь
            soup.find("main"),
            soup.find("div", class_=["container", "content", "main-content"]),
        ]
        for container in potential_containers:
            if container:
                updates_container = container
                logger.debug(f"Найден потенциальный контейнер: {container.name} ({container.get('id')}, {container.get('class')})")
                break
        
        if not updates_container:
            updates_container = soup.body if soup.body else soup
            logger.warning("Контейнер обновлений не найден по селекторам, использую body или весь soup.")

        # Поиск ссылок на отдельные обновления
        # Обычно это ссылки вида /updates/some-title
        update_links = updates_container.find_all("a", href=lambda href: href and href.startswith("/updates/") and href != "/updates/")
        logger.debug(f"Найдено {len(update_links)} ссылок на обновления.")
        
        if not update_links:
            # План Б: ищем любые ссылки с "updates" в href
            update_links = updates_container.find_all("a", href=lambda href: href and "updates" in href and href not in ["/updates", "/updates/"])
            logger.debug(f"План Б: найдено {len(update_links)} ссылок с 'updates' в href.")

        if not update_links:
            # План В: ищем заголовки, возможно, они кликабельны
            headers = updates_container.find_all(['h1', 'h2', 'h3', 'h4'], string=lambda text: text and "обновлен" in text.lower())
            logger.debug(f"План В: найдено {len(headers)} заголовков с 'обновлен'.")
            # Тут логика сложнее, пропустим для простоты

        if not update_links:
            logger.error("Не найдены ссылки на страницы обновлений.")
            # Отправим пользователю часть HTML для отладки (только владельцу)
            preview_html = html_content[:2000] if len(html_content) > 2000 else html_content
            await status_message.edit_text(
                "❌ Не удалось найти обновления на странице. "
                "Структура сайта могла измениться. "
                "Информация отправлена администратору."
            )
            if update.effective_user.id == OWNER_ID:
                await update.message.reply_text(
                    f"Для отладки: первые 2000 символов HTML:\n```\n{preview_html}\n```",
                    parse_mode='MarkdownV2'
                )
            return

        # Берем первую ссылку (предполагаем, что она ведет к последнему обновлению)
        latest_update_link = update_links[0]['href']
        full_update_url = f"https://dota1x6.com{latest_update_link}" if latest_update_link.startswith('/') else latest_update_link
        logger.info(f"Найдена ссылка на последнее обновление: {full_update_url}")

        # --- Получение и рендеринг страницы конкретного обновления ---
        logger.info(f"Запуск Playwright для страницы обновления {full_update_url}")
        async with async_playwright() as p:
            browser_detail = await p.chromium.launch(headless=True)
            page_detail = await browser_detail.new_page()
            logger.debug(f"Переход на {full_update_url}")
            
            await page_detail.goto(full_update_url, wait_until='networkidle', timeout=30000)
            logger.debug("Страница обновления загружена, жду выполнения JS...")
            await page_detail.wait_for_timeout(5000)
            
            detail_html_content = await page_detail.content()
            logger.debug(f"HTML деталей обновления получен, длина: {len(detail_html_content)} символов.")
            await browser_detail.close()

        # --- Парсинг деталей обновления ---
        logger.debug("Парсинг HTML деталей обновления...")
        detail_soup = BeautifulSoup(detail_html_content, "html.parser")
        
        if "You need to enable JavaScript" in detail_html_content:
            logger.warning("Страница деталей обновления всё ещё показывает заглушку JavaScript.")

        # Извлечение заголовка
        title = "Без названия"
        # Ищем заголовок в <title>, <h1>, <h2> и т.д.
        title_tag = detail_soup.find('title')
        if title_tag:
            title = title_tag.get_text(strip=True).replace(" - Dota 1x6", "") # Часто сайт добавляет суффикс
        else:
            header_tag = detail_soup.find(['h1', 'h2'])
            if header_tag:
                title = header_tag.get_text(strip=True)
        
        logger.info(f"Заголовок обновления: {title}")

        # Извлечение основного текста
        # Ищем основной контент
        content_div = None
        potential_content_selectors = [
            "article", # Семантический тег для статьи
            "div.content",
            "div.post-content",
            "div.entry-content",
            "main", # Если весь main - это содержимое
        ]
        for selector in potential_content_selectors:
            content_div = detail_soup.select_one(selector)
            if content_div:
                logger.debug(f"Найден контент по селектору: {selector}")
                break
        
        if not content_div:
            content_div = detail_soup.body if detail_soup.body else detail_soup
            logger.warning("Контент не найден по селекторам, использую body или весь soup.")

        # Получаем текст, стараясь сохранить структуру
        content_text = content_div.get_text(separator='\n', strip=True) if content_div else "Нет текста."
        
        # Ограничиваем длину текста для Telegram
        max_length = 3500
        if len(content_text) > max_length:
            content_text = content_text[:max_length] + "\n...\n(Текст обрезан)"

        # Отправка заголовка и текста
        message_text = f"🆕 *{title}*\n\n{content_text}"
        if len(message_text) > 4096:
            message_text = message_text[:4090] + "..."
        
        await status_message.edit_text("✅ Найдено последнее обновление! Отправляю...")
        try:
            await update.message.reply_text(message_text, parse_mode='Markdown')
        except Exception as e: # Если Markdown не прошел
            logger.warning(f"Не удалось отправить с Markdown: {e}. Отправляю без форматирования.")
            await update.message.reply_text(f"🆕 {title}\n\n{content_text}"[:4096]) # Еще одна проверка длины

        # --- Поиск и отправка изображений ---
        images = content_div.find_all("img") if content_div else []
        logger.info(f"Найдено {len(images)} изображений в контенте.")
        
        sent_images = 0
        max_images = 5
        for img in images:
            if sent_images >= max_images:
                await update.message.reply_text(f"(Есть ещё изображения, отправка ограничена {max_images} шт.)")
                break

            img_src = img.get("src") or img.get("data-src") or img.get("data-lazy-src")
            if not img_src:
                continue

            # Обработка относительных путей
            if img_src.startswith(("http://", "https://")):
                img_url = img_src
            elif img_src.startswith('/'):
                img_url = f"https://dota1x6.com{img_src}"
            else:
                img_url = f"https://dota1x6.com/{img_src}"
            
            logger.debug(f"Попытка загрузки изображения: {img_url}")
            try:
                img_resp = requests.get(img_url, timeout=20)
                if img_resp.status_code == 200 and img_resp.content:
                    await update.message.reply_photo(photo=BytesIO(img_resp.content))
                    sent_images += 1
                    logger.info(f"Изображение отправлено: {img_url}")
                else:
                    logger.warning(f"Не удалось загрузить изображение {img_url}, статус: {img_resp.status_code}")
            except requests.exceptions.RequestException as e:
                logger.error(f"Ошибка сети при загрузке изображения {img_url}: {e}")
            except Exception as e:
                logger.error(f"Ошибка при загрузке/отправке изображения {img_url}: {e}", exc_info=True)

        if sent_images == 0 and images:
            await update.message.reply_text("Изображения найдены на странице, но не удалось их загрузить.")

        # Кнопка "Все обновления"
        inline_keyboard = [[InlineKeyboardButton("Все обновления", url="https://dota1x6.com/updates")]]
        await update.message.reply_text(
            "Полный список обновлений:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard)
        )

    except asyncio.TimeoutError:
        logger.error("Таймаут при работе с Playwright.")
        await status_message.edit_text("⏰ Превышено время ожидания загрузки страницы обновлений.")
    except Exception as e:
        logger.error(f"Ошибка при получении обновлений: {e}", exc_info=True)
        await status_message.edit_text("❌ Произошла ошибка при получении обновлений.")
        # Отправляем сообщение об ошибке владельцу
        if update.effective_user.id == OWNER_ID:
            await update.message.reply_text(f"Детали ошибки (только для админа):\n`{str(e)[:500]}`", parse_mode='MarkdownV2')

# --- Команды для администратора ---

async def getlog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет файл логов (только для владельца)"""
    user = update.effective_user
    log_user_message(user, "/getlog")

    if user.id != OWNER_ID:
        await update.message.reply_text("🚫 Нет доступа")
        return

    if not os.path.exists(USER_LOG_FILE) or os.path.getsize(USER_LOG_FILE) == 0:
        await update.message.reply_text("📭 Файл логов пуст или не существует.")
        return

    try:
        with open(USER_LOG_FILE, "rb") as f:
            await update.message.reply_document(document=f, filename="user_messages.txt")
    except Exception as e:
        logger.error(f"Ошибка при отправке лога: {e}")
        await update.message.reply_text("❌ Произошла ошибка при отправке файла логов.")

async def previewlog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет последние 50 строк лога (только для владельца)"""
    user = update.effective_user
    log_user_message(user, "/previewlog")

    if user.id != OWNER_ID:
        await update.message.reply_text("🚫 Нет доступа")
        return

    try:
        with open(USER_LOG_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        if not lines:
             await update.message.reply_text("📭 Лог пуст.")
             return
             
        last_lines = "".join(lines[-50:]) if lines else "(пусто)"
        if len(last_lines) > 3500:
            last_lines = last_lines[-3500:]
            
        await update.message.reply_text(
            f"```\nПоследние строки лога:\n\n{last_lines}\n```",
            parse_mode='MarkdownV2'
        )
    except Exception as e:
        logger.error(f"Ошибка при предпросмотре лога: {e}")
        await update.message.reply_text("❌ Произошла ошибка при получении предпросмотра лога.")

# --- Точка входа ---

async def main_async():
    """Асинхронная точка входа для инициализации и запуска бота."""
    logger.info("Начало инициализации бота...")
    
    # 1. Установка браузеров Playwright
    await install_playwright_browsers()
    
    # 2. Проверка токена
    if not TOKEN:
        logger.critical("Токен бота не установлен! Завершение работы.")
        return # Завершаем, если нет токена
        
    # 3. Создание и настройка Application
    app = ApplicationBuilder().token(TOKEN).build()
    
    # 4. Регистрация обработчиков
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("getlog", getlog))
    app.add_handler(CommandHandler("previewlog", previewlog))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # 5. Запуск бота
    logger.info("✅ Бот инициализирован и готов к запуску.")
    await app.run_polling()

def main():
    """Синхронная точка входа, которая запускает асинхронную логику."""
    logger.info("🚀 Запуск бота...")
    asyncio.run(main_async())

if __name__ == "__main__":
    main()
