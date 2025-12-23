
![Galf Logo](Galf.png)

# ⛳ Galf

**Galf** is a desktop golf companion app focused on ***playing smarter* , not just tracking scores. It combines a** **yardbook** / **greenbook** ,*****scorecard** ,** ***club distances** , and** **stats** into a single, clean, Apple‑HIG‑inspired Tkinter application.

This is not a social app, simulator, or gimmicky range toy. Galf is built for golfers who care about **course management, repeatability, and decision‑making** .

---

## ✨ Core Features

### 🗺️ Yardbook / Course Mapping

* Per‑hole visual yardbook
* Tee, green front/back, hazards, targets, and custom pins
* Distance calculations rendered **directly on the map**
* Designed to replace traditional hole‑plan sketches

### 📝 Log a Round

* Track scores hole‑by‑hole
* Automatically applies:
  * Preferred courses
  * Preferred tee box color
* Clean flow focused on speed and accuracy

### 📊 Stats & Analysis

* Score trends relative to par
* Consistent ranking logic (par‑adjusted, not raw score)
* Built to surface *patterns* , not noise

### 🧭 Club Distances

* Maintain personal carry distances
* Reference distances while logging or planning shots

### 📚 Rulebook

* Integrated golf rule reference
* Designed for quick lookup during play

### 🧾 Scorecard Viewer

* Review historical rounds
* Compare performance across courses and conditions

---

## 🧠 Design Philosophy (KISS)

* **One primary window**
* Tab‑based navigation (mobile‑app feel)
* Large spacing, clear hierarchy, minimal clutter
* Built with Apple Human Interface Guidelines in mind

Galf prioritizes ****clarity over configuration** and** **signal over features** .

---

## 🛠️ Tech Stack

* **Language:** Python 3
* **UI:** Tkinter
* **Data:** pandas, numpy
* **Mapping:** tkintermapview (where available)
* **Architecture:**
  * `Frontend.py` — UI, views, interaction logic
  * `Backend.py` — data models, calculations, persistence

---

## 📁 Project Structure

```
Galf/
├── Frontend.py        # UI, views, navigation
├── Backend.py         # Data logic, stats, persistence
├── Galf.png           # App / README logo
├── data/              # User data (courses, rounds, prefs)
└── README.md
```

---

## 🚀 Getting Started

### 1. Clone the repo

```bash
git clone https://github.com/Reddsoul/galf.git
cd galf
```

### 2. Install dependencies

```bash
pip install pandas numpy tkintermapview ... theres alot
```

*(Tkinter is included with most Python installs.)*

### 3. Run the app

```bash
python Frontend.py
```

---

## ⚠️ Notes & Limitations

* Mapping features gracefully degrade if optional dependencies are missing
* Designed for desktop use (macOS / Windows / Linux)
* No cloud sync — data stays local by design

---

## 🧭 Roadmap (High‑Level)

* Improved yardbook pin workflows
* Smarter default hole positioning when adding new courses
* Enhanced stats views (dispersion, consistency)
* 

---

## 🤝 Philosophy

> *Golf is a game of decisions made under uncertainty.*

Galf exists to reduce that uncertainty — not by telling you what to do, but by giving you **better information at the moment it matters** with a 0 trust privacy aproach.

---

## 📄 License

MIT License
