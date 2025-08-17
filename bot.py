# bot.py — финальная интегрированная версия, использующая API
import logging
import os
import re
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
    CallbackQueryHandler,
)

# ---------- НАСТРОЙКИ ----------
TOKEN = os.environ.get("BOT_TOKEN") or "ВАШ_ТОКЕН_ТЕЛЕГРАМ"
OWNER_ID = 741409144  # Замените на ваш Telegram ID, если нужно
USER_LOG_FILE = "user_messages.txt"
BASE_URL = "https://dota1x6.com"
API_UPDATES_URL = "https://stats.dota1x6.com/api/v2/updates/?page=1&count=20"
API_HEROES_URL = "https://stats.dota1x6.com/api/v2/heroes/"
CDN_HEROES_URL = "https://cdn.dota1x6.com/shared/"

# ---------- ЛОГИ ----------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# cloudscraper для обхода Cloudflare
scraper = cloudscraper.create_scraper()

# ---------- Утилиты ----------
if not os.path.exists(USER_LOG_FILE):
    open(USER_LOG_FILE, "w", encoding="utf-8").close()

def log_user_message(user, text):
    try:
        with open(USER_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(
                f"{datetime.now()} | ID:{getattr(user, 'id', None)} | "
                f"Имя:{getattr(user, 'first_name', None)} | "
                f"Username:@{getattr(user, 'username', None)} | {text}\n"
            )
    except Exception:
        logger.exception("Не удалось записать лог пользователя")

def escape_markdown(text):
    """Экранирует специальные символы Markdown V2."""
    if not isinstance(text, str):
        return ""
    
    escape_chars = r"[_*[\]()~`>#+\-=|{}.!]"
    return re.sub(escape_chars, r'\\\g<0>', text)

# ---------- Conversation states ----------
WAITING_FOR_DOTA_ID = 1

# ---------- API ----------
def get_latest_update_info_from_api():
    """Получает информацию о последнем обновлении с API."""
    try:
        r = requests.get(API_UPDATES_URL, timeout=10)
        r.raise_for_status()
        data = r.json().get("data")
        if not data:
            return None
        updates_list = data.get("values")
        if not updates_list or not isinstance(updates_list, list) or len(updates_list) == 0:
            return None
        return updates_list[0]
    except Exception:
        logger.exception("Error fetching or parsing latest update from API")
        return None

def get_heroes_from_api():
    """Получает список всех героев с API."""
    try:
        r = requests.get(API_HEROES_URL, timeout=10)
        r.raise_for_status()
        data = r.json().get("data")
        if not data:
            return None
        return data.get("heroes", [])
    except Exception:
        logger.exception("Error fetching heroes from API")
        return None

# ---------- Handlers ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    log_user_message(user, "/start")
    keyboard = [
        ["Проверить статистику", "Обновления"],
        ["Герои"]
    ]
    markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Привет! Выберите действие:", reply_markup=markup)

async def handle_updates_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    log_user_message(user, "Обновления")
    await update.message.reply_text("🔎 Ищу последнее обновление...")

    latest_update_info = get_latest_update_info_from_api()

    if not latest_update_info:
        await update.message.reply_text("Не удалось получить информацию об обновлениях с API. Попробуйте позже.")
        return

    update_url_slug = latest_update_info.get("url")
    if not update_url_slug:
        await update.message.reply_text("В полученных данных нет ссылки на обновление. Попробуйте позже.")
        return

    update_url = urljoin(BASE_URL, f"/updates/{update_url_slug}")

    api_update_url = f"https://stats.dota1x6.com/api/v2/updates/{update_url_slug}"
    
    try:
        response = requests.get(api_update_url, timeout=10)
        response.raise_for_status()
        api_data = response.json()
        
        title = api_data.get("data", {}).get("ruName", "Без названия")
        text_content = ""
        heroes = api_data.get("data", {}).get("heroes", [])
        
        EMOJI_MAP = {
            "purple": "🟪", "blue": "🟦", "orange": "🟧", "scepter": "🔮",
            "innate": "🔥", "shard": "🔷", "up": "🟢", "down": "🔴",
            "change": "🟡", "hero_talent": "🤓",
        }
        SKILL_EMOJI_MAP = {
            "mist": "☁️", "aphotic": "🛡️", "curse": "💀", "borrowed": "🛡️",
            "acid": "🧪", "unstable": "💥", "greed": "💰", "chemical": "🧪",
            "manabreak": "⚡", "antimage_blink": "⚡", "counterspell": "🪄",
            "manavoid": "💥", "flux": "⚡", "field": "🛡️", "spark": "💥",
            "double": "👥", "call": "🛡️", "hunger": "🩸", "helix": "🌪️",
            "culling": "🔪", "enfeeble": "👻", "brain": "🧠", "nightmare": "💤",
            "grip": "✊", "bloodrage": "🩸", "bloodrite": "🩸", "thirst": "🩸",
            "rupture": "🩸", "goo": "💦", "spray": "💥", "back": "🛡️",
            "warpath": "🏃", "stomp": "🦶", "edge": "⚔️", "retaliate": "🛡️",
            "stampede": "🐎", "crystal": "🧊", "frostbite": "❄️", "arcane": "🪄",
            "freezing": "❄️", "frost": "❄️", "gust": "💨", "multishot": "🏹",
            "marksman": "🎯", "chain": "⛓️", "fist": "👊", "guard": "🛡️",
            "fireremnant": "🔥", "malefice": "🔮", "conversion": "🌑",
            "midnight": "🌑", "blackhole": "🌌", "acorn": "🌰", "bush": "🐿️",
            "scurry": "🏃", "sharp": "🎯", "inner_fire": "🔥", "burning_spears": "🔥",
            "berserkers_blood": "🩸", "life_break": "💔", "quas": "🧊", "wex": "💨",
            "exort": "🔥", "invoke": "🪄", "blade_fury": "🌪️", "healing_ward": "💚",
            "blade_dance": "🗡️", "omnislash": "🗡️", "odds": "🛡️", "press": "💚",
            "moment": "⚔️", "duel": "⚔️", "earth": "🌎", "edict": "💥", "storm": "⚡",
            "nova": "☄️", "lifestealer_rage": "🩸", "wounds": "🩸", "ghoul": "🧟",
            "infest": "🦠", "dragon": "🔥", "array": "⚡", "soul": "🔥", "laguna": "⚡",
            "dispose": "🤾", "rebound": "🤸", "sidekick": "🤜", "unleash": "👊",
            "spear": "🔱", "rebuke": "🛡️", "bulwark": "🛡️", "arena": "🏟️",
            "boundless": "🌳", "tree": "🌳", "mastery": "👊", "command": "👑",
            "wave": "🌊", "adaptive": "🔀", "attribute": "💪", "morph": "💧",
            "dead": "👻", "calling": "👻", "gun": "🔫", "veil": "👻", "sprout": "🌲",
            "teleport": " teleport", "nature_call": "🌳", "nature_wrath": "🌲",
            "fireblast": "🔥", "ignite": "🔥", "bloodlust": "🩸", "multicast": "💥",
            "buckle": "🛡️", "shield": "🛡️", "lucky": "🎲", "rolling": "🎳",
            "stifling_dagger": "🔪", "phantom_strike": "👻", "blur": "💨",
            "coup_de_grace": "🔪", "onslaught": "🐾", "trample": "🐾", "uproar": "🔊",
            "pulverize": "💥", "orb": "🔮", "rift": "🌌", "shift": "💨", "coil": "🌌",
            "hook": "⛓️", "rot": "🤢", "flesh": "💪", "dismember": "🔪", "dagger": "🔪",
            "blink": "⚡", "scream": "🗣️", "sonic": "💥", "plasma": "⚡", "link": "⛓️",
            "current": "🌊", "eye": "👁️", "burrow": " burrow", "sand": "⏳",
            "stinger": "🦂", "epicenter": "💥", "shadowraze": "💥", "frenzy": "👻",
            "dark_lord": "💀", "requiem": "💀", "arcane_bolt": "🔮", "concussive": "💥",
            "seal": "📜", "flare": " flare", "pact": "👻", "pounce": "🐾", "essence": "👻",
            "dance": "🕺", "scatter": "🔫", "cookie": "🍪", "shredder": "⚙️",
            "kisses": "💋", "shrapnel": "💣", "headshot": "🎯", "aim": "🎯",
            "assassinate": "🔪", "hammer": "🔨", "cleave": "🪓", "cry": "🗣️", "god": "⚔️",
            "refraction": "🪄", "meld": "🪞", "psiblades": "🗡️", "psionic": "💥",
            "reflection": "🪞", "illusion": "👻", "meta": "👹", "sunder": "💔",
            "laser": "💥", "march": "🤖", "matrix": "🛡️", "rearm": "🔄", "rage": "👹",
            "axes": "🪓", "fervor": "🔥", "trance": "🕺", "remnant": "🔮", "astral": "👻",
            "pulse": "💥", "step": "👟", "blast": "💥", "vampiric": "🩸",
            "strike": "⚔️", "reincarnation": "💀", "arc": "⚡", "bolt": "⚡", "jump": "⚡",
            "wrath": "⛈️"
        }

        RU_NAMES = {
            "purple": "Эпический талант", "blue": "Редкий талант", "orange": "Легендарный талант",
            "scepter": "Аганим", "innate": "Врожденный талант", "shard": "Аганим шард",
            "hero_talent": "Таланты героя",
        }
        
        for hero in heroes:
            hero_name = hero.get("userFriendlyName", "Неизвестный герой")
            text_content += f"\n*{escape_markdown('Изменения для ')}{escape_markdown(hero_name)}*:\n"
            
            upgrades = hero.get("upgrades", [])
            if upgrades:
                for upgrade in upgrades:
                    item_type = upgrade.get("type")
                    ru_rows = upgrade.get("ruRows")
                    change_type = upgrade.get("changeType", "").lower()
                    if ru_rows:
                        item_emoji = EMOJI_MAP.get(item_type.lower(), "")
                        change_emoji = EMOJI_MAP.get(change_type, "")
                        name = RU_NAMES.get(item_type.lower(), "")
                        text_content += f"\n{item_emoji} {escape_markdown(name)} {item_emoji}\n"
                        text_content += f"  {change_emoji} {escape_markdown(ru_rows.strip())}\n"
            
            talents = hero.get("talents", [])
            if talents:
                for talent in talents:
                    talent_name = talent.get("name", "")
                    if talent_name == "hero_talent":
                        name = RU_NAMES.get("hero_talent")
                        emoji = EMOJI_MAP.get("hero_talent")
                        text_content += f"\n{emoji} {escape_markdown(name)} {emoji}\n"
                    else:
                        skill_emoji = SKILL_EMOJI_MAP.get(talent_name.lower(), "")
                        if skill_emoji:
                             text_content += f"\n{skill_emoji} *{escape_markdown(talent_name.capitalize())}* {skill_emoji}\n"
                        else:
                             text_content += f"\n*{escape_markdown(talent_name.capitalize())}*:\n"
                    
                    for color in ["orangeRuRows", "purpleRuRows", "blueRuRows", "abilityRuRows"]:
                        ru_rows = talent.get(color)
                        change_type = talent.get("changeType", "").lower()
                        if ru_rows:
                            formatted_rows = ru_rows.replace("\r\n", "\n").strip()
                            if color == "orangeRuRows":
                                emoji = EMOJI_MAP.get("orange", "")
                                name = RU_NAMES.get("orange", "")
                                text_content += f" {emoji} {escape_markdown(name)} {emoji}\n"
                            elif color == "purpleRuRows":
                                emoji = EMOJI_MAP.get("purple", "")
                                name = RU_NAMES.get("purple", "")
                                text_content += f" {emoji} {escape_markdown(name)} {emoji}\n"
                            elif color == "blueRuRows":
                                emoji = EMOJI_MAP.get("blue", "")
                                name = RU_NAMES.get("blue", "")
                                text_content += f" {emoji} {escape_markdown(name)} {emoji}\n"
                            
                            for line in formatted_rows.split('\n'):
                                if line.strip():
                                    change_emoji = EMOJI_MAP.get(change_type, "")
                                    text_content += f"  {change_emoji} {escape_markdown(line.strip())}\n"
        
        text_to_send = f"*{escape_markdown(title)}*\n\n{text_content}"
        if len(text_to_send) > 4096:
            text_to_send = text_to_send[:4000] + "\n\n_(текст обрезан)_"
        await update.message.reply_text(text_to_send, parse_mode='MarkdownV2')

        kb = [[
            InlineKeyboardButton("Источник", url=update_url),
            InlineKeyboardButton("Все обновления", url=urljoin(BASE_URL, "/updates"))
        ]]
        await update.message.reply_text("Смотреть на сайте:", reply_markup=InlineKeyboardMarkup(kb))

    except Exception as e:
        logger.exception("Error fetching update from API")
        await update.message.reply_text("Произошла ошибка при получении данных. Попробуйте позже.")


async def handle_heroes_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Выводит кнопки для выбора категории героев (Strength, Agility, Intellect, All).
    """
    user = update.effective_user
    log_user_message(user, "Герои")
    
    response_text = "Выберите атрибут героя:"
    keyboard = [
        [InlineKeyboardButton("Strength", callback_data="attribute_Strength")],
        [InlineKeyboardButton("Agility", callback_data="attribute_Agility")],
        [InlineKeyboardButton("Intellect", callback_data="attribute_Intellect")],
        [InlineKeyboardButton("All", callback_data="attribute_All")],
    ]
    
    markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(response_text, reply_markup=markup)


async def handle_attribute_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает нажатие на кнопку атрибута и выводит список героев этого атрибута.
    """
    query = update.callback_query
    await query.answer()
    
    attribute = query.data.replace("attribute_", "")
    log_user_message(query.from_user, f"Выбран атрибут: {attribute}")
    
    await query.edit_message_text(f"🔎 Загружаю список героев для атрибута {attribute}...")

    heroes_data = get_heroes_from_api()

    if not heroes_data:
        await query.edit_message_text("Не удалось получить список героев. Попробуйте позже.")
        return

    filtered_heroes = []
    if attribute == "All":
        filtered_heroes = heroes_data
    else:
        filtered_heroes = [hero for hero in heroes_data if hero.get("attribute") == attribute]

    if not filtered_heroes:
        await query.edit_message_text(f"Герои с атрибутом {attribute} не найдены.")
        return
        
    keyboard = []
    for hero in sorted(filtered_heroes, key=lambda h: h.get('userFriendlyName')):
        hero_name = hero.get("userFriendlyName", "Неизвестный герой")
        url_name = hero.get("urlName")
        callback_data = f"hero_{url_name}"
        keyboard.append([InlineKeyboardButton(hero_name, callback_data=callback_data)])
    
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="back_to_attributes")])
    
    markup = InlineKeyboardMarkup(keyboard)
    
    response_text = f"Список героев с атрибутом *{escape_markdown(attribute)}*:"
    await query.edit_message_text(response_text, parse_mode='MarkdownV2', reply_markup=markup)


