from enum import Enum

class Collision(Enum):
    NONE = 0
    LEFT = 1
    RIGHT = 2
    TOP = 3
    BOTTOM = 4
    LEFT_AND_RIGHT = 5
    TOP_AND_BOTTOM = 6
    TOP_LEFT = 7
    TOP_RIGHT = 8
    BOTTOM_LEFT = 9
    BOTTOM_RIGHT = 10
    TOP_LEFT_AND_RIGHT = 11
    BOTTOM_LEFT_AND_RIGHT = 12
    LEFT_TOP_AND_BOTTOM = 13
    RIGHT_TOP_AND_BOTTOM = 14
    INSIDE = 15
    SURROUNDED = 16

class LayoutManager:
    def __init__(self, config=None):
        # Store configuration, which may include forbidden areas
        self.config = config

    def offset_to_the_left(self, input_left_x, input_right_x, forbidden_left_x):
        offset = input_right_x - forbidden_left_x + 1
        input_left_x = input_left_x - offset
        input_right_x = input_right_x - offset
        return input_left_x, input_right_x

    def offset_to_the_right(self, input_left_x, input_right_x, forbidden_right_x):
        offset = forbidden_right_x - input_left_x + 1
        input_right_x = input_right_x + offset
        input_left_x = input_left_x + offset
        return input_left_x, input_right_x
    
    def offset_up(self, input_top_y, input_bottom_y, forbidden_top_y):
        offset = input_bottom_y - forbidden_top_y + 1
        input_top_y = input_top_y - offset
        input_bottom_y = input_bottom_y - offset
        return input_top_y, input_bottom_y

    def offset_down(self, input_top_y, input_bottom_y, forbidden_bottom_y):
        offset = forbidden_bottom_y - input_top_y + 1
        input_bottom_y = input_bottom_y + offset
        input_top_y = input_top_y + offset
        return input_top_y, input_bottom_y
    
    def find_collision(self, input_left_x, input_top_y, input_right_x, input_bottom_y):
        """
        Check if a rectangle collisions any forbidden area.
        Returns True if there is collision.
        """
        # If no config or forbidden areas, always allow placement
        if not self.config or not self.config.forbidden_areas:
            return (input_left_x, input_top_y, input_right_x, input_bottom_y)
        # Check each forbidden area for collision
        for area in self.config.forbidden_areas:
            forbidden_left_x, forbidden_top_y, forbidden_right_x, forbidden_bottom_y = area
            
            # Check if the input rectangle collisions with the forbidden area
            collisionping_edge = self.check_collision((input_left_x, input_top_y, input_right_x, input_bottom_y),
                                (forbidden_left_x, forbidden_top_y, forbidden_right_x, forbidden_bottom_y))
            # Calculate new position to avoid collision

            if collisionping_edge != Collision.NONE:
                if collisionping_edge == Collision.LEFT:
                    input_left_x, input_right_x = self.offset_to_the_left(input_left_x, input_right_x, forbidden_left_x)
                elif collisionping_edge == Collision.RIGHT:
                    input_left_x, input_right_x = self.offset_to_the_right(input_left_x, input_right_x, forbidden_right_x)
                elif collisionping_edge == Collision.TOP:
                    input_top_y, input_bottom_y = self.offset_up(input_top_y, input_bottom_y, forbidden_top_y)
                elif collisionping_edge == Collision.BOTTOM:
                    input_top_y, input_bottom_y = self.offset_down(input_top_y, input_bottom_y, forbidden_bottom_y)
                # For any collision that has more than one edge collisionping, we will find the movement that is the least pixels
                elif collisionping_edge == Collision.LEFT_AND_RIGHT:
                    # Move to the right if the left edge is closer to the forbidden area
                    if abs(input_left_x - forbidden_left_x) < abs(input_right_x - forbidden_right_x):
                        input_left_x, input_right_x = self.offset_to_the_right(input_left_x, input_right_x, forbidden_right_x)
                    else:
                        input_left_x, input_right_x = self.offset_to_the_left(input_left_x, input_right_x, forbidden_left_x)
                elif collisionping_edge == Collision.TOP_AND_BOTTOM:
                    # Move down if the top edge is closer to the forbidden area
                    if abs(input_top_y - forbidden_top_y) < abs(input_bottom_y - forbidden_bottom_y):
                        input_top_y, input_bottom_y = self.offset_down(input_top_y, input_bottom_y, forbidden_bottom_y)
                    else:
                        input_top_y, input_bottom_y = self.offset_up(input_top_y, input_bottom_y, forbidden_top_y)
                elif collisionping_edge == Collision.TOP_LEFT:
                    # Move right if the left edge is closer to the forbidden area
                    if abs(input_left_x - forbidden_left_x) < abs(input_top_y - forbidden_top_y):
                        input_left_x, input_right_x = self.offset_to_the_right(input_left_x, input_right_x, forbidden_right_x)
                    else:
                        input_top_y, input_bottom_y = self.offset_up(input_top_y, input_bottom_y, forbidden_top_y)
                elif collisionping_edge == Collision.TOP_RIGHT:
                    # Move left if the right edge is closer to the forbidden area
                    if abs(input_right_x - forbidden_right_x) < abs(input_top_y - forbidden_top_y):
                        input_left_x, input_right_x = self.offset_to_the_left(input_left_x, input_right_x, forbidden_left_x)
                    else:
                        input_top_y, input_bottom_y = self.offset_up(input_top_y, input_bottom_y, forbidden_top_y)
                elif collisionping_edge == Collision.BOTTOM_LEFT:
                    # Move right if the left edge is closer to the forbidden area
                    if abs(input_left_x - forbidden_left_x) < abs(input_bottom_y - forbidden_bottom_y):
                        input_left_x, input_right_x = self.offset_to_the_right(input_left_x, input_right_x, forbidden_right_x)
                    else:
                        input_top_y, input_bottom_y = self.offset_down(input_top_y, input_bottom_y, forbidden_bottom_y)
                elif collisionping_edge == Collision.BOTTOM_RIGHT:
                    # Move left if the right edge is closer to the forbidden area
                    if abs(input_right_x - forbidden_right_x) < abs(input_bottom_y - forbidden_bottom_y):
                        input_left_x, input_right_x = self.offset_to_the_left(input_left_x, input_right_x, forbidden_left_x)
                    else:
                        input_top_y, input_bottom_y = self.offset_down(input_top_y, input_bottom_y, forbidden_bottom_y)
                elif collisionping_edge == Collision.TOP_LEFT_AND_RIGHT:
                    # Move down if the top edge is closer to the forbidden area
                    if abs(input_top_y - forbidden_top_y) < abs(input_left_x - forbidden_left_x):
                        input_top_y, input_bottom_y = self.offset_down(input_top_y, input_bottom_y, forbidden_bottom_y)
                    else:
                        input_left_x, input_right_x = self.offset_to_the_right(input_left_x, input_right_x, forbidden_right_x)
                elif collisionping_edge == Collision.BOTTOM_LEFT_AND_RIGHT:
                    # Move up if the bottom edge is closer to the forbidden area
                    if abs(input_bottom_y - forbidden_bottom_y) < abs(input_left_x - forbidden_left_x):
                        input_top_y, input_bottom_y = self.offset_up(input_top_y, input_bottom_y, forbidden_top_y)
                    else:
                        input_left_x, input_right_x = self.offset_to_the_right(input_left_x, input_right_x, forbidden_right_x)
                elif collisionping_edge == Collision.LEFT_TOP_AND_BOTTOM:
                    # Move right if the left edge is closer to the forbidden area
                    if abs(input_left_x - forbidden_left_x) < abs(input_top_y - forbidden_top_y):
                        input_left_x, input_right_x = self.offset_to_the_right(input_left_x, input_right_x, forbidden_right_x)
                    else:
                        input_top_y, input_bottom_y = self.offset_down(input_top_y, input_bottom_y, forbidden_bottom_y)
                elif collisionping_edge == Collision.RIGHT_TOP_AND_BOTTOM:
                    # Move left if the right edge is closer to the forbidden area
                    if abs(input_right_x - forbidden_right_x) < abs(input_top_y - forbidden_top_y):
                        input_left_x, input_right_x = self.offset_to_the_left(input_left_x, input_right_x, forbidden_left_x)
                    else:
                        input_top_y, input_bottom_y = self.offset_down(input_top_y, input_bottom_y, forbidden_bottom_y)
                elif collisionping_edge == Collision.SURROUNDED or collisionping_edge == Collision.INSIDE:
                    # If the rectangle is surrounded, we can move it in any direction.
                    # Find the shorter direction to move it out of the forbidden area
                    left_distance = abs(input_left_x - forbidden_left_x)
                    right_distance = abs(input_right_x - forbidden_right_x)
                    top_distance = abs(input_top_y - forbidden_top_y)
                    bottom_distance = abs(input_bottom_y - forbidden_bottom_y)
                    # Find the minimum distance to move
                    min_distance = min(left_distance, right_distance, top_distance, bottom_distance)
                    if min_distance == left_distance:
                        input_left_x, input_right_x = self.offset_to_the_right(input_left_x, input_right_x, forbidden_right_x)
                    elif min_distance == right_distance:
                        input_left_x, input_right_x = self.offset_to_the_left(input_left_x, input_right_x, forbidden_left_x)
                    elif min_distance == top_distance:
                        input_top_y, input_bottom_y = self.offset_down(input_top_y, input_bottom_y, forbidden_bottom_y)
                    elif min_distance == bottom_distance:
                        input_top_y, input_bottom_y = self.offset_up(input_top_y, input_bottom_y, forbidden_top_y)
        
        return (input_left_x, input_top_y, input_right_x, input_bottom_y)

    def check_collision(self, area1, area2):
        """
        Check if two rectangles collide.
        area1 and area2 are tuples of the form (left, top, right, bottom).
        Returns the collision enum value that was found to collide.
        """
        left1, top1, right1, bottom1 = area1
        left2, top2, right2, bottom2 = area2
        left_collision = False
        right_collision = False
        top_collision = False
        bottom_collision = False
        if left1 < left2:
            if not (right1 < left2 or bottom1 < top2 or top1 > bottom2):
                left_collision = True
        if right1 > right2:
            if not (left1 > right2 or bottom1 < top2 or top1 > bottom2):
                right_collision = True
        if top1 < top2:
            if not (bottom1 < top2 or right1 < left2 or left1 > right2):
                top_collision = True
        if bottom1 > bottom2:
            if not (top1 > bottom2 or right1 < left2 or left1 > right2):
                bottom_collision = True

        # print("Left collision:", str(left_collision))
        # print("Right collision:", str(right_collision))
        # print("Top collision:", str(top_collision))
        # print("Bottom collision:", str(bottom_collision))

        if left_collision and right_collision and top_collision and bottom_collision:
            return Collision.SURROUNDED
        if not left_collision and not right_collision and not top_collision and not bottom_collision:
            # No collision at all means either it is entirely outside or entirelty inside
            if (left1 >= left2 and right1 <= right2 and
                top1 >= top2 and bottom1 <= bottom2):
                return Collision.INSIDE
            else:
                return Collision.NONE
        if left_collision and right_collision:
            if top_collision:
                return Collision.TOP_LEFT_AND_RIGHT
            elif bottom_collision:
                return Collision.BOTTOM_LEFT_AND_RIGHT
            else:
                return Collision.LEFT_AND_RIGHT
        if top_collision and bottom_collision:
            if left_collision:
                return Collision.LEFT_TOP_AND_BOTTOM
            elif right_collision:
                return Collision.RIGHT_TOP_AND_BOTTOM
            else:
                return Collision.TOP_AND_BOTTOM
        if left_collision:
            if top_collision:
                return Collision.TOP_LEFT
            elif bottom_collision:
                return Collision.BOTTOM_LEFT
            else:
                return Collision.LEFT
        if right_collision:
            if top_collision:
                return Collision.TOP_RIGHT
            elif bottom_collision:
                return Collision.BOTTOM_RIGHT
            else:
                return Collision.RIGHT
        if top_collision:
            return Collision.TOP
        if bottom_collision:
            return Collision.BOTTOM

    def calculate_layout(self, deck, card_width, card_height, cards_per_row, padding, frame_thickness):
        """
        Calculate (x, y) positions for each card in the deck's main_deck.
        Ensures cards do not collision forbidden areas and are arranged in rows.
        """
        positions = []
        x, y = 0, 0
        for i, card in enumerate(deck.main_deck):
            if i > 0 and i % cards_per_row == 0:
                x = 0
                y += card_height + padding

            # Calculate the position of the card
            left_x = x + frame_thickness
            top_y = y + frame_thickness
            right_x = left_x + card_width - frame_thickness * 2
            bottom_y = top_y + card_height - frame_thickness * 2

            # Check for collision with forbidden areas
            left_x, top_y, right_x, bottom_y = self.find_collision(left_x, top_y, right_x, bottom_y)

            positions.append((left_x, top_y))
            x += card_width + padding

        return positions
