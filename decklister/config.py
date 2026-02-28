import json


class Config:
    def __init__(
        self,
        resolution=(1920, 1080),
        background=None,
        foreground=None,
        leader_areas=None,
        base_areas=None,
        deck_area=None,
        sb_area=None,
        count_background=None,
        padding=3,
        uniform_card_size=True,
    ):
        self.resolution = tuple(resolution)
        self.background = background  # Path to image or [r, g, b]
        self.foreground = foreground  # Path to image (alpha-composited on top)
        self.leader_areas = leader_areas or []  # List of [x0, y0, x1, y1]
        self.base_areas = base_areas or []  # List of [x0, y0, x1, y1]
        self.deck_area = deck_area  # [x0, y0, x1, y1]
        self.sb_area = sb_area  # [x0, y0, x1, y1]
        self.count_background = count_background  # Path to image
        self.padding = padding # Padding between individual card images
        self.uniform_card_size = uniform_card_size

    @classmethod
    def from_file(cls, path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(
            resolution=data.get("resolution", (1920, 1080)),
            background=data.get("background"),
            foreground=data.get("foreground"),
            leader_areas=data.get("leader_areas"),
            base_areas=data.get("base_areas"),
            deck_area=data.get("deck_area"),
            sb_area=data.get("sb_area"),
            count_background=data.get("count_background"),
            padding=data.get("padding"),
            uniform_card_size=data.get("uniform_card_size", True),
        )
