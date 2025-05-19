import tkinter as tk
from tkinter import messagebox
import json
import os
from statistics import mean

COURSES_FILE = 'data/courses.json'
ROUNDS_FILE = 'data/rounds.json'

def load_json(filename):
    if not os.path.exists(filename):
        return []
    with open(filename, 'r') as f:
        return json.load(f)

def save_json(filename, data):
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)

class GolfApp:
    def __init__(self, root):
        self.root = root
        root.title("Golf App")

        self.courses = load_json(COURSES_FILE)
        self.rounds = load_json(ROUNDS_FILE)

        # UI Elements
        self.main_frame = tk.Frame(root)
        self.main_frame.pack()

        self.round_frame = tk.LabelFrame(self.main_frame, text="Add Round")
        self.info_frame = tk.LabelFrame(self.main_frame, text="Summary")

        self.round_frame.grid(row=0, column=0, padx=10, pady=10)
        self.info_frame.grid(row=0, column=1, padx=10, pady=10)

        self.create_round_ui()
        self.create_info_ui()

        tk.Button(self.main_frame, text="Add New Course", command=self.open_course_window).grid(row=1, column=0, columnspan=2, pady=10)

        self.refresh_summary()

    def create_round_ui(self):
        tk.Label(self.round_frame, text="Course Name").grid(row=0, column=0)
        tk.Label(self.round_frame, text="Score").grid(row=1, column=0)
        tk.Label(self.round_frame, text="Holes (must be 18)").grid(row=2, column=0)

        self.round_course_name = tk.Entry(self.round_frame)
        self.round_score = tk.Entry(self.round_frame)
        self.round_holes = tk.Entry(self.round_frame)
        self.is_serious = tk.BooleanVar()
        tk.Checkbutton(self.round_frame, text="Serious Round", variable=self.is_serious).grid(row=3, columnspan=2)

        self.round_course_name.grid(row=0, column=1)
        self.round_score.grid(row=1, column=1)
        self.round_holes.grid(row=2, column=1)

        tk.Button(self.round_frame, text="Save Round", command=self.save_round).grid(row=4, columnspan=2)

    def create_info_ui(self):
        self.handicap_label = tk.Label(self.info_frame, text="Handicap Index: ")
        self.best_round_label = tk.Label(self.info_frame, text="Best Round: ")
        self.total_rounds_label = tk.Label(self.info_frame, text="Total Rounds: ")

        self.handicap_label.pack()
        self.best_round_label.pack()
        self.total_rounds_label.pack()

    def open_course_window(self):
        self.course_window = tk.Toplevel(self.root)
        self.course_window.title("Add New Course")

        tk.Label(self.course_window, text="Course Name").grid(row=0, column=0)
        tk.Label(self.course_window, text="Rating").grid(row=1, column=0)
        tk.Label(self.course_window, text="Slope").grid(row=2, column=0)

        self.course_name_entry = tk.Entry(self.course_window)
        self.course_rating_entry = tk.Entry(self.course_window)
        self.course_slope_entry = tk.Entry(self.course_window)

        self.course_name_entry.grid(row=0, column=1)
        self.course_rating_entry.grid(row=1, column=1)
        self.course_slope_entry.grid(row=2, column=1)

        tk.Button(self.course_window, text="Next", command=self.ask_hole_count).grid(row=3, columnspan=2)

    def ask_hole_count(self):
        try:
            self.course_name = self.course_name_entry.get()
            self.course_rating = float(self.course_rating_entry.get())
            self.course_slope = int(self.course_slope_entry.get())
        except ValueError:
            messagebox.showerror("Error", "Rating must be float and slope must be integer.")
            return

        for widget in self.course_window.winfo_children():
            widget.destroy()

        tk.Label(self.course_window, text="Number of Holes").pack()
        self.hole_count_var = tk.IntVar(value=9)
        tk.Radiobutton(self.course_window, text="9 Holes", variable=self.hole_count_var, value=9).pack()
        tk.Radiobutton(self.course_window, text="18 Holes", variable=self.hole_count_var, value=18).pack()

        tk.Button(self.course_window, text="Next", command=self.ask_pars).pack()

    def ask_pars(self):
        self.num_holes = self.hole_count_var.get()
        self.par_vars = []

        for widget in self.course_window.winfo_children():
            widget.destroy()

        tk.Label(self.course_window, text="Select Par for Each Hole").grid(row=0, column=0, columnspan=4)

        for i in range(self.num_holes):
            tk.Label(self.course_window, text=f"Hole {i+1}").grid(row=i+1, column=0, padx=5, pady=2)

            var = tk.IntVar(value=4)  # Default to 4
            self.par_vars.append(var)

            for j, val in enumerate([3, 4, 5]):
                b = tk.Radiobutton(self.course_window, text=str(val), variable=var, value=val)
                b.grid(row=i+1, column=j+1)

        tk.Button(self.course_window, text="Save Course", command=self.save_course).grid(row=self.num_holes+1, column=0, columnspan=4, pady=10)

    def save_course(self):
        par_list = [var.get() for var in self.par_vars]

        course = {
            "name": self.course_name,
            "rating": self.course_rating,
            "slope": self.course_slope,
            "pars": par_list
        }

        existing = next((c for c in self.courses if c["name"] == self.course_name), None)
        if existing:
            self.courses.remove(existing)

        self.courses.append(course)
        save_json(COURSES_FILE, self.courses)
        self.course_window.destroy()
        messagebox.showinfo("Success", f"Saved course: {self.course_name}")

    def save_round(self):
        try:
            name = self.round_course_name.get()
            score = int(self.round_score.get())
            holes = int(self.round_holes.get())
            serious = self.is_serious.get()

            if holes != 18:
                messagebox.showerror("Error", "Only 18-hole rounds allowed for handicap.")
                return

            if not any(c["name"] == name for c in self.courses):
                messagebox.showerror("Error", "Course not found. Add it first.")
                return

            self.rounds.append({
                "course_name": name,
                "score": score,
                "holes_played": holes,
                "is_serious": serious
            })

            save_json(ROUNDS_FILE, self.rounds)
            messagebox.showinfo("Saved", "Round recorded.")
            self.refresh_summary()

        except ValueError:
            messagebox.showerror("Error", "Invalid input. Score and holes must be integers.")

    def refresh_summary(self):
        self.courses = load_json(COURSES_FILE)
        self.rounds = load_json(ROUNDS_FILE)

        index = self.calculate_handicap_index()
        best = self.get_best_round()

        self.handicap_label.config(text=f"Handicap Index: {index}")
        self.best_round_label.config(text=f"Best Round: {best}")
        self.total_rounds_label.config(text=f"Total Rounds: {len(self.rounds)}")

    def calculate_handicap_index(self):
        diffs = []
        for r in self.rounds:
            if r["holes_played"] != 18 or not r["is_serious"]:
                continue
            course = next((c for c in self.courses if c["name"] == r["course_name"]), None)
            if course:
                diff = (r["score"] - course["rating"]) * 113 / course["slope"]
                diffs.append(diff)

        if len(diffs) < 5:
            return "Need 5+ serious rounds"

        top_diffs = sorted(diffs)[:min(20, len(diffs))]
        return round(mean(top_diffs) * 0.96, 2)

    def get_best_round(self):
        serious_18 = [r for r in self.rounds if r["holes_played"] == 18 and r["is_serious"]]
        if not serious_18:
            return "No serious 18-hole rounds."
        best = min(serious_18, key=lambda x: x["score"])
        return f"{best['score']} on {best['course_name']}"

# Run the app
if __name__ == "__main__":
    os.makedirs("data", exist_ok=True)
    root = tk.Tk()
    app = GolfApp(root)
    root.mainloop()