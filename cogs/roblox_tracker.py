"""
Cog for tracking Grow a Garden stock in real-time and posting updates.
"""
import asyncio
import copy
import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import discord
import websockets
from discord import app_commands
from discord.ext import commands, tasks

from config import Config
from utils.embed_utils import create_embed, create_error_embed
from utils.time_utils import format_time

logger = logging.getLogger(__name__)

# --- Constants ---
NOTABLE_SEEDS = [
    "Beanstalk", "Moon Blossom", "Hive Fruit", "Sugar Apple", "Elephant Ears", "Ember Lily",
    "Cacao", "Sunflower", "Pepper", "Grape", "Mushroom", "Traveler's Fruit", "Rosy Delight",
    "Dragon Pepper", "Lotus", "Firework Flower", "Candy Blossom"
]
NOTABLE_GEAR = [
    "Advanced Sprinkler", "Star Caller", "Night Staff", "Godly Sprinkler",
    "Chocolate Sprinkler", "Magnifying Glass", "Master Sprinkler", "Cleaning Spray",
    "Favorite Tool", "Harvest Tool", "Friendship Pot", "Honey Sprinkler", "Lightning Rod",
    "Recall Wrench"
]
NOTABLE_EGGS = ["Legendary Egg", "Mythical Egg", "Paradise Egg", "Bee Egg", "Bug Egg", "Night Egg"]

WEATHER_ICONS = {
    "Bình thường": "☀️", "Sunny": "☀️", "normal": "☀️", "Rain": "🌧️", "rain": "🌧️", "Thunderstorm": "⛈️",
    "thunder": "⛈️", "Frost": "❄️", "Snow": "☃️", "Night": "🌙", "Blood Moon": "🩸", "Meteor Shower": "☄️",
    "Heatwave": "🔥", "heatwave": "🔥", "Windy": "💨", "Tropical Rain": "💦", "Drought": "🏜️",
    "Aurora": "✨", "Bee Swarm": "🐝", "Working Bee Swarm": "🐝", "Disco": "🕺", "Tornado": "🌪️",
    "Jandel Storm": "⛈️", "Sheckle Rain": "💰", "Chocolate Rain": "🍫", "Lazer Storm": "☄️",
    "Black Hole": "⚫", "Sun God": "👑", "Floating Jandel": "😇", "Volcano Event": "🌋",
    "Meteor Strike": "💥", "Alien Invasion": "👽", "Space Travel": "🚀", "Fried Chicken": "🍗",
    "Under the Sea": "🌊", "Solar Flare": "☀️",
}

CATEGORY_MAPPING = {
    "gear": {"name": "GEAR STOCK", "emoji": "🛠️"},
    "seeds": {"name": "SEEDS STOCK", "emoji": "🌱"},
    "eggs": {"name": "EGG STOCK", "emoji": "🥚"},
}

NOTABLE_MAP = {
    "seeds": (NOTABLE_SEEDS, "Seeds"),
    "gear": (NOTABLE_GEAR, "Gear"),
    "eggs": (NOTABLE_EGGS, "Eggs"),
}

PLANTING_TREES_GUILD_ID = 1382226403889647746


