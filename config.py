"""
Tệp cấu hình trung tâm cho Inu-Bot.

Tải các biến môi trường từ tệp .env và định nghĩa các hằng số cấu hình
được sử dụng trong toàn bộ ứng dụng.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# pylint: disable=too-few-public-methods
class Config:
    """
    Lớp cấu hình chứa tất cả các cài đặt và hằng số cho bot.
    """
    # Discord Settings
    DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
    # A comma-separated list of guild IDs for instant command syncing
    DEV_GUILD_IDS = [
        int(x.strip())
        for x in os.getenv(
            'DEV_GUILD_IDS', '1264247195310362746,1382226403889647746'
        ).split(',')
        if x.strip()
    ]
    
    # Admin Settings
    ADMIN_USERS = [int(x.strip()) for x in os.getenv('ADMIN_USERS', '').split(',') if x.strip()]
    DEPUTY_ADMIN_ROLES = [
        int(x.strip()) for x in os.getenv('DEPUTY_ADMIN_ROLES', '').split(',') if x.strip()
    ]
    
    # Currency Settings
    CURRENCY_NAME = os.getenv('CURRENCY_NAME', 'Inu Coin')
    CURRENCY_SYMBOL = os.getenv('CURRENCY_SYMBOL', '🪙')
    DAILY_REWARD = int(os.getenv('DAILY_REWARD', '100'))
    MAX_STREAK_MULTIPLIER = int(os.getenv('MAX_STREAK_MULTIPLIER', '5'))
    
    # Database Settings
    DATABASE_PATH = os.getenv('DATABASE_PATH', './data/inu_bot.db')
    
    # Update Channel
    UPDATE_CHANNEL_ID_STR = os.getenv('UPDATE_CHANNEL_ID')
    UPDATE_CHANNEL_ID = int(UPDATE_CHANNEL_ID_STR) if UPDATE_CHANNEL_ID_STR else 1390646361673961492
    
    # Roblox Settings
    ROBLOX_COOKIE = os.getenv('ROBLOX_COOKIE')
    
    # Bot Settings
    COMMAND_PREFIX = '/'
    BOT_NAME = 'Inu Bot'
    BOT_VERSION = '1.0.0'
    ACTIVITY_NAME = os.getenv('ACTIVITY_NAME', '/help for commands')
    
    # Gambling Settings
    MIN_BET = int(os.getenv("MIN_BET", '10'))
    MAX_BET = int(os.getenv("MAX_BET", '1000000'))
    HOUSE_EDGE = 0.02  # 2% house edge
    
    # Colors for embeds
    COLOR_SUCCESS = 0x00ff00
    COLOR_ERROR = 0xff0000
    COLOR_WARNING = 0xffff00
    COLOR_INFO = 0x0099ff
    COLOR_PRIMARY = 0xff6b35  # Orange color for Inu theme 

    # --- Roblox Stock Tracker (GrowAGarden.PRO WebSocket) ---
    ROBLOX_STOCK_ENABLED = os.getenv(
        "ROBLOX_STOCK_ENABLED", "True"
    ).lower() in ("true", "1", "t")
    ROBLOX_WEBSOCKET_URL = os.getenv(
        "ROBLOX_WEBSOCKET_URL", "wss://ws.growagardenpro.com/"
    )
    ROBLOX_PING_ROLE_ID = int(os.getenv("ROBLOX_PING_ROLE_ID", '1390656247732375573'))
    # A comma-separated list of channel IDs to send stock updates to (DEPRECATED)
    # ROBLOX_ANNOUNCE_CHANNEL_IDS = [
    #    int(x.strip())
    #    for x in os.getenv(
    #        'ROBLOX_ANNOUNCE_CHANNEL_IDS',
    #        '1390646361673961492,1382227986996133978'
    #    ).split(',')
    #    if x.strip()
    # ]

# Create a singleton instance of the config
Config = Config()