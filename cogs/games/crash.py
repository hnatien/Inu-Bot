"""
A cog for a graphical and interactive Crash game.
"""
import asyncio
import logging
import random
import time
from io import BytesIO

import discord
from discord import app_commands
from discord.ext import commands

from config import Config
from utils.embed_utils import create_embed, create_error_embed, format_currency
from utils.easing import ease_in_cubic
from utils.graph_utils import generate_graph_image

logger = logging.getLogger(__name__)

# --- Game Constants ---
BETTING_TIME = 15  # seconds
MIN_MULTIPLIER = 1.0
MAX_PLAYERS = 20

# --- Views ---
class CrashJoinView(discord.ui.View):
    """View for the initial betting phase, allowing users to join."""

    def __init__(self, game):
        super().__init__(timeout=BETTING_TIME)
        self.game = game

    async def on_timeout(self):
        """Locks bets when the view times out."""
        await self.game.lock_bets()

    @discord.ui.button(label="Join Game", style=discord.ButtonStyle.green)
    async def join_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        """Button to join the game."""
        await interaction.response.send_modal(CrashBetModal(self.game))


class CrashBetModal(discord.ui.Modal, title="Place Your Bet"):
    """Modal for the user to enter their bet amount."""

    bet_amount = discord.ui.TextInput(
        label=f"Bet Amount ({Config.CURRENCY_SYMBOL})",
        placeholder=f"Enter a number between {Config.MIN_BET} and {Config.MAX_BET}",
        min_length=len(str(Config.MIN_BET)),
        max_length=len(str(Config.MAX_BET))
    )

    def __init__(self, game):
        super().__init__(timeout=120)
        self.game = game

    async def on_submit(self, interaction: discord.Interaction):
        """Handles the submission of the bet modal."""
        try:
            amount = int(self.bet_amount.value)
            if not Config.MIN_BET <= amount <= Config.MAX_BET:
                raise ValueError
        except (ValueError, TypeError):
            return await interaction.response.send_message(
                embed=create_error_embed(f"Invalid bet amount. Please enter a number between {Config.MIN_BET} and {Config.MAX_BET}."),
                ephemeral=True
            )

        await interaction.response.defer(ephemeral=True)
        await self.game.add_player(interaction, amount)


class CrashGameView(discord.ui.View):
    """View for the active game phase, allowing users to cash out."""

    def __init__(self, game):
        super().__init__(timeout=300)
        self.game = game

    @discord.ui.button(label="Cash Out!", style=discord.ButtonStyle.blurple, emoji="💰")
    async def cashout_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        """Button to cash out of the game."""
        await self.game.cashout_player(interaction)


