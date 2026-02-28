import os
try:
    from .deck import Deck
    from .config import Config
    from .card_sizer import CardSizer
    from .renderer import Renderer
    from . import image_downloader as ImageDownloader
except ImportError:
    from decklister.deck import Deck
    from decklister.config import Config
    from decklister.card_sizer import CardSizer
    from decklister.renderer import Renderer
    from decklister import image_downloader as ImageDownloader


class DeckImageGenerator:
    """
    Orchestrates deck image generation:
    1. Loads config and deck
    2. Downloads missing card images
    3. Calculates card sizes
    4. Renders the final image
    5. Saves output
    """

    def __init__(self, config=None):
        self.config = config or Config()

    def run(self, deck_file, output_path=None):
        """
        Generate a deck image from a deck file.

        Args:
            deck_file: Path to the deck JSON file.
            output_path: Optional output file path. Auto-named if not provided.
        """
        if not deck_file:
            print("No deck file provided.")
            return

        # Load deck
        try:
            deck = Deck.from_json_file(deck_file)
        except Exception as e:
            print(f"Error loading deck: {e}")
            return

        # Download missing images
        self._download_images(deck)

        # Calculate card sizes
        deck_layout = self._calculate_layout(self.config.deck_area, len(deck.main_deck))
        sb_layout = self._calculate_layout(self.config.sb_area, len(deck.sideboard))

        # If uniform sizing, use the smaller card size for both
        if self.config.uniform_card_size and deck_layout and sb_layout:
            min_width = min(deck_layout[0], sb_layout[0])
            min_height = min(deck_layout[1], sb_layout[1])
            deck_layout = (min_width, min_height, deck_layout[2], deck_layout[3], deck_layout[4])
            sb_layout = (min_width, min_height, sb_layout[2], sb_layout[3], sb_layout[4])

        # Render
        renderer = Renderer(self.config)
        image = renderer.render(deck, deck_layout, sb_layout)

        # Save
        output_path = output_path or self._auto_output_name()
        image.save(output_path)
        print(f"Deck image saved as {output_path}")

    def _download_images(self, deck):
        """Download images for all cards in the deck."""
        for card in deck.leaders + deck.bases:
            ImageDownloader.download_images(card.card_set, card.card_number)
        for card in deck.main_deck + deck.sideboard:
            ImageDownloader.download_images(card.card_set, card.card_number)

    def _calculate_layout(self, area, card_count):
        """Calculate card layout for an area. Returns None if area or count is missing."""
        if area is None or card_count <= 0:
            return None
        return CardSizer.calculate(area, card_count, padding=self.config.padding)

    def _auto_output_name(self):
        """Generate an auto-incremented output filename."""
        prefix = "deck_output_"
        suffix = ".png"
        existing = [
            f for f in os.listdir(".")
            if f.startswith(prefix) and f.endswith(suffix)
        ]
        numbers = []
        for f in existing:
            num_str = f[len(prefix):-len(suffix)]
            if num_str.isdigit():
                numbers.append(int(num_str))
        next_num = max(numbers, default=0) + 1
        return f"{prefix}{next_num}{suffix}"
