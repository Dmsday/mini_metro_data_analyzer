import time
import threading
import subprocess
import pyautogui
import keyboard
import pygetwindow as gw
import cv2
import numpy as np
import tkinter as tk
from detectors import analyze_game_image
import json
import os

# Global variables
analysis_running = False
analysis_history = []
visualizer_proc = None

CONFIG_FILE = "regions_config.json"
# Load configured regions if available; otherwise, use defaults.
if os.path.exists(CONFIG_FILE):
    try:
        with open(CONFIG_FILE, "r") as f:
            detection_regions = json.load(f)
    except Exception as e:
        print("Error loading config, using defaults:", e)
        detection_regions = {
            "score_region": [0.838, 0.062, 0.045, 0.03],
            "train_region": [0.358, 0.916, 0.02, 0.03],
            "tunnel_region": [0.709, 0.916, 0.02, 0.03],
            "lines_region": [0.385, 0.913, 0.26, 0.06],
            "station_map_region": [0.01, 0.105, 0.98, 0.8],
            "wagon_region": [0.305, 0.916, 0.02, 0.03]
        }
else:
    detection_regions = {
        "score_region": [0.838, 0.062, 0.045, 0.03],
        "train_region": [0.358, 0.916, 0.02, 0.03],
        "tunnel_region": [0.709, 0.916, 0.02, 0.03],
        "lines_region": [0.385, 0.913, 0.26, 0.06],
        "station_map_region": [0.01, 0.105, 0.98, 0.8],
        "wagon_region": [0.305, 0.916, 0.02, 0.03]
    }

def find_game_window():
    """
    Finds the game window titled exactly "Mini Metro", activates it, and waits 0.1 s.
    Returns (left, top, width, height) if found; otherwise, None.
    """
    windows = gw.getWindowsWithTitle("Mini Metro")
    for w in windows:
        if w.title.strip() == "Mini Metro":
            try:
                w.activate()
                time.sleep(0.1)
            except Exception as e:
                print("Error activating game window:", e)
            return (w.left, w.top, w.width, w.height)
    return None

def capture_game_window(window_box):
    """
    Captures a screenshot of the specified window region.
    Returns an OpenCV BGR image.
    """
    try:
        screenshot = pyautogui.screenshot(region=window_box)
        image = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
        return image
    except Exception as e:
        print(f"Error capturing window: {e}")
        return None

# Create main window
root = tk.Tk()
root.title("Mini Metro Real-Time Analysis")

# Create StringVar for GUI elements
score_var = tk.StringVar()
trains_var = tk.StringVar()
tunnels_var = tk.StringVar()
lines_avail_var = tk.StringVar()
lines_locked_var = tk.StringVar()
stations_var = tk.StringVar()
placed_lines_var = tk.StringVar()
trains_detected_var = tk.StringVar()
wagons_var = tk.StringVar()

# Create and layout GUI elements
tk.Label(root, text="Score:").grid(row=0, column=0, sticky="e")
tk.Entry(root, textvariable=score_var, width=20).grid(row=0, column=1)

tk.Label(root, text="Available Trains:").grid(row=1, column=0, sticky="e")
tk.Entry(root, textvariable=trains_var, width=20).grid(row=1, column=1)

tk.Label(root, text="Available Tunnels:").grid(row=2, column=0, sticky="e")
tk.Entry(root, textvariable=tunnels_var, width=20).grid(row=2, column=1)

tk.Label(root, text="Available Metro Lines:").grid(row=3, column=0, sticky="e")
tk.Entry(root, textvariable=lines_avail_var, width=10).grid(row=3, column=1, sticky="w")
tk.Entry(root, textvariable=lines_locked_var, width=10).grid(row=3, column=1, sticky="e")

tk.Label(root, text="Stations Detected:").grid(row=4, column=0, sticky="e")
tk.Entry(root, textvariable=stations_var, width=30).grid(row=4, column=1)

tk.Label(root, text="Placed Lines Detected:").grid(row=5, column=0, sticky="e")
tk.Entry(root, textvariable=placed_lines_var, width=30).grid(row=5, column=1)

tk.Label(root, text="Trains on Map:").grid(row=6, column=0, sticky="e")
tk.Entry(root, textvariable=trains_detected_var, width=30).grid(row=6, column=1)