# --- Main Game Logic ---
class CrashGameInstance:
    """Represents and manages a single game of Crash."""

    def __init__(self, bot, interaction: discord.Interaction):
        self.bot = bot
        self.interaction = interaction
        self.players = {}  # {user_id: {"bet": int, "user": Member, "cashout_at": float | None}}
        self.message: discord.WebhookMessage = None
        self.crashed_at = self._get_crash_point()
        self.current_multiplier = 1.0
        self.is_betting_open = True
        self.is_running = False

    async def start(self):
        """Starts the betting phase of the game."""
        embed = create_embed(
            "🚀 Crash Game Starting!",
            f"Bets are open for **{BETTING_TIME} seconds**! Press 'Join Game' to place your bet.",
            color=discord.Color.blurple()
        )
        embed.add_field(name="Min Bet", value=format_currency(Config.MIN_BET))
        embed.add_field(name="Max Bet", value=format_currency(Config.MAX_BET))
        embed.set_footer(text="The game will begin automatically after the betting phase.")

        await self.interaction.response.send_message(embed=embed, view=CrashJoinView(self))
        self.message = await self.interaction.original_response()

    async def lock_bets(self):
        """Ends the betting phase and starts the game if there are players."""
        self.is_betting_open = False
        if not self.players:
            embed = create_embed("Game Cancelled", "No one joined the game.", color=discord.Color.orange())
            await self.interaction.edit_original_response(embed=embed, view=None)
            return

        await self.run_game()

    async def add_player(self, interaction: discord.Interaction, bet: int):
        """Adds a player to the game."""
        user = interaction.user
        if not self.is_betting_open:
            return await interaction.followup.send("The betting phase is over.", ephemeral=True)
        if user.id in self.players:
            return await interaction.followup.send("You have already joined.", ephemeral=True)
        if len(self.players) >= MAX_PLAYERS:
            return await interaction.followup.send("The game is full.", ephemeral=True)

        if not await self.bot.db.update_balance(user.id, -bet):
            return await interaction.followup.send(embed=create_error_embed("You don't have enough funds for that bet."), ephemeral=True)

        self.players[user.id] = {"bet": bet, "user": user, "cashout_at": None}
        await interaction.followup.send(f"You have joined the game with a bet of **{format_currency(bet)}**!", ephemeral=True)
        await self._update_player_list_embed()

    async def cashout_player(self, interaction: discord.Interaction):
        """Attempts to cash out a player."""
        user = interaction.user
        if not self.is_running or user.id not in self.players:
            return await interaction.response.send_message("You are not in an active game.", ephemeral=True)
        if self.players[user.id]["cashout_at"] is not None:
            return await interaction.response.send_message("You have already cashed out.", ephemeral=True)

        self.players[user.id]["cashout_at"] = self.current_multiplier
        winnings = self.players[user.id]["bet"] * self.current_multiplier
        await self.bot.db.update_balance(user.id, winnings)
        await interaction.response.send_message(
            f"You cashed out at **{self.current_multiplier:.2f}x** and won **{format_currency(winnings)}**!", ephemeral=True
        )

    async def _update_player_list_embed(self):
        """Updates the main game embed to show the current list of players."""
        if not self.message:
            return
        
        original_embed = self.message.embeds[0]
        original_embed.clear_fields()
        original_embed.add_field(name="Min Bet", value=format_currency(Config.MIN_BET))
        original_embed.add_field(name="Max Bet", value=format_currency(Config.MAX_BET))

        player_list = "\n".join([
            f"• {p['user'].display_name} - {format_currency(p['bet'])}" for p in self.players.values()
        ])
        original_embed.add_field(name=f"Players ({len(self.players)}/{MAX_PLAYERS})", value=player_list or "No one yet!", inline=False)
        await self.message.edit(embed=original_embed)

    async def run_game(self):
        """Runs the main graphical loop of the game."""
        self.is_running = True
        graph_data = [1.0]
        start_time_loop = time.time()
        duration = 5  # Animation duration

        while self.current_multiplier < self.crashed_at:
            elapsed = time.time() - start_time_loop
            progress = min(elapsed / duration, 1.0)
            eased_progress = ease_in_cubic(progress)

            self.current_multiplier = 1 + (self.crashed_at - 1) * eased_progress
            self.current_multiplier = min(self.current_multiplier, self.crashed_at)
            graph_data.append(self.current_multiplier)
            
            # Reduce update frequency to avoid rate limits
            if len(graph_data) % 3 != 0 and self.current_multiplier < self.crashed_at:
                await asyncio.sleep(0.2)
                continue

            graph_image_bytes = generate_graph_image(graph_data, True)
            await self._update_game_embed(graph_image_bytes, in_progress=True)
            await asyncio.sleep(0.75)

        # Final update
        self.is_running = False
        final_graph_bytes = generate_graph_image(graph_data, False)
        await self._payout_losers()
        await self._update_game_embed(final_graph_bytes, in_progress=False)

    async def _update_game_embed(self, graph_bytes: BytesIO, in_progress: bool):
        """Updates the message with the current game state and graph."""
        if in_progress:
            title = f"Multiplier: {self.current_multiplier:.2f}x"
            description = "The rocket is climbing! Press 'Cash Out' to take your winnings."
            color = discord.Color.green()
        else:
            title = "🚀 CRASHED! 🚀"
            description = f"The rocket crashed at **{self.crashed_at:.2f}x**."
            color = discord.Color.red()

        embed = create_embed(title, description, color)
        file = discord.File(graph_bytes, filename="graph.png")
        embed.set_image(url="attachment://graph.png")
        
        payout_info = self._get_payout_info()
        if payout_info:
            embed.add_field(name="Player Status", value=payout_info, inline=False)

        view = CrashGameView(self) if in_progress else None
        if view and in_progress:
            # Disable cashout for players who have already cashed out
            pass # TODO

        await self.message.edit(embed=embed, view=view, attachments=[file])


    async def _payout_losers(self):
        """Handles post-game stats for players who did not cash out."""
        # No DB change needed, money was already deducted. This is for stats.
        pass

    def _get_payout_info(self) -> str:
        """Generates a string listing the status of all players."""
        lines = []
        for p_id, data in self.players.items():
            user = data['user']
            if data['cashout_at']:
                winnings = data['bet'] * data['cashout_at']
                lines.append(f"✅ {user.display_name}: Cashed out at {data['cashout_at']:.2f}x ({format_currency(winnings)})")
            elif not self.is_running:
                lines.append(f"❌ {user.display_name}: Lost {format_currency(data['bet'])}")
            else:
                 lines.append(f"IN-GAME: {user.display_name} - {format_currency(data['bet'])}")
        return "\n".join(lines)


    @staticmethod
    def _get_crash_point() -> float:
        """
        Generates a crash point using a distribution that favors lower multipliers.
        99% of multipliers will be below 100x. 1% chance of an "instant" crash at 1.00x.
        """
        if random.random() < 0.01:
            return 1.00
        # This formula creates a nice curve where high multipliers are rare.
        e = 2**32
        house_edge = 0.99 # 1% house edge means 99% is paid back ON AVERAGE.
        p = random.random()
        return (e * house_edge - p * e) / (e - p * e)


class Crash(commands.Cog):
    """Cog for the Crash game."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.active_games = {}  # guild_id: CrashGameInstance

    @app_commands.command(name="crash", description="Start a new game of Crash!")
    async def crash(self, interaction: discord.Interaction):
        """Starts a new game of Crash in the current channel."""
        guild_id = interaction.guild_id
        if self.active_games.get(guild_id) and (self.active_games[guild_id].is_running or self.active_games[guild_id].is_betting_open):
            return await interaction.response.send_message(
                "A game of Crash is already in progress in this server.", ephemeral=True
            )

        game = CrashGameInstance(self.bot, interaction)
        self.active_games[guild_id] = game
        await game.start()


async def setup(bot: commands.Bot):
    """Loads the Crash cog."""
    await bot.add_cog(Crash(bot)) 