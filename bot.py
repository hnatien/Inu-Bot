"""Module chính cho Inu-Bot, một bot Discord đa năng."""

import logging
import logging.config
import os
from typing import Literal, Optional

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from config import Config
from database.database_manager import DatabaseManager
from utils.embed_utils import create_error_embed

load_dotenv()

# --- Logging Setup ---
logging.config.dictConfig({
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'default': {
            'format': '[%(asctime)s] [%(levelname)-5s] [%(name)-20s] --- %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S'
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'default',
            'level': 'INFO',
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'formatter': 'default',
            'level': 'INFO',
            'filename': 'inu_bot.log',
            'maxBytes': 1024*1024*5, # 5 MB
            'backupCount': 5,
            'encoding': 'utf-8',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    }
})
logger = logging.getLogger(__name__)

# --- Bot Initialization ---
class InuBot(commands.Bot):
    """
    Lớp bot chính kế thừa từ commands.Bot, khởi tạo và quản lý bot.
    """
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix="!", intents=intents)
        self.db = DatabaseManager('database/inu_database.db')
        self.active_game_sessions = set()

    async def setup_hook(self):
        """
        Thiết lập hook để khởi tạo kết nối cơ sở dữ liệu và tải các cogs.
        """
        logger.info("--- Starting Bot Setup ---")
        
        # Connect to the database
        await self.db.initialize()
        logger.info("Successfully connected to the database.")

        # Load cogs recursively and robustly
        cogs_loaded = 0
        cogs_path = "cogs"
        for root, _, files in os.walk(cogs_path):
            for filename in files:
                if filename.endswith(".py") and not filename.startswith("__"):
                    # Construct the full cog path like 'cogs.games.blackjack'
                    relative_path = os.path.relpath(root, start=os.getcwd())
                    module_path = os.path.join(relative_path, filename[:-3]).replace(os.sep, '.')
                    
                    try:
                        await self.load_extension(module_path)
                        logger.info("Successfully loaded cog: %s", module_path)
                        cogs_loaded += 1
                    except commands.ExtensionError as e:
                        logger.error("Failed to load cog %s: %s", module_path, e, exc_info=True)
        
        logger.info("--- Loaded %s cogs ---", cogs_loaded)
        
        logger.info("--- Bot Setup Complete ---")

    async def on_ready(self):
        """
        Được gọi khi bot sẵn sàng và đã kết nối thành công với Discord.
        """
        await self.change_presence(activity=discord.Game(name=Config.ACTIVITY_NAME))
        logger.info('Logged in as %s (ID: %s)', self.user, self.user.id)
        logger.info('Bot is ready and online!')
        
    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Trình xử lý lỗi chung cho tất cả các lệnh slash."""
        # Log the full error for debugging purposes
        command_name = interaction.command.name if interaction.command else "unknown"
        logger.error(
            "Error in command '%s': %s", command_name, error, exc_info=True
        )

        user_error_message = "Có lỗi không mong muốn xảy ra. Vui lòng thử lại sau."
        
        if isinstance(error, app_commands.errors.CommandOnCooldown):
            user_error_message = (
                f"Lệnh này đang trong thời gian hồi. "
                f"Vui lòng thử lại sau {error.retry_after:.1f} giây."
            )
        elif isinstance(error, app_commands.errors.MissingPermissions):
            user_error_message = "Bạn không có quyền để sử dụng lệnh này."
        elif isinstance(error, app_commands.errors.CheckFailure):
            # A generic catch-all for other permission-related checks.
            # This will also catch our custom "is_not_in_game" check.
            user_error_message = (
                "Bạn không đáp ứng đủ điều kiện để sử dụng lệnh này. "
                "(Có thể bạn đang trong một game khác?)"
            )

        embed = create_error_embed(user_error_message)

        try:
            # Use followup if the initial response has already been sent
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)
        except discord.HTTPException as e:
            # Log if sending the error message itself fails
            logger.error("Failed to send error message to interaction: %s", e)

    async def close(self):
        """
        Dọn dẹp tài nguyên trước khi bot đóng kết nối.
        """
        logger.info("Closing bot connection...")
        await self.db.close()
        await super().close()

bot = InuBot()

@bot.command()
@commands.guild_only()
@commands.is_owner()
async def sync(
    ctx: commands.Context,
    guilds: commands.Greedy[discord.Object],
    spec: Optional[Literal["~", "*", "^"]] = None
) -> None:
    """
    Đồng bộ hóa các lệnh ứng dụng (slash commands) với Discord.

    Chỉ có chủ sở hữu bot mới có thể sử dụng lệnh này.

    Usage:
    - `!sync`: Đồng bộ các lệnh global.
    - `!sync ~`: Đồng bộ các lệnh cho guild hiện tại.
    - `!sync *`: Sao chép và đồng bộ các lệnh global vào guild hiện tại.
    - `!sync ^`: Xóa tất cả các lệnh khỏi guild hiện tại và đồng bộ.
    - `!sync <guild_id_1> <guild_id_2>`: Đồng bộ các lệnh cho các guild được chỉ định.
    - `!sync ^ <guild_id_1>`: Xóa các lệnh khỏi guild được chỉ định.
    """
    if not guilds:
        if spec == "~":
            # Sync to the current guild only.
            synced = await ctx.bot.tree.sync(guild=ctx.guild)
            await ctx.send(f"Synced {len(synced)} commands to the current guild.")
        elif spec == "*":
            # Copies all global commands to the current guild and syncs.
            ctx.bot.tree.copy_global_to(guild=ctx.guild)
            synced = await ctx.bot.tree.sync(guild=ctx.guild)
            await ctx.send(
                f"Copied and synced {len(synced)} commands to the current guild."
            )
        elif spec == "^":
            # Clears all commands from the current guild tree and syncs.
            ctx.bot.tree.clear_commands(guild=ctx.guild)
            await ctx.bot.tree.sync(guild=ctx.guild)
            await ctx.send("Cleared all commands from the current guild.")
        else:
            # Syncs all global commands to all guilds.
            synced = await ctx.bot.tree.sync()
            await ctx.send(f"Synced {len(synced)} commands globally.")
        return

    # Handle syncing to specified guilds
    synced_count = 0
    for guild in guilds:
        try:
            if spec == "^":
                # Clear commands for the specified guild before syncing.
                logger.info("Clearing commands for guild %s...", guild.id)
                ctx.bot.tree.clear_commands(guild=guild)
                await ctx.bot.tree.sync(guild=guild) # Sync the clearance
                logger.info("Commands cleared for guild %s.", guild.id)

            # Sync the new tree
            await ctx.bot.tree.sync(guild=guild)
            logger.info("Synced commands for guild %s.", guild.id)
            synced_count += 1
        except discord.HTTPException as e:
            logger.error("Failed to sync commands to guild %s: %s", guild.id, e)

    await ctx.send(f"Synced/Cleared commands for {synced_count}/{len(guilds)} specified guilds.")


if __name__ == "__main__":
    TOKEN = os.getenv('DISCORD_TOKEN')
    if TOKEN is None:
        raise ValueError("DISCORD_TOKEN environment variable not set.")
    bot.run(TOKEN)
