# bot.py — финальная интегрированная версия (ReplyKeyboard + ConversationHandler + updates via API)
import logging
import os
from io import BytesIO
from urllib.parse import urljoin
from datetime import datetime

import requests
import cloudscraper
from bs4 import BeautifulSoup
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    WebAppInfo,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# ---------- НАСТРОЙКИ ----------
TOKEN = os.environ.get("BOT_TOKEN") or "ВАШ_ТОКЕН_ТЕЛЕГРАМ"
OWNER_ID = 741409144
USER_LOG_FILE = "user_messages.txt"

# старая «неудачная» точка — пробуем её первым (как у вас было)
UPDATE_PAGE = "https://dota1x6.com/updates/?page=1&count=20"
BASE_URL = "https://dota1x6.com"

# ---------- ЛОГИ ----------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# ---------- cloudscraper (для обхода Cloudflare при парсинге HTML) ----------
scraper = cloudscraper.create_scraper()

# ---------- Утилиты ----------
if not os.path.exists(USER_LOG_FILE):
    open(USER_LOG_FILE, "w", encoding="utf-8").close()

def log_user_message(user, text):
    try:
        with open(USER_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(
                f"{datetime.now()} | ID:{getattr(user,'id',None)} | "
                f"Имя:{getattr(user,'first_name',None)} | "
                f"Username:@{getattr(user,'username',None)} | {text}\n"
            )
    except Exception:
        logger.exception("Не удалось записать лог пользователя")

# ---------- Conversation states ----------
WAITING_FOR_DOTA_ID = 1

# ---------- API / парсинг апдейтов ----------
def fetch_updates_list_first_item():
    """
    Возвращает первый элемент списка обновлений (dict) или None.
    Алгоритм:
      1) Пытаемся взять JSON (как в оригинале).
      2) Если не получилось — парсим HTML (/updates) через cloudscraper:
         - ищем tbody>tr
         - если нет — ищем карточки типа div.card, div.news-card и т.д.
    Возвращаем словарь с хотя бы полями {'title': ..., 'url': ...} или None.
    """
    # --- попытка JSON (оригинальная) ---
    try:
        r = requests.get(UPDATE_PAGE, timeout=10)
        if r.status_code == 200:
            try:
                j = r.json()
                items = None
                if isinstance(j, dict):
                    for key in ("data", "items", "result", "updates"):
                        if key in j and isinstance(j[key], (list, tuple)):
                            items = j[key]
                            break
                elif isinstance(j, list):
                    items = j
                if items:
                    if len(items) == 0:
                        return None
                    return items[0]
            except ValueError:
                # not json — перейдём к HTML
                pass
        else:
            logger.info("UPDATE_PAGE returned %s, will try HTML parse", r.status_code)
    except Exception as e:
        logger.info("Cannot fetch update page as JSON: %s", e)

    # --- fallback: парсим HTML через cloudscraper ---
    try:
        r = scraper.get(urljoin(BASE_URL, "/updates"), timeout=10)
        if r.status_code != 200:
            logger.warning("Updates page returned %s", r.status_code)
            return None
        soup = BeautifulSoup(r.text, "html.parser")

        # 1) tbody > tr (если используется таблица)
        tbody = soup.find("tbody")
        if tbody:
            first_row = tbody.find("tr")
            if first_row:
                a = first_row.find("a", href=True)
                if a:
                    title = a.get_text(strip=True) or ""
                    link = urljoin(BASE_URL, a["href"])
                    return {"title": title, "url": link}

        # 2) карточки — ищем наиболее вероятные селекторы
        card_selectors = [
            ("div", {"class": lambda v: v and "card" in v}),
            ("div", {"class": lambda v: v and "news-card" in v}),
            ("article", {}),
            ("div", {"role": "article"}),
            ("li", {"class": lambda v: v and "update" in v}),
        ]
        for tag, attrs in card_selectors:
            el = soup.find(tag, attrs=attrs)
            if el:
                a = el.find("a", href=True)
                if a:
                    title = a.get_text(strip=True) or ""
                    link = urljoin(BASE_URL, a["href"])
                    return {"title": title, "url": link}
