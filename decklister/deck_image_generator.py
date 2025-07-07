import os
from decklister.deck import Deck
import decklister.image_downloader as ImageDownloader
from decklister.layout_manager import LayoutManager
from decklister.background_manager import BackgroundManager
from decklister.config import Config
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from PIL import ImageDraw

class DeckImageGenerator:
    def __init__(self, config=None, blur_count_area=True):
        # Initialize configuration, background manager, layout manager, and blur option
        self.config = config or Config()
        self.background_manager = BackgroundManager(self.config)
        self.layout_manager = LayoutManager(self.config)
        self.blur_count_area = blur_count_area

    def run(self, deck_file):
        # Main entry point: loads deck, downloads images, and renders the deck image
        if not deck_file:
            print("No deck file provided.")
            return

        # Load the deck from a JSON file
        try:
            deck = Deck.from_json_file(deck_file)
        except Exception as e:
            print(f"Error loading deck: {e}")
            return

        # Load the background image at the configured resolution
        self.background_manager.load_background(self.config.resolution)

        # Download images for all cards in the main deck and sideboard
        for card in deck.main_deck + deck.sideboard:
            # Card identifiers are split into set and number (e.g., "[Set]_[Number]")
            ImageDownloader.download_images(card.card_set, card.card_number)

        # Render the final deck image
        self.render_image(deck)

        # print("Stub: Finished minimal run.")

    def render_image(self, deck):
        # Render the deck image with all cards placed and counts overlaid

        # Gather all unique cards from main deck and sideboard
        unique_cards = deck.main_deck + deck.sideboard
        num_cards = len(deck.main_deck) + len(deck.sideboard)

        # Get image dimensions from config
        img_width, img_height = self.config.resolution

        # Define forbidden areas for card placement (frame around the image)
        frame_thickness = 55

        self._prepare_forbidden_areas(img_width, img_height, frame_thickness)
        aspect_ratio = 5.0 / 7.0  # Standard card width/height ratio
        padding = 3

        # Find optimal card size and layout
        card_width, card_height, cards_per_row = self._find_optimal_card_size(
            num_cards, aspect_ratio, padding
        )

        # print("***************************************************************")
        # print(card_width)
        # print(card_height)
        # print(cards_per_row)
        # print("***************************************************************")

        # Create the background image
        background = self.background_manager.load_background((img_width, img_height))

        # Calculate card positions using the layout manager (avoids forbidden areas)
        positions = self.layout_manager.calculate_layout(
            self.config.deck_area,
            self.config.sb_area,
            deck,
            card_width,
            card_height,
            cards_per_row,
            padding,
            frame_thickness,
        )

        if positions is None:
            return

        # print(f"Number of unique cards: {len(unique_cards)}")
        # print(f"Image size: {img_width}x{img_height}")
        # print(f"Card size: {card_width}x{card_height}, cards per row: {cards_per_row}")
        # print(f"Positions calculated: {len(positions)}")
        # print(f"Forbidden areas: {self.config.forbidden_areas}")

        # Place each card image at its calculated position
        card_images_dir = "images"
        for i, (card, (x, y)) in enumerate(zip(unique_cards, positions)):
            img_path = f"{card_images_dir}/{card.card_set}/{card.card_number}.png"
            # print(f"Placing card {i}: {img_path} at ({x}, {y})")
            try:
                # Load and resize the card image
                if not os.path.isfile(img_path):
                    print(f"File does not exist: {img_path}")
                # print(card_width, card_height)
                card_img = Image.open(img_path).resize((card_width, card_height))
            except Exception as e:
                print(f"Failed to load {img_path}: {e}")
                # Use a placeholder if the image is missing
                card_img = Image.new("RGB", (card_width, card_height), (80, 80, 80))

            # Optionally blur the bottom area of the card for the count overlay
            blur_fraction = 0.15  # Bottom 15% of the card
            blur_height = int(card_height * blur_fraction)
            if self.blur_count_area:
                blur_box = (0, card_height - blur_height, card_width, card_height)
                card_img_blur = card_img.crop(blur_box).filter(ImageFilter.GaussianBlur(radius=6))
                card_img.paste(card_img_blur, (0, card_height - blur_height))

            # Draw the card count (centered in the blurred area)
            draw = ImageDraw.Draw(card_img)
            try:
                font = ImageFont.truetype("arial.ttf", 40)
            except Exception:
                font = ImageFont.load_default()
            text = str(card.count)
            try:
                text_width, text_height = font.getsize(text)
            except AttributeError:
                # Fallback for PIL versions without getsize
                bbox = draw.textbbox((0, 0), text, font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]

            # Calculate y-position for the text (centered in blurred area or above bottom)
            if self.blur_count_area:
                text_y = card_height - blur_height + (blur_height - text_height) // 2
            else:
                text_y = card_height - text_height - 15  # 15px above the bottom

            text_x = (card_width - text_width) // 2

            # Draw black outline for better readability
            outline_range = 2  # Outline thickness
            for ox in range(-outline_range, outline_range + 1):
                for oy in range(-outline_range, outline_range + 1):
                    if ox == 0 and oy == 0:
                        continue
                    draw.text((text_x + ox, text_y + oy), text, font=font, fill=(0, 0, 0))
            # Draw white text on top
            draw.text((text_x, text_y), text, font=font, fill=(255, 255, 255))

            # Paste the card image onto the background at the calculated position
            background.paste(card_img, (x, y))

        # Place leader card
        if deck.leader_card is not None and self.config.leader_area:
            lx0, ly0, lx1, ly1 = self.config.leader_area
            leader_width, leader_height = lx1 - lx0, ly1 - ly0
            leader_filename = f"{card_images_dir}/{deck.leader_card.card_set}/{deck.leader_card.card_number}.png"
            # print(f"Loading leader card from {leader_filename}")
            leader_img = Image.open(leader_filename).resize((leader_width, leader_height))
            background.paste(leader_img, (lx0, ly0))

        # Place base card
        if deck.base_card is not None and self.config.base_area:
            bx0, by0, bx1, by1 = self.config.base_area
            base_width, base_height = bx1 - bx0, by1 - by0
            base_filename = f"{card_images_dir}/{deck.base_card.card_set}/{deck.base_card.card_number}.png"
            # print(f"Loading base card from {base_filename}")
            # check that files exists and if not, use image_downloader to download it
            if not os.path.exists(base_filename):
                ImageDownloader.download_images(deck.base_card.card_set, deck.base_card.card_number)
            base_img = Image.open(base_filename).resize((base_width, base_height))
            background.paste(base_img, (bx0, by0))

        # After all cards have been pasted onto 'background'
        if self.config and getattr(self.config, "foreground", None):
            fg = self.config.foreground
            if isinstance(fg, str):
                try:
                    fg_img = Image.open(fg).convert("RGBA").resize(background.size)
                    background = background.convert("RGBA")
                    background.alpha_composite(fg_img)
                    background = background.convert("RGB")
                except Exception:
                    pass  # Ignore foreground if loading fails

        # Save the final deck image
        background.save("deck_output.png")
        print("Deck image saved as deck_output.png")

    def _prepare_forbidden_areas(self, img_width, img_height, frame_thickness):
        frame_forbidden_areas = [
            [0, 0, img_width, frame_thickness],
            [0, img_height - frame_thickness, img_width, img_height],
            [0, 0, frame_thickness, img_height],
            [img_width - frame_thickness, 0, img_width, img_height],
        ]
        all_forbidden_areas = list(self.config.forbidden_areas)
        if self.config.leader_area:
            all_forbidden_areas.append(self.config.leader_area)
        if self.config.base_area:
            all_forbidden_areas.append(self.config.base_area)
        all_forbidden_areas += frame_forbidden_areas
        self.config.forbidden_areas = all_forbidden_areas

    def _find_optimal_card_size(self, num_cards, card_aspect_ratio, padding):
        """
        Calculates the largest possible card size that fits all cards in the available area.
        Uses the relationship: num_rows = num_cols * card_aspect_ratio.
        """
        avail_width = self.config.deck_area[2] - self.config.deck_area[0]
        avail_height = self.config.deck_area[3] - self.config.deck_area[1]

        # print(avail_width)
        # print(avail_height)

        max_card_width = 300
        max_card_height = int(max_card_width / card_aspect_ratio)
        num_cols = 0
        num_rows = 0
        card_width = max_card_width
        card_height = max_card_height

        # calculate card_width and card_height by making sure it always fits in the deck area
        while(True):
            num_cols = int(avail_width / card_width)
            num_rows = int(avail_height / card_height)
            total_cards_width = num_cols * card_width + (num_cols - 1) * padding
            total_cards_height = num_rows * card_height + (num_rows - 1) * padding
            if num_cols * num_rows >= num_cards and total_cards_height <= avail_height and total_cards_width <= avail_width:
                # print(num_cols)
                # print(num_rows)
                break
            else:
                card_width -= 1
                card_height = int(card_width / card_aspect_ratio)


        # print(card_width, card_height)

        return card_width, card_height, num_cols

        # return best_card_width, best_card_height, best_cols


    # def _find_optimal_card_size(self, deck, num_cards, img_width, img_height, frame_thickness, card_aspect_ratio, padding):
    #     """
    #     Finds the largest card size that allows all cards to fit, by:
    #     1. Trying the largest possible card size.
    #     2. For each card size, trying all possible column counts.
    #     3. If a layout fits, returns the card size and columns.
    #     4. If not, reduces card size and repeats.
    #     """
        
    #     min_card_width = 50
    #     avail_width = img_width - 2 * frame_thickness
    #     avail_height = img_height - 2 * frame_thickness

    #     # Start with the largest possible card width that could fit at least one card per row
    #     max_card_width = avail_width
    #     for card_width in range(max_card_width, min_card_width - 1, -1):
    #         card_height = int(card_width / card_aspect_ratio)
    #         if card_height < min_card_width:
    #             continue  # Skip if height is too small

    #         for cols in range(1, num_cards + 1):
    #             rows = int(cols * card_aspect_ratio)
    #             if cols * rows < num_cards:
    #                 continue  # Not enough cards can fit in this layout
    #             total_width = cols * card_width + (cols - 1) * padding
    #             total_height = rows * card_height + (rows - 1) * padding

    #             if total_width > avail_width or total_height > avail_height:
    #                 break

    #             return card_width, card_height, cols

    #     # If no layout found, raise error
    #     print("ERROR: Could not fit all cards even at minimal size.")
    #     raise RuntimeError("Could not fit all cards even at minimal size.")

    def _draw_cards(self, background, unique_cards, positions, card_width, card_height):
        card_images_dir = "images"
        for i, (card, (x, y)) in enumerate(zip(unique_cards, positions)):
            img_path = f"{card_images_dir}/{card.card_set}/{card.card_number}.png"
            # print(f"Placing card {i}: {img_path} at ({x}, {y})")
            try:
                # Load and resize the card image
                if not os.path.isfile(img_path):
                    print(f"File does not exist: {img_path}")
                # print(card_width, card_height)
                card_img = Image.open(img_path).resize((card_width, card_height))
            except Exception as e:
                print(f"Failed to load {img_path}: {e}")
                # Use a placeholder if the image is missing
                card_img = Image.new("RGB", (card_width, card_height), (80, 80, 80))

            # Optionally blur the bottom area of the card for the count overlay
            blur_fraction = 0.15  # Bottom 15% of the card
            blur_height = int(card_height * blur_fraction)
            if self.blur_count_area:
                blur_box = (0, card_height - blur_height, card_width, card_height)
                card_img_blur = card_img.crop(blur_box).filter(ImageFilter.GaussianBlur(radius=6))
                card_img.paste(card_img_blur, (0, card_height - blur_height))

            # Draw the card count (centered in the blurred area)
            draw = ImageDraw.Draw(card_img)
            try:
                font = ImageFont.truetype("arial.ttf", 40)
            except Exception:
                font = ImageFont.load_default()
            text = str(card.count)
            try:
                text_width, text_height = font.getsize(text)
            except AttributeError:
                # Fallback for PIL versions without getsize
                bbox = draw.textbbox((0, 0), text, font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]

            # Calculate y-position for the text (centered in blurred area or above bottom)
            if self.blur_count_area:
                text_y = card_height - blur_height + (blur_height - text_height) // 2
            else:
                text_y = card_height - text_height - 15  # 15px above the bottom

            text_x = (card_width - text_width) // 2

            # Draw black outline for better readability
            outline_range = 2  # Outline thickness
            for ox in range(-outline_range, outline_range + 1):
                for oy in range(-outline_range, outline_range + 1):
                    if ox == 0 and oy == 0:
                        continue
                    draw.text((text_x + ox, text_y + oy), text, font=font, fill=(0, 0, 0))
            # Draw white text on top
            draw.text((text_x, text_y), text, font=font, fill=(255, 255, 255))

            # Paste the card image onto the background at the calculated position
            background.paste(card_img, (x, y))

    def _draw_leader_and_base(self, background, deck):
        card_images_dir = "images"
        # Place leader card
        if deck.leader_card is not None and self.config.leader_area:
            lx0, ly0, lx1, ly1 = self.config.leader_area
            leader_width, leader_height = lx1 - lx0, ly1 - ly0
            leader_filename = f"{card_images_dir}/{deck.leader_card.card_set}/{deck.leader_card.card_number}.png"
            print(f"Loading leader card from {leader_filename}")
            leader_img = Image.open(leader_filename).resize((leader_width, leader_height))
            background.paste(leader_img, (lx0, ly0))

        # Place base card
        if deck.base_card is not None and self.config.base_area:
            bx0, by0, bx1, by1 = self.config.base_area
            base_width, base_height = bx1 - bx0, by1 - by0
            base_filename = f"{card_images_dir}/{deck.base_card.card_set}/{deck.base_card.card_number}.png"
            print(f"Loading base card from {base_filename}")
            # check that files exists and if not, use image_downloader to download it
            if not os.path.exists(base_filename):
                ImageDownloader.download_images(deck.base_card.card_set, deck.base_card.card_number)
            base_img = Image.open(base_filename).resize((base_width, base_height))
            background.paste(base_img, (bx0, by0))

    def _draw_foreground(self, background):
        # After all cards have been pasted onto 'background'
        if self.config and getattr(self.config, "foreground", None):
            fg = self.config.foreground
            if isinstance(fg, str):
                try:
                    fg_img = Image.open(fg).convert("RGBA").resize(background.size)
                    background = background.convert("RGBA")
                    background.alpha_composite(fg_img)
                    background = background.convert("RGB")
                except Exception:
                    pass  # Ignore foreground if loading fails
