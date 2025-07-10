"""
Generates a professional-looking graph image for the crash game using Matplotlib and Pillow.
"""

import io
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# --- Font and Style Configuration ---
# Set a backend that doesn't require a GUI
mpl.use('Agg')

# Define paths for fonts
BASE_DIR = Path(__file__).resolve().parent.parent
# FONT_PATH_REGULAR = BASE_DIR / "assets" / "fonts" / "Kanit-Regular.ttf"
# FONT_PATH_BOLD = BASE_DIR / "assets" / "fonts" / "Kanit-Bold.ttf"

# Matplotlib styling
plt.style.use('dark_background')
# mpl.rcParams['font.family'] = 'Kanit'
# mpl.rcParams['font.sans-serif'] = 'Kanit'
mpl.rcParams['axes.edgecolor'] = '#555555'
mpl.rcParams['axes.linewidth'] = 1.5
mpl.rcParams['axes.labelcolor'] = '#AAAAAA'
mpl.rcParams['xtick.color'] = '#AAAAAA'
mpl.rcParams['ytick.color'] = '#AAAAAA'
mpl.rcParams['grid.color'] = '#333333'
mpl.rcParams['figure.facecolor'] = 'none'
mpl.rcParams['savefig.facecolor'] = 'none'
mpl.rcParams['axes.facecolor'] = '#1E1E1E'  # Dark gray plot background

def _plot_graph_to_buffer(history: list, current_multiplier: float, is_crashed: bool) -> io.BytesIO:
    """Handles all Matplotlib plotting and returns a buffer with the image."""
    fig, ax = plt.subplots(figsize=(6, 3), dpi=100)

    x_values = np.arange(len(history))
    y_values = np.array(history)
    color = "#E74C3C" if is_crashed else "#2ECC71"

    ax.plot(x_values, y_values, color=color, linewidth=2.5)
    ax.fill_between(x_values, y_values, color=color, alpha=0.15)

    ax.grid(True, which='both', linestyle='--', linewidth=0.5)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    ax.set_xlim(left=0, right=max(10, len(history) - 1))
    ax.set_ylim(bottom=1, top=max(2.0, np.max(y_values) * 1.1))

    ax.set_xlabel("Thời gian", fontsize=10)
    ax.set_ylabel("Hệ số", fontsize=10)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f'{y:.2f}x'))

    if not is_crashed:
        ax.set_title(
            f"{current_multiplier:.2f}x", fontsize=18, color=color, weight='bold'
        )

    buf = io.BytesIO()
    plt.savefig(buf, format='png', transparent=True, bbox_inches='tight', pad_inches=0.1)
    plt.close(fig)
    buf.seek(0)
    return buf

def _add_busted_overlay(image: Image.Image) -> Image.Image:
    """Adds a 'BUSTED!' overlay to the image."""
    overlay = Image.new("RGBA", image.size, (200, 20, 20, 80))
    draw = ImageDraw.Draw(overlay)

    font_size = int(image.height / 4)
    try:
        # Try to find a system font, otherwise fall back to default
        font = ImageFont.truetype("arial.ttf", size=font_size)
    except IOError:
        font = ImageFont.load_default()

    text = "BUSTED!"
    text_pos = (image.width / 2, image.height / 2)
    outline_color = "black"

    # Draw outline
    for x_offset in [-2, 0, 2]:
        for y_offset in [-2, 0, 2]:
            if x_offset != 0 or y_offset != 0:
                draw.text(
                    (text_pos[0] + x_offset, text_pos[1] + y_offset),
                    text, font=font, fill=outline_color, anchor="mm"
                )

    draw.text(text_pos, text, font=font, fill="white", anchor="mm")

    return Image.alpha_composite(image, overlay)

def generate_graph_image(history: list, current_multiplier: float, is_crashed: bool = False) -> io.BytesIO:
    """
    Generates a PNG image of the crash graph with a professional look.
    """
    if not history:
        history = [1.0]

    buf = _plot_graph_to_buffer(history, current_multiplier, is_crashed)
    image = Image.open(buf).convert("RGBA")

    if is_crashed:
        image = _add_busted_overlay(image)

    # Save the final image back to a new buffer
    final_buf = io.BytesIO()
    image.save(final_buf, 'PNG')
    final_buf.seek(0)

    return final_buf