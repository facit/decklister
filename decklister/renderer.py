import os
from PIL import Image, ImageDraw
try:
    from .count_overlay import CountOverlay
except ImportError:
    from decklister.count_overlay import CountOverlay

# Corner radius measured at the source image resolution (1117x1560)
SOURCE_CORNER_RADIUS = 46
SOURCE_IMAGE_HEIGHT = 1560


class Renderer:
    """
    Composes the final deck image by layering:
    1. Background (solid color or image)
    2. Leader cards in leader_areas
    3. Base cards in base_areas
    4. Deck cards in deck_area grid
    5. Sideboard cards in sb_area grid
    6. Foreground overlay (alpha-composited on top)
    """

    def __init__(self, config, count_overlay=None):
        self.config = config
        self.count_overlay = count_overlay or CountOverlay(
            count_background=config.count_background
        )

    def render(self, deck, deck_layout, sb_layout):
        """
        Render the full deck image.

        Args:
            deck: Deck object.
            deck_layout: (card_width, card_height, cols, rows) for deck_area, or None.
            sb_layout: (card_width, card_height, cols, rows) for sb_area, or None.

        Returns:
            PIL Image of the final composed deck image.
        """
        img_width, img_height = self.config.resolution
        background = self._create_background(img_width, img_height)

        self._draw_leaders(background, deck)
        self._draw_bases(background, deck)

        if deck_layout and self.config.deck_area:
            self._draw_card_grid(
                background, deck.main_deck, self.config.deck_area, deck_layout
            )

        if sb_layout and self.config.sb_area:
            self._draw_card_grid(
                background, deck.sideboard, self.config.sb_area, sb_layout
            )

        background = self._apply_foreground(background)

        return background

    def _create_background(self, width, height):
        """Create the background image from config."""
        default_color = (30, 30, 30)
        bg = self.config.background

        if bg is None:
            return Image.new("RGB", (width, height), default_color)

        if isinstance(bg, str):
            try:
                return Image.open(bg).convert("RGB").resize((width, height))
            except Exception:
                return Image.new("RGB", (width, height), default_color)

        if isinstance(bg, (tuple, list)) and len(bg) == 3:
            return Image.new("RGB", (width, height), tuple(bg))

        return Image.new("RGB", (width, height), default_color)

    def _draw_leaders(self, background, deck):
        """Place leader cards into their designated areas."""
        areas = self.config.leader_areas or []
        for i, leader in enumerate(deck.leaders):
            if i >= len(areas):
                break
            self._draw_special_card(background, leader, areas[i])

    def _draw_bases(self, background, deck):
        """Place base cards into their designated areas."""
        areas = self.config.base_areas or []
        for i, base in enumerate(deck.bases):
            if i >= len(areas):
                break
            self._draw_special_card(background, base, areas[i])

    def _draw_special_card(self, background, card, area):
        """Load and paste a single card (leader/base) into an area, preserving aspect ratio."""
        x0, y0, x1, y1 = area
        area_width, area_height = x1 - x0, y1 - y0
        if area_width <= 0 or area_height <= 0:
            print(f"Skipping card {card} — area {area} has invalid dimensions ({area_width}x{area_height})")
            return
        img_path = self._card_image_path(card)
        try:
            card_img = Image.open(img_path).convert("RGBA")
            orig_w, orig_h = card_img.size
            if orig_w <= 0 or orig_h <= 0:
                return

            # Apply rounded corners at source resolution (pixel-perfect)
            card_img = self._apply_rounded_corners(card_img)

            # Fit within the area while preserving aspect ratio
            scale = min(area_width / orig_w, area_height / orig_h)
            new_w = int(orig_w * scale)
            new_h = int(orig_h * scale)
            card_img = card_img.resize((new_w, new_h), Image.LANCZOS)

            # Center within the area and composite
            paste_x = x0 + (area_width - new_w) // 2
            paste_y = y0 + (area_height - new_h) // 2
            background_rgba = background.convert("RGBA")
            background_rgba.paste(card_img, (paste_x, paste_y), card_img)
            background.paste(background_rgba.convert("RGB"))
        except Exception as e:
            print(f"Failed to load {img_path}: {e}")

    def _draw_card_grid(self, background, cards, area, layout):
        """
        Draw a list of cards in a grid within the given area.

        Args:
            background: PIL Image to draw onto.
            cards: List of Card objects.
            area: (x0, y0, x1, y1) rectangle for the grid.
            layout: (card_width, card_height, cols, rows, padding) from CardSizer.
        """
        x0, y0, x1, y1 = area
        card_width, card_height, cols, rows, padding = layout
        background_rgba = background.convert("RGBA")

        for i, card in enumerate(cards):
            col = i % cols
            row = i // cols
            x = x0 + col * (card_width + padding)
            y = y0 + row * (card_height + padding)

            card_img = self._load_card_image(card, card_width, card_height)
            card_img = self.count_overlay.apply(card_img, card.count)

            # Convert to RGBA if not already (count_overlay may return RGB)
            if card_img.mode != "RGBA":
                card_img = card_img.convert("RGBA")
            background_rgba.paste(card_img, (x, y), card_img)

        background.paste(background_rgba.convert("RGB"))

    def _load_card_image(self, card, width, height):
        """Load a card image, apply rounded corners at source resolution, then resize."""
        img_path = self._card_image_path(card)
        try:
            img = Image.open(img_path).convert("RGBA")
            img = self._apply_rounded_corners(img)
            return img.resize((width, height), Image.LANCZOS)
        except Exception as e:
            print(f"Failed to load {img_path}: {e}")
            return Image.new("RGBA", (width, height), (80, 80, 80, 255))

    def _apply_rounded_corners(self, img):
        """
        Apply a rounded corner alpha mask to an image.
        If the image already has meaningful transparency in the corners,
        skip masking and use the existing alpha.
        The radius is calculated from the known source dimensions.
        Uses supersampling for smooth anti-aliased edges.
        """
        w, h = img.size

        # Check if corners already have transparency
        if img.mode == "RGBA":
            corner_pixels = [
                img.getpixel((0, 0)),
                img.getpixel((w - 1, 0)),
                img.getpixel((0, h - 1)),
                img.getpixel((w - 1, h - 1)),
            ]
            if all(p[3] < 128 for p in corner_pixels):
                return img

        long_side = max(w, h)
        radius = max(1, int(SOURCE_CORNER_RADIUS * long_side / SOURCE_IMAGE_HEIGHT))

        # Draw circle at 4x resolution for smooth anti-aliasing
        scale = 4
        big_r = radius * scale
        circle_big = Image.new("L", (big_r * 2, big_r * 2), 0)
        draw = ImageDraw.Draw(circle_big)
        draw.ellipse((0, 0, big_r * 2 - 1, big_r * 2 - 1), fill=255)
        # Downscale to actual radius size
        circle = circle_big.resize((radius * 2, radius * 2), Image.LANCZOS)

        alpha = Image.new("L", (w, h), 255)
        # Top-left
        alpha.paste(circle.crop((0, 0, radius, radius)), (0, 0))
        # Top-right
        alpha.paste(circle.crop((radius, 0, radius * 2, radius)), (w - radius, 0))
        # Bottom-left
        alpha.paste(circle.crop((0, radius, radius, radius * 2)), (0, h - radius))
        # Bottom-right
        alpha.paste(circle.crop((radius, radius, radius * 2, radius * 2)), (w - radius, h - radius))

        img.putalpha(alpha)
        return img

    def _card_image_path(self, card):
        """Build the file path for a card image."""
        return os.path.join("images", card.card_set, f"{card.card_number}.png")

    def _apply_foreground(self, background):
        """Composite the foreground image on top if configured."""
        fg = self.config.foreground
        if not fg or not isinstance(fg, str):
            return background
        try:
            fg_img = Image.open(fg).convert("RGBA").resize(background.size)
            background = background.convert("RGBA")
            background.alpha_composite(fg_img)
            return background.convert("RGB")
        except Exception:
            return background
