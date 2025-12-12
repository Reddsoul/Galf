# **Golf Handicap Tracker ⛳**

A clean, privacy-first application for tracking golf rounds, managing courses, and calculating a fully WHS-compliant handicap — built with Python and designed for everyday golfers.

No accounts. No cloud. Your data stays on your machine.

---

## **Features**

### **Core Functionality**

* **Score Tracking** — Log 9 or 18-hole rounds with simple data entry
* **Automatic Handicap Calculation** — Full USGA/WHS 2024 logic
* **Statistics Dashboard** — View trend lines, differentials, and scoring insights
* **Serious vs. Casual Rounds** — Control what counts toward the index
* **Round Notes** — Add post-game comments or reminders
* **Editable Round Dates** — Fix or adjust round dates anytime

### **Course Management**

* Create courses with:
  * Hole-by-hole par values
  * Tee boxes (color, rating, slope)
  * **Full yardage maps per tee**
* Courses are stored locally for quick lookup and editing

### **Rulebook System**

* Bring your own official USGA rulebook PDF/text
* App extracts the content and stores a local searchable version
* **Fast keyword search**
* **Bookmarks & Notes** per rule
* Auto-updates the rulebook JSON when new editions are provided

### **Scorecard Export**

* Generate clean **PDF scorecards** using ReportLab
* Supports 9 or 18 holes
* Includes totals, course info, tee data, and your notes

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
pip install tkcalendar reportlab pillow
```

---

## **Usage**

### **Add a Course**

1. **Open ****Add Course**
2. Enter course & tee details
3. Add par and **yardages** for each hole
4. Save — the course becomes available for all future rounds

### **Log a Round**

1. **Open ****Log Round**
2. Pick course, tee, and holes played (Front 9, Back 9, or 18)
3. Enter scores
4. Mark it Serious/Casual
5. (Optional) Edit the round date
6. Save or export to PDF

### **Rulebook**

1. Open the **Rulebook** tab
2. Search instantly by keyword
3. Bookmark frequently referenced rules
4. Add personal notes
5. App updates the JSON rulebook when new data is provided

---

## **Handicap Calculation (WHS 2024)**

Implements the full WHS formula:

* Converts 9-hole rounds to 18-hole equivalents
* Uses correct differential selection based on number of rounds
* Applies WHS adjustments (-2, -1, or none)
* **Final Index = ****Average of selected diffs × 0.96**

A golfer-friendly system, internally implemented with developer-clean logic.

---

## **Developer Notes**

* **Built with a ****Backend/Frontend separation**
  * **Backend.py** handles data models, JSON storage, and WHS logic
  * **Frontend.py** handles all tkinter UI components
* Data is stored in **data/** as human-readable JSON
* Rulebook ingestion uses text extraction → normalization → indexing
* PDF generation uses ReportLab tables + custom layout logic
* Codebase is intentionally small, readable, and mod-friendly

---

## **Project Structure**

```
golf-handicap-tracker/
├── Frontend.py
├── Backend.py
├── README.md
└── data/
    ├── courses.json
    ├── rounds.json
    ├── clubs.json
    ├── rulebook_cache.json
    └── rulebook.pdf
```

---

## **License**

MIT License — free for personal and open-source use.

---

## **Contributing**

Pull requests welcome for:

* UI improvements
* Analytics/visualization enhancements
* Additional export formats
* Additional rulebook utilities
