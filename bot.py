import logging
import os
import re
import asyncio
import aiohttp
import aiofiles
from urllib.parse import urljoin
from datetime import datetime
from collections import deque

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    WebAppInfo,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
    CallbackQueryHandler,
    ConversationHandler,
)
from telegram.error import Conflict

# ---------- НАСТРОЙКИ ----------
TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID"))
USER_LOG_FILE = "user_messages.txt"
BASE_URL = "https://dota1x6.com"
API_UPDATES_URL = "https://stats.dota1x6.com/api/v2/updates/?page=1&count=20"
API_HEROES_URL = "https://stats.dota1x6.com/api/v2/heroes/"
API_LEADERBOARD_URL = "https://stats.dota1x6.com/api/v2/leaderboard/"
CDN_HEROES_INFO_URL = "https://cdn.dota1x6.com/shared/"
API_PLAYERS_URL = "https://stats.dota1x6.com/api/v2/players/"
API_STEAM_PROFILE_URL = "https://stats.dota1x6.com/api/v2/players/steam-profile"
LEADERBOARD_PAGE_SIZE = 50

# ---------- СОСТОЯНИЯ ДЛЯ CONVERSATIONHANDLER ----------
GET_DOTA_ID = 1

# ---------- ЛОГИ ----------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# ---------- УТИЛИТЫ ----------
if not os.path.exists(USER_LOG_FILE):
    open(USER_LOG_FILE, "w", encoding="utf-8").close()

RECENT_MESSAGES = deque(maxlen=3000)

async def log_user_message(user, text):
    try:
        log_line = (
            f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | ID:{getattr(user, 'id', None)} | "
            f"Имя:{getattr(user, 'first_name', None)} | "
            f"Username:@{getattr(user, 'username', None)} | {text}\n"
        )
        async with aiofiles.open(USER_LOG_FILE, "a", encoding="utf-8") as f:
            await f.write(log_line)
        RECENT_MESSAGES.append(log_line)
    except Exception:
        logger.exception("Не удалось записать лог пользователя")

SKILL_EMOJI_MAP = {
    "Spear of Mars": "🔱", "God's Rebuke": "⚔️", "Bulwark": "🛡️", "Arena of Blood": "🏟️",
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
    "wrath": "⛈️",
    "movespeed": "🥾"
}
EMOJI_MAP = {
    "purple": "🟪", "blue": "🟦", "orange": "🟧", "scepter": "🔮",
    "innate": "🔥", "shard": "🔷", "up": "🟢", "down": "🔴",
    "change": "🟡", "hero_talent": "🤓",
    "Aghanim Scepter": "🔮 Aghanim Scepter",
    "Aghanim Shard": "🔷 Aghanim Shard",
    "online": "🟩",
    "offline": "🟥"
}
COMBINED_EMOJI_MAP = {**SKILL_EMOJI_MAP, **EMOJI_MAP}

def escape_markdown_v2(text):
    if not isinstance(text, str):
        return str(text)
    
    escape_chars = r"[_*[\]()~`>#+\-=|{}.!]"
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)

