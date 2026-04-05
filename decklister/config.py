import json


class Config:
    def __init__(
        self,
        resolution=(1920, 1080),
        layers=None,
        leader_areas=None,
        base_areas=None,
        deck_area=None,
        sb_area=None,
        count_background=None,
        padding=3,
        uniform_card_size=True,
    ):
        self.resolution = tuple(resolution)
        self.layers = layers or []  # Ordered list of layer specs; see from_file for format
        self.leader_areas = leader_areas or []  # List of [x0, y0, x1, y1]
        self.base_areas = base_areas or []  # List of [x0, y0, x1, y1]
        self.deck_area = deck_area  # [x0, y0, x1, y1]
        self.sb_area = sb_area  # [x0, y0, x1, y1]
        self.count_background = count_background  # Path to image
        self.padding = padding  # Padding between individual card images
        self.uniform_card_size = uniform_card_size

    @classmethod
    def from_file(cls, path):
        """
        Load config from a JSON file.

        Layer format (new):
          "layers": [
            "bg.png",                                          # image, full canvas
            [30, 30, 30],                                      # solid color fill
            {"type": "image", "path": "logo.png",
             "area": [x0, y0, x1, y1]},                       # image in specific area
            {"type": "color", "color": [r, g, b]},            # solid color (optional alpha)
            {"type": "cards"},                                 # renders all card elements here
            "fg.png"                                           # image, full canvas
          ]

        Backwards-compatible (old):
          "background": "bg.png" or [r, g, b],
          "foreground": "fg.png"
          → auto-converted to layers with {"type": "cards"} in the middle.
        """
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        layers = data.get("layers")
        if layers is None:
            # Backwards compatibility: build layers from old background/foreground fields
            layers = []
            background = data.get("background")
            foreground = data.get("foreground")
            if background is not None:
                if isinstance(background, str):
                    layers.append({"type": "image", "path": background})
                elif isinstance(background, (list, tuple)) and len(background) == 3:
                    layers.append({"type": "color", "color": list(background)})
            layers.append({"type": "cards"})
            if foreground is not None and isinstance(foreground, str):
                layers.append({"type": "image", "path": foreground})

        return cls(
            resolution=data.get("resolution", (1920, 1080)),
            layers=layers,
            leader_areas=data.get("leader_areas"),
            base_areas=data.get("base_areas"),
            deck_area=data.get("deck_area"),
            sb_area=data.get("sb_area"),
            count_background=data.get("count_background"),
            padding=data.get("padding", 3),
            uniform_card_size=data.get("uniform_card_size", True),
        )
