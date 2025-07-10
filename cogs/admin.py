import logging
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

from utils.embed_utils import create_embed, create_error_embed, format_currency

logger = logging.getLogger(__name__)

class Admin(commands.Cog):
    """A cog for bot owner and admin commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = bot.db

    # Group for economy administration commands
    eco_admin_group = app_commands.Group(
        name="eco_admin",
        description="[Admin] Các lệnh quản lý kinh tế.",
        default_permissions=discord.Permissions(administrator=True)
    )

    @eco_admin_group.command(name="add", description="[Admin] Cộng tiền cho một người dùng.")
    @app_commands.describe(user="Người dùng bạn muốn cộng tiền.", amount="Số tiền muốn cộng.")
    @app_commands.checks.has_permissions(administrator=True)
    async def eco_add(
        self, interaction: discord.Interaction, user: discord.Member, amount: app_commands.Range[int, 1]
    ):
        """Cộng tiền vào số dư của người dùng."""
        await self.db.add_or_update_user(user)
        success = await self.db.update_balance(user.id, amount)

        if success:
            new_balance = await self.db.get_user_balance(user.id)
            await interaction.response.send_message(
                embed=create_embed(
                    "Thành công",
                    f"Đã cộng **{format_currency(amount)}** cho {user.mention}.\n"
                    f"Số dư mới: **{format_currency(new_balance)}**."
                ), ephemeral=True
            )
        else:
            await interaction.response.send_message(
                embed=create_error_embed("Có lỗi xảy ra khi cập nhật số dư."), ephemeral=True
            )

    @eco_admin_group.command(name="remove", description="[Admin] Trừ tiền của một người dùng.")
    @app_commands.describe(user="Người dùng bạn muốn trừ tiền.", amount="Số tiền muốn trừ.")
    @app_commands.checks.has_permissions(administrator=True)
    async def eco_remove(
        self, interaction: discord.Interaction, user: discord.Member, amount: app_commands.Range[int, 1]
    ):
        """Trừ tiền từ số dư của người dùng."""
        await self.db.add_or_update_user(user)
        
        current_balance = await self.db.get_user_balance(user.id)
        if current_balance < amount:
            await interaction.response.send_message(
                embed=create_error_embed(f"Người dùng chỉ có {format_currency(current_balance)}, không thể trừ {format_currency(amount)}."),
                ephemeral=True
            )
            return
            
        success = await self.db.update_balance(user.id, -amount)

        if success:
            new_balance = await self.db.get_user_balance(user.id)
            await interaction.response.send_message(
                embed=create_embed(
                    "Thành công",
                    f"Đã trừ **{format_currency(amount)}** của {user.mention}.\n"
                    f"Số dư mới: **{format_currency(new_balance)}**."
                ), ephemeral=True
            )
        else:
            await interaction.response.send_message(
                embed=create_error_embed("Có lỗi xảy ra khi cập nhật số dư."),
                ephemeral=True
            )

    @eco_admin_group.command(name="set", description="[Admin] Thiết lập số dư chính xác cho một người dùng.")
    @app_commands.describe(user="Người dùng bạn muốn đặt số dư.", amount="Số dư chính xác muốn đặt.")
    @app_commands.checks.has_permissions(administrator=True)
    async def eco_set(
        self, interaction: discord.Interaction, user: discord.Member, amount: app_commands.Range[int, 0]
    ):
        """Thiết lập một số dư chính xác cho người dùng."""
        await self.db.add_or_update_user(user)
        success = await self.db.force_set_balance(user.id, amount)

        if success:
            await interaction.response.send_message(
                embed=create_embed(
                    "Thành công",
                    f"Đã đặt số dư của {user.mention} thành **{format_currency(amount)}**."
                ), ephemeral=True
            )
        else:
            await interaction.response.send_message(
                embed=create_error_embed("Có lỗi xảy ra khi cập nhật số dư."), ephemeral=True
            )

    @app_commands.command(name="broadcast", description="[Admin] Gửi một thông báo tới tất cả các kênh theo dõi stock.")
    @app_commands.describe(message="Nội dung thông báo bạn muốn gửi.")
    @app_commands.checks.has_permissions(administrator=True)
    async def broadcast(self, interaction: discord.Interaction, message: str):
        """Gửi một thông báo broadcast từ chủ sở hữu bot đến tất cả các kênh stock."""
        await interaction.response.defer(ephemeral=True)

        all_channel_ids = await self.db.get_all_stock_channels()
        if not all_channel_ids:
            await interaction.followup.send(
                embed=create_error_embed("Không có kênh nào được cấu hình để nhận thông báo."),
                ephemeral=True
            )
            return

        embed = create_embed(
            title="📢 Thông báo từ Developer 📢",
            description=message,
            color=discord.Color.orange()
        )
        embed.set_footer(
            text=f"Gửi bởi {interaction.user.display_name}",
            icon_url=interaction.user.display_avatar.url
        )
        embed.timestamp = datetime.now(timezone.utc)

        successful_sends = 0
        failed_sends = 0
        for channel_id in all_channel_ids:
            channel = self.bot.get_channel(channel_id)
            if channel:
                try:
                    await channel.send(embed=embed)
                    successful_sends += 1
                except discord.Forbidden:
                    logger.warning("Không thể gửi broadcast tới kênh %s (Forbidden).", channel_id)
                    failed_sends += 1
                except discord.HTTPException as e:
                    logger.error("Lỗi khi gửi broadcast tới kênh %s: %s", channel_id, e)
                    failed_sends += 1
            else:
                logger.warning("Không tìm thấy kênh %s để gửi broadcast.", channel_id)
                failed_sends += 1

        await interaction.followup.send(
            embed=create_embed(
                "Hoàn tất Broadcast",
                f"✅ Đã gửi tới: {successful_sends} kênh.\n❌ Thất bại: {failed_sends} kênh."
            ),
            ephemeral=True
        )

async def setup(bot: commands.Bot):
    """Tải cog Admin vào bot."""
    await bot.add_cog(Admin(bot))