tk.Label(root, text="Available Wagons:").grid(row=7, column=0, sticky="e")
tk.Entry(root, textvariable=wagons_var, width=20).grid(row=7, column=1)

def update_gui(data):
    """
    Updates GUI fields with the latest analysis data.
    """
    score_var.set(str(data.get('score', 0)))
    trains_var.set(str(data.get('available_trains', 0)))
    tunnels_var.set(str(data.get('available_tunnels', 0)))

    avail_lines = data.get('available_lines', {})
    lines_avail_var.set("Avail: " + str(avail_lines.get("available", 0)))
    lines_locked_var.set("Locked: " + str(avail_lines.get("locked", 0)))

    stations = data.get('stations', [])
    stations_var.set(f"{len(stations)} detected")

    placed_lines = data.get('placed_lines', [])
    placed_lines_var.set(f"{len(placed_lines)} detected")

    trains = data.get('trains', [])
    train_info = f"{len(trains)} detected"
    if trains:
        wagon_count = sum(1 for t in trains if t.get('has_wagon'))
        train_info += f" (wagons: {wagon_count})"
    trains_detected_var.set(train_info)

    wagons_var.set(str(data.get('available_wagons', 0)))

# Add "Manual Update" button
tk.Button(root, text="Manual Update",
          command=lambda: update_gui(analysis_history[-1] if analysis_history else {})) \
    .grid(row=8, column=0, columnspan=2, pady=5)

def analysis_loop():
    """
    Main analysis loop that runs in a separate thread.
    Continuously captures and analyzes the game window when analysis_running is True.
    """
    global analysis_running, analysis_history
    while True:
        try:
            if analysis_running:
                window_box = find_game_window()
                if window_box:
                    image = capture_game_window(window_box)
                    if image is not None:
                        data = analyze_game_image(image, window_box[2], window_box[3], detection_regions)
                        if data.get('score', 0) > 0:
                            analysis_history.append(data)
                            if len(analysis_history) > 5:
                                analysis_history.pop(0)
                            root.after(0, update_gui, data)
                        else:
                            print("Game not running (score=0)")
                else:
                    print("Mini Metro game window not found.")
                time.sleep(1)
            else:
                time.sleep(0.1)
        except Exception as e:
            print(f"Error in analysis loop: {e}")
            time.sleep(1)

def toggle_analysis():
    """
    Toggles the analysis on/off. Called when shift+r is pressed.
    """
    global analysis_running
    analysis_running = not analysis_running
    if analysis_running:
        print("Analysis started.")
    else:
        print("Analysis stopped.")

def launch_visualizer():
    """
    Launches the visualizer process and returns the process object.
    """
    try:
        if os.name == 'nt':  # Windows
            # Use CREATE_NEW_PROCESS_GROUP flag instead of DETACHED_PROCESS
            CREATE_NEW_PROCESS_GROUP = 0x00000200
            return subprocess.Popen(["python", "visualizer.py"],
                                  creationflags=CREATE_NEW_PROCESS_GROUP)
        else:  # Unix-like
            return subprocess.Popen(["python3", "visualizer.py"])
    except Exception as e:
        print("Error launching visualizer:", e)
        return None

def on_closing():
    """
    Handler for when the main window is closed.
    Terminates the visualizer process if it's running.
    """
    global visualizer_proc
    if visualizer_proc:
        try:
            visualizer_proc.terminate()
        except Exception as e:
            print(f"Error terminating visualizer: {e}")
    root.destroy()
    os._exit(0)

if __name__ == "__main__":
    # Set up keyboard shortcut
    keyboard.add_hotkey('shift+r', toggle_analysis)

    # Start analysis thread
    analysis_thread = threading.Thread(target=analysis_loop, daemon=True)
    analysis_thread.start()

    # Launch visualizer
    visualizer_proc = launch_visualizer()
    if not visualizer_proc:
        print("Failed to launch visualizer")
        root.destroy()
        os._exit(1)

    # Set up closing handler
    root.protocol("WM_DELETE_WINDOW", on_closing)

    # Start main GUI loop
    try:
        root.mainloop()
    except Exception as e:
        print(f"Error in main loop: {e}")
        if visualizer_proc:
            visualizer_proc.terminate()
        os._exit(1)