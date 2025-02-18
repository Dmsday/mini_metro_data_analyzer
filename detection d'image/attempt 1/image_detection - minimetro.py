import time
import threading
import cv2
import numpy as np
import pyautogui
import keyboard
import pygetwindow as gw
import pytesseract
import tkinter as tk

# --------------------------
# GLOBAL VARIABLES & SETTINGS
# --------------------------
analysis_running = False
# List to store the analysis results for the last 5 screenshots
analysis_history = []

# Configure pytesseract if needed (for example, set tesseract_cmd)
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Define relative regions (offsets and sizes) within the game window.
# These values must be tuned for your particular setup.
# All regions are defined as (x_offset, y_offset, width, height)
regions = {
    "score_region": (10, 10, 150, 50),         # Region where the score is displayed
    "station_region": (50, 70, 500, 300),        # Region where stations appear (assumed circular)
    "train_region": (50, 400, 500, 150),         # Region where trains are shown (assumed rectangular shapes)
    "resource_region": (600, 10, 200, 150),      # Region where resource numbers (crossings, lines, tunnels) are shown
    "line_region": (600, 170, 200, 150)          # Region where line color icons appear
}

# --------------------------
# UTILITY FUNCTIONS
# --------------------------
def find_mini_metro_window():
    """
    Search for a window with a title that includes "Mini Metro".
    Returns the (left, top, width, height) tuple if found, otherwise None.
    """
    windows = gw.getWindowsWithTitle("Mini Metro")
    if windows:
        w = windows[0]
        return (w.left, w.top, w.width, w.height)
    return None

def capture_game_window(window_box):
    """
    Capture a screenshot of the game window region.
    Returns an OpenCV image (BGR).
    """
    # window_box is (left, top, width, height)
    screenshot = pyautogui.screenshot(region=window_box)
    # Convert the PIL image to a NumPy array and then to BGR format for OpenCV
    image = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
    return image

# --------------------------
# DETECTION FUNCTIONS
# --------------------------
def extract_score(image, region):
    """
    Extract the score from a specific region using OCR.
    'region' is defined relative to the game window.
    """
    x, y, w, h = region
    score_img = image[y:y+h, x:x+w]
    # Preprocess: convert to grayscale and threshold to improve OCR
    gray = cv2.cvtColor(score_img, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
    text = pytesseract.image_to_string(thresh, config='--psm 7 digits')
    try:
        # Extract numbers from the OCR result
        score = int(''.join(filter(str.isdigit, text)))
    except ValueError:
        score = 0
    return score

def count_stations(image, region):
    """
    Count the number of stations by detecting circular shapes using Hough Circle Transform.
    'region' is defined relative to the game window.
    """
    x, y, w, h = region
    station_img = image[y:y+h, x:x+w]
    gray = cv2.cvtColor(station_img, cv2.COLOR_BGR2GRAY)
    gray = cv2.medianBlur(gray, 5)
    # HoughCircles parameters may need tuning for your actual image
    circles = cv2.HoughCircles(gray, cv2.HOUGH_GRADIENT, dp=1.2, minDist=30,
                               param1=50, param2=30, minRadius=10, maxRadius=40)
    if circles is not None:
        count = len(np.uint16(np.around(circles)))
    else:
        count = 0
    return count

def count_trains(image, region):
    """
    Count the number of trains by detecting contours that are likely train icons.
    'region' is defined relative to the game window.
    This function assumes train icons have a roughly rectangular shape.
    """
    x, y, w, h = region
    train_img = image[y:y+h, x:x+w]
    gray = cv2.cvtColor(train_img, cv2.COLOR_BGR2GRAY)
    # Use adaptive thresholding for better results on varying lighting
    thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                   cv2.THRESH_BINARY_INV, 11, 2)
    # Find contours
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    train_count = 0
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < 50 or area > 1000:
            continue
        # Approximate contour to a polygon and check if it is roughly rectangular
        approx = cv2.approxPolyDP(cnt, 0.02 * cv2.arcLength(cnt, True), True)
        if len(approx) == 4:
            train_count += 1
    return train_count

def extract_resources(image, region):
    """
    Extract resource numbers (e.g., crossings, lines, tunnels) via OCR.
    'region' is defined relative to the game window.
    For demonstration, we assume that the resource panel contains text like:
      "Crossings: 3 Lines: 5 Tunnels: 2"
    """
    x, y, w, h = region
    resource_img = image[y:y+h, x:x+w]
    gray = cv2.cvtColor(resource_img, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
    text = pytesseract.image_to_string(thresh, config='--psm 6')
    resources = {"crossings": 0, "lines": 0, "tunnels": 0}
    # Simple parsing: look for keywords and numbers
    for keyword in resources.keys():
        # Look for the keyword in a case-insensitive manner
        idx = text.lower().find(keyword)
        if idx != -1:
            # Get a substring starting at the keyword and extract numbers
            substr = text[idx:idx+15]
            num_str = ''.join(filter(str.isdigit, substr))
            try:
                resources[keyword] = int(num_str)
            except ValueError:
                resources[keyword] = 0
    return resources

def detect_line_colors(image, region, num_colors=3):
    """
    Detect the dominant colors in a given region (assumed to be where line color icons are displayed).
    Uses k-means clustering to find the top 'num_colors' dominant colors.
    Returns a list of color names (as hex strings).
    """
    x, y, w, h = region
    line_img = image[y:y+h, x:x+w]
    # Reshape image to a list of pixels
    pixels = line_img.reshape((-1, 3))
    pixels = np.float32(pixels)
    # Define criteria and apply k-means
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 0.5)
    _, labels, centers = cv2.kmeans(pixels, num_colors, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS)
    centers = np.uint8(centers)
    # Convert each dominant color to hex code
    colors = ['#{:02x}{:02x}{:02x}'.format(int(c[2]), int(c[1]), int(c[0])) for c in centers]
    return colors

