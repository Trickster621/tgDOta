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

# Логирование
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# Токен бота
TOKEN = os.environ.get("BOT_TOKEN") # Убедитесь, что переменная окружения установлена на Railway

# Telegram ID владельца
OWNER_ID = 741409144

# Путь к лог-файлу
USER_LOG_FILE = "user_messages.txt"
if not os.path.exists(USER_LOG_FILE):
    open(USER_LOG_FILE, "w", encoding="utf-8").close()

async def install_playwright_browsers():
    """Устанавливает браузеры для Playwright"""
    try:
        logging.info("Начало установки браузеров Playwright...")
        # Используем sys.executable для правильного вызова
        result = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium", "--with-deps"],
            capture_output=True, text=True, timeout=600 # 10 минут на установку
        )
        logging.info(f"Команда установки завершена. Код возврата: {result.returncode}")
        if result.stdout:
            logging.debug(f"STDOUT установки: {result.stdout}")
        if result.stderr:
            logging.debug(f"STDERR установки: {result.stderr}")
            
        if result.returncode == 0:
            logging.info("Playwright Chromium установлен успешно или уже был установлен.")
        else:
            logging.error(f"Ошибка установки Playwright: {result.stderr}")
            # Не прерываем запуск, возможно, браузер уже есть или установка не критична для других функций
    except subprocess.TimeoutExpired:
        logging.error("Таймаут при установке браузера Playwright (более 10 минут).")
    except Exception as e:
        logging.error(f"Неожиданная ошибка при установке браузеров Playwright: {e}", exc_info=True)

