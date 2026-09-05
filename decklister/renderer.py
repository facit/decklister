import os
from PIL import Image, ImageDraw, ImageFont
try:
    from .count_overlay import CountOverlay
    from .app_paths import get_image_cache_dir
except ImportError:
    from decklister.count_overlay import CountOverlay
    from decklister.app_paths import get_image_cache_dir

# Corner radius measured at the source image resolution (1117x1560)
SOURCE_CORNER_RADIUS = 46
SOURCE_IMAGE_HEIGHT = 1560


class Renderer:
    """
    Composes the final deck image by processing config.layers in order.
    Each layer is one of:
      - {"type": "image", "path": "...", "area": [x0,y0,x1,y1]}  (area optional)
      - {"type": "color", "color": [r, g, b]}  (or [r, g, b, a])
      - {"type": "cards"}  — renders leaders, bases, deck grid, sideboard

    Shorthands accepted in config:
      - A bare string  →  {"type": "image", "path": ...}
      - A [r,g,b] list →  {"type": "color", "color": ...}
    """

    def __init__(self, config, count_overlay=None):
        self.config = config
        self.count_overlay = count_overlay or CountOverlay(
            count_background=config.count_background,
            font_path=config.count_font,
        )

    def render(self, deck, deck_layout, sb_layout):
        """
        Render the full deck image.

        Args:
            deck: Deck object.
            deck_layout: (card_width, card_height, cols, rows, padding) for deck_area, or None.
            sb_layout: (card_width, card_height, cols, rows, padding) for sb_area, or None.

        Returns:
            PIL Image (RGB) of the final composed deck image.
        """
        img_width, img_height = self.config.resolution

        # Start transparent if transparent_background is enabled, else opaque dark
        if getattr(self.config, "transparent_background", False):
            canvas = Image.new("RGBA", (img_width, img_height), (0, 0, 0, 0))
        else:
            canvas = Image.new("RGBA", (img_width, img_height), (30, 30, 30, 255))

        for layer in self.config.layers:
            layer_type, layer_data = self._parse_layer(layer)
            if layer_type == "color":
                fill = Image.new("RGBA", (img_width, img_height), layer_data)
                canvas.alpha_composite(fill)
            elif layer_type == "image":
                self._apply_image_layer(canvas, layer_data["path"], layer_data.get("area"))
            elif layer_type == "cards":
                self._draw_image_areas(canvas)
                self._draw_leaders(canvas, deck)
                self._draw_bases(canvas, deck)
                if deck_layout and self.config.deck_area:
                    self._draw_card_grid(canvas, deck.main_deck, self.config.deck_area, deck_layout)
                if sb_layout and self.config.sb_area:
                    self._draw_card_grid(canvas, deck.sideboard, self.config.sb_area, sb_layout)
            elif layer_type == "text":
                self._draw_text_layer(canvas, layer_data, text=layer_data.get("text", ""))
            elif layer_type == "csv_field":
                column = layer_data.get("column", "")
                meta = deck.metadata or {}
                if column == "DeckName":
                    text = meta.get("AdminGivenName") or meta.get("Name", "")
                else:
                    text = meta.get(column, f"[{column}]")
                self._draw_text_layer(canvas, layer_data, text=text)

        # Keep alpha if transparent background requested, else flatten to RGB
        if getattr(self.config, "transparent_background", False):
            return canvas
        return canvas.convert("RGB")

    def _parse_layer(self, layer):
        """
        Normalize a layer spec to (type, data).

        Returns one of:
          ("image",  {"path": str, "area": list|None})
          ("color",  (r, g, b, a))
          ("cards",  None)
          (None,     None)   — unrecognised, will be skipped
        """
        # Shorthand: bare string → image layer
        if isinstance(layer, str):
            return ("image", {"path": layer, "area": None})

        # Shorthand: [r, g, b] → color layer
        if isinstance(layer, (list, tuple)):
            if len(layer) == 3 and all(isinstance(x, int) for x in layer):
                return ("color", (*layer, 255))
            if len(layer) == 4 and all(isinstance(x, int) for x in layer):
                return ("color", tuple(layer))

        if isinstance(layer, dict):
            t = layer.get("type")
            if t == "image":
                return ("image", {"path": layer["path"], "area": layer.get("area")})
            if t == "color":
                c = layer["color"]
                if len(c) == 3:
                    return ("color", (c[0], c[1], c[2], 255))
                return ("color", tuple(c))
            if t == "cards":
                return ("cards", None)
            if t == "text":
                return ("text", layer)
            if t == "csv_field":
                return ("csv_field", layer)

        return (None, None)

    def _draw_text_layer(self, canvas, data, text):
        """Draw text onto the canvas at a position or within an area."""
        color = data.get("color", [255, 255, 255])
        color = tuple(color) if len(color) == 4 else (*color, 255)
        size = data.get("size", 48)
        align = data.get("align", "left")

        font_path = data.get("font")
        try:
            font = ImageFont.truetype(font_path, size) if font_path else ImageFont.load_default(size=size)
        except Exception:
            font = ImageFont.load_default()

        draw = ImageDraw.Draw(canvas)
        area = data.get("area")
        position = data.get("position")

        if area:
            x0, y0, x1, y1 = area
            if align == "center":
                x, anchor = (x0 + x1) // 2, "mt"
            elif align == "right":
                x, anchor = x1, "rt"
            else:
                x, anchor = x0, "lt"
            draw.text((x, y0), text, font=font, fill=color, anchor=anchor)
        elif position:
            draw.text(tuple(position), text, font=font, fill=color, anchor="lt")
        else:
            draw.text((0, 0), text, font=font, fill=color)

    def _apply_image_layer(self, canvas, path, area=None):
        """
        Composite an RGBA image onto the canvas.

        If area is None the image fills the full canvas.
        If area is [x0, y0, x1, y1] the image is stretched to that rectangle.
        """
        try:
            img = Image.open(path).convert("RGBA")
            if area is None:
                img = img.resize(canvas.size, Image.LANCZOS)
                canvas.alpha_composite(img)
            else:
                x0, y0, x1, y1 = area
                w, h = x1 - x0, y1 - y0
                if w <= 0 or h <= 0:
                    print(f"Skipping layer {path} — area {area} has invalid dimensions ({w}x{h})")
                    return
                img = img.resize((w, h), Image.LANCZOS)
                canvas.alpha_composite(img, (x0, y0))
        except Exception as e:
            print(f"Failed to load layer image {path}: {e}")

    def _draw_leaders(self, canvas, deck):
        """Place leader cards into their designated areas."""
        areas = self.config.leader_areas or []
        for i, leader in enumerate(deck.leaders):
            if i >= len(areas):
                break
            self._draw_special_card(canvas, leader, areas[i])

    def _draw_bases(self, canvas, deck):
        """Place base cards into their designated areas."""
        areas = self.config.base_areas or []
        for i, base in enumerate(deck.bases):
            if i >= len(areas):
                break
            self._draw_special_card(canvas, base, areas[i])

    def _draw_image_areas(self, canvas):
        """Render image_areas: load each image and fit within its area, preserving aspect ratio."""
        for entry in self.config.image_areas or []:
            area = entry.get("area")
            image_path = entry.get("image")
            if not area or not image_path:
                continue
            x0, y0, x1, y1 = area
            area_width, area_height = x1 - x0, y1 - y0
            if area_width <= 0 or area_height <= 0:
                continue
            try:
                img = Image.open(image_path).convert("RGBA")
                orig_w, orig_h = img.size
                if orig_w <= 0 or orig_h <= 0:
                    continue
                scale = min(area_width / orig_w, area_height / orig_h)
                new_w = int(orig_w * scale)
                new_h = int(orig_h * scale)
                img = img.resize((new_w, new_h), Image.LANCZOS)
                paste_x = x0 + (area_width - new_w) // 2
                paste_y = y0 + (area_height - new_h) // 2
                canvas.alpha_composite(img, (paste_x, paste_y))
            except Exception as e:
                print(f"Failed to load image area {image_path}: {e}")

    def _draw_special_card(self, canvas, card, area):
        """Load and composite a single card (leader/base) into an area, preserving aspect ratio."""
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
            canvas.alpha_composite(card_img, (paste_x, paste_y))
        except Exception as e:
            print(f"Failed to load {img_path}: {e}")

    def _draw_card_grid(self, canvas, cards, area, layout):
        """
        Draw a list of cards in a grid within the given area.

        Args:
            canvas: RGBA PIL Image to draw onto.
            cards: List of Card objects.
            area: (x0, y0, x1, y1) rectangle for the grid.
            layout: (card_width, card_height, cols, rows, padding) from CardSizer.
        """
        x0, y0, x1, y1 = area
        card_width, card_height, cols, rows, padding = layout

        # Card name settings
        cn = self.config.card_names
        show_names = cn.get("enabled", False)
        name_position = cn.get("position", "below")
        name_size = cn.get("size", 14)
        name_color = tuple(cn.get("color", [255, 255, 255]))
        if len(name_color) == 3:
            name_color = (*name_color, 255)

        name_font = None
        if show_names:
            font_path = cn.get("font")
            try:
                name_font = ImageFont.truetype(font_path, name_size) if font_path else ImageFont.load_default(size=name_size)
            except Exception:
                try:
                    name_font = ImageFont.truetype("arial.ttf", name_size)
                except Exception:
                    name_font = ImageFont.load_default()

        # Calculate cell size (card + label space)
        draw = ImageDraw.Draw(canvas)

        # Calculate actual label dimensions from card names
        label_height = 0
        label_width = 0
        if show_names and name_font:
            if name_position in ("below", "above"):
                max_h = 0
                for card in cards:
                    if card.name:
                        bbox = draw.textbbox((0, 0), card.name, font=name_font)
                        max_h = max(max_h, bbox[3] - bbox[1])
                label_height = max_h + 6 if max_h else name_size + 4
            elif name_position in ("left", "right"):
                max_w = 0
                for card in cards:
                    if card.name:
                        bbox = draw.textbbox((0, 0), card.name, font=name_font)
                        max_w = max(max_w, bbox[2] - bbox[0])
                label_width = max_w + 6 if max_w else name_size * 5

        cell_width = card_width + label_width
        cell_height = card_height + label_height

        for i, card in enumerate(cards):
            col = i % cols
            row = i // cols
            cell_x = x0 + col * (cell_width + padding)
            cell_y = y0 + row * (cell_height + padding)

            # Determine card position within cell
            if name_position == "above":
                card_x = cell_x + label_width // 2
                card_y = cell_y + label_height
            elif name_position == "left":
                card_x = cell_x + label_width
                card_y = cell_y
            else:  # below, right, overlay-top, overlay-bottom
                card_x = cell_x
                card_y = cell_y

            card_img = self._load_card_image(card, card_width, card_height)
            if getattr(self.config, "show_counts", True):
                card_img = self.count_overlay.apply(card_img, card.count)

            if card_img.mode != "RGBA":
                card_img = card_img.convert("RGBA")
            canvas.alpha_composite(card_img, (card_x, card_y))

            # Draw card name
            if show_names and card.name and name_font:
                self._draw_card_name(draw, card.name, card_x, card_y,
                                     card_width, card_height, name_position,
                                     name_font, name_color, label_height, label_width)

    def _draw_card_name(self, draw, name, card_x, card_y, card_w, card_h,
                        position, font, color, label_height, label_width):
        """Draw a card name at the specified position relative to the card."""
        # Use PIL's anchor parameter for precise alignment.
        # Anchor codes: horizontal (l/m/r) + vertical (a/m/d = ascender/middle/descender)
        if position == "below":
            tx = card_x + card_w // 2
            ty = card_y + card_h + 2
            anchor = "ma"  # middle-ascender (top-centered)
        elif position == "above":
            tx = card_x + card_w // 2
            ty = card_y - 2
            anchor = "md"  # middle-descender (bottom-centered)
        elif position == "left":
            tx = card_x - 4
            ty = card_y + card_h // 2
            anchor = "rm"  # right-middle
        elif position == "right":
            tx = card_x + card_w + 4
            ty = card_y + card_h // 2
            anchor = "lm"  # left-middle
        elif position == "overlay-top":
            tx = card_x + card_w // 2
            ty = card_y + 4
            anchor = "ma"
        elif position == "overlay-bottom":
            tx = card_x + card_w // 2
            ty = card_y + card_h - 4
            anchor = "md"
        else:
            return

        # Draw with outline for readability
        for ox in range(-1, 2):
            for oy in range(-1, 2):
                if ox == 0 and oy == 0:
                    continue
                draw.text((tx + ox, ty + oy), name, font=font, fill=(0, 0, 0, 255), anchor=anchor)
        draw.text((tx, ty), name, font=font, fill=color, anchor=anchor)

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
        return os.path.join(get_image_cache_dir(), card.card_set, f"{card.card_number}.png")
