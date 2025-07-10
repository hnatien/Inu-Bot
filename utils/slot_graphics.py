"""
This module handles the generation of all graphics for the cluster slots game,
including rendering the game grid, animations, and overlays using the Pillow library.
"""
import io
import math
import os
import random

from PIL import Image, ImageDraw, ImageFont

from game_config import GRID_WIDTH, GRID_HEIGHT, BASE_REELS, ANTE_REELS

# --- Constants ---
CELL_SIZE = 100
PADDING = 20
GRID_LINE_COLOR = (80, 80, 80)
BACKGROUND_COLOR = (47, 49, 54)  # Discord Dark Theme
HIGHLIGHT_COLOR_WIN = (80, 200, 80, 128)  # Semi-transparent green

# --- Font Loading ---
def get_font_path(font_name="seguiemj.ttf"):
    """Finds a font, preferring system paths but falling back to a local directory."""
    font_path = os.path.join("C:", os.sep, "Windows", "Fonts", font_name)
    if os.path.exists(font_path):
        return font_path
    # Fallback for non-Windows or if font isn't in the default location
    return os.path.join(os.path.dirname(__file__), font_name)

try:
    FONT_PATH = get_font_path()
    EMOJI_FONT = ImageFont.truetype(FONT_PATH, 75)
except IOError:
    print(f"Emoji font could not be loaded from {FONT_PATH}. Using default font.")
    EMOJI_FONT = ImageFont.load_default()


