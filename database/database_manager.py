"""
Database manager for the bot, handling all interactions with the SQLite database.
"""
import json
import logging
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Any

import aiosqlite

logger = logging.getLogger(__name__)

@dataclass
class GiveawayData:
    """Represents the data for a giveaway."""
    message_id: int
    channel_id: int
    guild_id: int
    prize: str
    end_time: datetime
    host_id: int

class DatabaseManager:
    """
    Manages all database operations for the bot.
    NOTE: This class has a large number of public methods and could be refactored
    into smaller, more domain-specific managers (e.g., EconomyManager, GiveawayManager).
    """
    def __init__(self, db_path):
        self.db_path = db_path
        self.conn: aiosqlite.Connection | None = None
        self.log = logging.getLogger(__name__)

    async def initialize(self):
        """Initializes the database connection and creates tables if they don't exist."""
        if self.conn:
            return
        try:
            self.conn = await aiosqlite.connect(self.db_path)
            self.conn.row_factory = aiosqlite.Row
            
            # Create tables
            await self._create_users_table()
            await self._create_economy_table()
            await self._create_daily_claims_table()
            await self._create_giveaways_table()
            await self._create_crash_history_table()
            await self._create_stock_status_message_table()
            await self._create_guild_settings_table()
            await self._create_stock_channels_table()
            await self._create_bot_config_table()

            await self._cleanup_old_roblox_tables()
            
            self.log.info("Database initialized successfully.")
        except aiosqlite.Error as e:
            self.log.critical("Failed to initialize database: %s", e)
            # If the DB fails to init, we should probably stop the bot.
            raise e

    async def _create_users_table(self):
        """Create the users table."""
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT NOT NULL,
                discriminator TEXT,
                avatar_hash TEXT,
                created_at TIMESTAMP NOT NULL,
                last_seen TIMESTAMP NOT NULL
            )
        """)
        await self.conn.commit()

    async def _create_economy_table(self):
        """Create the economy table."""
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS economy (
                user_id INTEGER PRIMARY KEY,
                balance INTEGER NOT NULL DEFAULT 0,
                net_worth INTEGER NOT NULL DEFAULT 0,
                total_earned INTEGER NOT NULL DEFAULT 0,
                total_spent INTEGER NOT NULL DEFAULT 0,
                blackjack_games INTEGER NOT NULL DEFAULT 0,
                blackjack_wins INTEGER NOT NULL DEFAULT 0,
                blackjack_pushes INTEGER NOT NULL DEFAULT 0,
                blackjack_losses INTEGER NOT NULL DEFAULT 0,
                blackjack_total_wagered INTEGER NOT NULL DEFAULT 0,
                crash_games_played INTEGER NOT NULL DEFAULT 0,
                crash_total_wagered INTEGER NOT NULL DEFAULT 0,
                crash_total_won INTEGER NOT NULL DEFAULT 0,
                crash_highest_multiplier REAL NOT NULL DEFAULT 0.0,
                FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
            )
        """)
        await self.conn.commit()

    async def _create_crash_history_table(self):
        """Creates the table to log crash game results."""
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS crash_history (
                game_id INTEGER PRIMARY KEY AUTOINCREMENT,
                crash_multiplier REAL NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await self.conn.commit()

    async def _create_daily_claims_table(self):
        """Create the daily_claims table."""
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_claims (
                user_id INTEGER PRIMARY KEY,
                last_claim_date DATE NOT NULL,
                streak INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
            )
        """)
        await self.conn.commit()

    async def _create_giveaways_table(self):
        """Creates tables for the persistent giveaway system."""
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS giveaways (
                message_id INTEGER PRIMARY KEY,
                channel_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                prize TEXT NOT NULL,
                end_time TIMESTAMP NOT NULL,
                host_id INTEGER NOT NULL,
                is_ended BOOLEAN NOT NULL DEFAULT 0
            )
        """)
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS giveaway_participants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                FOREIGN KEY (message_id) REFERENCES giveaways (message_id) ON DELETE CASCADE,
                UNIQUE(message_id, user_id)
            )
        """)
        await self.conn.commit()

    async def _create_stock_status_message_table(self):
        """
        Creates the table to store message IDs for stock status embeds in various channels.
        The channel_id is the primary key to ensure one tracked message per channel.
        """
        # Drop the old table if it exists to ensure a clean migration
        await self.conn.execute("DROP TABLE IF EXISTS stock_status_message")
        
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS stock_status_messages (
                channel_id INTEGER PRIMARY KEY,
                message_id INTEGER NOT NULL
            )
        """)
        await self.conn.commit()

    async def _create_guild_settings_table(self):
        """Creates the table for guild-specific settings."""
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS guild_settings (
                guild_id INTEGER PRIMARY KEY,
                stock_ping_role_id INTEGER
            )
        """)
        # Safely add the new column for moderation logs
        try:
            await self.conn.execute(
                "ALTER TABLE guild_settings ADD COLUMN mod_log_channel_id INTEGER;"
            )
        except aiosqlite.OperationalError as e:
            if "duplicate column name" not in str(e):
                logger.error(
                    "Failed to add mod_log_channel_id column: %s", e
                )
                raise
        await self.conn.commit()

    async def _create_stock_channels_table(self):
        """Creates the table to store stock announcement channels for each guild."""
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS stock_channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                UNIQUE(guild_id, channel_id)
            )
        """)
        await self.conn.commit()

    async def _create_bot_config_table(self):
        """Creates a table for storing generic key-value configuration."""
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS bot_config (
                key TEXT PRIMARY KEY,
                value_json TEXT NOT NULL
            )
        """)
        await self.conn.commit()

    # --- Bot Config ---
    async def set_config_value(self, key: str, value: Any):
        """Sets a configuration value, overwriting if it exists."""
        query = "INSERT OR REPLACE INTO bot_config (key, value_json) VALUES (?, ?)"
        try:
            # Serialize the value to a JSON string
            value_json = json.dumps(value)
            await self.conn.execute(query, (key, value_json))
            await self.conn.commit()
        except aiosqlite.Error as e:
            logger.error("Failed to set config value for key '%s': %s", key, e)

    async def get_config_value(self, key: str) -> Any | None:
        """Gets a configuration value."""
        query = "SELECT value_json FROM bot_config WHERE key = ?"
        try:
            async with self.conn.cursor() as cursor:
                await cursor.execute(query, (key,))
                result = await cursor.fetchone()
                if result:
                    # Deserialize the JSON string back to a Python object
                    return json.loads(result[0])
                return None
        except (aiosqlite.Error, json.JSONDecodeError) as e:
            logger.error("Failed to get config value for key '%s': %s", key, e)
            return None

    # --- Guild Settings ---
    async def set_stock_ping_role(self, guild_id: int, role_id: int | None):
        """Sets the role to ping for stock updates in a specific guild."""
        query = """
            INSERT INTO guild_settings (guild_id, stock_ping_role_id) VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET stock_ping_role_id = excluded.stock_ping_role_id
        """
        try:
            await self.conn.execute(query, (guild_id, role_id))
            await self.conn.commit()
            return True
        except aiosqlite.Error as e:
            logger.error("Error setting stock ping role for guild %d: %s", guild_id, e)
            return False

    async def get_stock_ping_role(self, guild_id: int) -> int | None:
        """Gets the stock ping role for a specific guild."""
        query = "SELECT stock_ping_role_id FROM guild_settings WHERE guild_id = ?"
        try:
            async with self.conn.cursor() as cursor:
                await cursor.execute(query, (guild_id,))
                result = await cursor.fetchone()
                return result[0] if result and result[0] is not None else None
        except aiosqlite.Error as e:
            logger.error("Error getting stock ping role for guild %d: %s", guild_id, e)
            return None
            
    async def set_mod_log_channel(self, guild_id: int, channel_id: int | None) -> bool:
        """Sets or clears the moderation log channel for a guild."""
        query = """
            INSERT INTO guild_settings (guild_id, mod_log_channel_id) VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET mod_log_channel_id = excluded.mod_log_channel_id
        """
        try:
            # Ensure the guild has a row first before updating
            await self.conn.execute("INSERT OR IGNORE INTO guild_settings (guild_id) VALUES (?)", (guild_id,))
            # Now update it
            await self.conn.execute(query, (guild_id, channel_id))
            await self.conn.commit()
            return True
        except aiosqlite.Error as e:
            logger.error("Error setting mod log channel for guild %d: %s", guild_id, e)
            return False

    async def get_mod_log_channel(self, guild_id: int) -> int | None:
        """Gets the moderation log channel ID for a guild."""
        query = "SELECT mod_log_channel_id FROM guild_settings WHERE guild_id = ?"
        try:
            async with self.conn.cursor() as cursor:
                await cursor.execute(query, (guild_id,))
                result = await cursor.fetchone()
                return result[0] if result and result[0] is not None else None
        except aiosqlite.Error as e:
            logger.error("Error getting mod log channel for guild %d: %s", guild_id, e)
            return None

    async def _cleanup_old_roblox_tables(self):
        """Cleans up old tables that are no longer in use."""
        await self.conn.execute("DROP TABLE IF EXISTS roblox_stock_channels")
        await self.conn.execute("DROP TABLE IF EXISTS roblox_guild_settings")
        await self.conn.commit()

    async def close(self):
        """Close the database connection."""
        if self.conn:
            await self.conn.close()
            logger.info("Database connection closed.")
            
    async def add_or_update_user(self, user):
        """Add a new user or update an existing one."""
        query = """
            INSERT INTO users (user_id, username, discriminator, avatar_hash, created_at, last_seen)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                discriminator = excluded.discriminator,
                avatar_hash = excluded.avatar_hash,
                last_seen = excluded.last_seen
        """
        params = (
            user.id,
            user.name,
            user.discriminator,
            user.avatar.key if user.avatar else None,
            user.created_at,
            datetime.now(timezone.utc)
        )
        
        try:
            async with self.conn.cursor() as cursor:
                await cursor.execute(query, params)
                # Also ensure the user has an economy entry
                await cursor.execute("INSERT OR IGNORE INTO economy (user_id) VALUES (?)", (user.id,))
            await self.conn.commit()
            return True
        except aiosqlite.Error as e:
            logger.error(f"Error adding/updating user {user.id}: {e}")
            return False

    async def get_user_balance(self, user_id: int):
        """Get the balance of a user."""
        try:
            async with self.conn.cursor() as cursor:
                await cursor.execute("SELECT balance FROM economy WHERE user_id = ?", (user_id,))
                result = await cursor.fetchone()
                return result[0] if result else 0
        except aiosqlite.Error as e:
            logger.error(f"Error getting balance for user {user_id}: {e}")
            return 0
            
    async def force_set_balance(self, user_id: int, amount: int) -> bool:
        """
        Sets a user's balance to a specific amount, bypassing transaction tracking.
        Ensures the user exists first.
        """
        if not await self.get_user_profile(user_id):
            logger.warning(
                "Attempted to set balance for non-existent user %d", user_id
            )
            return False

        query = "UPDATE economy SET balance = ? WHERE user_id = ?"
        try:
            await self.conn.execute(query, (amount, user_id))
            await self.conn.commit()
            return True
        except aiosqlite.Error as e:
            logger.error("Failed to force set balance for user %d: %s", user_id, e)
            return False
            
    async def update_balance(self, user_id: int, amount: int) -> bool:
        """
        Updates a user's balance and tracks total earned/spent.
        A positive amount is considered earned, negative is spent.
        """
        if not await self.get_user_profile(user_id):
            logger.warning("Attempted to update balance for non-existent user %d", user_id)
            return False

        try:
            if amount > 0:
                # User earned money
                query = "UPDATE economy SET balance = balance + ?, total_earned = total_earned + ? WHERE user_id = ?"
                await self.conn.execute(query, (amount, amount, user_id))
            else:
                # User spent money, amount is negative
                spent_amount = abs(amount)
                query = "UPDATE economy SET balance = balance + ?, total_spent = total_spent + ? WHERE user_id = ?"
                await self.conn.execute(query, (amount, spent_amount, user_id))

            await self.conn.commit()
            return True
        except aiosqlite.Error as e:
            logger.error("Failed to update balance for user %d: %s", user_id, e)
            return False
            
    async def get_daily_claim_info(self, user_id: int):
        """Get daily claim info for a user."""
        try:
            async with self.conn.cursor() as cursor:
                await cursor.execute("SELECT last_claim_date, streak FROM daily_claims WHERE user_id = ?", (user_id,))
                return await cursor.fetchone()
        except aiosqlite.Error as e:
            logger.error(
                "Error getting daily claim info for user %d: %s", user_id, e
            )
            return None

    async def update_daily_claim(self, user_id: int, claim_date, new_streak: int):
        """Updates or creates a daily claim entry for a user."""
        query = """
            INSERT INTO daily_claims (user_id, last_claim_date, streak) VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                last_claim_date = excluded.last_claim_date,
                streak = excluded.streak
        """
        try:
            await self.conn.execute(query, (user_id, claim_date, new_streak))
            await self.conn.commit()
        except aiosqlite.Error as e:
            logger.error("Error updating daily claim for user %d: %s", user_id, e)

    async def get_leaderboard(self, limit: int = 10):
        """
        Retrieves the top users by balance.
        Returns a list of tuples (user_id, username, balance).
        """
        query = """
            SELECT u.user_id, u.username, e.balance
            FROM economy e
            JOIN users u ON e.user_id = u.user_id
            WHERE e.balance > 0
            ORDER BY e.balance DESC
            LIMIT ?
        """
        try:
            async with self.conn.cursor() as cursor:
                await cursor.execute(query, (limit,))
                return await cursor.fetchall()
        except aiosqlite.Error as e:
            logger.error("Error fetching leaderboard: %s", e)
            return []

    async def get_user_profile(self, user_id: int):
        """Get a user's full profile data."""
        query = """
            SELECT
                u.user_id, u.username, u.discriminator, u.avatar_hash, u.created_at, u.last_seen,
                e.balance, e.net_worth, e.total_earned, e.total_spent,
                d.last_claim_date, d.streak
            FROM users u
            LEFT JOIN economy e ON u.user_id = e.user_id
            LEFT JOIN daily_claims d ON u.user_id = d.user_id
            WHERE u.user_id = ?
        """
        try:
            async with self.conn.cursor() as cursor:
                await cursor.execute(query, (user_id,))
                return await cursor.fetchone()
        except aiosqlite.Error as e:
            logger.error("Error fetching user profile for %d: %s", user_id, e)
            return None

    # --- Giveaway Methods ---
    async def create_giveaway(self, g: GiveawayData):
        """Creates a new entry for a giveaway."""
        query = """
            INSERT INTO giveaways (message_id, channel_id, guild_id, prize, end_time, host_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        try:
            await self.conn.execute(
                query, (g.message_id, g.channel_id, g.guild_id, g.prize, g.end_time, g.host_id)
            )
            await self.conn.commit()
        except aiosqlite.Error as e:
            logger.error("Error creating giveaway for message %d: %s", g.message_id, e)

    async def add_giveaway_participant(self, msg_id, user_id):
        """Adds a participant to a giveaway, ignoring duplicates."""
        query = "INSERT OR IGNORE INTO giveaway_participants (message_id, user_id) VALUES (?, ?)"
        try:
            cursor = await self.conn.execute(query, (msg_id, user_id))
            await self.conn.commit()
            return cursor.rowcount > 0  # True if a row was inserted, False if already exists
        except aiosqlite.Error as e:
            logger.error(
                "Error adding participant %d to giveaway %d: %s", user_id, msg_id, e
            )
            return None  # Indicate error

    async def get_giveaway_participants(self, msg_id):
        """Retrieves all participant IDs for a given giveaway."""
        query = "SELECT user_id FROM giveaway_participants WHERE message_id = ?"
        try:
            async with self.conn.cursor() as cursor:
                await cursor.execute(query, (msg_id,))
                return [row[0] for row in await cursor.fetchall()]
        except aiosqlite.Error as e:
            logger.error("Error getting participants for giveaway %d: %s", msg_id, e)
            return []

    async def get_ended_giveaways(self):
        """Retrieves all giveaways that have passed their end time and are not marked as ended."""
        query = "SELECT * FROM giveaways WHERE end_time <= ? AND is_ended = 0"
        try:
            async with self.conn.cursor() as cursor:
                await cursor.execute(query, (datetime.now(timezone.utc),))
                return await cursor.fetchall()
        except aiosqlite.Error as e:
            logger.error("Error fetching ended giveaways: %s", e)
            return []

    async def end_giveaway_db(self, msg_id):
        """Marks a giveaway as ended in the database."""
        query = "UPDATE giveaways SET is_ended = 1 WHERE message_id = ?"
        try:
            await self.conn.execute(query, (msg_id,))
            await self.conn.commit()
        except aiosqlite.Error as e:
            logger.error("Error marking giveaway %d as ended: %s", msg_id, e)

    # --- Stock Tracker Methods ---
    async def get_all_stock_status_messages(self):
        """Gets all stored stock status messages from the database."""
        query = "SELECT channel_id, message_id FROM stock_status_messages"
        try:
            async with self.conn.cursor() as cursor:
                await cursor.execute(query)
                return await cursor.fetchall()
        except aiosqlite.Error as e:
            logger.error("Error fetching all stock status messages: %s", e)
            return []

    async def get_stock_message_id(self, channel_id: int) -> int | None:
        """Gets the stored message ID for a specific channel."""
        query = "SELECT message_id FROM stock_status_messages WHERE channel_id = ?"
        try:
            async with self.conn.cursor() as cursor:
                await cursor.execute(query, (channel_id,))
                result = await cursor.fetchone()
                return result[0] if result else None
        except aiosqlite.Error as e:
            logger.error("Error getting stock message id for channel %d: %s", channel_id, e)
            return None

    async def delete_stock_message(self, channel_id: int):
        """Deletes a stock message entry from the database."""
        query = "DELETE FROM stock_status_messages WHERE channel_id = ?"
        try:
            await self.conn.execute(query, (channel_id,))
            await self.conn.commit()
        except aiosqlite.Error as e:
            logger.error("Error deleting stock message for channel %d: %s", channel_id, e)

    async def set_stock_status_message(self, channel_id: int, message_id: int):
        """Saves or updates the message ID for a stock status embed in a channel."""
        query = "INSERT OR REPLACE INTO stock_status_messages (channel_id, message_id) VALUES (?, ?)"
        try:
            await self.conn.execute(query, (channel_id, message_id))
            await self.conn.commit()
        except aiosqlite.Error as e:
            logger.error(
                "Error setting stock status message for channel %d: %s", channel_id, e
            )

    async def add_stock_channel(self, guild_id: int, channel_id: int) -> bool:
        """Adds a channel to the list of stock announcement channels for a guild."""
        query = "INSERT OR IGNORE INTO stock_channels (guild_id, channel_id) VALUES (?, ?)"
        try:
            cursor = await self.conn.execute(query, (guild_id, channel_id))
            await self.conn.commit()
            if cursor.rowcount == 0:
                logger.warning(
                    "Attempted to add duplicate stock channel %d for guild %d.",
                    channel_id, guild_id
                )
                return False
            return True
        except aiosqlite.Error as e:
            logger.error("Error adding stock channel for guild %d: %s", guild_id, e)
            return False

    async def remove_stock_channel(self, guild_id: int, channel_id: int) -> bool:
        """Removes a channel from the list of stock announcement channels for a guild."""
        query = "DELETE FROM stock_channels WHERE guild_id = ? AND channel_id = ?"
        try:
            cursor = await self.conn.execute(query, (guild_id, channel_id))
            await self.conn.commit()
            return cursor.rowcount > 0
        except aiosqlite.Error as e:
            logger.error(
                "Error removing stock channel for guild %d: %s", guild_id, e
            )
            return False

    async def get_stock_channels_for_guild(self, guild_id: int) -> list[int]:
        """Gets all stock announcement channel IDs for a specific guild."""
        query = "SELECT channel_id FROM stock_channels WHERE guild_id = ?"
        try:
            async with self.conn.cursor() as cursor:
                await cursor.execute(query, (guild_id,))
                return [row[0] for row in await cursor.fetchall()]
        except aiosqlite.Error as e:
            logger.error(
                "Error getting stock channels for guild %d: %s", guild_id, e
            )
            return []

    async def get_all_stock_channels(self) -> list[int]:
        """Gets all unique stock announcement channel IDs across all guilds."""
        query = "SELECT DISTINCT channel_id FROM stock_channels"
        try:
            async with self.conn.cursor() as cursor:
                await cursor.execute(query)
                return [row[0] for row in await cursor.fetchall()]
        except aiosqlite.Error as e:
            logger.error("Error getting all stock channels: %s", e)
            return []
            
    # --- Game Stats Methods ---
    async def update_blackjack_stats(self, user_id: int, outcome: str, wager: int):
        """Updates a user's blackjack stats."""
        # This is a bit complex, might be better in a stored procedure if not for sqlite
        if outcome == 'win':
            field_to_increment = "blackjack_wins"
        elif outcome == 'loss':
            field_to_increment = "blackjack_losses"
        elif outcome == 'push':
            field_to_increment = "blackjack_pushes"
        else:
            return # Should not happen

        query = f"""
            UPDATE economy
            SET {field_to_increment} = {field_to_increment} + 1,
                blackjack_games = blackjack_games + 1,
                blackjack_total_wagered = blackjack_total_wagered + ?
            WHERE user_id = ?
        """
        try:
            await self.conn.execute(query, (wager, user_id))
            await self.conn.commit()
        except aiosqlite.Error as e:
            logger.error("Error updating blackjack stats for user %d: %s", user_id, e)

    async def update_crash_stats(
        self, user_id: int, wager: int, winnings: int, multiplier: float
    ):
        """Updates a user's crash game stats."""
        query = """
            UPDATE economy
            SET crash_games_played = crash_games_played + 1,
                crash_total_wagered = crash_total_wagered + ?,
                crash_total_won = crash_total_won + ?,
                crash_highest_multiplier = MAX(crash_highest_multiplier, ?)
            WHERE user_id = ?
        """
        try:
            await self.conn.execute(query, (wager, winnings, multiplier, user_id))
            await self.conn.commit()
        except aiosqlite.Error as e:
            logger.error("Error updating crash stats for user %d: %s", user_id, e)

    async def log_crash_game(self, crash_multiplier: float):
        """Logs a completed crash game's multiplier to the history table."""
        try:
            await self.conn.execute(
                "INSERT INTO crash_history (crash_multiplier) VALUES (?)", (crash_multiplier,)
            )
            await self.conn.commit()
        except aiosqlite.Error as e:
            logger.error("Error logging crash game: %s", e)

    async def get_crash_history(self, limit: int = 10) -> list[float]:
        """Gets the most recent crash multipliers."""
        query = "SELECT crash_multiplier FROM crash_history ORDER BY game_id DESC LIMIT ?"
        try:
            async with self.conn.cursor() as cursor:
                await cursor.execute(query, (limit,))
                return [row[0] for row in await cursor.fetchall()]
        except aiosqlite.Error as e:
            logger.error("Error getting crash history: %s", e)
            return []