"""
Utility functions for creating standardized Discord embeds.
"""
import discord
from config import Config

def create_embed(title, description, color=Config.COLOR_PRIMARY, **kwargs):
    """Creates a standard Discord embed."""
    embed = discord.Embed(title=title, description=description, color=color, **kwargs)
    embed.set_footer(text=f"{Config.BOT_NAME} v{Config.BOT_VERSION}")
    return embed

def create_error_embed(description):
    """Creates a standard error embed."""
    return create_embed("Lỗi", description, color=Config.COLOR_ERROR)

def create_success_embed(description):
    """Creates a standard success embed."""
    return create_embed("Thành Công", description, color=Config.COLOR_SUCCESS)

def format_currency(amount):
    """Formats a number into a currency string."""
    return f"{amount:,} {Config.CURRENCY_SYMBOL}" 