def format_text_with_emojis(text):
    if not isinstance(text, str):
        return ""

    formatted_text = text

    # Замена маркеров up, down, change
    formatted_text = re.sub(r'\b(увеличен[оаы]?)\b', f'{EMOJI_MAP.get("up", "")} \\1', formatted_text, flags=re.IGNORECASE)
    formatted_text = re.sub(r'\b(снижен[оаы]?)\b', f'{EMOJI_MAP.get("down", "")} \\1', formatted_text, flags=re.IGNORECASE)
    formatted_text = re.sub(r'\b(изменен[оы]?)\b', f'{EMOJI_MAP.get("change", "")} \\1', formatted_text, flags=re.IGNORECASE)
    formatted_text = re.sub(r'\b(изменено)\b', f'{EMOJI_MAP.get("change", "")} \\1', formatted_text, flags=re.IGNORECASE)
    formatted_text = re.sub(r'\b(больше не)\b', f'{EMOJI_MAP.get("down", "")} \\1', formatted_text, flags=re.IGNORECASE)

    # Замена названий способностей и предметов на эмодзи
    sorted_keys = sorted(COMBINED_EMOJI_MAP.keys(), key=len, reverse=True)
    for key in sorted_keys:
        emoji = COMBINED_EMOJI_MAP[key]
        if key.lower() in ['scepter', 'shard', 'hero_talent', 'innate', 'up', 'down', 'change']:
            continue
            
        pattern = r'\b' + re.escape(key) + r'\b'
        formatted_text = re.sub(pattern, f"{emoji} {key}", formatted_text, flags=re.IGNORECASE)
    
    formatted_text = re.sub(
        r'\bAghanim Scepter\b',
        EMOJI_MAP.get("Aghanim Scepter", "🔮 Aghanim Scepter"),
        formatted_text,
        flags=re.IGNORECASE
    )
    formatted_text = re.sub(
        r'\bAghanim Shard\b',
        EMOJI_MAP.get("Aghanim Shard", "🔷 Aghanim Shard"),
        formatted_text,
        flags=re.IGNORECASE
    )
    
    return formatted_text

async def send_long_message(context: ContextTypes.DEFAULT_TYPE, chat_id, text, parse_mode='MarkdownV2'):
    max_length = 4096
    
    parts = text.split('\n')
    current_message = ""
    
    for part in parts:
        if len(current_message) + len(part) + 1 < max_length:
            current_message += part + "\n"
        else:
            if current_message:
                await context.bot.send_message(chat_id=chat_id, text=current_message, parse_mode=parse_mode)
                await asyncio.sleep(0.5)
            current_message = part + "\n"
            
    if current_message:
        await context.bot.send_message(chat_id=chat_id, text=current_message, parse_mode=parse_mode)

# ---------- API ----------
async def fetch_json(url):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=15) as response:
                response.raise_for_status()
                return await response.json()
    except aiohttp.ClientError as e:
        logger.error(f"HTTP error fetching {url}: {e}")
        return None
    except asyncio.TimeoutError:
        logger.error(f"Timeout fetching {url}")
        return None
    except Exception as e:
        logger.error(f"An error occurred while fetching {url}: {e}")
        return None

# ---------- Handlers ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await log_user_message(user, "/start")
    keyboard = [
        ["Проверить статистику", "Обновления"],
        ["Герои", "Ладдер"]
    ]
    markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Привет! Выберите действие:", reply_markup=markup)

async def start_dota_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await log_user_message(update.effective_user, "Нажал 'Проверить статистику'")
    await update.message.reply_text("Введите числовой Dota ID:")
    return GET_DOTA_ID

