# detectors.py
import cv2
import numpy as np
import pytesseract
from scipy.spatial import distance

# Global dictionary to store previously detected objects for tracking
previous_objects = {
    'stations': [],
    'trains': [],
    'passengers': []
}

def get_absolute_region(relative_region, win_width, win_height):
    """
    Converts a region defined in percentages (x, y, width, height)
    into absolute pixel coordinates.
    """
    x_percent, y_percent, w_percent, h_percent = relative_region
    x = int(x_percent * win_width)
    y = int(y_percent * win_height)
    w = int(w_percent * win_width)
    h = int(h_percent * win_height)
    return (x, y, w, h)

def detect_score(image, win_width, win_height, region=None):
    """
    Detects the score displayed in the top-right corner using OCR.
    Default region: (0.80, 0.00, 0.18, 0.10)
    Returns the score as an integer.
    """
    if region is None:
        region = (0.80, 0.00, 0.18, 0.10)
    x, y, w, h = get_absolute_region(region, win_width, win_height)
    roi = image[y:y+h, x:x+w]
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
    config = "--psm 7 -c tessedit_char_whitelist=0123456789"
    text = pytesseract.image_to_string(thresh, config=config)
    digits = ''.join(filter(str.isdigit, text))
    try:
        return int(digits)
    except ValueError:
        return 0

def detect_available_trains(image, win_width, win_height, region=None):
    """
    Detects the number of available trains (via OCR) in the bottom-left area.
    Default region: (0.10, 0.85, 0.20, 0.10)
    """
    if region is None:
        region = (0.10, 0.85, 0.20, 0.10)
    x, y, w, h = get_absolute_region(region, win_width, win_height)
    roi = image[y:y+h, x:x+w]
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
    config = "--psm 7 -c tessedit_char_whitelist=0123456789"
    text = pytesseract.image_to_string(thresh, config=config)
    digits = ''.join(filter(str.isdigit, text))
    try:
        return int(digits)
    except ValueError:
        return 0

def detect_available_tunnels(image, win_width, win_height, region=None):
    """
    Detects the number of available tunnels (via OCR) in the bottom-right area.
    Default region: (0.70, 0.85, 0.20, 0.10)
    """
    if region is None:
        region = (0.70, 0.85, 0.20, 0.10)
    x, y, w, h = get_absolute_region(region, win_width, win_height)
    roi = image[y:y+h, x:x+w]
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
    config = "--psm 7 -c tessedit_char_whitelist=0123456789"
    text = pytesseract.image_to_string(thresh, config=config)
    digits = ''.join(filter(str.isdigit, text))
    try:
        return int(digits)
    except ValueError:
        return 0

def detect_available_lines(image, win_width, win_height, region=None):
    """
    Detects the metro lines indicator.
    Improved to differentiate between available, locked, and placed lines.
    """
    if region is None:
        region = (0.35, 0.85, 0.30, 0.10)
    x, y, w, h = get_absolute_region(region, win_width, win_height)
    roi = image[y:y+h, x:x+w]

    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    gray = cv2.medianBlur(gray, 5)

    circles = cv2.HoughCircles(gray, cv2.HOUGH_GRADIENT, 1.2, 20,
                               param1=50, param2=30,
                               minRadius=int(0.03 * w), maxRadius=int(0.15 * w))

    available = 0
    locked = 0
    placed = 0

    if circles is not None:
        circles = np.uint16(np.around(circles))
        for c in circles[0]:
            cx, cy, radius = c[0], c[1], c[2]
            # Use a small region around the circle to get the average HSV color
            color_roi = hsv[max(0, cy - 2):min(h, cy + 2), max(0, cx - 2):min(w, cx + 2)]
            if color_roi.size > 0:
                avg_color = np.mean(color_roi, axis=(0, 1))
                # Low saturation indicates a locked (grey) line
                if avg_color[1] < 50:
                    locked += 1
                else:
                    if radius >= int(0.12 * w):
                        placed += 1
                    else:
                        available += 1

    return {"available": available, "locked": locked, "placed": placed}