def log_user_message(user, text):
    """Сохраняем данные пользователя и сообщение в файл"""
    try:
        with open(USER_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(
                f"{datetime.now()} | ID: {user.id} | "
                f"Имя: {user.first_name} | Фамилия: {user.last_name} | "
                f"Username: @{user.username} | Сообщение: {text}\n"
            )
    except Exception as e:
        logging.error(f"Ошибка при записи в лог-файл: {e}")

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
        await send_last_update(update)
        return

    if not text.isdigit():
        await update.message.reply_text("Неизвестная команда. Используйте кнопки ниже.")
        return

    dota_id = text
    url = f"https://stats.dota1x6.com/api/v2/players/?playerId={dota_id}"
    try:
        response = requests.get(url, timeout=10)
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

        # Mini App кнопка
        player_url = f"https://dota1x6.com/players/{dota_id}"
        inline_keyboard = [
            [InlineKeyboardButton("Посмотреть историю игр", web_app=WebAppInfo(url=player_url))]
        ]
        await update.message.reply_text(
            "Вы можете посмотреть историю игр:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard)
        )

    except requests.exceptions.Timeout:
        logging.error(f"Таймаут при запросе к API для ID {text}")
        await update.message.reply_text("Превышено время ожидания ответа от API.")
    except Exception as e:
        logging.error(f"Ошибка при обработке ID {text}: {e}", exc_info=True)
        await update.message.reply_text("Произошла ошибка при получении данных.")

async def send_last_update(update: Update):
    """Получает и отправляет последнее обновление с сайта."""
    try:
        url = "https://dota1x6.com/updates"
        logging.info(f"Попытка получения обновлений с {url}")
        
        async with async_playwright() as p:
            logging.info("Запуск браузера Chromium...")
            browser = await p.chromium.launch(
                headless=True,
                # args=['--no-sandbox', '--disable-setuid-sandbox'] # Иногда помогает в контейнерах
            )
            logging.info("Браузер запущен. Создание новой страницы...")
            page = await browser.new_page()
            
            logging.info(f"Переход на страницу {url}...")
            await page.goto(url, wait_until='networkidle', timeout=30000) # Ждем, пока сеть успокоится
            logging.info("Страница загружена. Ожидание дополнительной загрузки JS...")
            await page.wait_for_timeout(5000)  # Дополнительное ожидание для JS
            
            html = await page.content()
            logging.info(f"HTML получен. Длина: {len(html)} символов")
            await browser.close()
            
        if "You need to enable JavaScript" in html:
            logging.warning("Страница обновлений всё ещё требует JavaScript. Возможно, контент не загрузился полностью.")
            # Можно попробовать увеличить wait_for_timeout или использовать wait_for_selector
        
        soup = BeautifulSoup(html, "html.parser")
        
        # --- Логика поиска последнего обновления ---
        # Попробуем найти основной контейнер. Структура сайта может быть разной.
        # Часто обновления находятся в <main>, <div class="content">, <div id="updates"> и т.д.
        
        # Метод 1: Ищем по тегам и классам, которые часто используются
        main_content = (soup.find("main") or 
                       soup.find("div", class_="main-content") or
                       soup.find("div", class_="content") or
                       soup.find("div", id="main") or
                       soup.find("div", id="content") or
                       soup.body)
        
        if not main_content:
            logging.error("Не найден основной контейнер содержимого на странице обновлений.")
            await update.message.reply_text("Не удалось найти основной контент на странице обновлений.")
            return
            
        # Метод 2: Ищем список обновлений. Это могут быть <ul>, <div class="updates-list">, <table> и т.д.
        updates_list_container = (main_content.find("ul", class_="updates-list") or
                                 main_content.find("div", class_="updates") or
                                 main_content.find("div", class_="posts") or
                                 main_content.find("table", class_="updates") or
                                 main_content) # Если не нашли, используем весь контент

        # Метод 3: Ищем сами элементы обновлений. Это могут быть <li>, <div class="update-item">, <tr> и т.д.
        update_items = []
        if updates_list_container:
            update_items = (updates_list_container.find_all("li") or
                           updates_list_container.find_all("div", class_=["update-item", "post", "news-item"]) or
                           updates_list_container.find_all("tr") or
                           updates_list_container.find_all("a", href=lambda x: x and '/updates/' in x)) # Ищем ссылки на обновления
        
        # Если всё ещё пусто, попробуем более общий подход
        if not update_items:
             # Ищем все ссылки, которые могут вести к обновлениям
             all_links = soup.find_all("a", href=lambda x: x and '/updates/' in x)
             if all_links:
                 update_items = [link.find_parent() or link for link in all_links] # Берем родителя ссылки или саму ссылку
             else:
                 # Крайний случай: ищем любые заголовки (h1-h6) и предполагаем, что они рядом с ссылками
                 headers = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
                 update_items = [header.find_parent() or header for header in headers[:10]] # Ограничиваем 10 первыми
        
        if not update_items:
            logging.warning("Не найдены элементы обновлений на странице.")
            # Отправим часть полученного HTML для отладки
            preview_html = html[:2000] if len(html) > 2000 else html
            logging.info(f"Превью полученного HTML (первые 2000 символов):\n{preview_html}")
            await update.message.reply_text(
                "Не удалось найти элементы обновлений на странице. "
                "Возможно, структура сайта изменилась. "
                "Администратору отправлена информация для отладки."
            )
            # Отправляем админу уведомление о проблеме
            if update.message.from_user.id == OWNER_ID:
                 await update.message.reply_text(f"Отладка: HTML (первые 2000 символов):\n```\n{preview_html}\n```", parse_mode='MarkdownV2') # Осторожно с Markdown
            return
            
        logging.info(f"Найдено {len(update_items)} элементов обновлений. Обрабатываем первый.")
        
        # Берем первый элемент (предполагаем, что он самый свежий)
        latest_update_element = update_items[0]
        
        # --- Извлечение заголовка и ссылки ---
        title = "Без заголовка"
        full_link = url # Ссылка по умолчанию
        
        # Ищем заголовок (h1-h6, strong, или просто текст внутри элемента)
        title_element = (latest_update_element.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']) or
                        latest_update_element.find('strong') or
                        latest_update_element.find('a')) # Если нет заголовка, берем первую ссылку
        
        if title_element:
            title = title_element.get_text(strip=True)
        else:
            # Если и ссылки нет, берем весь текст элемента
            title = latest_update_element.get_text(strip=True)[:100] + "..." if len(latest_update_element.get_text(strip=True)) > 100 else latest_update_element.get_text(strip=True)
            
        # Ищем ссылку
        link_element = latest_update_element.find("a")
        if link_element and link_element.get("href"):
            link_href = link_element.get("href")
            if link_href.startswith(("http://", "https://")):
                full_link = link_href
            elif link_href.startswith('/'):
                full_link = f"https://dota1x6.com{link_href}"
            else:
                full_link = f"https://dota1x6.com/{link_href}"
        
        logging.info(f"Найдено обновление: '{title}' -> {full_link}")
        
        # --- Получение деталей обновления ---
        if full_link and full_link != url:
            logging.info(f"Получение деталей обновления со страницы {full_link}")
            async with async_playwright() as p:
                browser_detail = await p.chromium.launch(headless=True)
                page_detail = await browser_detail.new_page()
                await page_detail.goto(full_link, wait_until='networkidle', timeout=30000)
                await page_detail.wait_for_timeout(5000) # Ждем загрузку JS
                detail_html = await page_detail.content()
                await browser_detail.close()
                
                detail_soup = BeautifulSoup(detail_html, "html.parser")
                
                # Ищем контент обновления
                content_div = (detail_soup.find("div", class_="post-content") or
                              detail_soup.find("div", class_="content") or
                              detail_soup.find("article") or
                              detail_soup.find("main") or
                              detail_soup.body)
                
                if not content_div:
                    logging.warning("Контейнер содержимого обновления не найден, используем body.")
                    content_div = detail_soup.body or detail_soup
                
                # Извлекаем текст
                content_text = content_div.get_text(separator='\n', strip=True) if content_div else "Нет содержимого."
                
                # Ограничиваем длину текста для Telegram
                max_length = 3500 # Оставляем запас для форматирования
                if len(content_text) > max_length:
                    content_text = content_text[:max_length] + "\n...\n(Текст обрезан)"
                
                # Отправляем текст обновления
                message_text = f"*{title}*\n\n{content_text}"
                # Проверяем длину итогового сообщения
                if len(message_text) > 4096:
                     message_text = message_text[:4090] + "..."

                try:
                    await update.message.reply_text(message_text, parse_mode='Markdown')
                except Exception as e:
                    logging.warning(f"Не удалось отправить с Markdown, пробуем HTML или обычный текст: {e}")
                    # Попробуем упростить форматирование
                    message_text_simple = f"*{title}*\n\n{content_text}"
                    if len(message_text_simple) <= 4096:
                        try:
                            await update.message.reply_text(message_text_simple, parse_mode=None) # Без форматирования
                        except Exception as e2:
                             logging.error(f"Ошибка отправки текста обновления: {e2}")
                             await update.message.reply_text("Ошибка при отправке текста обновления.")
                    else:
                         await update.message.reply_text("Текст обновления слишком длинный для отправки.")
                
                # --- Поиск и отправка изображений ---
                images = content_div.find_all("img") if content_div else []
                sent_images = 0
                max_images = 3 # Ограничим количество изображений
                for img in images:
                    if sent_images >= max_images:
                        await update.message.reply_text(f"(Есть ещё изображения, но отправка ограничена {max_images} шт.)")
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
                    
                    try:
                        logging.info(f"Попытка загрузки изображения: {img_url}")
                        img_resp = requests.get(img_url, timeout=15) # Увеличен таймаут для изображений
                        if img_resp.status_code == 200 and img_resp.content:
                            await update.message.reply_photo(photo=BytesIO(img_resp.content))
                            sent_images += 1
                            logging.info(f"Изображение отправлено: {img_url}")
                        else:
                            logging.warning(f"Не удалось загрузить изображение {img_url}, статус: {img_resp.status_code}")
                    except requests.exceptions.RequestException as e:
                        logging.error(f"Ошибка сети при загрузке изображения {img_url}: {e}")
                    except Exception as e:
                        logging.error(f"Ошибка при загрузке/отправке изображения {img_url}: {e}", exc_info=True)
                
                if sent_images == 0 and images:
                     await update.message.reply_text("Изображения найдены на странице, но не удалось их загрузить.")
        else:
            # Если детальная страница не найдена, отправляем только заголовок
            await update.message.reply_text(f"Последнее обновление: *{title}*", parse_mode='Markdown')
            
        # Кнопка "Все обновления"
        inline_keyboard = [[InlineKeyboardButton("Все обновления", url="https://dota1x6.com/updates")]]
        await update.message.reply_text("Полный список обновлений:", reply_markup=InlineKeyboardMarkup(inline_keyboard))
    
    except asyncio.TimeoutError:
        logging.error("Таймаут при работе с Playwright.")
        await update.message.reply_text("Превышено время ожидания загрузки страницы обновлений.")
    except Exception as e:
        logging.error(f"Ошибка при получении обновлений: {e}", exc_info=True)
        error_msg = f"Произошла ошибка при получении обновлений: {str(e)[:200]}"
        await update.message.reply_text(error_msg)

# /getlog — присылает весь лог
async def getlog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    log_user_message(user, "/getlog")

    if user.id != OWNER_ID:
        await update.message.reply_text("Нет доступа")
        return

    if not os.path.exists(USER_LOG_FILE):
        await update.message.reply_text("Файл логов пока пуст.")
        return

    try:
        with open(USER_LOG_FILE, "r", encoding="utf-8") as f:
            content = f.read()
        if not content.strip():
             await update.message.reply_text("Файл логов пуст.")
             return
        bio = BytesIO()
        bio.write(content.encode("utf-8"))
        bio.seek(0)
        await update.message.reply_document(document=bio, filename="user_messages.txt")
    except Exception as e:
        logging.error(f"Ошибка при отправке лога: {e}")
        await update.message.reply_text("Произошла ошибка при отправке файла логов.")

# /previewlog — последние 50 сообщений
async def previewlog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    log_user_message(user, "/previewlog")

    if user.id != OWNER_ID:
        await update.message.reply_text("Нет доступа")
        return

    try:
        with open(USER_LOG_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
        if not lines:
            await update.message.reply_text("(лог пуст)")
            return
        last_lines = "".join(lines[-50:]) if lines else "(пусто)"
        if len(last_lines) > 3500:
            last_lines = last_lines[-3500:]
        await update.message.reply_text(f"Последние строки лога:\n\n```\n{last_lines}\n```", parse_mode='MarkdownV2')
    except Exception as e:
        logging.error(f"Ошибка при предпросмотре лога: {e}")
        await update.message.reply_text("Произошла ошибка при получении предпросмотра лога.")

async def main_async():
    """Асинхронная точка входа"""
    await install_playwright_browsers()  # Устанавливаем браузеры при запуске
    
    if not TOKEN or TOKEN == "ВАШ_НОВЫЙ_ТОКЕН":
        logging.error("Токен бота не установлен! Установите переменную окружения BOT_TOKEN на Railway.")
        return
        
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("getlog", getlog))
    app.add_handler(CommandHandler("previewlog", previewlog))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logging.info("Бот готов к запуску...")
    await app.run_polling()

def main():
    """Синхронная точка входа"""
    asyncio.run(main_async())

if __name__ == "__main__":
    main()
