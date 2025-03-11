import time
import threading
import subprocess
import pyautogui
import keyboard
import pygetwindow as gw
import cv2
import numpy as np
import tkinter as tk
from tkinter import messagebox, ttk
import logging
from datetime import datetime
import json
import os
from detectors_py import analyze_game_image


# ----------------------- Logger Setup -----------------------
def setup_logger():
    log_filename = f"mini_metro_analyzer_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    logging.basicConfig(
        filename=log_filename,
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    # Also log to console
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    logging.getLogger('').addHandler(console)
    logging.info("Application started")


# ----------------------- Global Variables -----------------------
MAX_CONSECUTIVE_ERRORS = 5
error_count = 0
last_valid_data = None

history_data = {
    'times': [],
    'scores': [],
    'passengers': []
}

UPDATE_INTERVAL = 2000  # in milliseconds
CONFIG_FILE = "regions_config.json"
if os.path.exists(CONFIG_FILE):
    try:
        with open(CONFIG_FILE, "r") as f:
            detection_regions = json.load(f)
    except Exception as e:
        logging.error(f"Error loading config: {e}", exc_info=True)
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

analysis_running = False
visualizer_proc = None
manual_entry = None  # Will be set in the UI section


# ----------------------- Utility Functions -----------------------
def find_game_window():
    """
    Searches for the "Mini Metro" game window, activates it, and returns its position.
    Returns (left, top, width, height) if found; otherwise, returns None.
    """
    windows = gw.getWindowsWithTitle("Mini Metro")
    for w in windows:
        if w.title.strip() == "Mini Metro":
            try:
                w.activate()
                time.sleep(0.1)
            except Exception as e:
                logging.error(f"Error activating game window: {e}", exc_info=True)
            return (w.left, w.top, w.width, w.height)
    return None


def capture_game_window(window_box):
    """
    Captures a screenshot of the specified window region.
    Returns an OpenCV BGR image, or None if an error occurs.
    """
    try:
        screenshot = pyautogui.screenshot(region=window_box)
        image = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
        return image
    except Exception as e:
        logging.error(f"Error capturing window: {e}", exc_info=True)
        return None


def launch_visualizer():
    """
    Launches the visualizer process and returns the process object.
    """
    try:
        if os.name == 'nt':  # Windows
            CREATE_NEW_PROCESS_GROUP = 0x00000200
            return subprocess.Popen(["python", "visualizer.py"],
                                    creationflags=CREATE_NEW_PROCESS_GROUP)
        else:
            return subprocess.Popen(["python3", "visualizer.py"])
    except Exception as e:
        logging.error(f"Error launching visualizer: {e}", exc_info=True)
        return None


def open_visualizer():
    """
    Opens the visualizer (for recalibration, for example).
    """
    global visualizer_proc
    visualizer_proc = launch_visualizer()


def show_recalibration_prompt():
    """
    Displays a dialog prompting the user to recalibrate the detection zones.
    """
    if messagebox.askyesno("Recalibration",
                           "Unable to properly detect the game. Would you like to recalibrate the detection zones?"):
        open_visualizer()


def show_error_dialog(title, message):
    """
    Displays an error dialog.
    """
    messagebox.showerror(title, message)


def schedule_update():
    """
    Schedules the next update_analysis call after UPDATE_INTERVAL milliseconds.
    """
    root.after(UPDATE_INTERVAL, update_analysis)


def validate_data(data):
    """
    Validates the consistency of the detected data.
    For example, it checks that the score hasn't decreased or increased unrealistically.
    """
    if last_valid_data and 'score' in data and 'score' in last_valid_data:
        score_diff = data['score'] - last_valid_data['score']
        if score_diff < 0 or score_diff > 100:
            return False
    return True