def analyze_game_screenshot(game_image):
    """
    Perform full analysis on the given game image.
    Returns a dictionary with all detected information.
    """
    analysis = {}
    # Check if game has started by verifying that the score region yields a number > 0.
    analysis['score'] = extract_score(game_image, regions["score_region"])
    game_started = analysis['score'] > 0
    analysis['game_started'] = game_started

    if game_started:
        analysis['num_stations'] = count_stations(game_image, regions["station_region"])
        analysis['num_trains'] = count_trains(game_image, regions["train_region"])
        analysis['resources'] = extract_resources(game_image, regions["resource_region"])
        analysis['line_colors'] = detect_line_colors(game_image, regions["line_region"], num_colors=5)
    else:
        # If game not started, set default values
        analysis['num_stations'] = 0
        analysis['num_trains'] = 0
        analysis['resources'] = {"crossings": 0, "lines": 0, "tunnels": 0}
        analysis['line_colors'] = []
    return analysis

# --------------------------
# GUI: Tkinter window to display the analysis summary
# --------------------------
root = tk.Tk()
root.title("Mini Metro Analysis Summary")

# Tkinter StringVars for each piece of information
score_var = tk.StringVar()
stations_var = tk.StringVar()
trains_var = tk.StringVar()
crossings_var = tk.StringVar()
lines_var = tk.StringVar()
tunnels_var = tk.StringVar()
colors_var = tk.StringVar()

# Create labels and entry fields (editable) for each piece of data
tk.Label(root, text="Score:").grid(row=0, column=0, sticky='e')
tk.Entry(root, textvariable=score_var, width=20).grid(row=0, column=1)

tk.Label(root, text="Number of Stations:").grid(row=1, column=0, sticky='e')
tk.Entry(root, textvariable=stations_var, width=20).grid(row=1, column=1)

tk.Label(root, text="Number of Trains:").grid(row=2, column=0, sticky='e')
tk.Entry(root, textvariable=trains_var, width=20).grid(row=2, column=1)

tk.Label(root, text="Crossings:").grid(row=3, column=0, sticky='e')
tk.Entry(root, textvariable=crossings_var, width=20).grid(row=3, column=1)

tk.Label(root, text="Lines:").grid(row=4, column=0, sticky='e')
tk.Entry(root, textvariable=lines_var, width=20).grid(row=4, column=1)

tk.Label(root, text="Tunnels:").grid(row=5, column=0, sticky='e')
tk.Entry(root, textvariable=tunnels_var, width=20).grid(row=5, column=1)

tk.Label(root, text="Line Colors:").grid(row=6, column=0, sticky='e')
tk.Entry(root, textvariable=colors_var, width=40).grid(row=6, column=1)

def update_gui(analysis):
    """
    Update the GUI fields with the latest analysis data.
    """
    score_var.set(str(analysis.get('score', 0)))
    stations_var.set(str(analysis.get('num_stations', 0)))
    trains_var.set(str(analysis.get('num_trains', 0)))
    resources = analysis.get('resources', {})
    crossings_var.set(str(resources.get("crossings", 0)))
    lines_var.set(str(resources.get("lines", 0)))
    tunnels_var.set(str(resources.get("tunnels", 0)))
    colors_var.set(", ".join(analysis.get('line_colors', [])))

# Button to force a manual update with the latest data
tk.Button(root, text="Manual Update", command=lambda: update_gui(analysis_history[-1] if analysis_history else {}))\
    .grid(row=7, column=0, columnspan=2, pady=5)

# --------------------------
# ANALYSIS LOOP THREAD
# --------------------------
def analysis_loop():
    global analysis_running, analysis_history
    while True:
        if analysis_running:
            window_box = find_mini_metro_window()
            if window_box is not None:
                game_img = capture_game_window(window_box)
                analysis = analyze_game_screenshot(game_img)
                # Only store analysis if the game is running (score > 0)
                if analysis.get('game_started'):
                    analysis_history.append(analysis)
                    if len(analysis_history) > 5:
                        analysis_history.pop(0)
                    # Update GUI on the main thread
                    root.after(0, update_gui, analysis)
            else:
                print("Mini Metro window not found.")
            time.sleep(1)  # Wait 1 second between captures
        else:
            time.sleep(0.1)

def toggle_analysis():
    """
    Toggle the analysis_running flag on or off when Shift+R is pressed.
    """
    global analysis_running
    analysis_running = not analysis_running
    if analysis_running:
        print("Analysis started.")
    else:
        print("Analysis stopped.")

# Bind Shift+R as a hotkey to toggle analysis
keyboard.add_hotkey('shift+r', toggle_analysis)

# Start the analysis loop in a separate daemon thread
analysis_thread = threading.Thread(target=analysis_loop, daemon=True)
analysis_thread.start()

# Start the Tkinter mainloop (GUI)
root.mainloop()