class RobloxTracker(commands.Cog):
    """Handles tracking Grow a Garden stock in real-time and posting updates."""

    stock_group = app_commands.Group(
        name="stock", description="Quản lý cài đặt theo dõi stock cho server này."
    )

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = bot.db
        self.last_data_hash: Optional[str] = None
        self.last_raw_data: Optional[Dict[str, Any]] = None
        self.weather_history: List[Dict[str, Any]] = []
        self.websocket_task: Optional[asyncio.Task] = None

        if Config.ROBLOX_STOCK_ENABLED and Config.ROBLOX_WEBSOCKET_URL:
            self.websocket_task = self.bot.loop.create_task(self.websocket_listener())
        else:
            logger.warning("Roblox Stock Tracker is disabled or not configured. It will not run.")

    async def cog_unload(self):
        """Cancels the websocket listener task when the cog is unloaded."""
        if self.websocket_task:
            self.websocket_task.cancel()

    async def _process_websocket_message(self, message: str):
        """Processes a single message from the websocket."""
        logger.info("Raw websocket data: %s", message)
        try:
            current_data = json.loads(message).get("data", {})
            self.last_raw_data = current_data
            if not current_data:
                logger.warning("Received an empty 'data' object from websocket, skipping.")
                return

            current_hash = self._calculate_data_hash(current_data)
            self.weather_history = current_data.get("weatherHistory", [])

            if self.last_data_hash is None:
                self.last_data_hash = current_hash
                logger.info("Established baseline with hash: %s", self.last_data_hash)
                return

            if current_hash != self.last_data_hash:
                logger.info("Change detected! Old: %s, New: %s", self.last_data_hash, current_hash)
                await self._handle_update(current_data)
                self.last_data_hash = current_hash

        except json.JSONDecodeError:
            logger.error("Failed to decode JSON from websocket message: %s", message)
        except discord.DiscordException as e:
            logger.error("A discord error occurred processing a websocket message: %s", e, exc_info=True)

    async def websocket_listener(self):
        """Connects to the WebSocket and processes stock data in real-time."""
        await self.bot.wait_until_ready()
        logger.info("Starting real-time GrowAGarden.PRO WebSocket listener...")
        while not self.bot.is_closed():
            try:
                async with websockets.connect(Config.ROBLOX_WEBSOCKET_URL) as websocket:
                    logger.info("Successfully connected to WebSocket.")
                    async for message in websocket:
                        await self._process_websocket_message(message)
            except (websockets.exceptions.ConnectionClosedError, OSError) as e:
                logger.warning("WebSocket connection error: %s. Reconnecting in 30s...", e)
            except Exception as e:
                logger.error("An unexpected error occurred in websocket_listener: %s", e, exc_info=True)
            await asyncio.sleep(30)

    async def _handle_update(self, new_data: Dict[str, Any]):
        """The core logic to handle a detected change."""
        all_channel_ids = await self.db.get_all_stock_channels()
        if not all_channel_ids:
            logger.info("No stock announcement channels configured. Skipping update.")
            return

        embed = self._build_stock_embed(new_data)
        if not embed:
            logger.info("Update embed was not built, likely no items in stock. Skipping.")
            return

        change_summary = self._generate_change_summary(new_data)

        update_tasks = []
        channels_to_update = []
        for channel_id in all_channel_ids:
            if channel := self.bot.get_channel(channel_id):
                # Schedule each channel update to run concurrently
                task = asyncio.create_task(self._update_channel(channel, embed, change_summary))
                update_tasks.append(task)
                channels_to_update.append(channel)
            else:
                logger.warning("Stock channel %s not found, skipping.", channel_id)

        if update_tasks:
            # Wait for all updates to complete, but don't stop if one fails
            results = await asyncio.gather(*update_tasks, return_exceptions=True)
            for channel, result in zip(channels_to_update, results):
                if isinstance(result, Exception):
                    logger.error(
                        "Failed to update channel #%s (%s): %s",
                        channel.name, channel.id, result, exc_info=False
                    )

    async def _update_channel(
        self, channel: discord.TextChannel, embed: discord.Embed, change_summary: str
    ):
        """Updates a single channel with the new stock information."""
        if change_summary:
            await self._send_notification(channel, change_summary)

        try:
            message_id = await self.db.get_stock_message_id(channel.id)
            message = None
            if message_id:
                try:
                    message = await channel.fetch_message(message_id)
                except (discord.NotFound, discord.Forbidden):
                    await self.db.delete_stock_message(channel.id)

            if message:
                await message.edit(embed=embed)
            else:
                new_message = await channel.send(embed=embed)
                await self.db.set_stock_status_message(channel.id, new_message.id)
        except discord.HTTPException as e:
            logger.error("Failed to update channel %s: %s", channel.id, e, exc_info=True)

    def _calculate_data_hash(self, data: Dict[str, Any]) -> str:
        """Calculates a consistent MD5 hash for the relevant parts of the stock data."""
        if not data:
            return ""
        relevant_data = {"weather": self._get_weather_type(data), "items": {}}
        for category in sorted(CATEGORY_MAPPING):
            items = data.get(category, [])
            if items:
                names = [item.get('name', '').lower() for item in items if item.get('name')]
                relevant_data["items"][category] = sorted(names)
        canonical_string = json.dumps(relevant_data, sort_keys=True, separators=(',', ':'))
        return hashlib.md5(canonical_string.encode('utf-8')).hexdigest()

    def _get_weather_type(self, data: Optional[Dict[str, Any]]) -> str:
        """Safely extracts the weather type from the data payload."""
        if not data or not isinstance(weather := data.get("weather"), dict):
            return "Bình thường"
        return weather.get("type", "Bình thường")

    def _generate_change_summary(self, new_data: Dict) -> str:
        """Generates a simple list of all new, notable items that have appeared in the shop."""
        notable_items_by_cat = self._get_notable_items(new_data)

        summary_parts = []
        if notable_items_by_cat:
            category_parts = []
            for category_key in sorted(notable_items_by_cat):
                items = notable_items_by_cat[category_key]
                emoji = CATEGORY_MAPPING.get(category_key, {}).get("emoji", "🔹")
                category_name = NOTABLE_MAP.get(category_key, ("", ""))[1]
                item_lines = [f"• {item}" for item in items]
                category_parts.append(f"\n**{emoji} {category_name}**\n" + "\n".join(item_lines))
            summary_parts.append("**Vật phẩm hiếm trong kho:**" + "".join(category_parts))

        return "\n".join(summary_parts)

    def _get_notable_items(self, new_data: Dict) -> Dict[str, List[str]]:
        """Extracts notable items from the new stock data, grouped by category."""
        notable_by_category = {}
        for category_key, (notable_list, _) in NOTABLE_MAP.items():
            new_set = {item['name'].lower() for item in new_data.get(category_key, []) if item.get('name')}
            notable_list_lower = {name.lower() for name in notable_list}
            current_notables = new_set.intersection(notable_list_lower)

            if current_notables:
                original_casing_map = {
                    item['name'].lower(): item['name'] for item in new_data.get(category_key, [])
                }
                original_names = sorted([
                    original_casing_map.get(name, name.title()) for name in current_notables
                ])
                if original_names:
                    notable_by_category[category_key] = original_names
        return notable_by_category


    async def _send_notification(self, channel: discord.TextChannel, change_summary: str):
        """Sends a notification message, deleting the previous one to prevent spam."""
        config_key = f"last_notification_channel_{channel.id}"
        if last_noti_id := await self.db.get_config_value(config_key):
            try:
                last_message = await channel.fetch_message(last_noti_id)
                await last_message.delete()
                logger.info("Deleted previous notification message %s in #%s", last_noti_id, channel.name)
            except (discord.NotFound, discord.Forbidden):
                pass

        ping_text, mentions = await self._get_ping_settings(channel.guild)
        content = f"{ping_text}Cập nhật stock mới!\n\n{change_summary}"

        try:
            logger.info("Sending notification to #%s in %s.", channel.name, channel.guild.name)
            new_msg = await channel.send(content, allowed_mentions=mentions)
            await self.db.set_config_value(config_key, new_msg.id)
        except discord.HTTPException as e:
            logger.error("Failed to send stock notification to channel %s: %s", channel.id, e)

    async def _get_ping_settings(self, guild: discord.Guild) -> (str, discord.AllowedMentions):
        """Determines the appropriate ping role and allowed mentions for a guild."""
        if role_id := await self.db.get_stock_ping_role(guild.id):
            return f"<@&{role_id}> ", discord.AllowedMentions(roles=True)
        if guild.id == PLANTING_TREES_GUILD_ID:
            return "@everyone ", discord.AllowedMentions(everyone=True)
        return "", discord.AllowedMentions.none()

    def _build_stock_embed(self, data: Dict[str, Any]) -> Optional[discord.Embed]:
        """Builds the main embed displaying the current shop stock."""
        weather_type = self._get_weather_type(data)
        weather_emoji = WEATHER_ICONS.get(weather_type, "❓")

        if weather_emoji == "❓":
            logger.warning("Unknown weather type: '%s'. Add to WEATHER_ICONS.", weather_type)

        embed = create_embed(
            title="Grow a Garden - Shop Stock",
            description=f"**Thời tiết hiện tại:** {weather_emoji} {weather_type}",
            color=discord.Color.from_rgb(47, 49, 54)
        )

        for category_key in ['seeds', 'gear', 'eggs']:
            if not (items := data.get(category_key)) or not isinstance(items, list):
                continue

            processed_items = self._process_items(items)
            if not processed_items:
                continue

            mapping = CATEGORY_MAPPING.get(category_key)
            if not mapping:
                continue

            field_name = f"{mapping['emoji']} **{mapping['name']}**"
            field_value = [f"**{name}** `x{qty}`" for name, qty in sorted(processed_items.items())]
            if field_value:
                embed.add_field(name=field_name, value="\n".join(field_value), inline=True)

        embed.set_footer(text="made by Tiến đẹp trai • Last Updated")
        embed.timestamp = datetime.now(timezone.utc)
        return embed

    def _process_items(self, items: List[Dict]) -> Dict[str, int]:
        """Deduplicates and counts items from a list."""
        processed = {}
        for item in items:
            if name := item.get('name'):
                processed[name] = processed.get(name, 0) + item.get('quantity', 0)
        return processed

    @stock_group.command(name="add_channel", description="[Admin] Thêm một kênh để nhận thông báo stock.")
    @app_commands.describe(channel="Kênh văn bản bạn muốn bot gửi thông báo vào.")
    @app_commands.checks.has_permissions(administrator=True)
    async def stock_add_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """Adds a channel to receive stock update notifications."""
        await self.db.add_stock_channel(interaction.guild_id, channel.id)
        embed = create_embed(
            title="Kênh đã được thêm",
            description=f"Kênh {channel.mention} sẽ bắt đầu nhận thông báo về kho hàng.",
            color=Config.COLOR_SUCCESS
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @stock_group.command(name="remove_channel", description="[Admin] Xóa kênh khỏi danh sách nhận thông báo.")
    @app_commands.describe(channel="Kênh bạn muốn xóa khỏi danh sách.")
    @app_commands.checks.has_permissions(administrator=True)
    async def stock_remove_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """Removes a channel from receiving stock update notifications."""
        await self.db.delete_stock_channel(interaction.guild_id, channel.id)
        embed = create_embed(
            title="Kênh đã được xóa",
            description=f"Kênh {channel.mention} sẽ không còn nhận thông báo về kho hàng.",
            color=Config.COLOR_SUCCESS
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @stock_group.command(name="list_channels", description="Xem các kênh đang nhận thông báo stock.")
    async def stock_list_channels(self, interaction: discord.Interaction):
        """Lists all channels configured to receive stock updates in this server."""
        channel_ids = await self.db.get_stock_channels_by_guild(interaction.guild_id)
        if not channel_ids:
            embed = create_embed(
                "Không có kênh nào",
                description="Không có kênh nào được cấu hình để nhận thông báo stock trong server này.",
                color=Config.COLOR_INFO
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        description = "\n".join(f"- <#{channel_id}> (`{channel_id}`)" for channel_id in channel_ids)
        embed = create_embed(
            "Các kênh nhận thông báo",
            description=description,
            color=Config.COLOR_PRIMARY
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="set_stock_ping", description="[Admin] Đặt vai trò sẽ được ping khi có stock mới.")
    @app_commands.describe(role="Vai trò bạn muốn ping. Để trống để không ping vai trò nào.")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_stock_ping(self, interaction: discord.Interaction, role: Optional[discord.Role]):
        """Sets or removes the role to be pinged on stock updates for this server."""
        if role:
            await self.db.set_stock_ping_role(interaction.guild_id, role.id)
            desc = f"Vai trò {role.mention} sẽ được ping khi có vật phẩm hiếm mới."
        else:
            await self.db.remove_stock_ping_role(interaction.guild_id)
            desc = "Đã xóa vai trò ping. Sẽ không có vai trò nào được ping."

        embed = create_embed("Cài đặt Ping đã được cập nhật", description=desc, color=Config.COLOR_SUCCESS)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="weather", description="Xem lịch sử thời tiết gần đây trong Grow a Garden.")
    async def weather_history_command(self, interaction: discord.Interaction):
        """Displays the recent weather history."""
        if not self.weather_history:
            embed = create_embed(
                title="Lịch sử thời tiết",
                description="Không có dữ liệu lịch sử thời tiết nào được ghi lại.",
                color=Config.COLOR_INFO
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        description = []
        for event in self.weather_history[:10]:  # Show latest 10 events
            weather_type = event.get('type', 'Unknown')
            start_time_str = event.get('startTime')

            if not start_time_str:
                continue

            try:
                # The timestamp is in ISO format with 'Z' for UTC
                dt_object = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
                time_str = format_time(dt_object)
                icon = WEATHER_ICONS.get(weather_type, "❓")
                description.append(f"{icon} **{weather_type}** - {time_str}")
            except (ValueError, TypeError) as e:
                logger.warning("Could not parse weather history event timestamp: %s. Error: %s", event, e)

        embed = create_embed(
            title="Lịch sử thời tiết gần đây",
            description="\n".join(description) or "Không thể xử lý dữ liệu thời tiết.",
            color=Config.COLOR_PRIMARY
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="stockdebug", description="[Admin] Hiển thị dữ liệu thô từ API stock.")
    @app_commands.checks.has_permissions(administrator=True)
    async def stock_debug(self, interaction: discord.Interaction):
        """Displays the last raw data received from the websocket for debugging."""
        if not self.last_raw_data:
            return await interaction.response.send_message(
                "Chưa nhận được dữ liệu nào từ API.", ephemeral=True
            )

        embed = create_embed(
            title="🔍 Dữ liệu API Stock Thô",
            description="Đây là danh sách đầy đủ các vật phẩm từ lần cập nhật API cuối cùng.",
            color=Config.COLOR_WARNING
        )

        for category, items in self.last_raw_data.items():
            if isinstance(items, list) and items:
                # Limit the number of items displayed to avoid hitting Discord's character limit
                item_names = [f"`{item.get('name', 'N/A')}`" for item in items[:25]]
                if len(items) > 25:
                    item_names.append(f"... và {len(items) - 25} nữa.")
                
                value = ", ".join(item_names)
                embed.add_field(name=f"Category: {category.title()}", value=value or "Không có", inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    """Sets up the cog."""
    await bot.add_cog(RobloxTracker(bot))
