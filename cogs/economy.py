"""
Cog for economy-related commands like daily rewards, balance checking, and leaderboards.
"""
import logging
import math
from datetime import date, datetime, timedelta

import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite

from config import Config
from utils.embed_utils import create_embed, create_error_embed, format_currency

logger = logging.getLogger(__name__)

# --- Leaderboard View ---
def create_leaderboard_embed(page_data, page_num, total_pages):
    """Creates an embed for a single page of the leaderboard."""
    title = f"🏆 Bảng Xếp Hạng {Config.CURRENCY_NAME} 🏆"
    description = "Những người dùng giàu có và quyền lực nhất server."
    embed = create_embed(title=title, description=description)

    description_lines = []
    medals = ["🥇", "🥈", "🥉"]

    for i, (_, username, balance) in enumerate(page_data):
        rank = (page_num - 1) * 10 + i + 1
        rank_display = medals[rank - 1] if rank <= 3 else f"**#{rank}**"

        description_lines.append(
            f"{rank_display} {username} - **{format_currency(balance)}**"
        )

    embed.description = "\n".join(description_lines)
    embed.set_footer(text=f"Trang {page_num}/{total_pages}")
    return embed


class LeaderboardView(discord.ui.View):
    """
    A view for navigating through the leaderboard pages.
    """
    def __init__(self, all_data, author_id, items_per_page=10):
        super().__init__(timeout=180)
        self.all_data = all_data
        self.author_id = author_id
        self.items_per_page = items_per_page
        self.current_page = 1
        self.total_pages = math.ceil(len(self.all_data) / self.items_per_page)
        self.message = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Checks if the user interacting with the view is the author."""
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "Chỉ người gọi lệnh mới có thể sử dụng các nút này.", ephemeral=True
            )
            return False
        return True

    async def start(self, interaction: discord.Interaction):
        """Starts the view and sends the initial message."""
        page_data = self.get_page_data()
        embed = create_leaderboard_embed(page_data, self.current_page, self.total_pages)
        self.update_buttons()
        await interaction.followup.send(embed=embed, view=self)
        self.message = await interaction.original_response()

    def get_page_data(self):
        """Gets the data for the current page."""
        start_index = (self.current_page - 1) * self.items_per_page
        end_index = start_index + self.items_per_page
        return self.all_data[start_index:end_index]

    def update_buttons(self):
        """Updates the state of the navigation buttons."""
        self.prev_page.disabled = self.current_page == 1
        self.next_page.disabled = self.current_page >= self.total_pages

    async def update_message(self, interaction: discord.Interaction):
        """Updates the message with the new page content."""
        self.update_buttons()
        page_data = self.get_page_data()
        embed = create_leaderboard_embed(page_data, self.current_page, self.total_pages)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="<<", style=discord.ButtonStyle.grey)
    async def prev_page(self, interaction: discord.Interaction, _: discord.ui.Button):
        """Goes to the previous page."""
        if self.current_page > 1:
            self.current_page -= 1
            await self.update_message(interaction)

    @discord.ui.button(label=">>", style=discord.ButtonStyle.grey)
    async def next_page(self, interaction: discord.Interaction, _: discord.ui.Button):
        """Goes to the next page."""
        if self.current_page < self.total_pages:
            self.current_page += 1
            await self.update_message(interaction)

    async def on_timeout(self):
        """Disables buttons when the view times out."""
        if self.message:
            for item in self.children:
                item.disabled = True
            try:
                await self.message.edit(view=self)
            except discord.NotFound:
                pass  # Message was likely deleted

class Economy(commands.Cog):
    """
    Handles all economy-related commands and logic.
    """
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = bot.db

    @app_commands.command(name="daily", description=f"Nhận {Config.DAILY_REWARD} {Config.CURRENCY_NAME} hàng ngày.")
    async def daily(self, interaction: discord.Interaction):
        """Allows a user to claim their daily reward and manages streaks."""
        await interaction.response.defer(ephemeral=True)
        user = interaction.user
        await self.db.add_or_update_user(user)

        today = date.today()

        try:
            claim_info = await self.db.get_daily_claim_info(user.id)
            streak = 1
            if claim_info:
                last_claim_date_str, current_streak = claim_info
                last_claim_date = datetime.strptime(last_claim_date_str, '%Y-%m-%d').date()

                if last_claim_date == today:
                    msg = "Bạn đã điểm danh hôm nay rồi. Hãy quay lại vào ngày mai nhé!"
                    await interaction.followup.send(embed=create_error_embed(msg))
                    return

                if last_claim_date == today - timedelta(days=1):
                    streak = current_streak + 1

            reward_details = self._calculate_reward(streak)

            success = await self.db.update_balance(user.id, reward_details['total'])
            if not success:
                await interaction.followup.send(
                    embed=create_error_embed("Có lỗi xảy ra khi cập nhật số dư của bạn.")
                )
                return

            await self.db.update_daily_claim(user.id, today.isoformat(), streak)

            embed = self._create_daily_embed(reward_details, streak)
            await interaction.followup.send(embed=embed)

        except (discord.HTTPException, aiosqlite.Error) as e:
            logger.error("Error in /daily command for user %s: %s", user.id, e)
            await interaction.followup.send(
                embed=create_error_embed("Đã có lỗi xảy ra. Vui lòng thử lại sau.")
            )

    def _calculate_reward(self, streak: int) -> dict:
        """Calculates the daily reward based on the streak."""
        base = Config.DAILY_REWARD
        bonus_multiplier = min(streak - 1, Config.MAX_STREAK_MULTIPLIER)
        bonus = bonus_multiplier * (base // 10)
        total = base + bonus
        return {"base": base, "bonus": bonus, "total": total}

    def _create_daily_embed(self, reward: dict, streak: int):
        """Helper function to create the daily success embed."""
        embed = create_embed(
            title="Điểm Danh Thành Công!",
            description=f"Bạn đã nhận được **{reward['total']} {Config.CURRENCY_SYMBOL}**.",
            color=Config.COLOR_SUCCESS
        )
        embed.add_field(
            name="Phần Thưởng Gốc", value=f"{reward['base']} {Config.CURRENCY_SYMBOL}", inline=True
        )
        if reward['bonus'] > 0:
            embed.add_field(
                name="Thưởng Chuỗi", value=f"{reward['bonus']} {Config.CURRENCY_SYMBOL}", inline=True
            )
        embed.add_field(name="Chuỗi Hiện Tại", value=f"🔥 {streak} ngày", inline=True)
        embed.set_footer(text="Hãy quay lại vào ngày mai để duy trì chuỗi điểm danh!")
        return embed

    @app_commands.command(name="balance", description="Kiểm tra số dư Inu Coin của bạn hoặc người khác.")
    @app_commands.describe(user="Người dùng bạn muốn kiểm tra (để trống nếu là bạn).")
    async def balance(self, interaction: discord.Interaction, user: discord.Member = None):
        """Displays the currency balance of a user."""
        await interaction.response.defer(ephemeral=True)
        target_user = user or interaction.user
        await self.db.add_or_update_user(target_user)

        balance_val = await self.db.get_user_balance(target_user.id)

        embed = create_embed(
            title=f"Số Dư Của {target_user.display_name}",
            description=f"Hiện đang có: **{format_currency(balance_val)}**"
        )
        embed.set_thumbnail(url=target_user.display_avatar.url)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="leaderboard", description="Xem bảng xếp hạng các đại gia Inu Coin.")
    async def leaderboard(self, interaction: discord.Interaction):
        """Shows the server's leaderboard."""
        await interaction.response.defer()

        leaderboard_data = await self.db.get_leaderboard()

        if not leaderboard_data:
            await interaction.followup.send(embed=create_error_embed("Chưa có ai trên bảng xếp hạng cả!"))
            return

        view = LeaderboardView(leaderboard_data, interaction.user.id)
        await view.start(interaction)

    @app_commands.command(name="profile", description="Xem thông tin chi tiết của bạn hoặc người khác.")
    @app_commands.describe(user="Người dùng bạn muốn xem (để trống nếu là bạn).")
    async def profile(self, interaction: discord.Interaction, user: discord.Member = None):
        """Displays a detailed profile for a user."""
        await interaction.response.defer(ephemeral=True)
        target_user = user or interaction.user
        await self.db.add_or_update_user(target_user)

        profile_data = await self.db.get_user_profile(target_user.id)

        if not profile_data:
            await interaction.followup.send(
                embed=create_error_embed("Không thể tìm thấy thông tin người dùng này.")
            )
            return

        embed = self._create_profile_embed(target_user, profile_data)
        await interaction.followup.send(embed=embed)

    def _create_profile_embed(self, user, data):
        """Helper function to create the profile embed."""
        created_at = datetime.fromisoformat(data['created_at'])

        embed = create_embed(
            title=f"Thông Tin Của {user.display_name}",
            description=f"ID: `{user.id}`",
            color=user.color
        )
        embed.set_thumbnail(url=user.display_avatar.url)

        embed.add_field(
            name="💰 Kinh Tế",
            value=(
                f"**Số dư:** {format_currency(data['balance'])}\n"
                f"**Tổng kiếm được:** {format_currency(data['total_earned'])}\n"
                f"**Tổng đã tiêu:** {format_currency(data['total_spent'])}"
            ),
            inline=True
        )

        last_claim_str = "Chưa điểm danh"
        if data['last_claim_date']:
            last_claim_date = datetime.fromisoformat(data['last_claim_date']).date()
            if last_claim_date == date.today():
                last_claim_str = f"Hôm nay (🔥 {data['streak']})"
            else:
                last_claim_str = f"{last_claim_date.strftime('%d/%m/%Y')} (🔥 {data['streak']})"

        embed.add_field(
            name="📅 Hoạt Động",
            value=(
                f"**Ngày tham gia:** <t:{int(created_at.timestamp())}:D>\n"
                f"**Lần cuối điểm danh:** {last_claim_str}"
            ),
            inline=True
        )
        return embed

async def setup(bot: commands.Bot):
    """Loads the Economy cog."""
    await bot.add_cog(Economy(bot))