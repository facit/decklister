from PIL import Image

class BackgroundManager:
    def __init__(self, config=None):
        # Store the configuration object, which may contain background settings
        self.config = config

    def load_background(self, size):
        """
        Returns a PIL Image as the background, compositing a foreground image (with alpha)
        over a background (solid color or opaque image).
        Config options:
        - background: file path (opaque image) or RGB tuple/list
        - foreground: file path (may have alpha channel)
        """
        # 1. Create the background (solid color or opaque image)
        bg_color = (30, 30, 30)
        if self.config and getattr(self.config, "background", None):
            bg = self.config.background
            if isinstance(bg, str):
                try:
                    bg_img = Image.open(bg).convert("RGB").resize(size)
                    background = bg_img
                except Exception:
                    background = Image.new("RGB", size, bg_color)
            elif isinstance(bg, (tuple, list)) and len(bg) == 3:
                background = Image.new("RGB", size, tuple(bg))
            else:
                background = Image.new("RGB", size, bg_color)
        else:
            background = Image.new("RGB", size, bg_color)

        # 2. Composite the foreground (if any) over the background
        if self.config and getattr(self.config, "foreground", None):
            fg = self.config.foreground
            if isinstance(fg, str):
                try:
                    fg_img = Image.open(fg).convert("RGBA").resize(size)
                    background = background.convert("RGBA")
                    background.alpha_composite(fg_img)
                    background = background.convert("RGB")
                except Exception:
                    pass  # Ignore foreground if loading fails

        return background