async def get_dota_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    dota_id = update.message.text
    await log_user_message(update.effective_user, f"Ввел ID: {dota_id}")

    player_data_url = f"{API_PLAYERS_URL}?playerId={dota_id}"
    steam_profile_url = f"{API_STEAM_PROFILE_URL}?playerId={dota_id}"
    
    player_data, steam_profile_data = await asyncio.gather(
        fetch_json(player_data_url),
        fetch_json(steam_profile_url)
    )

    if not player_data or not player_data.get("data"):
        await update.message.reply_text("Игрок с таким ID не найден или произошла ошибка API.")
        return ConversationHandler.END

    player_info = player_data.get("data")
    match_count = player_info.get("matchCount", "неизвестно")
    avg_place = round(player_info.get("avgPlace", 0), 2)
    first_places = player_info.get("firstPlaces", "неизвестно")
    rating = player_info.get("rating", "неизвестно")
    favorite_hero_url = player_info.get("favoriteHero")

    social_data = player_info.get("social", {})
    if social_data is None:
        social_data = {}
    
    youtube_url = social_data.get("youtube")
    twitch_url = social_data.get("twitch")
    is_youtube_live = social_data.get("isYoutubeLive")
    is_twitch_live = social_data.get("isTwitchLive")

    player_name = None
    if steam_profile_data and steam_profile_data.get("data"):
        player_name = steam_profile_data.get("data").get("personaname")

    if player_name:
        header = f"*Статистика игрока {escape_markdown_v2(player_name)}*"
    else:
        header = "*Статистика игрока*"

    msg = f"{header}\n"
    msg += f"Всего игр: {escape_markdown_v2(str(match_count))}\n"
    msg += f"Среднее место: {escape_markdown_v2(str(avg_place))}\n"
    msg += f"Первых мест: {escape_markdown_v2(str(first_places))}\n"
    msg += f"Рейтинг: {escape_markdown_v2(str(rating))}\n"
    
    if favorite_hero_url:
        hero_name = favorite_hero_url.replace("npc_dota_hero_", "").capitalize()
        msg += f"Любимый герой: {escape_markdown_v2(hero_name)}\n"
        
    if youtube_url:
        yt_status = EMOJI_MAP.get("online") if is_youtube_live else EMOJI_MAP.get("offline")
        msg += f"\n{yt_status} [{escape_markdown_v2('Ютуб')}]({escape_markdown_v2(youtube_url)})"
    if twitch_url:
        twitch_status = EMOJI_MAP.get("online") if is_twitch_live else EMOJI_MAP.get("offline")
        msg += f"\n{twitch_status} [{escape_markdown_v2('Твич')}]({escape_markdown_v2(twitch_url)})"
        
    await update.message.reply_text(msg, parse_mode='MarkdownV2')

    player_url = f"{BASE_URL}/players/{dota_id}"
    inline_keyboard = [
        [InlineKeyboardButton("Посмотреть историю игр", web_app=WebAppInfo(url=player_url))]
    ]
    await update.message.reply_text(
        "Вы можете посмотреть историю игр:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard)
    )

    return ConversationHandler.END

async def cancel_dota_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Действие отменено.")
    return ConversationHandler.END

