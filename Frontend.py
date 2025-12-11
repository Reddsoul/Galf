from datetime import datetime, date

from Backend import GolfBackend, save_json, ROUNDS_FILE, generate_scorecard_data, PDF_AVAILABLE

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from tkcalendar import DateEntry

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

from PIL import Image, ImageDraw, ImageFont, ImageTk

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

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

        holes_choice = rd.get("holes_choice", "full_18")
        holes_played = rd.get("holes_played", 18)
        if holes_choice == "front_9":
            holes_text = "Front 9"
        elif holes_choice == "back_9":
            holes_text = "Back 9"
        else:
            holes_text = f"{holes_played} Holes"

        ttk.Label(frame, text=rd['course_name'], style="Title.TLabel").pack()
        ttk.Label(frame, text=f"{rd.get('date', 'N/A')}").pack()
        ttk.Label(frame, text=f"Score: {rd['total_score']} ({diff_str})", font=("Helvetica", 14, "bold")).pack(pady=5)
        ttk.Label(frame, text=f"Holes: {holes_text}", font=("Helvetica", 11)).pack(pady=(0, 10))

        info_frame = ttk.Frame(frame)
        info_frame.pack()
        for i, line in enumerate([
            f"Target: {rd.get('target_score', 'N/A')}",
            f"Tee: {rd.get('tee_color', 'N/A')}",
            f"Type: {rd.get('round_type', 'solo').title()}",
            f"Serious: {'Yes' if rd['is_serious'] else 'No'}"
        ]):
            ttk.Label(info_frame, text=line).grid(row=i//2, column=i%2, padx=10, sticky='w')

        ttk.Label(frame, text="Hole-by-Hole", style="Header.TLabel").pack(pady=(15, 5))

        table_frame = ttk.Frame(frame)
        table_frame.pack()

        # Build pars and yardages
        pars = course["pars"] if course else [4] * len(rd["scores"])
        yardages = course.get("yardages", {}).get(rd.get("tee_color", ""), []) if course else []
        has_yardages = bool(yardages and any(y > 0 for y in yardages))

        # Determine which holes to show based on holes_choice
        scores = rd["scores"]
        n_scores = len(scores)

        if holes_choice == "front_9":
            start_idx = 0
            end_idx = min(9, n_scores)
        elif holes_choice == "back_9":
            # Prefer the classic back 9 (10–18) if available
            if n_scores >= 18:
                start_idx = 9
                end_idx = 18
            else:
                # Fallback: last 9 holes of whatever we have
                start_idx = max(0, n_scores - 9)
                end_idx = n_scores
        else:  # full_18 or unknown → show everything we have
            start_idx = 0
            end_idx = n_scores

        holes_indices = list(range(start_idx, end_idx))

        if not holes_indices:
            ttk.Label(table_frame, text="No hole-by-hole data available.").pack()
        else:
            # Row labels
            ttk.Label(table_frame, text="Hole", width=6, relief='ridge').grid(row=0, column=0, padx=1)
            ttk.Label(table_frame, text="Par", width=6, relief='ridge').grid(row=1, column=0, padx=1)
            if has_yardages:
                ttk.Label(table_frame, text="Yds", width=6, relief='ridge').grid(row=2, column=0, padx=1)
            ttk.Label(
                table_frame,
                text="Score",
                width=6,
                relief='ridge'
            ).grid(row=3 if has_yardages else 2, column=0, padx=1)

            # Hole numbers
            for col, hole_idx in enumerate(holes_indices, start=1):
                ttk.Label(
                    table_frame,
                    text=str(hole_idx + 1),
                    width=4,
                    relief='ridge'
                ).grid(row=0, column=col)

            # Par row
            for col, hole_idx in enumerate(holes_indices, start=1):
                par_val = pars[hole_idx] if hole_idx < len(pars) else 4
                ttk.Label(
                    table_frame,
                    text=str(par_val),
                    width=4,
                    relief='ridge'
                ).grid(row=1, column=col)

            # Yardages row (optional)
            if has_yardages:
                for col, hole_idx in enumerate(holes_indices, start=1):
                    yds = yardages[hole_idx] if hole_idx < len(yardages) else 0
                    y_text = str(yds) if yds > 0 else "-"
                    ttk.Label(
                        table_frame,
                        text=y_text,
                        width=4,
                        relief='ridge'
                    ).grid(row=2, column=col)

            # Scores row
            score_row = 3 if has_yardages else 2
            for col, hole_idx in enumerate(holes_indices, start=1):
                sc = scores[hole_idx] if hole_idx < len(scores) else None
                s_text = str(sc) if sc is not None else "-"
                ttk.Label(
                    table_frame,
                    text=s_text,
                    width=4,
                    relief='ridge'
                ).grid(row=score_row, column=col)

        if rd.get("notes"):
            ttk.Label(frame, text="Notes:", style="Header.TLabel").pack(pady=(15, 5))
            ttk.Label(frame, text=rd["notes"], wraplength=300).pack()

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(pady=15)
        ttk.Button(btn_frame, text="Export", command=lambda: self.show_export_dialog(rd)).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Close", command=win.destroy).pack(side='left', padx=5)

    def open_rulebook(self):
        """Open an enhanced PDF rulebook viewer with Apple HIG-inspired design."""
        self.rulebook_window = tk.Toplevel(self.root)
        self.rulebook_window.title("Rules of Golf")
        self.rulebook_window.geometry("1200x800")
        self.rulebook_window.minsize(1000, 650)
        
        # Configure Apple HIG-inspired styling
        style = ttk.Style()
        style.configure("Sidebar.TFrame", background="#F5F5F7")
        style.configure("Toolbar.TFrame", background="#FFFFFF")
        style.configure("Sidebar.Treeview", background="#F5F5F7", fieldbackground="#F5F5F7",
                       font=("SF Pro Text", 11))
        style.configure("Sidebar.Treeview.Heading", font=("SF Pro Text", 11, "bold"))
        style.map("Sidebar.Treeview", background=[("selected", "#007AFF")])
        
        # Initialize PDF viewer state
        self.current_pdf_page = 0
        self.pdf_zoom = 1.5
        self.pdf_images = []
        self.highlight_mode = False
        self.highlight_color = "#FFFF00"  # Yellow default
        self.pdf_annotations = self.backend.get_pdf_annotations() if hasattr(self.backend, 'get_pdf_annotations') else {}
        self.page_bookmarks = self.backend.get_page_bookmarks() if hasattr(self.backend, 'get_page_bookmarks') else []

        main_frame = ttk.Frame(self.rulebook_window)
        main_frame.pack(fill='both', expand=True)

        # ===== TOOLBAR (Apple-style unified toolbar) =====
        toolbar_frame = ttk.Frame(main_frame, style="Toolbar.TFrame")
        toolbar_frame.pack(fill='x', padx=0, pady=0)
        
        # Inner toolbar with padding
        toolbar_inner = ttk.Frame(toolbar_frame)
        toolbar_inner.pack(fill='x', padx=15, pady=8)
        
        # Left: Navigation
        nav_group = ttk.Frame(toolbar_inner)
        nav_group.pack(side='left')
        
        ttk.Button(nav_group, text="◀", command=self.prev_page, width=3).pack(side='left', padx=1)
        ttk.Button(nav_group, text="▶", command=self.next_page, width=3).pack(side='left', padx=1)
        
        ttk.Separator(toolbar_inner, orient='vertical').pack(side='left', fill='y', padx=12)
        
        # Page indicator
        page_group = ttk.Frame(toolbar_inner)
        page_group.pack(side='left')
        
        self.page_num_var = tk.StringVar(value="1")
        self.page_entry = ttk.Entry(page_group, textvariable=self.page_num_var, width=5, justify='center')
        self.page_entry.pack(side='left')
        self.page_entry.bind('<Return>', lambda e: self.go_to_entered_page())
        
        total_pages = self.backend.get_total_pages() if self.backend.is_rulebook_available() else 0
        self.total_pages_label = ttk.Label(page_group, text=f" of {total_pages}", font=("SF Pro Text", 11))
        self.total_pages_label.pack(side='left')
        
        ttk.Separator(toolbar_inner, orient='vertical').pack(side='left', fill='y', padx=12)
        
        # Zoom controls
        zoom_group = ttk.Frame(toolbar_inner)
        zoom_group.pack(side='left')
        
        ttk.Button(zoom_group, text="−", command=self.zoom_out, width=3).pack(side='left', padx=1)
        self.zoom_label = ttk.Label(zoom_group, text="150%", width=5, anchor='center', font=("SF Pro Text", 10))
        self.zoom_label.pack(side='left', padx=4)
        ttk.Button(zoom_group, text="+", command=self.zoom_in, width=3).pack(side='left', padx=1)
        
        ttk.Separator(toolbar_inner, orient='vertical').pack(side='left', fill='y', padx=12)
        
        # Search (Apple-style search field)
        search_group = ttk.Frame(toolbar_inner)
        search_group.pack(side='left', fill='x', expand=True)
        
        ttk.Label(search_group, text="🔍", font=("SF Pro Text", 12)).pack(side='left')
        self.rule_search_var = tk.StringVar()
        search_entry = ttk.Entry(search_group, textvariable=self.rule_search_var, width=30)
        search_entry.pack(side='left', padx=5)
        search_entry.bind('<Return>', lambda e: self.search_pdf_with_highlight())
        
        ttk.Separator(toolbar_inner, orient='vertical').pack(side='left', fill='y', padx=12)
        
        # Annotation tools
        annot_group = ttk.Frame(toolbar_inner)
        annot_group.pack(side='left')
        
        self.highlight_btn = ttk.Button(annot_group, text="🖍", command=self.toggle_highlight_mode, width=3)
        self.highlight_btn.pack(side='left', padx=2)
        
        self.highlight_color_var = tk.StringVar(value="Yellow")
        color_combo = ttk.Combobox(annot_group, textvariable=self.highlight_color_var, 
                                    values=["Yellow", "Green", "Blue", "Pink"], width=7, state='readonly')
        color_combo.pack(side='left', padx=2)
        color_combo.bind('<<ComboboxSelected>>', self.on_highlight_color_change)
        
        ttk.Button(annot_group, text="📝", command=self.add_page_note, width=3).pack(side='left', padx=2)
        ttk.Button(annot_group, text="⭐", command=self.bookmark_current_page, width=3).pack(side='left', padx=2)
        
        # Right: Import/Settings
        right_group = ttk.Frame(toolbar_inner)
        right_group.pack(side='right')
        
        ttk.Button(right_group, text="📥 Import", command=self.import_rulebook).pack(side='left', padx=2)

        # ===== MAIN CONTENT (Split View - Apple style) =====
        content_pane = ttk.PanedWindow(main_frame, orient='horizontal')
        content_pane.pack(fill='both', expand=True)

        # ----- LEFT SIDEBAR: Table of Contents -----
        sidebar_frame = ttk.Frame(content_pane, style="Sidebar.TFrame", width=320)
        
        # Sidebar header
        sidebar_header = ttk.Frame(sidebar_frame)
        sidebar_header.pack(fill='x', padx=10, pady=(10, 5))
        ttk.Label(sidebar_header, text="Table of Contents", font=("SF Pro Display", 13, "bold")).pack(side='left')
        
        # TOC Tree with Apple-style appearance
        toc_container = ttk.Frame(sidebar_frame)
        toc_container.pack(fill='both', expand=True, padx=5, pady=5)
        
        self.section_tree = ttk.Treeview(toc_container, show="tree", style="Sidebar.Treeview", selectmode='browse')
        toc_scroll = ttk.Scrollbar(toc_container, orient='vertical', command=self.section_tree.yview)
        self.section_tree.configure(yscrollcommand=toc_scroll.set)
        self.section_tree.pack(side='left', fill='both', expand=True)
        toc_scroll.pack(side='right', fill='y')
        self.section_tree.bind('<<TreeviewSelect>>', self.on_section_select)
        
        # Load TOC
        self._load_section_tree()
        
        # Sidebar footer with bookmarks/search results toggle
        sidebar_footer = ttk.Frame(sidebar_frame)
        sidebar_footer.pack(fill='x', padx=10, pady=10)
        ttk.Button(sidebar_footer, text="📑 Bookmarks", command=self.show_page_bookmarks).pack(side='left', padx=2)
        ttk.Button(sidebar_footer, text="📝 Notes", command=self.show_all_notes).pack(side='left', padx=2)
        
        content_pane.add(sidebar_frame, weight=1)

        # ----- RIGHT: PDF View -----
        pdf_frame = ttk.Frame(content_pane)
        
        # PDF Canvas with dark background (like Preview.app)
        canvas_container = ttk.Frame(pdf_frame)
        canvas_container.pack(fill='both', expand=True)
        
        self.pdf_canvas = tk.Canvas(canvas_container, bg='#525252', highlightthickness=0)
        self.pdf_v_scroll = ttk.Scrollbar(canvas_container, orient='vertical', command=self.pdf_canvas.yview)
        self.pdf_h_scroll = ttk.Scrollbar(canvas_container, orient='horizontal', command=self.pdf_canvas.xview)
        
        self.pdf_canvas.configure(yscrollcommand=self.pdf_v_scroll.set, xscrollcommand=self.pdf_h_scroll.set)
        
        self.pdf_v_scroll.pack(side='right', fill='y')
        self.pdf_h_scroll.pack(side='bottom', fill='x')
        self.pdf_canvas.pack(side='left', fill='both', expand=True)
        
        # Mouse bindings
        self.pdf_canvas.bind('<MouseWheel>', self.on_mousewheel)
        self.pdf_canvas.bind('<Button-4>', lambda e: self.pdf_canvas.yview_scroll(-1, 'units'))
        self.pdf_canvas.bind('<Button-5>', lambda e: self.pdf_canvas.yview_scroll(1, 'units'))
        self.pdf_canvas.bind('<Button-1>', self.on_canvas_click)
        self.pdf_canvas.bind('<B1-Motion>', self.on_canvas_drag)
        self.pdf_canvas.bind('<ButtonRelease-1>', self.on_canvas_release)
        
        self.highlight_start = None
        self.temp_highlight = None
        
        content_pane.add(pdf_frame, weight=3)

        # ===== STATUS BAR =====
        status_bar = ttk.Frame(main_frame)
        status_bar.pack(fill='x', pady=(5, 0))
        
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(status_bar, textvariable=self.status_var, font=("SF Pro Text", 10), foreground='#666666').pack(side='left', padx=10)

        # Show initial content
        if self.backend.is_rulebook_available():
            self.display_pdf_page_canvas(0)
        else:
            self._show_welcome_message()
    def _load_section_tree(self):
        """Load hierarchical TOC into the tree view with Apple HIG-inspired styling."""
        for item in self.section_tree.get_children():
            self.section_tree.delete(item)
        
        # Get the full hierarchical TOC from backend
        rulebook = self.backend.get_rulebook()
        if not rulebook or not rulebook.is_available():
            self.section_tree.insert("", "end", iid="no_pdf", text="📥 Import PDF to view contents")
            return
        
        toc = rulebook.get_toc()
        if not toc:
            self.section_tree.insert("", "end", iid="no_toc", text="No table of contents found")
            return
        
        # Track parent items for hierarchy
        parent_stack = {0: ""}  # level -> parent iid
        
        for i, item in enumerate(toc):
            level = item["level"]
            title = item["title"]
            page = item["page"]
            item_id = f"toc_{i}"
            
            # Find appropriate parent
            parent_iid = parent_stack.get(level - 1, "")
            
            # Format display text based on level (Apple HIG: clear hierarchy, readable)
            if level == 1:
                # Part headers - bold, prominent
                display_text = f"📘 {title}"
            elif level == 2:
                # Rules - clear numbering
                display_text = f"    {title}"
            else:
                # Sub-rules - indented, lighter
                display_text = f"        {title}"
            
            # Insert with page info stored in values
            self.section_tree.insert(parent_iid, "end", iid=item_id, text=display_text, 
                                    values=(page,), open=(level == 1))
            
            # Update parent stack for this level
            parent_stack[level] = item_id
            # Clear deeper levels
            for l in list(parent_stack.keys()):
                if l > level:
                    del parent_stack[l]
    
    def _show_welcome_message(self):
        """Show welcome message on canvas when no PDF is loaded."""
        self.pdf_canvas.delete('all')
        
        # Apple HIG inspired: clean, centered, helpful
        welcome_lines = [
            "",
            "📖 Rules of Golf Viewer",
            "",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "",
            "No PDF Loaded",
            "",
            "Click 'Import PDF' below to load",
            "the official Rules of Golf PDF.",
            "",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "",
            "Features:",
            "• Navigate using Table of Contents",
            "• Search across all pages",
            "• Highlight important text",
            "• Add notes to any page",
            "• Bookmark pages for quick access",
        ]
        
        y_pos = 80
        for line in welcome_lines:
            if line.startswith("📖"):
                self.pdf_canvas.create_text(300, y_pos, text=line, fill='#FFFFFF', 
                                            font=("SF Pro Display", 18, "bold"), anchor='center')
            elif line.startswith("━"):
                self.pdf_canvas.create_text(300, y_pos, text=line, fill='#666666', 
                                            font=("Helvetica", 10), anchor='center')
            elif line == "No PDF Loaded":
                self.pdf_canvas.create_text(300, y_pos, text=line, fill='#FF9500', 
                                            font=("SF Pro Text", 14), anchor='center')
            elif line.startswith("Features"):
                self.pdf_canvas.create_text(300, y_pos, text=line, fill='#AAAAAA', 
                                            font=("SF Pro Text", 12, "bold"), anchor='center')
            elif line.startswith("•"):
                self.pdf_canvas.create_text(300, y_pos, text=line, fill='#888888', 
                                            font=("SF Pro Text", 11), anchor='center')
            else:
                self.pdf_canvas.create_text(300, y_pos, text=line, fill='#CCCCCC', 
                                            font=("SF Pro Text", 12), anchor='center')
            y_pos += 24

    # ===== PDF CANVAS DISPLAY METHODS =====
    
    def display_pdf_page_canvas(self, page_num):
        """Display a PDF page on the canvas with proper rendering."""
        if not PYMUPDF_AVAILABLE:
            self.status_var.set("PyMuPDF not installed")
            return
        
        rulebook = self.backend.get_rulebook()
        if not rulebook.is_available():
            self.status_var.set("No PDF loaded")
            return
        
        doc = rulebook.doc
        total_pages = len(doc)
        
        # Bounds check
        if page_num < 0:
            page_num = 0
        if page_num >= total_pages:
            page_num = total_pages - 1
        
        self.current_pdf_page = page_num
        self.page_num_var.set(str(page_num + 1))
        
        try:
            page = doc[page_num]
            
            # Render with current zoom level
            mat = fitz.Matrix(self.pdf_zoom, self.pdf_zoom)
            pix = page.get_pixmap(matrix=mat)
            
            # FIX: Use samples for correct RGB data (no red tint)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            
            # Convert to PhotoImage
            photo = ImageTk.PhotoImage(img)
            
            # Store reference
            self.pdf_images = [photo]  # Clear old, keep only current
            
            # Clear canvas and display
            self.pdf_canvas.delete('all')
            
            # Center image on canvas
            canvas_width = self.pdf_canvas.winfo_width()
            canvas_height = self.pdf_canvas.winfo_height()
            
            x_offset = max(0, (canvas_width - pix.width) // 2)
            y_offset = 10
            
            self.pdf_canvas.create_image(x_offset, y_offset, anchor='nw', image=photo, tags='pdf_page')
            
            # Set scroll region
            self.pdf_canvas.configure(scrollregion=(0, 0, max(pix.width, canvas_width), pix.height + 20))
            
            # Draw any saved annotations for this page
            self._draw_page_annotations(page_num, x_offset, y_offset)
            
            # Update status
            bookmark_status = "⭐ Bookmarked" if (page_num + 1) in self.page_bookmarks else ""
            self.status_var.set(f"Page {page_num + 1} of {total_pages} {bookmark_status}")
            
        except Exception as e:
            self.status_var.set(f"Error: {str(e)}")
            self.pdf_canvas.delete('all')
            self.pdf_canvas.create_text(300, 200, text=f"Error loading page:\n{str(e)}", 
                                        fill='red', font=("Helvetica", 11))
    
    def _draw_page_annotations(self, page_num, x_offset, y_offset):
        """Draw saved highlights and annotations for a page."""
        page_key = str(page_num)
        if page_key in self.pdf_annotations:
            for annotation in self.pdf_annotations[page_key]:
                if annotation['type'] == 'highlight':
                    x1 = annotation['x1'] * self.pdf_zoom + x_offset
                    y1 = annotation['y1'] * self.pdf_zoom + y_offset
                    x2 = annotation['x2'] * self.pdf_zoom + x_offset
                    y2 = annotation['y2'] * self.pdf_zoom + y_offset
                    color = annotation.get('color', '#FFFF00')
                    self.pdf_canvas.create_rectangle(x1, y1, x2, y2, 
                                                     fill=color, stipple='gray50',
                                                     outline='', tags='annotation')
    
    # ===== NAVIGATION METHODS =====
    
    def next_page(self):
        """Go to next page."""
        if self.backend.is_rulebook_available():
            total = self.backend.get_total_pages()
            if self.current_pdf_page < total - 1:
                self.display_pdf_page_canvas(self.current_pdf_page + 1)
    
    def prev_page(self):
        """Go to previous page."""
        if self.current_pdf_page > 0:
            self.display_pdf_page_canvas(self.current_pdf_page - 1)
    
    def go_to_page(self, page_num):
        """Go to specific page (0-indexed)."""
        if self.backend.is_rulebook_available():
            self.display_pdf_page_canvas(page_num)
    
    def go_to_entered_page(self):
        """Go to page number entered in the entry field."""
        try:
            page_num = int(self.page_num_var.get()) - 1  # Convert to 0-indexed
            self.go_to_page(page_num)
        except ValueError:
            messagebox.showwarning("Invalid Page", "Please enter a valid page number")
    
    # ===== ZOOM METHODS =====
    
    def zoom_in(self):
        """Increase zoom level."""
        if self.pdf_zoom < 4.0:
            self.pdf_zoom += 0.25
            self.zoom_label.config(text=f"{int(self.pdf_zoom * 100)}%")
            self.display_pdf_page_canvas(self.current_pdf_page)
    
    def zoom_out(self):
        """Decrease zoom level."""
        if self.pdf_zoom > 0.5:
            self.pdf_zoom -= 0.25
            self.zoom_label.config(text=f"{int(self.pdf_zoom * 100)}%")
            self.display_pdf_page_canvas(self.current_pdf_page)
    
    def zoom_fit(self):
        """Fit page to canvas width."""
        if not self.backend.is_rulebook_available():
            return
        
        rulebook = self.backend.get_rulebook()
        doc = rulebook.doc
        page = doc[self.current_pdf_page]
        page_width = page.rect.width
        canvas_width = self.pdf_canvas.winfo_width() - 40
        
        if canvas_width > 100 and page_width > 0:
            self.pdf_zoom = canvas_width / page_width
            self.zoom_label.config(text=f"{int(self.pdf_zoom * 100)}%")
            self.display_pdf_page_canvas(self.current_pdf_page)
    
    # ===== MOUSE EVENT HANDLERS =====
    
    def on_mousewheel(self, event):
        """Handle mouse wheel for scrolling."""
        self.pdf_canvas.yview_scroll(-1 * (event.delta // 120), 'units')
    
    def on_canvas_click(self, event):
        """Handle click on canvas for highlight start."""
        if self.highlight_mode:
            self.highlight_start = (self.pdf_canvas.canvasx(event.x), 
                                   self.pdf_canvas.canvasy(event.y))
    
    def on_canvas_drag(self, event):
        """Handle drag for highlight drawing."""
        if self.highlight_mode and self.highlight_start:
            if self.temp_highlight:
                self.pdf_canvas.delete(self.temp_highlight)
            
            x1, y1 = self.highlight_start
            x2 = self.pdf_canvas.canvasx(event.x)
            y2 = self.pdf_canvas.canvasy(event.y)
            
            self.temp_highlight = self.pdf_canvas.create_rectangle(
                x1, y1, x2, y2,
                fill=self.highlight_color, stipple='gray50',
                outline=self.highlight_color, tags='temp_highlight'
            )
    
    def on_canvas_release(self, event):
        """Handle release to complete highlight."""
        if self.highlight_mode and self.highlight_start:
            x1, y1 = self.highlight_start
            x2 = self.pdf_canvas.canvasx(event.x)
            y2 = self.pdf_canvas.canvasy(event.y)
            
            # Only save if it's a meaningful selection
            if abs(x2 - x1) > 10 and abs(y2 - y1) > 5:
                self._save_highlight(x1, y1, x2, y2)
            
            # Clear temp
            if self.temp_highlight:
                self.pdf_canvas.delete(self.temp_highlight)
            self.highlight_start = None
            self.temp_highlight = None
    
    def _save_highlight(self, x1, y1, x2, y2):
        """Save a highlight annotation."""
        # Get canvas offset to convert to page coordinates
        canvas_items = self.pdf_canvas.find_withtag('pdf_page')
        if not canvas_items:
            return
        
        coords = self.pdf_canvas.coords(canvas_items[0])
        x_offset = coords[0] if coords else 0
        y_offset = coords[1] if coords else 0
        
        # Convert to base coordinates (without zoom)
        annotation = {
            'type': 'highlight',
            'x1': (min(x1, x2) - x_offset) / self.pdf_zoom,
            'y1': (min(y1, y2) - y_offset) / self.pdf_zoom,
            'x2': (max(x1, x2) - x_offset) / self.pdf_zoom,
            'y2': (max(y1, y2) - y_offset) / self.pdf_zoom,
            'color': self.highlight_color
        }
        
        page_key = str(self.current_pdf_page)
        if page_key not in self.pdf_annotations:
            self.pdf_annotations[page_key] = []
        self.pdf_annotations[page_key].append(annotation)
        
        # Save to backend
        if hasattr(self.backend, 'save_pdf_annotations'):
            self.backend.save_pdf_annotations(self.pdf_annotations)
        
        # Redraw to show saved annotation properly
        self.display_pdf_page_canvas(self.current_pdf_page)
        self.status_var.set(f"Highlight added to page {self.current_pdf_page + 1}")
    
    # ===== HIGHLIGHT/ANNOTATION TOOLS =====
    
    def toggle_highlight_mode(self):
        """Toggle highlight mode on/off."""
        self.highlight_mode = not self.highlight_mode
        if self.highlight_mode:
            self.highlight_btn.config(text="🖍 ON")
            self.pdf_canvas.config(cursor='cross')
            self.status_var.set("Highlight mode: Click and drag to highlight")
        else:
            self.highlight_btn.config(text="🖍 Highlight")
            self.pdf_canvas.config(cursor='')
            self.status_var.set("Highlight mode off")
    
    def on_highlight_color_change(self, event):
        """Change highlight color."""
        color_map = {
            "Yellow": "#FFFF00",
            "Green": "#90EE90",
            "Blue": "#87CEEB",
            "Pink": "#FFB6C1",
            "Orange": "#FFA500"
        }
        self.highlight_color = color_map.get(self.highlight_color_var.get(), "#FFFF00")
    
    def add_page_note(self):
        """Add a note to the current page."""
        if not self.backend.is_rulebook_available():
            return messagebox.showwarning("Warning", "No PDF loaded")
        
        note_win = tk.Toplevel(self.rulebook_window)
        note_win.title(f"📝 Note for Page {self.current_pdf_page + 1}")
        note_win.geometry("400x250")
        note_win.transient(self.rulebook_window)
        
        frame = ttk.Frame(note_win, padding=15)
        frame.pack(fill='both', expand=True)
        
        ttk.Label(frame, text=f"Add note for Page {self.current_pdf_page + 1}:", 
                  font=("Helvetica", 11, "bold")).pack(anchor='w')
        
        # Get existing note
        page_key = str(self.current_pdf_page)
        existing_note = ""
        if page_key in self.pdf_annotations:
            for ann in self.pdf_annotations[page_key]:
                if ann.get('type') == 'note':
                    existing_note = ann.get('text', '')
                    break
        
        note_text = tk.Text(frame, wrap='word', height=8, width=45)
        note_text.pack(fill='both', expand=True, pady=10)
        note_text.insert('1.0', existing_note)
        
        def save_note():
            text = note_text.get('1.0', tk.END).strip()
            if text:
                # Remove old note if exists
                if page_key in self.pdf_annotations:
                    self.pdf_annotations[page_key] = [a for a in self.pdf_annotations[page_key] 
                                                      if a.get('type') != 'note']
                else:
                    self.pdf_annotations[page_key] = []
                
                self.pdf_annotations[page_key].append({
                    'type': 'note',
                    'text': text
                })
                
                if hasattr(self.backend, 'save_pdf_annotations'):
                    self.backend.save_pdf_annotations(self.pdf_annotations)
                
                self.status_var.set(f"Note saved for page {self.current_pdf_page + 1}")
            note_win.destroy()
        
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x')
        ttk.Button(btn_frame, text="💾 Save Note", command=save_note).pack(side='left')
        ttk.Button(btn_frame, text="Cancel", command=note_win.destroy).pack(side='right')
    
    def clear_annotations(self):
        """Clear all annotations for current page."""
        if messagebox.askyesno("Clear Annotations", 
                              f"Clear all highlights and notes from page {self.current_pdf_page + 1}?"):
            page_key = str(self.current_pdf_page)
            if page_key in self.pdf_annotations:
                del self.pdf_annotations[page_key]
                if hasattr(self.backend, 'save_pdf_annotations'):
                    self.backend.save_pdf_annotations(self.pdf_annotations)
                self.display_pdf_page_canvas(self.current_pdf_page)
                self.status_var.set("Annotations cleared")
    
    # ===== BOOKMARK METHODS =====
    
    def bookmark_current_page(self):
        """Bookmark or unbookmark the current page."""
        page_num = self.current_pdf_page + 1  # 1-indexed for storage
        
        if page_num in self.page_bookmarks:
            self.page_bookmarks.remove(page_num)
            self.status_var.set(f"Bookmark removed from page {page_num}")
        else:
            self.page_bookmarks.append(page_num)
            self.page_bookmarks.sort()
            self.status_var.set(f"Page {page_num} bookmarked")
        
        # Save to backend
        if hasattr(self.backend, 'save_page_bookmarks'):
            self.backend.save_page_bookmarks(self.page_bookmarks)
        
        # Update page list display
        self._refresh_page_list()
    
    def _refresh_page_list(self):
        """Refresh any page list displays to show bookmark indicators."""
        # The new UI doesn't have a separate page listbox, so this is a no-op
        # Bookmarks are tracked in self.page_bookmarks and shown in the bookmarks dialog
        pass
    
    def show_page_bookmarks(self):
        """Show list of bookmarked pages."""
        win = tk.Toplevel(self.rulebook_window)
        win.title("📑 Bookmarked Pages")
        win.geometry("350x400")
        win.transient(self.rulebook_window)
        
        frame = ttk.Frame(win, padding=15)
        frame.pack(fill='both', expand=True)
        
        ttk.Label(frame, text="📑 Bookmarked Pages", style="Title.TLabel").pack(pady=(0, 10))
        
        if not self.page_bookmarks:
            ttk.Label(frame, text="No bookmarked pages yet.\n\nClick '⭐ Bookmark Page' while viewing a page.").pack(pady=20)
        else:
            listbox = tk.Listbox(frame, height=15, width=35)
            scroll = ttk.Scrollbar(frame, orient='vertical', command=listbox.yview)
            listbox.configure(yscrollcommand=scroll.set)
            listbox.pack(side='left', fill='both', expand=True)
            scroll.pack(side='right', fill='y')
            
            for page_num in self.page_bookmarks:
                listbox.insert(tk.END, f"⭐ Page {page_num}")
            
            def go_to_bookmark():
                sel = listbox.curselection()
                if sel:
                    page_num = self.page_bookmarks[sel[0]] - 1  # Convert to 0-indexed
                    self.display_pdf_page_canvas(page_num)
                    win.destroy()
            
            def remove_bookmark():
                sel = listbox.curselection()
                if sel:
                    page_num = self.page_bookmarks[sel[0]]
                    self.page_bookmarks.remove(page_num)
                    listbox.delete(sel[0])
                    if hasattr(self.backend, 'save_page_bookmarks'):
                        self.backend.save_page_bookmarks(self.page_bookmarks)
                    self._refresh_page_list()
            
            btn_frame = ttk.Frame(frame)
            btn_frame.pack(fill='x', pady=10)
            ttk.Button(btn_frame, text="Go to Page", command=go_to_bookmark).pack(side='left', padx=5)
            ttk.Button(btn_frame, text="Remove", command=remove_bookmark).pack(side='left')
        
        ttk.Button(frame, text="Close", command=win.destroy).pack(pady=10)
    
    # ===== SEARCH METHODS =====
    
    def search_pdf_with_highlight(self):
        """Search PDF and show results in a popup window."""
        query = self.rule_search_var.get().strip()
        if not query:
            return messagebox.showwarning("Warning", "Enter a search term")
        
        if not self.backend.is_rulebook_available():
            return messagebox.showwarning("Warning", "No PDF loaded")
        
        results = self.backend.search_rulebook_pages(query)
        self._search_results = results  # Store for later access
        
        if not results:
            self.status_var.set(f"No matches found for '{query}'")
            messagebox.showinfo("Search Results", f"No matches found for '{query}'")
            return
        
        # Show results in a popup window
        self._show_search_results_window(query, results)
        self.status_var.set(f"Found {len(results)} matches for '{query}'")
    
    def clear_search(self):
        """Clear search field and results."""
        self.rule_search_var.set("")
        self._search_results = []
        self.status_var.set("Search cleared")
    
    # ===== NAVIGATION EVENT HANDLERS =====
    
    def on_section_select(self, event):
        """Handle section selection from tree."""
        selection = self.section_tree.selection()
        if not selection:
            return
        
        # Skip placeholder items
        if selection[0] in ("no_pdf", "no_toc", "no_sections"):
            return
        
        # Get page from item values (stored when tree was built)
        item = self.section_tree.item(selection[0])
        values = item.get('values', ())
        
        if values and len(values) > 0 and values[0] is not None:
            try:
                page_num = int(values[0])
                self.display_pdf_page_canvas(page_num)
                self.status_var.set(f"Page {page_num + 1}")
            except (ValueError, TypeError):
                self.status_var.set("Could not navigate to page")
        else:
            self.status_var.set("No page information available")
    
    def _show_search_results_window(self, query, results):
        """Show search results in a popup window."""
        results_win = tk.Toplevel(self.rulebook_window)
        results_win.title(f"Search Results: {query}")
        results_win.geometry("500x400")
        results_win.transient(self.rulebook_window)
        
        frame = ttk.Frame(results_win, padding=15)
        frame.pack(fill='both', expand=True)
        
        ttk.Label(frame, text=f"Found {len(results)} matches for '{query}'", 
                  font=("SF Pro Text", 12, "bold")).pack(anchor='w', pady=(0, 10))
        
        # Results listbox
        list_frame = ttk.Frame(frame)
        list_frame.pack(fill='both', expand=True)
        
        results_list = tk.Listbox(list_frame, height=15, width=60, font=("SF Pro Text", 11))
        scroll = ttk.Scrollbar(list_frame, orient='vertical', command=results_list.yview)
        results_list.configure(yscrollcommand=scroll.set)
        results_list.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')
        
        for result in results:
            snippet = result['snippet'][:60].replace('\n', ' ')
            results_list.insert(tk.END, f"Page {result['page']}: {snippet}...")
        
        def go_to_result():
            sel = results_list.curselection()
            if sel:
                page_num = results[sel[0]]['page'] - 1  # Convert to 0-indexed
                self.display_pdf_page_canvas(page_num)
                results_win.destroy()
        
        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x', pady=(10, 0))
        ttk.Button(btn_frame, text="Go to Page", command=go_to_result).pack(side='left')
        ttk.Button(btn_frame, text="Close", command=results_win.destroy).pack(side='right')
        
        # Double-click to go to result
        results_list.bind('<Double-1>', lambda e: go_to_result())

    def search_rules(self):
        """Legacy search - redirect to new search."""
        self.search_pdf_with_highlight()

    def search_pdf_pages(self):
        """Search PDF pages directly and show results with page numbers."""
        query = self.rule_search_var.get().strip()
        if not query:
            return messagebox.showwarning("Warning", "Enter a search term")

        if not self.backend.is_rulebook_available():
            return messagebox.showwarning("Warning", "PDF rulebook not loaded. Import a PDF first.")

        results = self.backend.search_rulebook_pages(query)
        self.rule_content.config(state='normal')
        self.rule_content.delete('1.0', tk.END)

        if not results:
            self.rule_content.insert('1.0', f"No page matches found for '{query}'")
        else:
            self.rule_content.insert('1.0', f"Page Search Results for '{query}' ({len(results)} matches):\n\n")
            for result in results:
                self.rule_content.insert(tk.END, f"📄 Page {result['page']}:\n{result['snippet']}\n\n" + "─" * 50 + "\n\n")

        self.rule_content.config(state='disabled')

    def open_page_browser(self):
        """Open a window to browse PDF pages directly."""
        if not self.backend.is_rulebook_available():
            return messagebox.showwarning("Warning", "PDF rulebook not loaded.")
        
        browser = tk.Toplevel(self.rulebook_window)
        browser.title("📖 Page Browser")
        browser.geometry("600x500")
        
        frame = ttk.Frame(browser, padding=10)
        frame.pack(fill='both', expand=True)
        
        # Navigation bar
        nav_frame = ttk.Frame(frame)
        nav_frame.pack(fill='x', pady=(0, 10))
        
        total_pages = self.backend.get_total_pages()
        current_page = tk.IntVar(value=1)
        
        ttk.Label(nav_frame, text="Page:").pack(side='left')
        page_spin = ttk.Spinbox(nav_frame, from_=1, to=total_pages, textvariable=current_page, width=6)
        page_spin.pack(side='left', padx=5)
        ttk.Label(nav_frame, text=f"of {total_pages}").pack(side='left')
        
        def go_to_page():
            page_num = current_page.get() - 1  # Convert to 0-indexed
            content = self.backend.get_page_content(page_num)
            page_text.config(state='normal')
            page_text.delete('1.0', tk.END)
            page_text.insert('1.0', f"Page {current_page.get()}\n" + "─" * 40 + "\n\n")
            page_text.insert(tk.END, content)
            page_text.config(state='disabled')
        
        def prev_page():
            if current_page.get() > 1:
                current_page.set(current_page.get() - 1)
                go_to_page()
        
        def next_page():
            if current_page.get() < total_pages:
                current_page.set(current_page.get() + 1)
                go_to_page()
        
        ttk.Button(nav_frame, text="◀ Prev", command=prev_page).pack(side='left', padx=10)
        ttk.Button(nav_frame, text="Go", command=go_to_page).pack(side='left')
        ttk.Button(nav_frame, text="Next ▶", command=next_page).pack(side='left', padx=10)
        
        # Page content
        page_text = tk.Text(frame, wrap='word', height=25, width=70)
        scroll = ttk.Scrollbar(frame, orient='vertical', command=page_text.yview)
        page_text.configure(yscrollcommand=scroll.set)
        page_text.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')
        
        page_text.insert('1.0', "Use the navigation above to browse pages.\n\nClick 'Go' to view a specific page.")
        page_text.config(state='disabled')
        
        ttk.Button(frame, text="Close", command=browser.destroy).pack(pady=10)

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
        filepath = filedialog.askopenfilename(
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")], 
            title="Select Rules of Golf PDF File"
        )
        if not filepath:
            return
        
        if self.backend.import_rulebook_from_file(filepath):
            messagebox.showinfo("Success", "Rulebook PDF imported successfully!\n\nThe PDF will be parsed and indexed for searching.")
            
            # Refresh the section tree with proper page mapping
            self._load_section_tree()
            
            # Update page list
            self._refresh_page_list()
            
            # Update total pages label
            total_pages = self.backend.get_total_pages()
            if hasattr(self, 'total_pages_label'):
                self.total_pages_label.config(text=f"of {total_pages}")
            
            # Display first page
            self.display_pdf_page_canvas(0)
            self.status_var.set(f"PDF imported: {total_pages} pages")
        else:
            messagebox.showerror("Error", "Failed to import rulebook PDF.\n\nMake sure the file is a valid PDF.")

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