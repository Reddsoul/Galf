import json
import os
from statistics import mean

COURSES_FILE = 'data/courses.json'
ROUNDS_FILE  = 'data/rounds.json'

def load_json(filename):
    if not os.path.exists(filename):
        return []
    with open(filename, 'r') as f:
        return json.load(f)

def save_json(filename, data):
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)

class GolfBackend:
    def __init__(self):
        os.makedirs('data', exist_ok=True)
        self.courses = load_json(COURSES_FILE)
        self.rounds  = load_json(ROUNDS_FILE)

    # ---- Courses ----

    def get_courses(self):
        return self.courses

    def get_course_by_name(self, name):
        return next((c for c in self.courses if c["name"] == name), None)

    def add_course(self, course_data):
        # course_data must include name, rating, slope, pars
        # calculate course_handicap
        par_total = sum(course_data["pars"])
        course_handicap = (course_data["slope"] / 113) * (course_data["rating"] - par_total)
        course_data["course_handicap"] = round(course_handicap, 1)

        self.courses.append(course_data)
        save_json(COURSES_FILE, self.courses)

    # ---- Rounds ----

    def get_rounds(self):
        return self.rounds

    def add_round(self, round_data):
        # round_data must include course_name, scores, is_serious, notes, holes_played, total_score
        # backend will also store target_score
        course = self.get_course_by_name(round_data["course_name"])
        if course:
            par = sum(course["pars"])
            round_data["target_score"] = par + round(course["course_handicap"])
        self.rounds.append(round_data)
        save_json(ROUNDS_FILE, self.rounds)

    # ---- Aggregates ----

    def calculate_handicap_index(self):
        diffs = []
        for r in self.rounds:
            if r.get("is_serious") and r.get("holes_played") == 18:
                course = self.get_course_by_name(r["course_name"])
                if course:
                    try:
                        diff = (113 * (r["total_score"] - course["rating"])) / course["slope"]
                        diffs.append(round(diff, 1))
                    except ZeroDivisionError:
                        pass

        diffs.sort()
        n = len(diffs)
        if n < 3:
            return None

        # USGA simplified table lookup
        if n == 3:     idx = diffs[0] - 2.0
        elif n == 4:   idx = diffs[0] - 1.0
        elif n == 5:   idx = diffs[0]
        elif n == 6:   idx = mean(diffs[:2]) - 1.0
        elif n <= 8:   idx = mean(diffs[:2])
        elif n <= 11:  idx = mean(diffs[:3])
        elif n <= 14:  idx = mean(diffs[:4])
        elif n <= 16:  idx = mean(diffs[:5])
        elif n <= 18:  idx = mean(diffs[:6])
        elif n == 19:  idx = mean(diffs[:7])
        else:          idx = mean(diffs[:8])

        return round(idx * 0.96, 1)

    def get_best_round(self):
        serious18 = [r for r in self.rounds if r.get("is_serious") and r.get("holes_played") == 18]
        if not serious18:
            return None
        return min(serious18, key=lambda r: r["total_score"])