async def handle_updates_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await log_user_message(user, "Обновления")
    await update.message.reply_text("🔎 Ищу последнее обновление...")

    latest_update_info = await fetch_json(API_UPDATES_URL)
    if not latest_update_info or not latest_update_info.get("data", {}).get("values"):
        await update.message.reply_text("Не удалось получить информацию об обновлениях с API. Попробуйте позже.")
        return ConversationHandler.END

    update_url_slug = latest_update_info["data"]["values"][0].get("url")
    if not update_url_slug:
        await update.message.reply_text("В полученных данных нет ссылки на обновление. Попробуйте позже.")
        return ConversationHandler.END

    update_url = urljoin(BASE_URL, f"/updates/{update_url_slug}")
    api_update_url = f"https://stats.dota1x6.com/api/v2/updates/{update_url_slug}"
    
    api_data = await fetch_json(api_update_url)
    if not api_data or not api_data.get("data"):
        await update.message.reply_text("Произошла ошибка при получении данных об обновлении. Попробуйте позже.")
        return ConversationHandler.END

    data = api_data.get("data")
    title = data.get("ruName", "Без названия")
    output_text = f"*{escape_markdown_v2(title)}*\n\n"
    
    if data.get("ruRows"):
        output_text += f"{escape_markdown_v2(format_text_with_emojis(data['ruRows']))}\n\n"

    heroes = data.get("heroes", [])
    if heroes:
        for hero in heroes:
            hero_name = hero.get('userFriendlyName') or hero.get('userFrendlyName') or 'Неизвестный герой'
            output_text += f"*{escape_markdown_v2(f'Изменения для {hero_name}')}*\n\n"
            
            if hero.get("ruRows"):
                output_text += f"{escape_markdown_v2(format_text_with_emojis(hero['ruRows']))}\n\n"

            upgrades = hero.get("upgrades", [])
            if upgrades:
                for upgrade in upgrades:
                    if upgrade.get("ruRows"):
                        upgrade_type = upgrade.get("type", "").lower()
                        if upgrade_type == "scepter":
                            output_text += f"🔮 Аганим 🔮\n"
                        elif upgrade_type == "shard":
                            output_text += f"🔷 Аганим шард 🔷\n"
                        else:
                            continue
                        output_text += f" {escape_markdown_v2(format_text_with_emojis(upgrade['ruRows']))}\n\n"

            talents = hero.get("talents", [])
            if talents:
                output_text += "*Таланты героя*\n"
                for talent in talents:
                    talent_name = talent.get('name', '')
                    
                    if talent_name:
                        skill_emoji = SKILL_EMOJI_MAP.get(talent_name.lower().replace(" ", "_"), "✨")
                        output_text += f"\n{skill_emoji} *{escape_markdown_v2(talent_name.capitalize())}*\n"
                    
                    if talent.get("abilityRuRows"):
                        rows_text = format_text_with_emojis(talent['abilityRuRows'])
                        lines = [line.strip() for line in rows_text.split('\n') if line.strip()]
                        for line in lines:
                            output_text += f" {escape_markdown_v2('-')} {escape_markdown_v2(line)}\n"
                        output_text += "\n"
                    
                    if talent.get("orangeRuRows"):
                        output_text += f"🟧 {escape_markdown_v2('Легендарный талант')} 🟧\n"
                        rows_text = format_text_with_emojis(talent['orangeRuRows'])
                        lines = [line.strip() for line in rows_text.split('\n') if line.strip()]
                        for line in lines:
                            output_text += f" {escape_markdown_v2('-')} {escape_markdown_v2(line)}\n"
                        output_text += "\n"
                    
                    if talent.get("purpleRuRows"):
                        output_text += f"🟪 {escape_markdown_v2('Эпический талант')} 🟪\n"
                        rows_text = format_text_with_emojis(talent['purpleRuRows'])
                        lines = [line.strip() for line in rows_text.split('\n') if line.strip()]
                        for line in lines:
                            output_text += f" {escape_markdown_v2('-')} {escape_markdown_v2(line)}\n"
                        output_text += "\n"
                    
                    if talent.get("blueRuRows"):
                        output_text += f"🟦 {escape_markdown_v2('Редкий талант')} 🟦\n"
                        rows_text = format_text_with_emojis(talent['blueRuRows'])
                        lines = [line.strip() for line in rows_text.split('\n') if line.strip()]
                        for line in lines:
                            output_text += f" {escape_markdown_v2('-')} {escape_markdown_v2(line)}\n"
                        output_text += "\n"
                        
    items = data.get("items", [])
    if items:
        output_text += f"\n*{escape_markdown_v2('Корректировки Предметов')}*\n\n"
        for item in items:
            ru_rows = item.get("ruRows")
            if ru_rows:
                formatted_item_text = format_text_with_emojis(ru_rows)
                output_text += f"• {escape_markdown_v2(item.get('name', ''))}\n"
                output_text += f"  {escape_markdown_v2(formatted_item_text)}\n\n"
                

    final_text = output_text.strip()
    
    if not final_text or final_text.strip() == f"*{escape_markdown_v2(title)}*":
        await update.message.reply_text("Не удалось получить данные об изменениях. Возможно, раздел пуст.")
        return
        
    await send_long_message(context, update.effective_chat.id, final_text)

    kb = [[
        InlineKeyboardButton("Источник", web_app=WebAppInfo(url=update_url)),
        InlineKeyboardButton("Все обновления", web_app=WebAppInfo(url=urljoin(BASE_URL, "/updates")))
    ]]
    await update.message.reply_text("Смотреть на сайте:", reply_markup=InlineKeyboardMarkup(kb))
    return ConversationHandler.END


