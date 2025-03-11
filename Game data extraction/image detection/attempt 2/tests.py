import unittest
import cv2
import numpy as np
import os
from detectors_py import (
    detect_score, detect_stations, detect_trains,
    classify_station_type, count_passengers_at_station
)


class DetectorsTest(unittest.TestCase):
    def setUp(self):
        # Créer le répertoire pour les images de test si nécessaire
        if not os.path.exists("test_images"):
            os.makedirs("test_images")

        # Générer des images de test synthétiques si elles n'existent pas
        self.test_score_image = self._create_test_score_image()
        self.test_station_circle = self._create_test_station_image("circle")
        self.test_station_triangle = self._create_test_station_image("triangle")
        self.test_station_square = self._create_test_station_image("square")

    def _create_test_score_image(self):
        """Crée une image synthétique avec un score"""
        if os.path.exists("test_images/score.png"):
            return cv2.imread("test_images/score.png")

        # Créer une image noire
        img = np.zeros((100, 200, 3), dtype=np.uint8)
        # Ajouter du texte blanc (score)
        cv2.putText(img, "5432", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        # Sauvegarder et retourner
        cv2.imwrite("test_images/score.png", img)
        return img

    def _create_test_station_image(self, shape_type):
        """Crée une image synthétique avec un type de station spécifique"""
        filename = f"test_images/station_{shape_type}.png"
        if os.path.exists(filename):
            return cv2.imread(filename)

        # Créer une image noire
        img = np.zeros((100, 100, 3), dtype=np.uint8)

        # Dessiner la forme selon le type
        if shape_type == "circle":
            cv2.circle(img, (50, 50), 30, (255, 255, 255), -1)
        elif shape_type == "triangle":
            pts = np.array([[50, 20], [20, 80], [80, 80]], np.int32)
            cv2.fillPoly(img, [pts], (255, 255, 255))
        elif shape_type == "square":
            cv2.rectangle(img, (20, 20), (80, 80), (255, 255, 255), -1)

        # Sauvegarder et retourner
        cv2.imwrite(filename, img)
        return img

    def test_score_detection(self):
        """Teste la détection du score"""
        score = detect_score(self.test_score_image, 800, 600)
        self.assertEqual(score, 5432, "La détection du score devrait retourner 5432")

    def test_station_type_classification(self):
        """Teste la classification des types de stations"""
        circle_type = classify_station_type(self.test_station_circle)
        self.assertEqual(circle_type, "circle", "Devrait détecter un cercle")

        triangle_type = classify_station_type(self.test_station_triangle)
        self.assertEqual(triangle_type, "triangle", "Devrait détecter un triangle")

        square_type = classify_station_type(self.test_station_square)
        self.assertEqual(square_type, "square", "Devrait détecter un carré")

    def test_passengers_counting(self):
        """Teste le comptage des passagers"""
        # Créer une image avec des "passagers" (petits cercles)
        img = np.zeros((200, 200, 3), dtype=np.uint8)

        # Station au centre
        cv2.circle(img, (100, 100), 30, (255, 255, 255), 2)

        # Ajouter 5 "passagers" (petits cercles colorés)
        for i in range(5):
            x = 100 + int(20 * np.cos(i * 2 * np.pi / 5))
            y = 100 + int(20 * np.sin(i * 2 * np.pi / 5))
            cv2.circle(img, (x, y), 5, (0, 0, 255), -1)

        # Compter les passagers
        count = count_passengers_at_station(img, 70, 70, 60, 60)
        self.assertEqual(count, 5, "Devrait compter 5 passagers")


# Exécuter les tests si le fichier est lancé directement
if __name__ == "__main__":
    unittest.main()