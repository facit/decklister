import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter


class CountOverlay:
    """
    Strategy for drawing a card count overlay on a card image.
    Default implementation: blur the bottom portion and draw outlined text.
    Subclass and override apply() to change the style.
    """

    def __init__(self, count_background=None, blur_fraction=0.15, font_size_ratio=0.2):
        """
        Args:
            count_background: Path to an image to use behind the count text (optional).
            blur_fraction: Fraction of card height to blur at the bottom.
            font_size_ratio: Font size as a fraction of card width.
        """
        self.count_background = count_background
        self.blur_fraction = blur_fraction
        self.font_size_ratio = font_size_ratio

    def apply(self, card_img, count):
        """
        Draw the count overlay on a card image. Modifies card_img in place.

        Args:
            card_img: PIL Image of the card.
            count: Integer count to display.

        Returns:
            The modified card image.
        """
        if count <= 0:
            return card_img

        card_width, card_height = card_img.size
        blur_height = int(card_height * self.blur_fraction)

        # Only blur bottom area if there's no count_background to provide contrast
        if blur_height > 0 and not self.count_background:
            blur_box = (0, card_height - blur_height, card_width, card_height)
            blurred = card_img.crop(blur_box).filter(ImageFilter.GaussianBlur(radius=6))
            card_img.paste(blurred, (0, card_height - blur_height))

        # Draw optional count background image and get its bounds
        bg_bounds = self._draw_count_background(card_img, card_width, card_height)

        # Load font
        font_size = max(10, int(card_width * self.font_size_ratio))
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except Exception:
            font = ImageFont.load_default()

        # Measure text
        draw = ImageDraw.Draw(card_img)
        text = str(count)
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        # bbox may not start at (0,0) due to font metrics — track the offset
        bbox_offset_x = bbox[0]
        bbox_offset_y = bbox[1]

        # Position text: center on count_background if present, otherwise in blurred area
        if bg_bounds:
            bg_x, bg_y, bg_w, bg_h = bg_bounds
            text_x = bg_x + (bg_w - text_width) // 2 - bbox_offset_x
            text_y = bg_y + (bg_h - text_height) // 2 - bbox_offset_y
        else:
            text_x = (card_width - text_width) // 2 - bbox_offset_x
            text_y = card_height - blur_height + (blur_height - text_height) // 2 - bbox_offset_y

        # Draw outlined text
        outline_range = 2
        for ox in range(-outline_range, outline_range + 1):
            for oy in range(-outline_range, outline_range + 1):
                if ox == 0 and oy == 0:
                    continue
                draw.text((text_x + ox, text_y + oy), text, font=font, fill=(0, 0, 0))
        draw.text((text_x, text_y), text, font=font, fill=(255, 255, 255))

        return card_img

    def _draw_count_background(self, card_img, card_width, card_height):
        """
        Draw the count background image if configured.

        Returns:
            (x, y, width, height) of the pasted background, or None.
        """
        if self.count_background is None:
            return None
        if not isinstance(self.count_background, str) or not os.path.isfile(self.count_background):
            return None

        try:
            with Image.open(self.count_background) as bg_img:
                orig_w, orig_h = bg_img.size
                if orig_h == 0:
                    return None
                ar = orig_w / orig_h
                target_height = int(card_width / 4)
                target_width = int(target_height * ar)
                bg_resized = bg_img.resize((target_width, target_height))
                paste_x = (card_width - target_width) // 2
                paste_y = card_height - target_height
                card_img.paste(
                    bg_resized,
                    (paste_x, paste_y),
                    bg_resized.convert("RGBA"),
                )
                return (paste_x, paste_y, target_width, target_height)
        except Exception:
            return None