async def handle_leaderboard_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await log_user_message(user, "Ладдер")

    sent_message = await update.message.reply_text("🏆 Загружаю ладдер...")
    
    leaderboard_data = await fetch_json(API_LEADERBOARD_URL)
    
    if not leaderboard_data or not leaderboard_data.get("data"):
        await sent_message.edit_text("Не удалось получить данные ладдера. Попробуйте позже.")
        return
        
    players = leaderboard_data.get("data")
    players_to_display = players[:50]
    
    message_text = f"*{escape_markdown_v2('ТОП-50 ИГРОКОВ LADDER.')}*\n\n"
    
    for player in players_to_display:
        place = player.get("place")
        nickname = player.get("nickname")
        rating = player.get("rating")
        match_count = player.get("matchCount")
        favorite_hero = player.get("favoriteHero")
        
        social_data = player.get("social", {})
        if social_data is None:
            social_data = {}
        
        youtube_url = social_data.get("youtube")
        twitch_url = social_data.get("twitch")
        is_youtube_live = social_data.get("isYoutubeLive")
        is_twitch_live = social_data.get("isTwitchLive")

        player_info = (
            f"*{escape_markdown_v2(str(place))}\\. {escape_markdown_v2(nickname)}*\n"
            f"Рейтинг: {escape_markdown_v2(str(rating))}\n"
            f"Игр: {escape_markdown_v2(str(match_count))}\n"
        )
        
        if favorite_hero:
            hero_name = favorite_hero.replace("npc_dota_hero_", "").capitalize()
            player_info += f"Лучший герой: {escape_markdown_v2(hero_name)}\n"
        
        social_links = []
        if youtube_url:
            yt_status = EMOJI_MAP.get("online") if is_youtube_live else EMOJI_MAP.get("offline")
            social_links.append(f" {yt_status} [{escape_markdown_v2('Ютуб')}]({escape_markdown_v2(youtube_url)})")
        if twitch_url:
            twitch_status = EMOJI_MAP.get("online") if is_twitch_live else EMOJI_MAP.get("offline")
            social_links.append(f" {twitch_status} [{escape_markdown_v2('Твич')}]({escape_markdown_v2(twitch_url)})")
        
        if social_links:
            player_info += "\\|".join(social_links)
            player_info += "\n"
        
        message_text += player_info + "\n"
        
    keyboard = [
        [InlineKeyboardButton("Весь ладдер на сайте", web_app=WebAppInfo(url=f"{BASE_URL}/leaderboard"))]
    ]
    
    markup = InlineKeyboardMarkup(keyboard)
    
    await sent_message.edit_text(message_text, reply_markup=markup, parse_mode='MarkdownV2', disable_web_page_preview=True)

async def handle_heroes_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await log_user_message(user, "Герои")

    keyboard = [
        [InlineKeyboardButton("Strength", callback_data="attribute_Strength")],
        [InlineKeyboardButton("Agility", callback_data="attribute_Agility")],
        [InlineKeyboardButton("Intellect", callback_data="attribute_Intellect")],
        [InlineKeyboardButton("Universal", callback_data="attribute_All")],
        [InlineKeyboardButton("Посмотреть на сайте", web_app=WebAppInfo(url=f"{BASE_URL}/heroes"))]
    ]
    
    markup = InlineKeyboardMarkup(keyboard)
    
    if update.message:
        await update.message.reply_text("Выберите атрибут героя:", reply_markup=markup)
    elif update.callback_query and update.callback_query.message:
        await update.callback_query.message.edit_text("Выберите атрибут героя:", reply_markup=markup)
    return ConversationHandler.END

async def handle_attribute_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    attribute = query.data.split("_")[1]
    context.user_data['selected_attribute'] = attribute
    
    heroes_data = await fetch_json(API_HEROES_URL)
    
    if not heroes_data:
        await query.message.reply_text("Не удалось получить список героев.")
        return
        
    heroes = heroes_data.get("data", {}).get("heroes", [])
    
    filtered_heroes = [h for h in heroes if h.get("attribute") == attribute]
    
    if not filtered_heroes:
        await query.edit_message_text(
            text="К сожалению, героев этого атрибута не найдено. Попробуйте выбрать другой.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Назад", callback_data="back_to_attributes")]
            ])
        )
        return

    keyboard = []
    row = []
    for hero in sorted(filtered_heroes, key=lambda x: x.get("userFriendlyName") or x.get("userFrendlyName", "")):
        name = hero.get("userFriendlyName") or hero.get("userFrendlyName")
        hero_name_api = hero.get("name")
        
        if name and hero_name_api:
            row.append(InlineKeyboardButton(name, callback_data=f"hero_{hero_name_api}"))
            if len(row) == 2:
                keyboard.append(row)
                row = []
    if row:
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton("Назад", callback_data="back_to_attributes")])
    markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text="Выберите героя:",
        reply_markup=markup
    )
    
