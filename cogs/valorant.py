"""
Cog for Valorant-related commands like agent/map randomization and custom game sessions.
"""
import logging
import random
from typing import Dict, List, Optional

import discord
from discord import app_commands
from discord.ext import commands

from utils.embed_utils import create_embed, create_error_embed

logger = logging.getLogger(__name__)

# --- Constants ---
AGENTS: Dict[str, List[str]] = {
    "duelist": ["Jett", "Reyna", "Phoenix", "Raze", "Yoru", "Neon", "Iso"],
    "initiator": ["Sova", "Breach", "Skye", "KAY/O", "Fade", "Gekko"],
    "controller": ["Brimstone", "Viper", "Omen", "Astra", "Harbor", "Clove"],
    "sentinel": ["Sage", "Cypher", "Killjoy", "Chamber", "Deadlock"],
}

ROLE_EMOJIS: Dict[str, str] = {
    "duelist": "⚔️", "initiator": "🎯", "controller": "💨", "sentinel": "🛡️",
}

MAP_POOL: List[str] = ["Ascent", "Bind", "Icebox", "Lotus", "Sunset", "Haven", "Abyss"]


class ValorantSessionManager:
    """Manages the state of a single custom game session for a guild."""

    def __init__(self):
        self.is_active: bool = False
        self.host: Optional[discord.Member] = None
        self.players: List[discord.Member] = []
        self.message: Optional[discord.Message] = None

    def start(self, host: discord.Member, message: discord.Message):
        """Starts a new session."""
        self.is_active = True
        self.host = host
        self.players = [host]
        self.message = message

    def add_player(self, player: discord.Member) -> bool:
        """Adds a player to the session if not full."""
        if len(self.players) >= 10 or player in self.players:
            return False
        self.players.append(player)
        return True

    def remove_player(self, player: discord.Member) -> bool:
        """Removes a player from the session."""
        if player in self.players:
            self.players.remove(player)
            return True
        return False

    def reset(self):
        """Resets the session to its initial state."""
        self.is_active = False
        self.host = None
        self.players.clear()
        self.message = None

    def create_lobby_embed(self) -> discord.Embed:
        """Creates the embed for the session lobby."""
        embed = create_embed(
            title="<:valorant:1248556094254354522> Phòng Chờ Custom Valorant",
            description=(
                f"**Phòng chờ được tạo bởi {self.host.mention}**\n\n"
                "Nhấn nút bên dưới để tham gia!"
            ),
            color=discord.Color.red()
        )

        player_list = "\n".join(
            [f"• {player.mention}" for player in self.players]
        )
        embed.add_field(name=f"Người Chơi ({len(self.players)}/10)", value=player_list or "Chưa có ai tham gia.", inline=False)
        return embed

    def randomize_teams(self) -> discord.Embed:
        """Randomizes teams and returns a results embed."""
        if not self.players:
            return create_error_embed("Không có người chơi nào để bắt đầu.")

        random.shuffle(self.players)
        mid_point = len(self.players) // 2
        team_a = self.players[:mid_point]
        team_b = self.players[mid_point:]

        embed = create_embed(
            title="🎉 Đội hình Custom đã sẵn sàng! 🎉",
            description="Các người chơi đã được chia ngẫu nhiên. GLHF!",
            color=discord.Color.green()
        )

        if team_a:
            embed.add_field(name="**Team A**", value="\n".join(p.mention for p in team_a), inline=True)
        if team_b:
            embed.add_field(name="**Team B**", value="\n".join(p.mention for p in team_b), inline=True)

        return embed

    def get_teams_embed(self, team_a, team_b):
        """Creates an embed displaying the final teams."""
        embed = create_embed(
            title="<:valorant:1248556094254354522> Chia Đội Valorant Thành Công",
            description="Các người chơi đã được chia thành 2 đội!",
            color=discord.Color.green()
        )
        embed.add_field(name="**Team A**", value="\n".join(p.mention for p in team_a), inline=True)
        embed.set_footer(text="GLHF!")
        embed.add_field(name="**Team B**", value="\n".join(p.mention for p in team_b), inline=True)
        return embed


