import os
try:
    from .deck import Deck
    from .config import Config
    from .card_sizer import CardSizer
    from .renderer import Renderer
    from .variant_resolver import resolve_variant
    from . import image_downloader as ImageDownloader
except ImportError:
    from decklister.deck import Deck
    from decklister.config import Config
    from decklister.card_sizer import CardSizer
    from decklister.renderer import Renderer
    from decklister.variant_resolver import resolve_variant
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

    def __init__(self, config=None, hyperspace=False, showcase=False):
        self.config = config or Config()
        self.hyperspace = hyperspace
        self.showcase = showcase

    def run(self, deck_file, output_path=None, player=None, deck_index=0):
        """
        Generate a deck image from a deck file.

        Args:
            deck_file: Path to the deck file (.json or Melee.gg .csv).
            output_path: Optional output file path. Auto-named if not provided.
            player: (CSV only) Player name to select from a multi-deck CSV.
            deck_index: (CSV only) 0-based row index when player is not given.
        """
        if not deck_file:
            print("No deck file provided.")
            return

        # Load deck — dispatch by file extension
        is_multi_deck = False
        try:
            ext = os.path.splitext(deck_file)[1].lower()
            if ext == ".csv":
                try:
                    from .melee_csv_parser import parse_melee_csv, _count_rows
                except ImportError:
                    from decklister.melee_csv_parser import parse_melee_csv, _count_rows
                is_multi_deck = _count_rows(deck_file) > 1
                deck = parse_melee_csv(deck_file, player_name=player, deck_index=deck_index)
            else:
                deck = Deck.from_json_file(deck_file)
        except Exception as e:
            print(f"Error loading deck: {e}")
            return

        self._generate_image(deck, deck_file, output_path, player=player, deck_index=deck_index, is_multi_deck=is_multi_deck)

    def run_all(self, deck_file, output_path=None):
        """
        Generate deck images for ALL decks in a Melee CSV export.

        Args:
            deck_file: Path to a Melee.gg CSV file.
            output_path: Not used (each deck gets an auto-named output).
        """
        if not deck_file:
            print("No deck file provided.")
            return

        ext = os.path.splitext(deck_file)[1].lower()
        if ext != ".csv":
            print("--all only works with CSV files. Running single deck instead.")
            self.run(deck_file, output_path=output_path)
            return

        try:
            from .melee_csv_parser import parse_melee_csv, _count_rows
        except ImportError:
            from decklister.melee_csv_parser import parse_melee_csv, _count_rows

        total = _count_rows(deck_file)
        if total == 0:
            print("CSV file contains no decks.")
            return

        print(f"Generating images for {total} deck(s)...")
        is_multi_deck = total > 1

        for i in range(total):
            try:
                deck = parse_melee_csv(deck_file, deck_index=i)
                display = deck.metadata.get("OwnerDisplayName") or deck.metadata.get("OwnerUsername", f"index {i}")
                print(f"\n--- Deck {i + 1}/{total}: {display} ---")
                self._generate_image(deck, deck_file, output_path=None, deck_index=i, is_multi_deck=is_multi_deck)
            except Exception as e:
                print(f"Error processing deck {i}: {e}")

        print(f"\nDone — {total} deck(s) processed.")

    def _generate_image(self, deck, deck_file, output_path=None, player=None, deck_index=0, is_multi_deck=False):
        """
        Generate and save a single deck image.

        Args:
            deck: Deck object.
            deck_file: Original input file path (for auto-naming).
            output_path: Optional explicit output path.
            player: Player name (for auto-naming).
            deck_index: Deck index (for auto-naming).
            is_multi_deck: Whether the source has multiple decks.
        """
        # Resolve variant card numbers and download images
        self._apply_variants(deck)
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
        output_path = output_path or self._auto_output_name(deck_file, player=player, deck_index=deck_index, is_multi_deck=is_multi_deck)
        image.save(output_path)
        print(f"Deck image saved as {output_path}")

    def _apply_variants(self, deck):
        """Resolve variant card numbers for all cards in the deck."""
        if not self.hyperspace and not self.showcase:
            return

        for card in deck.leaders + deck.bases + deck.main_deck + deck.sideboard:
            card.card_number = resolve_variant(
                card.card_set, card.card_number,
                hyperspace=self.hyperspace,
                showcase=self.showcase,
            )

    def _download_images(self, deck):
        """Download images for all cards in the deck concurrently."""
        cards = []
        for card in deck.leaders + deck.bases + deck.main_deck + deck.sideboard:
            cards.append((card.card_set, card.card_number))
        ImageDownloader.download_images_batch(cards)

    def _calculate_layout(self, area, card_count):
        """Calculate card layout for an area. Returns None if area or count is missing."""
        if area is None or card_count <= 0:
            return None
        return CardSizer.calculate(area, card_count, padding=self.config.padding)

    def _auto_output_name(self, deck_file, player=None, deck_index=0, is_multi_deck=False):
        """
        Generate an output filename based on the input file.

        - Base name from input file (without extension)
        - Multi-deck CSV: append _PlayerName or _index_N
        - Auto-increment if file exists: name.png, name_2.png, etc.
        """
        import re
        base = os.path.splitext(os.path.basename(deck_file))[0]

        # For multi-deck CSVs, add a disambiguator
        if is_multi_deck:
            if player:
                # Sanitize player name for use in a filename
                safe_player = re.sub(r'[^\w\-. ]', '', player).strip().replace(' ', '_')
                base = f"{base}_{safe_player}"
            else:
                base = f"{base}_index_{deck_index}"

        # Auto-increment if file already exists
        candidate = f"{base}.png"
        if not os.path.isfile(candidate):
            return candidate

        n = 2
        while os.path.isfile(f"{base}_{n}.png"):
            n += 1
        return f"{base}_{n}.png"