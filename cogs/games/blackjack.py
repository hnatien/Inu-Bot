"""
Cog for a full Blackjack game against the house.
"""
import logging
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from config import Config
from utils.embed_utils import create_embed, create_error_embed, format_currency
from utils.game_utils import Deck, Hand

logger = logging.getLogger(__name__)


class BlackjackView(discord.ui.View):
    """Manages the UI for a Blackjack game, including Hit, Stand, and Double Down."""

    def __init__(self, game, can_double_down: bool):
        super().__init__(timeout=120)  # Game ends after 2 minutes of inactivity
        self.game = game

        # Explicitly define buttons to be modified later
        self.hit_button = discord.ui.Button(label="Hit", style=discord.ButtonStyle.green)
        self.stand_button = discord.ui.Button(label="Stand", style=discord.ButtonStyle.red)
        self.double_button = discord.ui.Button(
            label="Double", style=discord.ButtonStyle.blurple, disabled=not can_double_down
        )

        self.hit_button.callback = self.hit_callback
        self.stand_button.callback = self.stand_callback
        self.double_button.callback = self.double_callback

        self.add_item(self.hit_button)
        self.add_item(self.stand_button)
        self.add_item(self.double_button)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensures only the player who started the game can interact."""
        if interaction.user.id == self.game.player.id:
            return True
        await interaction.response.send_message(
            "Đây không phải là ván bài của bạn!", ephemeral=True
        )
        return False

    async def on_timeout(self):
        """Ends the game with a loss if the player is inactive."""
        if not self.game.game_over:
            await self.game.end_game("loss", "Bạn đã thua do không hoạt động.", is_timeout=True)

    def disable_all(self, *, double_only: bool = False):
        """Disables buttons, typically at the end of a turn or game."""
        if not double_only:
            self.hit_button.disabled = True
            self.stand_button.disabled = True
        self.double_button.disabled = True
        self.stop()

    async def hit_callback(self, interaction: discord.Interaction):
        """Callback for the 'Hit' button."""
        await interaction.response.defer()
        self.disable_all(double_only=True)
        await self.game.hit()

    async def stand_callback(self, interaction: discord.Interaction):
        """Callback for the 'Stand' button."""
        await interaction.response.defer()
        self.disable_all()
        await self.game.stand()

    async def double_callback(self, interaction: discord.Interaction):
        """Callback for the 'Double Down' button."""
        await interaction.response.defer()
        self.disable_all()
        await self.game.double_down()


class BlackjackGame:
    """Contains the logic for a single game of Blackjack."""

    def __init__(self, bot: commands.Bot, interaction: discord.Interaction, bet: int):
        self.bot = bot
        self.interaction = interaction
        self.player = interaction.user
        self.bet = bet
        self.deck = Deck(num_decks=4)
        self.player_hand = Hand()
        self.dealer_hand = Hand()
        self.game_over = False
        self.view: Optional[BlackjackView] = None

    async def start(self):
        """Starts the Blackjack game, deals initial cards, and sets up the view."""
        balance = await self.bot.db.get_user_balance(self.player.id)
        can_double = balance >= self.bet  # Can they afford to double their bet?

        self.player_hand.add_card(self.deck.deal())
        self.dealer_hand.add_card(self.deck.deal())
        self.player_hand.add_card(self.deck.deal())
        self.dealer_hand.add_card(self.deck.deal())

        self.view = BlackjackView(self, can_double)
        embed = self._create_game_embed("Đến lượt bạn. Hit, Stand, hay Double?")

        await self.interaction.followup.send(embed=embed, view=self.view)

        # Check for immediate Blackjack
        if self.player_hand.value == 21:
            await self.stand(blackjack=True)

    def _create_game_embed(self, status_text: str) -> discord.Embed:
        """Builds the embed to display the current game state."""
        embed = create_embed(title="♦️ Blackjack ♣️", description=status_text)
        embed.add_field(
            name=f"{self.player.display_name} ({self.player_hand.value})",
            value=f"`{self.player_hand}`", inline=True
        )
        dealer_cards = f"`{self.dealer_hand.cards[0]}` `🎴`"
        dealer_value = self.dealer_hand.cards[0].value
        if self.game_over:
            dealer_cards = f"`{self.dealer_hand}`"
            dealer_value = self.dealer_hand.value
        embed.add_field(name=f"Nhà Cái ({dealer_value})", value=dealer_cards, inline=True)
        embed.set_footer(text=f"Tiền cược: {format_currency(self.bet)}")
        return embed

    async def hit(self):
        """Player chooses to take another card."""
        self.player_hand.add_card(self.deck.deal())
        if self.player_hand.value >= 21:
            await self.stand()
        else:
            embed = self._create_game_embed("Đến lượt bạn. Hit hay Stand?")
            await self.interaction.edit_original_response(embed=embed, view=self.view)

    async def double_down(self):
        """Player chooses to double their bet and take one final card."""
        transaction_successful = await self.bot.db.update_balance(self.player.id, -self.bet)
        if not transaction_successful:
            # This is a fallback; the button should be disabled if they can't afford it.
            await self.interaction.followup.send(
                "Bạn không đủ tiền để Double Down!", ephemeral=True
            )
            # Re-enable buttons if the double fails
            self.view.disable_all(double_only=True)
            self.view.hit_button.disabled = False
            self.view.stand_button.disabled = False
            await self.interaction.edit_original_response(view=self.view)
            return

        self.bet *= 2
        self.player_hand.add_card(self.deck.deal())
        await self.stand()

    async def stand(self, blackjack: bool = False):
        """Player stands, triggering the dealer's turn and game resolution."""
        # Dealer's turn
        while self.dealer_hand.value < 17:
            self.dealer_hand.add_card(self.deck.deal())

        player_score = self.player_hand.value
        dealer_score = self.dealer_hand.value

        if blackjack:
            await self.end_game("blackjack", "Blackjack!")
        elif player_score > 21:
            await self.end_game("loss", "Bust! Bạn thua.")
        elif dealer_score > 21 or player_score > dealer_score:
            await self.end_game("win", "Bạn thắng!")
        elif player_score < dealer_score:
            await self.end_game("loss", "Nhà cái thắng!")
        else:
            await self.end_game("push", "Hòa (Push)!")

    async def end_game(self, outcome: str, result_text: str, is_timeout: bool = False):
        """Ends the game, calculates payout, updates DB, and edits the message."""
        self.game_over = True
        if self.view:
            self.view.disable_all()

        payout_map = {
            "win": self.bet * 2,
            "loss": 0,
            "blackjack": self.bet + int(self.bet * 1.5),
            "push": self.bet,
        }
        color_map = {
            "win": Config.COLOR_SUCCESS,
            "loss": Config.COLOR_ERROR,
            "blackjack": 0xFFD700,
            "push": Config.COLOR_INFO,
        }

        payout = payout_map.get(outcome, 0)
        color = color_map.get(outcome, Config.COLOR_PRIMARY)

        if payout > 0:
            await self.bot.db.update_balance(self.player.id, payout)

        await self.bot.db.update_blackjack_stats(self.player.id, outcome, self.bet)

        status_lines = [f"**{result_text}**"]
        if payout > self.bet:
            status_lines.append(f"Bạn thắng **{format_currency(payout - self.bet)}**!")
        elif outcome == "loss":
            status_lines.append(f"Bạn thua **{format_currency(self.bet)}**.")

        if new_balance := await self.bot.db.get_user_balance(self.player.id):
            status_lines.append(f"💰 Số dư mới: **{format_currency(new_balance)}**")

        embed = self._create_game_embed("\n".join(status_lines))
        embed.color = color

        try:
            if is_timeout:
                await self.interaction.channel.send(
                    content=f"{self.player.mention}, ván bài đã hết hạn!", embed=embed
                )
                await self.interaction.edit_original_response(view=self.view)
            else:
                await self.interaction.edit_original_response(embed=embed, view=self.view)
        except (discord.NotFound, discord.Forbidden) as e:
            logger.warning(
                "Blackjack: Could not edit original message %s to show result: %s",
                self.interaction.message.id if self.interaction.message else 'N/A', e
            )