class ValorantSessionView(discord.ui.View):
    """The view containing buttons to interact with a Valorant session."""

    def __init__(self, manager: ValorantSessionManager):
        super().__init__(timeout=3600)  # 1 hour
        self.manager = manager
        self.update_buttons()

    def update_buttons(self):
        """Updates the state of the buttons based on the session state."""
        join_button = discord.utils.get(self.children, custom_id="valorant_join")
        if join_button:
            join_button.disabled = len(self.manager.players) >= 10

    async def _update_view(self, interaction: discord.Interaction, message: str, is_public: bool=False):
        """Helper to update the lobby message and send a response."""
        self.update_buttons()
        embed = self.manager.create_lobby_embed()
        if self.manager.message:
            await self.manager.message.edit(embed=embed, view=self)
        await interaction.response.send_message(message, ephemeral=not is_public)

    @discord.ui.button(label="Tham gia", style=discord.ButtonStyle.green, emoji="✅", custom_id="valorant_join")
    async def join(self, interaction: discord.Interaction, _: discord.ui.Button):
        """Handles a user joining the session."""
        if self.manager.add_player(interaction.user):
            await self._update_view(interaction, "Bạn đã tham gia thành công!")
        else:
            await interaction.response.send_message(
                "Bạn đã tham gia rồi hoặc phòng đã đầy.", ephemeral=True
            )

    @discord.ui.button(label="Rời khỏi", style=discord.ButtonStyle.gray, emoji="👋", custom_id="valorant_leave")
    async def leave(self, interaction: discord.Interaction, _: discord.ui.Button):
        """Handles a user leaving the session."""
        if interaction.user == self.manager.host and len(self.manager.players) > 1:
            await interaction.response.send_message(
                "Host không thể rời, chỉ có thể hủy phòng.", ephemeral=True
            )
            return

        if self.manager.remove_player(interaction.user):
            await self._update_view(interaction, "Bạn đã rời khỏi phòng chờ.")
        else:
            await interaction.response.send_message("Bạn không có trong phòng chờ.", ephemeral=True)

    @discord.ui.button(label="Bắt đầu", style=discord.ButtonStyle.primary, emoji="▶️", custom_id="valorant_start")
    async def start_now(self, interaction: discord.Interaction, _: discord.ui.Button):
        """Handles the host starting the game."""
        if interaction.user != self.manager.host:
            await interaction.response.send_message("Chỉ host mới có thể bắt đầu.", ephemeral=True)
            return

        result_embed = self.manager.randomize_teams()
        if self.manager.message:
            await self.manager.message.edit(embed=result_embed, view=None)
        self.manager.reset()
        self.stop()

    @discord.ui.button(label="Hủy bỏ", style=discord.ButtonStyle.danger, emoji="✖️", custom_id="valorant_cancel")
    async def cancel(self, interaction: discord.Interaction, _: discord.ui.Button):
        """Handles the host canceling the session."""
        if interaction.user != self.manager.host:
            await interaction.response.send_message("Chỉ host mới có thể hủy phòng.", ephemeral=True)
            return

        embed = self.manager.create_lobby_embed()
        embed.title = "🚫 Phiên đã bị hủy 🚫"
        embed.description = f"Phiên đã được hủy bởi host {self.manager.host.mention}."
        if self.manager.message:
            await self.manager.message.edit(embed=embed, view=None)
        self.manager.reset()
        self.stop()


