"""A cog for a slots game."""

import asyncio
import logging
import random
from collections import namedtuple
import sqlite3

import discord
from discord import app_commands
from discord.ext import commands

from config import Config
from utils.embed_utils import create_embed, create_error_embed, format_currency

logger = logging.getLogger(__name__)

REELS = ['💎', '🍊', '🍋', '🔔', '🍒', '🍀', 'BAR']
PAYOUTS = {
    '💎': 20, '🍀': 15, 'BAR': 10, '🔔': 8,
    '🍊': 5, '🍋': 3, '🍒': 2
}
GameResult = namedtuple("GameResult", ["results", "winnings", "is_win"])

class SlotsCog(commands.Cog):
    """Cog for the slots game command."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _check_balance(self, interaction: discord.Interaction, bet: int) -> bool:
        """Check if the user has enough balance."""
        balance = await self.bot.db.get_user_balance(interaction.user.id)
        if balance < bet:
            await interaction.followup.send(
                embed=create_error_embed("Bạn không đủ tiền để đặt cược."),
                ephemeral=True
            )
            return False
        return True

    async def _run_spin_animation(self, interaction: discord.Interaction) -> discord.Message:
        """Display the initial spinning embed."""
        initial_embed = create_embed(
            title="🎰 Slots 🎰",
            description="Đang quay... Chúc may mắn!",
            color=Config.COLOR_INFO
        )
        initial_embed.add_field(name="Kết quả", value="`?` `?` `?`")
        await interaction.followup.send(embed=initial_embed)
        return await interaction.original_response()

    def _get_game_result(self, bet: int) -> GameResult:
        """Determine the outcome of the slots game."""
        results = [random.choice(REELS) for _ in range(3)]
        is_win = results[0] == results[1] == results[2]
        winnings = 0

        if is_win:
            symbol = results[0]
            multiplier = PAYOUTS.get(symbol, 0)
            winnings = bet * multiplier
        else:
            winnings = -bet

        return GameResult(results=results, winnings=winnings, is_win=is_win)

    async def _process_game_result(
        self, interaction: discord.Interaction, bet: int, game_result: GameResult
    ) -> discord.Embed:
        """Processes the result of the game, updating balance and creating the final embed."""
        user_id = interaction.user.id
        winnings = game_result.winnings

        try:
            # A win (winnings > bet) or breaking even (winnings == bet)
            # still results in a positive 'winnings' value.
            # A loss means winnings are 0.
            # The net change is always winnings - bet.
            net_change = winnings - bet
            await self.bot.db.update_balance(user_id, net_change)

        except sqlite3.Error as e:
            logger.error("Database error processing slots result for %s: %s", user_id, e)
            return create_error_embed(
                "Đã xảy ra lỗi khi cập nhật số dư. Vui lòng thử lại sau."
            )

        result_text = f"`{'` `'.join(game_result.results)}`"

        if game_result.is_win:
            final_description = f"**JACKPOT!** Bạn đã thắng **{format_currency(winnings)}**!"
            color = Config.COLOR_SUCCESS
        else:
            final_description = f"**Tiếc quá!** Bạn đã thua **{format_currency(bet)}**."
            color = Config.COLOR_ERROR

        final_embed = create_embed(
            title="🎰 Slots 🎰", description=final_description, color=color
        )
        final_embed.add_field(name="Kết quả", value=result_text)

        new_balance = await self.bot.db.get_user_balance(user_id)
        final_embed.set_footer(text=f"Số dư mới: {format_currency(new_balance)}")
        return final_embed

    @app_commands.command(name="slots", description="Thử vận may với máy kéo!")
    @app_commands.describe(bet="Số tiền bạn muốn cược.")
    async def slots(
        self, interaction: discord.Interaction,
        bet: app_commands.Range[int, Config.MIN_BET, Config.MAX_BET]
    ):
        """Allows a user to play a game of slots."""
        await interaction.response.defer()

        if not await self._check_balance(interaction, bet):
            return

        original_message = await self._run_spin_animation(interaction)
        await asyncio.sleep(2)

        game_result = self._get_game_result(bet)

        final_embed = await self._process_game_result(
            interaction, bet, game_result
        )

        await original_message.edit(embed=final_embed)


async def setup(bot: commands.Bot):
    """Sets up the cog."""
    await bot.add_cog(SlotsCog(bot)) 