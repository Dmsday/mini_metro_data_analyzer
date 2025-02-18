# detectors.py
import cv2
import numpy as np
import pytesseract

# Each detection function now accepts an optional region parameter.
# If no region is given, the default relative region is used.

def get_absolute_region(relative_region, win_width, win_height):
    """
    Converts a region defined as (x%, y%, width%, height%) into absolute pixel coordinates.
    """
    x_percent, y_percent, w_percent, h_percent = relative_region
    x = int(x_percent * win_width)
    y = int(y_percent * win_height)
    w = int(w_percent * win_width)
    h = int(h_percent * win_height)
    return (x, y, w, h)

def detect_score(image, win_width, win_height, region=None):
    """
    Detects the score from the top-right corner using OCR.
    Default relative region: (0.80, 0.00, 0.18, 0.10)
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
    Detects available trains from the bottom-left area using OCR.
    Default relative region: (0.10, 0.85, 0.20, 0.10)
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
    Detects available tunnels from the bottom-right area using OCR.
    Default relative region: (0.70, 0.85, 0.20, 0.10)
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
    Detects the available metro lines indicator.
    Improved to better distinguish between available, locked, and placed lines.
    """
    if region is None:
        region = (0.35, 0.85, 0.30, 0.10)
    x, y, w, h = get_absolute_region(region, win_width, win_height)
    roi = image[y:y + h, x:x + w]

    # Conversion en HSV pour mieux détecter les couleurs
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    gray = cv2.medianBlur(gray, 5)

    # Détection des cercles avec des paramètres ajustés
    circles = cv2.HoughCircles(gray, cv2.HOUGH_GRADIENT, 1.2, 20,
                               param1=50, param2=30,
                               minRadius=int(0.03 * w), maxRadius=int(0.15 * w))

    available = 0
    locked = 0
    placed = 0

    if circles is not None:
        circles = np.uint16(np.around(circles))
        for c in circles[0]:
            x, y, radius = c[0], c[1], c[2]

            # Extraire la couleur du cercle
            color_roi = hsv[max(0, y - 2):min(h, y + 2), max(0, x - 2):min(w, x + 2)]
            if color_roi.size > 0:
                avg_color = np.mean(color_roi, axis=(0, 1))

                # Vérifier si c'est un cercle gris (locked)
                if avg_color[1] < 50:  # Faible saturation = gris
                    locked += 1
                else:
                    # Distinguer entre disponible et placé selon la taille
                    if radius >= int(0.12 * w):
                        placed += 1
                    else:
                        available += 1

    return {"available": available, "locked": locked, "placed": placed}


# Mise à jour de la fonction detect_stations pour inclure les pentagones
def detect_stations(image, win_width, win_height, region=None):
    """
    Detects stations on the map (top 80% of the window).
    Stations may be circle, square, triangle, pentagon, cross, or bell.
    Uses contour detection and polygon approximation.
    """
    if region is None:
        region = (0.00, 0.00, 1.00, 0.80)
    stations = []
    x, y, w, h = get_absolute_region(region, win_width, win_height)
    roi = image[y:y + h, x:x + w]
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 100, 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < 50 or area > 5000:
            continue
        bx, by, bw, bh = cv2.boundingRect(cnt)
        if bw < 20 or bh < 20:
            continue
        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.04 * peri, True)

        # Amélioration de la détection des formes
        shape = "unidentified"
        vertices = len(approx)
        if vertices >= 8:
            shape = "circle"
        elif vertices == 4:
            ratio = bw / float(bh)
            shape = "square" if 0.9 < ratio < 1.1 else "rectangle"
        elif vertices == 3:
            shape = "triangle"
        elif vertices == 5:
            shape = "pentagon"  # Ajout de la détection des pentagones
        elif vertices == 6:
            shape = "cross"

        stations.append({
            "shape": shape,
            "position": (bx + bw // 2, by + bh // 2),
            "bbox": (bx, by, bw, bh)
        })
    return stations

def detect_placed_lines(image, win_width, win_height, region=None):
    """
    Improved line detection with better river handling and line consolidation.
    """
    if region is None:
        region = (0.00, 0.00, 1.00, 0.80)
    x, y, w, h = get_absolute_region(region, win_width, win_height)
    roi = image[y:y + h, x:x + w]

    # Conversion en HSV pour mieux détecter les couleurs
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

    # Paramètres pour la détection des lignes
    min_line_width = int(0.005 * w)  # Minimum width for metro lines
    max_line_width = int(0.015 * w)  # Maximum width for metro lines
    river_width = int(0.03 * w)  # Approximate river width

    # Structure pour stocker les lignes par couleur
    lines_by_color = {}

    # Détection des contours avec un seuil adaptatif
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                   cv2.THRESH_BINARY_INV, 11, 2)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    for cnt in contours:
        rect = cv2.minAreaRect(cnt)
        width = min(rect[1])

        # Ignorer la rivière
        if width > river_width:
            continue

        # Vérifier si c'est une ligne de métro valide
        if min_line_width <= width <= max_line_width:
            # Extraire la couleur moyenne
            mask = np.zeros(roi.shape[:2], dtype=np.uint8)
            cv2.drawContours(mask, [cnt], -1, 255, -1)
            color = cv2.mean(roi, mask=mask)[:3]

            # Arrondir les valeurs de couleur pour le regroupement
            color_key = tuple(map(lambda x: round(x / 20) * 20, color))

            if color_key not in lines_by_color:
                lines_by_color[color_key] = []

            # Stocker les points de début et de fin
            box = cv2.boxPoints(rect)
            # Remplacer np.int0 par np.array(...).astype(int)
            box = np.array(box).astype(int)
            start = tuple(box[0])
            end = tuple(box[2])
            lines_by_color[color_key].append({
                "start": start,
                "end": end,
                "color": color
            })

    # Consolider les lignes par couleur
    consolidated_lines = []
    for color, lines in lines_by_color.items():
        if len(lines) > 0:
            consolidated_lines.append({
                "color": color,
                "segments": lines
            })

    return consolidated_lines

