"""
Hole Plan UI Module for Golf App.
Provides strategy planning interface for individual holes.

Allows users to:
- View hole yardages and features
- Plan shots with target selection
- Assign clubs to each shot
- Add notes per shot and per hole
- Save plans to courses.json
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime
import json
import os

from ui_layout import autosize_toplevel, ScrollableFrame, CollapsibleSection


# Default clubs list (used when user has no clubs configured)
DEFAULT_CLUBS = [
    "Driver", "3 Wood", "5 Wood", "Hybrid", "3 Iron", "4 Iron", 
    "5 Iron", "6 Iron", "7 Iron", "8 Iron", "9 Iron", 
    "PW", "GW", "SW", "LW", "Putter"
]


class HolePlanWindow:
    """
    Window for creating and editing hole strategy plans.
    """
    
    def __init__(
        self,
        parent: tk.Tk,
        backend: Any,
        courses_file: str,
        yardbook_integration: Optional[Any] = None,
        initial_course: Optional[str] = None,
        initial_hole: int = 1,
        initial_tee: Optional[str] = None
    ):
        """
        Initialize the Hole Plan window.
        
        Args:
            parent: Parent Tkinter window
            backend: GolfBackend instance
            courses_file: Path to courses.json
            yardbook_integration: Optional yardbookIntegration for distances
            initial_course: Course name to pre-select
            initial_hole: Hole number to pre-select
            initial_tee: Tee box to pre-select
        """
        self.parent = parent
        self.backend = backend
        self.courses_file = courses_file
        self.yardbook = yardbook_integration
        
        # State
        self.current_course: Optional[Dict] = None
        self.current_hole = initial_hole
        self.current_tee = initial_tee
        self.current_plan: Dict = {}
        self.shots: List[Dict] = []
        self.unsaved_changes = False
        
        # Get user's clubs
        self.user_clubs = self._get_user_clubs()
        
        # Create window
        self._create_window()
        self._create_ui()
        
        # Initialize with provided course if any
        if initial_course:
            self._select_course_by_name(initial_course)
        
        # Auto-size
        autosize_toplevel(self.window, min_size=(600, 500), max_ratio=0.85)
    
    def _get_user_clubs(self) -> List[str]:
        """Get list of clubs from user's bag."""
        try:
            clubs = self.backend.get_clubs()
            if clubs:
                return [c["name"] for c in clubs]
        except:
            pass
        return DEFAULT_CLUBS
    
    def _create_window(self):
        """Create the main window."""
        self.window = tk.Toplevel(self.parent)
        self.window.title("Hole Plan - Strategy Builder")
        self.window.geometry("700x600")
        self.window.minsize(600, 500)
        
        # Handle close
        self.window.protocol("WM_DELETE_WINDOW", self._on_close)
    
    def _create_ui(self):
        """Create the UI components."""
        main_frame = ttk.Frame(self.window, padding=10)
        main_frame.pack(fill='both', expand=True)
        
        # Top section: Course/Hole/Tee selection
        self._create_selection_section(main_frame)
        
        # Middle section: Hole info and distances
        self._create_info_section(main_frame)
        
        # Main section: Shot planning
        self._create_shot_planning_section(main_frame)
        
        # Bottom: Buttons
        self._create_button_bar(main_frame)
    
    def _create_selection_section(self, parent: ttk.Frame):
        """Create the course/hole/tee selection section."""
        sel_frame = ttk.LabelFrame(parent, text="Select Hole", padding=10)
        sel_frame.pack(fill='x', pady=(0, 10))
        
        # Course selection
        ttk.Label(sel_frame, text="Course:").grid(row=0, column=0, sticky='e', padx=5)
        self.course_var = tk.StringVar()
        self.course_combo = ttk.Combobox(
            sel_frame,
            textvariable=self.course_var,
            state='readonly',
            width=30
        )
        self.course_combo.grid(row=0, column=1, padx=5, pady=3)
        self.course_combo.bind('<<ComboboxSelected>>', self._on_course_change)
        
        # Populate courses
        courses = self.backend.get_courses()
        course_names = [c["name"] for c in sorted(courses, key=lambda x: x.get("name", ""))]
        self.course_combo['values'] = course_names
        
        # Tee selection
        ttk.Label(sel_frame, text="Tee:").grid(row=0, column=2, sticky='e', padx=5)
        self.tee_var = tk.StringVar()
        self.tee_combo = ttk.Combobox(
            sel_frame,
            textvariable=self.tee_var,
            state='readonly',
            width=12
        )
        self.tee_combo.grid(row=0, column=3, padx=5, pady=3)
        self.tee_combo.bind('<<ComboboxSelected>>', self._on_tee_change)
        
        # Hole selection
        ttk.Label(sel_frame, text="Hole:").grid(row=1, column=0, sticky='e', padx=5)
        
        hole_frame = ttk.Frame(sel_frame)
        hole_frame.grid(row=1, column=1, columnspan=3, sticky='w', padx=5, pady=5)
        
        self.hole_buttons: Dict[int, ttk.Button] = {}
        self.hole_var = tk.IntVar(value=1)
        
        for i in range(18):
            hole_num = i + 1
            btn = ttk.Button(
                hole_frame,
                text=str(hole_num),
                width=3,
                command=lambda h=hole_num: self._select_hole(h)
            )
            btn.grid(row=i // 9, column=i % 9, padx=1, pady=1)
            self.hole_buttons[hole_num] = btn
    
    def _create_info_section(self, parent: ttk.Frame):
        """Create the hole info and distances section."""
        info_frame = ttk.LabelFrame(parent, text="Hole Information", padding=10)
        info_frame.pack(fill='x', pady=(0, 10))
        
        # Hole details row
        details_frame = ttk.Frame(info_frame)
        details_frame.pack(fill='x')
        
        self.hole_label = ttk.Label(
            details_frame, 
            text="Select a course and hole",
            font=("Helvetica", 12, "bold")
        )
        self.hole_label.pack(side='left')
        
        self.par_label = ttk.Label(details_frame, text="")
        self.par_label.pack(side='left', padx=20)
        
        self.yardage_label = ttk.Label(details_frame, text="")
        self.yardage_label.pack(side='left', padx=20)
        
        # Yardbook distances (if available)
        self.distances_frame = ttk.Frame(info_frame)
        self.distances_frame.pack(fill='x', pady=(10, 0))
        
        self.distances_labels: Dict[str, ttk.Label] = {}
    
    def _create_shot_planning_section(self, parent: ttk.Frame):
        """Create the main shot planning section."""
        plan_frame = ttk.LabelFrame(parent, text="Shot Plan", padding=10)
        plan_frame.pack(fill='both', expand=True, pady=(0, 10))
        
        # Scrollable area for shots
        self.shots_scroll = ScrollableFrame(plan_frame, max_height=300)
        self.shots_scroll.pack(fill='both', expand=True)
        
        self.shots_container = self.shots_scroll.inner_frame
        
        # Add shot button
        btn_frame = ttk.Frame(plan_frame)
        btn_frame.pack(fill='x', pady=(10, 0))
        
        ttk.Button(
            btn_frame, 
            text="➕ Add Shot", 
            command=self._add_shot
        ).pack(side='left')
        
        ttk.Button(
            btn_frame,
            text="🗑 Clear Plan",
            command=self._clear_plan
        ).pack(side='left', padx=10)
        
        # General notes
        notes_frame = ttk.LabelFrame(parent, text="General Notes for Hole", padding=5)
        notes_frame.pack(fill='x', pady=(0, 10))
        
        self.general_notes = tk.Text(notes_frame, height=3, width=60)
        self.general_notes.pack(fill='x')
        self.general_notes.bind('<KeyRelease>', lambda e: self._mark_unsaved())
    
    def _create_button_bar(self, parent: ttk.Frame):
        """Create the bottom button bar."""
        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill='x')
        
        ttk.Button(
            btn_frame,
            text="💾 Save Plan",
            command=self._save_plan
        ).pack(side='right', padx=5)
        
        ttk.Button(
            btn_frame,
            text="Cancel",
            command=self._on_close
        ).pack(side='right', padx=5)
        
        # Navigation buttons
        ttk.Button(
            btn_frame,
            text="◀ Prev Hole",
            command=self._prev_hole
        ).pack(side='left', padx=5)
        
        ttk.Button(
            btn_frame,
            text="Next Hole ▶",
            command=self._next_hole
        ).pack(side='left', padx=5)
    
    def _select_course_by_name(self, course_name: str):
        """Select a course by name."""
        self.course_var.set(course_name)
        self._on_course_change()
    
    def _on_course_change(self, event=None):
        """Handle course selection change."""
        course_name = self.course_var.get()
        self.current_course = self.backend.get_course_by_name(course_name)
        
        if not self.current_course:
            return
        
        # Update tee options
        tee_boxes = self.current_course.get("tee_boxes", [])
        tee_colors = [tb.get("color", "") for tb in tee_boxes]
        self.tee_combo['values'] = tee_colors
        
        if tee_colors:
            if self.current_tee and self.current_tee in tee_colors:
                self.tee_var.set(self.current_tee)
            else:
                self.tee_var.set(tee_colors[0])
        
        # Update hole buttons state
        num_holes = len(self.current_course.get("pars", []))
        for hole_num, btn in self.hole_buttons.items():
            if hole_num <= num_holes:
                btn.config(state='normal')
                # Check if hole has a plan
                if self._hole_has_plan(hole_num):
                    btn.config(text=f"✓{hole_num}")
                else:
                    btn.config(text=str(hole_num))
            else:
                btn.config(state='disabled')
        
        # Select first hole
        self._select_hole(1)
    
    def _on_tee_change(self, event=None):
        """Handle tee selection change."""
        self.current_tee = self.tee_var.get()
        self._update_hole_info()
    
    def _hole_has_plan(self, hole_num: int) -> bool:
        """Check if a hole has a saved plan."""
        if not self.current_course:
            return False
        
        holes = self.current_course.get("holes", {})
        hole_data = holes.get(str(hole_num), {})
        plans = hole_data.get("hole_plans", {})
        
        return len(plans) > 0
    
    def _select_hole(self, hole_num: int):
        """Select a hole and load its plan."""
        if self.unsaved_changes:
            if not self._confirm_discard():
                return
        
        self.current_hole = hole_num
        self.hole_var.set(hole_num)
        
        # Update button highlighting
        for h, btn in self.hole_buttons.items():
            if h == hole_num:
                btn.state(['pressed'])
            else:
                btn.state(['!pressed'])
        
        # Update info and load plan
        self._update_hole_info()
        self._load_current_plan()
        self.unsaved_changes = False
    
    def _update_hole_info(self):
        """Update the hole information display."""
        if not self.current_course:
            self.hole_label.config(text="Select a course")
            return
        
        pars = self.current_course.get("pars", [])
        if self.current_hole <= len(pars):
            par = pars[self.current_hole - 1]
        else:
            par = 4
        
        self.hole_label.config(text=f"Hole {self.current_hole}")
        self.par_label.config(text=f"Par {par}")
        
        # Get yardage
        yardages = self.current_course.get("yardages", {})
        tee_yardages = yardages.get(self.current_tee, [])
        if self.current_hole <= len(tee_yardages):
            yardage = tee_yardages[self.current_hole - 1]
            self.yardage_label.config(text=f"{yardage} yards ({self.current_tee})")
        else:
            self.yardage_label.config(text="")
        
        # Update yardbook distances if available
        self._update_yardbook_distances()
    
    def _update_yardbook_distances(self):
        """Update the yardbook distance display."""
        # Clear existing labels
        for widget in self.distances_frame.winfo_children():
            widget.destroy()
        self.distances_labels.clear()
        
        if not self.yardbook or not self.current_course:
            return
        
        # Get distances from yardbook
        distances = self.yardbook.get_hole_distances(
            self.current_course["name"], 
            self.current_hole
        )
        
        if not distances:
            ttk.Label(
                self.distances_frame,
                text="No yardbook data for this hole",
                foreground="gray"
            ).pack(anchor='w')
            return
        
        # Display main distances
        dist_texts = []
        
        if distances.get("tee_to_green_front"):
            dist_texts.append(f"Front: {distances['tee_to_green_front']:.0f}y")
        
        if distances.get("tee_to_green_center"):
            dist_texts.append(f"Center: {distances['tee_to_green_center']:.0f}y")
        
        if distances.get("tee_to_green_back"):
            dist_texts.append(f"Back: {distances['tee_to_green_back']:.0f}y")
        
        if dist_texts:
            ttk.Label(
                self.distances_frame,
                text="📍 " + " | ".join(dist_texts),
                font=("Helvetica", 10)
            ).pack(anchor='w')
        
        # Display targets
        for target in distances.get("targets", []):
            text = f"◎ {target['name']}: {target['from_tee']:.0f}y from tee"
            if target.get("to_green"):
                text += f" → {target['to_green']:.0f}y to green"
            ttk.Label(
                self.distances_frame,
                text=text,
                foreground="gray"
            ).pack(anchor='w')
    
    def _load_current_plan(self):
        """Load the plan for the current hole."""
        # Clear existing shots UI
        for widget in self.shots_container.winfo_children():
            widget.destroy()
        self.shots.clear()
        
        # Clear general notes
        self.general_notes.delete('1.0', tk.END)
        
        if not self.current_course:
            return
        
        # Load plan from course data
        holes = self.current_course.get("holes", {})
        hole_data = holes.get(str(self.current_hole), {})
        plans = hole_data.get("hole_plans", {})
        
        # Get plan for current tee
        tee_key = self.current_tee or "default"
        plan = plans.get(tee_key, {})
        
        self.current_plan = plan
        
        # Load shots
        for shot_data in plan.get("shots", []):
            self._add_shot_ui(shot_data)
        
        # Load general notes
        notes = plan.get("general_notes", "")
        if notes:
            self.general_notes.insert('1.0', notes)
        
        # If no shots exist, add one empty shot
        if not self.shots:
            self._add_shot()
    
    def _add_shot(self):
        """Add a new shot to the plan."""
        shot_num = len(self.shots) + 1
        shot_data = {
            "shot": shot_num,
            "club": "",
            "aim": "",
            "target_marker_id": "",
            "notes": ""
        }
        self._add_shot_ui(shot_data)
        self._mark_unsaved()
    
    def _add_shot_ui(self, shot_data: Dict):
        """Add a shot entry UI."""
        shot_num = len(self.shots) + 1
        
        frame = ttk.Frame(self.shots_container, padding=5)
        frame.pack(fill='x', pady=2)
        
        # Shot number
        ttk.Label(
            frame, 
            text=f"Shot {shot_num}:", 
            font=("Helvetica", 10, "bold"),
            width=8
        ).pack(side='left')
        
        # Club selection
        ttk.Label(frame, text="Club:").pack(side='left', padx=(10, 2))
        club_var = tk.StringVar(value=shot_data.get("club", ""))
        club_combo = ttk.Combobox(
            frame,
            textvariable=club_var,
            values=self.user_clubs,
            width=12
        )
        club_combo.pack(side='left')
        club_combo.bind('<<ComboboxSelected>>', lambda e: self._mark_unsaved())
        club_combo.bind('<KeyRelease>', lambda e: self._mark_unsaved())
        
        # Aim/target
        ttk.Label(frame, text="Aim:").pack(side='left', padx=(10, 2))
        aim_var = tk.StringVar(value=shot_data.get("aim", ""))
        aim_entry = ttk.Entry(frame, textvariable=aim_var, width=20)
        aim_entry.pack(side='left')
        aim_entry.bind('<KeyRelease>', lambda e: self._mark_unsaved())
        
        # Notes
        ttk.Label(frame, text="Notes:").pack(side='left', padx=(10, 2))
        notes_var = tk.StringVar(value=shot_data.get("notes", ""))
        notes_entry = ttk.Entry(frame, textvariable=notes_var, width=25)
        notes_entry.pack(side='left', fill='x', expand=True)
        notes_entry.bind('<KeyRelease>', lambda e: self._mark_unsaved())
        
        # Delete button
        def delete_shot():
            self.shots.remove(shot_entry)
            frame.destroy()
            self._renumber_shots()
            self._mark_unsaved()
        
        ttk.Button(
            frame,
            text="✕",
            width=3,
            command=delete_shot
        ).pack(side='right', padx=5)
        
        # Store entry
        shot_entry = {
            "frame": frame,
            "club_var": club_var,
            "aim_var": aim_var,
            "notes_var": notes_var,
            "target_marker_id": shot_data.get("target_marker_id", "")
        }
        self.shots.append(shot_entry)
    
    def _renumber_shots(self):
        """Renumber shots after deletion."""
        for i, shot in enumerate(self.shots):
            # Find and update the label
            for widget in shot["frame"].winfo_children():
                if isinstance(widget, ttk.Label):
                    text = widget.cget("text")
                    if text.startswith("Shot"):
                        widget.config(text=f"Shot {i + 1}:")
                        break
    
    def _clear_plan(self):
        """Clear the current plan."""
        if self.shots or self.general_notes.get('1.0', 'end-1c'):
            if not messagebox.askyesno("Clear Plan", "Clear all shots and notes for this hole?"):
                return
        
        for widget in self.shots_container.winfo_children():
            widget.destroy()
        self.shots.clear()
        self.general_notes.delete('1.0', tk.END)
        
        # Add one empty shot
        self._add_shot()
        self._mark_unsaved()
    
    def _save_plan(self):
        """Save the current plan to courses.json."""
        if not self.current_course:
            messagebox.showwarning("Warning", "Please select a course first.")
            return
        
        # Build plan data
        shots_data = []
        for i, shot in enumerate(self.shots):
            club = shot["club_var"].get().strip()
            aim = shot["aim_var"].get().strip()
            notes = shot["notes_var"].get().strip()
            
            # Skip completely empty shots
            if not club and not aim and not notes:
                continue
            
            shots_data.append({
                "shot": i + 1,
                "club": club,
                "aim": aim,
                "target_marker_id": shot.get("target_marker_id", ""),
                "notes": notes
            })
        
        general_notes = self.general_notes.get('1.0', 'end-1c').strip()
        
        plan_data = {
            "tee_box": self.current_tee or "default",
            "updated_at": datetime.now().isoformat(),
            "shots": shots_data,
            "general_notes": general_notes
        }
        
        # Save to courses.json
        try:
            self._save_plan_to_file(plan_data)
            self.unsaved_changes = False
            
            # Update button to show plan exists
            if shots_data or general_notes:
                self.hole_buttons[self.current_hole].config(
                    text=f"✓{self.current_hole}"
                )
            
            messagebox.showinfo("Saved", f"Plan saved for Hole {self.current_hole}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save plan: {e}")
    
    def _save_plan_to_file(self, plan_data: Dict):
        """Save plan data to the courses.json file."""
        # Load current courses
        if os.path.exists(self.courses_file):
            with open(self.courses_file, 'r') as f:
                courses = json.load(f)
        else:
            courses = []
        
        # Find and update the course
        for course in courses:
            if course.get("name") == self.current_course["name"]:
                # Ensure holes dict exists
                if "holes" not in course:
                    course["holes"] = {}
                
                hole_key = str(self.current_hole)
                if hole_key not in course["holes"]:
                    course["holes"][hole_key] = {}
                
                # Ensure hole_plans dict exists
                if "hole_plans" not in course["holes"][hole_key]:
                    course["holes"][hole_key]["hole_plans"] = {}
                
                # Save plan for current tee
                tee_key = self.current_tee or "default"
                course["holes"][hole_key]["hole_plans"][tee_key] = plan_data
                
                break
        
        # Save back to file
        with open(self.courses_file, 'w') as f:
            json.dump(courses, f, indent=2)
        
        # Update local course data
        self.current_course = self.backend.get_course_by_name(self.current_course["name"])
    
    def _prev_hole(self):
        """Go to previous hole."""
        if self.current_hole > 1:
            self._select_hole(self.current_hole - 1)
        elif self.current_course:
            num_holes = len(self.current_course.get("pars", []))
            self._select_hole(num_holes)
    
    def _next_hole(self):
        """Go to next hole."""
        if not self.current_course:
            return
        
        num_holes = len(self.current_course.get("pars", []))
        if self.current_hole < num_holes:
            self._select_hole(self.current_hole + 1)
        else:
            self._select_hole(1)
    
    def _mark_unsaved(self):
        """Mark that there are unsaved changes."""
        self.unsaved_changes = True
    
    def _confirm_discard(self) -> bool:
        """Ask user to confirm discarding changes."""
        return messagebox.askyesno(
            "Unsaved Changes",
            "You have unsaved changes. Discard them?"
        )
    
    def _on_close(self):
        """Handle window close."""
        if self.unsaved_changes:
            if not self._confirm_discard():
                return
        self.window.destroy()


def open_hole_plan(
    parent: tk.Tk,
    backend: Any,
    courses_file: str,
    yardbook_integration: Optional[Any] = None,
    course_name: Optional[str] = None,
    hole_num: int = 1,
    tee: Optional[str] = None
) -> HolePlanWindow:
    """
    Open the Hole Plan window.
    
    Args:
        parent: Parent Tkinter window
        backend: GolfBackend instance
        courses_file: Path to courses.json
        yardbook_integration: Optional yardbookIntegration instance
        course_name: Course to pre-select
        hole_num: Hole number to pre-select
        tee: Tee box to pre-select
    
    Returns:
        HolePlanWindow instance
    """
    return HolePlanWindow(
        parent=parent,
        backend=backend,
        courses_file=courses_file,
        yardbook_integration=yardbook_integration,
        initial_course=course_name,
        initial_hole=hole_num,
        initial_tee=tee
    )