# --- Reel Strip Generation ---
def _create_reel_strips(reels_data):
    """
    Pre-renders each reel strip into a long vertical image (sprite sheet).
    This is a massive performance boost compared to drawing emojis frame by frame.
    """
    reel_strips = []
    for reel in reels_data:
        strip_height = len(reel) * CELL_SIZE
        strip_image = Image.new("RGBA", (CELL_SIZE, strip_height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(strip_image)
        for i, symbol in enumerate(reel):
            y0 = i * CELL_SIZE
            bbox = draw.textbbox((0, 0), symbol, font=EMOJI_FONT)
            text_width, text_height = bbox[2] - bbox[0], bbox[3] - bbox[1]
            text_x = (CELL_SIZE - text_width) / 2
            text_y = y0 + (CELL_SIZE - text_height) / 2 - 10
            draw.text(
                (text_x, text_y), symbol, font=EMOJI_FONT,
                fill=(255, 255, 255), embedded_color=True
            )
        reel_strips.append(strip_image)
    return reel_strips

REEL_STRIP_IMAGES = _create_reel_strips(BASE_REELS)
ANTE_REEL_STRIP_IMAGES = [] # To be populated if ante bet is used

def _draw_reels(image, reel_positions, active_reel_strips):
    """Draws the animated spinning reels onto the main image."""
    for c, reel_strip in enumerate(active_reel_strips):
        if c >= len(reel_positions):
            continue
        col_x = PADDING + c * CELL_SIZE
        reel_len_pixels = reel_strip.height
        slice_y = (reel_positions[c] * CELL_SIZE) % reel_len_pixels
        image.paste(reel_strip, (col_x, PADDING - int(slice_y)), reel_strip)
        image.paste(reel_strip, (col_x, PADDING - int(slice_y) + reel_len_pixels), reel_strip)

def _draw_static_grid(draw, grid, y_offsets):
    """Draws a static grid of symbols, applying physics offsets if provided."""
    for r in range(GRID_HEIGHT):
        for c in range(GRID_WIDTH):
            symbol = grid[r][c]
            if not symbol:
                continue
            col_x = PADDING + c * CELL_SIZE
            y0 = PADDING + r * CELL_SIZE
            if y_offsets and (r, c) in y_offsets:
                y0 += y_offsets.get((r, c), 0)
            bbox = draw.textbbox((0, 0), symbol, font=EMOJI_FONT)
            text_width, text_height = bbox[2] - bbox[0], bbox[3] - bbox[1]
            text_x = col_x + (CELL_SIZE - text_width) / 2
            text_y = y0 + (CELL_SIZE - text_height) / 2 - 10
            draw.text(
                (text_x, text_y), symbol, font=EMOJI_FONT,
                fill=(255, 255, 255), embedded_color=True
            )

def _draw_grid_lines(draw, img_width, img_height):
    """Draws the grid lines over the symbols."""
    for r in range(GRID_HEIGHT + 1):
        y = PADDING + r * CELL_SIZE
        draw.line([(PADDING, y), (img_width - PADDING, y)], fill=GRID_LINE_COLOR, width=2)
    for c in range(GRID_WIDTH + 1):
        x = PADDING + c * CELL_SIZE
        draw.line([(x, PADDING), (x, img_height - PADDING)], fill=GRID_LINE_COLOR, width=2)

def _draw_highlights(draw, highlights, alpha_override):
    """Draws highlights over winning cells."""
    if not highlights:
        return
    alpha = alpha_override if alpha_override is not None else HIGHLIGHT_COLOR_WIN[3]
    color = (HIGHLIGHT_COLOR_WIN[0], HIGHLIGHT_COLOR_WIN[1], HIGHLIGHT_COLOR_WIN[2], alpha)
    for r, c in highlights:
        x0, y0 = PADDING + c * CELL_SIZE, PADDING + r * CELL_SIZE
        x1, y1 = x0 + CELL_SIZE, y0 + CELL_SIZE
        draw.rectangle([x0, y0, x1, y1], fill=color)

def generate_slot_image(options: dict) -> io.BytesIO:
    """
    Generates an image of the slot machine grid based on the provided options.
    """
    img_width = GRID_WIDTH * CELL_SIZE + 2 * PADDING
    img_height = GRID_HEIGHT * CELL_SIZE + 2 * PADDING
    image = Image.new("RGBA", (img_width, img_height), BACKGROUND_COLOR)
    draw = ImageDraw.Draw(image, "RGBA")

    # Unpack options with defaults
    grid = options.get('grid')
    reel_positions = options.get('reel_positions')
    highlights = options.get('highlights')
    y_offsets = options.get('y_offsets')
    alpha_override = options.get('highlight_alpha_override')
    ante_bet = options.get('ante_bet', False)

    if reel_positions:
        if ante_bet and not ANTE_REEL_STRIP_IMAGES:
            ANTE_REEL_STRIP_IMAGES[:] = _create_reel_strips(ANTE_REELS)
        active_strips = ANTE_REEL_STRIP_IMAGES if ante_bet else REEL_STRIP_IMAGES
        _draw_reels(image, reel_positions, active_strips)
    elif grid:
        _draw_static_grid(draw, grid, y_offsets)

    _draw_grid_lines(draw, img_width, img_height)
    _draw_highlights(draw, highlights, alpha_override)

    img_buffer = io.BytesIO()
    image.save(img_buffer, format="PNG")
    img_buffer.seek(0)
    return img_buffer

def _draw_flashing_border(draw, width, height, progress):
    """Draws a pulsing border on the image."""
    border_pulse = math.sin(progress * 4 * math.pi)
    border_width = int(10 * (0.5 + 0.5 * border_pulse))
    if border_width > 0:
        border_color = (138, 43, 226, 200)  # BlueViolet
        draw.rectangle([0, 0, width-1, height-1], outline=border_color, width=border_width)

def _draw_royal_rain(draw, width, height, progress):
    """Draws a rain of royal items."""
    num_items = int(100 * progress)
    royal_items = ["💰", "💎", "👑"]
    random.seed(42)
    for _ in range(num_items):
        item = random.choice(royal_items)
        x_start, y_start = random.uniform(0, width), random.uniform(-height, 0)
        speed = random.uniform(0.5, 1.5)
        y_pos = y_start + (height * 1.5) * progress * speed
        if 0 < y_pos < height:
            draw.text((x_start, y_pos), item, font=EMOJI_FONT, embedded_color=True)
    random.seed()

def draw_big_win_overlay(image: Image.Image, frame_num: int, total_frames: int) -> Image.Image:
    """Draws a 'Big Win' celebration overlay onto an image."""
    draw = ImageDraw.Draw(image, "RGBA")
    width, height = image.size
    progress = frame_num / total_frames if total_frames > 0 else 1.0

    _draw_flashing_border(draw, width, height, progress)
    _draw_royal_rain(draw, width, height, progress)
    return image

def generate_animation_gif(frames: list[Image.Image], frame_duration_ms: int) -> io.BytesIO:
    """Saves a list of PIL Image objects as an animated GIF."""
    gif_buffer = io.BytesIO()
    if not frames:
        return gif_buffer
    frames[0].save(
        gif_buffer, format="GIF", save_all=True, append_images=frames[1:],
        duration=frame_duration_ms, loop=0, transparency=0, disposal=2
    )
    gif_buffer.seek(0)
    return gif_buffer

def draw_winnings_on_image(image: Image.Image, amount: int) -> Image.Image:
    """Draws the winnings amount onto the image."""
    draw = ImageDraw.Draw(image)
    text = f"WIN: {amount:,}"
    try:
        font = ImageFont.truetype(FONT_PATH, 60)
    except IOError:
        font = EMOJI_FONT

    x, y = 20, 20
    outline_color = "black"
    for x_offset in [-2, 0, 2]:
        for y_offset in [-2, 0, 2]:
            if x_offset != 0 or y_offset != 0:
                draw.text((x + x_offset, y + y_offset), text, font=font, fill=outline_color)
    draw.text((x, y), text, font=font, fill="white")
    return image 