async def send_hero_details(update: Update, context: ContextTypes.DEFAULT_TYPE, hero_json, hero_name):
    text_parts = []
    
    text_parts.append(f"*{escape_markdown_v2(hero_name)}*\n")
    
    changes = hero_json.get('changes', [])
    upgrades = hero_json.get('upgrades', [])

    if changes:
        text_parts.append(f"*{escape_markdown_v2('Отличия от Dota:')}*")
        for change in changes:
            name = change.get('name')
            description = change.get('description', '')
            
            if name == 'innate':
                text_parts.append("")
                formatted_desc = format_text_with_emojis(description)
                text_parts.append(f"• {EMOJI_MAP.get('innate', '')} *{escape_markdown_v2('Врожденная способность:')}*\n_{escape_markdown_v2(formatted_desc)}_")
            else:
                text_parts.append("")
                skill_name_lower = name.lower() if name else None
                
                if skill_name_lower in SKILL_EMOJI_MAP:
                    skill_emoji = SKILL_EMOJI_MAP[skill_name_lower]
                elif skill_name_lower in EMOJI_MAP:
                    skill_emoji = EMOJI_MAP[skill_name_lower]
                else:
                    skill_emoji = ""
                
                if name:
                    formatted_name = f"*{escape_markdown_v2(name.capitalize())}*"
                    if skill_emoji:
                        formatted_name = f"{skill_emoji} {formatted_name}"
                    
                    formatted_desc = format_text_with_emojis(description)
                    text_parts.append(f"• {formatted_name}: _{escape_markdown_v2(formatted_desc)}_")
                else:
                    formatted_desc = format_text_with_emojis(description)
                    text_parts.append(f"• _{escape_markdown_v2(formatted_desc)}_")
        text_parts.append("")
    
    if upgrades:
        text_parts.append("*Улучшения:*")
        
        grouped_upgrades = {}
        for upgrade in upgrades:
            upgrade_type = upgrade.get('upgradeType', 'unknown')
            if upgrade_type not in grouped_upgrades:
                grouped_upgrades[upgrade_type] = []
            grouped_upgrades[upgrade_type].append(upgrade)
            
        upgrade_order = ['scepter', 'shard']
        
        for upgrade_type in upgrade_order:
            if upgrade_type in grouped_upgrades:
                upgrades_to_print = grouped_upgrades[upgrade_type]
                
                upgrade_title = "Неизвестное улучшение"
                if upgrade_type == 'scepter':
                    upgrade_title = "Аганим"
                elif upgrade_type == 'shard':
                    upgrade_title = "Аганим Шард"
                
                text_parts.append("")
                emoji = EMOJI_MAP.get(upgrade_type, "✨")
                text_parts.append(f"• {emoji} *{escape_markdown_v2(upgrade_title)}:*")
                
                for upgrade in upgrades_to_print:
                    description = format_text_with_emojis(upgrade.get('description', ''))
                    extra_values_text = ""
                    for extra_value_pair in upgrade.get('extraValues', []):
                        key = extra_value_pair[0]
                        value = extra_value_pair[1]
                        extra_values_text += f"_{format_text_with_emojis(key)}: {format_text_with_emojis(value)}_\n"

                    text_parts.append(f"{escape_markdown_v2(extra_values_text)}{escape_markdown_v2(description)}")

        text_parts.append("")

    talents_data = {
        'purple': {'title': 'Эпические таланты', 'data': hero_json.get('purpleTalents', {})},
        'blue': {'title': 'Редкие таланты', 'data': hero_json.get('blueTalents', {})},
        'orange': {'title': 'Легендарные таланты', 'data': hero_json.get('orangeTalents', {})},
    }
    
    for color, info in talents_data.items():
        if info['data']:
            text_parts.append(f"*{escape_markdown_v2(info['title'])}:*")
            talent_emoji = EMOJI_MAP.get(color, "✨")
            for skill_key, skill_talents in info['data'].items():
                for talent in skill_talents:
                    description = talent.get('description', '')
                    if description:
                        text_parts.append("")
                        formatted_desc = format_text_with_emojis(description)
                        text_parts.append(f"• {talent_emoji} {escape_markdown_v2(formatted_desc)}")
            text_parts.append("")

    message_text = "\n".join(text_parts).strip()
    
    if not message_text:
        message_text = "Информация по этому герою не найдена."
    
    await send_long_message(context, update.callback_query.message.chat_id, message_text)

