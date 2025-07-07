import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk  # Requires pillow: pip install pillow
import json

class AreaDrawer:
    def __init__(self, master):
        self.master = master
        self.master.title("Config Area Drawer")
        self.canvas = tk.Canvas(master, width=1920, height=1080, bg="white", scrollregion=(0,0,1920,1080))
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.rects = []
        self.start_x = self.start_y = None
        self.current_rect = None
        self.bg_image = None
        self.bg_image_id = None

        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)

        menu = tk.Menu(master)
        master.config(menu=menu)
        file_menu = tk.Menu(menu, tearoff=0)
        menu.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Load Background Image", command=self.load_background)
        file_menu.add_command(label="Export JSON", command=self.export_json)
        file_menu.add_command(label="Clear", command=self.clear_canvas)

    def load_background(self):
        file_path = filedialog.askopenfilename(filetypes=[("Image files", "*.png;*.jpg;*.jpeg;*.bmp;*.gif")])
        if file_path:
            # Get current canvas size
            width = self.canvas.winfo_width()
            height = self.canvas.winfo_height()
            # If not yet mapped, fallback to default resolution
            if width <= 1 or height <= 1:
                width, height = 1920, 1080
            img = Image.open(file_path)
            img = img.resize((width, height), Image.Resampling.LANCZOS)
            self.bg_image = ImageTk.PhotoImage(img)
            if self.bg_image_id:
                self.canvas.delete(self.bg_image_id)
            self.bg_image_id = self.canvas.create_image(0, 0, anchor="nw", image=self.bg_image)
            self.canvas.tag_lower(self.bg_image_id)

    def on_press(self, event):
        self.start_x = self.canvas.canvasx(event.x)
        self.start_y = self.canvas.canvasy(event.y)
        self.current_rect = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, outline="red")

    def on_drag(self, event):
        cur_x = self.canvas.canvasx(event.x)
        cur_y = self.canvas.canvasy(event.y)
        self.canvas.coords(self.current_rect, self.start_x, self.start_y, cur_x, cur_y)

    def on_release(self, event):
        x0, y0, x1, y1 = self.canvas.coords(self.current_rect)
        rect = [int(min(x0, x1)), int(min(y0, y1)), int(max(x0, x1)), int(max(y0, y1))]
        self.rects.append(rect)

    def export_json(self):
        config = {
            "resolution": [1920, 1080],
            "forbidden_areas": self.rects
        }
        file_path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON files", "*.json")])
        if file_path:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
            messagebox.showinfo("Export", f"Config saved to {file_path}")

    def clear_canvas(self):
        self.canvas.delete("all")
        self.rects.clear()
        self.bg_image_id = None
        self.bg_image = None

if __name__ == "__main__":
    root = tk.Tk()
    AreaDrawer(root)
    root.mainloop()