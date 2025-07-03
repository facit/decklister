class LayoutManager:
    def __init__(self, config=None):
        # Store configuration, which may include forbidden areas
        self.config = config

    def find_overlap(self, x, y, w, h):
        """
        Check if a rectangle (x, y, w, h) does not overlap any forbidden area.
        Returns True if placement is allowed, otherwise False.
        """
        # If no config or forbidden areas, always allow placement
        if not self.config or not self.config.forbidden_areas:
            return (x, y)
        # Check each forbidden area for overlap
        for fx0, fy0, fx1, fy1 in self.config.forbidden_areas:
            # If rectangles overlap, placement is not allowed
            if not (x + w <= fx0 or x >= fx1 or y + h <= fy0 or y >= fy1):
                # Overlap detected, placement not allowed
                # calculate the least movement to avoid overlap
                if x + w > fx0 and x < fx1:  # Overlaps horizontally
                    if y + h > fy0 and y < fy1:  # Overlaps vertically
                        # calculate the least movement to avoid overlap
                        if (fx1 - x) < (fx0 - (x + w)):
                            # Move to the right edge of the forbidden area
                            x = fx1
                        else:
                            # Move to the left edge of the forbidden area
                            x = fx0 - w
                        if (fy1 - y) < (fy0 - (y + h)):
                            # Move to the bottom edge of the forbidden area
                            y = fy1
                        else:
                            # Move to the top edge of the forbidden area
                            y = fy0 - h
                    elif y + h > fy0 and y < fy1:  # Only vertical overlap
                        # Move to the bottom edge of the forbidden area
                        y = fy1
                    elif x + w > fx0 and x < fx1:  # Only horizontal overlap
                        # Move to the right edge of the forbidden area
                        x = fx1
                    else:  # Only horizontal overlap
                        x = fx1
                elif y + h > fy0 and y < fy1:  # Overlaps vertically
                    # Move to the bottom edge of the forbidden area
                    y = fy1
                else:
                    # No overlap found, placement is allowed
                    continue

        return (x, y)  # No overlap found, placement is allowed

    def calculate_layout(self, deck, card_width, card_height, cards_per_row, padding, frame_thickness):
        """
        Calculate (x, y) positions for each card in the deck's main_deck.
        Ensures cards do not overlap forbidden areas and are arranged in rows.
        """
        positions = []
        x, y = frame_thickness, frame_thickness  # Start at initial padding
        row = 0
        col = 0
        for idx, card in enumerate(deck.main_deck):
            attempts = 0
            placed = False
            x, y = self.find_overlap(x, y, card_width, card_height)
            while not placed and attempts < 10:
                attempts += 1
                if (x + card_width > self.config.resolution[0] - frame_thickness or
                        y + card_height > self.config.resolution[1] - frame_thickness):
                    # If the card goes out of bounds, reset to next row
                    x = frame_thickness + padding + col * (card_width + padding)
                    y = frame_thickness + padding + row * (card_height + padding)
                    col += 1
                    if col >= cards_per_row:
                        col = 0
                        row += 1
                        y = frame_thickness + padding + row * (card_height + padding)
                x, y = self.find_overlap(x, y, card_width, card_height)
                if x < 0 or y < 0:
                    # If placement is still invalid, break and try next position
                    break
                positions.append((x, y))
                placed = True
                # Move to next position
                x += card_width + padding
            if not placed:
                print(f"Failed to place card {card} after {attempts} attempts, skipping.")
                continue
        return positions
