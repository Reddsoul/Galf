# **Golf Handicap Tracker ⛳**

A clean, **privacy-first** desktop golf application for tracking rounds, managing courses, calculating a **fully WHS-compliant handicap index**, and using a **digital Greenbook / yardage book**.

Built in Python.

No accounts. No cloud. **Your data stays on your machine.**

---

## **Why This App Exists**

Most golf apps are bloated, cloud-dependent, and opaque about how handicaps and distances are calculated.

**Golf Handicap Tracker** is intentionally different:

* Transparent **USGA / WHS logic**
* Fully **offline-capable** once data is stored
* Local JSON storage you can inspect and control
* **Focused workflows for ****pre-round planning** and **post-round review**
* Designed for everyday golfers who want to improve, not chase gimmicks

---

## **Core Features**

### **🏌️ Round & Score Tracking**

* Log **9-hole or 18-hole** rounds
* Front 9, Back 9, or Full 18 supported
* **Serious vs Casual** rounds (controls handicap inclusion)
* Editable round dates
* Optional round notes for post-game debrief
* Optional **detailed hole logging** (clubs used, strokes to green, putts)

---

### **📊 Handicap & Statistics**

* Full **USGA / WHS 2024** handicap calculation
* Automatic 9-hole score combination
* Correct differential selection logic
* WHS soft & hard cap handling
* Statistics dashboard:
  * Score differentials
  * Averages and trends
  * Scoring insights by hole and par

---

### **⛳ Course Management**

* Create and edit courses locally
* Define per-course:
  * Hole-by-hole pars
  * Multiple tee boxes
  * Tee color, rating, and slope
  * **Yardages per hole and tee**
* Courses are reusable across all rounds

---

### **📍 Greenbook / Digital Yardage Book**

An **interactive, map-based Greenbook** inspired by tools like 18Birdies — built entirely for desktop and offline use.

**Capabilities**

* Satellite map view of each hole
* Place markers for:
  * Tee
  * Green front / back
  * Targets / layups
  * Hazards
* Draw polygons for:
  * Fairways
  * Greens
  * Water
  * Bunkers
* Automatic distance calculations:
  * Tee → green (front / back / center)
  * Tee → hazards
  * Tee → targets and remaining yardage
* Distance rings based on club distances
* Aim lines and visual references
* Saved **per hole**, stored locally, reusable every round

Once markers are placed:

* All distances calculate **offline**
* No external services required
* Course yardages remain authoritative from the scorecard

---

### **📖 Rulebook System**

* Import official **USGA & R&A Rules of Golf** PDF
* App extracts and builds a **local searchable rulebook**
* Fast keyword search
* Bookmark frequently referenced rules
* Add personal notes
* Rulebook cache auto-refreshes when new editions are imported

---

### **🧾 Scorecard Export**

* Export rounds as **PNG or PDF**
* Supports 9 or 18 holes
* Includes:
  * Hole scores
  * Totals
  * Course & tee info
  * Round notes

---

## **Installation**

### **Requirements**

* Python **3.8+**
* tkinter (included with most Python installs)
* tkcalendar
* tkintermapview
* geopy
* reportlab
* Pillow

---

## **Usage Overview**

### **Add a Course**

1. Open **Add Course**
2. Enter course name
3. Define tee boxes (color, rating, slope)
4. Enter par and yardages per hole
5. Save — the course is now reusable everywhere

---

### **Log a Round**

1. Open **Log Round**
2. Select club, course, and tee
3. Choose holes played (Front 9, Back 9, or 18)
4. (Optional) Edit round date
5. Mark Solo or Scramble
6. Mark if the round is **Serious**
7. Enter scores or log detailed hole data
8. Save

---

### **Use the Greenbook**

1. Click **📍 Greenbook** from the main menu
2. Select a course and hole
3. Place markers and draw features on the map
4. View live yardages and distance rings
5. Save — data is stored locally per hole

---

### **Use the Rulebook**

1. **Open ****Rulebook**
2. Import your USGA / R&A Rules PDF
3. Search rules by keyword
4. Bookmark important rules
5. Navigate via table of contents
6. Add personal notes
7. Update when new editions are released

---

## **Project Structure**

```
golf-handicap-tracker/
├── Frontend.py                 # tkinter UI and workflows
├── Backend.py                  # Data models, WHS logic, storage
├── greenbook_ui.py             # Greenbook map interface
├── greenbook_data.py           # Greenbook data models & persistence
├── greenbook_geo.py            # Geodesic distance calculations
├── greenbook_integration.py    # Frontend integration layer
├── README.md
└── data/
    ├── courses.json
    ├── rounds.json
    ├── clubs.json
    ├── rulebook_cache.json
    ├── stats_cache.json
    ├── user_prefs.json
    └── rulebook.pdf
```

---

## **Developer Notes**

* Clean **Frontend / Backend separation**
* All data stored as **human-readable JSON**
* No external APIs required
* Greenbook distances calculated using **Haversine geodesic math**
* PDF generation via **ReportLab**
* Rulebook ingestion pipeline:
  * Text extraction → normalization → indexing
* Codebase is intentionally small, readable, and extensible

---

## **Roadmap**

### **Planned**

* Green slope arrows
* Greenbook PDF export
* Course strategy page
* Shot-planning overlays

### **Possible**

* Elevation integration
* Wind adjustment calculator
* Shot history visualization
* Offline tile caching

---

## **License**

MIT License — free for personal and open-source use.

---

## **Contributing**

Pull requests are welcome, especially for:

* UI/UX improvements
* Advanced statistics
* Greenbook enhancements
* Export and reporting features
* Rulebook utilities
