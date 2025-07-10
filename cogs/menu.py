"""
Cog for handling the interactive help menu.
"""
import discord
from discord.ext import commands
from discord import app_commands

from config import Config
from utils.embed_utils import create_embed

class HelpView(discord.ui.View):
    """
    A view that contains the help select menu.
    Dynamically adds the admin option for the bot owner.
    """
    def __init__(self, is_owner: bool = False):
        super().__init__(timeout=180) # View times out after 3 minutes
        self.add_item(HelpSelect(is_owner=is_owner))

class HelpSelect(discord.ui.Select):
    """
    The select menu for navigating help categories.
    """
    def __init__(self, is_owner: bool = False):
        options=[
            discord.SelectOption(
                label="Trang Chủ", description="Quay về trang chính.", emoji="🏠"
            ),
            discord.SelectOption(
                label="Kinh Tế", description="Các lệnh về tiền tệ, thu nhập.", emoji="💰"
            ),
            discord.SelectOption(
                label="Cờ Bạc", description="Các trò chơi may rủi.", emoji="🎲"
            ),
            discord.SelectOption(
                label="Kiểm Duyệt", description="Các lệnh kiểm duyệt server.", emoji="🛡️"
            ),
            discord.SelectOption(
                label="Roblox", description="Các lệnh liên quan đến Roblox.", emoji="🚀"
            ),
            discord.SelectOption(
                label="Valorant", description="Các lệnh liên quan đến Valorant.", emoji="🔫"
            ),
        ]
        if is_owner:
            options.append(
                discord.SelectOption(
                    label="Quản Trị", description="Lệnh dành cho chủ sở hữu bot.", emoji="👑"
                )
            )

        super().__init__(
            placeholder="Chọn một danh mục để xem...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        """Handles the selection from the user."""
        await interaction.response.defer()

        selection = self.values[0]
        embed = None

        embed_map = {
            "Trang Chủ": self.get_main_embed(interaction.user.id == interaction.client.owner_id),
            "Kinh Tế": self.get_economy_embed(),
            "Cờ Bạc": self.get_gambling_embed(),
            "Kiểm Duyệt": self.get_moderation_embed(),
            "Roblox": self.get_roblox_embed(),
            "Valorant": self.get_valorant_embed(),
            "Quản Trị": self.get_admin_embed()
        }

        if interaction.user.id != interaction.client.owner_id and selection == "Quản Trị":
            await interaction.followup.send("Bạn không có quyền xem mục này.", ephemeral=True)
            return

        embed = embed_map.get(selection)

        if embed:
            await interaction.edit_original_response(embed=embed)

    def get_main_embed(self, is_owner: bool) -> discord.Embed:
        """Creates the main help embed."""
        embed = create_embed(
            title=f"👋 Chào mừng đến với {Config.BOT_NAME}!",
            description=(
                "Đây là bot kinh tế và giải trí cho server của bạn.\n"
                "Sử dụng menu bên dưới để khám phá các lệnh."
            )
        )

        value_lines = [
            f"💰 **Kinh Tế**: Kiếm {Config.CURRENCY_NAME}, điểm danh, và leo top.",
            "🎲 **Cờ Bạc**: Thử vận may với các trò chơi cờ bạc.",
            "🛡️ **Kiểm Duyệt**: Các lệnh kick, ban, xóa tin nhắn và quản lý server.",
            "🚀 **Roblox**: Các lệnh liên quan đến Roblox.",
            "🔫 **Valorant**: Các lệnh random agent, map và quản lý session."
        ]
        if is_owner:
            value_lines.append("👑 **Quản Trị**: Các lệnh quản lý bot dành cho admin.")

        embed.add_field(
            name="Danh Mục Lệnh",
            value="\n".join(value_lines),
            inline=False
        )
        return embed

    def get_economy_embed(self) -> discord.Embed:
        """Creates the embed for the Economy category."""
        embed = create_embed(
            title="💰 Trợ Giúp - Lệnh Kinh Tế 💰",
            description="Các lệnh dùng để kiếm và quản lý tài sản của bạn."
        )
        embed.add_field(
            name="`/daily`",
            value=f"Nhận phần thưởng {Config.CURRENCY_NAME} hàng ngày. Duy trì chuỗi!",
            inline=False
        )
        embed.add_field(name="`/balance`", value="Kiểm tra số dư hiện tại của bạn.", inline=False)
        embed.add_field(name="`/profile`", value="Xem hồ sơ chi tiết của bạn.", inline=False)
        embed.add_field(
            name="`/leaderboard`",
            value="Xem bảng xếp hạng những người giàu nhất server.",
            inline=False
        )
        return embed

    def get_gambling_embed(self) -> discord.Embed:
        """Creates the embed for the Gambling category."""
        embed = create_embed(
            title="🎲 Trợ Giúp - Lệnh Cờ Bạc 🎲",
            description="Dùng tiền của bạn để thử vận may và kiếm nhiều hơn!"
        )
        embed.add_field(
            name="`/crash bet`",
            value="Game đối kháng đỉnh cao! Đặt cược và cashout trước khi biểu đồ sụp đổ.",
            inline=False
        )
        embed.add_field(name="`/slots bet`", value="Thử vận may với máy kéo.", inline=False)
        embed.add_field(name="`/blackjack bet`", value="Chơi Blackjack với nhà cái.", inline=False)
        embed.add_field(
            name="`/coinflip amount side`",
            value="Chơi tung đồng xu với người khác hoặc với bot.",
            inline=False
        )
        return embed

    def get_admin_embed(self) -> discord.Embed:
        """Creates the embed for the Admin category."""
        embed = create_embed(
            title="👑 Trợ Giúp - Lệnh Chủ Sở Hữu 👑",
            description="Các lệnh chỉ dành cho chủ sở hữu bot."
        )
        embed.add_field(
            name="`/broadcast ...`",
            value="Gửi một thông báo tới các kênh được chỉ định.",
            inline=False
        )
        embed.add_field(
            name="Lệnh quản lý kinh tế",
            value=(
                "`/eco_admin add`: Thêm tiền.\n"
                "`/eco_admin remove`: Trừ tiền.\n"
                "`/eco_admin set`: Đặt lại số dư."
            ),
            inline=False
        )
        embed.add_field(
            name="Quản lý Kênh Thông Báo (Admin)",
            value=(
                "`/stock add_channel`: Thêm kênh nhận thông báo.\n"
                "`/stock remove_channel`: Xóa kênh khỏi danh sách.\n"
                "`/stock list_channels`: Liệt kê các kênh."
            ),
            inline=False
        )
        embed.add_field(
            name="Quản lý Ping (Admin)",
            value="`/set_stock_ping`: Chọn một vai trò để bot ping khi có stock mới.",
            inline=False
        )
        embed.add_field(
            name="Xem thông tin",
            value="`/weather`: Xem lịch sử các sự kiện thời tiết gần đây trong game.",
            inline=False
        )
        return embed

    def get_moderation_embed(self) -> discord.Embed:
        """Creates the embed for the Moderation category."""
        embed = create_embed(
            title="🛡️ Trợ Giúp - Lệnh Kiểm Duyệt 🛡️",
            description="Các lệnh dùng để quản lý trật tự trong server."
        )
        embed.add_field(
            name="`/mod clear [amount]`",
            value="Xóa một số lượng tin nhắn trong kênh hiện tại (tối đa 100).",
            inline=False
        )
        embed.add_field(
            name="`/mod kick [member] [reason]`",
            value="Kick một thành viên khỏi server.",
            inline=False
        )
        embed.add_field(
            name="`/mod ban [member] [reason]`",
            value="Ban một thành viên khỏi server.",
            inline=False
        )
        embed.add_field(
            name="`/modlog set_channel [channel]`",
            value="[Admin] Thiết lập kênh để ghi lại các hành động kiểm duyệt.",
            inline=False
        )
        embed.add_field(
            name="Lệnh quản lý vai trò (Admin)",
            value=(
                "`/mod add_role`: Thêm vai trò cho thành viên.\n"
                "`/mod remove_role`: Xóa vai trò của thành viên."
            ),
            inline=False
        )
        return embed

    def get_roblox_embed(self) -> discord.Embed:
        """Creates the embed for the Roblox category."""
        embed = create_embed(
            title="🚀 Trợ Giúp - Lệnh Roblox 🚀",
            description=(
                "Các lệnh tương tác với Roblox.\n"
                "Lưu ý: `/stock` yêu cầu quyền Admin để cài đặt."
            )
        )
        embed.add_field(
            name="Quản lý Stock",
            value=(
                "`/stock add_channel`: Đặt kênh nhận thông báo.\n"
                "`/stock remove_channel`: Xóa kênh nhận thông báo.\n"
                "`/stock list_channels`: Xem các kênh đã đặt.\n"
                "`/set_stock_ping`: Đặt vai trò để ping."
            ),
            inline=False
        )
        embed.add_field(
            name="Xem thông tin",
            value="`/weather`: Xem lịch sử các sự kiện thời tiết gần đây trong game.",
            inline=False
        )
        return embed

    def get_valorant_embed(self) -> discord.Embed:
        """Creates the embed for the Valorant category."""
        embed = create_embed(
            title="🔫 Trợ Giúp - Lệnh Valorant 🔫",
            description="Các lệnh dùng để random trong Valorant hoặc quản lý session custom."
        )
        embed.add_field(
            name="Random Agent & Team",
            value=(
                "`/random duelist`: Random một agent Duelist.\n"
                "`/random initiator`: Random một agent Initiator.\n"
                "`/random controller`: Random một agent Controller.\n"
                "`/random sentinel`: Random một agent Sentinel.\n"
                "`/random team`: Random một đội hình 5 người hoàn chỉnh."
            ),
            inline=False
        )
        embed.add_field(
            name="Quản lý Session Custom",
            value=(
                "`/random session start`: Bắt đầu một phòng chờ mới.\n"
                "`/random session join`: Tham gia phòng chờ hiện tại.\n"
                "`/random session cancel`: Hủy phòng chờ (chỉ host).\n"
                "`/random session status`: Xem trạng thái phòng chờ."
            ),
            inline=False
        )
        return embed

class Menu(commands.Cog):
    """
    Cog that handles the /help command and its interactive menu.
    """
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="help", description="Hiển thị menu trợ giúp với tất cả các lệnh.")
    async def help(self, interaction: discord.Interaction):
        """Displays the interactive help menu."""
        is_owner = await self.bot.is_owner(interaction.user)
        view = HelpView(is_owner=is_owner)

        select_menu: HelpSelect = view.children[0]
        initial_embed = select_menu.get_main_embed(is_owner)
        await interaction.response.send_message(
            embed=initial_embed, view=view, ephemeral=True
        )

async def setup(bot: commands.Bot):
    """Loads the Menu cog."""
    await bot.add_cog(Menu(bot))