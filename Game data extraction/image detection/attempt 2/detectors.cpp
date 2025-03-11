// detectors.cpp
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/numpy.h>

#include <opencv2/opencv.hpp>
#include <tesseract/baseapi.h>
#include <leptonica/allheaders.h>

#include <vector>
#include <string>
#include <map>
#include <tuple>
#include <algorithm>
#include <cctype>

namespace py = pybind11;

// --- Helper: conversion d'un numpy.array vers cv::Mat ---
cv::Mat mat_from_numpy(py::array_t<unsigned char> input) {
    py::buffer_info buf = input.request();
    int rows = buf.shape[0];
    int cols = buf.shape[1];
    int channels = (buf.ndim == 3 ? buf.shape[2] : 1);
    int type = channels == 1 ? CV_8UC1 : CV_8UC(channels);
    cv::Mat mat(rows, cols, type, (unsigned char*)buf.ptr);
    return mat.clone(); // on clone pour posséder nos propres données
}

// --- get_absolute_region ---
// Convertit un rectangle relatif (x%, y%, w%, h%) en rectangle absolu
cv::Rect get_absolute_region(const std::vector<double>& relative_region, int win_width, int win_height) {
    int x = static_cast<int>(relative_region[0] * win_width);
    int y = static_cast<int>(relative_region[1] * win_height);
    int w = static_cast<int>(relative_region[2] * win_width);
    int h = static_cast<int>(relative_region[3] * win_height);
    return cv::Rect(x, y, w, h);
}

// --- Helper OCR ---
// Lit un nombre à partir d'une région d'image (avec Tesseract)
int ocr_read_number(const cv::Mat& roi) {
    cv::Mat gray;
    cv::cvtColor(roi, gray, cv::COLOR_BGR2GRAY);
    cv::Mat thresh;
    cv::threshold(gray, thresh, 150, 255, cv::THRESH_BINARY);
    tesseract::TessBaseAPI tess;
    if (tess.Init(NULL, "eng")) {
        return 0;
    }
    tess.SetPageSegMode(tesseract::PSM_SINGLE_LINE);
    tess.SetVariable("tessedit_char_whitelist", "0123456789");
    tess.SetImage(thresh.data, thresh.cols, thresh.rows, thresh.channels(), thresh.step);
    char* outText = tess.GetUTF8Text();
    std::string text(outText);
    delete[] outText;
    tess.End();
    std::string digits;
    for (char c : text) {
        if (std::isdigit(c))
            digits.push_back(c);
    }
    if (digits.empty())
        return 0;
    try {
        return std::stoi(digits);
    }
    catch (...) {
        return 0;
    }
}

// --- Détection du score ---
int detect_score(const cv::Mat& image, int win_width, int win_height, const std::vector<double>& region = { 0.80, 0.00, 0.18, 0.10 }) {
    cv::Rect abs_region = get_absolute_region(region, win_width, win_height);
    cv::Mat roi = image(abs_region);
    return ocr_read_number(roi);
}

// --- Détection des trains disponibles ---
int detect_available_trains(const cv::Mat& image, int win_width, int win_height, const std::vector<double>& region = { 0.10, 0.85, 0.20, 0.10 }) {
    cv::Rect abs_region = get_absolute_region(region, win_width, win_height);
    cv::Mat roi = image(abs_region);
    return ocr_read_number(roi);
}

// --- Détection des tunnels disponibles ---
int detect_available_tunnels(const cv::Mat& image, int win_width, int win_height, const std::vector<double>& region = { 0.70, 0.85, 0.20, 0.10 }) {
    cv::Rect abs_region = get_absolute_region(region, win_width, win_height);
    cv::Mat roi = image(abs_region);
    return ocr_read_number(roi);
}

// --- Détection des wagons disponibles ---
int detect_available_wagons(const cv::Mat& image, int win_width, int win_height, const std::vector<double>& region = { 0.10, 0.75, 0.20, 0.10 }) {
    cv::Rect abs_region = get_absolute_region(region, win_width, win_height);
    cv::Mat roi = image(abs_region);
    return ocr_read_number(roi);
}

