import json
import os
from statistics import mean
from datetime import datetime

# --- Data files ---
COURSES_FILE = 'data/courses.json'
ROUNDS_FILE = 'data/rounds.json'
CLUBS_FILE = 'data/clubs.json'


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
        self.courses.append(course_data)
        save_json(COURSES_FILE, self.courses)

    def update_course(self, original_name, course_data):
        par_total = sum(course_data["pars"])
        for box in course_data["tee_boxes"]:
            hc = (box["slope"] / 113) * (box["rating"] - par_total)
            box["handicap"] = round(hc, 1)
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