def update_history_graph(data):
    """
    Updates the historical graph with the new data.
    """
    current_time = datetime.now()
    history_data['times'].append(current_time)
    history_data['scores'].append(data.get('score', 0))
    history_data['passengers'].append(data.get('total_passengers', 0))
    if len(history_data['times']) > 60:
        history_data['times'].pop(0)
        history_data['scores'].pop(0)
        history_data['passengers'].pop(0)
    canvas = detail_vars['stats_canvas']
    canvas.delete("all")
    max_score = max(history_data['scores']) * 1.1 if history_data['scores'] else 100
    draw_line_graph(canvas, history_data['times'], history_data['scores'], color="blue", max_value=max_score)
    canvas.create_text(250, 20, text="Score Evolution", fill="black")


def draw_line_graph(canvas, x_data, y_data, color="blue", max_value=None):
    """
    Draws a simple line graph on the given canvas.
    """
    width = canvas.winfo_width()
    height = canvas.winfo_height()
    if not max_value:
        max_value = max(y_data) if y_data else 100
    points = []
    for i, y in enumerate(y_data):
        x_pos = int(i * width / (len(x_data) - 1 if len(x_data) > 1 else 1))
        y_pos = int(height - (y / max_value) * (height - 40))
        points.append((x_pos, y_pos))
    if len(points) > 1:
        flat_points = []
        for p in points:
            flat_points.extend(p)
        canvas.create_line(flat_points, fill=color, width=2)


def update_ui_with_data(data):
    """
    Updates both the main UI and the detailed section with the analysis data.
    """
    score_var.set(str(data.get('score', 'N/A')))
    trains_var.set(str(data.get('available_trains', 'N/A')))
    tunnels_var.set(str(data.get('available_tunnels', 'N/A')))

    avail_lines = data.get('available_lines', {})
    lines_avail_var.set("Avail: " + str(avail_lines.get("available", 'N/A')))
    lines_locked_var.set("Locked: " + str(avail_lines.get("locked", 'N/A')))

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
    wagons_var.set(str(data.get('available_wagons', 'N/A')))

    # Update detailed information if available
    if 'station_types' in data:
        detail_vars['station_types'].set(
            f"Circle: {data['station_types'].get('circle', 0)}, "
            f"Triangle: {data['station_types'].get('triangle', 0)}, "
            f"Square: {data['station_types'].get('square', 0)}"
        )
    if 'passenger_counts' in data:
        detail_vars['passenger_counts'].set(str(data['passenger_counts']))
    if 'line_efficiency' in data:
        detail_vars['line_efficiency'].set(str(data['line_efficiency']))

    update_history_graph(data)


def update_analysis():
    """
    Main analysis function with error recovery.
    It captures the screen, analyzes the image, validates the data, and updates the UI.
    In case of errors, it uses a recovery mechanism after MAX_CONSECUTIVE_ERRORS failures.
    """
    global error_count, last_valid_data
    if not analysis_running:
        schedule_update()
        return

    window_box = find_game_window()
    if window_box is None:
        logging.warning("Mini Metro game window not found.")
        schedule_update()
        return

    try:
        image = capture_game_window(window_box)
        if image is None:
            error_count += 1
            logging.warning(f"Screenshot capture failed. Attempt {error_count}/{MAX_CONSECUTIVE_ERRORS}")
            if error_count >= MAX_CONSECUTIVE_ERRORS:
                logging.error("Too many consecutive errors. Recalibration needed.")
                show_recalibration_prompt()
                error_count = 0
            else:
                if last_valid_data:
                    update_ui_with_data(last_valid_data)
                schedule_update()
                return
        else:
            error_count = 0  # Reset error count on success

        data = analyze_game_image(image, window_box[2], window_box[3], detection_regions)
        if validate_data(data):
            last_valid_data = data
            update_ui_with_data(data)
        else:
            logging.warning("Inconsistent data detected")
            if last_valid_data:
                update_ui_with_data(last_valid_data)
    except Exception as e:
        error_count += 1
        logging.error(f"Error in analysis loop: {e}", exc_info=True)
        if error_count >= MAX_CONSECUTIVE_ERRORS:
            logging.critical("Critical error - too many consecutive errors")
            show_error_dialog("Critical Error", f"Analysis encountered too many consecutive errors. Details: {str(e)}")
            error_count = 0

    schedule_update()