# -----------------------------------------------------------
# Object Tracking Functions
# -----------------------------------------------------------
def track_objects(new_objects, object_type):
    """
    Tracks objects between frames by associating new objects with previous ones.
    """
    global previous_objects

    if not previous_objects[object_type]:
        previous_objects[object_type] = new_objects
        return new_objects

    tracked_objects = []
    used_indices = set()

    for prev_obj in previous_objects[object_type]:
        # Compute distances between the previous object and each new object
        distances = [distance.euclidean(
            (prev_obj['x'], prev_obj['y']),
            (new_obj['x'], new_obj['y'])
        ) for new_obj in new_objects]

        if not distances:
            continue

        min_idx = np.argmin(distances)
        min_dist = distances[min_idx]

        # If the distance is reasonable and this new object is not yet associated
        if min_dist < 30 and min_idx not in used_indices:
            tracked_obj = new_objects[min_idx].copy()
            tracked_obj['id'] = prev_obj['id']
            tracked_obj['age'] = prev_obj['age'] + 1
            tracked_objects.append(tracked_obj)
            used_indices.add(min_idx)
        else:
            # The object has disappeared
            if prev_obj['age'] > 2:  # Ignore objects that just appeared and disappeared quickly
                prev_obj['missing'] = True
                tracked_objects.append(prev_obj)

    # Add new objects that were not associated
    for i, new_obj in enumerate(new_objects):
        if i not in used_indices:
            new_obj['id'] = len(previous_objects[object_type]) + i
            new_obj['age'] = 1
            tracked_objects.append(new_obj)

    previous_objects[object_type] = [obj for obj in tracked_objects if not obj.get('missing', False)]
    return tracked_objects

# -----------------------------------------------------------
# Station Classification and Passenger Counting
# -----------------------------------------------------------
def classify_station_type(station_image):
    """
    Classifies the station type (circle, triangle, square) using more robust
    shape features.
    """
    if len(station_image.shape) > 2:
        gray = cv2.cvtColor(station_image, cv2.COLOR_BGR2GRAY)
    else:
        gray = station_image

    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    _, thresh = cv2.threshold(blurred, 120, 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if not contours:
        return "unknown"

    cnt = max(contours, key=cv2.contourArea)
    area = cv2.contourArea(cnt)
    perimeter = cv2.arcLength(cnt, True)
    circularity = (4 * np.pi * area) / (perimeter * perimeter) if perimeter > 0 else 0
    epsilon = 0.04 * perimeter
    approx = cv2.approxPolyDP(cnt, epsilon, True)
    vertices = len(approx)
    x, y, w, h = cv2.boundingRect(cnt)
    aspect_ratio = float(w) / h if h > 0 else 0
    hull = cv2.convexHull(cnt)
    hull_area = cv2.contourArea(hull)
    solidity = float(area) / hull_area if hull_area > 0 else 0

    if 0.85 <= circularity <= 1.15:
        return "circle"
    elif 0.4 <= circularity <= 0.7 and vertices == 3:
        return "triangle"
    elif 0.7 <= circularity <= 0.9 and vertices == 4:
        return "square"
    elif vertices > 6 and circularity > 0.8:
        return "circle"  # Noisy circle contour
    else:
        # Fallback decision based on the number of vertices
        if vertices == 3:
            return "triangle"
        elif vertices == 4:
            return "square"
        elif vertices <= 6:
            return "circle"
        else:
            return "unknown"

def count_passengers_at_station(image, x, y, w, h):
    """
    Dummy function to count the number of passengers at a station.
    A real implementation might use OCR or other methods.
    """
    return 0

# -----------------------------------------------------------
# Modified detect_stations with Object Tracking
# -----------------------------------------------------------
def detect_stations(image, win_width, win_height, region=None):
    """
    Detects stations on the map and applies tracking between frames.
    """
    if region is None:
        region = (0.00, 0.00, 1.00, 0.80)
    x, y, w, h = get_absolute_region(region, win_width, win_height)
    roi = image[y:y+h, x:x+w]
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 100, 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    station_bboxes = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < 50 or area > 5000:
            continue
        bx, by, bw, bh = cv2.boundingRect(cnt)
        if bw < 20 or bh < 20:
            continue
        station_bboxes.append((bx, by, bw, bh))

    stations = []
    for i, (bx, by, bw, bh) in enumerate(station_bboxes):
        station_roi = roi[by:by+bh, bx:bx+bw]
        station_type = classify_station_type(station_roi)
        passengers = count_passengers_at_station(image, bx, by, bw, bh)
        stations.append({
            'x': bx + bw // 2,
            'y': by + bh // 2,
            'width': bw,
            'height': bh,
            'type': station_type,
            'passengers': passengers
        })

    tracked_stations = track_objects(stations, 'stations')
    return tracked_stations

# -----------------------------------------------------------
# Other detection functions (unchanged from previous implementation)
# -----------------------------------------------------------
def detect_placed_lines(image, win_width, win_height, region=None):
    """
    Improved detection of placed lines with river handling and line consolidation.
    """
    if region is None:
        region = (0.00, 0.00, 1.00, 0.80)
    x, y, w, h = get_absolute_region(region, win_width, win_height)
    roi = image[y:y+h, x:x+w]

    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    min_line_width = int(0.005 * w)
    max_line_width = int(0.015 * w)
    river_width = int(0.03 * w)

    lines_by_color = {}

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                   cv2.THRESH_BINARY_INV, 11, 2)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    for cnt in contours:
        rect = cv2.minAreaRect(cnt)
        width_rect = min(rect[1])
        if width_rect > river_width:
            continue
        if min_line_width <= width_rect <= max_line_width:
            mask = np.zeros(roi.shape[:2], dtype=np.uint8)
            cv2.drawContours(mask, [cnt], -1, 255, -1)
            color = cv2.mean(roi, mask=mask)[:3]
            color_key = tuple(map(lambda x: round(x / 20) * 20, color))
            if color_key not in lines_by_color:
                lines_by_color[color_key] = []
            box = cv2.boxPoints(rect)
            box = np.array(box).astype(int)
            start = tuple(box[0])
            end = tuple(box[2])
            lines_by_color[color_key].append({
                "start": start,
                "end": end,
                "color": color
            })

    consolidated_lines = []
    for color, lines in lines_by_color.items():
        if lines:
            consolidated_lines.append({
                "color": color,
                "segments": lines
            })

    return consolidated_lines

