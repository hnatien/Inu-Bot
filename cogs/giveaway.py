"""
Cog for handling persistent giveaways.
"""
import logging
import random
import sqlite3

import discord
from discord import app_commands
from discord.ext import commands, tasks

from utils.checks import is_deputy_admin
from utils.embed_utils import create_embed, create_error_embed
from utils.time_utils import parse_duration

logger = logging.getLogger(__name__)


class GiveawayView(discord.ui.View):
    """
    A persistent view for giveaway participation buttons.
    The actual logic is handled in the bot's listener to have access to the db.
    """
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(
        label="Tham Gia",
        style=discord.ButtonStyle.success,
        custom_id="persistent_giveaway:join"
    )
    async def join_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        """
        Handles the join button interaction.
        This is a placeholder; the main logic is in the bot's on_interaction listener.
        """
        result = await self.bot.db.add_giveaway_participant(
            interaction.message.id, interaction.user.id
        )

        if result is True:
            await interaction.response.send_message(
                "Bạn đã tham gia giveaway thành công! Chúc may mắn!", ephemeral=True
            )
        elif result is False:
            await interaction.response.send_message("Bạn đã tham gia giveaway này rồi!", ephemeral=True)
        else:
            await interaction.response.send_message(
                embed=create_error_embed("Có lỗi xảy ra khi tham gia. Vui lòng thử lại."),
                ephemeral=True
            )


class Giveaway(commands.Cog):
    """
    Manages giveaway creation, monitoring, and ending.
    """
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = bot.db
        self.bot.add_view(GiveawayView(self.bot))
        self.check_ended_giveaways.start()

    async def cog_unload(self):
        """Cancels the background task when the cog is unloaded."""
        self.check_ended_giveaways.cancel()

    @tasks.loop(seconds=15)
    async def check_ended_giveaways(self):
        """Periodically checks for and ends giveaways that have concluded."""
        try:
            ended_giveaways = await self.db.get_ended_giveaways()
            if ended_giveaways:
                logger.info("Found %d giveaway(s) to end.", len(ended_giveaways))

            for g_data in ended_giveaways:
                logger.info("Ending giveaway %s", g_data[0])
                await self.end_giveaway(g_data)
                await self.db.end_giveaway_db(g_data[0])
        except (discord.HTTPException, sqlite3.Error) as e:
            logger.error(
                "Error in check_ended_giveaways loop: %s", e, exc_info=True
            )

    @check_ended_giveaways.before_loop
    async def before_check_giveaways(self):
        """Waits for the bot to be ready before starting the loop."""
        await self.bot.wait_until_ready()

    @app_commands.command(name="giveaway", description="[Admin] Bắt đầu một giveaway mới.")
    @is_deputy_admin()
    @app_commands.describe(
        channel="Kênh để bắt đầu giveaway.",
        duration="Thời gian giveaway (ví dụ: 10s, 5m, 1h, 2d).",
        prize="Giải thưởng của giveaway."
    )
    async def giveaway(
        self, interaction: discord.Interaction, channel: discord.TextChannel,
        duration: str, prize: str
    ):
        """Creates a new persistent giveaway."""
        await interaction.response.defer(ephemeral=True)

        end_time = parse_duration(duration)
        if not end_time:
            await interaction.followup.send(
                embed=create_error_embed(
                    "Định dạng thời gian không hợp lệ. Hãy dùng (s, m, h, d)."
                )
            )
            return

        embed = create_embed(
            title="🎉 **GIVEAWAY** 🎉",
            description=f"**Giải thưởng:** {prize}\n\nHãy nhấn nút **Tham Gia** để thắng!",
            color=0x2ECC71
        )
        embed.add_field(
            name="Kết thúc", value=f"<t:{int(end_time.timestamp())}:R>", inline=True
        )
        embed.set_footer(text=f"Tổ chức bởi {interaction.user.display_name}")

        try:
            view = GiveawayView(self.bot)
            giveaway_message = await channel.send(embed=embed, view=view)

            await self.db.create_giveaway(
                giveaway_message.id,
                channel.id,
                interaction.guild.id,
                prize,
                end_time,
                interaction.user.id
            )

            await interaction.followup.send(f"Giveaway đã được bắt đầu tại {channel.mention}!")

        except discord.Forbidden:
            await interaction.followup.send(
                embed=create_error_embed(f"Bot không có quyền gửi tin nhắn trong {channel.mention}.")
            )
        except discord.HTTPException as e:
            logger.error(
                "Failed to start persistent giveaway: %s", e, exc_info=True
            )

    async def end_giveaway(self, giveaway_data):
        """Handles the logic for ending a giveaway and announcing the winner."""
        msg_id, chan_id, *_ = giveaway_data

        channel = self.bot.get_channel(chan_id)
        if not channel:
            logger.warning("Giveaway end: Channel %s not found.", chan_id)
            return

        participants = await self.db.get_giveaway_participants(msg_id)
        winner = await self._get_winner(participants)

        content, result_embed = await self._create_giveaway_result(
            winner, giveaway_data
        )

        try:
            await channel.send(content, embed=result_embed)
        except discord.Forbidden:
            logger.warning("Could not send giveaway result message in channel %s", chan_id)
        except discord.HTTPException as e:
            logger.error("Error sending giveaway result message: %s", e, exc_info=True)

    async def _get_winner(self, participants):
        """Selects and fetches a winner from the participant list."""
        if not participants:
            return None
        winner_id = random.choice(participants)
        try:
            return self.bot.get_user(winner_id) or await self.bot.fetch_user(winner_id)
        except discord.NotFound:
            logger.warning("Giveaway winner %s not found.", winner_id)
            return None

    async def _create_giveaway_result(self, winner, giveaway_data):
        """Creates the content and embed for the giveaway result message."""
        msg_id, chan_id, guild_id, prize, _, host_id = giveaway_data
        original_message_url = (
            f"https://discord.com/channels/{guild_id}/{chan_id}/{msg_id}"
        )
        result_embed = create_embed(
            title="🎉 Giveaway Đã Kết Thúc 🎉",
            description=(
                f"**Giải thưởng:** {prize}\n"
                f"Xem giveaway gốc [tại đây]({original_message_url})."
            ),
            color=0xE74C3C
        )

        if winner:
            content = f"Chúc mừng {winner.mention}! Bạn đã thắng **{prize}**."
            result_embed.add_field(
                name="Người chiến thắng", value=winner.mention, inline=False
            )
        else:
            content = f"Rất tiếc, không có ai tham gia giveaway **{prize}** cả."
            result_embed.add_field(
                name="Người chiến thắng", value="Không có ai tham gia.", inline=False
            )

        try:
            host = self.bot.get_user(host_id) or await self.bot.fetch_user(host_id)
            if host:
                result_embed.set_footer(text=f"Tổ chức bởi {host.display_name}")
        except discord.NotFound:
            logger.warning("Could not fetch host %s for giveaway result.", host_id)

        return content, result_embed


async def setup(bot: commands.Bot):
    """Loads the Giveaway cog."""
    await bot.add_cog(Giveaway(bot))