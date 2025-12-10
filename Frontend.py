from datetime import datetime, date

from Backend import GolfBackend, save_json, ROUNDS_FILE, generate_scorecard_data

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from tkcalendar import DateEntry

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

from PIL import Image, ImageDraw, ImageFont


REPORTLAB_AVAILABLE = True
PIL_AVAILABLE = True


class GolfApp:
    def __init__(self, root):
        self.backend = GolfBackend()
        self.root = root
        root.title("Golf Handicap Tracker")
        root.geometry("400x550")

        style = ttk.Style()
        style.configure("Title.TLabel", font=("Helvetica", 16, "bold"))
        style.configure("Header.TLabel", font=("Helvetica", 12, "bold"))

        self.main_frame = ttk.Frame(root, padding=20)
        self.main_frame.pack(fill='both', expand=True)

        ttk.Label(self.main_frame, text="⛳ Golf Tracker",
                  style="Title.TLabel").pack(pady=(0, 20))

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

        btn_frame = ttk.Frame(self.main_frame)
        btn_frame.pack(fill='x')

        buttons = [
            ("🏌️ Log a Round", self.open_log_round_page),
            ("📋 View Scorecards", self.open_scorecards_page),
            ("🏌️ Manage Courses", self.open_manage_courses),
            ("➕ Add New Course", lambda: self.open_course_window()),
            ("🏌️ Club Distances", self.open_club_distances),
            ("📖 Rulebook", self.open_rulebook),
            ("📊 Statistics", self.open_statistics),
        ]

        for text, cmd in buttons:
            ttk.Button(btn_frame, text=text, command=cmd, width=30).pack(pady=3)

        self.refresh_summary()

    def refresh_summary(self):
        stats = self.backend.get_statistics()
        self.total_rounds_label.config(text=f"Total Rounds: {stats['total_rounds']}")

        eligible_18 = stats.get('handicap_eligible_18', 0)
        eligible_9 = stats.get('handicap_eligible_9', 0)
        total_holes = stats.get('total_holes_played', 0)

        idx = self.backend.calculate_handicap_index()
        if idx is not None:
            self.eligible_label.config(text=f"Eligible: {eligible_18}×18 + {eligible_9}×9 holes")
        else:
            remaining = max(0, 54 - total_holes)
            if remaining > 0:
                self.eligible_label.config(text=f"Need {remaining} more holes (have {total_holes}/54)")
            else:
                self.eligible_label.config(text=f"Eligible: {eligible_18}×18 + {eligible_9}×9 holes")

        best = self.backend.get_best_round()
        if best:
            diff = best['total_score'] - best.get('par', 72)
            diff_str = f"+{diff}" if diff > 0 else str(diff)
            holes = best.get('holes_played', 18)
            text = f"{best['total_score']} ({diff_str}) at {best['course_name']} ({holes}h)"
        else:
            text = "N/A"
        self.best_round_label.config(text=f"Best Round: {text}")

        idx_text = f"{idx:.1f}" if idx is not None else "Not established"
        self.handicap_label.config(text=f"Handicap Index: {idx_text}")

    def open_manage_courses(self):
        win = tk.Toplevel(self.root)
        win.title("Manage Courses")
        win.geometry("550x400")

        ttk.Label(win, text="Courses by Club", style="Header.TLabel").pack(pady=10)

        cols = ("Club", "Course Name", "Holes", "Par")
        tree = ttk.Treeview(win, columns=cols, show="headings", height=12)
        for col in cols:
            tree.heading(col, text=col)
        tree.column("Club", width=130)
        tree.column("Course Name", width=200)
        tree.column("Holes", width=60, anchor='center')
        tree.column("Par", width=60, anchor='center')
        tree.pack(fill='both', expand=True, padx=10, pady=5)

        for c in sorted(self.backend.get_courses(), key=lambda x: (x.get("club", ""), x["name"])):
            tree.insert("", "end", values=(c.get("club", ""), c["name"], len(c["pars"]), sum(c["pars"])))

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
            if messagebox.askyesno("Confirm Delete", f"Delete '{vals[1]}'? This cannot be undone."):
                self.backend.delete_course(vals[1])
                tree.delete(sel)

        ttk.Button(btn_frame, text="Edit", command=edit_selected).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Delete", command=delete_selected).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Close", command=win.destroy).pack(side='left', padx=5)

    def open_course_window(self, course=None):
        self.editing_course = course
        self.original_name = course["name"] if course else None
        self.course_window = tk.Toplevel(self.root)
        self.course_window.title("Edit Course" if course else "Add New Course")

        frame = ttk.Frame(self.course_window, padding=20)
        frame.pack()

        ttk.Label(frame, text="Club Name:").grid(row=0, column=0, sticky='e', pady=5)
        self.club_entry = ttk.Entry(frame, width=30)
        self.club_entry.grid(row=0, column=1, pady=5)

        ttk.Label(frame, text="Course Name:").grid(row=1, column=0, sticky='e', pady=5)
        self.course_name_entry = ttk.Entry(frame, width=30)
        self.course_name_entry.grid(row=1, column=1, pady=5)

        if course:
            self.club_entry.insert(0, course.get("club", ""))
            self.course_name_entry.insert(0, course["name"])

        ttk.Button(frame, text="Next →", command=self.ask_hole_count).grid(row=2, column=0, columnspan=2, pady=15)

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

        self.hole_count_var = tk.IntVar(value=len(self.editing_course["pars"]) if self.editing_course else 18)

        ttk.Radiobutton(frame, text="9 Holes", variable=self.hole_count_var, value=9).pack(anchor='w')
        ttk.Radiobutton(frame, text="18 Holes", variable=self.hole_count_var, value=18).pack(anchor='w')

        ttk.Button(frame, text="Next →", command=self.ask_pars).pack(pady=15)

    def ask_pars(self):
        self.num_holes = self.hole_count_var.get()
        for w in self.course_window.winfo_children():
            w.destroy()

        canvas = tk.Canvas(self.course_window, height=400)
        scrollbar = ttk.Scrollbar(self.course_window, orient="vertical", command=canvas.yview)
        frame = ttk.Frame(canvas, padding=10)

        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        canvas.create_window((0, 0), window=frame, anchor="nw")

        ttk.Label(frame, text="Set Par for Each Hole", style="Header.TLabel").grid(row=0, column=0, columnspan=4, pady=10)

        self.par_vars = []
        existing_pars = self.editing_course["pars"] if self.editing_course else []

        for i in range(self.num_holes):
            ttk.Label(frame, text=f"Hole {i+1}:").grid(row=i+1, column=0, padx=5)
            var = tk.IntVar(value=existing_pars[i] if i < len(existing_pars) else 4)
            self.par_vars.append(var)
            for j, val in enumerate((3, 4, 5)):
                ttk.Radiobutton(frame, text=str(val), variable=var, value=val).grid(row=i+1, column=j+1)

        ttk.Button(frame, text="Next →", command=self.ask_tee_count).grid(row=self.num_holes+2, column=0, columnspan=4, pady=15)

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

        ttk.Spinbox(frame, from_=1, to=10, textvariable=self.tee_count_var, width=5).pack(pady=10)
        ttk.Button(frame, text="Next →", command=self.ask_tee_boxes).pack(pady=10)

    def ask_tee_boxes(self):
        count = self.tee_count_var.get()
        for w in self.course_window.winfo_children():
            w.destroy()

        frame = ttk.Frame(self.course_window, padding=20)
        frame.pack()

        ttk.Label(frame, text="Tee Box Details", style="Header.TLabel").grid(row=0, column=0, columnspan=6, pady=10)

        for col, text in enumerate(["Tee Color", "Rating", "Slope"]):
            ttk.Label(frame, text=text, font=("Helvetica", 10, "bold")).grid(row=1, column=col*2, columnspan=2, padx=5)

        self.tee_entries = []
        existing_tb = self.editing_course["tee_boxes"] if self.editing_course else []
        common_colors = ["Black", "Blue", "White", "Gold", "Red"]

        for i in range(count):
            row = i + 2
            color_var = tk.StringVar()
            color_cb = ttk.Combobox(frame, textvariable=color_var, width=10, values=common_colors)
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

        ttk.Button(frame, text="Next → Yardages", command=self.ask_yardages).grid(row=count+3, column=0, columnspan=6, pady=20)

    def ask_yardages(self):
        self.temp_tees = []
        for color_cb, rate_e, slope_e in self.tee_entries:
            try:
                color = color_cb.get().strip()
                rating = float(rate_e.get())
                slope = int(slope_e.get())
                if not color:
                    raise ValueError("Color empty")
            except ValueError:
                return messagebox.showerror("Error", "Each tee box needs: color, rating (decimal), slope (integer)")
            self.temp_tees.append({"color": color, "rating": rating, "slope": slope})

        for w in self.course_window.winfo_children():
            w.destroy()

        self.course_window.geometry("600x500")
        main_frame = ttk.Frame(self.course_window, padding=10)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="Yardages per Hole (Optional)", style="Header.TLabel").pack(pady=5)
        ttk.Label(main_frame, text="Enter yardage for each hole per tee box. Leave blank to skip.", font=("Helvetica", 9)).pack()

        canvas = tk.Canvas(main_frame, height=350)
        scrollbar_y = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollbar_x = ttk.Scrollbar(main_frame, orient="horizontal", command=canvas.xview)
        frame = ttk.Frame(canvas, padding=10)

        canvas.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)
        scrollbar_y.pack(side="right", fill="y")
        scrollbar_x.pack(side="bottom", fill="x")
        canvas.pack(side="left", fill="both", expand=True)
        canvas.create_window((0, 0), window=frame, anchor="nw")

        ttk.Label(frame, text="Hole", font=("Helvetica", 10, "bold")).grid(row=0, column=0, padx=3)
        for i, tee in enumerate(self.temp_tees):
            ttk.Label(frame, text=tee["color"], font=("Helvetica", 10, "bold")).grid(row=0, column=i+1, padx=3)

        self.yardage_entries = {}
        existing_yardages = self.editing_course.get("yardages", {}) if self.editing_course else {}

        for tee in self.temp_tees:
            self.yardage_entries[tee["color"]] = []

        for hole in range(self.num_holes):
            ttk.Label(frame, text=f"{hole+1}").grid(row=hole+1, column=0, padx=3, pady=2)
            for i, tee in enumerate(self.temp_tees):
                e = ttk.Entry(frame, width=6)
                e.grid(row=hole+1, column=i+1, padx=3, pady=2)
                if tee["color"] in existing_yardages:
                    yards = existing_yardages[tee["color"]]
                    if hole < len(yards) and yards[hole]:
                        e.insert(0, str(yards[hole]))
                self.yardage_entries[tee["color"]].append(e)

        frame.update_idletasks()
        canvas.config(scrollregion=canvas.bbox("all"))

        ttk.Button(main_frame, text="💾 Save Course", command=self.save_course).pack(pady=15)

    def save_course(self):
        pars = [v.get() for v in self.par_vars]
        tees = self.temp_tees

        yardages = {}
        for tee_color, entries in self.yardage_entries.items():
            yards = []
            for e in entries:
                val = e.get().strip()
                yards.append(int(val) if val else 0)
            if any(y > 0 for y in yards):
                yardages[tee_color] = yards

        data = {"club": self.course_club, "name": self.course_name, "pars": pars, "tee_boxes": tees, "yardages": yardages}

        if self.editing_course:
            self.backend.update_course(self.original_name, data)
            messagebox.showinfo("Success", "Course updated!")
        else:
            self.backend.add_course(data)
            messagebox.showinfo("Success", "Course added!")

        self.course_window.destroy()
        self.refresh_summary()
    def open_log_round_page(self):
        courses = self.backend.get_courses()
        if not courses:
            return messagebox.showwarning("No Courses", "Add a course first before logging rounds.")

        self.log_window = tk.Toplevel(self.root)
        self.log_window.title("Log a Round")
        self.log_window.geometry("420x520")

        frame = ttk.Frame(self.log_window, padding=20)
        frame.pack(fill='both', expand=True)

        ttk.Label(frame, text="Log New Round", style="Title.TLabel").grid(row=0, column=0, columnspan=2, pady=(0, 15))

        ttk.Label(frame, text="Course:").grid(row=1, column=0, sticky='e', pady=5)
        names = [c["name"] for c in courses]
        self.course_var = tk.StringVar()
        self.course_menu = ttk.Combobox(frame, textvariable=self.course_var, values=names, state='readonly', width=25)
        self.course_menu.grid(row=1, column=1, pady=5)
        self.course_menu.bind("<<ComboboxSelected>>", self.update_course_info)

        ttk.Label(frame, text="Tee Box:").grid(row=2, column=0, sticky='e', pady=5)
        self.tee_var = tk.StringVar()
        self.tee_menu = ttk.Combobox(frame, textvariable=self.tee_var, state='readonly', width=25)
        self.tee_menu.grid(row=2, column=1, pady=5)
        self.tee_menu.bind("<<ComboboxSelected>>", self.update_course_info)

        ttk.Label(frame, text="Holes to Play:").grid(row=3, column=0, sticky='e', pady=5)
        self.holes_choice_var = tk.StringVar(value="full_18")
        holes_frame = ttk.Frame(frame)
        holes_frame.grid(row=3, column=1, sticky='w')
        ttk.Radiobutton(holes_frame, text="Full 18", variable=self.holes_choice_var, value="full_18", command=self.update_course_info).pack(side='left')
        ttk.Radiobutton(holes_frame, text="Front 9", variable=self.holes_choice_var, value="front_9", command=self.update_course_info).pack(side='left', padx=5)
        ttk.Radiobutton(holes_frame, text="Back 9", variable=self.holes_choice_var, value="back_9", command=self.update_course_info).pack(side='left')

        # DATE PICKER
        ttk.Label(frame, text="Date:").grid(row=4, column=0, sticky='e', pady=5)

        self.date_entry = DateEntry(frame, width=23, date_pattern='yyyy-mm-dd', maxdate=date.today())
        self.date_entry.grid(row=4, column=1, pady=5, sticky='w')


        self.course_handicap_label = ttk.Label(frame, text="Course Handicap: N/A")
        self.course_handicap_label.grid(row=5, column=0, columnspan=2, pady=2)

        self.target_score_label = ttk.Label(frame, text="Target Score: N/A")
        self.target_score_label.grid(row=6, column=0, columnspan=2, pady=2)

        self.yardage_label = ttk.Label(frame, text="Total Yardage: N/A")
        self.yardage_label.grid(row=7, column=0, columnspan=2, pady=2)

        ttk.Separator(frame, orient='horizontal').grid(row=8, column=0, columnspan=2, sticky='ew', pady=10)

        ttk.Label(frame, text="Round Type:").grid(row=9, column=0, sticky='e', pady=5)
        self.round_type_var = tk.StringVar(value="solo")
        type_frame = ttk.Frame(frame)
        type_frame.grid(row=9, column=1, sticky='w')
        ttk.Radiobutton(type_frame, text="Solo", variable=self.round_type_var, value="solo").pack(side='left')
        ttk.Radiobutton(type_frame, text="Scramble", variable=self.round_type_var, value="scramble").pack(side='left', padx=10)

        self.is_serious_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(frame, text="Serious Round (counts toward handicap)", variable=self.is_serious_var).grid(row=10, column=0, columnspan=2, pady=5)

        ttk.Label(frame, text="Notes:").grid(row=11, column=0, sticky='ne', pady=5)
        self.notes_entry = ttk.Entry(frame, width=30)
        self.notes_entry.grid(row=11, column=1, pady=5)

        ttk.Button(frame, text="Start Scoring →", command=self.start_round_input).grid(row=12, column=0, columnspan=2, pady=20)

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

        choice = self.holes_choice_var.get() if hasattr(self, 'holes_choice_var') else "full_18"
        full_ch = box.get("handicap", 0)
        par_sum = sum(course["pars"])

        if choice == "full_18":
            ch = full_ch
            par_display = par_sum
            ts = par_sum + (round(ch) if isinstance(ch, (int, float)) else 0)
        else:
            ch = round(full_ch / 2, 1) if isinstance(full_ch, (int, float)) else "N/A"
            par_display = sum(course["pars"][:9]) if choice == "front_9" else (sum(course["pars"][9:]) if len(course["pars"]) > 9 else sum(course["pars"][:9]))
            ts = par_display + (round(ch) if isinstance(ch, (int, float)) else 0)

        self.course_handicap_label.config(text=f"Course Handicap: {ch}")
        self.target_score_label.config(text=f"Target Score: {ts} (Par {par_display})")

        total_yardage = self.backend.get_course_total_yardage(name, tee_color, choice)
        self.yardage_label.config(text=f"Total Yardage: {total_yardage} yds" if total_yardage else "Total Yardage: N/A")

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
        self.selected_date = self.date_entry.get_date()

        all_pars = self.selected_course["pars"]
        if self.holes_choice == "full_18":
            self.holes_to_score = list(range(len(all_pars)))
        elif self.holes_choice == "front_9":
            self.holes_to_score = list(range(min(9, len(all_pars))))
        else:
            self.holes_to_score = list(range(9, 18)) if len(all_pars) >= 18 else list(range(len(all_pars)))

        for w in self.log_window.winfo_children():
            w.destroy()

        par_total = sum(all_pars[i] for i in self.holes_to_score)
        holes_text = "Front 9" if self.holes_choice == "front_9" else ("Back 9" if self.holes_choice == "back_9" else f"{len(self.holes_to_score)} Holes")
        yardages = self.selected_course.get("yardages", {}).get(tee_color, [])

        canvas = tk.Canvas(self.log_window, height=450, width=380)
        scrollbar = ttk.Scrollbar(self.log_window, orient="vertical", command=canvas.yview)
        frame = ttk.Frame(canvas, padding=15)

        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        canvas.create_window((0, 0), window=frame, anchor="nw")

        ttk.Label(frame, text=f"{self.selected_course['name']}", style="Header.TLabel").grid(row=0, column=0, columnspan=4)
        ttk.Label(frame, text=f"{holes_text} • Par {par_total} • {tee_color} Tees").grid(row=1, column=0, columnspan=4, pady=(0, 10))

        self.running_total_var = tk.StringVar(value="Total: 0")
        ttk.Label(frame, textvariable=self.running_total_var, font=("Helvetica", 12, "bold")).grid(row=2, column=0, columnspan=4)

        ttk.Label(frame, text="Hole", font=("Helvetica", 9, "bold")).grid(row=3, column=0)
        ttk.Label(frame, text="Yds", font=("Helvetica", 9, "bold")).grid(row=3, column=1)
        ttk.Label(frame, text="Par", font=("Helvetica", 9, "bold")).grid(row=3, column=2)
        ttk.Label(frame, text="Score", font=("Helvetica", 9, "bold")).grid(row=3, column=3)

        self.score_entries = []
        self.score_vars = []

        for idx, hole_num in enumerate(self.holes_to_score):
            row = idx + 4
            par = all_pars[hole_num]
            yard_text = str(yardages[hole_num]) if yardages and hole_num < len(yardages) and yardages[hole_num] > 0 else ""

            ttk.Label(frame, text=f"{hole_num+1}").grid(row=row, column=0, padx=5)
            ttk.Label(frame, text=yard_text).grid(row=row, column=1, padx=5)
            ttk.Label(frame, text=f"{par}").grid(row=row, column=2, padx=5)

            var = tk.StringVar()
            var.trace_add("write", lambda *args: self.update_running_total())
            self.score_vars.append(var)

            e = ttk.Entry(frame, width=5, textvariable=var)
            e.grid(row=row, column=3, padx=5, pady=2)
            self.score_entries.append(e)

        ttk.Button(frame, text="✓ Submit Round", command=self.submit_round).grid(row=len(self.holes_to_score)+5, column=0, columnspan=4, pady=20)

        frame.update_idletasks()
        canvas.config(scrollregion=canvas.bbox("all"))

    def update_running_total(self):
        total = sum(int(var.get()) for var in self.score_vars if var.get().isdigit())
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
                    return messagebox.showerror("Error", "All scores must be numbers for serious rounds.")
            else:
                scores.append(int(v) if v.isdigit() else None)

        total = sum(s for s in scores if s is not None)
        par = sum(self.selected_course["pars"][i] for i in self.holes_to_score)
        holes_played = 9 if self.holes_choice in ["front_9", "back_9"] else (18 if len(scores) >= 18 else len(scores))

        box = next(b for b in self.selected_course["tee_boxes"] if b["color"] == self.selected_tee)
        tee_rating = box["rating"] / 2 if holes_played == 9 else box["rating"]
        tee_slope = box["slope"]

        full_scores = [None] * len(self.selected_course["pars"])
        for idx, hole_num in enumerate(self.holes_to_score):
            full_scores[hole_num] = scores[idx]

        date_str = self.selected_date.strftime("%Y-%m-%d") + " " + datetime.now().strftime("%H:%M")

        rd = {
            "course_name": self.selected_course["name"], "tee_color": self.selected_tee, "scores": full_scores,
            "is_serious": self.is_serious, "round_type": self.round_type, "notes": self.notes,
            "holes_played": holes_played, "holes_choice": self.holes_choice, "total_score": total,
            "par": par, "tee_rating": tee_rating, "tee_slope": tee_slope, "date": date_str
        }

        full_ch = box.get("handicap", 0)
        rd["target_score"] = par + round(full_ch / 2 if holes_played == 9 else full_ch)

        self.backend.rounds.append(rd)
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

        holes_text = "Front 9" if rd.get('holes_choice') == 'front_9' else ("Back 9" if rd.get('holes_choice') == 'back_9' else f"{rd['holes_played']} holes")

        for line in [f"Course: {rd['course_name']}", f"Date: {rd.get('date', 'N/A')[:10]}", f"Holes: {holes_text}",
                     f"Score: {rd['total_score']} ({diff_str})", f"Target: {rd.get('target_score', 'N/A')}",
                     f"Type: {rd['round_type'].title()}", f"Serious: {'Yes' if rd['is_serious'] else 'No'}"]:
            ttk.Label(frame, text=line).pack(anchor='w')

        if rd['is_serious'] and rd['round_type'] == 'solo':
            if rd['holes_played'] == 18:
                ttk.Label(frame, text="✓ Counts toward handicap!", foreground='green').pack(pady=10)
            elif rd['holes_played'] == 9:
                idx = self.backend.calculate_handicap_index()
                if idx is not None:
                    ttk.Label(frame, text="✓ 9-hole round - counts toward handicap!", foreground='green').pack(pady=10)
                else:
                    remaining = 54 - self.backend.get_total_holes_played()
                    ttk.Label(frame, text=f"📊 {remaining} more holes needed to establish handicap", foreground='blue').pack(pady=10)

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
    def open_scorecards_page(self):
        self.scorecards_window = tk.Toplevel(self.root)
        self.scorecards_window.title("Scorecards")
        self.scorecards_window.geometry("650x500")

        filter_frame = ttk.Frame(self.scorecards_window, padding=10)
        filter_frame.pack(fill='x')

        ttk.Label(filter_frame, text="Show:").pack(side='left')
        self.filter_type_var = tk.StringVar(value="all")
        for text, val in [("All", "all"), ("Solo", "solo"), ("Scramble", "scramble")]:
            ttk.Radiobutton(filter_frame, text=text, variable=self.filter_type_var, value=val, command=self.populate_scorecards).pack(side='left', padx=5)

        ttk.Label(filter_frame, text="  Sort:").pack(side='left', padx=(20, 5))
        self.sort_var = tk.StringVar(value="recent")
        sort_cb = ttk.Combobox(filter_frame, textvariable=self.sort_var, values=["recent", "best", "worst"], state='readonly', width=10)
        sort_cb.pack(side='left')
        sort_cb.bind("<<ComboboxSelected>>", lambda e: self.populate_scorecards())

        cols = ("Date", "Course", "Score", "Par", "+/-", "Holes", "Type", "Serious")
        self.score_tree = ttk.Treeview(self.scorecards_window, columns=cols, show="headings", height=15)
        widths = [90, 140, 55, 45, 45, 45, 60, 55]
        for col, w in zip(cols, widths):
            self.score_tree.heading(col, text=col)
            self.score_tree.column(col, width=w, anchor='center')
        self.score_tree.pack(fill='both', expand=True, padx=10, pady=5)
        self.score_tree.bind("<Double-1>", self.on_scorecard_select)

        btn_frame = ttk.Frame(self.scorecards_window)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="View Details", command=lambda: self.on_scorecard_select(None)).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Export Scorecard", command=self.export_selected_scorecard).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Delete Round", command=self.delete_selected_round).pack(side='left', padx=5)

        self.populate_scorecards()

    def populate_scorecards(self):
        for row in self.score_tree.get_children():
            self.score_tree.delete(row)

        for idx, rd in self.backend.get_filtered_rounds(round_type=self.filter_type_var.get(), sort_by=self.sort_var.get()):
            diff = rd["total_score"] - rd.get("par", 72)
            diff_str = f"+{diff}" if diff > 0 else str(diff)
            holes_choice = rd.get("holes_choice", "full_18")
            holes_str = "F9" if holes_choice == "front_9" else ("B9" if holes_choice == "back_9" else str(rd.get("holes_played", 18)))
            vals = (rd.get("date", "N/A")[:10], rd["course_name"], rd["total_score"], rd.get("par", "N/A"), diff_str, holes_str, rd.get("round_type", "solo").title(), "Yes" if rd["is_serious"] else "No")
            self.score_tree.insert("", "end", iid=str(idx), values=vals)

    def delete_selected_round(self):
        sel = self.score_tree.focus()
        if not sel:
            return messagebox.showwarning("Warning", "Select a round first")
        if messagebox.askyesno("Confirm Delete", "Delete this round? This cannot be undone."):
            self.backend.delete_round(int(sel))
            self.populate_scorecards()
            self.refresh_summary()

    def export_selected_scorecard(self):
        sel = self.score_tree.focus()
        if not sel:
            return messagebox.showwarning("Warning", "Select a round first")
        rd = self.backend.get_rounds()[int(sel)]
        self.show_export_dialog(rd)

    def show_export_dialog(self, round_data):
        win = tk.Toplevel(self.scorecards_window if hasattr(self, 'scorecards_window') else self.root)
        win.title("Export Scorecard")
        win.geometry("300x200")

        frame = ttk.Frame(win, padding=20)
        frame.pack(fill='both', expand=True)

        ttk.Label(frame, text="Export Scorecard", style="Header.TLabel").pack(pady=(0, 15))

        export_format = tk.StringVar(value="pdf")
        ttk.Radiobutton(frame, text="PDF Document", variable=export_format, value="pdf").pack(anchor='w')
        ttk.Radiobutton(frame, text="PNG Image", variable=export_format, value="png").pack(anchor='w')

        def do_export():
            fmt = export_format.get()
            if fmt == "pdf":
                if not REPORTLAB_AVAILABLE:
                    messagebox.showerror("Error", "PDF export requires reportlab.\nInstall with: pip install reportlab")
                    return
                self.export_scorecard_pdf(round_data)
            else:
                if not PIL_AVAILABLE:
                    messagebox.showerror("Error", "Image export requires Pillow.\nInstall with: pip install Pillow")
                    return
                self.export_scorecard_image(round_data)
            win.destroy()

        ttk.Button(frame, text="Export", command=do_export).pack(pady=20)
        ttk.Button(frame, text="Cancel", command=win.destroy).pack()

    def export_scorecard_pdf(self, round_data):
        sc_data = generate_scorecard_data(self.backend, round_data)
        filepath = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF files", "*.pdf")],
            initialfile=f"scorecard_{sc_data['date'][:10]}_{sc_data['course_name'].replace(' ', '_')}.pdf")
        if not filepath:
            return

        try:
            doc = SimpleDocTemplate(filepath, pagesize=landscape(letter))
            styles = getSampleStyleSheet()
            story = []

            title_style = ParagraphStyle('Title', parent=styles['Title'], fontSize=18)
            story.append(Paragraph(f"Scorecard - {sc_data['course_name']}", title_style))
            story.append(Spacer(1, 12))

            info_text = f"<b>Date:</b> {sc_data['date'][:10]} | <b>Tee:</b> {sc_data['tee_color']} | <b>Score:</b> {sc_data['total_score']} ({sc_data['diff_str']}) | <b>Par:</b> {sc_data['par']}"
            story.append(Paragraph(info_text, styles['Normal']))
            story.append(Spacer(1, 20))

            front_9 = sc_data['front_9']
            if front_9['scores']:
                story.append(Paragraph("<b>Front 9</b>", styles['Heading2']))
                header = ['Hole'] + [str(i+1) for i in range(9)] + ['OUT']
                par_row = ['Par'] + [str(p) for p in front_9['pars']] + [str(front_9['par_total'])]
                score_row = ['Score'] + [str(s) if s else '-' for s in sc_data['scores'][:9]] + [str(front_9['score_total'])]
                rows = [header, par_row]
                if front_9['yardages'] and any(y > 0 for y in front_9['yardages']):
                    yard_row = ['Yards'] + [str(y) if y else '-' for y in front_9['yardages']] + [str(front_9['yards_total'])]
                    rows.append(yard_row)
                rows.append(score_row)

                table = Table(rows)
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.darkgreen), ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'), ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 10), ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                    ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey), ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ]))
                story.append(table)
                story.append(Spacer(1, 20))

            back_9 = sc_data['back_9']
            if back_9['scores'] and len(sc_data['scores']) > 9:
                story.append(Paragraph("<b>Back 9</b>", styles['Heading2']))
                header = ['Hole'] + [str(i+10) for i in range(9)] + ['IN']
                par_row = ['Par'] + [str(p) for p in back_9['pars']] + [str(back_9['par_total'])]
                score_row = ['Score'] + [str(s) if s else '-' for s in sc_data['scores'][9:18]] + [str(back_9['score_total'])]
                rows = [header, par_row]
                if back_9['yardages'] and any(y > 0 for y in back_9['yardages']):
                    yard_row = ['Yards'] + [str(y) if y else '-' for y in back_9['yardages']] + [str(back_9['yards_total'])]
                    rows.append(yard_row)
                rows.append(score_row)

                table = Table(rows)
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.darkgreen), ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'), ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 10), ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                    ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey), ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ]))
                story.append(table)
                story.append(Spacer(1, 20))

            story.append(Paragraph(f"<b>Total:</b> {sc_data['total_score']} | <b>Par:</b> {sc_data['par']} | <b>Diff:</b> {sc_data['diff_str']}", styles['Normal']))
            if sc_data['notes']:
                story.append(Spacer(1, 10))
                story.append(Paragraph(f"<b>Notes:</b> {sc_data['notes']}", styles['Normal']))

            doc.build(story)
            messagebox.showinfo("Success", f"Scorecard exported to:\n{filepath}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export PDF:\n{str(e)}")

    def export_scorecard_image(self, round_data):
        sc_data = generate_scorecard_data(self.backend, round_data)
        filepath = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG files", "*.png")],
            initialfile=f"scorecard_{sc_data['date'][:10]}_{sc_data['course_name'].replace(' ', '_')}.png")
        if not filepath:
            return

        try:
            width, height = 800, 500
            img = Image.new('RGB', (width, height), color='white')
            draw = ImageDraw.Draw(img)

            try:
                font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
                font_header = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 12)
                font_normal = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 11)
            except:
                font_title = font_header = font_normal = ImageFont.load_default()

            draw.text((20, 20), f"Scorecard - {sc_data['course_name']}", fill='darkgreen', font=font_title)
            draw.text((20, 55), f"Date: {sc_data['date'][:10]} | Tee: {sc_data['tee_color']} | Score: {sc_data['total_score']} ({sc_data['diff_str']})", fill='black', font=font_normal)

            y_start, cell_width, cell_height, x_start = 100, 55, 25, 20

            # Front 9 header
            draw.rectangle([x_start, y_start, x_start + cell_width, y_start + cell_height], fill='darkgreen', outline='black')
            draw.text((x_start + 5, y_start + 5), "Hole", fill='white', font=font_header)
            for i in range(min(9, len(sc_data['scores']))):
                x = x_start + (i + 1) * cell_width
                draw.rectangle([x, y_start, x + cell_width, y_start + cell_height], fill='darkgreen', outline='black')
                draw.text((x + 20, y_start + 5), str(i + 1), fill='white', font=font_header)
            x = x_start + 10 * cell_width
            draw.rectangle([x, y_start, x + cell_width, y_start + cell_height], fill='darkgreen', outline='black')
            draw.text((x + 10, y_start + 5), "OUT", fill='white', font=font_header)

            # Par row
            y = y_start + cell_height
            draw.rectangle([x_start, y, x_start + cell_width, y + cell_height], fill='lightgray', outline='black')
            draw.text((x_start + 10, y + 5), "Par", fill='black', font=font_normal)
            front_par_total = 0
            for i in range(min(9, len(sc_data['pars']))):
                x = x_start + (i + 1) * cell_width
                par = sc_data['pars'][i]
                front_par_total += par
                draw.rectangle([x, y, x + cell_width, y + cell_height], fill='white', outline='black')
                draw.text((x + 20, y + 5), str(par), fill='black', font=font_normal)
            x = x_start + 10 * cell_width
            draw.rectangle([x, y, x + cell_width, y + cell_height], fill='lightgray', outline='black')
            draw.text((x + 15, y + 5), str(front_par_total), fill='black', font=font_normal)

            # Score row
            y = y_start + 2 * cell_height
            draw.rectangle([x_start, y, x_start + cell_width, y + cell_height], fill='lightgray', outline='black')
            draw.text((x_start + 5, y + 5), "Score", fill='black', font=font_normal)
            front_score_total = 0
            for i in range(min(9, len(sc_data['scores']))):
                x = x_start + (i + 1) * cell_width
                score = sc_data['scores'][i]
                score_str = str(score) if score is not None else "-"
                if score:
                    front_score_total += score
                draw.rectangle([x, y, x + cell_width, y + cell_height], fill='white', outline='black')
                draw.text((x + 20, y + 5), score_str, fill='black', font=font_normal)
            x = x_start + 10 * cell_width
            draw.rectangle([x, y, x + cell_width, y + cell_height], fill='lightgray', outline='black')
            draw.text((x + 15, y + 5), str(front_score_total), fill='black', font=font_normal)

            # Back 9 if applicable
            if len(sc_data['scores']) > 9:
                y_back = y_start + 4 * cell_height
                draw.rectangle([x_start, y_back, x_start + cell_width, y_back + cell_height], fill='darkgreen', outline='black')
                draw.text((x_start + 5, y_back + 5), "Hole", fill='white', font=font_header)
                for i in range(9):
                    x = x_start + (i + 1) * cell_width
                    draw.rectangle([x, y_back, x + cell_width, y_back + cell_height], fill='darkgreen', outline='black')
                    draw.text((x + 15, y_back + 5), str(i + 10), fill='white', font=font_header)
                x = x_start + 10 * cell_width
                draw.rectangle([x, y_back, x + cell_width, y_back + cell_height], fill='darkgreen', outline='black')
                draw.text((x + 15, y_back + 5), "IN", fill='white', font=font_header)

                y = y_back + cell_height
                draw.rectangle([x_start, y, x_start + cell_width, y + cell_height], fill='lightgray', outline='black')
                draw.text((x_start + 10, y + 5), "Par", fill='black', font=font_normal)
                back_par_total = 0
                for i in range(min(9, len(sc_data['pars']) - 9)):
                    x = x_start + (i + 1) * cell_width
                    par = sc_data['pars'][i + 9]
                    back_par_total += par
                    draw.rectangle([x, y, x + cell_width, y + cell_height], fill='white', outline='black')
                    draw.text((x + 20, y + 5), str(par), fill='black', font=font_normal)
                x = x_start + 10 * cell_width
                draw.rectangle([x, y, x + cell_width, y + cell_height], fill='lightgray', outline='black')
                draw.text((x + 15, y + 5), str(back_par_total), fill='black', font=font_normal)

                y = y_back + 2 * cell_height
                draw.rectangle([x_start, y, x_start + cell_width, y + cell_height], fill='lightgray', outline='black')
                draw.text((x_start + 5, y + 5), "Score", fill='black', font=font_normal)
                back_score_total = 0
                for i in range(min(9, len(sc_data['scores']) - 9)):
                    x = x_start + (i + 1) * cell_width
                    score = sc_data['scores'][i + 9]
                    score_str = str(score) if score is not None else "-"
                    if score:
                        back_score_total += score
                    draw.rectangle([x, y, x + cell_width, y + cell_height], fill='white', outline='black')
                    draw.text((x + 20, y + 5), score_str, fill='black', font=font_normal)
                x = x_start + 10 * cell_width
                draw.rectangle([x, y, x + cell_width, y + cell_height], fill='lightgray', outline='black')
                draw.text((x + 15, y + 5), str(back_score_total), fill='black', font=font_normal)

            draw.text((20, height - 60), f"Total: {sc_data['total_score']} | Par: {sc_data['par']} | {sc_data['diff_str']}", fill='black', font=font_title)
            img.save(filepath)
            messagebox.showinfo("Success", f"Scorecard exported to:\n{filepath}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export image:\n{str(e)}")

    def on_scorecard_select(self, event):
        sel = self.score_tree.focus()
        if not sel:
            return

        rd = self.backend.get_rounds()[int(sel)]
        course = self.backend.get_course_by_name(rd["course_name"])

        win = tk.Toplevel(self.scorecards_window)
        win.title(f"Scorecard - {rd['course_name']}")
        win.geometry("500x550")

        frame = ttk.Frame(win, padding=20)
        frame.pack(fill='both', expand=True)

        diff = rd['total_score'] - rd.get('par', 72)
        diff_str = f"+{diff}" if diff > 0 else str(diff)

        ttk.Label(frame, text=rd['course_name'], style="Title.TLabel").pack()
        ttk.Label(frame, text=f"{rd.get('date', 'N/A')}").pack()
        ttk.Label(frame, text=f"Score: {rd['total_score']} ({diff_str})", font=("Helvetica", 14, "bold")).pack(pady=10)

        info_frame = ttk.Frame(frame)
        info_frame.pack()
        for i, line in enumerate([f"Target: {rd.get('target_score', 'N/A')}", f"Tee: {rd.get('tee_color', 'N/A')}", f"Type: {rd.get('round_type', 'solo').title()}", f"Serious: {'Yes' if rd['is_serious'] else 'No'}"]):
            ttk.Label(info_frame, text=line).grid(row=i//2, column=i%2, padx=10, sticky='w')

        ttk.Label(frame, text="Hole-by-Hole", style="Header.TLabel").pack(pady=(15, 5))

        table_frame = ttk.Frame(frame)
        table_frame.pack()

        pars = course["pars"] if course else [4] * len(rd["scores"])
        yardages = course.get("yardages", {}).get(rd.get("tee_color", ""), []) if course else []
        has_yardages = yardages and any(y > 0 for y in yardages)

        for i in range(min(9, len(rd["scores"]))):
            ttk.Label(table_frame, text=str(i+1), width=4, relief='ridge').grid(row=0, column=i)
            ttk.Label(table_frame, text=str(pars[i]), width=4, relief='ridge').grid(row=1, column=i)
            if has_yardages and i < len(yardages):
                ttk.Label(table_frame, text=str(yardages[i]) if yardages[i] > 0 else "-", width=4, relief='ridge').grid(row=2, column=i)
            sc = rd["scores"][i]
            ttk.Label(table_frame, text=str(sc) if sc else "-", width=4, relief='ridge').grid(row=3 if has_yardages else 2, column=i)

        ttk.Label(table_frame, text="Hole").grid(row=0, column=9, padx=5)
        ttk.Label(table_frame, text="Par").grid(row=1, column=9, padx=5)
        if has_yardages:
            ttk.Label(table_frame, text="Yds").grid(row=2, column=9, padx=5)
        ttk.Label(table_frame, text="Score").grid(row=3 if has_yardages else 2, column=9, padx=5)

        if len(rd["scores"]) > 9:
            base_row = 4 if has_yardages else 3
            for i in range(9, len(rd["scores"])):
                col = i - 9
                ttk.Label(table_frame, text=str(i+1), width=4, relief='ridge').grid(row=base_row, column=col)
                ttk.Label(table_frame, text=str(pars[i]), width=4, relief='ridge').grid(row=base_row+1, column=col)
                if has_yardages and i < len(yardages):
                    ttk.Label(table_frame, text=str(yardages[i]) if yardages[i] > 0 else "-", width=4, relief='ridge').grid(row=base_row+2, column=col)
                sc = rd["scores"][i]
                ttk.Label(table_frame, text=str(sc) if sc else "-", width=4, relief='ridge').grid(row=base_row+3 if has_yardages else base_row+2, column=col)

        if rd.get("notes"):
            ttk.Label(frame, text="Notes:", style="Header.TLabel").pack(pady=(15, 5))
            ttk.Label(frame, text=rd["notes"], wraplength=300).pack()

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(pady=15)
        ttk.Button(btn_frame, text="Export", command=lambda: self.show_export_dialog(rd)).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Close", command=win.destroy).pack(side='left', padx=5)
    def open_rulebook(self):
        self.rulebook_window = tk.Toplevel(self.root)
        self.rulebook_window.title("📖 USGA/PGA Rulebook")
        self.rulebook_window.geometry("700x600")

        main_frame = ttk.Frame(self.rulebook_window)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill='x')

        version_info = self.backend.get_rulebook_version()
        ttk.Label(header_frame, text="📖 Rules of Golf", style="Title.TLabel").pack(side='left')
        ttk.Label(header_frame, text=f"Version: {version_info['version']}", font=("Helvetica", 9)).pack(side='right')

        search_frame = ttk.LabelFrame(main_frame, text="Search Rules", padding=10)
        search_frame.pack(fill='x', pady=10)

        self.rule_search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.rule_search_var, width=40)
        search_entry.pack(side='left', padx=(0, 10))
        search_entry.bind('<Return>', lambda e: self.search_rules())

        ttk.Button(search_frame, text="🔍 Search", command=self.search_rules).pack(side='left')
        ttk.Button(search_frame, text="📑 Bookmarks", command=self.show_bookmarks).pack(side='left', padx=10)
        ttk.Button(search_frame, text="📝 My Notes", command=self.show_all_notes).pack(side='left')

        paned = ttk.PanedWindow(main_frame, orient='horizontal')
        paned.pack(fill='both', expand=True, pady=10)

        nav_frame = ttk.LabelFrame(paned, text="Sections", padding=5)
        self.section_tree = ttk.Treeview(nav_frame, show="tree", height=20)
        nav_scroll = ttk.Scrollbar(nav_frame, orient='vertical', command=self.section_tree.yview)
        self.section_tree.configure(yscrollcommand=nav_scroll.set)
        self.section_tree.pack(side='left', fill='both', expand=True)
        nav_scroll.pack(side='right', fill='y')
        self.section_tree.bind('<<TreeviewSelect>>', self.on_section_select)

        for section_id, section_title in self.backend.get_all_sections():
            self.section_tree.insert("", "end", iid=section_id, text=f"{section_id}. {section_title}")

        paned.add(nav_frame, weight=1)

        content_frame = ttk.LabelFrame(paned, text="Rule Details", padding=5)
        self.rule_content = tk.Text(content_frame, wrap='word', height=25, width=50)
        content_scroll = ttk.Scrollbar(content_frame, orient='vertical', command=self.rule_content.yview)
        self.rule_content.configure(yscrollcommand=content_scroll.set)
        self.rule_content.pack(side='left', fill='both', expand=True)
        content_scroll.pack(side='right', fill='y')
        paned.add(content_frame, weight=2)

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill='x', pady=10)
        ttk.Button(btn_frame, text="Import New Rulebook", command=self.import_rulebook).pack(side='left')
        ttk.Button(btn_frame, text="Close", command=self.rulebook_window.destroy).pack(side='right')

        self.rule_content.insert('1.0', "Welcome to the Rules of Golf!\n\nSelect a section from the left panel to browse rules, or use the search box to find specific rules.\n\nFeatures:\n• Search across all rules\n• Bookmark important rules\n• Add personal notes to rules\n• Import updated rulebook versions")
        self.rule_content.config(state='disabled')

    def search_rules(self):
        query = self.rule_search_var.get().strip()
        if not query:
            return messagebox.showwarning("Warning", "Enter a search term")

        results = self.backend.search_rulebook(query)
        self.rule_content.config(state='normal')
        self.rule_content.delete('1.0', tk.END)

        if not results:
            self.rule_content.insert('1.0', f"No results found for '{query}'")
        else:
            self.rule_content.insert('1.0', f"Search Results for '{query}' ({len(results)} found):\n\n")
            for result in results:
                is_bookmarked = "★ " if self.backend.is_bookmarked(result['rule_id']) else ""
                self.rule_content.insert(tk.END, f"{is_bookmarked}Rule {result['rule_id']}: {result['rule_title']}\nSection: {result['section_title']}\n\n{result['content'][:300]}{'...' if len(result['content']) > 300 else ''}\n\n" + "─" * 50 + "\n\n")

        self.rule_content.config(state='disabled')

    def on_section_select(self, event):
        selection = self.section_tree.selection()
        if not selection:
            return

        rules = self.backend.get_section_rules(selection[0])
        self.rule_content.config(state='normal')
        self.rule_content.delete('1.0', tk.END)

        for rule in rules:
            is_bookmarked = "★ " if self.backend.is_bookmarked(rule['id']) else ""
            user_notes = self.backend.get_rule_notes(rule['id'])
            self.rule_content.insert(tk.END, f"{is_bookmarked}Rule {rule['id']}: {rule['title']}\n\n{rule['content']}\n")
            if user_notes:
                self.rule_content.insert(tk.END, f"\n📝 My Notes: {user_notes}\n")
            self.rule_content.insert(tk.END, "\n" + "─" * 50 + "\n\n")

        self.rule_content.config(state='disabled')

    def show_bookmarks(self):
        bookmarks = self.backend.get_bookmarks()
        win = tk.Toplevel(self.rulebook_window)
        win.title("📑 Bookmarked Rules")
        win.geometry("500x400")

        frame = ttk.Frame(win, padding=20)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text="📑 Bookmarked Rules", style="Title.TLabel").pack(pady=(0, 15))

        if not bookmarks:
            ttk.Label(frame, text="No bookmarks yet.\n\nRight-click on a rule to bookmark it.").pack()
        else:
            listbox = tk.Listbox(frame, height=15, width=60)
            listbox.pack(fill='both', expand=True, pady=10)
            for rule_id in bookmarks:
                rule_info = self.backend.get_rule_by_id(rule_id)
                if rule_info:
                    listbox.insert(tk.END, f"Rule {rule_id}: {rule_info['rule']['title']}")

            def remove_bookmark():
                sel = listbox.curselection()
                if sel:
                    self.backend.remove_bookmark(bookmarks[sel[0]])
                    listbox.delete(sel[0])

            ttk.Button(frame, text="Remove Bookmark", command=remove_bookmark).pack(pady=10)

        ttk.Button(frame, text="Close", command=win.destroy).pack()

    def show_all_notes(self):
        notes = self.backend.get_all_notes()
        win = tk.Toplevel(self.rulebook_window)
        win.title("📝 My Rule Notes")
        win.geometry("600x500")

        frame = ttk.Frame(win, padding=20)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text="📝 My Rule Notes", style="Title.TLabel").pack(pady=(0, 15))

        if not notes:
            ttk.Label(frame, text="No notes yet.\n\nAdd notes to rules from the main rulebook view.").pack()
        else:
            text = tk.Text(frame, wrap='word', height=20, width=60)
            scroll = ttk.Scrollbar(frame, orient='vertical', command=text.yview)
            text.configure(yscrollcommand=scroll.set)
            text.pack(side='left', fill='both', expand=True)
            scroll.pack(side='right', fill='y')

            for rule_id, note in notes.items():
                rule_info = self.backend.get_rule_by_id(rule_id)
                title = rule_info['rule']['title'] if rule_info else "Unknown Rule"
                text.insert(tk.END, f"Rule {rule_id}: {title}\nNote: {note}\n" + "─" * 40 + "\n\n")
            text.config(state='disabled')

        ttk.Button(frame, text="Close", command=win.destroy).pack(pady=10)

    def import_rulebook(self):
        filepath = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")], title="Select Rulebook JSON File")
        if not filepath:
            return
        if self.backend.import_rulebook_from_file(filepath):
            messagebox.showinfo("Success", "Rulebook imported successfully!")
            for item in self.section_tree.get_children():
                self.section_tree.delete(item)
            for section_id, section_title in self.backend.get_all_sections():
                self.section_tree.insert("", "end", iid=section_id, text=f"{section_id}. {section_title}")
        else:
            messagebox.showerror("Error", "Failed to import rulebook. Check the file format.")

    def open_club_distances(self):
        self.clubs_window = tk.Toplevel(self.root)
        self.clubs_window.title("Club Distance Mapper")
        self.clubs_window.geometry("400x500")

        frame = ttk.Frame(self.clubs_window, padding=15)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text="🏌️ Club Distances", style="Title.TLabel").pack(pady=(0, 15))

        add_frame = ttk.LabelFrame(frame, text="Add/Update Club", padding=10)
        add_frame.pack(fill='x', pady=(0, 15))

        ttk.Label(add_frame, text="Club:").grid(row=0, column=0, sticky='e', padx=5)
        self.club_name_var = tk.StringVar()
        ttk.Combobox(add_frame, textvariable=self.club_name_var, width=15, values=["Driver", "3 Wood", "5 Wood", "Hybrid", "3 Iron", "4 Iron", "5 Iron", "6 Iron", "7 Iron", "8 Iron", "9 Iron", "PW", "GW", "SW", "LW", "Putter"]).grid(row=0, column=1, pady=3)

        ttk.Label(add_frame, text="Distance (yds):").grid(row=1, column=0, sticky='e', padx=5)
        self.club_dist_var = tk.StringVar()
        ttk.Entry(add_frame, textvariable=self.club_dist_var, width=10).grid(row=1, column=1, sticky='w', pady=3)

        ttk.Label(add_frame, text="Notes:").grid(row=2, column=0, sticky='e', padx=5)
        self.club_notes_var = tk.StringVar()
        ttk.Entry(add_frame, textvariable=self.club_notes_var, width=20).grid(row=2, column=1, pady=3)

        ttk.Button(add_frame, text="Save Club", command=self.save_club).grid(row=3, column=0, columnspan=2, pady=10)

        ttk.Label(frame, text="Your Clubs (longest → shortest)", style="Header.TLabel").pack(anchor='w')

        cols = ("Club", "Distance", "Notes")
        self.clubs_tree = ttk.Treeview(frame, columns=cols, show="headings", height=12)
        for col in cols:
            self.clubs_tree.heading(col, text=col)
        self.clubs_tree.column("Club", width=100)
        self.clubs_tree.column("Distance", width=80, anchor='center')
        self.clubs_tree.column("Notes", width=150)
        self.clubs_tree.pack(fill='both', expand=True, pady=10)
        self.clubs_tree.bind("<Double-1>", self.on_club_select)

        ttk.Button(frame, text="Delete Selected", command=self.delete_club).pack()
        self.populate_clubs()

    def populate_clubs(self):
        for row in self.clubs_tree.get_children():
            self.clubs_tree.delete(row)
        for club in self.backend.get_clubs_sorted_by_distance():
            self.clubs_tree.insert("", "end", values=(club["name"], f"{club['distance']} yds", club.get("notes", "")))

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

        club_data = {"name": name, "distance": distance, "notes": self.club_notes_var.get().strip()}
        existing = next((c for c in self.backend.get_clubs() if c["name"].lower() == name.lower()), None)
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

    def open_statistics(self):
        win = tk.Toplevel(self.root)
        win.title("Statistics")
        win.geometry("450x550")

        frame = ttk.Frame(win, padding=20)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text="📊 Your Statistics", style="Title.TLabel").pack(pady=(0, 20))

        stats = self.backend.get_statistics()
        idx = self.backend.calculate_handicap_index()

        stats_frame = ttk.LabelFrame(frame, text="Overview", padding=10)
        stats_frame.pack(fill='x', pady=(0, 15))

        stat_lines = [
            ("Handicap Index:", f"{idx:.1f}" if idx else "Not established"),
            ("Total Rounds:", stats["total_rounds"]), ("18-Hole Rounds:", stats["rounds_18"]),
            ("9-Hole Rounds:", stats["rounds_9"]), ("Solo Rounds:", stats["solo_rounds"]),
            ("Scramble Rounds:", stats["scramble_rounds"]), ("Avg Score (18h):", stats["avg_score_18"] or "N/A"),
            ("Avg Score (9h):", stats.get("avg_score_9") or "N/A"), ("Total Holes Played:", stats.get("total_holes_played", 0)),
        ]

        for i, (label, value) in enumerate(stat_lines):
            ttk.Label(stats_frame, text=label).grid(row=i, column=0, sticky='e', padx=5)
            ttk.Label(stats_frame, text=str(value), font=("Helvetica", 10, "bold")).grid(row=i, column=1, sticky='w', padx=5)

        if idx is None:
            total_holes = stats.get("total_holes_played", 0)
            remaining = max(0, 54 - total_holes)
            if remaining > 0:
                note_frame = ttk.Frame(frame)
                note_frame.pack(fill='x', pady=5)
                ttk.Label(note_frame, text=f"ℹ️ Play {remaining} more holes to establish handicap", foreground='blue').pack()
                ttk.Label(note_frame, text="(You can use any mix of 9 and 18 hole rounds)", font=("Helvetica", 9)).pack()

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
                tree.insert("", "end", values=(d["diff"], d["score"], d.get("holes", 18), d["course"]))

        ttk.Button(frame, text="Close", command=win.destroy).pack(pady=10)


if __name__ == "__main__":
    root = tk.Tk()
    app = GolfApp(root)
    root.mainloop()