def toggle_analysis():
    """
    Toggles the analysis on/off when the shortcut (shift+r) is pressed.
    """
    global analysis_running
    analysis_running = not analysis_running
    if analysis_running:
        logging.info("Analysis started.")
    else:
        logging.info("Analysis stopped.")


def apply_settings():
    """
    Applies the new update interval set via the slider and/or manual entry.
    """
    global UPDATE_INTERVAL, manual_entry
    try:
        manual_val = manual_entry.get()
        if manual_val.strip() != "":
            new_val = int(manual_val)
        else:
            new_val = update_interval_var.get()
        update_interval_var.set(new_val)
        UPDATE_INTERVAL = new_val
        logging.info(f"New update interval set to {UPDATE_INTERVAL} ms")
    except ValueError:
        logging.error("Invalid manual input for update interval", exc_info=True)


# ----------------------- Detailed UI Setup -----------------------
def setup_detailed_ui():
    """
    Creates an interface with a "Main" tab and a "Details" tab.
    The "Details" tab contains a canvas for historical statistics and a frame for detailed textual information.
    """
    notebook = ttk.Notebook(root)
    notebook.pack(fill='both', expand=True)

    # Main tab for basic information
    main_frame = ttk.Frame(notebook)
    notebook.add(main_frame, text='Main')

    # Details tab for statistics and extra details
    detail_frame = ttk.Frame(notebook)
    notebook.add(detail_frame, text='Details')

    # Place basic widgets in the main tab
    basic_frame = ttk.Frame(main_frame)
    basic_frame.pack(pady=10)

    ttk.Label(basic_frame, text="Score:").grid(row=0, column=0, sticky="e")
    score_entry = ttk.Entry(basic_frame, textvariable=score_var, width=20)
    score_entry.grid(row=0, column=1)

    ttk.Label(basic_frame, text="Available Trains:").grid(row=1, column=0, sticky="e")
    trains_entry = ttk.Entry(basic_frame, textvariable=trains_var, width=20)
    trains_entry.grid(row=1, column=1)

    ttk.Label(basic_frame, text="Available Tunnels:").grid(row=2, column=0, sticky="e")
    tunnels_entry = ttk.Entry(basic_frame, textvariable=tunnels_var, width=20)
    tunnels_entry.grid(row=2, column=1)

    ttk.Label(basic_frame, text="Available Metro Lines:").grid(row=3, column=0, sticky="e")
    lines_avail_entry = ttk.Entry(basic_frame, textvariable=lines_avail_var, width=10)
    lines_avail_entry.grid(row=3, column=1, sticky="w")
    lines_locked_entry = ttk.Entry(basic_frame, textvariable=lines_locked_var, width=10)
    lines_locked_entry.grid(row=3, column=2, sticky="e")

    ttk.Label(basic_frame, text="Stations Detected:").grid(row=4, column=0, sticky="e")
    stations_entry = ttk.Entry(basic_frame, textvariable=stations_var, width=30)
    stations_entry.grid(row=4, column=1)

    ttk.Label(basic_frame, text="Placed Lines Detected:").grid(row=5, column=0, sticky="e")
    placed_lines_entry = ttk.Entry(basic_frame, textvariable=placed_lines_var, width=30)
    placed_lines_entry.grid(row=5, column=1)

    ttk.Label(basic_frame, text="Trains on Map:").grid(row=6, column=0, sticky="e")
    trains_detected_entry = ttk.Entry(basic_frame, textvariable=trains_detected_var, width=30)
    trains_detected_entry.grid(row=6, column=1)

    ttk.Label(basic_frame, text="Available Wagons:").grid(row=7, column=0, sticky="e")
    wagons_entry = ttk.Entry(basic_frame, textvariable=wagons_var, width=20)
    wagons_entry.grid(row=7, column=1)

    # Manual update button
    update_button = ttk.Button(main_frame, text="Manual Update",
                               command=lambda: update_ui_with_data(last_valid_data if last_valid_data else {}))
    update_button.pack(pady=5)

    # Modified update interval section with slider and manual entry
    interval_frame = ttk.Frame(main_frame)
    interval_frame.pack(pady=5)
    ttk.Label(interval_frame, text="Update Interval (ms):").grid(row=0, column=0, sticky="e")

    # Function to update the label with the current value from the slider
    def update_interval_label(value):
        interval_value_label.config(text=f"{int(float(value))} ms")

    interval_scale = ttk.Scale(
        interval_frame,
        from_=500,
        to=5000,
        orient="horizontal",
        variable=update_interval_var,
        command=update_interval_label
    )
    interval_scale.grid(row=0, column=1, padx=5)

    interval_value_label = ttk.Label(interval_frame, text=f"{update_interval_var.get()} ms")
    interval_value_label.grid(row=0, column=2, padx=5)

    # Manual entry field for update interval
    ttk.Label(interval_frame, text="Or enter manually:").grid(row=1, column=0, sticky="e")
    global manual_entry
    manual_entry = ttk.Entry(interval_frame, width=10)
    manual_entry.grid(row=1, column=1, padx=5)

    apply_button = ttk.Button(interval_frame, text="Apply", command=apply_settings)
    apply_button.grid(row=2, column=0, columnspan=3)

    # Details tab: canvas for statistics and frame for detailed info
    stats_canvas = tk.Canvas(detail_frame, width=500, height=300)
    stats_canvas.pack(pady=10)
    stats_frame = ttk.LabelFrame(detail_frame, text="Detailed Statistics")
    stats_frame.pack(fill='both', expand=True, padx=10, pady=10)

    station_types_var = tk.StringVar()
    passenger_counts_var = tk.StringVar()
    line_efficiency_var = tk.StringVar()

    ttk.Label(stats_frame, text="Station Types:").grid(row=0, column=0, sticky="w")
    ttk.Label(stats_frame, textvariable=station_types_var).grid(row=0, column=1, sticky="w")

    ttk.Label(stats_frame, text="Passengers per Station:").grid(row=1, column=0, sticky="w")
    ttk.Label(stats_frame, textvariable=passenger_counts_var).grid(row=1, column=1, sticky="w")

    ttk.Label(stats_frame, text="Line Efficiency:").grid(row=2, column=0, sticky="w")
    ttk.Label(stats_frame, textvariable=line_efficiency_var).grid(row=2, column=1, sticky="w")

    return {
        'station_types': station_types_var,
        'passenger_counts': passenger_counts_var,
        'line_efficiency': line_efficiency_var,
        'stats_canvas': stats_canvas
    }


