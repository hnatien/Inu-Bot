"""
Cog for a coin flip gambling game.
"""
import asyncio
import logging
import random
from typing import Literal

import discord
from discord import app_commands
from discord.ext import commands

from utils.embed_utils import create_embed, create_error_embed, format_currency

logger = logging.getLogger(__name__)

Side = Literal["heads", "tails"]

class Coinflip(commands.Cog):
    """A cog for the classic coin flip gambling game."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = bot.db

    @app_commands.command(name="coinflip", description="Cược Inu Coin bằng cách tung đồng xu.")
    @app_commands.describe(
        amount="Số Inu Coin bạn muốn cược.",
        side="Chọn mặt bạn muốn cược."
    )
    @app_commands.choices(side=[
        app_commands.Choice(name="Mặt Sấp (Heads)", value="heads"),
        app_commands.Choice(name="Mặt Ngửa (Tails)", value="tails")
    ])
    async def coinflip(
        self, interaction: discord.Interaction, amount: app_commands.Range[int, 1, None], side: Side
    ):
        """Allows a user to bet currency on a coin flip."""
        user_id = interaction.user.id
        
        current_balance = await self.db.get_user_balance(user_id)
        if current_balance < amount:
            await interaction.response.send_message(
                embed=create_error_embed(f"Bạn không có đủ {format_currency(amount)}."),
                ephemeral=True
            )
            return

        await self.db.update_balance(user_id, -amount)
        
        side_display = "Mặt Sấp" if side == 'heads' else "Mặt Ngửa"
        flipping_embed = self._create_flipping_embed(interaction.user, amount, side_display)
        await interaction.response.send_message(embed=flipping_embed)

        await asyncio.sleep(2.5)

        result: Side = random.choice(['heads', 'tails'])
        is_winner = (result == side)

        payout = amount * 2 if is_winner else 0
        if is_winner:
            await self.db.update_balance(user_id, payout)

        new_balance = await self.db.get_user_balance(user_id)
        
        result_data = {
            "amount": amount,
            "payout": payout,
            "new_balance": new_balance
        }
        result_embed = self._create_result_embed(result, is_winner, result_data)

        await interaction.edit_original_response(embed=result_embed)

    def _create_flipping_embed(
        self, user: discord.User, amount: int, side_display: str
    ) -> discord.Embed:
        """Creates the initial embed shown while the coin is 'flipping'."""
        embed = create_embed(
            title="🪙 Coinflip",
            description=f"{user.mention} đã cược **{format_currency(amount)}** và chọn **{side_display}**.\n\nĐang tung đồng xu...",
            color=discord.Color.gold()
        )
        embed.set_thumbnail(url="https://i.gifer.com/origin/33/332b7a9254388b1d8557f8414161a018_w200.gif")
        return embed

    def _create_result_embed(
        self, result: Side, is_winner: bool, data: dict
    ) -> discord.Embed:
        """Creates the final embed showing the game result."""
        result_display = "Mặt Sấp" if result == 'heads' else "Mặt Ngửa"
        if is_winner:
            desc = f"Kết quả là **{result_display}**! Bạn đã thắng **{format_currency(data['payout'])}**."
            color = discord.Color.green()
        else:
            desc = f"Kết quả là **{result_display}**... Bạn đã thua **{format_currency(data['amount'])}**."
            color = discord.Color.red()

        desc += f"\n💰 **Số dư mới:** {format_currency(data['new_balance'])}"

        embed = create_embed(
            title="🪙 Coinflip - Kết quả",
            description=desc,
            color=color
        )
        thumbnail_url = "https://i.imgur.com/67hT8fD.png" if result == 'heads' else "https://i.imgur.com/M8PjZ3n.png"
        embed.set_thumbnail(url=thumbnail_url)
        return embed


async def setup(bot: commands.Bot):
    """Loads the Coinflip cog."""
    await bot.add_cog(Coinflip(bot))