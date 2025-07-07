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

class OffsetState():
    def __init__(self):
        self.reset()

    def reset(self):
        self.to_the_left = False
        self.to_the_right = False
        self.up = False
        self.down = False
        self.current = None
        self.old_left_x = None
        self.old_top_y = None
        self.old_right_x = None
        self.old_bottom_y = None

    def all_offsets(self):
        return (self.to_the_left and self.to_the_right and
                self.up and self.down)
    
    def __repr__(self):
        return f"left:{self.to_the_left}, right:{self.to_the_right}, up:{self.up}, down:{self.down}"

class LayoutManager:
    def __init__(self, config=None):
        # Store configuration, which may include forbidden areas
        self.config = config

    def offset_to_the_left(self, offset_state, input_left_x, input_right_x, forbidden_left_x):
        tmp_left_x = offset_state.old_left_x if offset_state.old_left_x is not None else input_left_x
        tmp_right_x = offset_state.old_right_x if offset_state.old_right_x is not None else input_right_x
        if offset_state.old_left_x is None:
            offset_state.old_left_x = input_left_x
        if offset_state.old_right_x is None:
            offset_state.old_right_x = input_right_x
        offset = tmp_right_x - forbidden_left_x + 1
        tmp_left_x = tmp_left_x - offset
        tmp_right_x = tmp_right_x - offset
        offset_state.to_the_left = True
        return tmp_left_x, tmp_right_x

    def offset_to_the_right(self, offset_state, input_left_x, input_right_x, forbidden_right_x):
        tmp_left_x = offset_state.old_left_x if offset_state.old_left_x is not None else input_left_x
        tmp_right_x = offset_state.old_right_x if offset_state.old_right_x is not None else input_right_x
        if offset_state.old_left_x is None:
            offset_state.old_left_x = input_left_x
        if offset_state.old_right_x is None:
            offset_state.old_right_x = input_right_x
        offset = forbidden_right_x - tmp_left_x + 1
        tmp_right_x = tmp_right_x + offset
        tmp_left_x = tmp_left_x + offset
        offset_state.to_the_right = True
        return tmp_left_x, tmp_right_x
    
    def offset_up(self, offset_state, input_top_y, input_bottom_y, forbidden_top_y):
        tmp_top_y = offset_state.old_top_y if offset_state.old_top_y is not None else input_top_y
        tmp_bottom_y = offset_state.old_bottom_y if offset_state.old_bottom_y is not None else input_bottom_y
        if offset_state.old_top_y is None:
            offset_state.old_top_y = input_top_y
        if offset_state.old_bottom_y is None:
            offset_state.old_bottom_y = input_bottom_y
        offset = tmp_bottom_y - forbidden_top_y + 1
        tmp_top_y = tmp_top_y - offset
        tmp_bottom_y = tmp_bottom_y - offset
        offset_state.up = True
        return tmp_top_y, tmp_bottom_y

    def offset_down(self, offset_state, input_top_y, input_bottom_y, forbidden_bottom_y):
        tmp_top_y = offset_state.old_top_y if offset_state.old_top_y is not None else input_top_y
        tmp_bottom_y = offset_state.old_bottom_y if offset_state.old_bottom_y is not None else input_bottom_y
        if offset_state.old_top_y is None:
            offset_state.old_top_y = input_top_y
        if offset_state.old_bottom_y is None:
            offset_state.old_bottom_y = input_bottom_y
        offset = forbidden_bottom_y - tmp_top_y + 1
        tmp_bottom_y = tmp_bottom_y + offset
        tmp_top_y = tmp_top_y + offset
        offset_state.down = True
        return tmp_top_y, tmp_bottom_y
    
    def check_and_offset_right(self, offset_state, input_left_x, input_right_x, input_top_y, input_bottom_y,
                               forbidden_left_x, forbidden_right_x, forbidden_top_y, forbidden_bottom_y):
        if offset_state.up and not offset_state.down:
            input_top_y, input_bottom_y = self.offset_down(offset_state, input_top_y, input_bottom_y, forbidden_bottom_y)
        elif offset_state.down and not offset_state.up:
            input_top_y, input_bottom_y = self.offset_up(offset_state, input_top_y, input_bottom_y, forbidden_top_y)
        elif offset_state.to_the_right:
            if abs(input_top_y - forbidden_top_y) < abs(input_bottom_y - forbidden_bottom_y):
                input_top_y, input_bottom_y = self.offset_down(offset_state, input_top_y, input_bottom_y, forbidden_bottom_y)
            else:
                input_top_y, input_bottom_y = self.offset_up(offset_state, input_top_y, input_bottom_y, forbidden_top_y)
        elif offset_state.to_the_left:
            input_left_x, input_right_x = self.offset_to_the_left(offset_state, input_left_x, input_right_x, forbidden_left_x)
        else:
            input_left_x, input_right_x = self.offset_to_the_right(offset_state, input_left_x, input_right_x, forbidden_right_x)

        return offset_state, input_left_x, input_right_x, input_top_y, input_bottom_y
    
    def check_and_offset_left(self, offset_state, input_left_x, input_right_x, input_top_y, input_bottom_y,
                              forbidden_left_x, forbidden_right_x, forbidden_top_y, forbidden_bottom_y):
        if offset_state.up and not offset_state.down:
            input_top_y, input_bottom_y = self.offset_down(offset_state, input_top_y, input_bottom_y, forbidden_bottom_y)
        elif offset_state.down and not offset_state.up:
            input_top_y, input_bottom_y = self.offset_up(offset_state, input_top_y, input_bottom_y, forbidden_top_y)
        elif offset_state.to_the_right:
            if abs(input_top_y - forbidden_top_y) < abs(input_bottom_y - forbidden_bottom_y):
                input_top_y, input_bottom_y = self.offset_down(offset_state, input_top_y, input_bottom_y, forbidden_bottom_y)
            else:
                input_top_y, input_bottom_y = self.offset_up(offset_state, input_top_y, input_bottom_y, forbidden_top_y)
        elif offset_state.to_the_left:
            input_left_x, input_right_x = self.offset_to_the_right(offset_state, input_left_x, input_right_x, forbidden_right_x)
        else:
            input_left_x, input_right_x = self.offset_to_the_left(offset_state, input_left_x, input_right_x, forbidden_left_x)

        return offset_state, input_left_x, input_right_x, input_top_y, input_bottom_y

    def check_and_offset_up(self, offset_state, input_left_x, input_right_x, input_top_y, input_bottom_y,
                            forbidden_left_x, forbidden_right_x, forbidden_top_y, forbidden_bottom_y):
        if offset_state.to_the_left and not offset_state.to_the_right:
            input_left_x, input_right_x = self.offset_to_the_right(offset_state, input_left_x, input_right_x, forbidden_right_x)
        elif offset_state.to_the_right and not offset_state.to_the_left:
            input_left_x, input_right_x = self.offset_to_the_left(offset_state, input_left_x, input_right_x, forbidden_left_x) 
        elif offset_state.down:
            if abs(input_left_x - forbidden_left_x) < abs(input_right_x - forbidden_right_x):
                input_left_x, input_right_x = self.offset_to_the_right(offset_state, input_left_x, input_right_x, forbidden_right_x)
            else:
                input_left_x, input_right_x = self.offset_to_the_left(offset_state, input_left_x, input_right_x, forbidden_left_x)
        elif offset_state.up:
            input_top_y, input_bottom_y = self.offset_down(offset_state, input_top_y, input_bottom_y, forbidden_bottom_y)
        else:
            input_top_y, input_bottom_y = self.offset_up(offset_state, input_top_y, input_bottom_y, forbidden_top_y)

        return offset_state, input_left_x, input_right_x, input_top_y, input_bottom_y

    def check_and_offset_down(self, offset_state, input_left_x, input_right_x, input_top_y, input_bottom_y,
                              forbidden_left_x, forbidden_right_x, forbidden_top_y, forbidden_bottom_y):
        if offset_state.to_the_left and not offset_state.to_the_right:
            input_left_x, input_right_x = self.offset_to_the_right(offset_state, input_left_x, input_right_x, forbidden_right_x)
        elif offset_state.to_the_right and not offset_state.to_the_left:
            input_left_x, input_right_x = self.offset_to_the_left(offset_state, input_left_x, input_right_x, forbidden_left_x) 
        elif offset_state.up:
            if abs(input_left_x - forbidden_left_x) < abs(input_right_x - forbidden_right_x):
                input_left_x, input_right_x = self.offset_to_the_right(offset_state, input_left_x, input_right_x, forbidden_right_x)
            else:
                input_left_x, input_right_x = self.offset_to_the_left(offset_state, input_left_x, input_right_x, forbidden_left_x)
        elif offset_state.down:
            input_top_y, input_bottom_y = self.offset_up(offset_state, input_top_y, input_bottom_y, forbidden_top_y)
        else:
            input_top_y, input_bottom_y = self.offset_down(offset_state, input_top_y, input_bottom_y, forbidden_bottom_y)

        return offset_state, input_left_x, input_right_x, input_top_y, input_bottom_y

    def find_collision(self, input_left_x, input_top_y, input_right_x, input_bottom_y):
        """
        Check if a rectangle collides with any forbidden area.
        """
        # If no config or forbidden areas, always allow placement
        if not self.config or not self.config.forbidden_areas:
            return (input_left_x, input_top_y, input_right_x, input_bottom_y)
        # Check each forbidden area for collision
        for area in self.config.forbidden_areas:
            # print("new area")
            # print((input_left_x, input_top_y, input_right_x, input_bottom_y),)
            forbidden_left_x, forbidden_top_y, forbidden_right_x, forbidden_bottom_y = area
            
            # Check if the input rectangle collisions with the forbidden area
            collision_edge = self.check_collision((input_left_x, input_top_y, input_right_x, input_bottom_y),
                                (forbidden_left_x, forbidden_top_y, forbidden_right_x, forbidden_bottom_y))
            # Calculate new position to avoid collision

            offset_state = OffsetState()

            while collision_edge != Collision.NONE:
                if offset_state.all_offsets():
                    # We have an error if we have already offset in all directions
                    raise ValueError("Cannot resolve collision, already offset in all directions.")
                
                if collision_edge == Collision.LEFT:
                    offset_state, input_left_x, input_right_x, input_top_y, input_bottom_y = self.check_and_offset_left(offset_state, input_left_x, input_right_x, input_top_y, input_bottom_y, forbidden_left_x, forbidden_right_x, forbidden_top_y, forbidden_bottom_y)
                elif collision_edge == Collision.RIGHT:
                    offset_state, input_left_x, input_right_x, input_top_y, input_bottom_y = self.check_and_offset_right(offset_state, input_left_x, input_right_x, input_top_y, input_bottom_y, forbidden_left_x, forbidden_right_x, forbidden_top_y, forbidden_bottom_y)
                elif collision_edge == Collision.TOP:
                    offset_state, input_left_x, input_right_x, input_top_y, input_bottom_y = self.check_and_offset_up(offset_state, input_left_x, input_right_x, input_top_y, input_bottom_y, forbidden_left_x, forbidden_right_x, forbidden_top_y, forbidden_bottom_y)
                elif collision_edge == Collision.BOTTOM:
                    offset_state, input_left_x, input_right_x, input_top_y, input_bottom_y = self.check_and_offset_down(offset_state, input_left_x, input_right_x, input_top_y, input_bottom_y, forbidden_left_x, forbidden_right_x, forbidden_top_y, forbidden_bottom_y)
                # For any collision that has more than one edge collision, we will find the movement that is the least pixels
                elif collision_edge == Collision.LEFT_AND_RIGHT:
                    # Move to the right if the left edge is closer to the forbidden area
                    if offset_state.current == "to_the_right" or abs(input_left_x - forbidden_left_x) < abs(input_right_x - forbidden_right_x):
                        offset_state.current = "to_the_right"
                        offset_state, input_left_x, input_right_x, input_top_y, input_bottom_y = self.check_and_offset_right(offset_state, input_left_x, input_right_x, input_top_y, input_bottom_y, forbidden_left_x, forbidden_right_x, forbidden_top_y, forbidden_bottom_y)
                    else:
                        offset_state, input_left_x, input_right_x, input_top_y, input_bottom_y = self.check_and_offset_left(offset_state, input_left_x, input_right_x, input_top_y, input_bottom_y, forbidden_left_x, forbidden_right_x, forbidden_top_y, forbidden_bottom_y)
                elif collision_edge == Collision.TOP_AND_BOTTOM:
                    # Move down if the top edge is closer to the forbidden area
                    if offset_state.current == "down" or abs(input_top_y - forbidden_top_y) < abs(input_bottom_y - forbidden_bottom_y):
                        offset_state.current = "down"
                        offset_state, input_left_x, input_right_x, input_top_y, input_bottom_y = self.check_and_offset_down(offset_state, input_left_x, input_right_x, input_top_y, input_bottom_y, forbidden_left_x, forbidden_right_x, forbidden_top_y, forbidden_bottom_y)
                    else:
                        offset_state, input_left_x, input_right_x, input_top_y, input_bottom_y = self.check_and_offset_up(offset_state, input_left_x, input_right_x, input_top_y, input_bottom_y, forbidden_left_x, forbidden_right_x, forbidden_top_y, forbidden_bottom_y)
                elif collision_edge == Collision.TOP_LEFT:
                    if offset_state.current == "to_the_left" or abs(input_left_x - forbidden_left_x) < abs(input_top_y - forbidden_top_y):
                        offset_state.current = "to_the_left"
                        offset_state, input_left_x, input_right_x, input_top_y, input_bottom_y = self.check_and_offset_left(offset_state, input_left_x, input_right_x, input_top_y, input_bottom_y, forbidden_left_x, forbidden_right_x, forbidden_top_y, forbidden_bottom_y)
                    else:
                        offset_state, input_left_x, input_right_x, input_top_y, input_bottom_y = self.check_and_offset_up(offset_state, input_left_x, input_right_x, input_top_y, input_bottom_y, forbidden_left_x, forbidden_right_x, forbidden_top_y, forbidden_bottom_y)
                elif collision_edge == Collision.TOP_RIGHT:
                    if offset_state.current == "to_the_right" or abs(input_right_x - forbidden_right_x) < abs(input_top_y - forbidden_top_y):
                        offset_state.current = "to_the_right"
                        offset_state, input_left_x, input_right_x, input_top_y, input_bottom_y = self.check_and_offset_right(offset_state, input_left_x, input_right_x, input_top_y, input_bottom_y, forbidden_left_x, forbidden_right_x, forbidden_top_y, forbidden_bottom_y)
                    else:
                        offset_state, input_left_x, input_right_x, input_top_y, input_bottom_y = self.check_and_offset_down(offset_state, input_left_x, input_right_x, input_top_y, input_bottom_y, forbidden_left_x, forbidden_right_x, forbidden_top_y, forbidden_bottom_y)
                elif collision_edge == Collision.BOTTOM_LEFT:
                    if offset_state.current == "to_the_left" or abs(input_left_x - forbidden_left_x) < abs(input_bottom_y - forbidden_bottom_y):
                        offset_state.current = "to_the_left"
                        offset_state, input_left_x, input_right_x, input_top_y, input_bottom_y = self.check_and_offset_left(offset_state, input_left_x, input_right_x, input_top_y, input_bottom_y, forbidden_left_x, forbidden_right_x, forbidden_top_y, forbidden_bottom_y)
                    else:
                        offset_state, input_left_x, input_right_x, input_top_y, input_bottom_y = self.check_and_offset_down(offset_state, input_left_x, input_right_x, input_top_y, input_bottom_y, forbidden_left_x, forbidden_right_x, forbidden_top_y, forbidden_bottom_y)
                elif collision_edge == Collision.BOTTOM_RIGHT:
                    if offset_state.current == "to_the_right" or abs(input_right_x - forbidden_right_x) < abs(input_bottom_y - forbidden_bottom_y):
                        offset_state.current = "to_the_right"
                        offset_state, input_left_x, input_right_x, input_top_y, input_bottom_y = self.check_and_offset_right(offset_state, input_left_x, input_right_x, input_top_y, input_bottom_y, forbidden_left_x, forbidden_right_x, forbidden_top_y, forbidden_bottom_y)
                    else:
                        offset_state, input_left_x, input_right_x, input_top_y, input_bottom_y = self.check_and_offset_down(offset_state, input_left_x, input_right_x, input_top_y, input_bottom_y, forbidden_left_x, forbidden_right_x, forbidden_top_y, forbidden_bottom_y)
                elif collision_edge == Collision.TOP_LEFT_AND_RIGHT:
                    if offset_state.current == "up" or abs(input_top_y - forbidden_top_y) < abs(input_left_x - forbidden_left_x):
                        offset_state.current = "up"
                        offset_state, input_left_x, input_right_x, input_top_y, input_bottom_y = self.check_and_offset_up(offset_state, input_left_x, input_right_x, input_top_y, input_bottom_y, forbidden_left_x, forbidden_right_x, forbidden_top_y, forbidden_bottom_y)
                    else:
                        offset_state, input_left_x, input_right_x, input_top_y, input_bottom_y = self.check_and_offset_right(offset_state, input_left_x, input_right_x, input_top_y, input_bottom_y, forbidden_left_x, forbidden_right_x, forbidden_top_y, forbidden_bottom_y)
                elif collision_edge == Collision.BOTTOM_LEFT_AND_RIGHT:
                    if offset_state.current == "down" or abs(input_bottom_y - forbidden_bottom_y) < abs(input_left_x - forbidden_left_x):
                        offset_state.current = "down"
                        offset_state, input_left_x, input_right_x, input_top_y, input_bottom_y = self.check_and_offset_down(offset_state, input_left_x, input_right_x, input_top_y, input_bottom_y, forbidden_left_x, forbidden_right_x, forbidden_top_y, forbidden_bottom_y)
                    else:
                        offset_state, input_left_x, input_right_x, input_top_y, input_bottom_y = self.check_and_offset_right(offset_state, input_left_x, input_right_x, input_top_y, input_bottom_y, forbidden_left_x, forbidden_right_x, forbidden_top_y, forbidden_bottom_y)
                elif collision_edge == Collision.LEFT_TOP_AND_BOTTOM:
                    if offset_state.current == "to_the_left" or abs(input_left_x - forbidden_left_x) < abs(input_top_y - forbidden_top_y):
                        offset_state.current = "to_the_left"
                        offset_state, input_left_x, input_right_x, input_top_y, input_bottom_y = self.check_and_offset_left(offset_state, input_left_x, input_right_x, input_top_y, input_bottom_y, forbidden_left_x, forbidden_right_x, forbidden_top_y, forbidden_bottom_y)
                    else:
                        offset_state, input_left_x, input_right_x, input_top_y, input_bottom_y = self.check_and_offset_down(offset_state, input_left_x, input_right_x, input_top_y, input_bottom_y, forbidden_left_x, forbidden_right_x, forbidden_top_y, forbidden_bottom_y)
                elif collision_edge == Collision.RIGHT_TOP_AND_BOTTOM:
                    if offset_state.current == "to_the_right" or abs(input_right_x - forbidden_right_x) < abs(input_top_y - forbidden_top_y):
                        offset_state.current = "to_the_right"
                        offset_state, input_left_x, input_right_x, input_top_y, input_bottom_y = self.check_and_offset_right(offset_state, input_left_x, input_right_x, input_top_y, input_bottom_y, forbidden_left_x, forbidden_right_x, forbidden_top_y, forbidden_bottom_y)
                    else:
                        offset_state, input_left_x, input_right_x, input_top_y, input_bottom_y = self.check_and_offset_down(offset_state, input_left_x, input_right_x, input_top_y, input_bottom_y, forbidden_left_x, forbidden_right_x, forbidden_top_y, forbidden_bottom_y)
                elif collision_edge == Collision.SURROUNDED or collision_edge == Collision.INSIDE:
                    # If the rectangle is surrounded, we can move it in any direction.
                    # Find the shorter direction to move it out of the forbidden area
                    left_distance = abs(input_left_x - forbidden_left_x)
                    right_distance = abs(input_right_x - forbidden_right_x)
                    top_distance = abs(input_top_y - forbidden_top_y)
                    bottom_distance = abs(input_bottom_y - forbidden_bottom_y)
                    # Find the minimum distance to move
                    min_distance = min(left_distance, right_distance, top_distance, bottom_distance)
                    if offset_state.current == "to_the_right" or min_distance == left_distance:
                        offset_state.current = "to_the_right"
                        offset_state, input_left_x, input_right_x, input_top_y, input_bottom_y = self.check_and_offset_right(offset_state, input_left_x, input_right_x, input_top_y, input_bottom_y, forbidden_left_x, forbidden_right_x, forbidden_top_y, forbidden_bottom_y)
                    elif offset_state.current == "to_the_left" or min_distance == right_distance:
                        offset_state.current = "to_the_left"
                        offset_state, input_left_x, input_right_x, input_top_y, input_bottom_y = self.check_and_offset_left(offset_state, input_left_x, input_right_x, input_top_y, input_bottom_y, forbidden_left_x, forbidden_right_x, forbidden_top_y, forbidden_bottom_y)
                    elif offset_state.current == "down" or min_distance == top_distance:
                        offset_state.current = "down"
                        offset_state, input_left_x, input_right_x, input_top_y, input_bottom_y = self.check_and_offset_down(offset_state, input_left_x, input_right_x, input_top_y, input_bottom_y, forbidden_left_x, forbidden_right_x, forbidden_top_y, forbidden_bottom_y)
                    elif offset_state.current == "up" or min_distance == bottom_distance:
                        offset_state.current = "up"
                        offset_state, input_left_x, input_right_x, input_top_y, input_bottom_y = self.check_and_offset_up(offset_state, input_left_x, input_right_x, input_top_y, input_bottom_y, forbidden_left_x, forbidden_right_x, forbidden_top_y, forbidden_bottom_y)

                new_collision_edge = self.check_collision((input_left_x, input_top_y, input_right_x, input_bottom_y),
                                    (forbidden_left_x, forbidden_top_y, forbidden_right_x, forbidden_bottom_y))
                if new_collision_edge == Collision.NONE:
                    # print("breaking")
                    # print((input_left_x, input_top_y, input_right_x, input_bottom_y),)
                    offset_state.reset()
                    break

        # print((input_left_x, input_top_y, input_right_x, input_bottom_y,))
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

    def calculate_layout(self, deck_area, sb_area, deck, card_width, card_height, cards_per_row, padding, frame_thickness):
        """
        Calculate (x, y) positions for each card in the deck's main_deck.
        Ensures cards do not collide with forbidden areas and are arranged in rows.
        """
        positions = []

        if deck_area is not None:
            min_x = deck_area[0]
            min_y = deck_area[1]
            max_x = deck_area[2]
            max_y = deck_area[3]
            x, y = min_x, min_y
            for i, card in enumerate(deck.main_deck):
                if i > 0 and i % cards_per_row == 0:
                    x = min_x
                    y += card_height + padding
                if x + card_width > max_x or y + card_height > max_y:
                    print("Can't fit all cards!")
                    return None

                positions.append((x, y))
                x += card_width + padding

        if sb_area is not None:
            min_x = sb_area[0]
            min_y = sb_area[1]
            max_x = sb_area[2]
            max_y = sb_area[3]
            x, y = min_x, min_y
            for i, card in enumerate(deck.sideboard):
                if i > 0 and i % cards_per_row == 0:
                    x = min_x
                    y += card_height + padding
                if x + card_width > max_x or y + card_height > max_y:
                    print("Can't fit all cards!")
                    return None

                positions.append((x, y))
                x += card_width + padding

        return positions