// --- Détection des lignes disponibles ---
// Analyse la région pour détecter les cercles correspondant aux lignes et distingue
// entre disponibles, verrouillées (gris) et placées (grande taille)
py::dict detect_available_lines(const cv::Mat& image, int win_width, int win_height, const std::vector<double>& region = { 0.35, 0.85, 0.30, 0.10 }) {
    cv::Rect abs_region = get_absolute_region(region, win_width, win_height);
    cv::Mat roi = image(abs_region);
    cv::Mat hsv;
    cv::cvtColor(roi, hsv, cv::COLOR_BGR2HSV);
    cv::Mat gray;
    cv::cvtColor(roi, gray, cv::COLOR_BGR2GRAY);
    cv::medianBlur(gray, gray, 5);
    std::vector<cv::Vec3f> circles;
    cv::HoughCircles(gray, circles, cv::HOUGH_GRADIENT, 1.2, 20, 50, 30, int(0.03 * roi.cols), int(0.15 * roi.cols));

    int available = 0, locked = 0, placed = 0;
    for (size_t i = 0; i < circles.size(); i++) {
        cv::Vec3i c = circles[i];
        int cx = c[0], cy = c[1], radius = c[2];
        int x1 = std::max(cx - 2, 0);
        int y1 = std::max(cy - 2, 0);
        int x2 = std::min(cx + 2, roi.cols);
        int y2 = std::min(cy + 2, roi.rows);
        cv::Rect sample_rect(x1, y1, x2 - x1, y2 - y1);
        cv::Mat color_roi = hsv(sample_rect);
        if (color_roi.empty()) continue;
        cv::Scalar avg_color = cv::mean(color_roi);
        if (avg_color[1] < 50)
            locked++;
        else {
            if (radius >= int(0.12 * roi.cols))
                placed++;
            else
                available++;
        }
    }
    py::dict result;
    result["available"] = available;
    result["locked"] = locked;
    result["placed"] = placed;
    return result;
}

// --- Détection des stations ---
// Recherche les contours dans la région indiquée et en déduit une forme approximative.
std::vector<py::dict> detect_stations(const cv::Mat& image, int win_width, int win_height, const std::vector<double>& region = { 0.00, 0.00, 1.00, 0.80 }) {
    std::vector<py::dict> stations;
    cv::Rect abs_region = get_absolute_region(region, win_width, win_height);
    cv::Mat roi = image(abs_region);
    cv::Mat gray;
    cv::cvtColor(roi, gray, cv::COLOR_BGR2GRAY);
    cv::Mat thresh;
    cv::threshold(gray, thresh, 100, 255, cv::THRESH_BINARY_INV);
    std::vector<std::vector<cv::Point>> contours;
    cv::findContours(thresh, contours, cv::RETR_EXTERNAL, cv::CHAIN_APPROX_SIMPLE);

    for (const auto& cnt : contours) {
        double area = cv::contourArea(cnt);
        if (area < 50 || area > 5000)
            continue;
        cv::Rect bbox = cv::boundingRect(cnt);
        if (bbox.width < 20 || bbox.height < 20)
            continue;
        double peri = cv::arcLength(cnt, true);
        std::vector<cv::Point> approx;
        cv::approxPolyDP(cnt, approx, 0.04 * peri, true);

        std::string shape = "unidentified";
        size_t vertices = approx.size();
        if (vertices >= 8)
            shape = "circle";
        else if (vertices == 4) {
            double ratio = bbox.width / (double)bbox.height;
            shape = (ratio > 0.9 && ratio < 1.1) ? "square" : "rectangle";
        }
        else if (vertices == 3)
            shape = "triangle";
        else if (vertices == 5)
            shape = "pentagon";
        else if (vertices == 6)
            shape = "cross";

        py::dict station;
        station["shape"] = shape;
        station["position"] = py::make_tuple(bbox.x + bbox.width / 2, bbox.y + bbox.height / 2);
        station["bbox"] = py::make_tuple(bbox.x, bbox.y, bbox.width, bbox.height);
        stations.push_back(station);
    }
    return stations;
}

