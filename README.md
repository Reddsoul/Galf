# **Golf Handicap Tracker ⛳**

A modern, privacy-focused Python desktop application for tracking golf rounds, managing courses, and calculating an official-style **USGA/WHS Handicap Index** — fully offline and with no data sharing.

## **Features**

### **Core Tracking**

* **Score Tracking** – Log rounds with hole-by-hole scores for 9 or 18 holes
* **Statistics** – View score differentials, trends, and round summaries
* **Round Types** – Solo or scramble, with optional “serious” flag for handicap inclusion
* **Notes** – Attach notes to rounds for post-game review

### **Handicap Engine**

* **Full USGA/WHS 2024-Compliant Handicap Calculation**
* Automatically converts 9-hole rounds to 18-hole equivalents
* Selects the appropriate number of differentials based on rounds played
* Applies WHS adjustments (-2, -1, or none)

### **Course Management**

* Create and store:
  * Course info
  * Per-hole par
  * Tee boxes (color, rating, slope)
  * Full yardage maps per tee

### **Rulebook System**

* **Embedded PGA/USGA Rulebook**
* **Fast keyword search**
* **Bookmarks & Notes**
* Auto-updating rule data

### **Export Tools**

* **PDF Scorecard Export** (ReportLab)
  Clean, professional scorecards generated automatically.

---

## **Installation**

### **Requirements**

* Python 3.8+
* tkinter (usually included)
* tkcalendar
* reportlab
* Pillow

### **Install Dependencies**

```
pip install tkinter tkcalendar reportlab pillow
```

---

## **Usage**

### **Adding a Course**

1. Click **Add New Course**
2. Enter club & course names
3. Select **9 or 18 holes**
4. Set par for each hole
5. Add tee boxes (color, rating, slope)
6. Add **yardages per hole per tee**

---

### **Logging a Round**

1. Click **Log Round**
2. Select course and tee box
3. Choose holes: **Full 18**, **Front 9**, or **Back 9**
4. Select round type and whether it is *serious*
5. Enter hole-by-hole scores
6. Edit the date (if needed)
7. Save and optionally export the round

---

### **Viewing the Rulebook**

1. Open the **Rulebook** tab
2. Use:
   * Global **Search**
   * **Bookmarks** for frequently-used rules
   * Personal **Notes** per rule
3. The rulebook updates automatically when newer revisions are available.

---

## **Handicap Calculation (WHS 2024)**

The app implements full WHS logic, including 9-hole adjustments and differential selection.

| **Rounds** | **Differentials Used** | **Adjustment** |
| ---------------- | ---------------------------- | -------------------- |
| 3                | Lowest 1                     | -2.0                 |
| 4                | Lowest 1                     | -1.0                 |
| 5                | Lowest 1                     | 0                    |
| 6                | Average of lowest 2          | -1.0                 |
| 7–8             | Average of lowest 2          | 0                    |
| 9–11            | Average of lowest 3          | 0                    |
| 12–14           | Average of lowest 4          | 0                    |
| 15–16           | Average of lowest 5          | 0                    |
| 17–18           | Average of lowest 6          | 0                    |
| 19               | Average of lowest 7          | 0                    |
| 20+              | Average of lowest 8          | 0                    |

Final Index = (average of selected differentials) × **0.96**

---

## **File Structure**

```
golf-handicap-tracker/
├── Frontend.py        # GUI application
├── Backend.py         # Data logic, JSON management, rulebook updater
├── README.md
└── data/
    ├── courses.json
    ├── rounds.json
    ├── clubs.json
    ├── rulebook.json      # auto-updated
    └── exports/           # PDF scorecards
```

---

## **Data Storage**

All data is stored locally in JSON:

* **courses.json** — Courses, par values, tee boxes, yardages
* **rounds.json** — Logged rounds and notes
* **clubs.json** — Club distance mapping
* **rulebook.json** — Local copy of the PGA/USGA rules

Your data never leaves your device.

---

## **Contributing**

Pull requests are welcome for:

* UI/UX improvements
* Additional export formats
* Enhanced analytics or graphs
* New rulebook tools (offline caching, highlights, etc.)

---

## **License**

MIT License — Free for personal and open-source use.

---

## **Acknowledgments**

* **USGA** — Handicap rules and WHS documentation
* **PGA / R&A** — Official Rules of Golf
* Inspiration from aviation tools like **FAR/AIM** for search & bookmark design