def detect_trains(image, win_width, win_height, region=None):
    """
    Detects trains on the map.
    Trains appear as colored rectangles; if a train has an attached wagon,
    its bounding box is significantly wider.
    Returns a list of dictionaries with "position", "bbox", "color", and "has_wagon".
    Default region: (0.00, 0.00, 1.00, 0.80)
    Improved train detection with better color matching and wagon detection.
    """
    if region is None:
        region = (0.00, 0.00, 1.00, 0.80)
    trains = []
    x, y, w, h = get_absolute_region(region, win_width, win_height)
    roi = image[y:y + h, x:x + w]

    # Conversion en HSV pour une meilleure détection des couleurs
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

    # Paramètres ajustés pour la détection des trains
    min_train_area = 100
    max_train_area = 2000
    min_aspect_ratio = 1.5  # Pour les trains sans wagon
    max_aspect_ratio = 3.0  # Pour les trains avec wagon

    # Création d'un masque combiné pour toutes les couleurs de train possibles
    color_ranges = [
        # Jaune
        (np.array([20, 100, 100]), np.array([35, 255, 255])),
        # Rouge
        (np.array([0, 100, 100]), np.array([10, 255, 255])),
        # Bleu
        (np.array([100, 100, 100]), np.array([130, 255, 255])),
        # Orange
        (np.array([10, 100, 100]), np.array([20, 255, 255]))
    ]

    combined_mask = np.zeros(hsv.shape[:2], dtype=np.uint8)
    for lower, upper in color_ranges:
        mask = cv2.inRange(hsv, lower, upper)
        combined_mask = cv2.bitwise_or(combined_mask, mask)

    # Trouver les contours des trains
    contours, _ = cv2.findContours(combined_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if min_train_area <= area <= max_train_area:
            bx, by, bw, bh = cv2.boundingRect(cnt)
            aspect_ratio = bw / float(bh)

            if min_aspect_ratio <= aspect_ratio <= max_aspect_ratio:
                # Déterminer la couleur du train
                mask = np.zeros(roi.shape[:2], dtype=np.uint8)
                cv2.drawContours(mask, [cnt], -1, 255, -1)
                avg_color = cv2.mean(roi, mask=mask)[:3]

                has_wagon = aspect_ratio > 2.2  # Seuil pour déterminer la présence d'un wagon

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
    Default relative region: (0.10, 0.75, 0.20, 0.10)
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
    For each detected station, examines a small region above-right of its bounding box
    to detect passenger demand icons (tiny shapes similar to station shapes).
    Returns a list of dictionaries with "station_id" and "demands" (list of shapes).
    The region is determined relative to each station's bounding box.
    """
    demands = []
    for idx, station in enumerate(stations):
        bx, by, bw, bh = station["bbox"]
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
    Analyzes the entire game screenshot and returns a dictionary containing:
      - score
      - available_trains
      - available_tunnels
      - available_lines (with "available" and "locked" counts)
      - stations (list of detected stations)
      - placed_lines (list of detected line segments)
      - trains (list of detected trains with wagon flag)
      - available_wagons (number)
      - station_demands (list with demand shapes per station)
    If config_regions is provided, it uses those regions for each detection.
    """
    # Set defaults if config_regions is not provided
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
