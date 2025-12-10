import json
import os
from statistics import mean
from datetime import datetime

# --- Data files ---
COURSES_FILE = 'data/courses.json'
ROUNDS_FILE = 'data/rounds.json'
CLUBS_FILE = 'data/clubs.json'
RULEBOOK_FILE = 'data/rulebook.json'
BOOKMARKS_FILE = 'data/bookmarks.json'
RULE_NOTES_FILE = 'data/rule_notes.json'


def load_json(filename):
    if not os.path.exists(filename):
        return []
    with open(filename, 'r') as f:
        return json.load(f)


def save_json(filename, data):
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)


# --- Backend Logic ---
class GolfBackend:
    def __init__(self):
        os.makedirs('data', exist_ok=True)
        self.courses = load_json(COURSES_FILE)
        self.rounds = load_json(ROUNDS_FILE)
        self.clubs = load_json(CLUBS_FILE)
        self.rulebook = self._load_rulebook()
        self.bookmarks = load_json(BOOKMARKS_FILE) if os.path.exists(BOOKMARKS_FILE) else []
        self.rule_notes = load_json(RULE_NOTES_FILE) if os.path.exists(RULE_NOTES_FILE) else {}

    # ---- Courses ----
    def get_courses(self):
        return self.courses

    def get_course_by_name(self, name):
        return next((c for c in self.courses if c["name"] == name), None)

    def add_course(self, course_data):
        par_total = sum(course_data["pars"])
        for box in course_data["tee_boxes"]:
            hc = (box["slope"] / 113) * (box["rating"] - par_total)
            box["handicap"] = round(hc, 1)
        # Ensure yardages field exists (backward compatibility)
        if "yardages" not in course_data:
            course_data["yardages"] = {}
        self.courses.append(course_data)
        save_json(COURSES_FILE, self.courses)

    def update_course(self, original_name, course_data):
        par_total = sum(course_data["pars"])
        for box in course_data["tee_boxes"]:
            hc = (box["slope"] / 113) * (box["rating"] - par_total)
            box["handicap"] = round(hc, 1)
        # Ensure yardages field exists (backward compatibility)
        if "yardages" not in course_data:
            course_data["yardages"] = {}
        for i, c in enumerate(self.courses):
            if c["name"] == original_name:
                self.courses[i] = course_data
                break
        save_json(COURSES_FILE, self.courses)

    def delete_course(self, name):
        """Remove a course by name."""
        self.courses = [c for c in self.courses if c["name"] != name]
        save_json(COURSES_FILE, self.courses)

    def get_clubs_list(self):
        """Return list of unique club names."""
        return list(set(c.get("club", "") for c in self.courses if c.get("club")))

    def get_courses_by_club(self, club_name):
        """Return courses belonging to a specific club."""
        return [c for c in self.courses if c.get("club") == club_name]

    def get_course_yardages(self, course_name, tee_color):
        """Get yardages for a specific course and tee box."""
        course = self.get_course_by_name(course_name)
        if not course:
            return None
        yardages = course.get("yardages", {})
        return yardages.get(tee_color, [])

    def get_course_total_yardage(self, course_name, tee_color, holes_choice="full_18"):
        """Get total yardage for specified holes."""
        yardages = self.get_course_yardages(course_name, tee_color)
        if not yardages:
            return None
        
        if holes_choice == "front_9":
            return sum(yardages[:9]) if len(yardages) >= 9 else sum(yardages)
        elif holes_choice == "back_9":
            return sum(yardages[9:18]) if len(yardages) >= 18 else sum(yardages[:9])
        else:
            return sum(yardages)

    # ---- Rounds ----
    def get_rounds(self):
        return self.rounds

    def add_round(self, round_data):
        course = self.get_course_by_name(round_data["course_name"])
        if not course:
            return
        box = next(b for b in course["tee_boxes"] if b["color"] == round_data["tee_color"])
        par = sum(course["pars"])
        round_data["target_score"] = par + round(box["handicap"])
        round_data["tee_rating"] = box["rating"]
        round_data["tee_slope"] = box["slope"]
        round_data["par"] = par
        # Add timestamp if not present
        if "date" not in round_data:
            round_data["date"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.rounds.append(round_data)
        save_json(ROUNDS_FILE, self.rounds)

    def delete_round(self, index):
        """Delete a round by its index."""
        if 0 <= index < len(self.rounds):
            del self.rounds[index]
            save_json(ROUNDS_FILE, self.rounds)

    def update_round(self, index, round_data):
        """Update a round at the given index."""
        if 0 <= index < len(self.rounds):
            self.rounds[index] = round_data
            save_json(ROUNDS_FILE, self.rounds)

    def get_filtered_rounds(self, round_type="all", sort_by="recent"):
        """
        Filter and sort rounds.
        round_type: 'all', 'solo', 'scramble'
        sort_by: 'recent', 'best', 'worst'
        """
        rounds_with_idx = [(i, r) for i, r in enumerate(self.rounds)]

        # Filter by type
        if round_type == "solo":
            rounds_with_idx = [(i, r) for i, r in rounds_with_idx
                              if r.get("round_type", "solo") == "solo"]
        elif round_type == "scramble":
            rounds_with_idx = [(i, r) for i, r in rounds_with_idx
                              if r.get("round_type") == "scramble"]

        # Sort
        if sort_by == "recent":
            rounds_with_idx.sort(key=lambda x: x[1].get("date", ""), reverse=True)
        elif sort_by == "best":
            rounds_with_idx.sort(key=lambda x: x[1].get("total_score", 999))
        elif sort_by == "worst":
            rounds_with_idx.sort(key=lambda x: x[1].get("total_score", 0), reverse=True)

        return rounds_with_idx

    # ---- Aggregates ----
    def calculate_9hole_expected_differential(self, handicap_index):
        """
        Calculate expected 9-hole differential based on current handicap index.
        Formula from 2024 WHS rules: Expected Score = (0.52 × Handicap_Index) + 1.2
        """
        if handicap_index is None:
            return None
        return (0.52 * handicap_index) + 1.2

    def calculate_score_differential(self, round_data, current_handicap=None):
        """
        Calculate score differential for a round.
        For 9-hole rounds, uses the 2024 WHS method with expected score.
        """
        try:
            holes_played = round_data.get("holes_played", 18)
            total_score = round_data["total_score"]
            tee_rating = round_data["tee_rating"]
            tee_slope = round_data["tee_slope"]

            if holes_played == 18:
                # Standard 18-hole calculation
                diff = (113 * (total_score - tee_rating)) / tee_slope
            else:
                # 9-hole calculation (2024 WHS rules)
                # First calculate 9-hole differential
                nine_hole_diff = (113 * (total_score - tee_rating)) / tee_slope

                # Add expected differential for the unplayed 9
                if current_handicap is not None:
                    expected_diff = self.calculate_9hole_expected_differential(current_handicap)
                    diff = nine_hole_diff + expected_diff
                else:
                    # If no handicap established, double the 9-hole diff as approximation
                    diff = nine_hole_diff * 2

            return round(diff, 1)
        except (ZeroDivisionError, KeyError):
            return None

    def calculate_handicap_index(self):
        """
        Calculate handicap index using serious, solo rounds (both 9 and 18 hole).
        Uses the official USGA/WHS formula with the handicap table adjustments.
        9-hole rounds are converted to 18-hole equivalents using expected score.
        """
        # First pass: calculate differentials for 18-hole rounds to establish base handicap
        diffs_18 = []
        for r in self.rounds:
            is_solo = r.get("round_type", "solo") == "solo"
            is_serious = r.get("is_serious", False)
            is_18 = r.get("holes_played") == 18

            if is_solo and is_serious and is_18:
                diff = self.calculate_score_differential(r)
                if diff is not None:
                    diffs_18.append(diff)

        # Calculate preliminary handicap from 18-hole rounds
        preliminary_handicap = None
        if len(diffs_18) >= 3:
            sorted_diffs = sorted(diffs_18)
            preliminary_handicap = self._apply_handicap_table(sorted_diffs)

        # Second pass: include 9-hole rounds using the preliminary handicap
        all_diffs = []
        for r in self.rounds:
            is_solo = r.get("round_type", "solo") == "solo"
            is_serious = r.get("is_serious", False)

            if is_solo and is_serious:
                holes = r.get("holes_played", 18)
                if holes == 18:
                    diff = self.calculate_score_differential(r)
                elif holes == 9 and preliminary_handicap is not None:
                    # Only include 9-hole rounds if we have an established handicap
                    diff = self.calculate_score_differential(r, preliminary_handicap)
                else:
                    continue

                if diff is not None:
                    all_diffs.append(diff)

        if len(all_diffs) < 3:
            return None

        all_diffs.sort()
        return self._apply_handicap_table(all_diffs)

    def _apply_handicap_table(self, sorted_diffs):
        """Apply the USGA handicap table to sorted differentials."""
        n = len(sorted_diffs)

        if n < 3:
            return None

        if n == 3:
            idx = sorted_diffs[0] - 2.0
        elif n == 4:
            idx = sorted_diffs[0] - 1.0
        elif n == 5:
            idx = sorted_diffs[0]
        elif n == 6:
            idx = mean(sorted_diffs[:2]) - 1.0
        elif n <= 8:
            idx = mean(sorted_diffs[:2])
        elif n <= 11:
            idx = mean(sorted_diffs[:3])
        elif n <= 14:
            idx = mean(sorted_diffs[:4])
        elif n <= 16:
            idx = mean(sorted_diffs[:5])
        elif n <= 18:
            idx = mean(sorted_diffs[:6])
        elif n == 19:
            idx = mean(sorted_diffs[:7])
        else:
            idx = mean(sorted_diffs[:8])

        # Apply 0.96 multiplier (bonus for improvement)
        return round(idx * 0.96, 1)

    def get_handicap_rounds_count(self):
        """Return count of rounds eligible for handicap calculation."""
        count_18 = 0
        count_9 = 0
        for r in self.rounds:
            is_solo = r.get("round_type", "solo") == "solo"
            is_serious = r.get("is_serious", False)
            if is_solo and is_serious:
                if r.get("holes_played") == 18:
                    count_18 += 1
                elif r.get("holes_played") == 9:
                    count_9 += 1
        return {"18_hole": count_18, "9_hole": count_9, "total": count_18 + count_9}

    def get_total_holes_played(self):
        """Return total holes played for handicap-eligible rounds."""
        total = 0
        for r in self.rounds:
            is_solo = r.get("round_type", "solo") == "solo"
            is_serious = r.get("is_serious", False)
            if is_solo and is_serious:
                total += r.get("holes_played", 0)
        return total

    def get_best_round(self, holes_filter=None):
        """
        Get best serious solo round.
        holes_filter: None for any, 18 for 18-hole only, 9 for 9-hole only
        """
        serious_rounds = [r for r in self.rounds
                          if r.get("is_serious")
                          and r.get("round_type", "solo") == "solo"]

        if holes_filter:
            serious_rounds = [r for r in serious_rounds if r.get("holes_played") == holes_filter]

        if not serious_rounds:
            return None

        # For comparison, normalize to score vs par
        def score_vs_par(r):
            return r["total_score"] - r.get("par", 36 if r.get("holes_played") == 9 else 72)

        return min(serious_rounds, key=score_vs_par)

    def get_score_differentials(self):
        """Return list of all score differentials for serious solo rounds."""
        # Get current handicap for 9-hole calculations
        current_handicap = self.calculate_handicap_index()

        diffs = []
        for r in self.rounds:
            is_solo = r.get("round_type", "solo") == "solo"
            is_serious = r.get("is_serious", False)

            if is_solo and is_serious:
                holes = r.get("holes_played", 18)
                if holes == 18:
                    diff = self.calculate_score_differential(r)
                elif holes == 9 and current_handicap is not None:
                    diff = self.calculate_score_differential(r, current_handicap)
                else:
                    continue

                if diff is not None:
                    diffs.append({
                        "diff": diff,
                        "course": r["course_name"],
                        "score": r["total_score"],
                        "holes": holes,
                        "date": r.get("date", "N/A")
                    })

        return sorted(diffs, key=lambda x: x["diff"])

    # ---- Club Distances ----
    def get_clubs(self):
        """Return all saved clubs with distances."""
        return self.clubs

    def add_club(self, club_data):
        """
        Add a new club.
        club_data: {"name": "7 Iron", "distance": 150, "notes": ""}
        """
        # Check for duplicate
        existing = next((c for c in self.clubs if c["name"].lower() == club_data["name"].lower()), None)
        if existing:
            return False
        self.clubs.append(club_data)
        save_json(CLUBS_FILE, self.clubs)
        return True

    def update_club(self, original_name, club_data):
        """Update an existing club."""
        for i, c in enumerate(self.clubs):
            if c["name"] == original_name:
                self.clubs[i] = club_data
                save_json(CLUBS_FILE, self.clubs)
                return True
        return False

    def delete_club(self, name):
        """Delete a club by name."""
        self.clubs = [c for c in self.clubs if c["name"] != name]
        save_json(CLUBS_FILE, self.clubs)

    def get_clubs_sorted_by_distance(self):
        """Return clubs sorted by distance (longest first)."""
        return sorted(self.clubs, key=lambda c: c.get("distance", 0), reverse=True)

    # ---- Rulebook Management ----
    def _load_rulebook(self):
        """Load the rulebook from file or create default structure."""
        if os.path.exists(RULEBOOK_FILE):
            return load_json(RULEBOOK_FILE)
        else:
            # Create default rulebook structure with sample USGA/PGA rules
            default_rulebook = self._create_default_rulebook()
            save_json(RULEBOOK_FILE, default_rulebook)
            return default_rulebook

    def _create_default_rulebook(self):
        """Create a default rulebook with USGA/PGA rules structure."""
        return {
            "version": "2024",
            "last_updated": datetime.now().strftime("%Y-%m-%d"),
            "sections": [
                {
                    "id": "1",
                    "title": "The Game, Player Conduct and the Rules",
                    "rules": [
                        {
                            "id": "1.1",
                            "title": "The Game of Golf",
                            "content": "Golf is played in a round of 18 (or fewer) holes on a course by striking a ball with a club. Each hole starts with a stroke from the teeing area and ends when the ball is holed on the putting green (or when the Rules otherwise say the hole is completed). For each stroke, the player must play the ball as it lies and play the course as they find it."
                        },
                        {
                            "id": "1.2",
                            "title": "Standards of Player Conduct",
                            "content": "All players are expected to play in the spirit of the game by acting with integrity, showing consideration to others, and taking good care of the course. Players should play at a prompt pace and look out for the safety of others."
                        },
                        {
                            "id": "1.3",
                            "title": "Playing by the Rules",
                            "content": "Players are responsible for applying the Rules to themselves. Players are expected to recognize when they have breached a Rule, be honest in reporting, and promptly apply any penalty."
                        }
                    ]
                },
                {
                    "id": "2",
                    "title": "The Course",
                    "rules": [
                        {
                            "id": "2.1",
                            "title": "Course Boundaries and Out of Bounds",
                            "content": "The course is all areas inside the boundary edge set by the Committee. All areas outside the boundary edge are out of bounds. The boundary edge extends both up and down from the ground."
                        },
                        {
                            "id": "2.2",
                            "title": "Defined Areas of the Course",
                            "content": "There are five defined areas of the course: (1) The general area, (2) The teeing area, (3) All penalty areas, (4) All bunkers, and (5) The putting green of the hole being played."
                        },
                        {
                            "id": "2.3",
                            "title": "Objects and Conditions that Can Affect Play",
                            "content": "Certain Rules may give free relief from obstructions, abnormal course conditions, dangerous animal conditions, or integral objects."
                        }
                    ]
                },
                {
                    "id": "3",
                    "title": "The Competition",
                    "rules": [
                        {
                            "id": "3.1",
                            "title": "Match Play and Stroke Play",
                            "content": "In Match Play, a player and opponent compete against each other based on holes won, lost or tied. In Stroke Play, all players compete against one another based on total score."
                        },
                        {
                            "id": "3.2",
                            "title": "The Scorecard",
                            "content": "In stroke play, the player's scorecard is used to record the player's handicap and score for each hole. The player is responsible for the correctness of the hole scores entered on the scorecard."
                        },
                        {
                            "id": "3.3",
                            "title": "Handicaps",
                            "content": "A handicap is used to allow players of different abilities to compete on an equal basis. The Course Handicap™ is the number of strokes the player receives to adjust their gross score to a net score."
                        }
                    ]
                },
                {
                    "id": "4",
                    "title": "Player's Equipment",
                    "rules": [
                        {
                            "id": "4.1",
                            "title": "Clubs",
                            "content": "A player may carry no more than 14 clubs during a round. Clubs must conform to the requirements in the Equipment Rules. If a club is damaged during a round, the player may continue to use the damaged club or have it repaired."
                        },
                        {
                            "id": "4.2",
                            "title": "Balls",
                            "content": "The ball must conform to the requirements in the Equipment Rules. A player must hole out with the same ball played from the teeing area unless the Rules allow or require substitution."
                        },
                        {
                            "id": "4.3",
                            "title": "Use of Equipment",
                            "content": "Players may use equipment to help play, but must not use equipment in a way that gives artificial advantage or goes against the spirit of the game."
                        }
                    ]
                },
                {
                    "id": "5",
                    "title": "Playing the Round",
                    "rules": [
                        {
                            "id": "5.1",
                            "title": "Starting a Round",
                            "content": "A player's round starts when the player makes a stroke to begin their first hole. The player must start at the time and place set by the Committee."
                        },
                        {
                            "id": "5.2",
                            "title": "Practicing on Course",
                            "content": "Before or between rounds, players may practice on the competition course unless prohibited by Committee. Between holes, practice strokes are not allowed except on or near the putting green just completed."
                        },
                        {
                            "id": "5.3",
                            "title": "Ending a Round",
                            "content": "A player's round ends when all holes have been completed or when the player has been disqualified."
                        }
                    ]
                },
                {
                    "id": "6",
                    "title": "Playing a Hole",
                    "rules": [
                        {
                            "id": "6.1",
                            "title": "Starting Play of a Hole",
                            "content": "A hole begins when the player makes a stroke from the teeing area to begin the hole. The ball must be played from within the teeing area."
                        },
                        {
                            "id": "6.2",
                            "title": "Playing Ball from Teeing Area",
                            "content": "A ball is in the teeing area when any part of the ball touches or is above any part of the teeing area. The player may use a tee."
                        },
                        {
                            "id": "6.3",
                            "title": "Ball Used in Play of Hole",
                            "content": "A player must normally hole out with the same ball played from the teeing area. Substitution is allowed when a ball is lost, in a penalty area, or unplayable."
                        }
                    ]
                },
                {
                    "id": "7",
                    "title": "Ball Search and Identification",
                    "rules": [
                        {
                            "id": "7.1",
                            "title": "How to Fairly Search",
                            "content": "A player may take reasonable actions to find and identify their ball, including moving sand, water, and movable obstructions. If excess damage is caused, the player must restore the original lie."
                        },
                        {
                            "id": "7.2",
                            "title": "Identifying Ball",
                            "content": "A player's ball at rest may be identified by seeing it come to rest, by an identifying mark on the ball, or by finding a ball with the same characteristics in an area where the ball is expected to be."
                        },
                        {
                            "id": "7.3",
                            "title": "Ball Lost",
                            "content": "A ball is lost if not found within 3 minutes after the player or caddie begins to search for it."
                        },
                        {
                            "id": "7.4",
                            "title": "Provisional Ball",
                            "content": "If a ball might be lost outside a penalty area or out of bounds, the player may play a provisional ball to save time."
                        }
                    ]
                },
                {
                    "id": "8",
                    "title": "Playing the Ball",
                    "rules": [
                        {
                            "id": "8.1",
                            "title": "Actions That Improve Conditions",
                            "content": "A player must not improve the conditions affecting the stroke by moving, bending or breaking anything growing or fixed, creating or eliminating irregularities of surface, removing or pressing down sand or loose soil, or removing dew, frost or water."
                        },
                        {
                            "id": "8.2",
                            "title": "Actions That Worsen Conditions",
                            "content": "If a player or someone else worsens the conditions affecting the stroke, the player may restore them if possible."
                        },
                        {
                            "id": "8.3",
                            "title": "Ball Moving During Backswing or Stroke",
                            "content": "If a player's ball at rest moves after the player has begun the backswing for a stroke and the stroke is made, the ball must be played as it lies."
                        }
                    ]
                },
                {
                    "id": "9",
                    "title": "Ball Played as It Lies",
                    "rules": [
                        {
                            "id": "9.1",
                            "title": "Ball Played as It Lies",
                            "content": "A ball must be played as it lies, except when the Rules allow or require the player to play from a different place or lift the ball."
                        },
                        {
                            "id": "9.2",
                            "title": "Deciding Point Where Ball Came to Rest",
                            "content": "If the exact spot where a ball came to rest is not known, the player must use their reasonable judgment to determine the spot."
                        },
                        {
                            "id": "9.3",
                            "title": "Ball Lifted or Moved by Outside Influence",
                            "content": "If it is known or virtually certain that an outside influence lifted or moved a player's ball, there is no penalty and the ball must be replaced."
                        },
                        {
                            "id": "9.4",
                            "title": "Ball Moved by Player",
                            "content": "If the player lifts or deliberately touches their ball at rest or causes it to move, the player gets one penalty stroke. The ball must be replaced."
                        }
                    ]
                },
                {
                    "id": "10",
                    "title": "Preparing and Making a Stroke",
                    "rules": [
                        {
                            "id": "10.1",
                            "title": "Making a Stroke",
                            "content": "A stroke is made by fairly striking the ball with the head of the club. The player must not push, scrape or scoop the ball."
                        },
                        {
                            "id": "10.2",
                            "title": "Advice and Other Help",
                            "content": "During a round, a player must not give advice to anyone in the competition, ask anyone for advice except their caddie, or touch another player's equipment to learn information."
                        },
                        {
                            "id": "10.3",
                            "title": "Caddies",
                            "content": "A player may get help from a caddie. The caddie may carry clubs, give advice, search for the ball, and take other actions as allowed by the Rules."
                        }
                    ]
                },
                {
                    "id": "11",
                    "title": "Ball in Motion",
                    "rules": [
                        {
                            "id": "11.1",
                            "title": "Ball in Motion Accidentally Hits Person or Outside Influence",
                            "content": "If a ball in motion accidentally hits any person or outside influence, there is no penalty to any player. The ball must be played as it lies."
                        },
                        {
                            "id": "11.2",
                            "title": "Ball in Motion Deliberately Deflected or Stopped",
                            "content": "If any person deliberately deflects or stops a ball in motion, the Rules determine where the ball must be played from."
                        },
                        {
                            "id": "11.3",
                            "title": "Deliberately Moving Objects to Affect Ball in Motion",
                            "content": "A player must not deliberately move an object or take any action to affect where a ball in motion might come to rest."
                        }
                    ]
                },
                {
                    "id": "12",
                    "title": "Bunkers",
                    "rules": [
                        {
                            "id": "12.1",
                            "title": "When Ball Is in Bunker",
                            "content": "A ball is in a bunker when any part of the ball touches sand on the ground inside the edge of the bunker or is inside the edge and resting on or in anything else."
                        },
                        {
                            "id": "12.2",
                            "title": "Playing Ball in Bunker",
                            "content": "Before making a stroke at a ball in a bunker, a player must not touch sand in the bunker with a hand or club, except that the player may rest the club lightly on the sand."
                        },
                        {
                            "id": "12.3",
                            "title": "Relief When Ball in Bunker Is Unplayable",
                            "content": "If a ball is unplayable in a bunker, the player may take unplayable ball relief, with options including back-on-the-line relief outside the bunker for 2 penalty strokes."
                        }
                    ]
                },
                {
                    "id": "13",
                    "title": "Putting Greens",
                    "rules": [
                        {
                            "id": "13.1",
                            "title": "When Ball Is on Putting Green",
                            "content": "A ball is on the putting green when any part of the ball touches the putting green or lies on or in anything inside the edge of the putting green."
                        },
                        {
                            "id": "13.2",
                            "title": "Marking, Lifting and Cleaning Ball",
                            "content": "A ball on the putting green may be lifted and cleaned. The spot must be marked before lifting."
                        },
                        {
                            "id": "13.3",
                            "title": "Improvements Allowed on Putting Green",
                            "content": "On the putting green, the player may repair damage and remove sand and loose soil."
                        },
                        {
                            "id": "13.4",
                            "title": "Attending or Removing Flagstick",
                            "content": "The player may leave the flagstick in the hole, have it removed, or have someone attend it."
                        }
                    ]
                },
                {
                    "id": "14",
                    "title": "Procedures for Ball",
                    "rules": [
                        {
                            "id": "14.1",
                            "title": "Marking, Lifting and Cleaning Ball",
                            "content": "Before lifting a ball that must be replaced, the player must mark the spot. The player may clean the ball when lifting it except when lifting to see if it is cut or cracked, to identify it, or because it interferes with play."
                        },
                        {
                            "id": "14.2",
                            "title": "Replacing Ball on Spot",
                            "content": "A ball that was lifted or moved and must be replaced must be placed on its original spot."
                        },
                        {
                            "id": "14.3",
                            "title": "Dropping Ball in Relief Area",
                            "content": "When taking relief, the player must drop the ball in the relief area by holding the ball at knee height and dropping it straight down."
                        }
                    ]
                },
                {
                    "id": "15",
                    "title": "Relief from Loose Impediments and Movable Obstructions",
                    "rules": [
                        {
                            "id": "15.1",
                            "title": "Loose Impediments",
                            "content": "A player may remove any loose impediment anywhere on or off the course, and may do so in any manner. If the ball moves as a result, there is generally a one-stroke penalty."
                        },
                        {
                            "id": "15.2",
                            "title": "Movable Obstructions",
                            "content": "A player may remove a movable obstruction anywhere on or off the course and may do so in any manner."
                        }
                    ]
                },
                {
                    "id": "16",
                    "title": "Relief from Abnormal Course Conditions",
                    "rules": [
                        {
                            "id": "16.1",
                            "title": "Abnormal Course Conditions",
                            "content": "Free relief is allowed when an abnormal course condition (animal hole, ground under repair, immovable obstruction, or temporary water) interferes with the player's lie, stance, or area of intended swing."
                        },
                        {
                            "id": "16.2",
                            "title": "Dangerous Animal Condition",
                            "content": "A player may take relief from a dangerous animal condition even without interference with the player's lie or stance."
                        }
                    ]
                },
                {
                    "id": "17",
                    "title": "Penalty Areas",
                    "rules": [
                        {
                            "id": "17.1",
                            "title": "Options for Ball in Penalty Area",
                            "content": "Penalty areas are marked red (lateral) or yellow. When a ball is in a penalty area, the player may play it as it lies or take penalty relief under Rule 17.1."
                        },
                        {
                            "id": "17.2",
                            "title": "Relief Options for Ball in Penalty Area",
                            "content": "With one penalty stroke, the player may take stroke-and-distance relief, back-on-the-line relief, or (for red penalty areas) lateral relief."
                        }
                    ]
                },
                {
                    "id": "18",
                    "title": "Stroke-and-Distance Relief, Lost Ball, Out of Bounds",
                    "rules": [
                        {
                            "id": "18.1",
                            "title": "Relief Under Penalty of Stroke and Distance",
                            "content": "At any time, a player may take stroke-and-distance relief by adding one penalty stroke and playing from where the previous stroke was made."
                        },
                        {
                            "id": "18.2",
                            "title": "Ball Lost or Out of Bounds",
                            "content": "If a ball is lost or out of bounds, the player must take stroke-and-distance relief by adding one penalty stroke and playing from where the previous stroke was made."
                        },
                        {
                            "id": "18.3",
                            "title": "Provisional Ball",
                            "content": "To save time, a player who thinks the ball might be lost or out of bounds may play a provisional ball."
                        }
                    ]
                },
                {
                    "id": "19",
                    "title": "Unplayable Ball",
                    "rules": [
                        {
                            "id": "19.1",
                            "title": "Player May Decide Ball Is Unplayable",
                            "content": "A player is the only person who may decide to treat their ball as unplayable. The ball may be declared unplayable anywhere on the course except in a penalty area."
                        },
                        {
                            "id": "19.2",
                            "title": "Relief Options for Unplayable Ball",
                            "content": "With one penalty stroke, the player has three options: stroke-and-distance relief, back-on-the-line relief, or lateral relief within two club-lengths."
                        }
                    ]
                },
                {
                    "id": "20",
                    "title": "Resolving Rules Issues",
                    "rules": [
                        {
                            "id": "20.1",
                            "title": "Resolving Issues During Round",
                            "content": "Players should resolve any Rules issues with the opponent (match play) or with the Committee (stroke play)."
                        },
                        {
                            "id": "20.2",
                            "title": "Rulings on Issues Under the Rules",
                            "content": "Players may request a ruling from the Committee. In match play, players may agree how to decide a Rules issue."
                        }
                    ]
                }
            ]
        }

    def get_rulebook(self):
        """Return the current rulebook."""
        return self.rulebook

    def get_rulebook_version(self):
        """Return the rulebook version info."""
        return {
            "version": self.rulebook.get("version", "Unknown"),
            "last_updated": self.rulebook.get("last_updated", "Unknown")
        }

    def search_rulebook(self, query):
        """
        Search the rulebook for rules matching the query.
        Returns list of matching rules with section info.
        """
        query = query.lower()
        results = []

        for section in self.rulebook.get("sections", []):
            for rule in section.get("rules", []):
                # Search in rule ID, title, and content
                if (query in rule.get("id", "").lower() or
                    query in rule.get("title", "").lower() or
                    query in rule.get("content", "").lower()):
                    results.append({
                        "section_id": section["id"],
                        "section_title": section["title"],
                        "rule_id": rule["id"],
                        "rule_title": rule["title"],
                        "content": rule["content"]
                    })

        return results

    def get_rule_by_id(self, rule_id):
        """Get a specific rule by its ID."""
        for section in self.rulebook.get("sections", []):
            for rule in section.get("rules", []):
                if rule.get("id") == rule_id:
                    return {
                        "section_id": section["id"],
                        "section_title": section["title"],
                        "rule": rule
                    }
        return None

    def get_all_sections(self):
        """Return list of all sections for navigation."""
        return [(s["id"], s["title"]) for s in self.rulebook.get("sections", [])]

    def get_section_rules(self, section_id):
        """Get all rules in a specific section."""
        for section in self.rulebook.get("sections", []):
            if section["id"] == section_id:
                return section.get("rules", [])
        return []

    def update_rulebook(self, new_rulebook_data):
        """
        Update the rulebook with new data.
        This allows for rulebook updates without code changes.
        """
        self.rulebook = new_rulebook_data
        self.rulebook["last_updated"] = datetime.now().strftime("%Y-%m-%d")
        save_json(RULEBOOK_FILE, self.rulebook)

    def import_rulebook_from_file(self, filepath):
        """Import a rulebook from a JSON file."""
        try:
            with open(filepath, 'r') as f:
                new_rulebook = json.load(f)
            self.update_rulebook(new_rulebook)
            return True
        except Exception as e:
            print(f"Error importing rulebook: {e}")
            return False

    # ---- Bookmarks ----
    def get_bookmarks(self):
        """Return all bookmarked rules."""
        return self.bookmarks

    def add_bookmark(self, rule_id):
        """Add a rule to bookmarks."""
        if rule_id not in self.bookmarks:
            self.bookmarks.append(rule_id)
            save_json(BOOKMARKS_FILE, self.bookmarks)
            return True
        return False

    def remove_bookmark(self, rule_id):
        """Remove a rule from bookmarks."""
        if rule_id in self.bookmarks:
            self.bookmarks.remove(rule_id)
            save_json(BOOKMARKS_FILE, self.bookmarks)
            return True
        return False

    def is_bookmarked(self, rule_id):
        """Check if a rule is bookmarked."""
        return rule_id in self.bookmarks

    # ---- Rule Notes ----
    def get_rule_notes(self, rule_id):
        """Get user notes for a specific rule."""
        return self.rule_notes.get(rule_id, "")

    def set_rule_notes(self, rule_id, notes):
        """Set user notes for a specific rule."""
        if notes.strip():
            self.rule_notes[rule_id] = notes.strip()
        elif rule_id in self.rule_notes:
            del self.rule_notes[rule_id]
        save_json(RULE_NOTES_FILE, self.rule_notes)

    def get_all_notes(self):
        """Return all rules with notes."""
        return self.rule_notes

    # ---- Statistics ----
    def get_statistics(self):
        """Return various statistics about the player's rounds."""
        total_rounds = len(self.rounds)
        serious_rounds = len([r for r in self.rounds if r.get("is_serious")])
        solo_rounds = len([r for r in self.rounds if r.get("round_type", "solo") == "solo"])
        scramble_rounds = len([r for r in self.rounds if r.get("round_type") == "scramble"])

        # Count by holes
        rounds_18 = len([r for r in self.rounds if r.get("holes_played") == 18])
        rounds_9 = len([r for r in self.rounds if r.get("holes_played") == 9])

        # Average score for serious 18-hole rounds
        serious_18 = [r for r in self.rounds
                      if r.get("is_serious") and r.get("holes_played") == 18]
        avg_score_18 = None
        if serious_18:
            avg_score_18 = round(mean(r["total_score"] for r in serious_18), 1)

        # Average score for serious 9-hole rounds
        serious_9 = [r for r in self.rounds
                     if r.get("is_serious") and r.get("holes_played") == 9]
        avg_score_9 = None
        if serious_9:
            avg_score_9 = round(mean(r["total_score"] for r in serious_9), 1)

        handicap_counts = self.get_handicap_rounds_count()
        total_holes = self.get_total_holes_played()

        return {
            "total_rounds": total_rounds,
            "serious_rounds": serious_rounds,
            "solo_rounds": solo_rounds,
            "scramble_rounds": scramble_rounds,
            "rounds_18": rounds_18,
            "rounds_9": rounds_9,
            "avg_score_18": avg_score_18,
            "avg_score_9": avg_score_9,
            "handicap_eligible_18": handicap_counts["18_hole"],
            "handicap_eligible_9": handicap_counts["9_hole"],
            "total_holes_played": total_holes
        }


# ---- Scorecard Export Helper Functions ----
def generate_scorecard_data(backend, round_data):
    """
    Generate formatted scorecard data for export.
    Returns a dictionary with all data needed for PDF/image export.
    """
    course = backend.get_course_by_name(round_data["course_name"])
    pars = course["pars"] if course else [4] * len(round_data.get("scores", []))
    
    # Get yardages if available
    yardages = []
    if course:
        tee_color = round_data.get("tee_color", "")
        yardages = course.get("yardages", {}).get(tee_color, [])
    
    scores = round_data.get("scores", [])
    diff = round_data.get("total_score", 0) - round_data.get("par", 72)
    diff_str = f"+{diff}" if diff > 0 else str(diff)
    
    # Calculate front/back 9 totals
    front_9_scores = [s for s in scores[:9] if s is not None]
    back_9_scores = [s for s in scores[9:18] if s is not None] if len(scores) > 9 else []
    front_9_pars = pars[:9]
    back_9_pars = pars[9:18] if len(pars) > 9 else []
    front_9_yards = yardages[:9] if len(yardages) >= 9 else yardages
    back_9_yards = yardages[9:18] if len(yardages) >= 18 else []
    
    return {
        "course_name": round_data.get("course_name", "Unknown Course"),
        "club_name": course.get("club", "") if course else "",
        "date": round_data.get("date", "N/A"),
        "tee_color": round_data.get("tee_color", "N/A"),
        "holes_played": round_data.get("holes_played", 18),
        "holes_choice": round_data.get("holes_choice", "full_18"),
        "total_score": round_data.get("total_score", 0),
        "par": round_data.get("par", 72),
        "diff_str": diff_str,
        "target_score": round_data.get("target_score", "N/A"),
        "round_type": round_data.get("round_type", "solo"),
        "is_serious": round_data.get("is_serious", False),
        "notes": round_data.get("notes", ""),
        "pars": pars,
        "scores": scores,
        "yardages": yardages,
        "front_9": {
            "pars": front_9_pars,
            "scores": front_9_scores,
            "yardages": front_9_yards,
            "par_total": sum(front_9_pars),
            "score_total": sum(front_9_scores) if front_9_scores else 0,
            "yards_total": sum(front_9_yards) if front_9_yards else 0
        },
        "back_9": {
            "pars": back_9_pars,
            "scores": back_9_scores,
            "yardages": back_9_yards,
            "par_total": sum(back_9_pars) if back_9_pars else 0,
            "score_total": sum(back_9_scores) if back_9_scores else 0,
            "yards_total": sum(back_9_yards) if back_9_yards else 0
        }
    }