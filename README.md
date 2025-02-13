# mini_metro_data_analyzer

# Mini Metro AI Project

## 🚄 Overview
This project is an attempt to develop an AI capable of playing **Mini Metro**, a minimalist strategy game where players design a metro system to efficiently transport passengers. The primary challenge is the lack of an official API, requiring alternative methods to extract game data.

## 🎯 Goals
- **Extract real-time game data** (stations, lines, trains, resources, score)
- **Analyze optimal metro layouts** and improve network efficiency
- **Develop an AI** that can suggest or automate metro system management
- **Test different input methods**, including image recognition and manual input

## 🛠 Current Approach
Since direct data extraction is not available, two methods were considered:
1. **Image Recognition (Failed)** ❌
   - Used **MSS** and **Tesseract** to detect stations, lines, and score.
   - Poor accuracy due to overlapping elements and false detections.
2. **Manual Data Input (Current Method)** ✅
   - The user manually inputs game state updates using an overlay.
   - Press **Shift+R** to toggle data input mode.
   - Allows AI to track station placements, lines, and resources.

## 🔥 Challenges
- Image recognition failed to provide reliable data.
- Manual input is time-consuming and inefficient for fast-paced gameplay.
- No direct access to game mechanics, requiring creative workarounds.

## 📌 Next Steps
- Explore alternative **computer vision techniques** for better recognition.
- Investigate potential ways to **hook into game memory**.
- Improve the **manual input system** for better usability.
- Implement basic AI logic to **suggest** metro expansions based on available data.

## 🤝 Contributing
Any contributions, suggestions, or feedback are welcome ! Feel free to fork the repo, submit issues, or open a pull request.

## 📜 License
This project is open-source