async def handle_hero_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    try:
        hero_name_api = query.data.split("_", 1)[1]
        if not hero_name_api:
            await query.message.reply_text("Не удалось получить имя героя. Пожалуйста, попробуйте выбрать героя еще раз.")
            return
    except (IndexError, ValueError):
        await query.message.reply_text("Произошла ошибка при обработке данных. Пожалуйста, сообщите об этом разработчику.")
        return
    
    await query.message.edit_text(f"Загружаю информацию о герое {hero_name_api}...")
    
    full_api_url = f"{CDN_HEROES_INFO_URL}ru_{hero_name_api}.json"
    
    hero_json_data = await fetch_json(full_api_url)
    
    if not hero_json_data:
        await query.message.edit_text(f"Не удалось получить данные для героя {hero_name_api}. Попробуйте позже.")
        return
        
    hero_name = hero_json_data.get('userFriendlyName') or hero_json_data.get('userFrendlyName', 'Герой')

    await query.message.delete()
    
    await send_hero_details(update, context, hero_json_data, hero_name)
    
    keyboard = [
        [InlineKeyboardButton("Назад", callback_data="back_to_attributes")],
    ]
    markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=query.message.chat_id, 
        text="Выберите следующий шаг:", 
        reply_markup=markup
    )

async def handle_back_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "back_to_attributes":
        keyboard = [
            [InlineKeyboardButton("Strength", callback_data="attribute_Strength")],
            [InlineKeyboardButton("Agility", callback_data="attribute_Agility")],
            [InlineKeyboardButton("Intellect", callback_data="attribute_Intellect")],
            [InlineKeyboardButton("Universal", callback_data="attribute_All")],
            [InlineKeyboardButton("Посмотреть на сайте", web_app=WebAppInfo(url=f"{BASE_URL}/heroes"))]
        ]
        await update.callback_query.message.edit_text("Выберите атрибут героя:", reply_markup=InlineKeyboardMarkup(keyboard))

async def preview_log(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        await update.message.reply_text("У вас нет прав для выполнения этой команды.")
        return
    if not RECENT_MESSAGES:
        await update.message.reply_text("Нет сообщений для отображения.")
        return
    log_text = "".join(RECENT_MESSAGES)
    await send_long_message(context, update.effective_chat.id, escape_markdown_v2(log_text))

def main():
    application = Application.builder().token(TOKEN).build()
    
    # Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("log", preview_log))
    
    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^Проверить статистику$"), start_dota_stats),
            MessageHandler(filters.Regex("^Обновления$"), handle_updates_button),
            MessageHandler(filters.Regex("^Герои$"), handle_heroes_button),
            MessageHandler(filters.Regex("^Ладдер$"), handle_leaderboard_button),
        ],
        states={
            GET_DOTA_ID: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_dota_id)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel_dota_stats)],
    )
    
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(handle_attribute_selection, pattern=r"^attribute_"))
    application.add_handler(CallbackQueryHandler(handle_hero_selection, pattern=r"^hero_"))
    application.add_handler(CallbackQueryHandler(handle_back_buttons, pattern=r"^back_to_attributes"))
    application.add_handler(CallbackQueryHandler(handle_heroes_button, pattern=r"^back_to_heroes"))
    
    try:
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except Conflict:
        logger.warning("Conflict detected, polling will continue.")

if __name__ == '__main__':
    main()
