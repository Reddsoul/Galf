"""
yardbook Integration Module.
Provides the interface between the existing Golf App and the new yardbook feature.

Usage in Frontend.py:
    from yardbook_integration import yardbookIntegration
    
    # In GolfApp.__init__:
    self.yardbook = yardbookIntegration(self.backend, COURSES_FILE)
    
    # Add button:
    ttk.Button(btn_frame, text="📍 yardbook", command=self.open_yardbook_selector).pack(pady=3)
    
    # Add method:
    def open_yardbook_selector(self):
        self.yardbook.show_course_selector(self.root)
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, Optional, Callable, Any

# Import yardbook modules
from yardbook_ui import yardbookView, open_yardbook, MAP_AVAILABLE
from yardbook_data import yardbookManager
from yardbook_geo import calculate_hole_distances


class yardbookIntegration:
    """
    Integration layer between the Golf App and yardbook feature.
    Handles course/hole selection and yardbook launch.
    """
    
    def __init__(self, backend: Any, courses_file: str):
        """
        Initialize the integration.
        
        Args:
            backend: GolfBackend instance
            courses_file: Path to courses.json
        """
        self.backend = backend
        self.courses_file = courses_file
        
        self.manager = yardbookManager(courses_file)

        
        self.active_yardbook: Optional[yardbookView] = None
    
    def is_available(self) -> bool:
        """Check if yardbook feature is available."""
        return MAP_AVAILABLE
    
    def show_course_selector(self, parent: tk.Tk):
        """
        Show the course/hole selector dialog.
        
        Args:
            parent: Parent Tkinter window
        """
        if not self.is_available():
            messagebox.showerror(
                "Feature Unavailable",
                "The yardbook feature requires additional dependencies.\n\n"
                "Please install:\n"
                "  pip install tkintermapview\n\n"
                "Then restart the application."
            )
            return
        
        selector = CourseHoleSelector(
            parent=parent,
            backend=self.backend,
            manager=self.manager,
            on_select=lambda course, hole: self._launch_yardbook(parent, course, hole)
        )
    
    def _launch_yardbook(self, parent: tk.Tk, course_data: Dict, hole_num: int):
        """Launch the yardbook view for a specific hole."""
        # Close existing yardbook if open
        if self.active_yardbook:
            try:
                self.active_yardbook.window.destroy()
            except:
                pass
        
        self.active_yardbook = open_yardbook(
            parent=parent,
            course_data=course_data,
            hole_num=hole_num,
            courses_file=self.courses_file,
            on_save_callback=lambda: self._on_yardbook_save(course_data["name"])
        )
    
    def _on_yardbook_save(self, course_name: str):
        """Callback when yardbook data is saved."""
        # Invalidate any caches
        if self.manager:
            self.manager.invalidate_cache(course_name)
    
    def open_hole_direct(self, parent: tk.Tk, course_name: str, hole_num: int):
        """
        Open yardbook directly for a specific course and hole.
        Useful for integration from scorecard view.
        
        Args:
            parent: Parent window
            course_name: Name of the course
            hole_num: Hole number (1-18)
        """
        if not self.is_available():
            messagebox.showerror("Feature Unavailable", "yardbook feature is not available.")
            return
        
        course_data = self.backend.get_course_by_name(course_name)
        if not course_data:
            messagebox.showerror("Error", f"Course '{course_name}' not found.")
            return
        
        self._launch_yardbook(parent, course_data, hole_num)
    
    def get_hole_distances(self, course_name: str, hole_num: int) -> Optional[Dict]:
        """
        Get calculated distances for a hole (for display in other parts of the app).
        
        Args:
            course_name: Course name
            hole_num: Hole number
        
        Returns:
            Dictionary of distances or None if no yardbook data
        """
        if not self.manager:
            return None
        
        features = self.manager.get_hole_features(course_name, hole_num)
        if not features.has_data():
            return None
        
        map_features_dict = {
            "tee": features.tee.to_dict(),
            "green_front": features.green_front.to_dict(),
            "green_back": features.green_back.to_dict(),
            "targets": [t.to_dict() for t in features.targets],
            "hazards": [h.to_dict() for h in features.hazards]
        }
        
        return calculate_hole_distances(map_features_dict)
    
    def has_yardbook_data(self, course_name: str) -> bool:
        """Check if a course has any yardbook data."""
        if not self.manager:
            return False
        
        summary = self.manager.get_course_yardbook_summary(course_name)
        return summary.get("holes_with_data", 0) > 0


class CourseHoleSelector:
    """
    Dialog for selecting a course and hole to view in the yardbook.
    """
    
    def __init__(
        self,
        parent: tk.Tk,
        backend: Any,
        manager: yardbookManager,
        on_select: Callable[[Dict, int], None]
    ):
        self.parent = parent
        self.backend = backend
        self.manager = manager
        self.on_select = on_select
        
        self.window = tk.Toplevel(parent)
        self.window.title("Open yardbook")
        self.window.geometry("500x450")
        self.window.transient(parent)
        self.window.grab_set()
        
        self._create_ui()
        self._populate_courses()
    
    def _create_ui(self):
        """Create the selector UI."""
        main_frame = ttk.Frame(self.window, padding=15)
        main_frame.pack(fill='both', expand=True)
        
        # Title
        ttk.Label(
            main_frame, 
            text="📍 Open yardbook",
            font=("Helvetica", 16, "bold")
        ).pack(pady=(0, 15))
        
        # Course selection
        course_frame = ttk.LabelFrame(main_frame, text="Select Course", padding=10)
        course_frame.pack(fill='x', pady=(0, 10))
        
        self.course_var = tk.StringVar()
        self.course_combo = ttk.Combobox(
            course_frame,
            textvariable=self.course_var,
            state='readonly',
            width=50
        )
        self.course_combo.pack(fill='x')
        self.course_combo.bind('<<ComboboxSelected>>', self._on_course_selected)
        
        # Course info
        self.course_info_label = ttk.Label(
            course_frame,
            text="",
            font=("Helvetica", 9),
            foreground="gray"
        )
        self.course_info_label.pack(anchor='w', pady=(5, 0))
        
        # Hole selection
        hole_frame = ttk.LabelFrame(main_frame, text="Select Hole", padding=10)
        hole_frame.pack(fill='both', expand=True, pady=(0, 10))
        
        # Hole grid
        self.hole_grid_frame = ttk.Frame(hole_frame)
        self.hole_grid_frame.pack(fill='both', expand=True)
        
        self.hole_buttons: Dict[int, ttk.Button] = {}
        self.selected_hole = tk.IntVar(value=1)
        
        # Create 18 hole buttons in a grid
        for i in range(18):
            hole_num = i + 1
            row = i // 9
            col = i % 9
            
            btn = ttk.Button(
                self.hole_grid_frame,
                text=str(hole_num),
                width=4,
                command=lambda h=hole_num: self._select_hole(h)
            )
            btn.grid(row=row, column=col, padx=2, pady=2)
            self.hole_buttons[hole_num] = btn
        
        # Row labels
        ttk.Label(self.hole_grid_frame, text="Front 9", font=("Helvetica", 9)).grid(row=0, column=9, padx=5)
        ttk.Label(self.hole_grid_frame, text="Back 9", font=("Helvetica", 9)).grid(row=1, column=9, padx=5)
        
        # Hole info
        self.hole_info_label = ttk.Label(
            hole_frame,
            text="Select a hole",
            font=("Helvetica", 10)
        )
        self.hole_info_label.pack(pady=10)
        
        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill='x')
        
        ttk.Button(
            btn_frame,
            text="Open yardbook",
            command=self._open_yardbook
        ).pack(side='right', padx=5)
        
        ttk.Button(
            btn_frame,
            text="Cancel",
            command=self.window.destroy
        ).pack(side='right', padx=5)
    
    def _populate_courses(self):
        """Populate the course dropdown."""
        courses = self.backend.get_courses()
        course_names = [c["name"] for c in sorted(courses, key=lambda x: x.get("club", ""))]
        
        self.course_combo['values'] = course_names
        
        if course_names:
            self.course_combo.set(course_names[0])
            self._on_course_selected()
    
    def _on_course_selected(self, event=None):
        """Handle course selection change."""
        course_name = self.course_var.get()
        course = self.backend.get_course_by_name(course_name)
        
        if not course:
            return
        
        # Update course info
        num_holes = len(course.get("pars", []))
        total_par = sum(course.get("pars", []))
        
        # Get yardbook completion
        summary = self.manager.get_course_yardbook_summary(course_name)
        completion = summary.get("completion_percent", 0)
        holes_complete = summary.get("holes_complete", 0)
        
        info_text = f"{course.get('club', '')} • {num_holes} holes • Par {total_par}"
        if holes_complete > 0:
            info_text += f" • yardbook: {holes_complete}/{num_holes} holes ({completion}%)"
        else:
            info_text += " • No yardbook data yet"
        
        self.course_info_label.config(text=info_text)
        
        # Update hole button states
        self._update_hole_buttons(course)
    
    def _update_hole_buttons(self, course: Dict):
        """Update hole button appearances based on data status."""
        course_name = course["name"]
        pars = course.get("pars", [])
        
        for hole_num, btn in self.hole_buttons.items():
            # Disable buttons beyond course hole count
            if hole_num > len(pars):
                btn.config(state='disabled')
                continue
            
            btn.config(state='normal')
            
            # Check if hole has yardbook data
            features = self.manager.get_hole_features(course_name, hole_num)
            if features.has_data():
                # Has data - use different style
                btn.config(text=f"✓{hole_num}")
            else:
                btn.config(text=str(hole_num))
    
    def _select_hole(self, hole_num: int):
        """Handle hole button click."""
        self.selected_hole.set(hole_num)
        
        # Update info label
        course_name = self.course_var.get()
        course = self.backend.get_course_by_name(course_name)
        
        if course:
            pars = course.get("pars", [])
            if hole_num <= len(pars):
                par = pars[hole_num - 1]
                
                # Get yardage
                yardages = course.get("yardages", {})
                yardage_str = ""
                for tee, yards in yardages.items():
                    if hole_num <= len(yards):
                        yardage_str = f" • {yards[hole_num - 1]} yds ({tee})"
                        break
                
                # Check yardbook status
                features = self.manager.get_hole_features(course_name, hole_num)
                status = "✓ Has yardbook data" if features.has_data() else "No yardbook data"
                
                self.hole_info_label.config(
                    text=f"Hole {hole_num} • Par {par}{yardage_str} • {status}"
                )
        
        # Highlight selected button
        for h, btn in self.hole_buttons.items():
            if h == hole_num:
                btn.state(['pressed'])
            else:
                btn.state(['!pressed'])
    
    def _open_yardbook(self):
        """Open the yardbook for selected course and hole."""
        course_name = self.course_var.get()
        hole_num = self.selected_hole.get()
        
        if not course_name:
            messagebox.showwarning("Warning", "Please select a course.")
            return
        
        course = self.backend.get_course_by_name(course_name)
        if not course:
            messagebox.showerror("Error", "Course not found.")
            return
        
        # Close selector
        self.window.destroy()
        
        # Open yardbook
        self.on_select(course, hole_num)


# === Utility Functions for Frontend Integration ===

def add_yardbook_to_scorecard(
    parent_frame: ttk.Frame,
    course_name: str,
    hole_num: int,
    yardbook_integration: yardbookIntegration,
    parent_window: tk.Tk
):
    """
    Add a yardbook button to a scorecard hole display.
    
    Args:
        parent_frame: Frame to add button to
        course_name: Course name
        hole_num: Hole number
        yardbook_integration: yardbookIntegration instance
        parent_window: Main app window
    """
    if not yardbook_integration.is_available():
        return
    
    btn = ttk.Button(
        parent_frame,
        text="📍",
        width=3,
        command=lambda: yardbook_integration.open_hole_direct(
            parent_window, course_name, hole_num
        )
    )
    btn.pack(side='right', padx=2)


def create_distance_display_widget(
    parent: ttk.Frame,
    yardbook_integration: yardbookIntegration,
    course_name: str,
    hole_num: int
) -> Optional[ttk.Frame]:
    """
    Create a widget showing yardbook distances for a hole.
    Returns None if no yardbook data exists.
    
    Args:
        parent: Parent frame
        yardbook_integration: yardbookIntegration instance
        course_name: Course name
        hole_num: Hole number
    
    Returns:
        Frame widget with distance info or None
    """
    distances = yardbook_integration.get_hole_distances(course_name, hole_num)
    
    if not distances:
        return None
    
    frame = ttk.Frame(parent)
    
    if distances.get("tee_to_green_center"):
        ttk.Label(
            frame,
            text=f"📍 {distances['tee_to_green_center']:.0f}y",
            font=("Helvetica", 9)
        ).pack(side='left', padx=2)
    
    # Show targets if any
    for target in distances.get("targets", [])[:2]:  # Max 2 targets
        ttk.Label(
            frame,
            text=f"• {target['name']}: {target['from_tee']:.0f}y",
            font=("Helvetica", 8),
            foreground="gray"
        ).pack(side='left', padx=2)
    
    return frame