// --- Détection des lignes placées ---
// Utilise un seuillage adaptatif et regroupe les segments par couleur.
std::vector<py::dict> detect_placed_lines(const cv::Mat& image, int win_width, int win_height, const std::vector<double>& region = { 0.00, 0.00, 1.00, 0.80 }) {
    std::vector<py::dict> consolidated_lines;
    cv::Rect abs_region = get_absolute_region(region, win_width, win_height);
    cv::Mat roi = image(abs_region);
    cv::Mat hsv;
    cv::cvtColor(roi, hsv, cv::COLOR_BGR2HSV);

    int w = roi.cols;
    int min_line_width = static_cast<int>(0.005 * w);
    int max_line_width = static_cast<int>(0.015 * w);
    int river_width = static_cast<int>(0.03 * w);

    std::map<std::tuple<int, int, int>, std::vector<py::dict>> lines_by_color;

    cv::Mat gray;
    cv::cvtColor(roi, gray, cv::COLOR_BGR2GRAY);
    cv::Mat thresh;
    cv::adaptiveThreshold(gray, thresh, 255, cv::ADAPTIVE_THRESH_GAUSSIAN_C,
        cv::THRESH_BINARY_INV, 11, 2);
    std::vector<std::vector<cv::Point>> contours;
    cv::findContours(thresh, contours, cv::RETR_EXTERNAL, cv::CHAIN_APPROX_SIMPLE);

    for (const auto& cnt : contours) {
        cv::RotatedRect rect = cv::minAreaRect(cnt);
        float width = std::min(rect.size.width, rect.size.height);
        if (width > river_width)
            continue;
        if (width < min_line_width || width > max_line_width)
            continue;

        cv::Mat mask = cv::Mat::zeros(roi.size(), CV_8UC1);
        cv::drawContours(mask, std::vector<std::vector<cv::Point>>{cnt}, -1, 255, -1);
        cv::Scalar color_mean = cv::mean(roi, mask);

        int r = static_cast<int>(std::round(color_mean[2] / 20.0) * 20);
        int g = static_cast<int>(std::round(color_mean[1] / 20.0) * 20);
        int b = static_cast<int>(std::round(color_mean[0] / 20.0) * 20);
        std::tuple<int, int, int> color_key = std::make_tuple(r, g, b);

        cv::Point2f boxPoints[4];
        rect.points(boxPoints);
        cv::Point start = boxPoints[0];
        cv::Point end = boxPoints[2];

        py::dict segment;
        segment["start"] = py::make_tuple(start.x, start.y);
        segment["end"] = py::make_tuple(end.x, end.y);
        segment["color"] = py::make_tuple(b, g, r); // en BGR

        lines_by_color[color_key].push_back(segment);
    }

    for (auto& kv : lines_by_color) {
        auto color_key = kv.first;
        int r, g, b;
        std::tie(r, g, b) = color_key;
        py::dict line_data;
        line_data["color"] = py::make_tuple(b, g, r);
        line_data["segments"] = kv.second;
        consolidated_lines.push_back(line_data);
    }
    return consolidated_lines;
}

// --- Détection des trains ---
// Recherche des rectangles colorés et détecte la présence d'un wagon en fonction du rapport largeur/hauteur.
std::vector<py::dict> detect_trains(const cv::Mat& image, int win_width, int win_height, const std::vector<double>& region = { 0.00, 0.00, 1.00, 0.80 }) {
    std::vector<py::dict> trains;
    cv::Rect abs_region = get_absolute_region(region, win_width, win_height);
    cv::Mat roi = image(abs_region);
    cv::Mat hsv;
    cv::cvtColor(roi, hsv, cv::COLOR_BGR2HSV);

    int min_train_area = 100;
    int max_train_area = 2000;
    double min_aspect_ratio = 1.5;
    double max_aspect_ratio = 3.0;

    std::vector<std::pair<cv::Scalar, cv::Scalar>> color_ranges = {
        {cv::Scalar(20, 100, 100), cv::Scalar(35, 255, 255)},   // Jaune
        {cv::Scalar(0, 100, 100), cv::Scalar(10, 255, 255)},      // Rouge
        {cv::Scalar(100, 100, 100), cv::Scalar(130, 255, 255)},   // Bleu
        {cv::Scalar(10, 100, 100), cv::Scalar(20, 255, 255)}      // Orange
    };

    cv::Mat combined_mask = cv::Mat::zeros(hsv.size(), CV_8UC1);
    for (auto& range : color_ranges) {
        cv::Mat mask;
        cv::inRange(hsv, range.first, range.second, mask);
        cv::bitwise_or(combined_mask, mask, combined_mask);
    }

    std::vector<std::vector<cv::Point>> contours;
    cv::findContours(combined_mask, contours, cv::RETR_EXTERNAL, cv::CHAIN_APPROX_SIMPLE);

    for (const auto& cnt : contours) {
        double area = cv::contourArea(cnt);
        if (area < min_train_area || area > max_train_area)
            continue;
        cv::Rect bbox = cv::boundingRect(cnt);
        double aspect_ratio = bbox.width / (double)bbox.height;
        if (aspect_ratio < min_aspect_ratio || aspect_ratio > max_aspect_ratio)
            continue;

        cv::Mat mask = cv::Mat::zeros(roi.size(), CV_8UC1);
        cv::drawContours(mask, std::vector<std::vector<cv::Point>>{cnt}, -1, 255, -1);
        cv::Scalar avg_color = cv::mean(roi, mask);
        bool has_wagon = aspect_ratio > 2.2;

        py::dict train;
        train["position"] = py::make_tuple(bbox.x + bbox.width / 2, bbox.y + bbox.height / 2);
        train["bbox"] = py::make_tuple(bbox.x, bbox.y, bbox.width, bbox.height);
        train["color"] = py::make_tuple((int)avg_color[0], (int)avg_color[1], (int)avg_color[2]);
        train["has_wagon"] = has_wagon;
        trains.push_back(train);
    }
    return trains;
}

