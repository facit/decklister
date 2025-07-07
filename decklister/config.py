import json

class Config:
    def __init__(self, resolution=(1920, 1080), forbidden_areas=None, background=None,
                 foreground=None, leader_area=None, base_area=None, deck_area=None, sb_area=None, count_background=None):
        self.resolution = resolution
        # forbidden_areas: list of rectangles [x0, y0, x1, y1]
        self.forbidden_areas = forbidden_areas if forbidden_areas else []
        self.background = background  # Can be a path to an image or an RGB tuple
        self.foreground = foreground  # Can be a path to an image (may have alpha channel)
        self.leader_area = leader_area  # [x0, y0, x1, y1] or None
        self.base_area = base_area      # [x0, y0, x1, y1] or None
        self.deck_area = deck_area
        self.sb_area = sb_area
        self.count_background = count_background
        # add leader area and base area to forbidden areas
        if self.leader_area:
            self.forbidden_areas.append(self.leader_area)
        if self.base_area:
            self.forbidden_areas.append(self.base_area)

    @classmethod
    def from_file(cls, path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(
            resolution=tuple(data.get("resolution", (1920, 1080))),
            forbidden_areas=data.get("forbidden_areas"),
            background=data.get("background"),
            foreground=data.get("foreground"),
            leader_area=data.get("leader_area"),
            base_area=data.get("base_area"),
            deck_area=data.get("deck_area"),
            sb_area=data.get("sb_area"),
            count_background=data.get("count_background"),
        )