import pygetwindow as gw
import pyautogui
import cv2
import numpy as np
import pytesseract
import time
import keyboard  # Pour la gestion des événements clavier

# Chemin vers l'exécutable Tesseract
# pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

def find_minimetro_window():
    """
    Tente de récupérer la fenêtre dont le titre contient 'Mini Metro'.
    Retourne l'objet fenêtre ou lève une exception si non trouvé.
    """
    all_windows = gw.getWindowsWithTitle("Mini Metro")
    if not all_windows:
        raise Exception("Impossible de trouver une fenêtre 'Mini Metro'.")
    # On suppose que la première fenêtre correspond au jeu
    return all_windows[0]

def capture_game_screenshot(window):
    """
    Capture la zone correspondant à la fenêtre du jeu et renvoie l'image en format BGR.
    """
    left, top, width, height = window.left, window.top, window.width, window.height
    screenshot = pyautogui.screenshot(region=(left, top, width, height))
    img_bgr = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
    return img_bgr

def detect_river(img_bgr):
    """
    Détecte la présence de la rivière dans l'image.
    La rivière est identifiée comme une large zone bleue.
    Retourne un masque binaire (pixels blancs = zones bleues).
    """
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    lower_blue = np.array([90, 50, 50])
    upper_blue = np.array([130, 255, 255])
    mask_blue = cv2.inRange(hsv, lower_blue, upper_blue)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask_blue = cv2.morphologyEx(mask_blue, cv2.MORPH_CLOSE, kernel)
    return mask_blue

def detect_stations_and_demands(img_bgr):
    """
    Détecte les stations et, potentiellement, leurs demandes (icônes au-dessus).
    La détection se base sur un seuillage en niveaux de gris et l'analyse des contours.
    Retourne une liste de dictionnaires contenant :
        - 'shape' : type de station (triangle, carre, cercle ou inconnu)
        - 'position' : position approximative (centre)
        - 'demand' : information sur la demande (à implémenter)
    """
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    stations_info = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < 50:  # Filtrer le bruit
            continue

        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
        x, y, w, h = cv2.boundingRect(approx)

        # Identification de la forme
        if len(approx) == 3:
            shape_type = "triangle"
        elif len(approx) == 4:
            shape_type = "carre"
        elif len(approx) >= 5:
            shape_type = "cercle"
        else:
            shape_type = "inconnu"

        stations_info.append({
            "shape": shape_type,
            "position": (x + w // 2, y + h // 2),
            "demand": "à_implementer"  # TODO: Implémenter la détection de la demande
        })

    return stations_info

def detect_lines(img_bgr):
    """
    Détecte les lignes déjà posées en recherchant différentes plages de couleurs.
    Pour chaque couleur, on identifie la présence de contours et on associe
    les segments aux stations (cette partie est à affiner).
    Retourne un dictionnaire { couleur: "stations_relies_à_implementer", ... }.
    """
    lines_info = {}
    color_ranges = {
        "rouge": ([0, 50, 50], [10, 255, 255]),
        # Pour le rouge, il peut être nécessaire de gérer la plage haute (170-180)
        "jaune": ([25, 50, 50], [35, 255, 255]),
        "vert": ([40, 50, 50], [70, 255, 255]),
        "bleu_ligne": ([90, 50, 50], [130, 255, 255])  # À distinguer de la rivière
    }

    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    for color_name, (lower, upper) in color_ranges.items():
        lower_np = np.array(lower, dtype=np.uint8)
        upper_np = np.array(upper, dtype=np.uint8)
        mask = cv2.inRange(hsv, lower_np, upper_np)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            # TODO: Associer les segments détectés aux stations
            lines_info[color_name] = "stations_relies_à_implementer"

    return lines_info

def detect_score(img_bgr):
    """
    Détecte le score affiché dans le jeu en utilisant l'OCR sur une zone définie.
    Retourne le score sous forme d'entier ou None si non détecté.
    """
    # Zone supposée du score (à ajuster)
    x, y, w, h = 50, 50, 100, 50
    roi = img_bgr[y:y + h, x:x + w]
    gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    config = "--psm 7"  # Lecture d'une seule ligne
    text = pytesseract.image_to_string(gray_roi, config=config)
    score_str = "".join([c for c in text if c.isdigit()])
    return int(score_str) if score_str else None

def detect_resources(img_bgr):
    """
    Détecte les ressources affichées en bas de l’écran (locomotives, lignes posées, etc.).
    La méthode utilisée ici repose sur l'OCR dans une zone fixe.
    Retourne un dictionnaire avec les informations (à affiner selon l'UI).
    """
    height, width, _ = img_bgr.shape
    bottom_bar_height = 50  # Hauteur supposée de la barre du bas
    x, y = 0, height - bottom_bar_height
    w, h = width, bottom_bar_height

    roi = img_bgr[y:y + h, x:x + w]
    gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    text = pytesseract.image_to_string(gray_roi)

    # Exemple de parsing (à adapter)
    numbers = [int(s) for s in text.split() if s.isdigit()]

    resources = {
        "locomotives": "à_déterminer",
        "lignes_posees": "à_déterminer",
        "lignes_dispo": "à_déterminer",
        "lignes_verrou": "à_déterminer",
        "tunnels": "à_déterminer"
    }

    return resources

def main():
    print("🔵 En attente de Ctrl + R pour démarrer...")
    keyboard.wait("ctrl+r")
    print("🟢 Détection en cours... Appuyez sur Échap (Esc) pour arrêter.")

    try:
        window = find_minimetro_window()
        while not keyboard.is_pressed("esc"):
            img_bgr = capture_game_screenshot(window)

            # Analyse de la rivière
            river_mask = detect_river(img_bgr)

            # Analyse des stations et des demandes
            stations_info = detect_stations_and_demands(img_bgr)

            # Analyse des lignes posées
            lines_info = detect_lines(img_bgr)

            # Détection du score
            score = detect_score(img_bgr)

            # Détection des ressources
            resources = detect_resources(img_bgr)

            print("------------------------------------------------")
            print(f"Rivière détectée : {np.sum(river_mask > 0)} pixels bleus")
            print("Stations :", stations_info)
            print("Lignes :", lines_info)
            print("Score :", score)
            print("Ressources :", resources)
            print("------------------------------------------------\n")

            time.sleep(1)  # Pause entre chaque analyse

    except Exception as e:
        print(f"❌ Erreur : {e}")

    print("🔴 Script arrêté.")

if __name__ == "__main__":
    main()