class ValorantCog(commands.Cog, name="Valorant"):
    """Provides Valorant-related commands."""

    random_group = app_commands.Group(name="random", description="Random một agent hoặc một đội hình Valorant.")
    session_group = app_commands.Group(
        name="session", parent=random_group, description="Quản lý một phiên random custom game."
    )

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.session_managers: Dict[int, ValorantSessionManager] = {}

    def _get_manager(self, guild_id: int) -> ValorantSessionManager:
        """Gets the session manager for a guild, creating it if it doesn't exist."""
        if guild_id not in self.session_managers:
            self.session_managers[guild_id] = ValorantSessionManager()
        return self.session_managers[guild_id]

    async def _random_agent(self, interaction: discord.Interaction, role: str):
        """Helper to send a random agent of a specific role."""
        agent = random.choice(AGENTS[role])
        embed = create_embed(
            title=f"{ROLE_EMOJIS[role]} Agent ngẫu nhiên",
            description=f"Agent của bạn là: **{agent}**",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed)

    @random_group.command(name="duelist", description="Random một agent thuộc role Duelist.")
    async def random_duelist(self, interaction: discord.Interaction):
        """Sends a random duelist agent."""
        await self._random_agent(interaction, "duelist")

    @random_group.command(name="initiator", description="Random một agent thuộc role Initiator.")
    async def random_initiator(self, interaction: discord.Interaction):
        """Sends a random initiator agent."""
        await self._random_agent(interaction, "initiator")

    @random_group.command(name="controller", description="Random một agent thuộc role Controller.")
    async def random_controller(self, interaction: discord.Interaction):
        """Sends a random controller agent."""
        await self._random_agent(interaction, "controller")

    @random_group.command(name="sentinel", description="Random một agent thuộc role Sentinel.")
    async def random_sentinel(self, interaction: discord.Interaction):
        """Sends a random sentinel agent."""
        await self._random_agent(interaction, "sentinel")

    @random_group.command(name="team", description="Random một đội hình 5 người theo meta.")
    async def random_team(self, interaction: discord.Interaction):
        """Generates a random 5-person team composition."""
        try:
            team = {
                "duelist": random.sample(AGENTS["duelist"], 2),
                "initiator": random.sample(AGENTS["initiator"], 1),
                "controller": random.sample(AGENTS["controller"], 1),
                "sentinel": random.sample(AGENTS["sentinel"], 1),
            }
            embed = create_embed(
                title="👊 Đội hình Valorant ngẫu nhiên",
                description="Đây là một đội hình được gợi ý theo meta hiện tại.",
                color=discord.Color.red()
            )
            for role, agents in team.items():
                embed.add_field(
                    name=f"{ROLE_EMOJIS[role]} {role.title()}",
                    value="\n".join(agents)
                )
            await interaction.response.send_message(embed=embed)
        except ValueError:
            await interaction.response.send_message(
                embed=create_error_embed("Không đủ agent trong một vai trò để tạo đội hình.")
            )

    @random_group.command(name="map", description="Random một hoặc nhiều map từ map pool.")
    @app_commands.describe(
        count="Số lượng map muốn random (mặc định là 1).",
        exclude="Các map muốn loại trừ, cách nhau bằng dấu phẩy (vd: Bind,Haven)."
    )
    async def random_map(
        self,
        interaction: discord.Interaction,
        count: app_commands.Range[int, 1, len(MAP_POOL)] = 1,
        exclude: Optional[str] = None
    ):
        """Picks one or more random maps from the competitive pool."""
        available_maps = list(MAP_POOL)
        excluded_maps = []
        if exclude:
            excluded_names = {name.strip().lower() for name in exclude.split(',')}
            # Normalize map names for comparison
            available_maps = [
                map_name for map_name in MAP_POOL if map_name.lower() not in excluded_names
            ]
            excluded_maps = [
                map_name for map_name in MAP_POOL if map_name.lower() in excluded_names
            ]

        if count > len(available_maps):
            return await interaction.response.send_message(
                embed=create_error_embed(
                    "Không thể random vì số lượng map yêu cầu lớn hơn số map có sẵn."
                ),
                ephemeral=True,
            )

        picked_maps = random.sample(available_maps, k=count)
        map_list_str = "\n".join([f"🗺️ **{m}**" for m in picked_maps])
        description = f"Map ngẫu nhiên của bạn là:\n{map_list_str}"

        if excluded_maps:
            description += f"\n\n*Đã loại trừ: {', '.join(excluded_maps)}*"

        embed = create_embed(
            title=f"🗺️ Map Ngẫu Nhiên ({count})",
            description=description,
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed)


    @session_group.command(name="start", description="Bắt đầu một phiên random custom game mới.")
    async def session_start(self, interaction: discord.Interaction):
        """Starts a new custom game session."""
        manager = self._get_manager(interaction.guild_id)
        if manager.is_active:
            await interaction.response.send_message(
                embed=create_error_embed("Đã có một phiên đang hoạt động trong server này."),
                ephemeral=True
            )
            return

        # Send initial message
        await interaction.response.send_message("Đang tạo phòng chờ...", ephemeral=True)
        original_response = await interaction.original_response()

        manager.start(interaction.user, original_response)
        view = ValorantSessionView(manager)
        embed = manager.create_lobby_embed()
        await original_response.edit(content=None, embed=embed, view=view)


    @session_group.command(name="status", description="Xem lại phòng chờ hiện tại.")
    async def session_status(self, interaction: discord.Interaction):
        """Resends the current session lobby message."""
        manager = self._get_manager(interaction.guild_id)
        if not manager.is_active or not manager.message:
            await interaction.response.send_message(
                embed=create_error_embed("Không có phiên nào đang hoạt động."),
                ephemeral=True
            )
            return

        view = ValorantSessionView(manager)
        embed = manager.create_lobby_embed()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def setup(bot: commands.Bot):
    """Loads the Valorant cog."""
    await bot.add_cog(ValorantCog(bot))