def detect_trains(image, win_width, win_height, region=None):
    """
    Detects trains on the map.
    Trains appear as colored rectangles.
    Returns a list of dictionaries with "position", "bbox", "color", and "has_wagon".
    """
    if region is None:
        region = (0.00, 0.00, 1.00, 0.80)
    trains = []
    x, y, w, h = get_absolute_region(region, win_width, win_height)
    roi = image[y:y+h, x:x+w]
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

    min_train_area = 100
    max_train_area = 2000
    min_aspect_ratio = 1.5
    max_aspect_ratio = 3.0

    color_ranges = [
        (np.array([20, 100, 100]), np.array([35, 255, 255])),
        (np.array([0, 100, 100]), np.array([10, 255, 255])),
        (np.array([100, 100, 100]), np.array([130, 255, 255])),
        (np.array([10, 100, 100]), np.array([20, 255, 255]))
    ]

    combined_mask = np.zeros(hsv.shape[:2], dtype=np.uint8)
    for lower, upper in color_ranges:
        mask = cv2.inRange(hsv, lower, upper)
        combined_mask = cv2.bitwise_or(combined_mask, mask)

    contours, _ = cv2.findContours(combined_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if min_train_area <= area <= max_train_area:
            bx, by, bw, bh = cv2.boundingRect(cnt)
            aspect_ratio = bw / float(bh)
            if min_aspect_ratio <= aspect_ratio <= max_aspect_ratio:
                mask = np.zeros(roi.shape[:2], dtype=np.uint8)
                cv2.drawContours(mask, [cnt], -1, 255, -1)
                avg_color = cv2.mean(roi, mask=mask)[:3]
                has_wagon = aspect_ratio > 2.2
                trains.append({
                    "position": (bx + bw // 2, by + bh // 2),
                    "bbox": (bx, by, bw, bh),
                    "color": tuple(map(int, avg_color)),
                    "has_wagon": has_wagon
                })

    return trains

def detect_available_wagons(image, win_width, win_height, region=None):
    """
    Detects the number of available wagons near the train indicator using OCR.
    Default region: (0.10, 0.75, 0.20, 0.10)
    """
    if region is None:
        region = (0.10, 0.75, 0.20, 0.10)
    x, y, w, h = get_absolute_region(region, win_width, win_height)
    roi = image[y:y+h, x:x+w]
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
    config = "--psm 7 -c tessedit_char_whitelist=0123456789"
    text = pytesseract.image_to_string(thresh, config=config)
    digits = ''.join(filter(str.isdigit, text))
    try:
        return int(digits)
    except ValueError:
        return 0

def detect_station_demands(image, win_width, win_height, stations, region=None):
    """
    For each detected station, examines a small region to the upper-right to detect
    passenger demand icons (small shapes similar to station shapes).
    Returns a list of dictionaries with "station_id" and "demands".
    """
    demands = []
    for idx, station in enumerate(stations):
        bx, by, bw, bh = station.get("bbox", (0, 0, 0, 0))
        dx = int(0.1 * bw)
        dy = int(0.1 * bh)
        region_x = bx + bw - dx
        region_y = max(by - dy, 0)
        region_w = dx * 2
        region_h = dy * 2
        roi = image[region_y:region_y+region_h, region_x:region_x+region_w]
        if roi.size == 0:
            continue
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 100, 255, cv2.THRESH_BINARY_INV)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        station_demands = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < 5 or area > 100:
                continue
            peri = cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, 0.04 * peri, True)
            shape = "unidentified"
            if len(approx) >= 8:
                shape = "circle"
            elif len(approx) == 4:
                shape = "square"
            elif len(approx) == 3:
                shape = "triangle"
            elif len(approx) == 5:
                shape = "bell"
            elif len(approx) == 6:
                shape = "cross"
            station_demands.append(shape)
        demands.append({
            "station_id": idx,
            "demands": station_demands
        })
    return demands

