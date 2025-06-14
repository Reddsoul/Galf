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
                  command=lambda: self.open_course_window(), width=30
                 ).pack(pady=5)

        tk.Button(self.main_frame, text="Manage Courses",
                  command=self.open_manage_courses, width=30
                 ).pack(pady=5)

        tk.Button(self.main_frame, text="Log a Round",
                  command=self.open_log_round_page, width=30
                 ).pack(pady=5)
        
        tk.Button(self.main_frame, text="View Scorecards",
                  command=self.open_scorecards_page, width=30
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
    # Course Management
    # -------------------
    def open_manage_courses(self):
        win = tk.Toplevel(self.root)
        win.title("Manage Courses")
        cols = ("Club", "Name")
        tree = ttk.Treeview(win, columns=cols, show="headings")
        for col in cols:
            tree.heading(col, text=col)
            tree.column(col, width=150, anchor='center')
        tree.pack(fill='both', expand=True, padx=10, pady=10)
        for c in self.backend.get_courses():
            tree.insert("", "end", values=(c.get("club", ""), c["name"]))
        tree.bind("<Double-1>", lambda e: self.on_course_select(e, tree, win))

    def on_course_select(self, event, tree, parent):
        sel = tree.focus()
        if not sel:
            return
        club, name = tree.item(sel)["values"]
        course = self.backend.get_course_by_name(name)
        parent.destroy()
        self.open_course_window(course)

    # -------------------
    # Add / Edit Course Flow
    # -------------------
    def open_course_window(self, course=None):
        self.editing_course = course
        self.original_name = course["name"] if course else None
        self.course_window = tk.Toplevel(self.root)
        self.course_window.title("Edit Course" if course else "Add New Course")

        # Club & Name
        tk.Label(self.course_window, text="Club").grid(row=0, column=0)
        self.club_entry = tk.Entry(self.course_window)
        self.club_entry.grid(row=0, column=1)
        tk.Label(self.course_window, text="Course Name").grid(row=1, column=0)
        self.course_name_entry = tk.Entry(self.course_window)
        self.course_name_entry.grid(row=1, column=1)
        if course:
            self.club_entry.insert(0, course.get("club", ""))
            self.course_name_entry.insert(0, course["name"])

        # Next
        tk.Button(self.course_window, text="Next",
                  command=self.ask_hole_count
                 ).grid(row=2, columnspan=2, pady=10)

    def ask_hole_count(self):
        # Capture club and name
        self.course_club = self.club_entry.get().strip()
        self.course_name = self.course_name_entry.get().strip()
        if not self.course_club:
            return messagebox.showerror("Error", "Club cannot be empty.")
        if not self.course_name:
            return messagebox.showerror("Error", "Course name cannot be empty.")

        # Clear window
        for w in self.course_window.winfo_children():
            w.destroy()

        tk.Label(self.course_window, text="Number of Holes").pack(pady=5)
        self.hole_count_var = tk.IntVar(value=len(self.editing_course["pars"]) if self.editing_course else 9)
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
        existing_pars = self.editing_course["pars"] if self.editing_course else []
        for i in range(self.num_holes):
            tk.Label(self.course_window, text=f"Hole {i+1}").grid(row=i+1, column=0)
            var = tk.IntVar(value=existing_pars[i] if i < len(existing_pars) else 4)
            self.par_vars.append(var)
            for j, val in enumerate((3,4,5)):
                tk.Radiobutton(self.course_window, text=str(val),
                               variable=var, value=val).grid(row=i+1, column=j+1)
        
        tk.Button(self.course_window, text="Next",
                  command=self.ask_tee_count
                 ).grid(row=self.num_holes+2, columnspan=4, pady=10)

    def ask_tee_count(self):
        for w in self.course_window.winfo_children(): w.destroy()
        tk.Label(self.course_window, text="How many tee boxes?").pack(pady=5)
        existing_count = len(self.editing_course["tee_boxes"]) if self.editing_course else 3
        self.tee_count_var = tk.IntVar(value=existing_count)
        tk.Spinbox(self.course_window, from_=1, to=10,
                   textvariable=self.tee_count_var, width=5).pack()
        tk.Button(self.course_window, text="Next",
                  command=self.ask_tee_boxes
                 ).pack(pady=10)
        
    def ask_tee_boxes(self):
        count = self.tee_count_var.get()
        for w in self.course_window.winfo_children(): w.destroy()
        self.tee_entries = []
        existing_tb = self.editing_course["tee_boxes"] if self.editing_course else []
        for i in range(count):
            row = i
            tk.Label(self.course_window, text=f"Tee #{i+1} Color").grid(row=row, column=0)
            tk.Label(self.course_window, text="Rating").grid(row=row, column=2)
            tk.Label(self.course_window, text="Slope").grid(row=row, column=4)
            color_e = tk.Entry(self.course_window); color_e.grid(row=row, column=1)
            rate_e  = tk.Entry(self.course_window); rate_e.grid(row=row, column=3)
            slope_e = tk.Entry(self.course_window); slope_e.grid(row=row, column=5)
            if i < len(existing_tb):
                color_e.insert(0, existing_tb[i]["color"])
                rate_e.insert(0, existing_tb[i]["rating"])
                slope_e.insert(0, existing_tb[i]["slope"])
            self.tee_entries.append((color_e, rate_e, slope_e))

        tk.Button(self.course_window, text="Save Course",
                  command=self.save_course
                 ).grid(row=count+1, columnspan=6, pady=10)

    def save_course(self):
        pars = [v.get() for v in self.par_vars]
        tees = []
        for color_e, rate_e, slope_e in self.tee_entries:
            try:
                color = color_e.get().strip()
                rating = float(rate_e.get())
                slope  = int(slope_e.get())
            except ValueError:
                return messagebox.showerror("Error",
                    "Tee boxes need a color, float rating, integer slope.")
            tees.append({"color": color, "rating": rating, "slope": slope})

        data = {
            "club": self.course_club,
            "name": self.course_name,
            "pars": pars,
            "tee_boxes": tees
        }
        if self.editing_course:
            self.backend.update_course(self.original_name, data)
        else:
            self.backend.add_course(data)

        self.course_window.destroy()
        self.refresh_summary()

    # -------------------
    # Log Round Flow
    # -------------------

    def open_log_round_page(self):
        self.log_window = tk.Toplevel(self.root)
        self.log_window.title("Log a Round")

        # Select Course
        tk.Label(self.log_window, text="Select Course").grid(row=0, column=0, sticky='w')
        courses = self.backend.get_courses()
        names   = [c["name"] for c in courses]

        self.course_var  = tk.StringVar()
        self.course_menu = ttk.Combobox(self.log_window,
                                        textvariable=self.course_var,
                                        values=names,
                                        state='readonly')
        self.course_menu.grid(row=0, column=1, padx=5, pady=5)
        self.course_menu.bind("<<ComboboxSelected>>", self.update_course_info)

        # Select Tee Box (populated in update_course_info)
        tk.Label(self.log_window, text="Select Tee Box").grid(row=1, column=0, sticky='w')
        self.tee_var  = tk.StringVar()
        self.tee_menu = ttk.Combobox(self.log_window,
                                     textvariable=self.tee_var,
                                     state='readonly')
        self.tee_menu.grid(row=1, column=1, padx=5, pady=5)
        self.tee_menu.bind("<<ComboboxSelected>>", self.update_course_info)

        # Handicap & Target
        self.course_handicap_label = tk.Label(self.log_window, text="Course Handicap: N/A")
        self.course_handicap_label.grid(row=2, column=0, columnspan=2, sticky='w')
        self.target_score_label    = tk.Label(self.log_window, text="Target Score: N/A")
        self.target_score_label.grid(row=3, column=0, columnspan=2, sticky='w')

        # Serious Round?
        self.is_serious_var = tk.BooleanVar()
        tk.Checkbutton(self.log_window, text="Serious Round",
                       variable=self.is_serious_var
                      ).grid(row=4, column=0, columnspan=2, pady=5, sticky='w')

        # Notes
        tk.Label(self.log_window, text="Notes").grid(row=5, column=0, sticky='w')
        self.notes_entry = tk.Entry(self.log_window, width=40)
        self.notes_entry.grid(row=5, column=1, pady=5, sticky='w')

        # Next button
        tk.Button(self.log_window, text="Next",
                  command=self.start_round_input
                 ).grid(row=6, column=0, columnspan=2, pady=10)

    def update_course_info(self, _=None):
        name   = self.course_var.get()
        course = self.backend.get_course_by_name(name)
        if not course:
            return

        # Populate tee boxes
        colors = [b["color"] for b in course["tee_boxes"]]
        self.tee_menu.config(values=colors)
        if self.tee_var.get() not in colors:
            self.tee_var.set(colors[0])

        # Update labels based on selected tee
        box = next(b for b in course["tee_boxes"] if b["color"] == self.tee_var.get())
        ch = box.get("handicap", "N/A")
        par_sum = sum(course["pars"])
        ts = par_sum + (round(ch) if isinstance(ch, (int, float)) else 0)

        self.course_handicap_label.config(text=f"Course Handicap: {ch}")
        self.target_score_label.config(text=f"Target Score: {ts}")

    def start_round_input(self):
        course_name = self.course_var.get()
        tee_color   = self.tee_var.get()
        if not course_name or not tee_color:
            messagebox.showerror("Error", "Please select both course and tee box.")
            return

        self.selected_course = self.backend.get_course_by_name(course_name)
        self.selected_tee    = tee_color
        self.is_serious      = self.is_serious_var.get()
        self.notes           = self.notes_entry.get().strip()

        # Clear window
        for w in self.log_window.winfo_children():
            w.destroy()

        # Header
        hole_count = len(self.selected_course["pars"])
        tk.Label(self.log_window,
                 text=f"Scoring for {self.selected_course['name']} ({hole_count} Holes, Tee: {tee_color})"
                ).grid(row=0, column=0, columnspan=3, pady=5)

        # Score entries
        self.score_entries = []
        for i, par in enumerate(self.selected_course["pars"], start=1):
            tk.Label(self.log_window, text=f"Hole {i} (Par {par})")\
                .grid(row=i, column=0, sticky='e')
            e = tk.Entry(self.log_window, width=5)
            e.grid(row=i, column=1)
            self.score_entries.append(e)
            if not self.is_serious:
                tk.Label(self.log_window, text="(enter number or skip)")\
                  .grid(row=i, column=2, sticky='w')

        # Submit button
        tk.Button(self.log_window, text="Submit Round",
                  command=self.submit_round
                 ).grid(row=hole_count+1, column=0, columnspan=3, pady=10)
    def submit_round(self):
        # Gather scores
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
                if v.lower() == "skip" or v == "":
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
            "tee_color":   self.selected_tee,
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

    # -------------------
    # Score card view
    # -------------------

    def open_scorecards_page(self):
        """Open a window listing all saved rounds."""
        self.scorecards_window = tk.Toplevel(self.root)
        self.scorecards_window.title("Scorecards")

        cols = ("Course", "Score", "Target", "Serious")
        self.score_tree = ttk.Treeview(self.scorecards_window,
                                    columns=cols, show="headings")
        for col in cols:
            self.score_tree.heading(col, text=col)
            self.score_tree.column(col, width=100, anchor='center')
        self.score_tree.pack(fill='both', expand=True, padx=10, pady=10)

        self.populate_scorecards()
        self.score_tree.bind("<Double-1>", self.on_scorecard_select)


    def populate_scorecards(self):
        """Load all rounds into the Treeview."""
        for row in self.score_tree.get_children():
            self.score_tree.delete(row)
        for idx, rd in enumerate(self.backend.get_rounds()):
            vals = (
                rd["course_name"],
                rd["total_score"],
                rd.get("target_score", "N/A"),
                "Yes" if rd["is_serious"] else "No"
            )
            self.score_tree.insert("", "end", iid=str(idx), values=vals)


    def on_scorecard_select(self, event):
        """Show the details for the selected round."""
        sel = self.score_tree.focus()
        if not sel:
            return
        rd = self.backend.get_rounds()[int(sel)]

        win = tk.Toplevel(self.scorecards_window)
        win.title(f"Details – {rd['course_name']}")

        # Basic info
        info = [
            f"Course: {rd['course_name']}",
            f"Total Score: {rd['total_score']}",
            f"Target Score: {rd.get('target_score','N/A')}",
            f"Serious Round: {'Yes' if rd['is_serious'] else 'No'}"
        ]
        for line in info:
            tk.Label(win, text=line).pack(anchor='w', padx=10)

        # Hole-by-hole
        tk.Label(win, text="Hole-by-Hole:").pack(anchor='w', padx=10, pady=(10,0))
        for i, sc in enumerate(rd["scores"], start=1):
            txt = sc if sc is not None else "Skipped"
            tk.Label(win, text=f"  Hole {i}: {txt}").pack(anchor='w', padx=20)

        # Notes
        tk.Label(win, text="Notes:").pack(anchor='w', padx=10, pady=(10,0))
        txt = tk.Text(win, height=5, width=40)
        txt.insert("1.0", rd["notes"])
        txt.config(state='disabled')
        txt.pack(padx=10, pady=(0,10))

if __name__ == "__main__":
    root = tk.Tk()
    app = GolfApp(root)
    root.mainloop()