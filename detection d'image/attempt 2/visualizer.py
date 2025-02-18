# visualizer.py
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk
import pyautogui
import cv2
import numpy as np
import pygetwindow as gw
import json
import os
from detectors import get_absolute_region, analyze_game_image

CONFIG_FILE = "regions_config.json"

# Default detection regions (with three decimal places)
default_regions = {
    "score_region": [0.800, 0.000, 0.180, 0.100],
    "train_region": [0.100, 0.850, 0.200, 0.100],
    "tunnel_region": [0.700, 0.850, 0.200, 0.100],
    "lines_region": [0.350, 0.850, 0.300, 0.100],
    "station_map_region": [0.000, 0.000, 1.000, 0.800],
    "wagon_region": [0.100, 0.750, 0.200, 0.100]
}

# Load detection regions from config file if available
if os.path.exists(CONFIG_FILE):
    try:
        with open(CONFIG_FILE, "r") as f:
            detection_regions = json.load(f)
    except Exception as e:
        print("Error loading configuration, using defaults:", e)
        detection_regions = default_regions.copy()
else:
    detection_regions = default_regions.copy()


def find_game_window():
    """
    Finds the game window titled exactly "Mini Metro", activates it,
    and waits 0.5 seconds.
    Returns (left, top, width, height) if found; otherwise, None.
    """
    windows = gw.getWindowsWithTitle("Mini Metro")
    for w in windows:
        if w.title.strip() == "Mini Metro":
            try:
                w.activate()
                import time
                time.sleep(0.5)
            except Exception as e:
                print("Error activating game window:", e)
            return (w.left, w.top, w.width, w.height)
    return None


def capture_game_window(window_box):
    """
    Captures a screenshot of the specified window region.
    Returns an OpenCV BGR image.
    """
    screenshot = pyautogui.screenshot(region=window_box)
    image = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
    return image


def cv2_to_tk(image):
    """
    Converts an OpenCV BGR image to an ImageTk.PhotoImage.
    """
    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    from PIL import Image
    pil_image = Image.fromarray(image_rgb)
    return ImageTk.PhotoImage(pil_image)


class VisualizerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Mini Metro Detection Visualizer")
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.window_box = find_game_window()
        if not self.window_box:
            messagebox.showerror("Error", "Mini Metro game window not found!")
            self.destroy()
            return
        self.left, self.top, self.win_width, self.win_height = self.window_box

        # Create a canvas for displaying the screenshot and overlays.
        self.canvas = tk.Canvas(self, width=self.win_width, height=self.win_height, bg="black")
        self.canvas.grid(row=0, column=0, padx=5, pady=5)

        # Create a configuration panel to modify detection regions.
        self.config_frame = tk.Frame(self)
        self.config_frame.grid(row=0, column=1, sticky="n", padx=5, pady=5)

        tk.Label(self.config_frame, text="Detection Regions (x,y,w,h as %)").grid(row=0, column=0, columnspan=2, pady=2)
        self.region_vars = {}
        row = 1
        for region_name, rel_coords in detection_regions.items():
            tk.Label(self.config_frame, text=f"{region_name}:").grid(row=row, column=0, sticky="w")
            var = tk.StringVar(value=",".join(f"{c:.3f}" for c in rel_coords))
            self.region_vars[region_name] = var
            tk.Entry(self.config_frame, textvariable=var, width=20).grid(row=row, column=1)
            row += 1

        tk.Button(self.config_frame, text="Refresh Screenshot", command=self.refresh_image) \
            .grid(row=row, column=0, pady=5)
        tk.Button(self.config_frame, text="Apply Changes", command=self.apply_changes) \
            .grid(row=row, column=1, pady=5)
        row += 1

        self.photo = None
        self.refresh_image()

    def refresh_image(self):
        """
        Captures a fresh screenshot (with the game window in the foreground),
        clears the canvas, draws detection region overlays, and overlays
        the detection results (stations, station demands, trains, and lines).
        """
        self.window_box = find_game_window()
        if not self.window_box:
            print("Mini Metro game window not found!")
            return
        self.left, self.top, self.win_width, self.win_height = self.window_box
        base_image = capture_game_window(self.window_box)
        overlay = base_image.copy()
        self.canvas.delete("all")
        # Draw detection region rectangles
        for region_name, var in self.region_vars.items():
            try:
                rel_values = [float(x.strip()) for x in var.get().split(",")]
                detection_regions[region_name] = rel_values
                x, y, w, h = get_absolute_region(rel_values, self.win_width, self.win_height)
                cv2.rectangle(overlay, (x, y), (x + w, y + h), (0, 255, 0), 2)
                cv2.putText(overlay, region_name, (x, y - 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            except Exception as e:
                print(f"Error drawing {region_name}: {e}")
        # Run analysis with the current configuration and overlay results
        analysis = analyze_game_image(base_image, self.win_width, self.win_height, detection_regions)
        # Overlay stations: draw a circle and label with shape
        for station in analysis.get('stations', []):
            bx, by, bw, bh = station["bbox"]
            center = (bx + bw // 2, by + bh // 2)
            cv2.circle(overlay, center, 10, (255, 0, 0), 2)
            cv2.putText(overlay, station["shape"], (center[0] - 20, center[1] - 15),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
        # Overlay station demands: for each station, draw demand shapes above it
        for demand in analysis.get('station_demands', []):
            # For simplicity, label them near the station center (offset upward)
            station = analysis.get('stations', [])[demand["station_id"]]
            bx, by, bw, bh = station["bbox"]
            pos = (bx + bw // 2, by - 10)
            demand_text = ",".join(demand["demands"])
            cv2.putText(overlay, demand_text, pos,
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1)
        # Overlay trains: draw their bounding boxes and a label
        for train in analysis.get('trains', []):
            bx, by, bw, bh = train["bbox"]
            cv2.rectangle(overlay, (bx, by), (bx + bw, by + bh), train["color"], 2)
            cv2.putText(overlay, "Train", (bx, by - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, train["color"], 1)
        # Overlay placed lines: draw the line segments
        for line_data in analysis.get('placed_lines', []):  # line_data contient "color" et "segments"
            for segment in line_data["segments"]:  # Boucle sur les segments individuels
                cv2.line(overlay, segment["start"], segment["end"], line_data["color"], 2)
        self.photo = cv2_to_tk(overlay)
        self.canvas.config(width=self.win_width, height=self.win_height)
        self.canvas.create_image(0, 0, anchor="nw", image=self.photo)

    def apply_changes(self):
        """
        Reads new region values, updates detection_regions, saves them to config,
        and refreshes the screenshot.
        """
        global detection_regions
        for region_name, var in self.region_vars.items():
            try:
                parts = var.get().split(',')
                new_coords = [float(p.strip()) for p in parts]
                if len(new_coords) == 4:
                    detection_regions[region_name] = new_coords
            except Exception as e:
                print(f"Error updating {region_name}: {e}")
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(detection_regions, f)
            print("Detection regions updated and saved!")
        except Exception as e:
            print("Error saving configuration:", e)
        self.refresh_image()

    def on_close(self):
        """
        Called when the visualizer window is closed.
        Exits the entire application.
        """
        self.destroy()
        import os
        os._exit(0)


if __name__ == "__main__":
    app = VisualizerApp()
    app.mainloop()
