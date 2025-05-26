import tkinter as tk
from tkinter import messagebox, ttk
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

        # Main UI
        self.main_frame = tk.Frame(root)
        self.main_frame.pack(padx=20, pady=20)

        tk.Button(self.main_frame, text="Add New Course", command=self.open_course_window, width=30).pack(pady=10)
        tk.Button(self.main_frame, text="Log a Round", command=self.open_log_round_page, width=30).pack(pady=10)

        self.info_frame = tk.LabelFrame(self.main_frame, text="Summary", padx=10, pady=10)
        self.info_frame.pack(pady=20)
        self.create_info_ui()

        self.refresh_summary()

    def create_info_ui(self):
        self.handicap_label = tk.Label(self.info_frame, text="Handicap Index: ")
        self.best_round_label = tk.Label(self.info_frame, text="Best Round: ")
        self.total_rounds_label = tk.Label(self.info_frame, text="Total Rounds: ")

        self.handicap_label.pack()
        self.best_round_label.pack()
        self.total_rounds_label.pack()

    def open_log_round_page(self):
        self.log_window = tk.Toplevel(self.root)
        self.log_window.title("Log a Round")

        tk.Label(self.log_window, text="Select Course").grid(row=0, column=0)
        self.course_names = [c["name"] for c in self.courses]
        self.course_var = tk.StringVar()
        self.course_menu = ttk.Combobox(self.log_window, textvariable=self.course_var, values=self.course_names, state='readonly')
        self.course_menu.grid(row=0, column=1)

        self.is_serious_var = tk.BooleanVar()
        tk.Checkbutton(self.log_window, text="Serious Round", variable=self.is_serious_var).grid(row=1, columnspan=2)

        tk.Label(self.log_window, text="Notes").grid(row=2, column=0)
        self.notes_entry = tk.Entry(self.log_window, width=40)
        self.notes_entry.grid(row=2, column=1)

        tk.Button(self.log_window, text="Next", command=self.start_round_input).grid(row=3, columnspan=2, pady=10)

    def start_round_input(self):
        course_name = self.course_var.get()
        if not course_name:
            messagebox.showerror("Error", "Please select a course.")
            return

        self.selected_course = next((c for c in self.courses if c["name"] == course_name), None)
        self.is_serious = self.is_serious_var.get()
        self.notes = self.notes_entry.get()
        self.hole_scores = []

        for widget in self.log_window.winfo_children():
            widget.destroy()

        tk.Label(self.log_window, text=f"Scoring for {self.selected_course['name']} ({len(self.selected_course['pars'])} Holes)").grid(row=0, column=0, columnspan=3)

        self.score_entries = []
        for i in range(len(self.selected_course['pars'])):
            tk.Label(self.log_window, text=f"Hole {i+1}").grid(row=i+1, column=0)
            e = tk.Entry(self.log_window)
            e.grid(row=i+1, column=1)
            self.score_entries.append(e)
            if not self.is_serious:
                tk.Label(self.log_window, text='(Enter number or "skip")').grid(row=i+1, column=2)

        tk.Button(self.log_window, text="Submit Round", command=self.submit_round).grid(row=len(self.selected_course['pars'])+1, columnspan=3, pady=10)

    def submit_round(self):
        scores = []
        for e in self.score_entries:
            val = e.get().strip()
            if self.is_serious:
                try:
                    scores.append(int(val))
                except:
                    messagebox.showerror("Error", "All scores must be numbers for serious rounds.")
                    return
            else:
                if val.lower() == "skip":
                    scores.append(None)
                else:
                    try:
                        scores.append(int(val))
                    except:
                        messagebox.showerror("Error", "Enter a number or 'skip' for non-serious rounds.")
                        return

        total = sum([s for s in scores if s is not None])
        course_handicap = self.selected_course.get("course_handicap", 0)
        par = sum(self.selected_course["pars"])
        target_score = par + round(course_handicap)

        round_data = {
            "course_name": self.selected_course["name"],
            "scores": scores,
            "is_serious": self.is_serious,
            "notes": self.notes,
            "holes_played": len(scores),
            "total_score": total,
            "target_score": target_score,  # NEW
        }

        self.rounds.append(round_data)
        save_json(ROUNDS_FILE, self.rounds)

        self.log_window.destroy()
        self.show_debrief(round_data)

    def show_debrief(self, round_data):
        self.debrief_window = tk.Toplevel(self.root)
        self.debrief_window.title("Round Debrief")

        tk.Label(self.debrief_window, text=f"Course: {round_data['course_name']}").pack()
        tk.Label(self.debrief_window, text=f"Total Score: {round_data['total_score']}").pack()
        tk.Label(self.debrief_window, text=f"Target Score: {round_data.get('target_score', 'N/A')}").pack()

        tk.Label(self.debrief_window, text="Notes").pack()
        self.debrief_notes = tk.Text(self.debrief_window, height=5, width=40)
        self.debrief_notes.insert(tk.END, round_data["notes"])
        self.debrief_notes.pack()

        tk.Button(self.debrief_window, text="Update Notes and Close", command=lambda: self.save_debrief(round_data)).pack(pady=10)

    def save_debrief(self, round_data):
        updated_note = self.debrief_notes.get("1.0", tk.END).strip()
        round_data["notes"] = updated_note
        save_json(ROUNDS_FILE, self.rounds)
        self.debrief_window.destroy()
        self.refresh_summary()

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

            var = tk.IntVar(value=4)
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

    def refresh_summary(self):
        self.handicap_index = self.calculate_handicap_index()

        if isinstance(self.handicap_index, (int, float)):
            handicap_text = f"Handicap Index: {self.handicap_index:.1f}"
        else:
            handicap_text = "Handicap Index: N/A"

        self.handicap_label.config(text=handicap_text)

        if self.rounds:
            serious_rounds = [r for r in self.rounds if r["is_serious"] and r["total_score"] is not None]
            best = min(serious_rounds, key=lambda r: r["total_score"], default=None)
            if best:
                self.best_round_label.config(text=f"Best Round: {best['total_score']} on {best['course_name']}")
            else:
                self.best_round_label.config(text="Best Round: N/A")
            self.total_rounds_label.config(text=f"Total Rounds: {len(self.rounds)}")
        else:
            self.best_round_label.config(text="Best Round: N/A")
            self.total_rounds_label.config(text="Total Rounds: 0")
    
    def update_course_handicaps(self):
        for course in self.courses:
            par = sum(course["pars"])
            course["course_handicap"] = round(self.handicap_index * (course["slope"] / 113) + (course["rating"] - par), 1)
        save_json(COURSES_FILE, self.courses)

    def calculate_handicap_index(self):
        differentials = []

        for rnd in self.rounds:
            if rnd.get("is_serious") and rnd.get("holes_played") == 18:
                course = next((c for c in self.courses if c["name"] == rnd["course_name"]), None)
                if course:
                    try:
                        score = rnd["total_score"]
                        rating = course["rating"]
                        slope = course["slope"]
                        differential = round((113 * (score - rating)) / slope, 1)
                        differentials.append(differential)
                    except Exception as e:
                        continue  # skip faulty data

        differentials.sort()
        num = len(differentials)

        # Table-based logic
        if num < 3:
            return "N/A"

        if num == 3:
            index = differentials[0] - 2.0
        elif num == 4:
            index = differentials[0] - 1.0
        elif num == 5:
            index = differentials[0]
        elif num == 6:
            index = mean(differentials[:2]) - 1.0
        elif num in [7, 8]:
            index = mean(differentials[:2])
        elif 9 <= num <= 11:
            index = mean(differentials[:3])
        elif 12 <= num <= 14:
            index = mean(differentials[:4])
        elif num in [15, 16]:
            index = mean(differentials[:5])
        elif num in [17, 18]:
            index = mean(differentials[:6])
        elif num == 19:
            index = mean(differentials[:7])
        else:
            index = mean(differentials[:8])

        return round(index, 1)

    def get_best_round(self):
        serious_18 = [r for r in self.rounds if r["holes_played"] == 18 and r["is_serious"]]
        if not serious_18:
            return "No serious 18-hole rounds."
        best = min(serious_18, key=lambda x: x["total_score"])
        return f"{best['total_score']} on {best['course_name']}"

if __name__ == "__main__":
    os.makedirs("data", exist_ok=True)
    root = tk.Tk()
    app = GolfApp(root)
    root.mainloop()