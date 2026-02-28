import math


class CardSizer:
    """
    Calculates the largest card size that fits a given number of cards
    in a rectangular area, arranged in a grid.
    """

    DEFAULT_ASPECT_RATIO = 5.0 / 7.0  # width / height

    @staticmethod
    def calculate(area, card_count, padding=3, aspect_ratio=None):
        """
        Given a rectangular area and a number of cards, find the largest card
        size that fits all cards in a grid layout.

        Args:
            area: (x0, y0, x1, y1) rectangle to fill.
            card_count: Number of cards to place.
            padding: Space between cards in pixels.
            aspect_ratio: Card width / height ratio. Defaults to 5/7.

        Returns:
            (card_width, card_height, cols, rows, padding) or None if card_count is 0.
        """
        if card_count <= 0:
            return None

        if aspect_ratio is None:
            aspect_ratio = CardSizer.DEFAULT_ASPECT_RATIO

        x0, y0, x1, y1 = area
        avail_width = x1 - x0
        avail_height = y1 - y0

        if avail_width <= 0 or avail_height <= 0:
            return None

        best = None  # (card_width, card_height, cols, rows, padding)

        # Try every possible column count from 1 to card_count.
        # For each, compute the required rows and the largest card that fits.
        for cols in range(1, card_count + 1):
            rows = math.ceil(card_count / cols)

            # Max card width given available width and padding between columns
            max_w = (avail_width - (cols - 1) * padding) / cols
            # Max card height given available height and padding between rows
            max_h = (avail_height - (rows - 1) * padding) / rows

            if max_w <= 0 or max_h <= 0:
                continue

            # The card must satisfy the aspect ratio. Pick the limiting dimension.
            # card_width = card_height * aspect_ratio
            card_w_from_h = max_h * aspect_ratio
            card_h_from_w = max_w / aspect_ratio

            if card_w_from_h <= max_w:
                # Height is the limiting factor
                card_width = int(card_w_from_h)
                card_height = int(max_h)
            else:
                # Width is the limiting factor
                card_width = int(max_w)
                card_height = int(card_h_from_w)

            if card_width <= 0 or card_height <= 0:
                continue

            # Maximize card area (width * height) to get the best visual fill.
            # When card area is equal, prefer more columns for better horizontal fill.
            card_area = card_width * card_height
            if best is None or card_area > best[0] * best[1]:
                best = (card_width, card_height, cols, rows, padding)
            elif card_area == best[0] * best[1] and cols > best[2]:
                best = (card_width, card_height, cols, rows, padding)

        return best
