import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from urllib.parse import urljoin
from html.parser import HTMLParser
import logging

# Конфигурация
CDN_HEROES_URL = "https://cdn.dota1x6.com/heroes/"

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Вспомогательная функция для очистки HTML-тегов
class HTMLTagStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.reset()
        self.strict = False
        self.convert_charrefs = True
        self.fed = []

    def handle_data(self, data):
        self.fed.append(data)

    def get_data(self):
        return "".join(self.fed)

def clean_html_tags(html_text):
    if not html_text:
        return ""
    stripper = HTMLTagStripper()
    stripper.feed(html_text)
    return stripper.get_data().replace("<b>", "").replace("</b>", "").strip()

# Вспомогательная функция для экранирования MarkdownV2
def escape_markdown(text):
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return ''.join('\\' + char if char in escape_chars else char for char in text)

async def handle_hero_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    url_name = query.data.replace("hero_", "")

    logger.info(f"Выбран герой: {url_name}")

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
        if changes and isinstance(changes, list):
            text_content += f"*{escape_markdown('Отличия от Dota')}*:\n"
            for change in changes:
                description = change.get("description", "")
                if description:
                    text_content += f"  - {escape_markdown(clean_html_tags(description))}\n"
            text_content += "\n"

        # Раздел "Улучшения"
        upgrades = hero_data.get("upgrades")
        if upgrades and isinstance(upgrades, list):
            text_content += f"*{escape_markdown('Улучшения')}*:\n"
            upgrade_emojis = {"shard": "🔷", "scepter": "🔮", "innate": "🔥"}
            upgrade_ru_names = {"shard": "Аганим шард", "scepter": "Аганим", "innate": "Врожденный талант"}
            for upgrade in upgrades:
                upgrade_type = upgrade.get("upgradeType")
                upgrade_text = upgrade.get("description", "")
                emoji = upgrade_emojis.get(upgrade_type, "✨")
                ru_name = upgrade_ru_names.get(upgrade_type, "")
                if upgrade_text:
                    text_content += f"  {emoji} {escape_markdown(ru_name)}: {escape_markdown(clean_html_tags(upgrade_text))}\n"
            text_content += "\n"
        
        # Раздел "Таланты"
        talent_groups = [
            ("orangeTalents", "Легендарные таланты", "🟧"),
            ("purpleTalents", "Эпические таланты", "🟪"),
            ("blueTalents", "Редкие таланты", "🟦")
        ]
        
        for talent_key, talent_name, talent_emoji in talent_groups:
            talents_dict = hero_data.get(talent_key)
            if talents_dict and isinstance(talents_dict, dict):
                text_content += f"*{escape_markdown(talent_name)}*:\n"
                for skill_key, talents_list in talents_dict.items():
                    if isinstance(talents_list, list):
                        for talent in talents_list:
                            talent_description = talent.get("description", "")
                            if talent_description:
                                text_content += f"  {talent_emoji} {escape_markdown(clean_html_tags(talent_description))}\n"
                text_content += "\n"

        if len(text_content) > 4096:
            text_content = text_content[:4000] + "\n\n_(текст обрезан)_"

        keyboard = [[InlineKeyboardButton("⬅️ Назад к атрибутам", callback_data="back_to_attributes")]]
        
        await query.edit_message_text(
            text_content,
            parse_mode='MarkdownV2',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка при запросе к CDN для героя {url_name}: {e}")
        await query.edit_message_text("Произошла ошибка при получении данных о герое. Пожалуйста, попробуйте позже.")
    except Exception as e:
        logger.exception(f"Неизвестная ошибка при обработке данных героя {url_name}: {e}")
        await query.edit_message_text("Произошла неизвестная ошибка.")
