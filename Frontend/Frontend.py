from datetime import datetime, date

from Backend.Backend import GolfBackend, save_json, ROUNDS_FILE, generate_scorecard_data

from Yardbook.yardbook_integration import yardbookIntegration

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from tkcalendar import DateEntry


import fitz

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

from PIL import Image, ImageDraw, ImageFont, ImageTk

# Import new modules
from ui_layout import autosize_toplevel, ScrollableFrame, CollapsibleSection
from hole_plan_ui import open_hole_plan

# Courses file path (must match Backend.py)
COURSES_FILE = 'Data/courses.json'

class GolfApp:
    def __init__(self, root):
        self.backend = GolfBackend()
        self.root = root
        root.title("Golf Handicap Tracker")
        root.geometry("400x580")  # Slightly taller to fit new button

        # === yardbook INITIALIZATION ===
        self.yardbook = yardbookIntegration(self.backend, COURSES_FILE)


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
            ("📍 Yardbook", self.open_yardbook),  # NEW: yardbook button
            ("📝 Hole Plan", self.open_hole_plan),  # NEW: Hole Plan button
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

        ttk.Label(win, text="Courses by Club", style="Header.TLabel").pack(pady=10)

        # === yardbook: Added yardbook column ===
        cols = ("Club", "Course Name", "Holes", "Par", "yardbook")
        tree = ttk.Treeview(win, columns=cols, show="headings", height=12)
        for col in cols:
            tree.heading(col, text=col)
        tree.column("Club", width=130)
        tree.column("Course Name", width=200)
        tree.column("Holes", width=60, anchor='center')
        tree.column("Par", width=60, anchor='center')
        tree.column("yardbook", width=90, anchor='center')
        tree.pack(fill='both', expand=True, padx=10, pady=5)

        for c in sorted(self.backend.get_courses(), key=lambda x: (x.get("club", ""), x["name"])):
            # Check yardbook completion status
            gb_status = "—"
            if self.yardbook and self.yardbook.is_available():
                summary = self.yardbook.manager.get_course_yardbook_summary(c["name"])
                if summary["holes_with_data"] > 0:
                    gb_status = f"✓ {summary['holes_complete']}/{summary['total_holes']}"
            tree.insert("", "end", values=(c.get("club", ""), c["name"], len(c["pars"]), sum(c["pars"]), gb_status))

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

        # === yardbook: Open yardbook for selected course ===
        def open_course_yardbook():
            sel = tree.focus()
            if not sel:
                return messagebox.showwarning("Warning", "Select a course first")
            vals = tree.item(sel)["values"]
            course_name = vals[1]
            if self.yardbook and self.yardbook.is_available():
                course = self.backend.get_course_by_name(course_name)
                if course:
                    self.yardbook._launch_yardbook(self.root, course, 1)
            else:
                messagebox.showinfo("Unavailable", "yardbook feature requires tkintermapview.\nInstall with: pip install tkintermapview")

        ttk.Button(btn_frame, text="Edit", command=edit_selected).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Delete", command=delete_selected).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="📍 yardbook", command=open_course_yardbook).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Close", command=win.destroy).pack(side='left', padx=5)
        
        # Auto-size the window
        autosize_toplevel(win, min_size=(650, 400))

    # === yardbook: Main yardbook launcher ===
    def open_yardbook(self):
        """Open the yardbook feature for mapping course holes."""
        if self.yardbook and self.yardbook.is_available():
            self.yardbook.show_course_selector(self.root)
        else:
            messagebox.showinfo(
                "yardbook Unavailable",
                "The yardbook feature requires the tkintermapview library.\n\n"
                "To enable this feature, run:\n"
                "  pip install tkintermapview\n\n"
                "Then restart the application.\n\n"
                "yardbook allows you to:\n"
                "• View satellite maps of course holes\n"
                "• Place tee, green, and target markers\n"
                "• Calculate accurate yardages\n"
                "• Draw fairway and hazard overlays"
            )

    # === Hole Plan: Strategy planning launcher ===
    def open_hole_plan(self):
        """Open the Hole Plan feature for strategy planning."""
        open_hole_plan(
            parent=self.root,
            backend=self.backend,
            courses_file=COURSES_FILE,
            yardbook_integration=self.yardbook
        )

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
        self.tee_color_vars = []  # Store StringVars to prevent garbage collection
        existing_tb = self.editing_course["tee_boxes"] if self.editing_course else []
        common_colors = ["Black", "Blue", "White", "Gold", "Yellow", "Green", "Red"]

        for i in range(count):
            row = i + 2
            color_var = tk.StringVar()
            self.tee_color_vars.append(color_var)  # Keep reference
            
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
        self.log_window.geometry("450x620")

        frame = ttk.Frame(self.log_window, padding=20)
        frame.pack(fill='both', expand=True)

        ttk.Label(frame, text="Log New Round", style="Title.TLabel").grid(row=0, column=0, columnspan=2, pady=(0, 15))

        # Club (facility) selection - FIRST
        ttk.Label(frame, text="Club:").grid(row=1, column=0, sticky='e', pady=5)
        clubs = sorted(list(set(c.get("club", "") for c in courses if c.get("club"))))
        if "" in clubs:
            clubs.remove("")
        clubs = ["All Clubs"] + clubs
        self.club_facility_var = tk.StringVar(value="All Clubs")
        self.club_facility_menu = ttk.Combobox(frame, textvariable=self.club_facility_var, values=clubs, state='readonly', width=25)
        self.club_facility_menu.grid(row=1, column=1, pady=5)
        self.club_facility_menu.bind("<<ComboboxSelected>>", self.on_club_facility_selected)

        # Course selection - filtered by club
        ttk.Label(frame, text="Course:").grid(row=2, column=0, sticky='e', pady=5)
        self.course_var = tk.StringVar()
        self.course_menu = ttk.Combobox(frame, textvariable=self.course_var, values=[], state='readonly', width=25)
        self.course_menu.grid(row=2, column=1, pady=5)
        self.course_menu.bind("<<ComboboxSelected>>", self.update_course_info)

        ttk.Label(frame, text="Tee Box:").grid(row=3, column=0, sticky='e', pady=5)
        self.tee_var = tk.StringVar()
        self.tee_menu = ttk.Combobox(frame, textvariable=self.tee_var, state='readonly', width=25)
        self.tee_menu.grid(row=3, column=1, pady=5)
        self.tee_menu.bind("<<ComboboxSelected>>", self.update_course_info)

        ttk.Label(frame, text="Holes to Play:").grid(row=4, column=0, sticky='e', pady=5)
        self.holes_choice_var = tk.StringVar(value="full_18")
        holes_frame = ttk.Frame(frame)
        holes_frame.grid(row=4, column=1, sticky='w')
        ttk.Radiobutton(holes_frame, text="Full 18", variable=self.holes_choice_var, value="full_18", command=self.update_course_info).pack(side='left')
        ttk.Radiobutton(holes_frame, text="Front 9", variable=self.holes_choice_var, value="front_9", command=self.update_course_info).pack(side='left', padx=5)
        ttk.Radiobutton(holes_frame, text="Back 9", variable=self.holes_choice_var, value="back_9", command=self.update_course_info).pack(side='left')

        # DATE PICKER
        ttk.Label(frame, text="Date:").grid(row=5, column=0, sticky='e', pady=5)

        self.date_entry = DateEntry(frame, width=23, date_pattern='yyyy-mm-dd', maxdate=date.today())
        self.date_entry.grid(row=5, column=1, pady=5, sticky='w')


        self.course_handicap_label = ttk.Label(frame, text="Course Handicap: N/A")
        self.course_handicap_label.grid(row=6, column=0, columnspan=2, pady=2)

        self.target_score_label = ttk.Label(frame, text="Target Score: N/A")
        self.target_score_label.grid(row=7, column=0, columnspan=2, pady=2)

        self.yardage_label = ttk.Label(frame, text="Total Yardage: N/A")
        self.yardage_label.grid(row=8, column=0, columnspan=2, pady=2)

        ttk.Separator(frame, orient='horizontal').grid(row=9, column=0, columnspan=2, sticky='ew', pady=10)

        ttk.Label(frame, text="Round Type:").grid(row=10, column=0, sticky='e', pady=5)
        self.round_type_var = tk.StringVar(value="solo")
        type_frame = ttk.Frame(frame)
        type_frame.grid(row=10, column=1, sticky='w')
        ttk.Radiobutton(type_frame, text="Solo", variable=self.round_type_var, value="solo").pack(side='left')
        ttk.Radiobutton(type_frame, text="Scramble", variable=self.round_type_var, value="scramble").pack(side='left', padx=10)

        self.is_serious_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(frame, text="Serious Round (counts toward handicap)", variable=self.is_serious_var).grid(row=11, column=0, columnspan=2, pady=5)

        # Entry Mode Selection
        ttk.Separator(frame, orient='horizontal').grid(row=12, column=0, columnspan=2, sticky='ew', pady=10)
        
        ttk.Label(frame, text="Entry Mode:", font=("Helvetica", 10, "bold")).grid(row=13, column=0, sticky='e', pady=5)
        last_mode = self.backend.get_entry_mode()
        self.entry_mode_var = tk.StringVar(value=last_mode)
        mode_frame = ttk.Frame(frame)
        mode_frame.grid(row=13, column=1, sticky='w')
        ttk.Radiobutton(mode_frame, text="Quick", variable=self.entry_mode_var, value="quick").pack(side='left')
        ttk.Radiobutton(mode_frame, text="Detailed", variable=self.entry_mode_var, value="detailed").pack(side='left', padx=10)
        
        # Mode description
        self.mode_desc_label = ttk.Label(frame, text="Quick: Scores only", font=("Helvetica", 9), foreground="gray")
        self.mode_desc_label.grid(row=14, column=0, columnspan=2)
        self.entry_mode_var.trace_add("write", self.update_mode_description)
        # Initialize description based on last mode
        self.update_mode_description()

        ttk.Label(frame, text="Notes:").grid(row=15, column=0, sticky='ne', pady=5)
        self.notes_entry = ttk.Entry(frame, width=30)
        self.notes_entry.grid(row=15, column=1, pady=5)

        ttk.Button(frame, text="Start Scoring →", command=self.start_round_input).grid(row=16, column=0, columnspan=2, pady=20)
        
        # Initialize course list AFTER all widgets are created
        self.on_club_facility_selected()
    
    def on_club_facility_selected(self, event=None):
        """Filter courses based on selected club"""
        selected_club = self.club_facility_var.get()
        courses = self.backend.get_courses()
        
        if selected_club == "All Clubs":
            filtered = courses
        else:
            filtered = [c for c in courses if c.get("club") == selected_club]
        
        course_names = [c["name"] for c in filtered]
        self.course_menu.config(values=course_names)
        
        # Select first course if available
        if course_names:
            self.course_var.set(course_names[0])
            self.update_course_info()
        else:
            self.course_var.set("")
    
    def update_mode_description(self, *args):
        """Update the mode description label based on selection."""
        mode = self.entry_mode_var.get()
        if mode == "quick":
            self.mode_desc_label.config(text="Quick: Scores only")
        else:
            self.mode_desc_label.config(text="Detailed: Scores + Clubs Used (auto-calculates Putts & To Green)")

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
        
        # Calculate proper course handicap using player's handicap index
        course_handicap, target_score = self.backend.calculate_course_handicap(name, tee_color, choice)
        
        # Determine par for display
        if choice == "full_18":
            par_display = sum(course["pars"])
        elif choice == "front_9":
            par_display = sum(course["pars"][:9])
        else:
            par_display = sum(course["pars"][9:]) if len(course["pars"]) > 9 else sum(course["pars"][:9])
        
        if course_handicap is not None:
            self.course_handicap_label.config(text=f"Course Handicap: {course_handicap}")
            self.target_score_label.config(text=f"Target Score: {target_score} (Par {par_display})")
        else:
            self.course_handicap_label.config(text="Course Handicap: N/A (need handicap index)")
            self.target_score_label.config(text=f"Target Score: N/A (Par {par_display})")

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
        self.entry_mode = self.entry_mode_var.get()
        
        # Save the entry mode preference
        self.backend.set_entry_mode(self.entry_mode)

        all_pars = self.selected_course["pars"]
        if self.holes_choice == "full_18":
            self.holes_to_score = list(range(len(all_pars)))
        elif self.holes_choice == "front_9":
            self.holes_to_score = list(range(min(9, len(all_pars))))
        else:
            self.holes_to_score = list(range(9, 18)) if len(all_pars) >= 18 else list(range(len(all_pars)))

        for w in self.log_window.winfo_children():
            w.destroy()
        
        if self.entry_mode == "detailed":
            self.start_detailed_round_input()
        else:
            self.start_quick_round_input()
    
    def start_quick_round_input(self):
        """Quick entry mode: scores only."""
        all_pars = self.selected_course["pars"]
        par_total = sum(all_pars[i] for i in self.holes_to_score)
        holes_text = "Front 9" if self.holes_choice == "front_9" else ("Back 9" if self.holes_choice == "back_9" else f"{len(self.holes_to_score)} Holes")
        yardages = self.selected_course.get("yardages", {}).get(self.selected_tee, [])

        self.log_window.geometry("380x550")
        canvas = tk.Canvas(self.log_window, height=450, width=350)
        scrollbar = ttk.Scrollbar(self.log_window, orient="vertical", command=canvas.yview)
        frame = ttk.Frame(canvas, padding=15)

        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        canvas.create_window((0, 0), window=frame, anchor="nw")

        ttk.Label(frame, text=f"{self.selected_course['name']}", style="Header.TLabel").grid(row=0, column=0, columnspan=4)
        ttk.Label(frame, text=f"{holes_text} • Par {par_total} • {self.selected_tee} Tees").grid(row=1, column=0, columnspan=4, pady=(0, 10))
        ttk.Label(frame, text="Quick Entry Mode", foreground="blue", font=("Helvetica", 9)).grid(row=2, column=0, columnspan=4)

        self.running_total_var = tk.StringVar(value="Total: 0")
        ttk.Label(frame, textvariable=self.running_total_var, font=("Helvetica", 12, "bold")).grid(row=3, column=0, columnspan=4)

        ttk.Label(frame, text="Hole", font=("Helvetica", 9, "bold")).grid(row=4, column=0)
        ttk.Label(frame, text="Yds", font=("Helvetica", 9, "bold")).grid(row=4, column=1)
        ttk.Label(frame, text="Par", font=("Helvetica", 9, "bold")).grid(row=4, column=2)
        ttk.Label(frame, text="Score", font=("Helvetica", 9, "bold")).grid(row=4, column=3)

        self.score_entries = []
        self.score_vars = []
        self.putt_vars = []  # Keep for compatibility but don't display
        self.putt_entries = []

        for idx, hole_num in enumerate(self.holes_to_score):
            row = idx + 5
            par = all_pars[hole_num]
            yard_text = str(yardages[hole_num]) if yardages and hole_num < len(yardages) and yardages[hole_num] > 0 else ""

            ttk.Label(frame, text=f"{hole_num+1}").grid(row=row, column=0, padx=5)
            ttk.Label(frame, text=yard_text).grid(row=row, column=1, padx=5)
            ttk.Label(frame, text=f"{par}").grid(row=row, column=2, padx=5)

            score_var = tk.StringVar()
            score_var.trace_add("write", lambda *args: self.update_running_total())
            self.score_vars.append(score_var)

            score_e = ttk.Entry(frame, width=5, textvariable=score_var)
            score_e.grid(row=row, column=3, padx=5, pady=2)
            self.score_entries.append(score_e)
            
            # Empty putt var for compatibility (not displayed)
            putt_var = tk.StringVar()
            self.putt_vars.append(putt_var)

        ttk.Button(frame, text="✓ Submit Round", command=self.submit_quick_round).grid(row=len(self.holes_to_score)+6, column=0, columnspan=4, pady=20)

        frame.update_idletasks()
        canvas.config(scrollregion=canvas.bbox("all"))
    
    def start_detailed_round_input(self):
        """Detailed entry mode: scores, strokes to green, putts, and clubs used."""
        all_pars = self.selected_course["pars"]
        par_total = sum(all_pars[i] for i in self.holes_to_score)
        holes_text = "Front 9" if self.holes_choice == "front_9" else ("Back 9" if self.holes_choice == "back_9" else f"{len(self.holes_to_score)} Holes")
        yardages = self.selected_course.get("yardages", {}).get(self.selected_tee, [])

        self.log_window.geometry("550x650")
        
        # Main container
        main_frame = ttk.Frame(self.log_window, padding=10)
        main_frame.pack(fill='both', expand=True)
        
        # Header
        ttk.Label(main_frame, text=f"{self.selected_course['name']}", style="Header.TLabel").pack()
        ttk.Label(main_frame, text=f"{holes_text} • Par {par_total} • {self.selected_tee} Tees").pack(pady=(0, 5))
        ttk.Label(main_frame, text="Detailed Entry Mode", foreground="green", font=("Helvetica", 9, "bold")).pack()
        
        # Instructions for auto-calculation
        ttk.Label(main_frame, text="Tap clubs in order used. Score = total clubs tapped.", 
                 font=("Helvetica", 9), foreground="gray").pack(pady=(2, 5))
        
        self.running_total_var = tk.StringVar(value="Total: 0")
        ttk.Label(main_frame, textvariable=self.running_total_var, font=("Helvetica", 12, "bold")).pack(pady=5)
        
        # Scrollable area
        canvas = tk.Canvas(main_frame, height=450)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        frame = ttk.Frame(canvas, padding=10)
        
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        canvas.create_window((0, 0), window=frame, anchor="nw")
        
        # Column headers - Score is now auto-calculated from clubs
        headers = ["Hole", "Yds", "Par", "Score", "Clubs Used"]
        for col, h in enumerate(headers):
            ttk.Label(frame, text=h, font=("Helvetica", 9, "bold")).grid(row=0, column=col, padx=3)
        
        # Data storage
        self.score_entries = []
        self.score_vars = []
        self.score_labels = []  # Display auto-calculated scores
        self.stg_vars = []  # Strokes to green (auto-calculated)
        self.putt_vars = []  # Putts (auto-calculated)
        self.clubs_used_data = []  # List of clubs used per hole
        self.clubs_labels = []  # Labels to display clubs
        
        # Get player's bag for club buttons (include Putter)
        self.player_clubs = self.backend.get_clubs_sorted_by_distance()
        club_names = [c["name"] for c in self.player_clubs]
        # Always add Putter if not in bag
        if "Putter" not in club_names:
            club_names.append("Putter")
        
        for idx, hole_num in enumerate(self.holes_to_score):
            row = idx + 1
            par = all_pars[hole_num]
            yard_text = str(yardages[hole_num]) if yardages and hole_num < len(yardages) and yardages[hole_num] > 0 else ""
            
            ttk.Label(frame, text=f"{hole_num+1}").grid(row=row, column=0, padx=3)
            ttk.Label(frame, text=yard_text).grid(row=row, column=1, padx=3)
            ttk.Label(frame, text=f"{par}").grid(row=row, column=2, padx=3)
            
            # Score display (auto-calculated from clubs)
            score_var = tk.StringVar(value="-")
            self.score_vars.append(score_var)
            score_label = ttk.Label(frame, textvariable=score_var, width=4, anchor='center', 
                                   font=("Helvetica", 10, "bold"))
            score_label.grid(row=row, column=3, padx=3, pady=2)
            self.score_labels.append(score_label)
            
            # Hidden strokes to green and putts (will be auto-calculated from clubs)
            stg_var = tk.StringVar()
            self.stg_vars.append(stg_var)
            
            putt_var = tk.StringVar()
            self.putt_vars.append(putt_var)
            
            # Clubs used - button to open selection
            self.clubs_used_data.append([])
            clubs_label = ttk.Label(frame, text="Select...", foreground="blue", cursor="hand2", width=18)
            clubs_label.grid(row=row, column=4, padx=3, pady=2, sticky='w')
            clubs_label.bind("<Button-1>", lambda e, i=idx, lbl=clubs_label: self.open_club_selector(i, lbl))
            self.clubs_labels.append(clubs_label)
        
        ttk.Button(frame, text="✓ Submit Round", command=self.submit_detailed_round).grid(
            row=len(self.holes_to_score)+2, column=0, columnspan=5, pady=20)
        
        frame.update_idletasks()
        canvas.config(scrollregion=canvas.bbox("all"))
    
    def open_club_selector(self, hole_idx, label_widget):
        """Open a popup to select clubs used for a hole."""
        popup = tk.Toplevel(self.log_window)
        popup.title(f"Clubs Used - Hole {self.holes_to_score[hole_idx] + 1}")
        popup.geometry("380x450")
        popup.transient(self.log_window)
        
        frame = ttk.Frame(popup, padding=15)
        frame.pack(fill='both', expand=True)
        
        ttk.Label(frame, text="Tap clubs in order used:", font=("Helvetica", 10, "bold")).pack(pady=(0, 5))
        ttk.Label(frame, text="Putts = # of Putter taps | To Green = clubs before Putter", 
                 font=("Helvetica", 9), foreground="gray").pack()
        
        # Selected clubs display
        selected_frame = ttk.LabelFrame(frame, text="Selected Order", padding=5)
        selected_frame.pack(fill='x', pady=10)
        
        selected_var = tk.StringVar(value=" → ".join(self.clubs_used_data[hole_idx]) if self.clubs_used_data[hole_idx] else "None")
        selected_label = ttk.Label(selected_frame, textvariable=selected_var, wraplength=300)
        selected_label.pack()
        
        # Local list for this selection
        temp_clubs = list(self.clubs_used_data[hole_idx])
        
        def add_club(club_name):
            temp_clubs.append(club_name)
            selected_var.set(" → ".join(temp_clubs))
        
        def clear_clubs():
            temp_clubs.clear()
            selected_var.set("None")
        
        def undo_last():
            if temp_clubs:
                temp_clubs.pop()
                selected_var.set(" → ".join(temp_clubs) if temp_clubs else "None")
        
        # Club buttons in a grid
        clubs_frame = ttk.Frame(frame)
        clubs_frame.pack(fill='both', expand=True, pady=10)
        
        # Get player's clubs (excluding Putter for now, we'll add it specially)
        player_clubs = [c["name"] for c in self.backend.get_clubs_sorted_by_distance() if c["name"].lower() != "putter"]
        
        # If no clubs in bag, show default list
        if not player_clubs:
            player_clubs = ["Driver", "3 Wood", "5 Wood", "Hybrid", "4 Iron", "5 Iron", "6 Iron", 
                          "7 Iron", "8 Iron", "9 Iron", "PW", "GW", "SW", "LW"]
        
        # Always add Putter at the end
        player_clubs.append("Putter")
        
        col = 0
        row = 0
        for club in player_clubs:
            # Make Putter button stand out
            if club == "Putter":
                btn = ttk.Button(clubs_frame, text="🏌️ Putter", width=10, 
                               command=lambda c=club: add_club(c))
            else:
                btn = ttk.Button(clubs_frame, text=club, width=10, 
                               command=lambda c=club: add_club(c))
            btn.grid(row=row, column=col, padx=2, pady=2)
            col += 1
            if col >= 3:
                col = 0
                row += 1
        
        # Stats display (auto-calculated)
        stats_frame = ttk.LabelFrame(frame, text="Auto-Calculated Stats", padding=5)
        stats_frame.pack(fill='x', pady=5)
        
        stats_var = tk.StringVar(value="Putts: 0 | To Green: 0")
        stats_label = ttk.Label(stats_frame, textvariable=stats_var, font=("Helvetica", 10))
        stats_label.pack()
        
        def update_stats():
            putts = sum(1 for c in temp_clubs if c.lower() == "putter")
            # To green = clubs used before first putter (all non-putter clubs before putting)
            to_green = 0
            for c in temp_clubs:
                if c.lower() == "putter":
                    break
                to_green += 1
            stats_var.set(f"Putts: {putts} | To Green: {to_green}")
        
        # Override add_club to update stats
        def add_club_with_stats(club_name):
            temp_clubs.append(club_name)
            selected_var.set(" → ".join(temp_clubs))
            update_stats()
        
        def clear_clubs_with_stats():
            temp_clubs.clear()
            selected_var.set("None")
            update_stats()
        
        def undo_last_with_stats():
            if temp_clubs:
                temp_clubs.pop()
                selected_var.set(" → ".join(temp_clubs) if temp_clubs else "None")
                update_stats()
        
        # Rebind buttons to use stats-updating versions
        for widget in clubs_frame.winfo_children():
            if isinstance(widget, ttk.Button):
                club_text = widget.cget("text").replace("🏌️ ", "")
                widget.config(command=lambda c=club_text: add_club_with_stats(c))
        
        # Action buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(pady=10)
        
        ttk.Button(btn_frame, text="Undo", command=undo_last_with_stats).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Clear", command=clear_clubs_with_stats).pack(side='left', padx=5)
        
        def save_and_close():
            self.clubs_used_data[hole_idx] = temp_clubs
            # Show abbreviated club list
            if temp_clubs:
                display = ", ".join(temp_clubs[:2])
                if len(temp_clubs) > 2:
                    display += f"... ({len(temp_clubs)})"
            else:
                display = "Select..."
            label_widget.config(text=display)
            
            # Auto-update score from club count
            score = len(temp_clubs)
            if score > 0:
                self.score_vars[hole_idx].set(str(score))
            else:
                self.score_vars[hole_idx].set("-")
            
            # Update running total
            self.update_running_total()
            popup.destroy()
        
        ttk.Button(btn_frame, text="Save", command=save_and_close).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Cancel", command=popup.destroy).pack(side='left', padx=5)
        
        # Initialize stats display
        update_stats()

    def update_running_total(self):
        total = 0
        for var in self.score_vars:
            val = var.get()
            if val.isdigit():
                total += int(val)
        par = sum(self.selected_course["pars"][i] for i in self.holes_to_score)
        diff = total - par
        diff_str = f"+{diff}" if diff > 0 else str(diff)
        self.running_total_var.set(f"Total: {total} ({diff_str})")

    def submit_quick_round(self):
        """Submit a round with quick entry (scores only)."""
        scores = []
        detailed_stats = []
        
        for idx, e in enumerate(self.score_entries):
            v = e.get().strip()
            
            if self.is_serious:
                try:
                    score = int(v)
                    scores.append(score)
                except ValueError:
                    return messagebox.showerror("Error", "All scores must be numbers for serious rounds.")
            else:
                scores.append(int(v) if v.isdigit() else None)
            
            # Build minimal detailed stats (just score for quick mode)
            hole_stats = {"score": scores[-1] if scores else None}
            detailed_stats.append(hole_stats)

        self._save_round(scores, detailed_stats)
    
    def submit_detailed_round(self):
        """Submit a round with detailed entry. Score = number of clubs used."""
        scores = []
        detailed_stats = []
        
        for idx in range(len(self.holes_to_score)):
            clubs = self.clubs_used_data[idx]
            
            # Score is the number of clubs used
            score = len(clubs) if clubs else None
            
            if self.is_serious:
                if not clubs:
                    return messagebox.showerror("Error", f"Hole {self.holes_to_score[idx]+1}: Please select clubs used for all holes in serious rounds.")
                scores.append(score)
            else:
                scores.append(score)
            
            # Build detailed stats - auto-calculate from clubs
            hole_stats = {"score": score}
            
            # Auto-calculate putts: count occurrences of "Putter" in clubs list
            putts = sum(1 for c in clubs if c.lower() == "putter")
            if putts > 0:
                hole_stats["putts"] = putts
            
            # Auto-calculate strokes to green: number of clubs used before first putter
            strokes_to_green = 0
            for c in clubs:
                if c.lower() == "putter":
                    break
                strokes_to_green += 1
            if strokes_to_green > 0:
                hole_stats["strokes_to_green"] = strokes_to_green
            
            if clubs:
                hole_stats["clubs_used"] = clubs
            
            detailed_stats.append(hole_stats)
        
        self._save_round(scores, detailed_stats)
    
    def _save_round(self, scores, detailed_stats):
        """Common method to save round data."""
        total = sum(s for s in scores if s is not None)
        par = sum(self.selected_course["pars"][i] for i in self.holes_to_score)
        holes_played = 9 if self.holes_choice in ["front_9", "back_9"] else (18 if len(scores) >= 18 else len(scores))

        box = next(b for b in self.selected_course["tee_boxes"] if b["color"] == self.selected_tee)
        tee_rating = box["rating"] / 2 if holes_played == 9 else box["rating"]
        tee_slope = box["slope"]

        full_scores = [None] * len(self.selected_course["pars"])
        full_detailed = [{}] * len(self.selected_course["pars"])
        
        for idx, hole_num in enumerate(self.holes_to_score):
            full_scores[hole_num] = scores[idx]
            if idx < len(detailed_stats):
                full_detailed[hole_num] = detailed_stats[idx]

        date_str = self.selected_date.strftime("%Y-%m-%d") + " " + datetime.now().strftime("%H:%M")

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
            "date": date_str,
            "entry_mode": self.entry_mode,
            "detailed_stats": full_detailed
        }

        # Calculate proper target score using course handicap
        course_handicap, target_score = self.backend.calculate_course_handicap(
            self.selected_course["name"], self.selected_tee, self.holes_choice
        )
        if target_score is not None:
            rd["target_score"] = target_score
        else:
            # Fallback if no handicap index established - just use par
            rd["target_score"] = par

        self.backend.rounds.append(rd)
        save_json(ROUNDS_FILE, self.backend.rounds)
        self.backend.invalidate_stats_cache()  # Ensure stats are recalculated
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
                self.export_scorecard_pdf(round_data)
            else:
                self.export_scorecard_image(round_data)
            win.destroy()

        ttk.Button(frame, text="Export", command=do_export).pack(pady=20)
        ttk.Button(frame, text="Cancel", command=win.destroy).pack()

    def export_scorecard_pdf(self, round_data, include_detailed=False):
        sc_data = generate_scorecard_data(self.backend, round_data)
        detailed_stats = round_data.get("detailed_stats", []) if include_detailed else []
        
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
                
                # Add detailed stats rows if requested
                if detailed_stats:
                    has_putts = any(detailed_stats[i].get("putts") is not None for i in range(min(9, len(detailed_stats))) if i < len(detailed_stats) and detailed_stats[i])
                    has_stg = any(detailed_stats[i].get("strokes_to_green") is not None for i in range(min(9, len(detailed_stats))) if i < len(detailed_stats) and detailed_stats[i])
                    
                    if has_putts:
                        putts_row = ['Putts']
                        total_putts = 0
                        for i in range(9):
                            if i < len(detailed_stats) and detailed_stats[i] and detailed_stats[i].get("putts") is not None:
                                putts_row.append(str(detailed_stats[i]["putts"]))
                                total_putts += detailed_stats[i]["putts"]
                            else:
                                putts_row.append("-")
                        putts_row.append(str(total_putts))
                        rows.append(putts_row)
                    
                    if has_stg:
                        stg_row = ['To Green']
                        for i in range(9):
                            if i < len(detailed_stats) and detailed_stats[i] and detailed_stats[i].get("strokes_to_green") is not None:
                                stg_row.append(str(detailed_stats[i]["strokes_to_green"]))
                            else:
                                stg_row.append("-")
                        stg_row.append("-")
                        rows.append(stg_row)

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
                
                # Add detailed stats rows if requested for back 9
                if detailed_stats and len(detailed_stats) > 9:
                    has_putts = any(detailed_stats[i].get("putts") is not None for i in range(9, min(18, len(detailed_stats))) if i < len(detailed_stats) and detailed_stats[i])
                    has_stg = any(detailed_stats[i].get("strokes_to_green") is not None for i in range(9, min(18, len(detailed_stats))) if i < len(detailed_stats) and detailed_stats[i])
                    
                    if has_putts:
                        putts_row = ['Putts']
                        total_putts = 0
                        for i in range(9, 18):
                            if i < len(detailed_stats) and detailed_stats[i] and detailed_stats[i].get("putts") is not None:
                                putts_row.append(str(detailed_stats[i]["putts"]))
                                total_putts += detailed_stats[i]["putts"]
                            else:
                                putts_row.append("-")
                        putts_row.append(str(total_putts))
                        rows.append(putts_row)
                    
                    if has_stg:
                        stg_row = ['To Green']
                        for i in range(9, 18):
                            if i < len(detailed_stats) and detailed_stats[i] and detailed_stats[i].get("strokes_to_green") is not None:
                                stg_row.append(str(detailed_stats[i]["strokes_to_green"]))
                            else:
                                stg_row.append("-")
                        stg_row.append("-")
                        rows.append(stg_row)

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

    def export_scorecard_image(self, round_data, include_detailed=False):
        sc_data = generate_scorecard_data(self.backend, round_data)
        detailed_stats = round_data.get("detailed_stats", []) if include_detailed else []
        has_detailed = bool(detailed_stats and any(
            ds.get("putts") is not None or ds.get("strokes_to_green") is not None 
            for ds in detailed_stats if ds
        ))
        
        filepath = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG files", "*.png")],
            initialfile=f"scorecard_{sc_data['date'][:10]}_{sc_data['course_name'].replace(' ', '_')}.png")
        if not filepath:
            return

        try:
            # Increase height if detailed stats
            width = 800
            height = 600 if has_detailed else 500
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
        win.geometry("650x700")

        # Create scrollable frame
        canvas = tk.Canvas(win)
        scrollbar = ttk.Scrollbar(win, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        
        frame = ttk.Frame(scrollable_frame, padding=20)
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
            f"Serious: {'Yes' if rd['is_serious'] else 'No'}",
            f"Entry Mode: {rd.get('entry_mode', 'quick').title()}"
        ]):
            ttk.Label(info_frame, text=line).grid(row=i//2, column=i%2, padx=10, sticky='w')

        ttk.Label(frame, text="Hole-by-Hole", style="Header.TLabel").pack(pady=(15, 5))

        table_frame = ttk.Frame(frame)
        table_frame.pack()

        # Build pars and yardages
        pars = course["pars"] if course else [4] * len(rd["scores"])
        yardages = course.get("yardages", {}).get(rd.get("tee_color", ""), []) if course else []
        has_yardages = bool(yardages and any(y > 0 for y in yardages))
        
        # Check for detailed stats
        detailed_stats = rd.get("detailed_stats", [])
        has_detailed_stats = any(
            ds.get("putts") is not None or ds.get("strokes_to_green") is not None or ds.get("clubs_used")
            for ds in detailed_stats if ds
        )

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
            # Determine which rows to show
            current_row = 0
            
            # Row labels
            ttk.Label(table_frame, text="Hole", width=6, relief='ridge').grid(row=current_row, column=0, padx=1)
            current_row += 1
            
            ttk.Label(table_frame, text="Par", width=6, relief='ridge').grid(row=current_row, column=0, padx=1)
            current_row += 1
            
            if has_yardages:
                ttk.Label(table_frame, text="Yds", width=6, relief='ridge').grid(row=current_row, column=0, padx=1)
                current_row += 1
            
            ttk.Label(table_frame, text="Score", width=6, relief='ridge').grid(row=current_row, column=0, padx=1)
            score_row = current_row
            current_row += 1
            
            # Add detailed stats rows if available
            putts_row = None
            stg_row = None
            clubs_row = None
            
            if has_detailed_stats:
                # Check what detailed data we have
                has_putts = any(ds.get("putts") is not None for ds in detailed_stats if ds)
                has_stg = any(ds.get("strokes_to_green") is not None for ds in detailed_stats if ds)
                has_clubs = any(ds.get("clubs_used") for ds in detailed_stats if ds)
                
                if has_putts:
                    ttk.Label(table_frame, text="Putts", width=6, relief='ridge', foreground='blue').grid(row=current_row, column=0, padx=1)
                    putts_row = current_row
                    current_row += 1
                
                if has_stg:
                    ttk.Label(table_frame, text="To Grn", width=6, relief='ridge', foreground='blue').grid(row=current_row, column=0, padx=1)
                    stg_row = current_row
                    current_row += 1

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
            for col, hole_idx in enumerate(holes_indices, start=1):
                sc = scores[hole_idx] if hole_idx < len(scores) else None
                s_text = str(sc) if sc is not None else "-"
                ttk.Label(
                    table_frame,
                    text=s_text,
                    width=4,
                    relief='ridge'
                ).grid(row=score_row, column=col)
            
            # Detailed stats rows
            if has_detailed_stats:
                for col, hole_idx in enumerate(holes_indices, start=1):
                    ds = detailed_stats[hole_idx] if hole_idx < len(detailed_stats) else {}
                    
                    if putts_row is not None:
                        putts = ds.get("putts")
                        p_text = str(putts) if putts is not None else "-"
                        ttk.Label(
                            table_frame,
                            text=p_text,
                            width=4,
                            relief='ridge',
                            foreground='blue'
                        ).grid(row=putts_row, column=col)
                    
                    if stg_row is not None:
                        stg = ds.get("strokes_to_green")
                        stg_text = str(stg) if stg is not None else "-"
                        ttk.Label(
                            table_frame,
                            text=stg_text,
                            width=4,
                            relief='ridge',
                            foreground='blue'
                        ).grid(row=stg_row, column=col)
        
        # Show round statistics if detailed stats available
        if has_detailed_stats:
            stats_frame = ttk.LabelFrame(frame, text="Round Statistics", padding=10)
            stats_frame.pack(fill='x', pady=(15, 5))
            
            # Calculate stats from this round
            total_putts = sum(ds.get("putts", 0) for ds in detailed_stats if ds and ds.get("putts"))
            holes_with_putts = sum(1 for ds in detailed_stats if ds and ds.get("putts") is not None)
            avg_putts = round(total_putts / holes_with_putts, 2) if holes_with_putts > 0 else None
            
            three_putts = sum(1 for ds in detailed_stats if ds and ds.get("putts", 0) >= 3)
            one_putts = sum(1 for ds in detailed_stats if ds and ds.get("putts") == 1)
            
            stats_data = []
            if total_putts > 0:
                stats_data.append(f"Total Putts: {total_putts}")
            if avg_putts:
                stats_data.append(f"Avg Putts: {avg_putts}")
            if holes_with_putts > 0:
                stats_data.append(f"3-Putts: {three_putts}")
                stats_data.append(f"1-Putts: {one_putts}")
            
            # Calculate GIR (simplified: strokes_to_green <= par - 2)
            gir_count = 0
            gir_holes = 0
            for idx, ds in enumerate(detailed_stats):
                if ds and ds.get("strokes_to_green") is not None and idx < len(pars):
                    gir_holes += 1
                    if ds["strokes_to_green"] <= pars[idx] - 2:
                        gir_count += 1
            if gir_holes > 0:
                gir_pct = round(gir_count / gir_holes * 100, 1)
                stats_data.append(f"GIR: {gir_count}/{gir_holes} ({gir_pct}%)")
            
            for i, stat in enumerate(stats_data):
                row = i // 3
                col = i % 3
                ttk.Label(stats_frame, text=stat, font=("Helvetica", 10)).grid(row=row, column=col, padx=10, pady=2, sticky='w')
            
            # Show clubs used summary
            all_clubs = []
            for ds in detailed_stats:
                if ds and ds.get("clubs_used"):
                    all_clubs.extend(ds["clubs_used"])
            
            if all_clubs:
                from collections import Counter
                club_counts = Counter(all_clubs)
                clubs_summary = ", ".join([f"{club}: {count}" for club, count in club_counts.most_common(5)])
                ttk.Label(stats_frame, text=f"Top Clubs: {clubs_summary}", 
                         font=("Helvetica", 9), foreground="gray").grid(row=len(stats_data)//3 + 1, column=0, columnspan=3, pady=(5, 0), sticky='w')

        if rd.get("notes"):
            ttk.Label(frame, text="Notes:", style="Header.TLabel").pack(pady=(15, 5))
            ttk.Label(frame, text=rd["notes"], wraplength=400).pack()

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(pady=15)
        ttk.Button(btn_frame, text="Export", command=lambda: self.show_export_dialog_with_options(rd, has_detailed_stats)).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Close", command=win.destroy).pack(side='left', padx=5)
    
    def show_export_dialog_with_options(self, round_data, has_detailed_stats):
        """Show export dialog with option to include detailed stats."""
        win = tk.Toplevel(self.scorecards_window if hasattr(self, 'scorecards_window') else self.root)
        win.title("Export Scorecard")
        win.geometry("350x280" if has_detailed_stats else "300x200")

        frame = ttk.Frame(win, padding=20)
        frame.pack(fill='both', expand=True)

        ttk.Label(frame, text="Export Scorecard", style="Header.TLabel").pack(pady=(0, 15))

        export_format = tk.StringVar(value="pdf")
        ttk.Radiobutton(frame, text="PDF Document", variable=export_format, value="pdf").pack(anchor='w')
        ttk.Radiobutton(frame, text="PNG Image", variable=export_format, value="png").pack(anchor='w')
        
        # Option to include detailed stats
        include_stats = tk.BooleanVar(value=True)
        if has_detailed_stats:
            ttk.Separator(frame, orient='horizontal').pack(fill='x', pady=10)
            ttk.Label(frame, text="Export Options:", font=("Helvetica", 10, "bold")).pack(anchor='w')
            ttk.Checkbutton(frame, text="Include detailed stats (Putts, To Green)", 
                           variable=include_stats).pack(anchor='w', padx=10)

        def do_export():
            fmt = export_format.get()
            include = include_stats.get() if has_detailed_stats else False
            win.destroy()
            if fmt == "pdf":
                self.export_scorecard_pdf(round_data, include_detailed=include)
            else:
                self.export_scorecard_image(round_data, include_detailed=include)

        ttk.Button(frame, text="Export", command=do_export).pack(pady=15)

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
        win.geometry("700x700")

        # Create notebook for tabs
        notebook = ttk.Notebook(win)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Tab 1: Overview
        self._create_overview_tab(notebook)
        
        # Tab 2: Advanced Stats (GIR, Putting)
        self._create_advanced_stats_tab(notebook)
        
        # Tab 3: Club Analytics
        self._create_club_analytics_tab(notebook)
        
        # Tab 4: Stroke Leak Analysis
        self._create_leak_analysis_tab(notebook)
        
        ttk.Button(win, text="Close", command=win.destroy).pack(pady=10)
    
    def _create_overview_tab(self, notebook):
        """Create the overview statistics tab."""
        frame = ttk.Frame(notebook, padding=15)
        notebook.add(frame, text="Overview")
        
        stats = self.backend.get_statistics()
        idx = self.backend.calculate_handicap_index()

        stats_frame = ttk.LabelFrame(frame, text="General Statistics", padding=10)
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
            ttk.Label(stats_frame, text=str(value), font=("Helvetica", 10, "bold")).grid(row=i, column=1, sticky='w', padx=5)

        if idx is None:
            total_holes = stats.get("total_holes_played", 0)
            remaining = max(0, 54 - total_holes)
            if remaining > 0:
                note_frame = ttk.Frame(frame)
                note_frame.pack(fill='x', pady=5)
                ttk.Label(note_frame, text=f"ℹ️ Play {remaining} more holes to establish handicap", foreground='blue').pack()

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
    
    def _create_advanced_stats_tab(self, notebook):
        """Create the advanced statistics tab with GIR and putting stats."""
        frame = ttk.Frame(notebook, padding=15)
        notebook.add(frame, text="Performance")
        
        adv_stats = self.backend.get_advanced_statistics()
        
        if adv_stats.get("total_holes_tracked", 0) == 0:
            ttk.Label(frame, text="No detailed stats available yet.", font=("Helvetica", 12)).pack(pady=20)
            ttk.Label(frame, text="Use 'Detailed' entry mode when logging rounds\nto track strokes to green, putts, and clubs used.", 
                     font=("Helvetica", 10), foreground="gray").pack()
            return
        
        # GIR Stats
        gir_frame = ttk.LabelFrame(frame, text="Greens in Regulation (GIR)", padding=10)
        gir_frame.pack(fill='x', pady=(0, 15))
        
        gir_data = [
            ("Overall GIR:", f"{adv_stats.get('gir_overall')}%" if adv_stats.get('gir_overall') else "N/A"),
            ("Par 3 GIR:", f"{adv_stats.get('gir_par3')}%" if adv_stats.get('gir_par3') else "N/A"),
            ("Par 4 GIR:", f"{adv_stats.get('gir_par4')}%" if adv_stats.get('gir_par4') else "N/A"),
            ("Par 5 GIR:", f"{adv_stats.get('gir_par5')}%" if adv_stats.get('gir_par5') else "N/A"),
        ]
        
        for i, (label, value) in enumerate(gir_data):
            ttk.Label(gir_frame, text=label).grid(row=i//2, column=(i%2)*2, sticky='e', padx=5, pady=2)
            ttk.Label(gir_frame, text=value, font=("Helvetica", 10, "bold")).grid(row=i//2, column=(i%2)*2+1, sticky='w', padx=5, pady=2)
        
        # Strokes to Green
        stg_frame = ttk.LabelFrame(frame, text="Average Strokes to Reach Green", padding=10)
        stg_frame.pack(fill='x', pady=(0, 15))
        
        stg_data = [
            ("Par 3 (target: 1):", f"{adv_stats.get('avg_strokes_to_green_par3')}" if adv_stats.get('avg_strokes_to_green_par3') else "N/A"),
            ("Par 4 (target: 2):", f"{adv_stats.get('avg_strokes_to_green_par4')}" if adv_stats.get('avg_strokes_to_green_par4') else "N/A"),
            ("Par 5 (target: 3):", f"{adv_stats.get('avg_strokes_to_green_par5')}" if adv_stats.get('avg_strokes_to_green_par5') else "N/A"),
        ]
        
        for i, (label, value) in enumerate(stg_data):
            ttk.Label(stg_frame, text=label).grid(row=i, column=0, sticky='e', padx=5, pady=2)
            ttk.Label(stg_frame, text=value, font=("Helvetica", 10, "bold")).grid(row=i, column=1, sticky='w', padx=5, pady=2)
        
        # Putting Stats
        putt_frame = ttk.LabelFrame(frame, text="Putting Statistics", padding=10)
        putt_frame.pack(fill='x', pady=(0, 15))
        
        putt_data = [
            ("Avg Putts/Hole:", f"{adv_stats.get('avg_putts_overall')}" if adv_stats.get('avg_putts_overall') else "N/A"),
            ("3-Putt Rate:", f"{adv_stats.get('three_putt_rate')}%" if adv_stats.get('three_putt_rate') else "N/A"),
            ("1-Putt Rate:", f"{adv_stats.get('one_putt_rate')}%" if adv_stats.get('one_putt_rate') else "N/A"),
        ]
        
        for i, (label, value) in enumerate(putt_data):
            ttk.Label(putt_frame, text=label).grid(row=0, column=i*2, sticky='e', padx=5, pady=2)
            ttk.Label(putt_frame, text=value, font=("Helvetica", 10, "bold")).grid(row=0, column=i*2+1, sticky='w', padx=5, pady=2)
        
        # Scrambling
        scramble_frame = ttk.LabelFrame(frame, text="Scrambling", padding=10)
        scramble_frame.pack(fill='x')
        
        scramble_rate = adv_stats.get('scramble_rate')
        scramble_opps = adv_stats.get('scramble_opportunities', 0)
        scramble_succ = adv_stats.get('scramble_successes', 0)
        
        ttk.Label(scramble_frame, text="Scramble Rate:").grid(row=0, column=0, sticky='e', padx=5)
        ttk.Label(scramble_frame, text=f"{scramble_rate}%" if scramble_rate else "N/A", 
                 font=("Helvetica", 10, "bold")).grid(row=0, column=1, sticky='w', padx=5)
        ttk.Label(scramble_frame, text=f"({scramble_succ}/{scramble_opps} saves)", 
                 foreground="gray").grid(row=0, column=2, sticky='w', padx=5)
        
        ttk.Label(frame, text=f"Based on {adv_stats.get('total_holes_tracked', 0)} holes tracked", 
                 foreground="gray", font=("Helvetica", 9)).pack(pady=10)
    
    def _create_club_analytics_tab(self, notebook):
        """Create the club usage analytics tab."""
        frame = ttk.Frame(notebook, padding=15)
        notebook.add(frame, text="Club Analytics")
        
        club_stats = self.backend.get_club_analytics()
        
        if club_stats.get("total_shots", 0) == 0:
            ttk.Label(frame, text="No club usage data available yet.", font=("Helvetica", 12)).pack(pady=20)
            ttk.Label(frame, text="Use 'Detailed' entry mode when logging rounds\nto track which clubs you use on each hole.", 
                     font=("Helvetica", 10), foreground="gray").pack()
            return
        
        # Most Used Clubs
        usage_frame = ttk.LabelFrame(frame, text="Club Usage (Most → Least)", padding=10)
        usage_frame.pack(fill='both', expand=True, pady=(0, 15))
        
        cols = ("Club", "Shots", "Usage %")
        tree = ttk.Treeview(usage_frame, columns=cols, show="headings", height=10)
        tree.heading("Club", text="Club")
        tree.heading("Shots", text="Shots")
        tree.heading("Usage %", text="Usage %")
        tree.column("Club", width=120)
        tree.column("Shots", width=80, anchor='center')
        tree.column("Usage %", width=80, anchor='center')
        tree.pack(fill='both', expand=True)
        
        for club_data in club_stats.get("ranked_clubs", []):
            tree.insert("", "end", values=(club_data["name"], club_data["count"], f"{club_data['percentage']}%"))
        
        # Rarely/Never Used
        insight_frame = ttk.LabelFrame(frame, text="Bag Health Insights", padding=10)
        insight_frame.pack(fill='x')
        
        rarely_used = club_stats.get("rarely_used", [])
        never_used = club_stats.get("never_used", [])
        
        row = 0
        if rarely_used:
            rarely_names = [c["name"] for c in rarely_used]
            ttk.Label(insight_frame, text="⚠️ Rarely used (<3%):", foreground="orange").grid(row=row, column=0, sticky='w', padx=5)
            ttk.Label(insight_frame, text=", ".join(rarely_names), wraplength=300).grid(row=row, column=1, sticky='w', padx=5)
            row += 1
        
        if never_used:
            ttk.Label(insight_frame, text="❌ Never used:", foreground="red").grid(row=row, column=0, sticky='w', padx=5)
            ttk.Label(insight_frame, text=", ".join(never_used), wraplength=300).grid(row=row, column=1, sticky='w', padx=5)
            row += 1
        
        if not rarely_used and not never_used:
            ttk.Label(insight_frame, text="✅ All clubs in your bag are being used!", foreground="green").grid(row=0, column=0, columnspan=2, padx=5)
        
        ttk.Label(frame, text=f"Total shots tracked: {club_stats.get('total_shots', 0)}", 
                 foreground="gray", font=("Helvetica", 9)).pack(pady=5)
    
    def _create_leak_analysis_tab(self, notebook):
        """Create the stroke leak analysis tab."""
        frame = ttk.Frame(notebook, padding=15)
        notebook.add(frame, text="Where You Lose Strokes")
        
        insights = self.backend.get_stroke_leak_analysis()
        
        if not insights:
            adv_stats = self.backend.get_advanced_statistics()
            if adv_stats.get("total_holes_tracked", 0) == 0:
                ttk.Label(frame, text="No data available for analysis.", font=("Helvetica", 12)).pack(pady=20)
                ttk.Label(frame, text="Use 'Detailed' entry mode when logging rounds\nto enable stroke leak analysis.", 
                         font=("Helvetica", 10), foreground="gray").pack()
            else:
                ttk.Label(frame, text="🎉 Great job!", font=("Helvetica", 14, "bold")).pack(pady=20)
                ttk.Label(frame, text="No significant areas of concern detected\nin your recent rounds.", 
                         font=("Helvetica", 11)).pack()
            return
        
        ttk.Label(frame, text="Areas to Focus On", font=("Helvetica", 14, "bold")).pack(pady=(0, 15))
        
        for insight in insights:
            severity = insight.get("severity", "medium")
            color = "red" if severity == "high" else "orange"
            icon = "🔴" if severity == "high" else "🟡"
            
            insight_frame = ttk.Frame(frame)
            insight_frame.pack(fill='x', pady=5)
            
            ttk.Label(insight_frame, text=icon, font=("Helvetica", 12)).pack(side='left', padx=(0, 10))
            ttk.Label(insight_frame, text=insight["message"], wraplength=500, 
                     font=("Helvetica", 11)).pack(side='left', fill='x')
        
        # Summary recommendation
        ttk.Separator(frame, orient='horizontal').pack(fill='x', pady=15)
        
        # Find the biggest leak
        if insights:
            biggest = insights[0]
            area = biggest.get("area", "")
            
            rec_frame = ttk.LabelFrame(frame, text="💡 Recommendation", padding=10)
            rec_frame.pack(fill='x')
            
            if "putt" in area:
                rec_text = "Consider practicing lag putting to reduce 3-putts,\nor work on short putts inside 6 feet."
            elif "approach" in area or "stg" in area:
                rec_text = "Focus on approach shot accuracy.\nConsider working on your 100-150 yard shots."
            elif "tee" in area or "par3" in area:
                rec_text = "Work on tee shot accuracy on par 3s.\nClub selection might be an area to review."
            elif "gir" in area:
                rec_text = "Improving your approach play will help\nyou hit more greens in regulation."
            else:
                rec_text = "Review your recent rounds to identify\npatterns in your mistakes."
            
            ttk.Label(rec_frame, text=rec_text, font=("Helvetica", 10), wraplength=400).pack()


if __name__ == "__main__":
    root = tk.Tk()
    app = GolfApp(root)
    root.mainloop()