async def handle_back_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает нажатие на кнопку "Назад" для возврата к выбору атрибута.
    """
    query = update.callback_query
    await query.answer()
    
    response_text = "Выберите атрибут героя:"
    keyboard = [
        [InlineKeyboardButton("Strength", callback_data="attribute_Strength")],
        [InlineKeyboardButton("Agility", callback_data="attribute_Agility")],
        [InlineKeyboardButton("Intellect", callback_data="attribute_Intellect")],
        [InlineKeyboardButton("All", callback_data="attribute_All")],
    ]
    
    markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(response_text, reply_markup=markup)


async def handle_hero_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    url_name = query.data.replace("hero_", "")

    log_user_message(query.from_user, f"Выбран герой: {url_name}")

    cdn_hero_url = urljoin(CDN_HEROES_URL, f"ru_npc_dota_hero_{url_name}.json")

    try:
        r = requests.get(cdn_hero_url, timeout=10)
        r.raise_for_status()
        hero_data = r.json()

        if not hero_data:
            await query.edit_message_text("Информация о герое не найдена.")
            return

        text_content = f"*{escape_markdown(hero_data.get('userFriendlyName', 'Неизвестный герой'))}*\n\n"
        
        # Раздел "Отличия от Dota"
        changes = hero_data.get("changes")
        if changes:
            text_content += f"*{escape_markdown('Отличия от Dota')}*:\n"
            text_content += f"{escape_markdown(changes)}\n\n"

        # Раздел "Улучшения"
        upgrades = hero_data.get("upgrades")
        if upgrades:
            text_content += f"*{escape_markdown('Улучшения')}*:\n"
            upgrade_emojis = {"shard": "🔷", "scepter": "🔮", "innate": "🔥"}
            upgrade_ru_names = {"shard": "Аганим шард", "scepter": "Аганим", "innate": "Врожденный талант"}
            for upgrade in upgrades:
                upgrade_type = upgrade.get("upgradeType")
                upgrade_text = upgrade.get("upgradeText", "")
                emoji = upgrade_emojis.get(upgrade_type, "✨")
                ru_name = upgrade_ru_names.get(upgrade_type, "")
                if upgrade_text:
                    text_content += f"  {emoji} {escape_markdown(ru_name)}: {escape_markdown(upgrade_text)}\n"
            text_content += "\n"
        
        # Раздел "Таланты"
        talent_groups = [
            ("orangeTalents", "Легендарные таланты", "🟧"),
            ("purpleTalents", "Эпические таланты", "🟪"),
            ("blueTalents", "Редкие таланты", "🟦")
        ]
        
        for talent_key, talent_name, talent_emoji in talent_groups:
            talents = hero_data.get(talent_key)
            if talents:
                text_content += f"*{escape_markdown(talent_name)}*:\n"
                for talent in talents:
                    talent_text = talent.get("talentText", "")
                    if talent_text:
                        text_content += f"  {talent_emoji} {escape_markdown(talent_text)}\n"
                text_content += "\n"

        hero_web_url = f"https://dota1x6.com/heroes/{url_name}"
        
        if len(text_content) > 4096:
            text_content = text_content[:4000] + "\n\n_(текст обрезан)_"

        keyboard = [[InlineKeyboardButton("⬅️ Назад к атрибутам", callback_data="back_to_attributes")]]
        
        await query.edit_message_text(
            text_content,
            parse_mode='MarkdownV2',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    except Exception as e:
        logger.exception(f"Ошибка при получении данных о герое {url_name}")
        await query.edit_message_text("Произошла ошибка при получении данных о герое.")


async def check_stats_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    log_user_message(user, "Проверить статистику (start)")
    await update.message.reply_text("Введите числовой Dota ID:")
    return WAITING_FOR_DOTA_ID

async def check_stats_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text.strip()
    log_user_message(user, text)

    if not text.isdigit():
        await update.message.reply_text("Пожалуйста, введите только числовой Dota ID. Для отмены введите /cancel")
        return ConversationHandler.END

    dota_id = text
    url = f"https://stats.dota1x6.com/api/v2/players/?playerId={dota_id}"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            await update.message.reply_text("Не удалось получить данные. Возможно, сервис недоступен.")
            return ConversationHandler.END
        
        data = r.json().get("data")
        if not data:
            await update.message.reply_text("Игрок с таким ID не найден.")
            return ConversationHandler.END

        msg = (
            f"📊 Статистика для ID: {dota_id}\n\n"
            f"Всего игр: {data.get('matchCount', 'н/д')}\n"
            f"Среднее место: {round(data.get('avgPlace', 0), 2)}\n"
            f"🏆 Первых мест: {data.get('firstPlaces', 'н/д')}\n"
            f"Рейтинг: {data.get('rating', 'н/д')}"
        )
        await update.message.reply_text(msg)

        player_url = f"https://dota1x6.com/players/{dota_id}"
        inline = [[InlineKeyboardButton("Подробная история игр", web_app=WebAppInfo(url=player_url))]]
        await update.message.reply_text("Смотреть всю историю матчей:", reply_markup=InlineKeyboardMarkup(inline))

    except Exception:
        logger.exception("Ошибка при получении статистики")
        await update.message.reply_text("Произошла ошибка при получении данных.")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    log_user_message(user, "/cancel")
    await update.message.reply_text("Действие отменено.")
    return ConversationHandler.END

async def getlog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != OWNER_ID:
        return
    log_user_message(user, "/getlog")
    if not os.path.exists(USER_LOG_FILE):
        await update.message.reply_text("Файл логов пуст.")
        return
    await update.message.reply_document(document=open(USER_LOG_FILE, 'rb'), filename="user_messages.txt")

async def previewlog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != OWNER_ID:
        return
    log_user_message(user, "/previewlog")
    try:
        with open(USER_LOG_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
        last_lines = "".join(lines[-50:]) if lines else "(пусто)"
        if len(last_lines) > 4000:
            last_lines = "..." + last_lines[-4000:]
        await update.message.reply_text(f"Последние 50 строк лога:\n\n```\n{last_lines}\n```", parse_mode='MarkdownV2')
    except Exception:
        await update.message.reply_text("Не удалось прочитать лог.")

async def unknown_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Неизвестная команда. Пожалуйста, используйте кнопки.")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    log_user_message(user, "Получено фото")
    await update.message.reply_text("Я получил ваше фото. К сожалению, я не могу проанализировать его содержимое.")


def main():
    if TOKEN == "ВАШ_ТОКЕН_ТЕЛЕГРАМ":
        logger.critical("!!! TOKEN не установлен. Замените 'ВАШ_ТОКЕН_ТЕЛЕГРАМ' в коде или установите переменную окружения BOT_TOKEN.")
        return

    app = ApplicationBuilder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Проверить статистику$"), check_stats_start)],
        states={WAITING_FOR_DOTA_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, check_stats_id)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("getlog", getlog))
    app.add_handler(CommandHandler("previewlog", previewlog))
    app.add_handler(conv)
    app.add_handler(MessageHandler(filters.Regex("^Обновления$"), handle_updates_button))
    app.add_handler(MessageHandler(filters.Regex("^Герои$"), handle_heroes_button))
    app.add_handler(CallbackQueryHandler(handle_attribute_callback, pattern="^attribute_"))
    app.add_handler(CallbackQueryHandler(handle_back_button, pattern="^back_to_attributes$"))
    app.add_handler(CallbackQueryHandler(handle_hero_callback, pattern="^hero_"))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unknown_text))

    logger.info("Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()