class BlackjackCog(commands.Cog, name="Blackjack"):
    """Commands for playing Blackjack."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="blackjack", description="Cược Inu Coin để chơi một ván Blackjack.")
    @app_commands.describe(bet="Số tiền bạn muốn cược.")
    @app_commands.checks.cooldown(1, 15.0, key=lambda i: i.user.id)
    async def blackjack(
        self, interaction: discord.Interaction, bet: app_commands.Range[int, Config.MIN_BET, Config.MAX_BET]
    ):
        """Starts a game of blackjack."""
        transaction_successful = await self.bot.db.update_balance(interaction.user.id, -bet)
        if not transaction_successful:
            await interaction.response.send_message(
                embed=create_error_embed("Bạn không đủ tiền để đặt cược."), ephemeral=True
            )
            return

        await interaction.response.defer()

        game = BlackjackGame(self.bot, interaction, bet)
        await game.start()

    @blackjack.error
    async def blackjack_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Handles errors for the blackjack command."""
        if isinstance(error, app_commands.CommandOnCooldown):
            await interaction.response.send_message(
                embed=create_error_embed(f"Bạn phải chờ **{error.retry_after:.1f}s** nữa."),
                ephemeral=True
            )
        else:
            logger.error("An unexpected error occurred in blackjack command: %s", error, exc_info=True)
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    embed=create_error_embed("Đã có lỗi xảy ra."), ephemeral=True
                )


async def setup(bot: commands.Bot):
    """Loads the BlackjackCog."""
    await bot.add_cog(BlackjackCog(bot))