def analyze_game_image(image, win_width, win_height, config_regions=None):
    """
    Analyzes the complete game screenshot and returns a dictionary containing:
      - score
      - available_trains
      - available_tunnels
      - available_lines (with "available" and "locked" counts)
      - stations (list of detected stations with tracking)
      - placed_lines (list of detected line segments)
      - trains (list of detected trains with wagon flag)
      - available_wagons (number)
      - station_demands (list of passenger demands per station)
    """
    if config_regions is None:
        config_regions = {
            "score_region": (0.80, 0.00, 0.18, 0.10),
            "train_region": (0.10, 0.85, 0.20, 0.10),
            "tunnel_region": (0.70, 0.85, 0.20, 0.10),
            "lines_region": (0.35, 0.85, 0.30, 0.10),
            "station_map_region": (0.00, 0.00, 1.00, 0.80),
            "wagon_region": (0.10, 0.75, 0.20, 0.10)
        }
    analysis = {}
    analysis['score'] = detect_score(image, win_width, win_height, config_regions.get("score_region"))
    analysis['available_trains'] = detect_available_trains(image, win_width, win_height, config_regions.get("train_region"))
    analysis['available_tunnels'] = detect_available_tunnels(image, win_width, win_height, config_regions.get("tunnel_region"))
    analysis['available_lines'] = detect_available_lines(image, win_width, win_height, config_regions.get("lines_region"))
    analysis['stations'] = detect_stations(image, win_width, win_height, config_regions.get("station_map_region"))
    analysis['placed_lines'] = detect_placed_lines(image, win_width, win_height, config_regions.get("station_map_region"))
    analysis['trains'] = detect_trains(image, win_width, win_height, config_regions.get("station_map_region"))
    analysis['available_wagons'] = detect_available_wagons(image, win_width, win_height, config_regions.get("wagon_region"))
    analysis['station_demands'] = detect_station_demands(image, win_width, win_height, analysis['stations'])
    return analysis
