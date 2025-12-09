# Golf Handicap Tracker ⛳

A simple Python desktop application for tracking golf scores, managing courses, and calculating your USGA handicap index.

## Features

* **Score Tracking** : Log rounds with hole-by-hole scores for 9 or 18 holes
* **Handicap Calculation** : Automatic USGA/WHS handicap index calculation
* **9-Hole Support** : Front 9, Back 9, or Full 18 — all count toward your handicap (2024 rules)
* **Course Management** : Save courses with multiple tee boxes, ratings, and slopes
* **Club Distance Mapper** : Track how far you hit each club in your bag
* **Round Types** : Distinguish between solo rounds and scrambles
* **Serious/Casual** : Mark rounds as serious (counts toward handicap) or casual
* **Statistics** : View score differentials, averages, and trends

## Installation

### Requirements

* Python 3.8+
* tkinter (usually included with Python)

### Setup

```bash
# Clone or download the files
git clone <your-repo-url>
cd golf-handicap-tracker

# Run the app
python Frontend.py
```

The app will automatically create a** **`data/` folder to store your courses, rounds, and club distances.

## Usage

### Adding a Course

1. Click "Add New Course"
2. Enter club name and course name
3. Select 9 or 18 holes
4. Set par for each hole (3, 4, or 5)
5. Add tee boxes with color, rating, and slope

### Logging a Round

1. Click "Log a Round"
2. Select course and tee box
3. Choose holes to play:** ** **Full 18** ,** ** **Front 9** , or** ****Back 9**
4. Select round type (Solo/Scramble) and if it's serious
5. Enter your score for each hole
6. Submit and add notes

### Handicap Calculation

The app follows** ** **2024 USGA/WHS rules** :

* **Initial Handicap** : Requires 54 holes played (any mix of 9 and 18 hole rounds)
* **Eligible Rounds** : Only serious, solo rounds count toward handicap
* **9-Hole Rounds** : Converted to 18-hole equivalents using expected score formula
* **Calculation** : Uses best differentials based on number of rounds (see table below)

| Rounds | Differentials Used  | Adjustment |
| ------ | ------------------- | ---------- |
| 3      | Lowest 1            | -2.0       |
| 4      | Lowest 1            | -1.0       |
| 5      | Lowest 1            | 0          |
| 6      | Average of lowest 2 | -1.0       |
| 7-8    | Average of lowest 2 | 0          |
| 9-11   | Average of lowest 3 | 0          |
| 12-14  | Average of lowest 4 | 0          |
| 15-16  | Average of lowest 5 | 0          |
| 17-18  | Average of lowest 6 | 0          |
| 19     | Average of lowest 7 | 0          |
| 20+    | Average of lowest 8 | 0          |

Final handicap index = (selected differentials average) × 0.96

## File Structure

```
golf-handicap-tracker/
├── Frontend.py      # GUI application
├── Backend.py       # Data management and calculations
├── README.md
└── data/            # Auto-created
    ├── courses.json
    ├── rounds.json
    └── clubs.json
```

## Data Storage

All data is stored locally in JSON files:

* **courses.json** : Course info, pars, tee boxes
* **rounds.json** : All logged rounds with scores
* **clubs.json** : Club distances

## Contributing

Feel free to fork and submit pull requests for:

* Bug fixes
* New features
* UI improvements

## License

MIT License - Use freely for personal projects.

## Acknowledgments

* USGA for handicap calculation rules
* 2024 WHS updates for 9-hole scoring methodology
