import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from Backend import GolfBackend, save_json, ROUNDS_FILE


class GolfApp:
    def __init__(self, root):
        self.backend = GolfBackend()
        self.root = root
        root.title("Golf Handicap Tracker")
        root.geometry("400x500")

        # Style configuration
        style = ttk.Style()
        style.configure("Title.TLabel", font=("Helvetica", 16, "bold"))
        style.configure("Header.TLabel", font=("Helvetica", 12, "bold"))

        # -- Main Menu --
        self.main_frame = ttk.Frame(root, padding=20)
        self.main_frame.pack(fill='both', expand=True)

        # Title
        ttk.Label(self.main_frame, text="⛳ Golf Tracker",
                  style="Title.TLabel").pack(pady=(0, 20))

        # -- Summary Panel (at top) --
        self.info_frame = ttk.LabelFrame(self.main_frame, text="Your Stats", padding=10)
        self.info_frame.pack(fill='x', pady=(0, 20))

        self.handicap_label = ttk.Label(self.info_frame, text="Handicap Index: N/A",
                                        font=("Helvetica", 14, "bold"))
        self.handicap_label.pack(anchor='w')

        self.best_round_label = ttk.Label(self.info_frame, text="Best Round: N/A")
        self.best_round_label.pack(anchor='w')

        self.total_rounds_label = ttk.Label(self.info_frame, text="Total Rounds: 0")
        self.total_rounds_label.pack(anchor='w')

        self.eligible_label = ttk.Label(self.info_frame, text="Handicap Eligible: 0")
        self.eligible_label.pack(anchor='w')

        # -- Button Panel --
        btn_frame = ttk.Frame(self.main_frame)
        btn_frame.pack(fill='x')

        buttons = [
            ("🏌️ Log a Round", self.open_log_round_page),
            ("📋 View Scorecards", self.open_scorecards_page),
            ("🏌️ Manage Courses", self.open_manage_courses),
            ("➕ Add New Course", lambda: self.open_course_window()),
            ("🏌️ Club Distances", self.open_club_distances),
            ("📊 Statistics", self.open_statistics),
        ]

        for text, cmd in buttons:
            ttk.Button(btn_frame, text=text, command=cmd, width=30).pack(pady=3)

        self.refresh_summary()

    # -------------------
    # Summary / Refresh
    # -------------------
    def refresh_summary(self):
        stats = self.backend.get_statistics()
        self.total_rounds_label.config(
            text=f"Total Rounds: {stats['total_rounds']}")

        # Show handicap eligible info
        eligible_18 = stats.get('handicap_eligible_18', 0)
        eligible_9 = stats.get('handicap_eligible_9', 0)
        total_holes = stats.get('total_holes_played', 0)

        idx = self.backend.calculate_handicap_index()
        if idx is not None:
            self.eligible_label.config(
                text=f"Eligible: {eligible_18}×18 + {eligible_9}×9 holes")
        else:
            # Need 54 holes to establish
            remaining = max(0, 54 - total_holes)
            if remaining > 0:
                self.eligible_label.config(
                    text=f"Need {remaining} more holes (have {total_holes}/54)")
            else:
                self.eligible_label.config(
                    text=f"Eligible: {eligible_18}×18 + {eligible_9}×9 holes")

        best = self.backend.get_best_round()
        if best:
            diff = best['total_score'] - best.get('par', 72)
            diff_str = f"+{diff}" if diff > 0 else str(diff)
            holes = best.get('holes_played', 18)
            text = f"{best['total_score']} ({diff_str}) at {best['course_name']} ({holes}h)"
        else:
            text = "N/A"
        self.best_round_label.config(text=f"Best Round: {text}")

        if idx is not None:
            idx_text = f"{idx:.1f}"
        else:
            idx_text = "Not established"
        self.handicap_label.config(text=f"Handicap Index: {idx_text}")

    # -------------------
    # Course Management
    # -------------------
    def open_manage_courses(self):
        win = tk.Toplevel(self.root)
        win.title("Manage Courses")
        win.geometry("500x400")

        # Group by club
        ttk.Label(win, text="Courses by Club", style="Header.TLabel").pack(pady=10)

        # Treeview
        cols = ("Club", "Course Name", "Holes", "Par")
        tree = ttk.Treeview(win, columns=cols, show="headings", height=12)
        for col in cols:
            tree.heading(col, text=col)
        tree.column("Club", width=120)
        tree.column("Course Name", width=180)
        tree.column("Holes", width=60, anchor='center')
        tree.column("Par", width=60, anchor='center')
        tree.pack(fill='both', expand=True, padx=10, pady=5)

        for c in sorted(self.backend.get_courses(), key=lambda x: (x.get("club", ""), x["name"])):
            tree.insert("", "end", values=(
                c.get("club", ""),
                c["name"],
                len(c["pars"]),
                sum(c["pars"])
            ))

        # Buttons
        btn_frame = ttk.Frame(win)
        btn_frame.pack(pady=10)

        def edit_selected():
            sel = tree.focus()
            if not sel:
                return messagebox.showwarning("Warning", "Select a course first")
            vals = tree.item(sel)["values"]
            course = self.backend.get_course_by_name(vals[1])
            win.destroy()
            self.open_course_window(course)

        def delete_selected():
            sel = tree.focus()
            if not sel:
                return messagebox.showwarning("Warning", "Select a course first")
            vals = tree.item(sel)["values"]
            if messagebox.askyesno("Confirm Delete",
                                   f"Delete '{vals[1]}'? This cannot be undone."):
                self.backend.delete_course(vals[1])
                tree.delete(sel)

        ttk.Button(btn_frame, text="Edit", command=edit_selected).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Delete", command=delete_selected).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Close", command=win.destroy).pack(side='left', padx=5)

    # -------------------
    # Add / Edit Course Flow
    # -------------------
    def open_course_window(self, course=None):
        self.editing_course = course
        self.original_name = course["name"] if course else None
        self.course_window = tk.Toplevel(self.root)
        self.course_window.title("Edit Course" if course else "Add New Course")

        frame = ttk.Frame(self.course_window, padding=20)
        frame.pack()

        # Club & Name
        ttk.Label(frame, text="Club Name:").grid(row=0, column=0, sticky='e', pady=5)
        self.club_entry = ttk.Entry(frame, width=30)
        self.club_entry.grid(row=0, column=1, pady=5)

        ttk.Label(frame, text="Course Name:").grid(row=1, column=0, sticky='e', pady=5)
        self.course_name_entry = ttk.Entry(frame, width=30)
        self.course_name_entry.grid(row=1, column=1, pady=5)

        if course:
            self.club_entry.insert(0, course.get("club", ""))
            self.course_name_entry.insert(0, course["name"])

        ttk.Button(frame, text="Next →", command=self.ask_hole_count).grid(
            row=2, column=0, columnspan=2, pady=15)

    def ask_hole_count(self):
        self.course_club = self.club_entry.get().strip()
        self.course_name = self.course_name_entry.get().strip()
        if not self.course_club:
            return messagebox.showerror("Error", "Club name cannot be empty.")
        if not self.course_name:
            return messagebox.showerror("Error", "Course name cannot be empty.")

        for w in self.course_window.winfo_children():
            w.destroy()

        frame = ttk.Frame(self.course_window, padding=20)
        frame.pack()

        ttk.Label(frame, text="Number of Holes", style="Header.TLabel").pack(pady=10)

        self.hole_count_var = tk.IntVar(
            value=len(self.editing_course["pars"]) if self.editing_course else 18)

        ttk.Radiobutton(frame, text="9 Holes", variable=self.hole_count_var,
                        value=9).pack(anchor='w')
        ttk.Radiobutton(frame, text="18 Holes", variable=self.hole_count_var,
                        value=18).pack(anchor='w')

        ttk.Button(frame, text="Next →", command=self.ask_pars).pack(pady=15)

    def ask_pars(self):
        self.num_holes = self.hole_count_var.get()
        for w in self.course_window.winfo_children():
            w.destroy()

        # Create scrollable frame for pars
        canvas = tk.Canvas(self.course_window, height=400)
        scrollbar = ttk.Scrollbar(self.course_window, orient="vertical",
                                  command=canvas.yview)
        frame = ttk.Frame(canvas, padding=10)

        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        canvas.create_window((0, 0), window=frame, anchor="nw")

        ttk.Label(frame, text="Set Par for Each Hole", style="Header.TLabel").grid(
            row=0, column=0, columnspan=4, pady=10)

        self.par_vars = []
        existing_pars = self.editing_course["pars"] if self.editing_course else []

        for i in range(self.num_holes):
            ttk.Label(frame, text=f"Hole {i+1}:").grid(row=i+1, column=0, padx=5)
            var = tk.IntVar(value=existing_pars[i] if i < len(existing_pars) else 4)
            self.par_vars.append(var)
            for j, val in enumerate((3, 4, 5)):
                ttk.Radiobutton(frame, text=str(val), variable=var,
                                value=val).grid(row=i+1, column=j+1)

        ttk.Button(frame, text="Next →", command=self.ask_tee_count).grid(
            row=self.num_holes+2, column=0, columnspan=4, pady=15)

        frame.update_idletasks()
        canvas.config(scrollregion=canvas.bbox("all"))

    def ask_tee_count(self):
        for w in self.course_window.winfo_children():
            w.destroy()

        frame = ttk.Frame(self.course_window, padding=20)
        frame.pack()

        ttk.Label(frame, text="How many tee boxes?", style="Header.TLabel").pack(pady=10)

        existing_count = len(self.editing_course["tee_boxes"]) if self.editing_course else 4
        self.tee_count_var = tk.IntVar(value=existing_count)

        ttk.Spinbox(frame, from_=1, to=10, textvariable=self.tee_count_var,
                    width=5).pack(pady=10)

        ttk.Button(frame, text="Next →", command=self.ask_tee_boxes).pack(pady=10)

    def ask_tee_boxes(self):
        count = self.tee_count_var.get()
        for w in self.course_window.winfo_children():
            w.destroy()

        frame = ttk.Frame(self.course_window, padding=20)
        frame.pack()

        ttk.Label(frame, text="Tee Box Details", style="Header.TLabel").grid(
            row=0, column=0, columnspan=6, pady=10)

        # Headers
        for col, text in enumerate(["Tee Color", "Rating", "Slope"]):
            ttk.Label(frame, text=text, font=("Helvetica", 10, "bold")).grid(
                row=1, column=col*2, columnspan=2, padx=5)

        self.tee_entries = []
        existing_tb = self.editing_course["tee_boxes"] if self.editing_course else []

        common_colors = ["Black", "Blue", "White", "Gold", "Red"]

        for i in range(count):
            row = i + 2

            color_var = tk.StringVar()
            color_cb = ttk.Combobox(frame, textvariable=color_var, width=10,
                                    values=common_colors)
            color_cb.grid(row=row, column=0, columnspan=2, padx=5, pady=3)

            rate_e = ttk.Entry(frame, width=8)
            rate_e.grid(row=row, column=2, columnspan=2, padx=5, pady=3)

            slope_e = ttk.Entry(frame, width=8)
            slope_e.grid(row=row, column=4, columnspan=2, padx=5, pady=3)

            if i < len(existing_tb):
                color_var.set(existing_tb[i]["color"])
                rate_e.insert(0, existing_tb[i]["rating"])
                slope_e.insert(0, existing_tb[i]["slope"])
            elif i < len(common_colors):
                color_var.set(common_colors[i])

            self.tee_entries.append((color_cb, rate_e, slope_e))

        ttk.Button(frame, text="💾 Save Course", command=self.save_course).grid(
            row=count+3, column=0, columnspan=6, pady=20)

    def save_course(self):
        pars = [v.get() for v in self.par_vars]
        tees = []

        for color_cb, rate_e, slope_e in self.tee_entries:
            try:
                color = color_cb.get().strip()
                rating = float(rate_e.get())
                slope = int(slope_e.get())
                if not color:
                    raise ValueError("Color empty")
            except ValueError:
                return messagebox.showerror("Error",
                    "Each tee box needs: color, rating (decimal), slope (integer)")
            tees.append({"color": color, "rating": rating, "slope": slope})

        data = {
            "club": self.course_club,
            "name": self.course_name,
            "pars": pars,
            "tee_boxes": tees
        }

        if self.editing_course:
            self.backend.update_course(self.original_name, data)
            messagebox.showinfo("Success", "Course updated!")
        else:
            self.backend.add_course(data)
            messagebox.showinfo("Success", "Course added!")

        self.course_window.destroy()
        self.refresh_summary()

    # -------------------
    # Log Round Flow
    # -------------------
    def open_log_round_page(self):
        courses = self.backend.get_courses()
        if not courses:
            return messagebox.showwarning("No Courses",
                "Add a course first before logging rounds.")

        self.log_window = tk.Toplevel(self.root)
        self.log_window.title("Log a Round")

        frame = ttk.Frame(self.log_window, padding=20)
        frame.pack()

        ttk.Label(frame, text="Log New Round", style="Title.TLabel").grid(
            row=0, column=0, columnspan=2, pady=(0, 15))

        # Course selection
        ttk.Label(frame, text="Course:").grid(row=1, column=0, sticky='e', pady=5)
        names = [c["name"] for c in courses]
        self.course_var = tk.StringVar()
        self.course_menu = ttk.Combobox(frame, textvariable=self.course_var,
                                        values=names, state='readonly', width=25)
        self.course_menu.grid(row=1, column=1, pady=5)
        self.course_menu.bind("<<ComboboxSelected>>", self.update_course_info)

        # Tee box
        ttk.Label(frame, text="Tee Box:").grid(row=2, column=0, sticky='e', pady=5)
        self.tee_var = tk.StringVar()
        self.tee_menu = ttk.Combobox(frame, textvariable=self.tee_var,
                                     state='readonly', width=25)
        self.tee_menu.grid(row=2, column=1, pady=5)
        self.tee_menu.bind("<<ComboboxSelected>>", self.update_course_info)

        # Holes to play selection
        ttk.Label(frame, text="Holes to Play:").grid(row=3, column=0, sticky='e', pady=5)
        self.holes_choice_var = tk.StringVar(value="full_18")
        holes_frame = ttk.Frame(frame)
        holes_frame.grid(row=3, column=1, sticky='w')
        ttk.Radiobutton(holes_frame, text="Full 18", variable=self.holes_choice_var,
                        value="full_18", command=self.update_course_info).pack(side='left')
        ttk.Radiobutton(holes_frame, text="Front 9", variable=self.holes_choice_var,
                        value="front_9", command=self.update_course_info).pack(side='left', padx=5)
        ttk.Radiobutton(holes_frame, text="Back 9", variable=self.holes_choice_var,
                        value="back_9", command=self.update_course_info).pack(side='left')

        # Info labels
        self.course_handicap_label = ttk.Label(frame, text="Course Handicap: N/A")
        self.course_handicap_label.grid(row=4, column=0, columnspan=2, pady=2)

        self.target_score_label = ttk.Label(frame, text="Target Score: N/A")
        self.target_score_label.grid(row=5, column=0, columnspan=2, pady=2)

        ttk.Separator(frame, orient='horizontal').grid(
            row=6, column=0, columnspan=2, sticky='ew', pady=10)

        # Round type
        ttk.Label(frame, text="Round Type:").grid(row=7, column=0, sticky='e', pady=5)
        self.round_type_var = tk.StringVar(value="solo")
        type_frame = ttk.Frame(frame)
        type_frame.grid(row=7, column=1, sticky='w')
        ttk.Radiobutton(type_frame, text="Solo", variable=self.round_type_var,
                        value="solo").pack(side='left')
        ttk.Radiobutton(type_frame, text="Scramble", variable=self.round_type_var,
                        value="scramble").pack(side='left', padx=10)

        # Serious round
        self.is_serious_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(frame, text="Serious Round (counts toward handicap)",
                        variable=self.is_serious_var).grid(
            row=8, column=0, columnspan=2, pady=5)

        # Notes
        ttk.Label(frame, text="Notes:").grid(row=9, column=0, sticky='ne', pady=5)
        self.notes_entry = ttk.Entry(frame, width=30)
        self.notes_entry.grid(row=9, column=1, pady=5)

        # Next button
        ttk.Button(frame, text="Start Scoring →",
                   command=self.start_round_input).grid(
            row=10, column=0, columnspan=2, pady=20)

    def update_course_info(self, _=None):
        name = self.course_var.get()
        course = self.backend.get_course_by_name(name)
        if not course:
            return

        colors = [b["color"] for b in course["tee_boxes"]]
        self.tee_menu.config(values=colors)
        if self.tee_var.get() not in colors:
            self.tee_var.set(colors[0] if colors else "")

        tee_color = self.tee_var.get()
        if not tee_color:
            return

        box = next((b for b in course["tee_boxes"] if b["color"] == tee_color), None)
        if not box:
            return

        # Get holes choice
        holes_choice = getattr(self, 'holes_choice_var', None)
        if holes_choice:
            choice = holes_choice.get()
        else:
            choice = "full_18"

        # Calculate handicap based on holes
        full_ch = box.get("handicap", 0)
        par_sum = sum(course["pars"])

        if choice == "full_18":
            ch = full_ch
            par_display = par_sum
            ts = par_sum + (round(ch) if isinstance(ch, (int, float)) else 0)
        else:
            # 9-hole handicap is roughly half
            ch = round(full_ch / 2, 1) if isinstance(full_ch, (int, float)) else "N/A"
            # Calculate 9-hole par
            if choice == "front_9":
                par_display = sum(course["pars"][:9])
            else:  # back_9
                par_display = sum(course["pars"][9:]) if len(course["pars"]) > 9 else sum(course["pars"][:9])
            ts = par_display + (round(ch) if isinstance(ch, (int, float)) else 0)

        self.course_handicap_label.config(text=f"Course Handicap: {ch}")
        self.target_score_label.config(text=f"Target Score: {ts} (Par {par_display})")

    def start_round_input(self):
        course_name = self.course_var.get()
        tee_color = self.tee_var.get()
        if not course_name or not tee_color:
            return messagebox.showerror("Error", "Select both course and tee box.")

        self.selected_course = self.backend.get_course_by_name(course_name)
        self.selected_tee = tee_color
        self.is_serious = self.is_serious_var.get()
        self.round_type = self.round_type_var.get()
        self.notes = self.notes_entry.get().strip()
        self.holes_choice = self.holes_choice_var.get()

        # Determine which holes to score
        all_pars = self.selected_course["pars"]
        if self.holes_choice == "full_18":
            self.holes_to_score = list(range(len(all_pars)))
            self.hole_offset = 0
        elif self.holes_choice == "front_9":
            self.holes_to_score = list(range(min(9, len(all_pars))))
            self.hole_offset = 0
        else:  # back_9
            if len(all_pars) >= 18:
                self.holes_to_score = list(range(9, 18))
                self.hole_offset = 9
            else:
                # If course is only 9 holes, back 9 = same as front 9
                self.holes_to_score = list(range(len(all_pars)))
                self.hole_offset = 0

        for w in self.log_window.winfo_children():
            w.destroy()

        hole_count = len(self.holes_to_score)
        par_total = sum(all_pars[i] for i in self.holes_to_score)

        # Determine display text
        if self.holes_choice == "front_9":
            holes_text = "Front 9"
        elif self.holes_choice == "back_9":
            holes_text = "Back 9"
        else:
            holes_text = f"{hole_count} Holes"

        # Create scrollable frame
        canvas = tk.Canvas(self.log_window, height=450, width=350)
        scrollbar = ttk.Scrollbar(self.log_window, orient="vertical",
                                  command=canvas.yview)
        frame = ttk.Frame(canvas, padding=15)

        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        canvas.create_window((0, 0), window=frame, anchor="nw")

        ttk.Label(frame, text=f"{self.selected_course['name']}",
                  style="Header.TLabel").grid(row=0, column=0, columnspan=3)
        ttk.Label(frame, text=f"{holes_text} • Par {par_total} • {tee_color} Tees").grid(
            row=1, column=0, columnspan=3, pady=(0, 10))

        # Running total
        self.running_total_var = tk.StringVar(value="Total: 0")
        ttk.Label(frame, textvariable=self.running_total_var,
                  font=("Helvetica", 12, "bold")).grid(row=2, column=0, columnspan=3)

        self.score_entries = []
        self.score_vars = []

        for idx, hole_num in enumerate(self.holes_to_score):
            row = idx + 3
            par = all_pars[hole_num]
            display_hole = hole_num + 1  # 1-indexed for display

            ttk.Label(frame, text=f"Hole {display_hole}").grid(row=row, column=0, sticky='e', padx=5)
            ttk.Label(frame, text=f"(Par {par})").grid(row=row, column=1)

            var = tk.StringVar()
            var.trace_add("write", lambda *args: self.update_running_total())
            self.score_vars.append(var)

            e = ttk.Entry(frame, width=5, textvariable=var)
            e.grid(row=row, column=2, padx=5, pady=2)
            self.score_entries.append(e)

        ttk.Button(frame, text="✓ Submit Round", command=self.submit_round).grid(
            row=len(self.holes_to_score)+4, column=0, columnspan=3, pady=20)

        frame.update_idletasks()
        canvas.config(scrollregion=canvas.bbox("all"))

    def update_running_total(self):
        total = 0
        for var in self.score_vars:
            try:
                total += int(var.get())
            except ValueError:
                pass
        par = sum(self.selected_course["pars"][i] for i in self.holes_to_score)
        diff = total - par
        diff_str = f"+{diff}" if diff > 0 else str(diff)
        self.running_total_var.set(f"Total: {total} ({diff_str})")

    def submit_round(self):
        scores = []
        for e in self.score_entries:
            v = e.get().strip()
            if self.is_serious:
                try:
                    scores.append(int(v))
                except ValueError:
                    return messagebox.showerror("Error",
                        "All scores must be numbers for serious rounds.")
            else:
                if v.lower() == "skip" or v == "":
                    scores.append(None)
                else:
                    try:
                        scores.append(int(v))
                    except ValueError:
                        return messagebox.showerror("Error",
                            "Enter a number or leave blank to skip.")

        total = sum(s for s in scores if s is not None)
        par = sum(self.selected_course["pars"][i] for i in self.holes_to_score)
        holes_played = len(scores)

        # Determine if this is 9 or 18 holes for handicap purposes
        if self.holes_choice in ["front_9", "back_9"]:
            holes_played = 9
        else:
            holes_played = 18 if len(scores) >= 18 else len(scores)

        # Get tee box info
        box = next(b for b in self.selected_course["tee_boxes"]
                   if b["color"] == self.selected_tee)

        # For 9-hole rounds, we need to use 9-hole rating/slope
        # Approximation: 9-hole rating is roughly half of 18-hole rating
        if holes_played == 9:
            tee_rating = box["rating"] / 2
            tee_slope = box["slope"]  # Slope stays the same
        else:
            tee_rating = box["rating"]
            tee_slope = box["slope"]

        # Build full scores array with None for unplayed holes
        full_scores = [None] * len(self.selected_course["pars"])
        for idx, hole_num in enumerate(self.holes_to_score):
            full_scores[hole_num] = scores[idx]

        rd = {
            "course_name": self.selected_course["name"],
            "tee_color": self.selected_tee,
            "scores": full_scores,
            "is_serious": self.is_serious,
            "round_type": self.round_type,
            "notes": self.notes,
            "holes_played": holes_played,
            "holes_choice": self.holes_choice,
            "total_score": total,
            "par": par,
            "tee_rating": tee_rating,
            "tee_slope": tee_slope,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M")
        }

        # Calculate target score
        full_ch = box.get("handicap", 0)
        if holes_played == 9:
            ch = full_ch / 2
        else:
            ch = full_ch
        rd["target_score"] = par + round(ch)

        self.backend.rounds.append(rd)
        from Backend import save_json, ROUNDS_FILE
        save_json(ROUNDS_FILE, self.backend.rounds)

        self.log_window.destroy()
        self.show_debrief(rd)

    def show_debrief(self, rd):
        win = tk.Toplevel(self.root)
        win.title("Round Complete!")

        frame = ttk.Frame(win, padding=20)
        frame.pack()

        diff = rd['total_score'] - rd['par']
        diff_str = f"+{diff}" if diff > 0 else str(diff)

        ttk.Label(frame, text="🎉 Round Saved!", style="Title.TLabel").pack(pady=(0, 15))

        # Determine holes display
        holes_choice = rd.get('holes_choice', 'full_18')
        if holes_choice == 'front_9':
            holes_text = "Front 9"
        elif holes_choice == 'back_9':
            holes_text = "Back 9"
        else:
            holes_text = f"{rd['holes_played']} holes"

        info = [
            f"Course: {rd['course_name']}",
            f"Holes: {holes_text}",
            f"Score: {rd['total_score']} ({diff_str})",
            f"Target: {rd.get('target_score', 'N/A')}",
            f"Type: {rd['round_type'].title()}",
            f"Serious: {'Yes' if rd['is_serious'] else 'No'}"
        ]

        for line in info:
            ttk.Label(frame, text=line).pack(anchor='w')

        # Check if eligible for handicap
        if rd['is_serious'] and rd['round_type'] == 'solo':
            if rd['holes_played'] == 18:
                ttk.Label(frame, text="✓ Counts toward handicap!",
                          foreground='green').pack(pady=10)
            elif rd['holes_played'] == 9:
                # Check if they have an established handicap
                idx = self.backend.calculate_handicap_index()
                if idx is not None:
                    ttk.Label(frame, text="✓ 9-hole round - counts toward handicap!",
                              foreground='green').pack(pady=10)
                else:
                    total_holes = self.backend.get_total_holes_played()
                    remaining = 54 - total_holes
                    ttk.Label(frame,
                              text=f"📊 {remaining} more holes needed to establish handicap",
                              foreground='blue').pack(pady=10)

        ttk.Label(frame, text="Notes:").pack(anchor='w', pady=(10, 0))
        txt = tk.Text(frame, height=4, width=35)
        txt.insert("1.0", rd["notes"])
        txt.pack(pady=5)

        def save_and_close():
            rd["notes"] = txt.get("1.0", tk.END).strip()
            all_rounds = self.backend.get_rounds()
            if all_rounds and all_rounds[-1]["date"] == rd["date"]:
                all_rounds[-1] = rd
                save_json(ROUNDS_FILE, all_rounds)
            win.destroy()
            self.refresh_summary()

        ttk.Button(frame, text="Save & Close", command=save_and_close).pack(pady=10)

    # -------------------
    # Scorecards View
    # -------------------
    def open_scorecards_page(self):
        self.scorecards_window = tk.Toplevel(self.root)
        self.scorecards_window.title("Scorecards")
        self.scorecards_window.geometry("600x500")

        # Filter controls
        filter_frame = ttk.Frame(self.scorecards_window, padding=10)
        filter_frame.pack(fill='x')

        ttk.Label(filter_frame, text="Show:").pack(side='left')
        self.filter_type_var = tk.StringVar(value="all")
        for text, val in [("All", "all"), ("Solo", "solo"), ("Scramble", "scramble")]:
            ttk.Radiobutton(filter_frame, text=text, variable=self.filter_type_var,
                            value=val, command=self.populate_scorecards).pack(side='left', padx=5)

        ttk.Label(filter_frame, text="  Sort:").pack(side='left', padx=(20, 5))
        self.sort_var = tk.StringVar(value="recent")
        sort_cb = ttk.Combobox(filter_frame, textvariable=self.sort_var,
                               values=["recent", "best", "worst"], state='readonly', width=10)
        sort_cb.pack(side='left')
        sort_cb.bind("<<ComboboxSelected>>", lambda e: self.populate_scorecards())

        # Treeview
        cols = ("Date", "Course", "Score", "Par", "+/-", "Holes", "Type", "Serious")
        self.score_tree = ttk.Treeview(self.scorecards_window, columns=cols,
                                       show="headings", height=15)

        widths = [90, 130, 55, 45, 45, 45, 60, 55]
        for col, w in zip(cols, widths):
            self.score_tree.heading(col, text=col)
            self.score_tree.column(col, width=w, anchor='center')

        self.score_tree.pack(fill='both', expand=True, padx=10, pady=5)
        self.score_tree.bind("<Double-1>", self.on_scorecard_select)

        # Buttons
        btn_frame = ttk.Frame(self.scorecards_window)
        btn_frame.pack(pady=10)

        ttk.Button(btn_frame, text="View Details",
                   command=lambda: self.on_scorecard_select(None)).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Delete Round",
                   command=self.delete_selected_round).pack(side='left', padx=5)

        self.populate_scorecards()

    def populate_scorecards(self):
        for row in self.score_tree.get_children():
            self.score_tree.delete(row)

        rounds = self.backend.get_filtered_rounds(
            round_type=self.filter_type_var.get(),
            sort_by=self.sort_var.get()
        )

        for idx, rd in rounds:
            diff = rd["total_score"] - rd.get("par", 72)
            diff_str = f"+{diff}" if diff > 0 else str(diff)

            # Show holes info
            holes = rd.get("holes_played", 18)
            holes_choice = rd.get("holes_choice", "full_18")
            if holes_choice == "front_9":
                holes_str = "F9"
            elif holes_choice == "back_9":
                holes_str = "B9"
            else:
                holes_str = str(holes)

            vals = (
                rd.get("date", "N/A")[:10],
                rd["course_name"],
                rd["total_score"],
                rd.get("par", "N/A"),
                diff_str,
                holes_str,
                rd.get("round_type", "solo").title(),
                "Yes" if rd["is_serious"] else "No"
            )
            self.score_tree.insert("", "end", iid=str(idx), values=vals)

    def delete_selected_round(self):
        sel = self.score_tree.focus()
        if not sel:
            return messagebox.showwarning("Warning", "Select a round first")

        if messagebox.askyesno("Confirm Delete",
                               "Delete this round? This cannot be undone."):
            self.backend.delete_round(int(sel))
            self.populate_scorecards()
            self.refresh_summary()

    def on_scorecard_select(self, event):
        sel = self.score_tree.focus()
        if not sel:
            return

        rd = self.backend.get_rounds()[int(sel)]
        course = self.backend.get_course_by_name(rd["course_name"])

        win = tk.Toplevel(self.scorecards_window)
        win.title(f"Scorecard - {rd['course_name']}")

        frame = ttk.Frame(win, padding=20)
        frame.pack()

        diff = rd['total_score'] - rd.get('par', 72)
        diff_str = f"+{diff}" if diff > 0 else str(diff)

        # Header
        ttk.Label(frame, text=rd['course_name'], style="Title.TLabel").pack()
        ttk.Label(frame, text=f"{rd.get('date', 'N/A')}").pack()

        ttk.Label(frame, text=f"Score: {rd['total_score']} ({diff_str})",
                  font=("Helvetica", 14, "bold")).pack(pady=10)

        info_frame = ttk.Frame(frame)
        info_frame.pack()

        info = [
            f"Target: {rd.get('target_score', 'N/A')}",
            f"Tee: {rd.get('tee_color', 'N/A')}",
            f"Type: {rd.get('round_type', 'solo').title()}",
            f"Serious: {'Yes' if rd['is_serious'] else 'No'}"
        ]

        for i, line in enumerate(info):
            ttk.Label(info_frame, text=line).grid(row=i//2, column=i%2, padx=10, sticky='w')

        # Hole-by-hole table
        ttk.Label(frame, text="Hole-by-Hole", style="Header.TLabel").pack(pady=(15, 5))

        table_frame = ttk.Frame(frame)
        table_frame.pack()

        pars = course["pars"] if course else [4] * len(rd["scores"])

        # Front 9
        for i in range(min(9, len(rd["scores"]))):
            ttk.Label(table_frame, text=str(i+1), width=4,
                      relief='ridge').grid(row=0, column=i)
            ttk.Label(table_frame, text=str(pars[i]), width=4,
                      relief='ridge').grid(row=1, column=i)
            sc = rd["scores"][i]
            sc_text = str(sc) if sc is not None else "-"
            ttk.Label(table_frame, text=sc_text, width=4,
                      relief='ridge').grid(row=2, column=i)

        # Labels
        ttk.Label(table_frame, text="Hole").grid(row=0, column=9, padx=5)
        ttk.Label(table_frame, text="Par").grid(row=1, column=9, padx=5)
        ttk.Label(table_frame, text="Score").grid(row=2, column=9, padx=5)

        # Back 9 if applicable
        if len(rd["scores"]) > 9:
            for i in range(9, len(rd["scores"])):
                col = i - 9
                ttk.Label(table_frame, text=str(i+1), width=4,
                          relief='ridge').grid(row=3, column=col)
                ttk.Label(table_frame, text=str(pars[i]), width=4,
                          relief='ridge').grid(row=4, column=col)
                sc = rd["scores"][i]
                sc_text = str(sc) if sc is not None else "-"
                ttk.Label(table_frame, text=sc_text, width=4,
                          relief='ridge').grid(row=5, column=col)

        # Notes
        if rd.get("notes"):
            ttk.Label(frame, text="Notes:", style="Header.TLabel").pack(pady=(15, 5))
            ttk.Label(frame, text=rd["notes"], wraplength=300).pack()

        ttk.Button(frame, text="Close", command=win.destroy).pack(pady=15)

    # -------------------
    # Club Distances
    # -------------------
    def open_club_distances(self):
        self.clubs_window = tk.Toplevel(self.root)
        self.clubs_window.title("Club Distance Mapper")
        self.clubs_window.geometry("400x500")

        frame = ttk.Frame(self.clubs_window, padding=15)
        frame.pack(fill='both', expand=True)

        ttk.Label(frame, text="🏌️ Club Distances", style="Title.TLabel").pack(pady=(0, 15))

        # Add club section
        add_frame = ttk.LabelFrame(frame, text="Add/Update Club", padding=10)
        add_frame.pack(fill='x', pady=(0, 15))

        ttk.Label(add_frame, text="Club:").grid(row=0, column=0, sticky='e', padx=5)
        self.club_name_var = tk.StringVar()
        club_cb = ttk.Combobox(add_frame, textvariable=self.club_name_var, width=15,
                               values=["Driver", "3 Wood", "5 Wood", "Hybrid",
                                       "3 Iron", "4 Iron", "5 Iron", "6 Iron",
                                       "7 Iron", "8 Iron", "9 Iron", "PW", "GW",
                                       "SW", "LW", "Putter"])
        club_cb.grid(row=0, column=1, pady=3)

        ttk.Label(add_frame, text="Distance (yds):").grid(row=1, column=0, sticky='e', padx=5)
        self.club_dist_var = tk.StringVar()
        ttk.Entry(add_frame, textvariable=self.club_dist_var, width=10).grid(
            row=1, column=1, sticky='w', pady=3)

        ttk.Label(add_frame, text="Notes:").grid(row=2, column=0, sticky='e', padx=5)
        self.club_notes_var = tk.StringVar()
        ttk.Entry(add_frame, textvariable=self.club_notes_var, width=20).grid(
            row=2, column=1, pady=3)

        ttk.Button(add_frame, text="Save Club", command=self.save_club).grid(
            row=3, column=0, columnspan=2, pady=10)

        # Club list
        ttk.Label(frame, text="Your Clubs (longest → shortest)",
                  style="Header.TLabel").pack(anchor='w')

        cols = ("Club", "Distance", "Notes")
        self.clubs_tree = ttk.Treeview(frame, columns=cols, show="headings", height=12)
        for col in cols:
            self.clubs_tree.heading(col, text=col)
        self.clubs_tree.column("Club", width=100)
        self.clubs_tree.column("Distance", width=80, anchor='center')
        self.clubs_tree.column("Notes", width=150)
        self.clubs_tree.pack(fill='both', expand=True, pady=10)

        self.clubs_tree.bind("<Double-1>", self.on_club_select)

        # Delete button
        ttk.Button(frame, text="Delete Selected", command=self.delete_club).pack()

        self.populate_clubs()

    def populate_clubs(self):
        for row in self.clubs_tree.get_children():
            self.clubs_tree.delete(row)

        for club in self.backend.get_clubs_sorted_by_distance():
            self.clubs_tree.insert("", "end", values=(
                club["name"],
                f"{club['distance']} yds",
                club.get("notes", "")
            ))

    def on_club_select(self, event):
        sel = self.clubs_tree.focus()
        if not sel:
            return
        vals = self.clubs_tree.item(sel)["values"]
        self.club_name_var.set(vals[0])
        self.club_dist_var.set(vals[1].replace(" yds", ""))
        self.club_notes_var.set(vals[2] if len(vals) > 2 else "")

    def save_club(self):
        name = self.club_name_var.get().strip()
        try:
            distance = int(self.club_dist_var.get())
        except ValueError:
            return messagebox.showerror("Error", "Distance must be a number")

        if not name:
            return messagebox.showerror("Error", "Enter a club name")

        notes = self.club_notes_var.get().strip()

        club_data = {"name": name, "distance": distance, "notes": notes}

        # Check if updating existing
        existing = next((c for c in self.backend.get_clubs()
                         if c["name"].lower() == name.lower()), None)
        if existing:
            self.backend.update_club(existing["name"], club_data)
        else:
            self.backend.add_club(club_data)

        self.populate_clubs()
        self.club_name_var.set("")
        self.club_dist_var.set("")
        self.club_notes_var.set("")

    def delete_club(self):
        sel = self.clubs_tree.focus()
        if not sel:
            return messagebox.showwarning("Warning", "Select a club first")

        vals = self.clubs_tree.item(sel)["values"]
        if messagebox.askyesno("Confirm", f"Delete {vals[0]}?"):
            self.backend.delete_club(vals[0])
            self.populate_clubs()

    # -------------------
    # Statistics
    # -------------------
    def open_statistics(self):
        win = tk.Toplevel(self.root)
        win.title("Statistics")
        win.geometry("450x550")

        frame = ttk.Frame(win, padding=20)
        frame.pack(fill='both', expand=True)

        ttk.Label(frame, text="📊 Your Statistics", style="Title.TLabel").pack(pady=(0, 20))

        stats = self.backend.get_statistics()
        idx = self.backend.calculate_handicap_index()

        # Main stats
        stats_frame = ttk.LabelFrame(frame, text="Overview", padding=10)
        stats_frame.pack(fill='x', pady=(0, 15))

        stat_lines = [
            ("Handicap Index:", f"{idx:.1f}" if idx else "Not established"),
            ("Total Rounds:", stats["total_rounds"]),
            ("18-Hole Rounds:", stats["rounds_18"]),
            ("9-Hole Rounds:", stats["rounds_9"]),
            ("Solo Rounds:", stats["solo_rounds"]),
            ("Scramble Rounds:", stats["scramble_rounds"]),
            ("Avg Score (18h):", stats["avg_score_18"] or "N/A"),
            ("Avg Score (9h):", stats.get("avg_score_9") or "N/A"),
            ("Total Holes Played:", stats.get("total_holes_played", 0)),
        ]

        for i, (label, value) in enumerate(stat_lines):
            ttk.Label(stats_frame, text=label).grid(row=i, column=0, sticky='e', padx=5)
            ttk.Label(stats_frame, text=str(value), font=("Helvetica", 10, "bold")).grid(
                row=i, column=1, sticky='w', padx=5)

        # 9-hole handicap note
        if idx is None:
            total_holes = stats.get("total_holes_played", 0)
            remaining = max(0, 54 - total_holes)
            if remaining > 0:
                note_frame = ttk.Frame(frame)
                note_frame.pack(fill='x', pady=5)
                ttk.Label(note_frame,
                          text=f"ℹ️ Play {remaining} more holes to establish handicap",
                          foreground='blue').pack()
                ttk.Label(note_frame,
                          text="(You can use any mix of 9 and 18 hole rounds)",
                          font=("Helvetica", 9)).pack()

        # Score differentials
        diffs = self.backend.get_score_differentials()
        if diffs:
            diff_frame = ttk.LabelFrame(frame, text="Score Differentials (Best First)", padding=10)
            diff_frame.pack(fill='both', expand=True)

            cols = ("Diff", "Score", "Holes", "Course")
            tree = ttk.Treeview(diff_frame, columns=cols, show="headings", height=8)
            for col in cols:
                tree.heading(col, text=col)
            tree.column("Diff", width=55, anchor='center')
            tree.column("Score", width=55, anchor='center')
            tree.column("Holes", width=45, anchor='center')
            tree.column("Course", width=180)
            tree.pack(fill='both', expand=True)

            for d in diffs:
                tree.insert("", "end", values=(
                    d["diff"],
                    d["score"],
                    d.get("holes", 18),
                    d["course"]
                ))

        ttk.Button(frame, text="Close", command=win.destroy).pack(pady=10)


if __name__ == "__main__":
    root = tk.Tk()
    app = GolfApp(root)
    root.mainloop()