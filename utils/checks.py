"""Custom decorators for application command checks."""

from discord import app_commands, Interaction
from config import Config

def is_admin():
    """Check if the user is a bot admin."""
    def predicate(interaction: Interaction) -> bool:
        return interaction.user.id in Config.ADMIN_USERS
    return app_commands.check(predicate)

def is_deputy_admin():
    """Check if the user is a deputy admin (has a specific role)."""
    async def predicate(interaction: Interaction) -> bool:
        if interaction.user.id in Config.ADMIN_USERS:
            return True
        if not interaction.guild or not hasattr(interaction.user, 'roles'):
            return False
        
        deputy_roles = set(Config.DEPUTY_ADMIN_ROLES)
        user_roles = {role.id for role in interaction.user.roles}
        
        return not deputy_roles.isdisjoint(user_roles)
    return app_commands.check(predicate)

def is_not_in_game():
    """Check if the user is currently in a game session."""
    async def predicate(interaction: Interaction) -> bool:
        # The bot instance is attached to the interaction.
        if interaction.client.active_game_sessions is None:
            return True # Should not happen, but as a safeguard.
        return interaction.user.id not in interaction.client.active_game_sessions
    return app_commands.check(predicate) 