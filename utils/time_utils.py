"""
Utility functions for handling time and duration parsing.
"""
from datetime import datetime, timedelta, timezone
import re

def parse_duration(duration_str: str) -> datetime | None:
    """
    Parses a duration string (e.g., "10s", "5m", "1h", "2d") into a future datetime object.
    Returns None if the format is invalid.
    """
    match = re.match(r"(\d+)\s*([smhd])", duration_str.lower())
    if not match:
        return None

    value, unit = int(match.group(1)), match.group(2)
    now = datetime.now(timezone.utc)

    if unit == 's':
        delta = timedelta(seconds=value)
    elif unit == 'm':
        delta = timedelta(minutes=value)
    elif unit == 'h':
        delta = timedelta(hours=value)
    elif unit == 'd':
        delta = timedelta(days=value)
    else:
        # This case is unreachable due to the regex, but good for completeness
        return None

    return now + delta

def format_time(dt_object: datetime) -> str:
    """Formats a datetime object into a Discord relative timestamp string."""
    return f"<t:{int(dt_object.timestamp())}:R>" 