import tkinter as tk
from tkinter import ttk, messagebox
from Backend import GolfBackend

class GolfApp:
    def __init__(self, root):
        self.backend = GolfBackend()
        self.root = root
        root.title("Golf App")

        # -- Main Menu --
        self.main_frame = tk.Frame(root)
        self.main_frame.pack(padx=20, pady=20)

        tk.Button(self.main_frame, text="Add New Course",
                  command=self.open_course_window, width=30
                 ).pack(pady=5)

        tk.Button(self.main_frame, text="Log a Round",
                  command=self.open_log_round_page, width=30
                 ).pack(pady=5)

        # -- Summary Panel --
        self.info_frame = tk.LabelFrame(self.main_frame,
                                        text="Summary", padx=10, pady=10)
        self.info_frame.pack(pady=20)

        self.handicap_label    = tk.Label(self.info_frame, text="Handicap Index: N/A")
        self.best_round_label = tk.Label(self.info_frame, text="Best Round: N/A")
        self.total_rounds_label= tk.Label(self.info_frame, text="Total Rounds: 0")

        for lbl in (self.handicap_label, self.best_round_label, self.total_rounds_label):
            lbl.pack(anchor='w')

        self.refresh_summary()

    # -------------------
    # Summary / Refresh
    # -------------------

    def refresh_summary(self):
        rounds = self.backend.get_rounds()
        self.total_rounds_label.config(text=f"Total Rounds: {len(rounds)}")

        best = self.backend.get_best_round()
        if best:
            text = f"{best['total_score']} on {best['course_name']}"
        else:
            text = "N/A"
        self.best_round_label.config(text=f"Best Round: {text}")

        idx = self.backend.calculate_handicap_index()
        idx_text = f"{idx:.1f}" if isinstance(idx, float) else "N/A"
        self.handicap_label.config(text=f"Handicap Index: {idx_text}")

    # -------------------
    # Add Course Flow
    # -------------------

    def open_course_window(self):
        self.course_window = tk.Toplevel(self.root)
        self.course_window.title("Add New Course")

        tk.Label(self.course_window, text="Course Name").grid(row=0, column=0)
        tk.Label(self.course_window, text="Rating").grid(row=1, column=0)
        tk.Label(self.course_window, text="Slope").grid(row=2, column=0)

        self.course_name_entry   = tk.Entry(self.course_window)
        self.course_rating_entry = tk.Entry(self.course_window)
        self.course_slope_entry  = tk.Entry(self.course_window)

        self.course_name_entry.grid(row=0, column=1)
        self.course_rating_entry.grid(row=1, column=1)
        self.course_slope_entry.grid(row=2, column=1)

        tk.Button(self.course_window, text="Next",
                  command=self.ask_hole_count
                 ).grid(row=3, columnspan=2, pady=10)

    def ask_hole_count(self):
        try:
            self.course_name = self.course_name_entry.get().strip()
            self.course_rating = float(self.course_rating_entry.get())
            self.course_slope  = int(self.course_slope_entry.get())
        except ValueError:
            messagebox.showerror("Error", "Rating must be a float and slope an integer.")
            return

        for w in self.course_window.winfo_children():
            w.destroy()

        tk.Label(self.course_window, text="Number of Holes").pack(pady=5)
        self.hole_count_var = tk.IntVar(value=9)
        tk.Radiobutton(self.course_window, text="9 Holes",
                       variable=self.hole_count_var, value=9).pack()
        tk.Radiobutton(self.course_window, text="18 Holes",
                       variable=self.hole_count_var, value=18).pack()

        tk.Button(self.course_window, text="Next",
                  command=self.ask_pars
                 ).pack(pady=10)

    def ask_pars(self):
        self.num_holes = self.hole_count_var.get()
        for w in self.course_window.winfo_children():
            w.destroy()

        tk.Label(self.course_window, text="Select Par for Each Hole")\
            .grid(row=0, column=0, columnspan=4, pady=5)

        self.par_vars = []
        for i in range(self.num_holes):
            tk.Label(self.course_window, text=f"Hole {i+1}").grid(row=i+1, column=0)
            var = tk.IntVar(value=4)
            self.par_vars.append(var)
            for j, val in enumerate((3,4,5)):
                tk.Radiobutton(self.course_window, text=str(val),
                               variable=var, value=val).grid(row=i+1, column=j+1)

        tk.Button(self.course_window, text="Save Course",
                  command=self.save_course
                 ).grid(row=self.num_holes+1, columnspan=4, pady=10)

    def save_course(self):
        pars = [v.get() for v in self.par_vars]
        data = {
            "name":   self.course_name,
            "rating": self.course_rating,
            "slope":  self.course_slope,
            "pars":   pars
        }
        self.backend.add_course(data)
        self.course_window.destroy()
        self.refresh_summary()

    # -------------------
    # Log Round Flow
    # -------------------

    def open_log_round_page(self):
        self.log_window = tk.Toplevel(self.root)
        self.log_window.title("Log a Round")

        tk.Label(self.log_window, text="Select Course").grid(row=0, column=0)
        courses = self.backend.get_courses()
        names   = [c["name"] for c in courses]

        self.course_var  = tk.StringVar()
        self.course_menu = ttk.Combobox(self.log_window,
                                        textvariable=self.course_var,
                                        values=names,
                                        state='readonly')
        self.course_menu.grid(row=0, column=1, padx=5, pady=5)
        self.course_menu.bind("<<ComboboxSelected>>", self.update_course_info)

        self.course_handicap_label = tk.Label(self.log_window, text="Course Handicap: N/A")
        self.course_handicap_label.grid(row=1, column=0, columnspan=2, sticky='w')

        self.target_score_label    = tk.Label(self.log_window, text="Target Score: N/A")
        self.target_score_label.grid(row=2, column=0, columnspan=2, sticky='w')

        self.is_serious_var = tk.BooleanVar()
        tk.Checkbutton(self.log_window, text="Serious Round",
                       variable=self.is_serious_var
                      ).grid(row=3, columnspan=2, pady=5)

        tk.Label(self.log_window, text="Notes").grid(row=4, column=0)
        self.notes_entry = tk.Entry(self.log_window, width=40)
        self.notes_entry.grid(row=4, column=1, pady=5)

        tk.Button(self.log_window, text="Next",
                  command=self.start_round_input
                 ).grid(row=5, columnspan=2, pady=10)

    def update_course_info(self, _=None):
        name   = self.course_var.get()
        course = self.backend.get_course_by_name(name)
        if course:
            ch = course.get("course_handicap", "N/A")
            par_sum = sum(course["pars"])
            ts = par_sum + (round(ch) if isinstance(ch, (int,float)) else 0)
            self.course_handicap_label.config(text=f"Course Handicap: {ch}")
            self.target_score_label.config(text=f"Target Score: {ts}")
        else:
            self.course_handicap_label.config(text="Course Handicap: N/A")
            self.target_score_label.config(text="Target Score: N/A")

    def start_round_input(self):
        course_name = self.course_var.get()
        if not course_name:
            messagebox.showerror("Error", "Please select a course.")
            return

        self.selected_course = self.backend.get_course_by_name(course_name)
        self.is_serious     = self.is_serious_var.get()
        self.notes          = self.notes_entry.get().strip()

        # clear window
        for w in self.log_window.winfo_children():
            w.destroy()

        tk.Label(self.log_window,
                 text=f"Scoring for {self.selected_course['name']} "
                      f"({len(self.selected_course['pars'])} Holes)"
                ).grid(row=0, column=0, columnspan=3, pady=5)

        self.score_entries = []
        for i, par in enumerate(self.selected_course["pars"], start=1):
            tk.Label(self.log_window, text=f"Hole {i} (Par {par})")\
                .grid(row=i, column=0, sticky='e')
            e = tk.Entry(self.log_window, width=5)
            e.grid(row=i, column=1)
            self.score_entries.append(e)
            if not self.is_serious:
                tk.Label(self.log_window, text='(Enter number or skip)')\
                  .grid(row=i, column=2, sticky='w')

        tk.Button(self.log_window, text="Submit Round",
                  command=self.submit_round
                 ).grid(row=len(self.score_entries)+1, columnspan=3, pady=10)

    def submit_round(self):
        scores = []
        for e in self.score_entries:
            v = e.get().strip()
            if self.is_serious:
                try:
                    scores.append(int(v))
                except ValueError:
                    messagebox.showerror("Error", "All scores must be numbers for serious rounds.")
                    return
            else:
                if v.lower() == "skip":
                    scores.append(None)
                else:
                    try:
                        scores.append(int(v))
                    except ValueError:
                        messagebox.showerror("Error", "Enter a number or 'skip'.")
                        return

        total = sum(s for s in scores if s is not None)
        rd = {
            "course_name": self.selected_course["name"],
            "scores":      scores,
            "is_serious":  self.is_serious,
            "notes":       self.notes,
            "holes_played": len(scores),
            "total_score": total
        }
        self.backend.add_round(rd)
        self.log_window.destroy()
        self.show_debrief(rd)

    def show_debrief(self, rd):
        win = tk.Toplevel(self.root)
        win.title("Round Debrief")

        tk.Label(win, text=f"Course: {rd['course_name']}").pack(anchor='w')
        tk.Label(win, text=f"Total Score: {rd['total_score']}").pack(anchor='w')
        tk.Label(win, text=f"Target Score: {rd.get('target_score', 'N/A')}")\
          .pack(anchor='w')

        tk.Label(win, text="Notes:").pack(anchor='w')
        txt = tk.Text(win, height=5, width=40)
        txt.insert("1.0", rd["notes"])
        txt.pack(pady=5)

        tk.Button(win, text="Save & Close", 
                  command=lambda: self.save_debrief(win, txt, rd)
                 ).pack(pady=5)

    def save_debrief(self, window, text_widget, rd):
        rd["notes"] = text_widget.get("1.0", tk.END).strip()
        # backend already saved round on add, just overwrite file
        # so we reload, replace, and save:
        all_rounds = self.backend.get_rounds()
        for i, r in enumerate(all_rounds):
            if r is rd:
                all_rounds[i] = rd
                break
        from Backend import save_json, ROUNDS_FILE
        save_json(ROUNDS_FILE, all_rounds)

        window.destroy()
        self.refresh_summary()

if __name__ == "__main__":
    root = tk.Tk()
    app = GolfApp(root)
    root.mainloop()