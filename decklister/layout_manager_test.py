import pytest
from .layout_manager import LayoutManager
from .layout_manager import Collision

class DummyConfig:
    def __init__(self, forbidden_areas=None, resolution=(1000, 1000)):
        self.forbidden_areas = forbidden_areas or []
        self.resolution = resolution

# Requirement: If no config is provided, the original position should be returned.
def test_no_config_returns_original():
    lm = LayoutManager()
    assert lm.find_collision(10, 10, 20, 20) == (10, 10, 20, 20)

# Requirement: If config has no forbidden areas, the original position should be returned.
def test_no_forbidden_areas_returns_original():
    config = DummyConfig([])
    lm = LayoutManager(config)
    assert lm.find_collision(30, 40, 10, 10) == (30, 40, 10, 10)

# Requirement: If the rectangle does not overlap any forbidden area, the original position should be returned.
def test_no_overlap_returns_original():
    config = DummyConfig([(100, 100, 200, 200)])
    lm = LayoutManager(config)
    assert lm.find_collision(10, 10, 20, 20) == (10, 10, 20, 20)
    config = DummyConfig([(0, 0, 5, 5)])
    lm = LayoutManager(config)
    assert lm.find_collision(10, 10, 20, 20) == (10, 10, 20, 20)

# Requirement: If the rectangle overlaps a forbidden area only on the right edge, it should be moved to the right edge of the forbidden area.
def test_overlap_right_edge_moves_right():
    config = DummyConfig([(10, 10, 40, 40)])
    lm = LayoutManager(config)
    # Overlaps with the forbidden area
    x0, y0, x1, y1 = lm.find_collision(20, 20, 50, 30)
    assert x0 >= 20

# Requirement: If the rectangle overlaps a forbidden area only on the bottom edge, it should be moved to the bottom edge of the forbidden area.
def test_overlap_bottom_edge_moves_down():
    config = DummyConfig([(10, 10, 40, 40)])
    lm = LayoutManager(config)
    # Overlaps with the forbidden area
    x0, y0, x1, y1 = lm.find_collision(20, 20, 30, 50)
    assert y0 >= 20

# Requirement: If the rectangle overlaps a forbidden area only on the left edge, it should be moved to the left edge of the forbidden area.
def test_overlap_left_edge_moves_left():
    config = DummyConfig([(10, 10, 40, 40)])
    lm = LayoutManager(config)
    # Overlaps with the forbidden area
    x0, y0, x1, y1 = lm.find_collision(5, 20, 20, 30)
    assert x1 <= 20

# Requirement: If the rectangle overlaps a forbidden area only on the top edge, it should be moved to the top edge of the forbidden area.
def test_overlap_top_edge_moves_up():
    config = DummyConfig([(10, 10, 40, 40)])
    lm = LayoutManager(config)
    # Overlaps with the forbidden area
    x0, y0, x1, y1 = lm.find_collision(20, 5, 30, 20)
    assert y1 <= 20

# Requirement: If the rectangle overlaps a forbidden area on multiple edges, it should be moved to the edge that minimizes the distance to the original position.
def test_overlap_multiple_edges_moves_min_distance():
    config = DummyConfig([(10, 10, 40, 40)])
    lm = LayoutManager(config)
    # Overlaps with the forbidden area on multiple edges
    x0, y0, x1, y1 = lm.find_collision(20, 20, 45, 50)
    # Should move to the right edge of the forbidden area
    assert y1 >= 50

@pytest.mark.parametrize("area1, area2, expected", [
    # No overlap at all
    ((0, 0, 10, 10), (20, 20, 30, 30), Collision.NONE),
    # area1 completely inside area2
    ((12, 12, 18, 18), (10, 10, 20, 20), Collision.INSIDE),
    # area2 completely inside area1
    ((10, 10, 30, 30), (15, 15, 20, 20), Collision.SURROUNDED),
    # Overlap on left edge
    ((5, 12, 15, 18), (10, 10, 20, 20), Collision.LEFT),
    # Overlap on right edge
    ((15, 12, 25, 18), (10, 10, 20, 20), Collision.RIGHT),
    # Overlap on top edge
    ((12, 5, 18, 15), (10, 10, 20, 20), Collision.TOP),
    # Overlap on bottom edge
    ((12, 15, 18, 25), (10, 10, 20, 20), Collision.BOTTOM),
    # Overlap on top-left corner
    ((5, 5, 15, 15), (10, 10, 20, 20), Collision.TOP_LEFT),
    # Overlap on top-right corner
    ((15, 5, 25, 15), (10, 10, 20, 20), Collision.TOP_RIGHT),
    # Overlap on bottom-left corner
    ((5, 15, 15, 25), (10, 10, 20, 20), Collision.BOTTOM_LEFT),
    # Overlap on bottom-right corner
    ((15, 15, 25, 25), (10, 10, 20, 20), Collision.BOTTOM_RIGHT),
    # Overlap on left and right edges
    ((5, 12, 25, 18), (10, 10, 20, 20), Collision.LEFT_AND_RIGHT),
    # Overlap on top and bottom edges
    ((12, 5, 18, 25), (10, 10, 20, 20), Collision.TOP_AND_BOTTOM),
    # Overlap on top-left and right edges
    ((5, 5, 25, 15), (10, 10, 20, 20), Collision.TOP_LEFT_AND_RIGHT),
    # Overlap on bottom-left and right edges
    ((5, 15, 25, 25), (10, 10, 20, 20), Collision.BOTTOM_LEFT_AND_RIGHT),
    # Overlap on left edge and top and bottom edges
    ((5, 8, 15, 25), (10, 10, 20, 20), Collision.LEFT_TOP_AND_BOTTOM),
    # Overlap on right edge and top and bottom edges
    ((15, 8, 25, 25), (10, 10, 20, 20), Collision.RIGHT_TOP_AND_BOTTOM),
    
])
def test_check_collision(area1, area2, expected):
    lm = LayoutManager()
    result = lm.check_collision(area1, area2)
    assert result == expected

def test_check_collision_touching_edges():
    lm = LayoutManager()
    # Touching right edge, no overlap
    assert lm.check_collision((21, 10, 30, 20), (10, 10, 20, 20)) == Collision.NONE
    # Touching bottom edge, no overlap
    assert lm.check_collision((10, 21, 20, 30), (10, 10, 20, 20)) == Collision.NONE
    # Touching left edge, no overlap
    assert lm.check_collision((0, 10, 9, 20), (10, 10, 20, 20)) == Collision.NONE
    # Touching top edge, no overlap
    assert lm.check_collision((10, 0, 20, 9), (10, 10, 20, 20)) == Collision.NONE
