class Config:
    def __init__(self, resolution=(1920, 1080), forbidden_areas=None, background=None,
                 foreground=None, leader_area=None, base_area=None):
        self.resolution = resolution
        # forbidden_areas: list of rectangles [x0, y0, x1, y1]
        self.forbidden_areas = forbidden_areas if forbidden_areas else []
        self.background = background  # Can be a path to an image or an RGB tuple
        self.foreground = foreground  # Can be a path to an image (may have alpha channel)
        self.leader_area = leader_area  # [x0, y0, x1, y1] or None
        self.base_area = base_area      # [x0, y0, x1, y1] or None
        # add leader area and base area to forbidden areas
        if self.leader_area:
            self.forbidden_areas.append(self.leader_area)
        if self.base_area:
            self.forbidden_areas.append(self.base_area)

    @classmethod
    def from_file(cls, path):
        print("Stub: Loading config from file (not implemented yet)")
        # TODO: Implement config file loading
        return cls()
