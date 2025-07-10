"""Cog for server moderation commands."""
import logging
from datetime import datetime, timezone
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from utils.embed_utils import create_embed, create_error_embed, create_success_embed

logger = logging.getLogger(__name__)


class Moderation(commands.Cog):
    """Commands for server moderation."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = bot.db

    mod_group = app_commands.Group(name="mod", description="Lệnh kiểm duyệt cho server.")
    modlog_group = app_commands.Group(name="modlog", description="Quản lý kênh log kiểm duyệt.")

    async def _log_action(self, interaction: discord.Interaction, log_details: dict):
        """A centralized function to send logs to the configured mod log channel."""
        if not interaction.guild:
            return

        log_channel_id = await self.db.get_mod_log_channel(interaction.guild.id)
        if not log_channel_id:
            return

        log_channel = self.bot.get_channel(log_channel_id)
        if not isinstance(log_channel, discord.TextChannel):
            logger.warning(
                "Mod log channel %s not found or not a text channel for guild %s",
                log_channel_id, interaction.guild.id
            )
            return

        embed = discord.Embed(
            title=log_details.get("title"),
            color=log_details.get("color"),
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_author(
            name=f"{interaction.user.display_name} ({interaction.user.id})",
            icon_url=interaction.user.display_avatar.url
        )

        target = log_details.get("target")
        if target:
            embed.add_field(name="Target", value=f"{target.mention} ({target.id})", inline=False)

        for name, value in log_details.get("fields", {}).items():
            embed.add_field(name=name.replace("_", " ").title(), value=value, inline=False)

        reason = log_details.get("reason")
        if reason:
            embed.add_field(name="Reason", value=reason, inline=False)

        try:
            await log_channel.send(embed=embed)
        except discord.Forbidden:
            logger.error(
                "Missing permissions to send to modlog channel %s in guild %s",
                log_channel.id, interaction.guild.id
            )
        except discord.HTTPException as e:
            logger.error("Failed to send to modlog channel: %s", e)

    @modlog_group.command(name="set_channel", description="[Admin] Đặt kênh để ghi lại các hành động kiểm duyệt.")
    @app_commands.describe(channel="Kênh văn bản bạn muốn dùng. Để trống để tắt ghi log.")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_log_channel(self, interaction: discord.Interaction, channel: Optional[discord.TextChannel]):
        """Sets or disables the moderation log channel for the guild."""
        if not interaction.guild_id:
            return

        await interaction.response.defer(ephemeral=True)

        channel_id_to_save = channel.id if channel else None
        await self.db.set_mod_log_channel(interaction.guild_id, channel_id_to_save)

        if channel:
            message = f"Kênh log kiểm duyệt đã được đặt thành {channel.mention}."
            try:
                log_embed = create_embed(
                    "Logger Enabled",
                    f"Kênh này sẽ được sử dụng để ghi lại các hành động kiểm duyệt, "
                    f"được thiết lập bởi {interaction.user.mention}."
                )
                await channel.send(embed=log_embed)
            except discord.Forbidden:
                message += "\n⚠️ **Cảnh báo:** Bot không có quyền gửi tin nhắn trong kênh đó."
        else:
            message = "Đã tắt chức năng ghi log kiểm duyệt."

        await interaction.followup.send(embed=create_success_embed(message), ephemeral=True)

    @mod_group.command(name="clear", description="[Mod] Xóa một số lượng tin nhắn trong kênh hiện tại.")
    @app_commands.describe(amount="Số lượng tin nhắn muốn xóa (tối đa 100).")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def clear(self, interaction: discord.Interaction, amount: app_commands.Range[int, 1, 100]):
        """Clears a specified number of messages from the current channel."""
        await interaction.response.defer(ephemeral=True)

        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.followup.send(
                embed=create_error_embed("Không thể xóa tin nhắn trong loại kênh này."), ephemeral=True
            )
            return

        deleted = await interaction.channel.purge(limit=amount)
        await interaction.followup.send(
            embed=create_success_embed(f"Đã xóa thành công {len(deleted)} tin nhắn."), ephemeral=True
        )

        log_details = {
            "title": "🗑️ Messages Cleared",
            "color": discord.Color.orange(),
            "fields": {
                "Channel": interaction.channel.mention,
                "Amount": f"{len(deleted)}",
            }
        }
        await self._log_action(interaction, log_details)

    async def _check_moderation_permissions(
        self, interaction: discord.Interaction, member: discord.Member
    ) -> Optional[discord.Embed]:
        """Performs standard permission checks for kick/ban commands."""
        if not interaction.guild:
            return create_error_embed("Lệnh này chỉ có thể dùng trong server.")
        if member.id == interaction.user.id:
            return create_error_embed("Bạn không thể tự thực hiện hành động này với chính mình.")
        if member.top_role >= interaction.user.top_role and interaction.guild.owner_id != interaction.user.id:
            return create_error_embed("Bạn không thể thực hiện với người có vai trò cao hơn hoặc bằng bạn.")
        if member.id == self.bot.user.id:
            return create_error_embed("...")
        return None

    @mod_group.command(name="kick", description="[Mod] Kick một thành viên khỏi server.")
    @app_commands.describe(member="Thành viên cần kick.", reason="Lý do kick (không bắt buộc).")
    @app_commands.checks.has_permissions(kick_members=True)
    async def kick(
        self, interaction: discord.Interaction, member: discord.Member, reason: Optional[str] = None
    ):
        """Kicks a member from the server."""
        permission_error = await self._check_moderation_permissions(interaction, member)
        if permission_error:
            await interaction.response.send_message(embed=permission_error, ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        reason = reason or "Không có lý do được cung cấp."

        try:
            dm_embed = create_embed(
                "Thông Báo Kick",
                f"Bạn đã bị kick khỏi server **{interaction.guild.name}**.\n**Lý do:** {reason}",
                color=discord.Color.orange()
            )
            await member.send(embed=dm_embed)
        except discord.Forbidden:
            pass  # User has DMs disabled

        await member.kick(reason=reason)
        await interaction.followup.send(
            embed=create_success_embed(f"Đã kick thành công {member.mention}."), ephemeral=True
        )

        log_details = {
            "title": "👢 Member Kicked",
            "color": discord.Color.orange(),
            "target": member,
            "reason": reason
        }
        await self._log_action(interaction, log_details)

    @mod_group.command(name="ban", description="[Mod] Ban một thành viên khỏi server.")
    @app_commands.describe(
        member="Thành viên cần ban.",
        reason="Lý do ban (không bắt buộc).",
        delete_message_days="Số ngày tin nhắn của người này sẽ bị xóa (0-7)."
    )
    @app_commands.checks.has_permissions(ban_members=True)
    async def ban(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: Optional[str] = None,
        delete_message_days: app_commands.Range[int, 0, 7] = 0
    ):
        """Bans a member from the server."""
        permission_error = await self._check_moderation_permissions(interaction, member)
        if permission_error:
            await interaction.response.send_message(embed=permission_error, ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        reason = reason or "Không có lý do được cung cấp."

        try:
            dm_embed = create_embed(
                "Thông Báo Ban",
                f"Bạn đã bị ban khỏi server **{interaction.guild.name}**.\n**Lý do:** {reason}",
                color=discord.Color.red()
            )
            await member.send(embed=dm_embed)
        except discord.Forbidden:
            pass  # User has DMs disabled

        await member.ban(reason=reason, delete_message_days=delete_message_days)
        await interaction.followup.send(
            embed=create_success_embed(f"Đã ban vĩnh viễn {member.mention}."), ephemeral=True
        )

        log_details = {
            "title": "🔨 Member Banned",
            "color": discord.Color.red(),
            "target": member,
            "reason": reason,
            "fields": {"Deleted Messages": f"{delete_message_days} ngày"}
        }
        await self._log_action(interaction, log_details)


async def setup(bot: commands.Bot):
    """Loads the Moderation cog."""
    await bot.add_cog(Moderation(bot))