// --- Détection des demandes de stations ---
// Pour chaque station, regarde une petite région autour du bbox pour détecter des icônes de demande
std::vector<py::dict> detect_station_demands(const cv::Mat& image, int win_width, int win_height, const std::vector<py::dict>& stations) {
    std::vector<py::dict> demands;
    for (size_t idx = 0; idx < stations.size(); idx++) {
        py::dict station = stations[idx];
        py::tuple bbox_tuple = station["bbox"].cast<py::tuple>();
        int bx = bbox_tuple[0].cast<int>();
        int by = bbox_tuple[1].cast<int>();
        int bw = bbox_tuple[2].cast<int>();
        int bh = bbox_tuple[3].cast<int>();
        int dx = static_cast<int>(0.1 * bw);
        int dy = static_cast<int>(0.1 * bh);
        int region_x = bx + bw - dx;
        int region_y = std::max(by - dy, 0);
        int region_w = dx * 2;
        int region_h = dy * 2;
        cv::Rect region_rect(region_x, region_y, region_w, region_h);
        if (region_rect.x + region_rect.width > image.cols || region_rect.y + region_rect.height > image.rows)
            continue;
        cv::Mat roi = image(region_rect);
        if (roi.empty())
            continue;
        cv::Mat gray;
        cv::cvtColor(roi, gray, cv::COLOR_BGR2GRAY);
        cv::Mat thresh;
        cv::threshold(gray, thresh, 100, 255, cv::THRESH_BINARY_INV);
        std::vector<std::vector<cv::Point>> contours;
        cv::findContours(thresh, contours, cv::RETR_EXTERNAL, cv::CHAIN_APPROX_SIMPLE);
        std::vector<std::string> station_demands;
        for (const auto& cnt : contours) {
            double area = cv::contourArea(cnt);
            if (area < 5 || area > 100)
                continue;
            double peri = cv::arcLength(cnt, true);
            std::vector<cv::Point> approx;
            cv::approxPolyDP(cnt, approx, 0.04 * peri, true);
            std::string shape = "unidentified";
            size_t vertices = approx.size();
            if (vertices >= 8)
                shape = "circle";
            else if (vertices == 4)
                shape = "square";
            else if (vertices == 3)
                shape = "triangle";
            else if (vertices == 5)
                shape = "bell";
            else if (vertices == 6)
                shape = "cross";
            station_demands.push_back(shape);
        }
        py::dict demand_entry;
        demand_entry["station_id"] = (int)idx;
        demand_entry["demands"] = station_demands;
        demands.push_back(demand_entry);
    }
    return demands;
}