# ----------------------- Main Interface Creation -----------------------
root = tk.Tk()
root.title("Mini Metro Real-Time Analysis")

# Variable for update interval
update_interval_var = tk.IntVar(root, value=UPDATE_INTERVAL)

# Variables for main data display
score_var = tk.StringVar()
trains_var = tk.StringVar()
tunnels_var = tk.StringVar()
lines_avail_var = tk.StringVar()
lines_locked_var = tk.StringVar()
stations_var = tk.StringVar()
placed_lines_var = tk.StringVar()
trains_detected_var = tk.StringVar()
wagons_var = tk.StringVar()

# Create the detailed interface (Main and Details tabs)
detail_vars = setup_detailed_ui()

# ----------------------- Keyboard Shortcut and Scheduling -----------------------
keyboard.add_hotkey('shift+r', toggle_analysis)
root.after(UPDATE_INTERVAL, update_analysis)


def on_closing():
    global visualizer_proc
    if visualizer_proc:
        try:
            visualizer_proc.terminate()
        except Exception as e:
            logging.error(f"Error terminating visualizer: {e}", exc_info=True)
    root.destroy()
    os._exit(0)


root.protocol("WM_DELETE_WINDOW", on_closing)

# ----------------------- Application Startup -----------------------
if __name__ == "__main__":
    setup_logger()
    logging.info("Starting application")
    root.mainloop()
