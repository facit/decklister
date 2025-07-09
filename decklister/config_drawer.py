import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
from PIL import Image, ImageTk  # Requires pillow: pip install pillow
import json

class AreaDrawer:
    def __init__(self, master):
        self.master = master
        self.master.title("Config Area Drawer")
        self.canvas = tk.Canvas(master, width=1920, height=1080, bg="white", scrollregion=(0,0,1920,1080))
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.rects = [] # List of dicts: {"name": ..., "coords": [...]}
        self.start_x = self.start_y = None
        self.current_rect = None
        self.bg_image = None
        self.bg_image_id = None
        self.resolution = [1920, 1080]

        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)

        menu = tk.Menu(master)
        master.config(menu=menu)
        file_menu = tk.Menu(menu, tearoff=0)
        menu.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Load Background Image", command=self.load_background)
        file_menu.add_command(label="Set Resolution", command=self.set_resolution)
        file_menu.add_command(label="Export JSON", command=self.export_json)
        file_menu.add_command(label="Clear", command=self.clear_canvas)

    def load_background(self):
        file_path = filedialog.askopenfilename(filetypes=[("Image files", "*.png;*.jpg;*.jpeg;*.bmp;*.gif")])
        if file_path:
            img = Image.open(file_path)
            width, height = img.size  # Use the image's native resolution
            img = img.resize((width, height), Image.Resampling.LANCZOS)
            self.bg_image = ImageTk.PhotoImage(img)
            if self.bg_image_id:
                self.canvas.delete(self.bg_image_id)
            self.bg_image_id = self.canvas.create_image(0, 0, anchor="nw", image=self.bg_image)
            self.canvas.config(width=width, height=height, scrollregion=(0, 0, width, height))
            self.master.geometry(f"{width}x{height}")
            self.resolution = [width, height]  # Store for export_json
            self.canvas.tag_lower(self.bg_image_id)
        else:
            self.resolution = [1920, 1080]  # Default if no image loaded

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
        # Ask user for a name for this rectangle
        name = simpledialog.askstring("Rectangle Name", "Enter a name for this area:", parent=self.master)
        if name:
            self.rects.append((name, rect))
            # Optionally, draw the name on the canvas
            self.canvas.create_text((rect[0]+rect[2])//2, (rect[1]+rect[3])//2, text=name, fill="blue")
        else:
            # If no name is given, remove the rectangle
            self.canvas.delete(self.current_rect)

    def export_json(self):
        # Use the current resolution (set by background image or default)
        config = {
            "resolution": getattr(self, "resolution", [1920, 1080])
        }
        for name, coords in self.rects:
            config[name] = coords
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

    def set_resolution(self):
        popup = tk.Toplevel(self.master)
        popup.title("Set Resolution")
        popup.grab_set()
        tk.Label(popup, text="Width:").grid(row=0, column=0, padx=5, pady=5)
        width_var = tk.IntVar(value=self.resolution[0])
        width_entry = tk.Entry(popup, textvariable=width_var)
        width_entry.grid(row=0, column=1, padx=5, pady=5)
        tk.Label(popup, text="Height:").grid(row=1, column=0, padx=5, pady=5)
        height_var = tk.IntVar(value=self.resolution[1])
        height_entry = tk.Entry(popup, textvariable=height_var)
        height_entry.grid(row=1, column=1, padx=5, pady=5)

        def apply():
            try:
                width = int(width_var.get())
                height = int(height_var.get())
                if width > 0 and height > 0:
                    self.resolution = [width, height]
                    self.canvas.config(width=width, height=height, scrollregion=(0, 0, width, height))
                    self.master.geometry(f"{width}x{height}")
                    # Remove background image if present, since it may not match new resolution
                    if self.bg_image_id:
                        self.canvas.delete(self.bg_image_id)
                        self.bg_image_id = None
                        self.bg_image = None
                    popup.destroy()
            except Exception:
                messagebox.showerror("Invalid input", "Please enter valid positive integers for width and height.")

        tk.Button(popup, text="OK", command=apply).grid(row=2, column=0, columnspan=2, pady=10)
        width_entry.focus_set()

if __name__ == "__main__":
    root = tk.Tk()
    AreaDrawer(root)
    root.mainloop()