// --- Analyse complète de l'image ---
// Appelle toutes les fonctions de détection et renvoie un dictionnaire complet.
py::dict analyze_game_image(py::array_t<unsigned char> image_array, int win_width, int win_height, py::dict config_regions = py::dict()) {
    cv::Mat image = mat_from_numpy(image_array);

    // Configuration par défaut si non fournie
    if (config_regions.size() == 0) {
        config_regions["score_region"] = py::make_tuple(0.80, 0.00, 0.18, 0.10);
        config_regions["train_region"] = py::make_tuple(0.10, 0.85, 0.20, 0.10);
        config_regions["tunnel_region"] = py::make_tuple(0.70, 0.85, 0.20, 0.10);
        config_regions["lines_region"] = py::make_tuple(0.35, 0.85, 0.30, 0.10);
        config_regions["station_map_region"] = py::make_tuple(0.00, 0.00, 1.00, 0.80);
        config_regions["wagon_region"] = py::make_tuple(0.10, 0.75, 0.20, 0.10);
    }
    auto tuple_to_vector = [](py::tuple t) -> std::vector<double> {
        std::vector<double> vec;
        for (auto item : t)
            vec.push_back(item.cast<double>());
        return vec;
        };

    std::vector<double> score_region = tuple_to_vector(config_regions["score_region"].cast<py::tuple>());
    std::vector<double> train_region = tuple_to_vector(config_regions["train_region"].cast<py::tuple>());
    std::vector<double> tunnel_region = tuple_to_vector(config_regions["tunnel_region"].cast<py::tuple>());
    std::vector<double> lines_region = tuple_to_vector(config_regions["lines_region"].cast<py::tuple>());
    std::vector<double> station_map_region = tuple_to_vector(config_regions["station_map_region"].cast<py::tuple>());
    std::vector<double> wagon_region = tuple_to_vector(config_regions["wagon_region"].cast<py::tuple>());

    py::dict analysis;
    analysis["score"] = detect_score(image, win_width, win_height, score_region);
    analysis["available_trains"] = detect_available_trains(image, win_width, win_height, train_region);
    analysis["available_tunnels"] = detect_available_tunnels(image, win_width, win_height, tunnel_region);
    analysis["available_lines"] = detect_available_lines(image, win_width, win_height, lines_region);
    auto stations = detect_stations(image, win_width, win_height, station_map_region);
    analysis["stations"] = stations;
    analysis["placed_lines"] = detect_placed_lines(image, win_width, win_height, station_map_region);
    analysis["trains"] = detect_trains(image, win_width, win_height, station_map_region);
    analysis["available_wagons"] = detect_available_wagons(image, win_width, win_height, wagon_region);
    analysis["station_demands"] = detect_station_demands(image, win_width, win_height, stations);

    return analysis;
}

// --- Exposition via Pybind11 ---
PYBIND11_MODULE(detectors_cpp, m) {
    m.doc() = "Module de détection pour Mini Metro";
    m.def("get_absolute_region", &get_absolute_region, "Convertit une région relative en région absolue",
        py::arg("relative_region"), py::arg("win_width"), py::arg("win_height"));
    m.def("detect_score", &detect_score, "Détecte le score",
        py::arg("image"), py::arg("win_width"), py::arg("win_height"),
        py::arg("region") = std::vector<double>{ 0.80, 0.00, 0.18, 0.10 });
    m.def("detect_available_trains", &detect_available_trains, "Détecte les trains disponibles",
        py::arg("image"), py::arg("win_width"), py::arg("win_height"),
        py::arg("region") = std::vector<double>{ 0.10, 0.85, 0.20, 0.10 });
    m.def("detect_available_tunnels", &detect_available_tunnels, "Détecte les tunnels disponibles",
        py::arg("image"), py::arg("win_width"), py::arg("win_height"),
        py::arg("region") = std::vector<double>{ 0.70, 0.85, 0.20, 0.10 });
    m.def("detect_available_lines", &detect_available_lines, "Détecte les lignes disponibles",
        py::arg("image"), py::arg("win_width"), py::arg("win_height"),
        py::arg("region") = std::vector<double>{ 0.35, 0.85, 0.30, 0.10 });
    m.def("detect_stations", &detect_stations, "Détecte les stations",
        py::arg("image"), py::arg("win_width"), py::arg("win_height"),
        py::arg("region") = std::vector<double>{ 0.00, 0.00, 1.00, 0.80 });
    m.def("detect_placed_lines", &detect_placed_lines, "Détecte les lignes placées",
        py::arg("image"), py::arg("win_width"), py::arg("win_height"),
        py::arg("region") = std::vector<double>{ 0.00, 0.00, 1.00, 0.80 });
    m.def("detect_trains", &detect_trains, "Détecte les trains",
        py::arg("image"), py::arg("win_width"), py::arg("win_height"),
        py::arg("region") = std::vector<double>{ 0.00, 0.00, 1.00, 0.80 });
    m.def("detect_available_wagons", &detect_available_wagons, "Détecte les wagons disponibles",
        py::arg("image"), py::arg("win_width"), py::arg("win_height"),
        py::arg("region") = std::vector<double>{ 0.10, 0.75, 0.20, 0.10 });
    m.def("detect_station_demands", &detect_station_demands, "Détecte les demandes des stations",
        py::arg("image"), py::arg("win_width"), py::arg("win_height"), py::arg("stations"));
    m.def("analyze_game_image", &analyze_game_image, "Analyse complète de l'image de jeu",
        py::arg("image"), py::arg("win_width"), py::arg("win_height"),
        py::arg("config_regions") = py::dict());
}
