from datetime import datetime, date

# Import from consolidated Backend module
from Backend import (
    GolfBackend, save_json, COURSES_FILE, ROUNDS_FILE, generate_scorecard_data,
    yardbookManager, GeoPoint, Target, Hazard, Polygon, HoleMapFeatures,
    DISTANCE_RING_PRESETS, POLYGON_STYLES, MARKER_STYLES,
    haversine_distance, bearing, destination_point, generate_distance_ring,
    midpoint, calculate_hole_distances, validate_yardage_difference,
    polygon_area_from_vertices
)

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Dict, List, Optional, Callable, Any, Tuple

from tkcalendar import DateEntry


import fitz

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

from PIL import Image, ImageDraw, ImageFont, ImageTk


# ============================================================================
# UI LAYOUT UTILITIES (from ui_layout.py)
# ============================================================================

def get_screen_size(window: tk.Misc) -> Tuple[int, int]:
    """Get the screen dimensions."""
    return window.winfo_screenwidth(), window.winfo_screenheight()


def autosize_toplevel(
    win: tk.Toplevel,
    pad: Tuple[int, int] = (40, 40),
    min_size: Tuple[int, int] = (300, 200),
    max_ratio: float = 0.9,
    center: bool = True
) -> None:
    """Auto-size a Toplevel window to fit its content within reasonable bounds."""
    win.update_idletasks()
    
    req_width = win.winfo_reqwidth()
    req_height = win.winfo_reqheight()
    
    width = req_width + pad[0]
    height = req_height + pad[1]
    
    screen_w, screen_h = get_screen_size(win)
    
    max_width = int(screen_w * max_ratio)
    max_height = int(screen_h * max_ratio)
    
    width = max(min_size[0], min(width, max_width))
    height = max(min_size[1], min(height, max_height))
    
    if center:
        x = (screen_w - width) // 2
        y = (screen_h - height) // 2
        win.geometry(f"{width}x{height}+{x}+{y}")
    else:
        win.geometry(f"{width}x{height}")
    
    win.minsize(min_size[0], min_size[1])


def autosize_root(
    root: tk.Tk,
    pad: Tuple[int, int] = (40, 40),
    min_size: Tuple[int, int] = (400, 500),
    max_ratio: float = 0.85,
    center: bool = True
) -> None:
    """Auto-size the root window to fit its content."""
    autosize_toplevel(root, pad, min_size, max_ratio, center)


def configure_dialog(
    win: tk.Toplevel,
    parent: tk.Misc,
    title: str,
    modal: bool = True,
    min_size: Optional[Tuple[int, int]] = None
) -> None:
    """Configure a dialog window with standard settings."""
    win.title(title)
    win.transient(parent)
    
    if modal:
        win.grab_set()
    
    if min_size:
        win.minsize(min_size[0], min_size[1])
    
    win.update_idletasks()
    
    parent_x = parent.winfo_rootx()
    parent_y = parent.winfo_rooty()
    parent_w = parent.winfo_width()
    parent_h = parent.winfo_height()
    
    win_w = win.winfo_reqwidth()
    win_h = win.winfo_reqheight()
    
    x = parent_x + (parent_w - win_w) // 2
    y = parent_y + (parent_h - win_h) // 2
    
    screen_w, screen_h = get_screen_size(win)
    x = max(0, min(x, screen_w - win_w))
    y = max(0, min(y, screen_h - win_h))
    
    win.geometry(f"+{x}+{y}")


class ScrollableFrame(ttk.Frame):
    """A frame that supports scrolling when content exceeds bounds."""
    
    def __init__(self, parent, max_height: int = 500, **kwargs):
        super().__init__(parent, **kwargs)
        
        self.max_height = max_height
        
        self.canvas = tk.Canvas(self, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        
        self.inner_frame = ttk.Frame(self.canvas)
        
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        self.canvas_window = self.canvas.create_window(
            (0, 0), 
            window=self.inner_frame, 
            anchor="nw"
        )
        
        self.scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        
        self.inner_frame.bind("<Configure>", self._on_frame_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        
        self.canvas.bind("<Enter>", self._bind_mousewheel)
        self.canvas.bind("<Leave>", self._unbind_mousewheel)
    
    def _on_frame_configure(self, event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        
        content_height = self.inner_frame.winfo_reqheight()
        if content_height <= self.max_height:
            self.canvas.configure(height=content_height)
            self.scrollbar.pack_forget()
        else:
            self.canvas.configure(height=self.max_height)
            self.scrollbar.pack(side="right", fill="y")
    
    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self.canvas_window, width=event.width)
    
    def _bind_mousewheel(self, event):
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind_all("<Button-4>", self._on_mousewheel_linux)
        self.canvas.bind_all("<Button-5>", self._on_mousewheel_linux)
    
    def _unbind_mousewheel(self, event):
        self.canvas.unbind_all("<MouseWheel>")
        self.canvas.unbind_all("<Button-4>")
        self.canvas.unbind_all("<Button-5>")
    
    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
    
    def _on_mousewheel_linux(self, event):
        if event.num == 4:
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self.canvas.yview_scroll(1, "units")


class CollapsibleSection(ttk.Frame):
    """A collapsible section widget with toggle button."""
    
    def __init__(
        self, 
        parent, 
        title: str, 
        expanded: bool = False,
        header_style: str = "Header.TLabel",
        **kwargs
    ):
        super().__init__(parent, **kwargs)
        
        self.title = title
        self._expanded = expanded
        
        self.header_frame = ttk.Frame(self)
        self.header_frame.pack(fill="x")
        
        self.toggle_var = tk.StringVar(value="▼" if expanded else "▶")
        self.toggle_btn = ttk.Button(
            self.header_frame,
            textvariable=self.toggle_var,
            width=3,
            command=self.toggle
        )
        self.toggle_btn.pack(side="left", padx=(0, 5))
        
        self.title_label = ttk.Label(
            self.header_frame,
            text=title,
            style=header_style,
            cursor="hand2"
        )
        self.title_label.pack(side="left", fill="x", expand=True)
        self.title_label.bind("<Button-1>", lambda e: self.toggle())
        
        self.content_frame = ttk.Frame(self)
        if expanded:
            self.content_frame.pack(fill="both", expand=True, pady=(5, 0))
    
    @property
    def content(self) -> ttk.Frame:
        return self.content_frame
    
    @property
    def is_expanded(self) -> bool:
        return self._expanded
    
    def toggle(self):
        self._expanded = not self._expanded
        
        if self._expanded:
            self.toggle_var.set("▼")
            self.content_frame.pack(fill="both", expand=True, pady=(5, 0))
        else:
            self.toggle_var.set("▶")
            self.content_frame.pack_forget()
    
    def expand(self):
        if not self._expanded:
            self.toggle()
    
    def collapse(self):
        if self._expanded:
            self.toggle()


def create_labeled_entry(
    parent: ttk.Frame,
    label_text: str,
    row: int,
    column: int = 0,
    width: int = 25,
    default_value: str = ""
) -> ttk.Entry:
    """Create a label + entry widget pair in a grid."""
    ttk.Label(parent, text=label_text).grid(row=row, column=column, sticky="e", padx=5, pady=3)
    entry = ttk.Entry(parent, width=width)
    entry.grid(row=row, column=column + 1, sticky="w", padx=5, pady=3)
    if default_value:
        entry.insert(0, default_value)
    return entry


def create_button_row(
    parent: ttk.Frame,
    buttons: list,
    pack_side: str = "right",
    padx: int = 5,
    pady: int = 10
) -> ttk.Frame:
    """Create a row of buttons."""
    btn_frame = ttk.Frame(parent)
    btn_frame.pack(fill="x", pady=pady)
    
    for text, command in buttons:
        ttk.Button(btn_frame, text=text, command=command).pack(
            side=pack_side, padx=padx
        )
    
    return btn_frame


# ============================================================================
# YARDBOOK INTEGRATION (from yardbook_integration.py)
# ============================================================================

def _check_map_available():
    """Check if tkintermapview is available at runtime."""
    try:
        import tkintermapview
        return True, tkintermapview
    except ImportError:
        return False, None

_map_available, tkintermapview = _check_map_available()


def is_map_available():
    """Public function to check map availability."""
    return _map_available

class yardbookView:
    """
    Main yardbook window for viewing and editing hole layouts.
    """
    
    # Placement modes
    MODE_NONE = "none"
    MODE_TEE = "tee"
    MODE_GREEN_FRONT = "green_front"
    MODE_GREEN_BACK = "green_back"
    MODE_TARGET = "target"
    MODE_HAZARD = "hazard"
    MODE_POLYGON = "polygon"
    MODE_PAN = "pan"
    MODE_DELETE = "delete"  # Delete mode
    MODE_MOVE = "move"      # Move mode
    
    def __init__(
        self, 
        parent: tk.Tk,
        course_data: Dict,
        hole_num: int,
        courses_file: str,
        on_save_callback: Optional[Callable] = None,
        selected_tee: Optional[str] = None,
        club_distances: Optional[Dict] = None
    ):
        """
        Initialize the yardbook view.
        
        Args:
            parent: Parent Tkinter window
            course_data: Full course dictionary from backend
            hole_num: Which hole to display (1-18)
            courses_file: Path to courses.json
            on_save_callback: Optional callback when data is saved
            selected_tee: Selected tee box color (for multiple tee support)
            club_distances: User's club distances from their bag
        """
        self.parent = parent
        self.course_data = course_data
        self.course_name = course_data.get("name", "Unknown")
        self.hole_num = hole_num
        self.courses_file = courses_file
        self.on_save_callback = on_save_callback
        self.selected_tee = selected_tee or self._get_default_tee()
        self.club_distances = club_distances or {}
        
        # Data management
        self.yardbook_mgr = yardbookManager(courses_file)
        self.features = self.yardbook_mgr.get_hole_features(self.course_name, hole_num)
        
        # UI state
        self.current_mode = self.MODE_PAN
        self.current_polygon_type = "fairway"
        self.current_hazard_type = "water"
        self.temp_polygon_vertices: List[Tuple[float, float]] = []
        self.unsaved_changes = False
        
        # Drag state for moving markers
        self.dragging_marker = None
        self.drag_marker_type = None
        self.drag_marker_index = None
        self.dragging_break_index = None  # NEW: For dragging aim line break points
        
        # Map objects tracking (for cleanup)
        self.map_markers: Dict[str, any] = {}
        self.map_paths: List[any] = []
        self.map_polygons: Dict[str, any] = {}
        self.distance_rings: List[any] = []
        self.aim_lines: List[any] = []
        self.distance_labels: Dict[str, any] = {}  # For on-map distance labels
        self.break_markers: List[any] = []  # NEW: Aim line break point markers
        
        # Smart positioning: track last known map position
        self.last_map_center: Optional[Tuple[float, float, int]] = None  # (lat, lon, zoom)
        
        # Toggle states
        self.show_distance_rings = tk.BooleanVar(value=False)
        self.show_aim_lines = tk.BooleanVar(value=True)
        self.show_polygons = tk.BooleanVar(value=True)
        self.show_distances = tk.BooleanVar(value=True)
        self.show_on_map_distances = tk.BooleanVar(value=True)  # New: show distances on map
        
        # Get hole info
        self.hole_par = self._get_hole_par()
        self.hole_yardage = self._get_hole_yardage()
        
        # Build UI
        self._create_window()
        self._create_map()
        self._create_sidebar()
        self._create_toolbar()
        
        # Load existing data onto map
        self._render_all_features()
        self._update_distances_panel()
        
        # Center map on hole properly
        self._center_on_hole()
    
    def _get_default_tee(self) -> str:
        """Get the default tee box color."""
        tee_boxes = self.course_data.get("tee_boxes", [])
        if tee_boxes:
            return tee_boxes[0].get("color", "White")
        return "White"
    
    def _get_available_tees(self) -> List[str]:
        """Get list of available tee box colors."""
        tee_boxes = self.course_data.get("tee_boxes", [])
        return [tb.get("color", "") for tb in tee_boxes if tb.get("color")]
    
    def _get_hole_par(self) -> int:
        """Get par for the current hole."""
        pars = self.course_data.get("pars", [])
        if self.hole_num <= len(pars):
            return pars[self.hole_num - 1]
        return 4
    
    def _get_hole_yardage(self) -> Optional[int]:
        """Get scorecard yardage for current hole (first available tee)."""
        yardages = self.course_data.get("yardages", {})
        for tee_color, yards in yardages.items():
            if self.hole_num <= len(yards):
                return yards[self.hole_num - 1]
        return None
    
    def _get_user_club_ring_presets(self) -> Dict:
        """
        Generate distance ring presets from user's club distances.
        Falls back to defaults if no user clubs are configured.
        """
        if not self.club_distances:
            return DISTANCE_RING_PRESETS
        
        # Define colors for different club categories
        category_colors = {
            "driver": "#FF6B6B",
            "wood": "#4ECDC4", 
            "hybrid": "#45B7D1",
            "iron": "#96CEB4",
            "wedge": "#FFEAA7",
            "putter": "#DDA0DD",
            "other": "#98D8C8"
        }
        
        # Build presets from user's clubs
        user_presets = {}
        for club in self.club_distances:
            club_name = club.get("name", "")
            distance = club.get("distance", 0)
            
            if distance <= 0 or club_name.lower() == "putter":
                continue
            
            # Determine category for color
            name_lower = club_name.lower()
            if "driver" in name_lower:
                color = category_colors["driver"]
            elif "wood" in name_lower:
                color = category_colors["wood"]
            elif "hybrid" in name_lower:
                color = category_colors["hybrid"]
            elif "iron" in name_lower or name_lower in ["2i", "3i", "4i", "5i", "6i", "7i", "8i", "9i"]:
                color = category_colors["iron"]
            elif any(w in name_lower for w in ["wedge", "pw", "gw", "sw", "lw", "aw"]):
                color = category_colors["wedge"]
            else:
                color = category_colors["other"]
            
            # Create a key-safe version of the name
            key = club_name.lower().replace(" ", "_").replace("-", "_")
            
            user_presets[key] = {
                "distance": distance,
                "color": color,
                "label": club_name
            }
        
        # If no valid user clubs, fall back to defaults
        return user_presets if user_presets else DISTANCE_RING_PRESETS
    
    def _create_window(self):
        """Create the main yardbook window with mobile-inspired styling."""
        self.window = tk.Toplevel(self.parent)
        self.window.title(f"Yardbook - {self.course_name} - Hole {self.hole_num}")
        self.window.geometry("1000x700")
        self.window.minsize(800, 550)
        
        # Mobile-style colors
        self.COLORS = {
            "bg": "#F2F2F7",
            "card_bg": "#FFFFFF",
            "accent": "#007AFF",
            "text": "#000000",
            "text_secondary": "#8E8E93",
            "destructive": "#FF3B30",
        }
        
        # Configure window background
        self.window.configure(bg=self.COLORS["bg"])
        
        # Handle window close
        self.window.protocol("WM_DELETE_WINDOW", self._on_close)
        
        # Main container
        self.main_frame = ttk.Frame(self.window)
        self.main_frame.pack(fill='both', expand=True)
        
        # Configure grid
        self.main_frame.columnconfigure(0, weight=3)  # Map area
        self.main_frame.columnconfigure(1, weight=0)  # Sidebar
        self.main_frame.rowconfigure(1, weight=1)     # Content row
    
    def _create_toolbar(self):
        """Create the top toolbar with mobile-style design."""
        toolbar = ttk.Frame(self.main_frame, padding=8)
        toolbar.grid(row=0, column=0, columnspan=2, sticky='ew')
        
        # Hole navigation - larger touch targets
        nav_frame = ttk.Frame(toolbar)
        nav_frame.pack(side='left')
        
        prev_btn = tk.Button(nav_frame, text="◀", font=("Helvetica", 16),
                            width=3, height=1, command=self._prev_hole,
                            bg="#E5E5EA", relief='flat')
        prev_btn.pack(side='left', padx=2)
        
        self.hole_label = ttk.Label(
            nav_frame, 
            text=f"Hole {self.hole_num}",
            font=("Helvetica", 18, "bold")
        )
        self.hole_label.pack(side='left', padx=12)
        
        self.par_label = ttk.Label(
            nav_frame,
            text=f"Par {self.hole_par}",
            font=("Helvetica", 14),
            foreground="#8E8E93"
        )
        self.par_label.pack(side='left', padx=(0, 12))
        
        next_btn = tk.Button(nav_frame, text="▶", font=("Helvetica", 16),
                            width=3, height=1, command=self._next_hole,
                            bg="#E5E5EA", relief='flat')
        next_btn.pack(side='left', padx=2)
        
        # Separator
        ttk.Separator(toolbar, orient='vertical').pack(side='left', fill='y', padx=12)
        
        # Mode buttons - segmented control style
        self.mode_var = tk.StringVar(value=self.MODE_PAN)
        
        modes_frame = ttk.Frame(toolbar)
        modes_frame.pack(side='left')
        
        modes = [
            ("🖐", self.MODE_PAN, "Pan"),
            ("T", self.MODE_TEE, "Tee"),
            ("F", self.MODE_GREEN_FRONT, "Front"),
            ("B", self.MODE_GREEN_BACK, "Back"),
            ("◎", self.MODE_TARGET, "Target"),
            ("⚠", self.MODE_HAZARD, "Hazard"),
            ("▢", self.MODE_POLYGON, "Area"),
            ("✥", self.MODE_MOVE, "Move"),
            ("🗑", self.MODE_DELETE, "Delete"),
        ]
        
        for icon, mode, tooltip in modes:
            btn = ttk.Radiobutton(
                modes_frame, 
                text=icon,
                variable=self.mode_var,
                value=mode,
                command=lambda m=mode: self._set_mode(m),
                width=3
            )
            btn.pack(side='left', padx=1)
        
        # Right side - action buttons
        action_frame = ttk.Frame(toolbar)
        action_frame.pack(side='right')
        
        tk.Button(action_frame, text="💾 Save", font=("Helvetica", 12),
                 command=self._save_features, bg="#34C759", fg="white",
                 relief='flat', padx=12, pady=4).pack(side='right', padx=4)
        
        tk.Button(action_frame, text="Clear All", font=("Helvetica", 12),
                 command=self._clear_all, bg="#FF3B30", fg="white",
                 relief='flat', padx=8, pady=4).pack(side='right', padx=4)
    
    def _create_map(self):
        """Create the map widget."""
        map_frame = ttk.Frame(self.main_frame)
        map_frame.grid(row=1, column=0, sticky='nsew', padx=5, pady=5)
        
        if not _map_available:
            ttk.Label(
                map_frame, 
                text="Map feature unavailable.\nPlease install tkintermapview:\npip install tkintermapview",
                font=("Helvetica", 14)
            ).pack(expand=True)
            self.map_widget = None
            return
        
        # Create map widget
        self.map_widget = tkintermapview.TkinterMapView(
            map_frame,
            width=800,
            height=600,
            corner_radius=0
        )
        self.map_widget.pack(fill='both', expand=True)
        
        # Set to satellite view (using Google satellite tiles)
        self.map_widget.set_tile_server(
            "https://mt0.google.com/vt/lyrs=s&hl=en&x={x}&y={y}&z={z}&s=Ga",
            max_zoom=22  # Increased max zoom for closer views
        )
        
        # Bind click events
        self.map_widget.add_left_click_map_command(self._on_map_click)
        self.map_widget.add_right_click_menu_command(
            "Place Tee Here",
            lambda coords: self._quick_place("tee", coords),
            pass_coords=True
        )
        self.map_widget.add_right_click_menu_command(
            "Place Target Here",
            lambda coords: self._quick_place("target", coords),
            pass_coords=True
        )
        self.map_widget.add_right_click_menu_command(
            "Delete Marker Here",
            lambda coords: self._delete_nearest_marker(coords),
            pass_coords=True
        )
    
    def _create_sidebar(self):
        """Create the right sidebar with mobile-inspired design."""
        sidebar = ttk.Frame(self.main_frame, width=280)
        sidebar.grid(row=1, column=1, sticky='ns', padx=5, pady=5)
        sidebar.grid_propagate(False)
        
        # Create scrollable container for sidebar
        sidebar_canvas = tk.Canvas(sidebar, highlightthickness=0, width=270)
        sidebar_scroll = ttk.Scrollbar(sidebar, orient="vertical", command=sidebar_canvas.yview)
        sidebar_content = ttk.Frame(sidebar_canvas)
        
        sidebar_content.bind("<Configure>", lambda e: sidebar_canvas.configure(scrollregion=sidebar_canvas.bbox("all")))
        sidebar_canvas.create_window((0, 0), window=sidebar_content, anchor="nw")
        sidebar_canvas.configure(yscrollcommand=sidebar_scroll.set)
        
        sidebar_canvas.pack(side='left', fill='both', expand=True)
        sidebar_scroll.pack(side='right', fill='y')
        
        # Hole Info Card
        info_card = ttk.LabelFrame(sidebar_content, text="Hole Info", padding=12)
        info_card.pack(fill='x', pady=(0, 8), padx=4)
        
        # Large par display
        par_frame = ttk.Frame(info_card)
        par_frame.pack(fill='x')
        
        ttk.Label(par_frame, text=f"Par {self.hole_par}",
                 font=("Helvetica", 24, "bold"),
                 foreground="#007AFF").pack(side='left')
        
        if self.hole_yardage:
            ttk.Label(par_frame, text=f"{self.hole_yardage} yds",
                     font=("Helvetica", 14),
                     foreground="#8E8E93").pack(side='right', anchor='e')
        
        # Distances Card
        dist_card = ttk.LabelFrame(sidebar_content, text="📏 Distances", padding=12)
        dist_card.pack(fill='x', pady=8, padx=4)
        
        self.dist_labels = {}
        dist_items = [
            ("tee_to_front", "To Front"),
            ("tee_to_back", "To Back"),
            ("tee_to_center", "To Center"),
            ("green_depth", "Green Depth"),
            ("route_distance", "Route"),
        ]
        
        for key, label_text in dist_items:
            row = ttk.Frame(dist_card)
            row.pack(fill='x', pady=2)
            ttk.Label(row, text=label_text, font=("Helvetica", 11)).pack(side='left')
            lbl = ttk.Label(row, text="—", font=("Helvetica", 12, "bold"),
                          foreground="#007AFF")
            lbl.pack(side='right')
            self.dist_labels[key] = lbl
        
        # Targets Card
        targets_card = ttk.LabelFrame(sidebar_content, text="◎ Targets", padding=8)
        targets_card.pack(fill='x', pady=8, padx=4)
        
        self.targets_listbox = tk.Listbox(targets_card, height=3, font=("Helvetica", 10),
                                          selectbackground="#007AFF")
        self.targets_listbox.pack(fill='x')
        self.targets_listbox.bind('<Double-1>', self._edit_target)
        self.targets_listbox.bind('<Delete>', self._delete_target)
        
        ttk.Label(targets_card, text="Double-click to edit, Delete to remove",
                 font=("Helvetica", 9), foreground="#8E8E93").pack(anchor='w', pady=(4, 0))
        
        # Hazards Card
        hazards_card = ttk.LabelFrame(sidebar_content, text="⚠ Hazards", padding=8)
        hazards_card.pack(fill='x', pady=8, padx=4)
        
        self.hazards_listbox = tk.Listbox(hazards_card, height=3, font=("Helvetica", 10),
                                          selectbackground="#FF3B30")
        self.hazards_listbox.pack(fill='x')
        
        # Display Options Card
        display_card = ttk.LabelFrame(sidebar_content, text="Display", padding=10)
        display_card.pack(fill='x', pady=8, padx=4)
        
        ttk.Checkbutton(
            display_card, text="Distance Rings",
            variable=self.show_distance_rings,
            command=self._toggle_distance_rings
        ).pack(anchor='w', pady=2)
        
        ttk.Checkbutton(
            display_card, text="Aim Lines",
            variable=self.show_aim_lines,
            command=self._toggle_aim_lines
        ).pack(anchor='w', pady=2)
        
        ttk.Checkbutton(
            display_card, text="Overlays",
            variable=self.show_polygons,
            command=self._toggle_polygons
        ).pack(anchor='w', pady=2)
        
        # Polygon Type Selection (when in polygon mode)
        self.polygon_frame = ttk.LabelFrame(sidebar_content, text="Area Type", padding=10)
        self.polygon_frame.pack(fill='x', pady=8, padx=4)
        
        self.polygon_type_var = tk.StringVar(value="fairway")
        for ptype, style in POLYGON_STYLES.items():
            ttk.Radiobutton(
                self.polygon_frame,
                text=style["label"],
                variable=self.polygon_type_var,
                value=ptype,
                command=lambda: self._set_polygon_type(self.polygon_type_var.get())
            ).pack(anchor='w', pady=1)
        
        btn_frame = ttk.Frame(self.polygon_frame)
        btn_frame.pack(fill='x', pady=(8, 0))
        
        ttk.Button(btn_frame, text="✓ Finish", width=8,
                  command=self._finish_polygon).pack(side='left', padx=2)
        ttk.Button(btn_frame, text="✗ Cancel", width=8,
                  command=self._cancel_polygon).pack(side='left', padx=2)
        
        # Hazard Type Selection
        self.hazard_frame = ttk.LabelFrame(sidebar_content, text="Hazard Type", padding=10)
        self.hazard_frame.pack(fill='x', pady=8, padx=4)
        
        self.hazard_type_var = tk.StringVar(value="water")
        hazard_types = [
            ("water", "💧 Water"),
            ("bunker", "🏖 Bunker"),
            ("ob", "🚫 Out of Bounds"),
            ("tree", "🌳 Trees"),
        ]
        
        for htype, label in hazard_types:
            ttk.Radiobutton(
                self.hazard_frame,
                text=label,
                variable=self.hazard_type_var,
                value=htype
            ).pack(anchor='w', pady=1)
        
        # Help Card
        help_card = ttk.LabelFrame(sidebar_content, text="Quick Help", padding=8)
        help_card.pack(fill='x', pady=8, padx=4)
        
        help_text = "• Click map to place markers\n• Right-click for quick actions\n• Drag markers to move them"
        ttk.Label(help_card, text=help_text, font=("Helvetica", 10),
                 foreground="#8E8E93").pack(anchor='w')
        
        # Distance Rings Config - Now uses player's clubs
        self.rings_frame = ttk.LabelFrame(sidebar_content, text="Distance Rings", padding=10)
        self.rings_frame.pack(fill='x', pady=8, padx=4)
        
        # Create scrollable frame for club rings if many clubs
        self._create_club_rings_ui()
        
        # Status bar at bottom of sidebar
        self.status_label = ttk.Label(
            sidebar_content, 
            text="Ready",
            font=("Helvetica", 10),
            foreground="#8E8E93"
        )
        self.status_label.pack(pady=8)
    
    def _create_club_rings_ui(self):
        """Create the UI for club distance rings using player's clubs."""
        # Clear existing widgets in rings_frame
        for widget in self.rings_frame.winfo_children():
            widget.destroy()
        
        # Get the ring presets (user's clubs or defaults)
        ring_presets = self._get_user_club_ring_presets()
        
        # Sort by distance descending
        sorted_presets = sorted(
            ring_presets.items(), 
            key=lambda x: x[1].get("distance", 0), 
            reverse=True
        )
        
        self.ring_vars = {}
        
        # Create a canvas with scrollbar for many clubs
        if len(sorted_presets) > 8:
            canvas = tk.Canvas(self.rings_frame, height=150)
            scrollbar = ttk.Scrollbar(self.rings_frame, orient="vertical", command=canvas.yview)
            scroll_frame = ttk.Frame(canvas)
            
            scroll_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )
            
            canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            
            canvas.pack(side='left', fill='both', expand=True)
            scrollbar.pack(side='right', fill='y')
            
            parent_frame = scroll_frame
        else:
            parent_frame = self.rings_frame
        
        for preset_key, preset in sorted_presets:
            var = tk.BooleanVar(value=False)
            self.ring_vars[preset_key] = var
            
            # Create frame for each club with color indicator
            club_frame = ttk.Frame(parent_frame)
            club_frame.pack(anchor='w', fill='x', pady=1)
            
            cb = ttk.Checkbutton(
                club_frame,
                text=f"{preset['label']} ({preset['distance']}y)",
                variable=var,
                command=self._update_distance_rings
            )
            cb.pack(side='left')
            
            # Color indicator
            try:
                color_label = tk.Label(
                    club_frame, 
                    text="●", 
                    foreground=preset.get("color", "#AAAAAA"),
                    font=("Helvetica", 10)
                )
                color_label.pack(side='left', padx=2)
            except:
                pass  # Skip color indicator if there's an issue
    
    def _set_mode(self, mode: str):
        """Set the current placement mode."""
        self.current_mode = mode
        
        # Show/hide relevant panels
        if mode == self.MODE_POLYGON:
            self.polygon_frame.pack(fill='x', pady=(0, 10))
            self.hazard_frame.pack_forget()
            self._set_status("Click on map to add polygon vertices. Double-click or 'Finish' to complete.")
        elif mode == self.MODE_HAZARD:
            self.hazard_frame.pack(fill='x', pady=(0, 10))
            self.polygon_frame.pack_forget()
            self._set_status("Click on map to place hazard marker.")
        elif mode == self.MODE_DELETE:
            self.polygon_frame.pack_forget()
            self.hazard_frame.pack_forget()
            self._set_status("Click on a marker to delete it.")
        elif mode == self.MODE_MOVE:
            self.polygon_frame.pack_forget()
            self.hazard_frame.pack_forget()
            self._set_status("Click and drag markers to move them.")
        else:
            self.polygon_frame.pack_forget()
            self.hazard_frame.pack_forget()
            
            if mode == self.MODE_PAN:
                self._set_status("Pan mode. Click and drag to move map.")
            elif mode == self.MODE_TEE:
                self._set_status("Click on map to place tee marker.")
            elif mode == self.MODE_GREEN_FRONT:
                self._set_status("Click on map to place green front marker.")
            elif mode == self.MODE_GREEN_BACK:
                self._set_status("Click on map to place green back marker.")
            elif mode == self.MODE_TARGET:
                self._set_status("Click on map to place target marker.")
    
    def _set_status(self, text: str):
        """Update status bar text."""
        self.status_label.config(text=text)
    
    def _on_map_click(self, coords: Tuple[float, float]):
        """Handle map click based on current mode."""
        lat, lon = coords
        
        # Check if we're dragging a break marker (any mode)
        if self._handle_break_marker_drag(lat, lon):
            return
        
        if self.current_mode == self.MODE_PAN:
            # Check if clicked on a break marker to start dragging
            if self._handle_break_marker_click(lat, lon):
                return
            return  # Let map handle panning
        
        elif self.current_mode == self.MODE_DELETE:
            self._handle_delete_click(lat, lon)
        
        elif self.current_mode == self.MODE_MOVE:
            # Check if clicked on a break marker first
            if self._handle_break_marker_click(lat, lon):
                return
            # Move mode click is handled by marker drag
            self._handle_move_click(lat, lon)
        
        elif self.current_mode == self.MODE_TEE:
            self.features.tee = GeoPoint(lat=lat, lon=lon)
            self._render_marker("tee", lat, lon)
            self.unsaved_changes = True
            self._update_distances_panel()
            self._set_status(f"Tee placed at ({lat:.6f}, {lon:.6f})")
        
        elif self.current_mode == self.MODE_GREEN_FRONT:
            self.features.green_front = GeoPoint(lat=lat, lon=lon)
            self._render_marker("green_front", lat, lon)
            self.unsaved_changes = True
            self._update_distances_panel()
            self._set_status(f"Green front placed at ({lat:.6f}, {lon:.6f})")
        
        elif self.current_mode == self.MODE_GREEN_BACK:
            self.features.green_back = GeoPoint(lat=lat, lon=lon)
            self._render_marker("green_back", lat, lon)
            self.unsaved_changes = True
            self._update_distances_panel()
            self._set_status(f"Green back placed at ({lat:.6f}, {lon:.6f})")
        
        elif self.current_mode == self.MODE_TARGET:
            self._add_target(lat, lon)
        
        elif self.current_mode == self.MODE_HAZARD:
            self._add_hazard(lat, lon)
        
        elif self.current_mode == self.MODE_POLYGON:
            self._add_polygon_vertex(lat, lon)
        
        # Update aim lines if enabled
        if self.show_aim_lines.get():
            self._render_aim_lines()
    
    def _handle_delete_click(self, lat: float, lon: float):
        """Handle click in delete mode - find and delete nearest marker."""
        self._delete_nearest_marker((lat, lon))
    
    def _handle_move_click(self, lat: float, lon: float):
        """Handle click in move mode - start dragging nearest marker."""
        marker_info = self._find_nearest_marker(lat, lon)
        if marker_info:
            marker_type, index = marker_info
            self._set_status(f"Click new location for {marker_type}")
            # Store the marker being moved for the next click
            self.dragging_marker = (marker_type, index, lat, lon)
        else:
            # If we have a marker being moved, place it at the new location
            if self.dragging_marker:
                marker_type, index, _, _ = self.dragging_marker
                self._move_marker_to(marker_type, index, lat, lon)
                self.dragging_marker = None
    
    def _find_nearest_marker(self, lat: float, lon: float, threshold: float = 50.0) -> Optional[Tuple[str, int]]:
        """Find the nearest marker within threshold yards."""
        nearest = None
        nearest_dist = threshold
        
        # Check tee
        if self.features.tee.is_set():
            dist = haversine_distance(lat, lon, self.features.tee.lat, self.features.tee.lon)
            if dist < nearest_dist:
                nearest_dist = dist
                nearest = ("tee", 0)
        
        # Check green front
        if self.features.green_front.is_set():
            dist = haversine_distance(lat, lon, self.features.green_front.lat, self.features.green_front.lon)
            if dist < nearest_dist:
                nearest_dist = dist
                nearest = ("green_front", 0)
        
        # Check green back
        if self.features.green_back.is_set():
            dist = haversine_distance(lat, lon, self.features.green_back.lat, self.features.green_back.lon)
            if dist < nearest_dist:
                nearest_dist = dist
                nearest = ("green_back", 0)
        
        # Check targets
        for i, target in enumerate(self.features.targets):
            if target.lat is not None:
                dist = haversine_distance(lat, lon, target.lat, target.lon)
                if dist < nearest_dist:
                    nearest_dist = dist
                    nearest = ("target", i)
        
        # Check hazards
        for i, hazard in enumerate(self.features.hazards):
            if hazard.lat is not None:
                dist = haversine_distance(lat, lon, hazard.lat, hazard.lon)
                if dist < nearest_dist:
                    nearest_dist = dist
                    nearest = ("hazard", i)
        
        return nearest
    
    def _delete_nearest_marker(self, coords: Tuple[float, float]):
        """Delete the nearest marker to the given coordinates."""
        lat, lon = coords
        marker_info = self._find_nearest_marker(lat, lon)
        
        if not marker_info:
            self._set_status("No marker found nearby.")
            return
        
        marker_type, index = marker_info
        
        # Delete based on type
        if marker_type == "tee":
            self.features.tee = GeoPoint()
            if "tee" in self.map_markers:
                try:
                    self.map_markers["tee"].delete()
                except:
                    pass
                del self.map_markers["tee"]
            self._set_status("Tee marker deleted.")
        
        elif marker_type == "green_front":
            self.features.green_front = GeoPoint()
            if "green_front" in self.map_markers:
                try:
                    self.map_markers["green_front"].delete()
                except:
                    pass
                del self.map_markers["green_front"]
            self._set_status("Green front marker deleted.")
        
        elif marker_type == "green_back":
            self.features.green_back = GeoPoint()
            if "green_back" in self.map_markers:
                try:
                    self.map_markers["green_back"].delete()
                except:
                    pass
                del self.map_markers["green_back"]
            self._set_status("Green back marker deleted.")
        
        elif marker_type == "target":
            if 0 <= index < len(self.features.targets):
                target_name = self.features.targets[index].name
                self.features.targets.pop(index)
                key = f"target_{index}"
                if key in self.map_markers:
                    try:
                        self.map_markers[key].delete()
                    except:
                        pass
                    del self.map_markers[key]
                # Re-render all targets to fix indices
                self._render_all_features()
                self._set_status(f"Target '{target_name}' deleted.")
        
        elif marker_type == "hazard":
            if 0 <= index < len(self.features.hazards):
                self.features.hazards.pop(index)
                key = f"hazard_{index}"
                if key in self.map_markers:
                    try:
                        self.map_markers[key].delete()
                    except:
                        pass
                    del self.map_markers[key]
                # Re-render all hazards to fix indices
                self._render_all_features()
                self._set_status("Hazard deleted.")
        
        self.unsaved_changes = True
        self._update_distances_panel()
        if self.show_aim_lines.get():
            self._render_aim_lines()
    
    def _move_marker_to(self, marker_type: str, index: int, new_lat: float, new_lon: float):
        """Move a marker to a new location."""
        if marker_type == "tee":
            self.features.tee = GeoPoint(lat=new_lat, lon=new_lon)
            self._render_marker("tee", new_lat, new_lon)
            self._set_status("Tee moved.")
        
        elif marker_type == "green_front":
            self.features.green_front = GeoPoint(lat=new_lat, lon=new_lon)
            self._render_marker("green_front", new_lat, new_lon)
            self._set_status("Green front moved.")
        
        elif marker_type == "green_back":
            self.features.green_back = GeoPoint(lat=new_lat, lon=new_lon)
            self._render_marker("green_back", new_lat, new_lon)
            self._set_status("Green back moved.")
        
        elif marker_type == "target":
            if 0 <= index < len(self.features.targets):
                self.features.targets[index].lat = new_lat
                self.features.targets[index].lon = new_lon
                self._render_target_marker(self.features.targets[index], index)
                self._set_status(f"Target '{self.features.targets[index].name}' moved.")
        
        elif marker_type == "hazard":
            if 0 <= index < len(self.features.hazards):
                self.features.hazards[index].lat = new_lat
                self.features.hazards[index].lon = new_lon
                self._render_hazard_marker(self.features.hazards[index], index)
                self._set_status("Hazard moved.")
        
        self.unsaved_changes = True
        self._update_distances_panel()
        if self.show_aim_lines.get():
            self._render_aim_lines()
        if self.show_on_map_distances.get():
            self._render_on_map_distances()
    
    def _quick_place(self, marker_type: str, coords: Tuple[float, float]):
        """Quick placement from right-click menu."""
        lat, lon = coords
        
        if marker_type == "tee":
            self.features.tee = GeoPoint(lat=lat, lon=lon)
            self._render_marker("tee", lat, lon)
        elif marker_type == "target":
            self._add_target(lat, lon)
        
        self.unsaved_changes = True
        self._update_distances_panel()
    
    def _add_target(self, lat: float, lon: float):
        """Add a new target point."""
        target_num = len(self.features.targets) + 1
        name = f"Target {target_num}"
        
        # Simple dialog for target name
        name = self._simple_input_dialog("Target Name", "Enter target name:", name)
        if name is None:
            return
        
        target = Target(name=name, lat=lat, lon=lon)
        self.features.targets.append(target)
        
        self._render_target_marker(target, len(self.features.targets) - 1)
        self.unsaved_changes = True
        self._update_distances_panel()
        self._set_status(f"Target '{name}' placed.")
    
    def _add_hazard(self, lat: float, lon: float):
        """Add a new hazard point."""
        hazard_type = self.hazard_type_var.get()
        hazard = Hazard(hazard_type=hazard_type, lat=lat, lon=lon)
        self.features.hazards.append(hazard)
        
        self._render_hazard_marker(hazard, len(self.features.hazards) - 1)
        self.unsaved_changes = True
        self._update_distances_panel()
        self._set_status(f"{hazard_type.title()} hazard placed.")
    
    def _add_polygon_vertex(self, lat: float, lon: float):
        """Add a vertex to the current polygon being drawn."""
        self.temp_polygon_vertices.append((lat, lon))
        
        # Visual feedback - draw temp marker
        if self.map_widget:
            marker = self.map_widget.set_marker(
                lat, lon,
                text=str(len(self.temp_polygon_vertices)),
                marker_color_circle="yellow",
                marker_color_outside="orange"
            )
            # Store for cleanup
            if "temp_vertices" not in self.map_markers:
                self.map_markers["temp_vertices"] = []
            self.map_markers["temp_vertices"].append(marker)
        
        # Draw line to previous vertex
        if len(self.temp_polygon_vertices) >= 2 and self.map_widget:
            path = self.map_widget.set_path(
                self.temp_polygon_vertices[-2:],
                color="yellow",
                width=2
            )
            self.map_paths.append(path)
        
        self._set_status(f"Polygon vertex {len(self.temp_polygon_vertices)} added. Double-click to finish.")
    
    def _finish_polygon(self):
        """Finish drawing the current polygon.
        
        CHANGED: Now adds polygon to list instead of replacing single polygon.
        Ensures polygon is properly closed by adding first vertex at end.
        """
        if len(self.temp_polygon_vertices) < 3:
            messagebox.showwarning("Warning", "Polygon needs at least 3 vertices.")
            return
        
        ptype = self.polygon_type_var.get()
        
        # Ensure polygon closes by checking if last == first
        vertices = list(self.temp_polygon_vertices)
        if vertices[0] != vertices[-1]:
            vertices.append(vertices[0])
        
        # Create new polygon and add to list
        new_polygon = Polygon()
        for lat, lon in vertices:
            new_polygon.add_vertex(lat, lon)
        
        # CHANGED: Add to list instead of replacing
        self.features.add_polygon(ptype, new_polygon)
        
        # Clear temp markers
        self._clear_temp_polygon_markers()
        
        # Render all polygons of this type
        self._render_polygons_of_type(ptype)
        
        self.temp_polygon_vertices = []
        self.unsaved_changes = True
        
        # Count total polygons of this type
        count = len(self.features.get_polygons(ptype))
        self._set_status(f"{POLYGON_STYLES[ptype]['label']} polygon #{count} saved.")
    
    def _cancel_polygon(self):
        """Cancel current polygon drawing."""
        self._clear_temp_polygon_markers()
        self.temp_polygon_vertices = []
        self._set_status("Polygon cancelled.")
    
    def _clear_temp_polygon_markers(self):
        """Clear temporary polygon markers."""
        if "temp_vertices" in self.map_markers:
            for marker in self.map_markers["temp_vertices"]:
                try:
                    marker.delete()
                except:
                    pass
            self.map_markers["temp_vertices"] = []
    
    def _set_polygon_type(self, ptype: str):
        """Set the polygon type being drawn."""
        self.current_polygon_type = ptype
    
    # === Rendering Methods ===
    
    def _render_all_features(self):
        """Render all saved features onto the map."""
        if not self.map_widget:
            return
        
        # Render polygons first (background) - now handles multiple per type
        for ptype in self.features.polygons.keys():
            self._render_polygons_of_type(ptype)
        
        # Render markers
        if self.features.tee.is_set():
            self._render_marker("tee", self.features.tee.lat, self.features.tee.lon)
        
        if self.features.green_front.is_set():
            self._render_marker("green_front", self.features.green_front.lat, self.features.green_front.lon)
        
        if self.features.green_back.is_set():
            self._render_marker("green_back", self.features.green_back.lat, self.features.green_back.lon)
        
        # Render targets
        for i, target in enumerate(self.features.targets):
            self._render_target_marker(target, i)
        
        # Render hazards
        for i, hazard in enumerate(self.features.hazards):
            self._render_hazard_marker(hazard, i)
        
        # Render aim lines if enabled
        if self.show_aim_lines.get():
            self._render_aim_lines()
    
    def _render_marker(self, marker_type: str, lat: float, lon: float):
        """Render a single marker on the map."""
        if not self.map_widget:
            return
        
        # Remove existing marker of this type
        if marker_type in self.map_markers:
            try:
                self.map_markers[marker_type].delete()
            except:
                pass
        
        style = MARKER_STYLES.get(marker_type, MARKER_STYLES["tee"])
        
        marker = self.map_widget.set_marker(
            lat, lon,
            text=style["label"],
            marker_color_circle=style["color"],
            marker_color_outside="white"
        )
        
        self.map_markers[marker_type] = marker
    
    def _render_target_marker(self, target: Target, index: int):
        """Render a target marker."""
        if not self.map_widget or target.lat is None:
            return
        
        key = f"target_{index}"
        
        # Remove existing
        if key in self.map_markers:
            try:
                self.map_markers[key].delete()
            except:
                pass
        
        marker = self.map_widget.set_marker(
            target.lat, target.lon,
            text=target.name[:3],  # Truncate name for display
            marker_color_circle="#FFFF44",
            marker_color_outside="white"
        )
        
        self.map_markers[key] = marker
    
    def _render_hazard_marker(self, hazard: Hazard, index: int):
        """Render a hazard marker."""
        if not self.map_widget or hazard.lat is None:
            return
        
        key = f"hazard_{index}"
        
        # Remove existing
        if key in self.map_markers:
            try:
                self.map_markers[key].delete()
            except:
                pass
        
        style_key = f"hazard_{hazard.hazard_type}"
        style = MARKER_STYLES.get(style_key, MARKER_STYLES["hazard_water"])
        
        marker = self.map_widget.set_marker(
            hazard.lat, hazard.lon,
            text=style["label"],
            marker_color_circle=style["color"],
            marker_color_outside="red"
        )
        
        self.map_markers[key] = marker
    
    def _render_polygons_of_type(self, ptype: str):
        """Render all polygons of a specific type.
        
        CHANGED: Now handles multiple polygons per type.
        """
        if not self.map_widget:
            return
        
        # Remove existing polygons of this type
        keys_to_remove = [k for k in self.map_polygons.keys() if k.startswith(f"{ptype}_")]
        for key in keys_to_remove:
            try:
                self.map_polygons[key].delete()
            except:
                pass
            del self.map_polygons[key]
        
        # Also try to remove old single-polygon key for backwards compat
        if ptype in self.map_polygons:
            try:
                self.map_polygons[ptype].delete()
            except:
                pass
            del self.map_polygons[ptype]
        
        style = POLYGON_STYLES.get(ptype, POLYGON_STYLES["fairway"])
        
        # Render each polygon
        for idx, polygon in enumerate(self.features.get_polygons(ptype)):
            if not polygon.is_valid():
                continue
            
            # Convert to list of tuples
            coords = [(v["lat"], v["lon"]) for v in polygon.vertices]
            
            # Ensure visual closure
            if coords and coords[0] != coords[-1]:
                coords.append(coords[0])
            
            try:
                poly = self.map_widget.set_polygon(
                    coords,
                    fill_color=style["fill_color"],
                    outline_color=style["outline_color"],
                    border_width=2
                )
                self.map_polygons[f"{ptype}_{idx}"] = poly
            except Exception as e:
                print(f"Error rendering polygon {ptype}_{idx}: {e}")
    
    def _render_polygon(self, ptype: str):
        """Legacy method - redirect to new implementation."""
        self._render_polygons_of_type(ptype)
    
    def _render_aim_lines(self):
        """
        Render segmented aim lines from tee to green with par-based breaks.
        
        Rules:
        - Par 3: 0 breaks (single segment)
        - Par 4: 1 break (two segments)
        - Par 5: 2 breaks (three segments)
        
        Break points are draggable and stored in features.aim_breaks.
        """
        if not self.map_widget:
            return
        
        # Clear existing aim lines and break markers
        for line in self.aim_lines:
            try:
                line.delete()
            except:
                pass
        self.aim_lines = []
        
        for marker in self.break_markers:
            try:
                marker.delete()
            except:
                pass
        self.break_markers = []
        
        if not self.features.tee.is_set():
            return
        
        tee = (self.features.tee.lat, self.features.tee.lon)
        
        # Determine aim endpoint (green front if set, else green back, else green center)
        aim_endpoint = None
        if self.features.green_front.is_set() and self.features.green_back.is_set():
            # Use center of green as endpoint
            aim_endpoint = midpoint(
                self.features.green_front.lat, self.features.green_front.lon,
                self.features.green_back.lat, self.features.green_back.lon
            )
        elif self.features.green_front.is_set():
            aim_endpoint = (self.features.green_front.lat, self.features.green_front.lon)
        elif self.features.green_back.is_set():
            aim_endpoint = (self.features.green_back.lat, self.features.green_back.lon)
        
        if not aim_endpoint:
            return
        
        # Determine number of breaks based on par
        num_breaks = self._get_break_count_for_par()
        
        # Initialize aim_breaks if needed (ensure correct count)
        self._initialize_aim_breaks(num_breaks, tee, aim_endpoint)
        
        # Build the path: tee -> breaks -> aim_endpoint
        path_points = [tee]
        for i, break_point in enumerate(self.features.aim_breaks[:num_breaks]):
            if break_point.is_set():
                path_points.append((break_point.lat, break_point.lon))
        path_points.append(aim_endpoint)
        
        # Draw the segmented aim line
        if len(path_points) >= 2:
            try:
                line = self.map_widget.set_path(
                    path_points,
                    color="#44FF44",
                    width=3
                )
                self.aim_lines.append(line)
            except Exception as e:
                print(f"Error rendering aim line: {e}")
        
        # Draw break point markers (draggable via click)
        for i, break_point in enumerate(self.features.aim_breaks[:num_breaks]):
            if break_point.is_set():
                self._render_break_marker(break_point, i)
        
        # Render segment distance labels on the map
        self._render_segment_distances(path_points)
        
        # Also render on-map distances for green/hazards/targets
        self._render_on_map_distances()
    
    def _get_break_count_for_par(self) -> int:
        """Get number of aim line breaks based on hole par."""
        if self.hole_par <= 3:
            return 0  # Par 3: no breaks
        elif self.hole_par == 4:
            return 1  # Par 4: 1 break
        else:
            return 2  # Par 5+: 2 breaks
    
    def _initialize_aim_breaks(self, num_breaks: int, tee: Tuple[float, float], endpoint: Tuple[float, float]):
        """
        Initialize aim break points if they don't exist or need adjustment.
        Places breaks evenly along the tee-to-endpoint line.
        """
        # Only initialize if we don't have the right number of breaks
        current_breaks = len([b for b in self.features.aim_breaks if b.is_set()])
        
        if current_breaks != num_breaks:
            self.features.aim_breaks = []
            
            if num_breaks > 0:
                # Calculate evenly spaced break points
                for i in range(num_breaks):
                    fraction = (i + 1) / (num_breaks + 1)
                    break_lat = tee[0] + fraction * (endpoint[0] - tee[0])
                    break_lon = tee[1] + fraction * (endpoint[1] - tee[1])
                    self.features.aim_breaks.append(GeoPoint(lat=break_lat, lon=break_lon))
    
    def _render_break_marker(self, break_point: GeoPoint, index: int):
        """Render a draggable break point marker."""
        if not self.map_widget or not break_point.is_set():
            return
        
        try:
            # Create marker with drag callback
            marker = self.map_widget.set_marker(
                break_point.lat, break_point.lon,
                text=f"B{index + 1}",
                marker_color_circle="#FF9900",
                marker_color_outside="#FFCC00"
            )
            self.break_markers.append(marker)
            
            # Store index for drag handling
            marker._break_index = index
        except Exception as e:
            print(f"Error rendering break marker: {e}")
    
    def _render_segment_distances(self, path_points: List[Tuple[float, float]]):
        """Render distance labels at segment midpoints."""
        if not self.map_widget or len(path_points) < 2:
            return
        
        # Clear existing segment distance labels
        for key in list(self.distance_labels.keys()):
            if key.startswith("seg_"):
                try:
                    self.distance_labels[key].delete()
                except:
                    pass
                del self.distance_labels[key]
        
        # Render distance for each segment
        for i in range(len(path_points) - 1):
            p1 = path_points[i]
            p2 = path_points[i + 1]
            
            # Calculate segment distance
            seg_dist = haversine_distance(p1[0], p1[1], p2[0], p2[1])
            
            # Calculate midpoint for label placement
            mid_lat = (p1[0] + p2[0]) / 2
            mid_lon = (p1[1] + p2[1]) / 2
            
            # Slight offset to avoid overlapping the line
            mid_lat += 0.00003
            
            # Create label
            label_text = f"{seg_dist:.0f}y"
            
            try:
                marker = self.map_widget.set_marker(
                    mid_lat, mid_lon,
                    text=label_text,
                    marker_color_circle="#FFFFFF",
                    marker_color_outside="#44FF44"
                )
                self.distance_labels[f"seg_{i}"] = marker
            except:
                pass
    
    def _render_on_map_distances(self):
        """
        Render distance labels directly on the map for green, hazards, and targets.
        """
        if not self.map_widget:
            return
        
        # Clear existing non-segment distance labels
        for key in list(self.distance_labels.keys()):
            if not key.startswith("seg_"):
                try:
                    self.distance_labels[key].delete()
                except:
                    pass
                del self.distance_labels[key]
        
        if not self.features.tee.is_set():
            return
        
        tee_lat, tee_lon = self.features.tee.lat, self.features.tee.lon
        
        # Green front distance label
        if self.features.green_front.is_set():
            gf_lat, gf_lon = self.features.green_front.lat, self.features.green_front.lon
            dist = haversine_distance(tee_lat, tee_lon, gf_lat, gf_lon)
            
            try:
                marker = self.map_widget.set_marker(
                    gf_lat + 0.00006, gf_lon,
                    text=f"F {dist:.0f}y",
                    marker_color_circle="#44FF44",
                    marker_color_outside="#FFFFFF"
                )
                self.distance_labels["green_front"] = marker
            except:
                pass
        
        # Green back distance label
        if self.features.green_back.is_set():
            gb_lat, gb_lon = self.features.green_back.lat, self.features.green_back.lon
            dist = haversine_distance(tee_lat, tee_lon, gb_lat, gb_lon)
            
            try:
                marker = self.map_widget.set_marker(
                    gb_lat + 0.00006, gb_lon,
                    text=f"B {dist:.0f}y",
                    marker_color_circle="#44FF44",
                    marker_color_outside="#FFFFFF"
                )
                self.distance_labels["green_back"] = marker
            except:
                pass
        
        # Target distance labels
        for i, target in enumerate(self.features.targets):
            if target.lat is not None and target.lon is not None:
                dist = haversine_distance(tee_lat, tee_lon, target.lat, target.lon)
                
                # Use target name if short, otherwise T1, T2, etc.
                name = target.name[:5] if target.name and len(target.name) <= 5 else f"T{i+1}"
                label_text = f"{name} {dist:.0f}y"
                
                try:
                    marker = self.map_widget.set_marker(
                        target.lat + 0.00005, target.lon,
                        text=label_text,
                        marker_color_circle="#FFFF44",
                        marker_color_outside="#333333"
                    )
                    self.distance_labels[f"target_{i}"] = marker
                except:
                    pass
        
        # Hazard distance labels
        for i, hazard in enumerate(self.features.hazards):
            if hazard.lat is not None and hazard.lon is not None:
                dist = haversine_distance(tee_lat, tee_lon, hazard.lat, hazard.lon)
                
                # Label based on hazard type
                htype = hazard.hazard_type
                if htype == "water":
                    prefix = "W"
                    color = "#4444FF"
                elif htype == "bunker":
                    prefix = "S"  # Sand
                    color = "#F4E4C1"
                elif htype == "ob":
                    prefix = "OB"
                    color = "#FFFFFF"
                else:
                    prefix = "HZ"
                    color = "#FF6666"
                
                label_text = f"{prefix} {dist:.0f}y"
                
                try:
                    marker = self.map_widget.set_marker(
                        hazard.lat + 0.00005, hazard.lon,
                        text=label_text,
                        marker_color_circle=color,
                        marker_color_outside="#FF0000"
                    )
                    self.distance_labels[f"hazard_{i}"] = marker
                except:
                    pass
    
    def _handle_break_marker_click(self, lat: float, lon: float):
        """Handle click near a break marker - start dragging."""
        # Check if click is near a break marker
        for i, break_point in enumerate(self.features.aim_breaks):
            if break_point.is_set():
                dist = haversine_distance(lat, lon, break_point.lat, break_point.lon)
                if dist < 15:  # Within 15 yards = click on marker
                    self.dragging_break_index = i
                    self._set_status(f"Dragging break point B{i+1}. Click to place.")
                    return True
        return False
    
    def _handle_break_marker_drag(self, lat: float, lon: float):
        """Handle placing a dragged break marker."""
        if hasattr(self, 'dragging_break_index') and self.dragging_break_index is not None:
            idx = self.dragging_break_index
            if 0 <= idx < len(self.features.aim_breaks):
                self.features.aim_breaks[idx] = GeoPoint(lat=lat, lon=lon)
                self.unsaved_changes = True
                self._render_aim_lines()
                self._set_status(f"Break point B{idx+1} moved.")
            self.dragging_break_index = None
            return True
        return False
    
    def _update_distance_rings(self):
        """Update distance ring display based on selections."""
        if not self.map_widget or not self.features.tee.is_set():
            return
        
        # Clear existing rings
        for ring in self.distance_rings:
            try:
                ring.delete()
            except:
                pass
        self.distance_rings = []
        
        if not self.show_distance_rings.get():
            return
        
        tee_lat = self.features.tee.lat
        tee_lon = self.features.tee.lon
        
        # Get the current ring presets (user's clubs or defaults)
        ring_presets = self._get_user_club_ring_presets()
        
        for preset_key, var in self.ring_vars.items():
            if var.get() and preset_key in ring_presets:
                preset = ring_presets[preset_key]
                ring_points = generate_distance_ring(
                    tee_lat, tee_lon, 
                    preset["distance"],
                    num_points=72
                )
                
                try:
                    ring = self.map_widget.set_path(
                        ring_points,
                        color=preset["color"],
                        width=2
                    )
                    self.distance_rings.append(ring)
                except Exception as e:
                    print(f"Error rendering distance ring: {e}")
    
    def _toggle_distance_rings(self):
        """Toggle distance rings visibility."""
        self._update_distance_rings()
    
    def _toggle_aim_lines(self):
        """Toggle aim lines visibility."""
        if self.show_aim_lines.get():
            self._render_aim_lines()
        else:
            for line in self.aim_lines:
                try:
                    line.delete()
                except:
                    pass
            self.aim_lines = []
    
    def _toggle_polygons(self):
        """Toggle polygon overlays visibility."""
        if self.show_polygons.get():
            for ptype in self.features.polygons:
                self._render_polygon(ptype)
        else:
            for poly in self.map_polygons.values():
                try:
                    poly.delete()
                except:
                    pass
            self.map_polygons = {}
    
    # === Distance Calculations ===
    
    def _update_distances_panel(self):
        """Update the distances panel with current calculations.
        
        # CHANGED: Now shows distances to each target and hazard from tee
        """
        map_features_dict = {
            "tee": self.features.tee.to_dict(),
            "green_front": self.features.green_front.to_dict(),
            "green_back": self.features.green_back.to_dict(),
            "targets": [t.to_dict() for t in self.features.targets],
            "hazards": [h.to_dict() for h in self.features.hazards]
        }
        
        distances = calculate_hole_distances(map_features_dict)
        
        # Update labels
        if distances["tee_to_green_front"] is not None:
            self.dist_labels["tee_to_front"].config(text=f"{distances['tee_to_green_front']:.0f} yds")
        else:
            self.dist_labels["tee_to_front"].config(text="--")
        
        if distances["tee_to_green_back"] is not None:
            self.dist_labels["tee_to_back"].config(text=f"{distances['tee_to_green_back']:.0f} yds")
        else:
            self.dist_labels["tee_to_back"].config(text="--")
        
        if distances["tee_to_green_center"] is not None:
            self.dist_labels["tee_to_center"].config(text=f"{distances['tee_to_green_center']:.0f} yds")
        else:
            self.dist_labels["tee_to_center"].config(text="--")
        
        if distances["green_depth"] is not None:
            self.dist_labels["green_depth"].config(text=f"{distances['green_depth']:.0f} yds")
        else:
            self.dist_labels["green_depth"].config(text="--")
        
        # Update route distance (curved fairway support)
        if distances.get("route_distance") is not None:
            # Show route distance in a different color to highlight it
            self.dist_labels["route_distance"].config(
                text=f"{distances['route_distance']:.0f} yds",
                foreground="#0066CC"  # Blue to distinguish from straight-line
            )
        else:
            # No targets set - route equals straight line
            self.dist_labels["route_distance"].config(text="--", foreground="")
        
        # Update targets list with distances
        self.targets_listbox.delete(0, tk.END)
        for target_dist in distances["targets"]:
            text = f"{target_dist['name']}: {target_dist['from_tee']:.0f}y"
            if target_dist['to_green']:
                text += f" → {target_dist['to_green']:.0f}y to green"
            self.targets_listbox.insert(tk.END, text)
        
        # CHANGED: Update hazards list with distances from tee
        self.hazards_listbox.delete(0, tk.END)
        if self.features.tee.is_set():
            for i, hazard in enumerate(self.features.hazards):
                if hazard.lat is not None and hazard.lon is not None:
                    dist_from_tee = haversine_distance(
                        self.features.tee.lat, self.features.tee.lon,
                        hazard.lat, hazard.lon
                    )
                    htype = hazard.hazard_type.title() if hazard.hazard_type else "Hazard"
                    # Calculate bearing for additional info
                    hdg = bearing(
                        self.features.tee.lat, self.features.tee.lon,
                        hazard.lat, hazard.lon
                    )
                    # Format bearing as compass direction
                    compass = self._bearing_to_compass(hdg)
                    text = f"{htype} #{i+1}: {dist_from_tee:.0f}y ({compass})"
                    self.hazards_listbox.insert(tk.END, text)
        
        # Validate against scorecard yardage
        if self.hole_yardage and distances["tee_to_green_center"]:
            is_valid, diff_pct = validate_yardage_difference(
                distances["tee_to_green_center"],
                self.hole_yardage
            )
            if not is_valid:
                self._set_status(f"⚠️ Map distance differs from scorecard by {diff_pct}%")
    
    def _bearing_to_compass(self, bearing_deg: float) -> str:
        """Convert bearing degrees to compass direction."""
        directions = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
        index = round(bearing_deg / 45) % 8
        return directions[index]
    
    # === Navigation ===
    
    def _prev_hole(self):
        """Navigate to previous hole."""
        if self._check_unsaved():
            new_hole = self.hole_num - 1
            if new_hole < 1:
                new_hole = len(self.course_data.get("pars", []))
            self._switch_hole(new_hole)
    
    def _next_hole(self):
        """Navigate to next hole."""
        if self._check_unsaved():
            new_hole = self.hole_num + 1
            if new_hole > len(self.course_data.get("pars", [])):
                new_hole = 1
            self._switch_hole(new_hole)
    
    def _switch_hole(self, new_hole: int):
        """Switch to a different hole."""
        # Store current map position before switching (for smart positioning)
        if self.map_widget and self.features.has_data():
            try:
                pos = self.map_widget.get_position()
                zoom = self.map_widget.zoom
                self.last_map_center = (pos[0], pos[1], zoom)
            except:
                pass
        
        # Store previous hole number for smart positioning
        prev_hole = self.hole_num
        
        # Load new hole
        self.hole_num = new_hole
        self.hole_par = self._get_hole_par()
        self.hole_yardage = self._get_hole_yardage()
        
        # Load features
        self.features = self.yardbook_mgr.get_hole_features(self.course_name, new_hole)
        
        # Update UI
        self.hole_label.config(text=f"Hole {self.hole_num}")
        self.par_label.config(text=f"Par {self.hole_par}")
        self.window.title(f"Yardbook - {self.course_name} - Hole {self.hole_num}")
        
        # Clear and re-render map
        self._clear_map_objects()
        self._render_all_features()
        self._update_distances_panel()
        
        # Smart center: use previous hole position if new hole has no data
        self._center_on_hole(prev_hole=prev_hole)
        
        # Reset state
        self.unsaved_changes = False
        self.temp_polygon_vertices = []
        self.dragging_marker = None
        self._set_status("Ready.")
    
    def _clear_map_objects(self):
        """Clear all map objects."""
        # Clear markers
        for marker in self.map_markers.values():
            if isinstance(marker, list):
                for m in marker:
                    try:
                        m.delete()
                    except:
                        pass
            else:
                try:
                    marker.delete()
                except:
                    pass
        self.map_markers = {}
        
        # Clear paths
        for path in self.map_paths:
            try:
                path.delete()
            except:
                pass
        self.map_paths = []
        
        # Clear polygons
        for poly in self.map_polygons.values():
            try:
                poly.delete()
            except:
                pass
        self.map_polygons = {}
        
        # Clear distance rings
        for ring in self.distance_rings:
            try:
                ring.delete()
            except:
                pass
        self.distance_rings = []
        
        # Clear aim lines
        for line in self.aim_lines:
            try:
                line.delete()
            except:
                pass
        self.aim_lines = []
        
        # Clear break markers
        for marker in self.break_markers:
            try:
                marker.delete()
            except:
                pass
        self.break_markers = []
        
        # Clear distance labels
        for label in self.distance_labels.values():
            try:
                label.delete()
            except:
                pass
        self.distance_labels = {}
    
    def _center_on_hole(self, prev_hole: Optional[int] = None):
        """
        Center the map on the hole, showing from tee to green.
        
        Smart positioning: If current hole has no data, use previous hole's
        position or last known map center to keep user in the same area.
        """
        if not self.map_widget:
            return
        
        # If we have both tee and green data, center between them
        if self.features.tee.is_set() and self.features.green_back.is_set():
            # Calculate center point between tee and green back
            tee_lat, tee_lon = self.features.tee.lat, self.features.tee.lon
            gb_lat, gb_lon = self.features.green_back.lat, self.features.green_back.lon
            
            # Get the midpoint
            center_lat, center_lon = midpoint(tee_lat, tee_lon, gb_lat, gb_lon)
            
            # Calculate the hole length to determine appropriate zoom
            hole_length = haversine_distance(tee_lat, tee_lon, gb_lat, gb_lon)
            zoom = self._calculate_zoom_for_distance(hole_length)
            
            self.map_widget.set_position(center_lat, center_lon)
            self.map_widget.set_zoom(zoom)
            self.last_map_center = (center_lat, center_lon, zoom)
            
        elif self.features.tee.is_set() and self.features.green_front.is_set():
            # Fall back to tee and green front
            tee_lat, tee_lon = self.features.tee.lat, self.features.tee.lon
            gf_lat, gf_lon = self.features.green_front.lat, self.features.green_front.lon
            
            center_lat, center_lon = midpoint(tee_lat, tee_lon, gf_lat, gf_lon)
            hole_length = haversine_distance(tee_lat, tee_lon, gf_lat, gf_lon)
            zoom = self._calculate_zoom_for_distance(hole_length)
            
            self.map_widget.set_position(center_lat, center_lon)
            self.map_widget.set_zoom(zoom)
            self.last_map_center = (center_lat, center_lon, zoom)
            
        elif self.features.tee.is_set():
            # Just tee - zoom in close
            self.map_widget.set_position(self.features.tee.lat, self.features.tee.lon)
            self.map_widget.set_zoom(19)
            self.last_map_center = (self.features.tee.lat, self.features.tee.lon, 19)
            
        elif self.features.green_front.is_set():
            # Just green - zoom in close
            self.map_widget.set_position(self.features.green_front.lat, self.features.green_front.lon)
            self.map_widget.set_zoom(19)
            self.last_map_center = (self.features.green_front.lat, self.features.green_front.lon, 19)
            
        else:
            # No data for this hole - use smart positioning
            position_set = False
            
            # SMART POSITIONING: Try previous hole's data first
            if prev_hole is not None and prev_hole != self.hole_num:
                prev_features = self.yardbook_mgr.get_hole_features(self.course_name, prev_hole)
                
                if prev_features.tee.is_set():
                    self.map_widget.set_position(prev_features.tee.lat, prev_features.tee.lon)
                    self.map_widget.set_zoom(18)
                    position_set = True
                    self._set_status("Positioned near previous hole. Place tee to begin.")
                elif prev_features.green_front.is_set():
                    self.map_widget.set_position(prev_features.green_front.lat, prev_features.green_front.lon)
                    self.map_widget.set_zoom(18)
                    position_set = True
                    self._set_status("Positioned near previous hole. Place tee to begin.")
                elif prev_features.green_back.is_set():
                    self.map_widget.set_position(prev_features.green_back.lat, prev_features.green_back.lon)
                    self.map_widget.set_zoom(18)
                    position_set = True
                    self._set_status("Positioned near previous hole. Place tee to begin.")
            
            # Use last known map center if available
            if not position_set and self.last_map_center:
                lat, lon, zoom = self.last_map_center
                self.map_widget.set_position(lat, lon)
                self.map_widget.set_zoom(zoom)
                position_set = True
                self._set_status("Using last map position. Place tee to begin.")
            
            # Fall back to course location or default
            if not position_set:
                course_lat = self.course_data.get("latitude")
                course_lon = self.course_data.get("longitude")
                
                if course_lat and course_lon:
                    self.map_widget.set_position(course_lat, course_lon)
                    self.map_widget.set_zoom(17)
                else:
                    # Default position (roughly center of US as fallback)
                    self.map_widget.set_position(39.8283, -98.5795)
                    self.map_widget.set_zoom(15)
                
                self._set_status("Position the map and place the tee marker to begin.")
    
    def _calculate_zoom_for_distance(self, hole_length: float) -> int:
        """Calculate appropriate zoom level based on hole length."""
        if hole_length < 150:
            return 20  # Very short par 3
        elif hole_length < 200:
            return 19  # Short par 3
        elif hole_length < 280:
            return 19  # Long par 3 / very short par 4
        elif hole_length < 350:
            return 18  # Short par 4
        elif hole_length < 430:
            return 18  # Medium par 4
        elif hole_length < 500:
            return 17  # Long par 4 / short par 5
        elif hole_length < 550:
            return 17  # Medium par 5
        else:
            return 16  # Long par 5
    
    # === Save/Load ===
    
    def _save_features(self):
        """Save current hole features to file."""
        self.yardbook_mgr.save_hole_features(
            self.course_name,
            self.hole_num,
            self.features
        )
        
        self.unsaved_changes = False
        self._set_status("✓ Saved!")
        
        if self.on_save_callback:
            self.on_save_callback()
    
    def _clear_all(self):
        """Clear all features for current hole."""
        if not messagebox.askyesno("Confirm", "Clear all map data for this hole?"):
            return
        
        self.features.clear_all()
        self._clear_map_objects()
        self._update_distances_panel()
        self.unsaved_changes = True
        self._set_status("All data cleared. Click Save to confirm.")
    
    def _check_unsaved(self) -> bool:
        """Check for unsaved changes and prompt user."""
        if not self.unsaved_changes:
            return True
        
        result = messagebox.askyesnocancel(
            "Unsaved Changes",
            "You have unsaved changes. Save before continuing?"
        )
        
        if result is None:  # Cancel
            return False
        elif result:  # Yes
            self._save_features()
        # No - continue without saving
        
        return True
    
    def _on_close(self):
        """Handle window close."""
        if self._check_unsaved():
            self.window.destroy()
    
    # === Dialogs ===
    
    def _simple_input_dialog(self, title: str, prompt: str, default: str = "") -> Optional[str]:
        """Show a simple input dialog."""
        dialog = tk.Toplevel(self.window)
        dialog.title(title)
        dialog.geometry("300x100")
        dialog.transient(self.window)
        dialog.grab_set()
        
        ttk.Label(dialog, text=prompt).pack(pady=5)
        
        entry = ttk.Entry(dialog, width=30)
        entry.insert(0, default)
        entry.pack(pady=5)
        entry.focus()
        
        result = [None]
        
        def on_ok():
            result[0] = entry.get()
            dialog.destroy()
        
        def on_cancel():
            dialog.destroy()
        
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=5)
        ttk.Button(btn_frame, text="OK", command=on_ok).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Cancel", command=on_cancel).pack(side='left', padx=5)
        
        entry.bind('<Return>', lambda e: on_ok())
        entry.bind('<Escape>', lambda e: on_cancel())
        
        dialog.wait_window()
        return result[0]
    
    def _edit_target(self, event):
        """Edit selected target."""
        selection = self.targets_listbox.curselection()
        if not selection:
            return
        
        index = selection[0]
        if index >= len(self.features.targets):
            return
        
        target = self.features.targets[index]
        new_name = self._simple_input_dialog("Edit Target", "Enter new name:", target.name)
        
        if new_name and new_name != target.name:
            target.name = new_name
            self._render_target_marker(target, index)
            self._update_distances_panel()
            self.unsaved_changes = True
    
    def _delete_target(self, event):
        """Delete selected target."""
        selection = self.targets_listbox.curselection()
        if not selection:
            return
        
        index = selection[0]
        if index >= len(self.features.targets):
            return
        
        if messagebox.askyesno("Confirm", "Delete this target?"):
            # Remove marker
            key = f"target_{index}"
            if key in self.map_markers:
                try:
                    self.map_markers[key].delete()
                except:
                    pass
                del self.map_markers[key]
            
            # Remove from features
            self.features.targets.pop(index)
            
            # Re-render remaining targets
            self._render_all_features()
            self._update_distances_panel()
            self.unsaved_changes = True
    
    def _render_on_map_distances(self):
        """Render distance labels directly on the map (greenbook style)."""
        if not self.map_widget:
            return
        
        # This would require custom canvas drawing over the map
        # For now, we'll use the aim lines with distance markers
        # Full implementation would use tkinter canvas overlay
        pass
    
    # NOTE: OSM Import feature has been removed from the app.
    # Manual polygon drawing is the only way to add course features.
    
    def _get_map_center(self) -> Tuple[Optional[float], Optional[float]]:
        """Get the current map center coordinates."""
        # First, try tee position
        if self.features.tee.is_set():
            return self.features.tee.lat, self.features.tee.lon
        
        # Try green position
        if self.features.green_front.is_set():
            return self.features.green_front.lat, self.features.green_front.lon
        
        # Try to get from map widget
        if self.map_widget:
            try:
                pos = self.map_widget.get_position()
                if pos:
                    return pos[0], pos[1]
            except:
                pass
        
        # Try course location if available
        course_lat = self.course_data.get("latitude")
        course_lon = self.course_data.get("longitude")
        if course_lat and course_lon:
            return course_lat, course_lon
        
        return None, None
    
    # CHANGED: Greenbook View feature removed per requirements.
    # Method kept as stub to prevent crashes if called from anywhere else.
    def _show_greenbook_view(self):
        """Greenbook View feature has been removed."""
        messagebox.showinfo(
            "Feature Removed",
            "The Greenbook View feature has been removed.\n\n"
            "Use the main yardbook map view for all hole visualization."
        )
    
    def _draw_greenbook_hole(self, canvas, width: int, height: int, distances: Dict):
        """Greenbook hole drawing - feature removed."""
        pass


def open_yardbook(
    parent: tk.Tk,
    course_data: Dict,
    hole_num: int,
    courses_file: str,
    on_save_callback: Optional[Callable] = None,
    selected_tee: Optional[str] = None,
    club_distances: Optional[List[Dict]] = None
) -> yardbookView:
    """
    Convenience function to open the yardbook view.
    
    Args:
        parent: Parent Tkinter window
        course_data: Course dictionary from backend
        hole_num: Hole number to display
        courses_file: Path to courses.json
        on_save_callback: Optional callback when data is saved
        selected_tee: Selected tee box color
        club_distances: User's club distances (list of {"name": str, "distance": int})
    
    Returns:
        yardbookView instance
    """
    return yardbookView(
        parent=parent,
        course_data=course_data,
        hole_num=hole_num,
        courses_file=courses_file,
        on_save_callback=on_save_callback,
        selected_tee=selected_tee,
        club_distances=club_distances
    )

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
        
        self.active_yardbook = None
    
    def is_available(self) -> bool:
        """Check if yardbook feature is available."""
        return is_map_available()
    
    def _get_user_club_distances(self) -> List[Dict]:
        """
        Get the user's club distances from the backend.
        
        Returns:
            List of club dictionaries with name and distance
        """
        try:
            clubs = self.backend.get_clubs()
            if clubs:
                return clubs
        except Exception as e:
            print(f"Warning: Could not load user club distances: {e}")
        return []
    
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
        
        # Get the user's club distances
        club_distances = self._get_user_club_distances()
        
        self.active_yardbook = open_yardbook(
            parent=parent,
            course_data=course_data,
            hole_num=hole_num,
            courses_file=self.courses_file,
            on_save_callback=lambda: self._on_yardbook_save(course_data["name"]),
            club_distances=club_distances
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
    
    # CHANGED: Added Club selection dropdown to filter courses by club,
    # matching the "log a round" UI pattern.
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
        self.window.geometry("500x500")  # CHANGED: Slightly taller to fit club dropdown
        self.window.transient(parent)
        self.window.grab_set()
        
        self._create_ui()
        self._populate_clubs()  # CHANGED: Populate clubs first
    
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
        
        # CHANGED: Added Club selection (like log-a-round)
        selection_frame = ttk.LabelFrame(main_frame, text="Select Course", padding=10)
        selection_frame.pack(fill='x', pady=(0, 10))
        
        # Club dropdown
        club_row = ttk.Frame(selection_frame)
        club_row.pack(fill='x', pady=(0, 5))
        ttk.Label(club_row, text="Club:", width=8).pack(side='left')
        self.club_var = tk.StringVar(value="All Clubs")
        self.club_combo = ttk.Combobox(
            club_row,
            textvariable=self.club_var,
            state='readonly',
            width=42
        )
        self.club_combo.pack(side='left', fill='x', expand=True)
        self.club_combo.bind('<<ComboboxSelected>>', self._on_club_selected)
        
        # Course dropdown
        course_row = ttk.Frame(selection_frame)
        course_row.pack(fill='x', pady=(0, 5))
        ttk.Label(course_row, text="Course:", width=8).pack(side='left')
        self.course_var = tk.StringVar()
        self.course_combo = ttk.Combobox(
            course_row,
            textvariable=self.course_var,
            state='readonly',
            width=42
        )
        self.course_combo.pack(side='left', fill='x', expand=True)
        self.course_combo.bind('<<ComboboxSelected>>', self._on_course_selected)
        
        # Course info
        self.course_info_label = ttk.Label(
            selection_frame,
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
    
    # CHANGED: Added _populate_clubs method and modified _populate_courses
    def _populate_clubs(self):
        """Populate the club dropdown and trigger course population."""
        courses = self.backend.get_courses()
        
        # Get unique club names
        clubs = sorted(list(set(c.get("club", "") for c in courses if c.get("club"))))
        if "" in clubs:
            clubs.remove("")
        
        # Add "All Clubs" option at the start
        clubs = ["All Clubs"] + clubs
        
        self.club_combo['values'] = clubs
        
        # Set default and trigger course population
        if clubs:
            self.club_combo.set("All Clubs")
            self._on_club_selected()
    
    def _on_club_selected(self, event=None):
        """Handle club selection change - filter courses by selected club."""
        selected_club = self.club_var.get()
        courses = self.backend.get_courses()
        
        # Filter courses by club
        if selected_club == "All Clubs":
            filtered = courses
        else:
            filtered = [c for c in courses if c.get("club") == selected_club]
        
        # Sort by name
        course_names = [c["name"] for c in sorted(filtered, key=lambda x: x["name"])]
        
        self.course_combo['values'] = course_names
        
        # Select first course if available
        if course_names:
            self.course_combo.set(course_names[0])
            self._on_course_selected()
        else:
            self.course_combo.set("")
            self.course_info_label.config(text="No courses found for this club")
    
    def _populate_courses(self):
        """Populate the course dropdown (called after club selection)."""
        # This is now handled by _on_club_selected
        pass
    
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
        
        # CHANGED: Don't repeat club name if already selected
        selected_club = self.club_var.get()
        if selected_club == "All Clubs":
            info_text = f"{course.get('club', '')} • {num_holes} holes • Par {total_par}"
        else:
            info_text = f"{num_holes} holes • Par {total_par}"
        
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


# ============================================================================
# HELPER WINDOWS FOR GOLF APP (Apple HIG-inspired design)
# ============================================================================

class LogRoundWindow:
    """Window for entering round scores - supports quick and detailed entry modes."""
    
    def __init__(self, parent, backend, course, tee, holes_choice, round_type, 
                 is_serious, selected_date, on_complete=None):
        self.backend = backend
        self.course = course
        self.tee = tee
        self.holes_choice = holes_choice
        self.round_type = round_type
        self.is_serious = is_serious
        self.selected_date = selected_date
        self.on_complete = on_complete
        
        self.window = tk.Toplevel(parent)
        self.window.title(f"Log Round - {course['name']}")
        self.window.geometry("500x600")
        self.window.transient(parent)
        
        # Determine which holes to score
        all_pars = course["pars"]
        if holes_choice == "front_9":
            self.holes_to_score = list(range(9))
        elif holes_choice == "back_9":
            self.holes_to_score = list(range(9, min(18, len(all_pars))))
        else:
            self.holes_to_score = list(range(len(all_pars)))
        
        self._build_ui()
    
    def _build_ui(self):
        """Build the score entry UI."""
        main = ttk.Frame(self.window, padding=15)
        main.pack(fill='both', expand=True)
        
        # Header
        header = ttk.Frame(main)
        header.pack(fill='x', pady=(0, 10))
        
        ttk.Label(header, text=self.course['name'], 
                 font=("Helvetica", 16, "bold")).pack(anchor='w')
        
        par_total = sum(self.course["pars"][i] for i in self.holes_to_score)
        holes_text = f"{len(self.holes_to_score)} holes • Par {par_total}"
        ttk.Label(header, text=holes_text, font=("Helvetica", 12),
                 foreground="#8E8E93").pack(anchor='w')
        
        # Entry mode selection
        mode_frame = ttk.LabelFrame(main, text="Entry Mode", padding=8)
        mode_frame.pack(fill='x', pady=(0, 10))
        
        self.entry_mode = tk.StringVar(value="quick")
        ttk.Radiobutton(mode_frame, text="Quick (scores only)", 
                       variable=self.entry_mode, value="quick",
                       command=self._refresh_score_area).pack(anchor='w')
        ttk.Radiobutton(mode_frame, text="Detailed (scores + clubs)", 
                       variable=self.entry_mode, value="detailed",
                       command=self._refresh_score_area).pack(anchor='w')
        
        # Running total
        self.running_total_var = tk.StringVar(value="Total: 0")
        ttk.Label(main, textvariable=self.running_total_var,
                 font=("Helvetica", 14, "bold")).pack(pady=5)
        
        # Scrollable score area
        self.score_container = ttk.Frame(main)
        self.score_container.pack(fill='both', expand=True)
        
        # Submit button
        ttk.Button(main, text="Submit Round", command=self._submit_round).pack(pady=10)
        
        # Build initial score area
        self._refresh_score_area()
    
    def _refresh_score_area(self):
        """Refresh the score entry area based on mode."""
        for widget in self.score_container.winfo_children():
            widget.destroy()
        
        # Create scrollable canvas
        canvas = tk.Canvas(self.score_container, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.score_container, orient="vertical", command=canvas.yview)
        frame = ttk.Frame(canvas)
        
        frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        
        # Headers
        headers = ["Hole", "Par", "Score"]
        for col, h in enumerate(headers):
            ttk.Label(frame, text=h, font=("Helvetica", 10, "bold")).grid(
                row=0, column=col, padx=8, pady=4)
        
        # Score entries
        self.score_vars = []
        all_pars = self.course["pars"]
        yardages = self.course.get("yardages", {}).get(self.tee, [])
        
        for idx, hole_num in enumerate(self.holes_to_score):
            row = idx + 1
            par = all_pars[hole_num]
            
            ttk.Label(frame, text=str(hole_num + 1)).grid(row=row, column=0, padx=8)
            ttk.Label(frame, text=str(par)).grid(row=row, column=1, padx=8)
            
            score_var = tk.StringVar()
            score_var.trace_add("write", lambda *args: self._update_total())
            self.score_vars.append(score_var)
            
            entry = ttk.Entry(frame, width=5, textvariable=score_var, justify='center')
            entry.grid(row=row, column=2, padx=8, pady=2)
    
    def _update_total(self):
        """Update running total."""
        total = 0
        for var in self.score_vars:
            try:
                val = int(var.get())
                total += val
            except:
                pass
        
        par_total = sum(self.course["pars"][i] for i in self.holes_to_score)
        diff = total - par_total
        diff_str = f"+{diff}" if diff > 0 else str(diff)
        self.running_total_var.set(f"Total: {total} ({diff_str})")
    
    def _submit_round(self):
        """Submit the round."""
        scores = []
        for var in self.score_vars:
            try:
                scores.append(int(var.get()))
            except:
                messagebox.showerror("Error", "Please enter valid scores for all holes")
                return
        
        total = sum(scores)
        par = sum(self.course["pars"][i] for i in self.holes_to_score)
        holes_played = len(self.holes_to_score)
        
        # Get tee box info
        box = next((b for b in self.course.get("tee_boxes", []) 
                   if b["color"] == self.tee), None)
        tee_rating = box["rating"] if box else 72
        tee_slope = box["slope"] if box else 113
        
        if holes_played == 9:
            tee_rating = tee_rating / 2
        
        # Build full scores array
        full_scores = [None] * len(self.course["pars"])
        for idx, hole_num in enumerate(self.holes_to_score):
            full_scores[hole_num] = scores[idx]
        
        date_str = self.selected_date.strftime("%Y-%m-%d") + " " + datetime.now().strftime("%H:%M")
        
        rd = {
            "course_name": self.course["name"],
            "tee_color": self.tee,
            "scores": full_scores,
            "is_serious": self.is_serious,
            "round_type": self.round_type,
            "notes": "",
            "holes_played": holes_played,
            "holes_choice": self.holes_choice,
            "total_score": total,
            "par": par,
            "tee_rating": tee_rating,
            "tee_slope": tee_slope,
            "date": date_str,
            "entry_mode": self.entry_mode.get(),
            "detailed_stats": []
        }
        
        # Calculate target score
        course_handicap, target_score = self.backend.calculate_course_handicap(
            self.course["name"], self.tee, self.holes_choice
        )
        rd["target_score"] = target_score if target_score else par
        
        self.backend.rounds.append(rd)
        save_json(ROUNDS_FILE, self.backend.rounds)
        self.backend.invalidate_stats_cache()
        
        self.window.destroy()
        
        # Show completion message
        diff = total - par
        diff_str = f"+{diff}" if diff > 0 else str(diff)
        messagebox.showinfo("Round Saved", 
            f"Score: {total} ({diff_str})\n"
            f"Course: {self.course['name']}\n"
            f"Holes: {holes_played}")
        
        if self.on_complete:
            self.on_complete()


class ScorecardDetailWindow:
    """Window showing detailed scorecard view."""
    
    def __init__(self, parent, backend, round_data):
        self.backend = backend
        self.round_data = round_data
        
        self.window = tk.Toplevel(parent)
        self.window.title("Scorecard Details")
        self.window.geometry("650x550")
        self.window.transient(parent)
        
        self._build_ui()
    
    def _build_ui(self):
        """Build the scorecard detail UI."""
        main = ttk.Frame(self.window, padding=15)
        main.pack(fill='both', expand=True)
        
        rd = self.round_data
        
        # Header
        ttk.Label(main, text=rd["course_name"],
                 font=("Helvetica", 18, "bold")).pack(anchor='w')
        
        diff = rd['total_score'] - rd.get('par', 72)
        diff_str = f"+{diff}" if diff > 0 else str(diff)
        
        # Course info with tee box
        course = self.backend.get_course_by_name(rd["course_name"])
        tee_color = rd.get('tee_color', '')
        
        info_text = f"{rd.get('date', 'N/A')[:10]}"
        if tee_color:
            info_text += f" • {tee_color} Tees"
        
        # Get total yardage for tee
        if course:
            yardages = course.get("yardages", {}).get(tee_color, [])
            if yardages:
                total_yardage = sum(y for y in yardages if y)
                info_text += f" • {total_yardage} yards"
        
        ttk.Label(main, text=info_text, font=("Helvetica", 12),
                 foreground="#8E8E93").pack(anchor='w', pady=(0, 10))
        
        # Score summary
        summary = ttk.Frame(main)
        summary.pack(fill='x', pady=10)
        
        ttk.Label(summary, text="Score:", font=("Helvetica", 14)).pack(side='left')
        ttk.Label(summary, text=f"{rd['total_score']} ({diff_str})",
                 font=("Helvetica", 20, "bold")).pack(side='left', padx=10)
        
        if rd.get("target_score"):
            target_diff = rd['total_score'] - rd['target_score']
            target_str = f"+{target_diff}" if target_diff > 0 else str(target_diff)
            ttk.Label(summary, text=f"vs Target: {target_str}",
                     font=("Helvetica", 12), foreground="#8E8E93").pack(side='left', padx=10)
        
        # Hole-by-hole scores with yardage
        pars = course["pars"] if course else [4] * len(rd.get("scores", []))
        scores = rd.get("scores", [])
        yardages = course.get("yardages", {}).get(tee_color, []) if course else []
        
        # Create treeview for scores - now includes yardage
        cols = ("Hole", "Yards", "Par", "Score", "+/-")
        tree = ttk.Treeview(main, columns=cols, show="headings", height=12)
        
        tree.heading("Hole", text="Hole")
        tree.heading("Yards", text="Yards")
        tree.heading("Par", text="Par")
        tree.heading("Score", text="Score")
        tree.heading("+/-", text="+/-")
        
        tree.column("Hole", width=50, anchor='center')
        tree.column("Yards", width=70, anchor='center')
        tree.column("Par", width=50, anchor='center')
        tree.column("Score", width=60, anchor='center')
        tree.column("+/-", width=50, anchor='center')
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(main, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        tree_frame = ttk.Frame(main)
        tree_frame.pack(fill='both', expand=True, pady=10)
        tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        for i, (par, score) in enumerate(zip(pars, scores)):
            if score is not None:
                hole_diff = score - par
                diff_str = f"+{hole_diff}" if hole_diff > 0 else str(hole_diff)
                yard = yardages[i] if i < len(yardages) and yardages[i] else ""
                tree.insert("", "end", values=(i + 1, yard, par, score, diff_str))
        
        # Totals row
        if scores:
            valid_scores = [s for s in scores if s is not None]
            total_yards = sum(y for y in yardages if y) if yardages else ""
            total_par = sum(pars)
            tree.insert("", "end", values=("Total", total_yards, total_par, 
                       rd['total_score'], f"+{diff}" if diff > 0 else str(diff)))
        
        # Notes
        if rd.get("notes"):
            notes_frame = ttk.LabelFrame(main, text="Notes", padding=8)
            notes_frame.pack(fill='x', pady=10)
            ttk.Label(notes_frame, text=rd["notes"], wraplength=500).pack(anchor='w')
        
        ttk.Button(main, text="Close", command=self.window.destroy).pack(pady=10)


class CourseEditorWindow:
    """Window for adding/editing courses."""
    
    def __init__(self, parent, backend, course=None, on_save=None):
        self.backend = backend
        self.editing_course = course
        self.original_name = course["name"] if course else None
        self.on_save = on_save
        
        self.window = tk.Toplevel(parent)
        self.window.title("Edit Course" if course else "Add New Course")
        self.window.geometry("500x600")
        self.window.transient(parent)
        
        self._build_ui()
    
    def _build_ui(self):
        """Build the course editor UI."""
        main = ttk.Frame(self.window, padding=15)
        main.pack(fill='both', expand=True)
        
        # Course info
        info_frame = ttk.LabelFrame(main, text="Course Information", padding=10)
        info_frame.pack(fill='x', pady=(0, 10))
        
        ttk.Label(info_frame, text="Course Name:").grid(row=0, column=0, sticky='e', padx=5)
        self.name_var = tk.StringVar(value=self.editing_course["name"] if self.editing_course else "")
        ttk.Entry(info_frame, textvariable=self.name_var, width=30).grid(row=0, column=1, pady=3)
        
        ttk.Label(info_frame, text="Club Name:").grid(row=1, column=0, sticky='e', padx=5)
        self.club_var = tk.StringVar(value=self.editing_course.get("club", "") if self.editing_course else "")
        ttk.Entry(info_frame, textvariable=self.club_var, width=30).grid(row=1, column=1, pady=3)
        
        ttk.Label(info_frame, text="Number of Holes:").grid(row=2, column=0, sticky='e', padx=5)
        self.holes_var = tk.StringVar(value="18")
        if self.editing_course:
            self.holes_var.set(str(len(self.editing_course["pars"])))
        ttk.Entry(info_frame, textvariable=self.holes_var, width=10).grid(row=2, column=1, sticky='w', pady=3)
        
        # Pars
        pars_frame = ttk.LabelFrame(main, text="Pars (comma-separated)", padding=10)
        pars_frame.pack(fill='x', pady=(0, 10))
        
        default_pars = ",".join(map(str, self.editing_course["pars"])) if self.editing_course else "4,4,4,3,5,4,4,3,5,4,4,4,3,5,4,4,3,5"
        self.pars_var = tk.StringVar(value=default_pars)
        ttk.Entry(pars_frame, textvariable=self.pars_var, width=50).pack(fill='x')
        
        # Tee boxes
        tees_frame = ttk.LabelFrame(main, text="Tee Boxes", padding=10)
        tees_frame.pack(fill='x', pady=(0, 10))
        
        self.tee_entries = []
        
        if self.editing_course:
            for tee in self.editing_course.get("tee_boxes", []):
                self._add_tee_row(tees_frame, tee)
        else:
            self._add_tee_row(tees_frame, {"color": "White", "rating": "72.0", "slope": "113"})
        
        ttk.Button(tees_frame, text="+ Add Tee Box", 
                  command=lambda: self._add_tee_row(tees_frame)).pack(anchor='w', pady=5)
        
        # Buttons
        btn_frame = ttk.Frame(main)
        btn_frame.pack(fill='x', pady=15)
        
        ttk.Button(btn_frame, text="Save Course", command=self._save_course).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.window.destroy).pack(side='left', padx=5)
    
    def _add_tee_row(self, parent, tee_data=None):
        """Add a tee box entry row."""
        row = ttk.Frame(parent)
        row.pack(fill='x', pady=2)
        
        color_var = tk.StringVar(value=tee_data.get("color", "") if tee_data else "")
        rating_var = tk.StringVar(value=str(tee_data.get("rating", "")) if tee_data else "")
        slope_var = tk.StringVar(value=str(tee_data.get("slope", "")) if tee_data else "")
        
        ttk.Label(row, text="Color:").pack(side='left')
        ttk.Entry(row, textvariable=color_var, width=10).pack(side='left', padx=2)
        
        ttk.Label(row, text="Rating:").pack(side='left', padx=(10, 0))
        ttk.Entry(row, textvariable=rating_var, width=6).pack(side='left', padx=2)
        
        ttk.Label(row, text="Slope:").pack(side='left', padx=(10, 0))
        ttk.Entry(row, textvariable=slope_var, width=5).pack(side='left', padx=2)
        
        self.tee_entries.append((color_var, rating_var, slope_var, row))
    
    def _save_course(self):
        """Save the course."""
        name = self.name_var.get().strip()
        club = self.club_var.get().strip()
        
        if not name:
            messagebox.showerror("Error", "Course name is required")
            return
        
        try:
            pars = [int(p.strip()) for p in self.pars_var.get().split(",")]
        except:
            messagebox.showerror("Error", "Invalid pars format")
            return
        
        tee_boxes = []
        for color_var, rating_var, slope_var, _ in self.tee_entries:
            color = color_var.get().strip()
            if color:
                try:
                    rating = float(rating_var.get())
                    slope = int(slope_var.get())
                    tee_boxes.append({"color": color, "rating": rating, "slope": slope})
                except:
                    pass
        
        course_data = {
            "name": name,
            "club": club,
            "pars": pars,
            "tee_boxes": tee_boxes,
            "yardages": self.editing_course.get("yardages", {}) if self.editing_course else {}
        }
        
        if self.editing_course:
            self.backend.update_course(self.original_name, course_data)
        else:
            self.backend.add_course(course_data)
        
        self.window.destroy()
        
        if self.on_save:
            self.on_save()


class ExportDialog:
    """Dialog for exporting scorecards."""
    
    def __init__(self, parent, backend, round_data):
        self.backend = backend
        self.round_data = round_data
        
        self.window = tk.Toplevel(parent)
        self.window.title("Export Scorecard")
        self.window.geometry("300x200")
        self.window.transient(parent)
        
        self._build_ui()
    
    def _build_ui(self):
        """Build the export dialog UI."""
        main = ttk.Frame(self.window, padding=20)
        main.pack(fill='both', expand=True)
        
        ttk.Label(main, text="Export Scorecard", 
                 font=("Helvetica", 16, "bold")).pack(pady=(0, 15))
        
        ttk.Label(main, text="Choose export format:").pack(anchor='w')
        
        self.format_var = tk.StringVar(value="pdf")
        ttk.Radiobutton(main, text="PDF Document", variable=self.format_var, 
                       value="pdf").pack(anchor='w', pady=2)
        ttk.Radiobutton(main, text="Image (PNG)", variable=self.format_var,
                       value="image").pack(anchor='w', pady=2)
        
        btn_frame = ttk.Frame(main)
        btn_frame.pack(fill='x', pady=15)
        
        ttk.Button(btn_frame, text="Export", command=self._do_export).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.window.destroy).pack(side='left', padx=5)
    
    def _do_export(self):
        """Perform the export."""
        format_type = self.format_var.get()
        
        if format_type == "pdf":
            self._export_pdf()
        else:
            self._export_image()
    
    def _export_pdf(self):
        """Export as PDF."""
        from tkinter import filedialog
        filepath = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")],
            initialfile=f"scorecard_{self.round_data['course_name'].replace(' ', '_')}.pdf"
        )
        
        if filepath:
            try:
                scorecard_data = generate_scorecard_data(self.backend, self.round_data)
                self._create_pdf(filepath, scorecard_data)
                messagebox.showinfo("Success", f"Scorecard exported to:\n{filepath}")
                self.window.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export: {e}")
    
    def _export_image(self):
        """Export as image."""
        from tkinter import filedialog
        filepath = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG files", "*.png")],
            initialfile=f"scorecard_{self.round_data['course_name'].replace(' ', '_')}.png"
        )
        
        if filepath:
            messagebox.showinfo("Info", "Image export not yet implemented")
            self.window.destroy()
    
    def _create_pdf(self, filepath, data):
        """Create a PDF scorecard."""
        doc = SimpleDocTemplate(filepath, pagesize=landscape(letter))
        styles = getSampleStyleSheet()
        elements = []
        
        # Title
        title_style = ParagraphStyle('Title', parent=styles['Heading1'], 
                                     fontSize=18, alignment=1)
        elements.append(Paragraph(data['course_name'], title_style))
        elements.append(Spacer(1, 12))
        
        # Info
        info_text = f"Date: {data['date']} | Tees: {data['tee_color']} | Score: {data['total_score']} ({data['diff_str']})"
        elements.append(Paragraph(info_text, styles['Normal']))
        elements.append(Spacer(1, 20))
        
        # Scores table
        scores = data['scores']
        pars = data['pars']
        yardages = data.get('yardages', [])
        
        # Front 9 table
        front_data = [
            ['Hole'] + [str(i+1) for i in range(min(9, len(scores)))] + ['OUT'],
        ]
        if yardages:
            front_data.append(['Yards'] + [str(y) if y else '-' for y in yardages[:9]] + [str(sum(y for y in yardages[:9] if y))])
        front_data.extend([
            ['Par'] + [str(p) for p in pars[:9]] + [str(sum(pars[:9]))],
            ['Score'] + [str(s) if s else '-' for s in scores[:9]] + [str(sum(s for s in scores[:9] if s))]
        ])
        
        front_table = Table(front_data)
        front_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#007AFF')),  # Blue header
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('BACKGROUND', (-1, 0), (-1, -1), colors.HexColor('#E8E8E8')),  # OUT column
        ]))
        elements.append(front_table)
        elements.append(Spacer(1, 12))
        
        # Back 9 table (if applicable)
        if len(scores) > 9:
            back_data = [
                ['Hole'] + [str(i+10) for i in range(min(9, len(scores)-9))] + ['IN', 'TOT'],
            ]
            if yardages and len(yardages) > 9:
                back_yards = yardages[9:18]
                total_yards = sum(y for y in yardages if y)
                back_data.append(['Yards'] + [str(y) if y else '-' for y in back_yards] + 
                               [str(sum(y for y in back_yards if y)), str(total_yards)])
            back_data.extend([
                ['Par'] + [str(p) for p in pars[9:18]] + [str(sum(pars[9:18])), str(sum(pars))],
            ])
            back_scores = [s for s in scores[9:18] if s]
            back_data.append(['Score'] + [str(s) if s else '-' for s in scores[9:18]] + 
                            [str(sum(back_scores)), str(data['total_score'])])
            
            back_table = Table(back_data)
            back_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#007AFF')),  # Blue header
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('BACKGROUND', (-2, 0), (-1, -1), colors.HexColor('#E8E8E8')),  # IN/TOT columns
            ]))
            elements.append(back_table)
        
        # Notes if present
        if data.get('notes'):
            elements.append(Spacer(1, 20))
            elements.append(Paragraph(f"Notes: {data['notes']}", styles['Normal']))
        
        doc.build(elements)


class GolfApp:
    """
    Main Golf App with mobile-style page-based navigation following Apple HIG principles.
    
    REDESIGNED: Uses tab bar navigation instead of popup windows.
    Consolidated pages:
    - Rounds: Log + View Scorecards combined
    - Courses: Manage + Add Course combined
    - Statistics: Now includes Club Distances
    """
    
    # Color palette inspired by iOS
    COLORS = {
        "bg": "#F2F2F7",           # System background
        "card_bg": "#FFFFFF",      # Card background
        "accent": "#007AFF",       # iOS blue
        "accent_green": "#34C759", # iOS green
        "text": "#000000",         # Primary text
        "text_secondary": "#8E8E93", # Secondary text
        "separator": "#C6C6C8",    # Separator lines
        "destructive": "#FF3B30",  # Red for destructive actions
    }
    
    def __init__(self, root):
        self.backend = GolfBackend()
        self.root = root
        root.title("Golf Stats")
        root.geometry("420x720")  # Mobile-like aspect ratio
        root.minsize(380, 600)
        
        # Configure root background
        root.configure(bg=self.COLORS["bg"])
        
        # yardbook initialization
        self.yardbook = yardbookIntegration(self.backend, COURSES_FILE)
        
        # Configure styles for Apple HIG look
        self._configure_styles()
        
        # Track current page
        self.current_page = None
        
        # Main container
        self.main_container = ttk.Frame(root, style="App.TFrame")
        self.main_container.pack(fill='both', expand=True)
        
        # Content area (will swap pages here)
        self.content_frame = ttk.Frame(self.main_container, style="App.TFrame")
        self.content_frame.pack(fill='both', expand=True)
        
        # Tab bar at bottom
        self._create_tab_bar()
        
        # Show home page by default
        self.show_page("home")
    
    def _configure_styles(self):
        """Configure ttk styles to match Apple HIG."""
        style = ttk.Style()
        
        # Use appropriate theme - avoid 'clam' on macOS as it causes highlighting issues
        import sys
        if sys.platform == 'darwin':
            try:
                style.theme_use('aqua')
            except:
                pass  # Fall back to default
        else:
            try:
                style.theme_use('clam')
            except:
                pass
        
        # Frame styles
        style.configure("App.TFrame", background=self.COLORS["bg"])
        style.configure("Card.TFrame", background=self.COLORS["card_bg"])
        
        # Label styles - don't set background on macOS aqua theme
        style.configure("Title.TLabel", 
                       font=("Helvetica", 24, "bold"),
                       foreground=self.COLORS["text"])
        style.configure("Header.TLabel",
                       font=("Helvetica", 18, "bold"),
                       foreground=self.COLORS["text"])
        style.configure("Subheader.TLabel",
                       font=("Helvetica", 14, "bold"),
                       foreground=self.COLORS["text"])
        style.configure("Body.TLabel",
                       font=("Helvetica", 13),
                       foreground=self.COLORS["text"])
        style.configure("Caption.TLabel",
                       font=("Helvetica", 11),
                       foreground=self.COLORS["text_secondary"])
        style.configure("Stat.TLabel",
                       font=("Helvetica", 28, "bold"),
                       foreground=self.COLORS["accent"])
        style.configure("CardTitle.TLabel",
                       font=("Helvetica", 12),
                       foreground=self.COLORS["text_secondary"])
        
        # Button styles
        style.configure("Primary.TButton",
                       font=("Helvetica", 14, "bold"),
                       padding=(16, 10))
        
        # List row style  
        style.configure("ListRow.TFrame", background=self.COLORS["card_bg"])
    
    def _create_tab_bar(self):
        """Create iOS-style tab bar at bottom."""
        self.tab_bar = ttk.Frame(self.main_container, style="Card.TFrame")
        self.tab_bar.pack(fill='x', side='bottom')
        
        # Separator line
        sep = ttk.Frame(self.tab_bar, height=1)
        sep.pack(fill='x')
        sep.configure(style="App.TFrame")
        
        # Tab buttons container
        tabs_inner = ttk.Frame(self.tab_bar, style="Card.TFrame")
        tabs_inner.pack(fill='x', pady=(8, 12))
        
        # Configure equal column weights - 3 tabs
        for i in range(3):
            tabs_inner.columnconfigure(i, weight=1)
        
        # Only Home, Rounds, Courses in tab bar
        # Stats accessible from Home page
        tabs = [
            ("🏌️", "Rounds", "rounds"),
            ("🏠", "Home", "home"),
            ("⛳", "Courses", "courses"),
        ]
        
        self.tab_buttons = {}
        for i, (icon, label, page) in enumerate(tabs):
            btn_frame = ttk.Frame(tabs_inner, style="Card.TFrame")
            btn_frame.grid(row=0, column=i, sticky='nsew')
            
            # Make entire frame clickable
            btn_frame.bind("<Button-1>", lambda e, p=page: self.show_page(p))
            
            icon_lbl = ttk.Label(btn_frame, text=icon, font=("Helvetica", 20), cursor="hand2")
            icon_lbl.pack()
            icon_lbl.bind("<Button-1>", lambda e, p=page: self.show_page(p))
            
            text_lbl = ttk.Label(btn_frame, text=label, font=("Helvetica", 10),
                                foreground=self.COLORS["text_secondary"], cursor="hand2")
            text_lbl.pack()
            text_lbl.bind("<Button-1>", lambda e, p=page: self.show_page(p))
            
            self.tab_buttons[page] = (icon_lbl, text_lbl)
    
    def _update_tab_bar(self, active_page):
        """Update tab bar to show active state."""
        for page, (icon_lbl, text_lbl) in self.tab_buttons.items():
            if page == active_page:
                text_lbl.configure(foreground=self.COLORS["accent"])
            else:
                text_lbl.configure(foreground=self.COLORS["text_secondary"])
    
    def show_page(self, page_name):
        """Switch to a different page."""
        # Clear current content
        for widget in self.content_frame.winfo_children():
            widget.destroy()
        
        self.current_page = page_name
        self._update_tab_bar(page_name)
        
        # Show appropriate page
        if page_name == "home":
            self._show_home_page()
        elif page_name == "rounds":
            self._show_rounds_page()
        elif page_name == "scorecard_detail":
            self._show_scorecard_detail_page()
        elif page_name == "log_round_setup":
            self._show_log_round_setup_page()
        elif page_name == "log_round_entry":
            self._show_log_round_entry_page()
        elif page_name == "log_round_notes":
            self._show_log_round_notes_page()
        elif page_name == "courses":
            self._show_courses_page()
        elif page_name == "course_editor":
            self._show_course_editor_page()
        elif page_name == "yardbook":
            self._show_yardbook_page()
        elif page_name == "statistics":
            self._show_statistics_page()
        elif page_name == "rulebook":
            self._show_rulebook_page()
    
    def _create_page_header(self, title, show_back=False, back_action=None):
        """Create a standard page header."""
        header = ttk.Frame(self.content_frame, style="App.TFrame")
        header.pack(fill='x', padx=16, pady=(16, 8))
        
        if show_back and back_action:
            back_btn = ttk.Button(header, text="← Back", command=back_action)
            back_btn.pack(side='left')
        
        ttk.Label(header, text=title, style="Title.TLabel").pack(side='left')
        
        return header
    
    def _create_card(self, parent, padding=16):
        """Create a rounded card container."""
        card = ttk.Frame(parent, style="Card.TFrame", padding=padding)
        return card
    
    # ==================== HOME PAGE ====================
    
    def _show_home_page(self):
        """Display the home page with summary stats."""
        self._create_page_header("Golf Stats")
        
        # Scrollable content
        canvas = tk.Canvas(self.content_frame, bg=self.COLORS["bg"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.content_frame, orient="vertical", command=canvas.yview)
        scroll_frame = ttk.Frame(canvas, style="App.TFrame")
        
        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw", width=388)
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True, padx=16)
        
        # Get stats
        stats = self.backend.get_statistics()
        idx = self.backend.calculate_handicap_index()
        
        # Handicap Card
        card1 = self._create_card(scroll_frame)
        card1.pack(fill='x', pady=8)
        
        ttk.Label(card1, text="HANDICAP INDEX", style="CardTitle.TLabel").pack(anchor='w')
        
        if idx is not None:
            ttk.Label(card1, text=f"{idx:.1f}", style="Stat.TLabel").pack(anchor='w')
        else:
            ttk.Label(card1, text="--", style="Stat.TLabel").pack(anchor='w')
            total_holes = stats.get('total_holes_played', 0)
            remaining = max(0, 54 - total_holes)
            if remaining > 0:
                ttk.Label(card1, text=f"Play {remaining} more holes to establish",
                         style="Caption.TLabel").pack(anchor='w')
        
        # Quick Stats Cards Row
        stats_row = ttk.Frame(scroll_frame, style="App.TFrame")
        stats_row.pack(fill='x', pady=8)
        stats_row.columnconfigure(0, weight=1)
        stats_row.columnconfigure(1, weight=1)
        
        # Rounds card
        card2 = self._create_card(stats_row, padding=12)
        card2.grid(row=0, column=0, sticky='nsew', padx=(0, 4))
        ttk.Label(card2, text="ROUNDS", style="CardTitle.TLabel").pack(anchor='w')
        ttk.Label(card2, text=str(stats['total_rounds']), 
                 font=("Helvetica", 24, "bold"),
                 background=self.COLORS["card_bg"]).pack(anchor='w')
        
        # Best Round card
        card3 = self._create_card(stats_row, padding=12)
        card3.grid(row=0, column=1, sticky='nsew', padx=(4, 0))
        ttk.Label(card3, text="BEST ROUND", style="CardTitle.TLabel").pack(anchor='w')
        
        best = self.backend.get_best_round()
        if best:
            diff = best['total_score'] - best.get('par', 72)
            diff_str = f"+{diff}" if diff > 0 else str(diff)
            ttk.Label(card3, text=f"{best['total_score']} ({diff_str})",
                     font=("Helvetica", 24, "bold"),
                     background=self.COLORS["card_bg"]).pack(anchor='w')
        else:
            ttk.Label(card3, text="--",
                     font=("Helvetica", 24, "bold"),
                     background=self.COLORS["card_bg"]).pack(anchor='w')
        
        # Quick Actions Card
        card4 = self._create_card(scroll_frame)
        card4.pack(fill='x', pady=8)
        
        ttk.Label(card4, text="QUICK ACTIONS", style="CardTitle.TLabel").pack(anchor='w', pady=(0, 12))
        
        actions = [
            ("🏌️ Log New Round", lambda: self._go_to_log_round()),
            ("📊 Statistics", lambda: self.show_page("statistics")),
            ("📖 Rules of Golf", self.open_rulebook),
        ]
        
        for text, cmd in actions:
            btn = ttk.Button(card4, text=text, command=cmd, style="Primary.TButton")
            btn.pack(fill='x', pady=4)
    
    # ==================== ROUNDS PAGE ====================
    
    def _show_rounds_page(self):
        """Display Rounds page (scorecards only - log round is from Home)."""
        self._create_page_header("My Rounds")
        
        # Filter options
        filter_card = self._create_card(self.content_frame, padding=10)
        filter_card.pack(fill='x', padx=16, pady=(0, 8))
        
        ttk.Label(filter_card, text="Filter:", style="Body.TLabel").pack(side='left')
        
        self.filter_type_var = tk.StringVar(value="all")
        for text, val in [("All", "all"), ("Solo", "solo"), ("Scramble", "scramble")]:
            ttk.Radiobutton(filter_card, text=text, variable=self.filter_type_var, 
                           value=val, command=self._populate_scorecards_list).pack(side='left', padx=5)
        
        # Hint
        ttk.Label(self.content_frame, text="Tap a round to view details",
                 foreground=self.COLORS["text_secondary"],
                 font=("Helvetica", 11)).pack(padx=16, anchor='w')
        
        # Scorecards list
        list_frame = ttk.Frame(self.content_frame, style="App.TFrame")
        list_frame.pack(fill='both', expand=True, padx=16, pady=(4, 8))
        
        cols = ("Date", "Course", "Score", "+/-", "Holes")
        self.score_tree = ttk.Treeview(list_frame, columns=cols, show="headings", height=14)
        
        widths = [80, 140, 50, 45, 45]
        for col, w in zip(cols, widths):
            self.score_tree.heading(col, text=col)
            self.score_tree.column(col, width=w, anchor='center')
        
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.score_tree.yview)
        self.score_tree.configure(yscrollcommand=scrollbar.set)
        
        self.score_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # Single click to view scorecard
        self.score_tree.bind("<ButtonRelease-1>", self._on_scorecard_click)
        
        self._populate_scorecards_list()
    
    def _on_scorecard_click(self, event):
        """Handle single click on scorecard row."""
        # Small delay to allow selection to complete
        sel = self.score_tree.focus()
        if sel:
            self.viewing_round = self.backend.get_rounds()[int(sel)]
            self.show_page("scorecard_detail")
    
    def _populate_scorecards_list(self):
        """Populate the scorecards treeview."""
        for row in self.score_tree.get_children():
            self.score_tree.delete(row)
        
        for idx, rd in self.backend.get_filtered_rounds(
            round_type=self.filter_type_var.get(), sort_by="recent"):
            diff = rd["total_score"] - rd.get("par", 72)
            diff_str = f"+{diff}" if diff > 0 else str(diff)
            holes_choice = rd.get("holes_choice", "full_18")
            holes_str = "F9" if holes_choice == "front_9" else (
                "B9" if holes_choice == "back_9" else str(rd.get("holes_played", 18)))
            
            vals = (rd.get("date", "N/A")[:10], rd["course_name"][:18], 
                   rd["total_score"], diff_str, holes_str)
            self.score_tree.insert("", "end", iid=str(idx), values=vals)
    
    def _view_scorecard_inline(self, event=None):
        """View selected scorecard as inline page."""
        sel = self.score_tree.focus()
        if not sel:
            messagebox.showinfo("Info", "Select a round first")
            return
        
        self.viewing_round = self.backend.get_rounds()[int(sel)]
        self.show_page("scorecard_detail")
    
    # ==================== SCORECARD DETAIL PAGE ====================
    
    def _show_scorecard_detail_page(self):
        """Display scorecard details as inline page."""
        rd = getattr(self, 'viewing_round', None)
        if not rd:
            self.show_page("rounds")
            return
        
        self._create_page_header("Scorecard", show_back=True, 
                                back_action=lambda: self.show_page("rounds"))
        
        # Scrollable content
        canvas = tk.Canvas(self.content_frame, bg=self.COLORS["bg"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.content_frame, orient="vertical", command=canvas.yview)
        scroll_frame = ttk.Frame(canvas, style="App.TFrame")
        
        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side='left', fill='both', expand=True, padx=16)
        scrollbar.pack(side='right', fill='y')
        
        # Course info card
        info_card = self._create_card(scroll_frame)
        info_card.pack(fill='x', pady=8)
        
        ttk.Label(info_card, text=rd["course_name"], style="Header.TLabel").pack(anchor='w')
        
        diff = rd['total_score'] - rd.get('par', 72)
        diff_str = f"+{diff}" if diff > 0 else str(diff)
        
        # Get course for yardage
        course = self.backend.get_course_by_name(rd["course_name"])
        tee_color = rd.get('tee_color', '')
        
        info_parts = [rd.get('date', 'N/A')[:10]]
        if tee_color:
            info_parts.append(f"{tee_color} Tees")
        
        if course:
            yardages = course.get("yardages", {}).get(tee_color, [])
            if yardages:
                total_yardage = sum(y for y in yardages if y)
                info_parts.append(f"{total_yardage} yards")
        
        ttk.Label(info_card, text=" • ".join(info_parts), style="Caption.TLabel").pack(anchor='w', pady=(4, 8))
        
        # Score summary
        score_frame = ttk.Frame(info_card)
        score_frame.pack(fill='x', pady=8)
        
        ttk.Label(score_frame, text="Score:", font=("Helvetica", 14)).pack(side='left')
        ttk.Label(score_frame, text=f"{rd['total_score']} ({diff_str})",
                 font=("Helvetica", 22, "bold"), foreground=self.COLORS["accent"]).pack(side='left', padx=10)
        
        if rd.get("target_score"):
            target_diff = rd['total_score'] - rd['target_score']
            target_str = f"+{target_diff}" if target_diff > 0 else str(target_diff)
            ttk.Label(score_frame, text=f"vs Target: {target_str}",
                     font=("Helvetica", 12), foreground=self.COLORS["text_secondary"]).pack(side='left', padx=10)
        
        # Hole-by-hole scores card
        scores_card = self._create_card(scroll_frame)
        scores_card.pack(fill='x', pady=8)
        
        ttk.Label(scores_card, text="Hole by Hole", style="Subheader.TLabel").pack(anchor='w', pady=(0, 8))
        
        pars = course["pars"] if course else [4] * len(rd.get("scores", []))
        scores = rd.get("scores", [])
        yardages = course.get("yardages", {}).get(tee_color, []) if course else []
        
        # Create table
        table_frame = ttk.Frame(scores_card)
        table_frame.pack(fill='x')
        
        # Headers
        headers = ["Hole", "Yards", "Par", "Score", "+/-"]
        for i, h in enumerate(headers):
            ttk.Label(table_frame, text=h, font=("Helvetica", 11, "bold")).grid(
                row=0, column=i, padx=6, pady=4, sticky='w')
        
        ttk.Separator(table_frame, orient='horizontal').grid(row=1, column=0, columnspan=5, sticky='ew', pady=4)
        
        row_num = 2
        for i, (par, score) in enumerate(zip(pars, scores)):
            if score is not None:
                hole_diff = score - par
                diff_str = f"+{hole_diff}" if hole_diff > 0 else str(hole_diff)
                yard = yardages[i] if i < len(yardages) and yardages[i] else "-"
                
                # Color code the score
                fg = "#FF3B30" if hole_diff > 0 else ("#34C759" if hole_diff < 0 else self.COLORS["text"])
                
                ttk.Label(table_frame, text=str(i + 1)).grid(row=row_num, column=0, padx=6, pady=2)
                ttk.Label(table_frame, text=str(yard)).grid(row=row_num, column=1, padx=6, pady=2)
                ttk.Label(table_frame, text=str(par)).grid(row=row_num, column=2, padx=6, pady=2)
                ttk.Label(table_frame, text=str(score), foreground=fg, 
                         font=("Helvetica", 11, "bold")).grid(row=row_num, column=3, padx=6, pady=2)
                ttk.Label(table_frame, text=diff_str, foreground=fg).grid(row=row_num, column=4, padx=6, pady=2)
                row_num += 1
        
        # Totals row
        ttk.Separator(table_frame, orient='horizontal').grid(row=row_num, column=0, columnspan=5, sticky='ew', pady=4)
        row_num += 1
        
        total_yards = sum(y for y in yardages if y) if yardages else "-"
        total_par = sum(pars)
        ttk.Label(table_frame, text="Total", font=("Helvetica", 11, "bold")).grid(row=row_num, column=0, padx=6, pady=2)
        ttk.Label(table_frame, text=str(total_yards)).grid(row=row_num, column=1, padx=6, pady=2)
        ttk.Label(table_frame, text=str(total_par)).grid(row=row_num, column=2, padx=6, pady=2)
        ttk.Label(table_frame, text=str(rd['total_score']), font=("Helvetica", 11, "bold")).grid(row=row_num, column=3, padx=6, pady=2)
        final_diff = rd['total_score'] - total_par
        final_str = f"+{final_diff}" if final_diff > 0 else str(final_diff)
        ttk.Label(table_frame, text=final_str, font=("Helvetica", 11, "bold")).grid(row=row_num, column=4, padx=6, pady=2)
        
        # Notes
        if rd.get("notes"):
            notes_card = self._create_card(scroll_frame)
            notes_card.pack(fill='x', pady=8)
            ttk.Label(notes_card, text="Notes", style="Subheader.TLabel").pack(anchor='w')
            ttk.Label(notes_card, text=rd["notes"], wraplength=350).pack(anchor='w', pady=8)
        
        # Action buttons
        btn_card = self._create_card(scroll_frame)
        btn_card.pack(fill='x', pady=8)
        
        btn_row = ttk.Frame(btn_card)
        btn_row.pack(fill='x')
        
        ttk.Button(btn_row, text="📤 Export", 
                  command=lambda: self._show_export_dialog(rd)).pack(side='left', padx=4)
        
        # Delete button (with confirmation)
        def delete_this_round():
            if messagebox.askyesno("Delete Round", 
                "Are you sure you want to delete this round?\nThis cannot be undone."):
                # Find and delete the round
                rounds = self.backend.get_rounds()
                for i, r in enumerate(rounds):
                    if r.get("date") == rd.get("date") and r.get("course_name") == rd.get("course_name"):
                        self.backend.delete_round(i)
                        break
                self.show_page("rounds")
        
        ttk.Button(btn_row, text="🗑 Delete",
                  command=delete_this_round).pack(side='left', padx=4)
        
        ttk.Button(btn_row, text="← Back",
                  command=lambda: self.show_page("rounds")).pack(side='right', padx=4)
    
    # ==================== LOG ROUND SETUP PAGE ====================
    
    def _show_log_round_setup_page(self):
        """Display log round setup page with user preferences."""
        self._create_page_header("Log Round", show_back=True, 
                                back_action=lambda: self.show_page("home"))
        
        # Scrollable content
        canvas = tk.Canvas(self.content_frame, bg=self.COLORS["bg"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.content_frame, orient="vertical", command=canvas.yview)
        scroll_frame = ttk.Frame(canvas, style="App.TFrame")
        
        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side='left', fill='both', expand=True, padx=16)
        scrollbar.pack(side='right', fill='y')
        
        courses = self.backend.get_courses()
        if not courses:
            card = self._create_card(scroll_frame)
            card.pack(fill='x', pady=8)
            ttk.Label(card, text="No courses added yet", style="Subheader.TLabel").pack(anchor='w')
            ttk.Label(card, text="Add a course before logging a round.",
                     style="Caption.TLabel").pack(pady=12)
            ttk.Button(card, text="➕ Add Course", 
                      command=lambda: self.show_page("courses")).pack()
            return
        
        # Get user preferences
        pref_tee = self.backend.get_preferred_tee_color()
        pref_entry_mode = self.backend.get_entry_mode()
        favorite_courses = self.backend.get_favorite_courses()
        
        # Course selection card
        course_card = self._create_card(scroll_frame)
        course_card.pack(fill='x', pady=8)
        
        ttk.Label(course_card, text="Select Course", style="Subheader.TLabel").pack(anchor='w', pady=(0, 8))
        
        course_names = sorted([c["name"] for c in courses])
        # Put favorites first
        if favorite_courses:
            fav_set = set(favorite_courses)
            course_names = [c for c in course_names if c in fav_set] + [c for c in course_names if c not in fav_set]
        
        self.log_course_var = tk.StringVar()
        course_combo = ttk.Combobox(course_card, textvariable=self.log_course_var,
                                    values=course_names, state='readonly', width=35)
        course_combo.pack(anchor='w')
        if course_names:
            # Default to first favorite or first course
            default_course = favorite_courses[0] if favorite_courses and favorite_courses[0] in course_names else course_names[0]
            course_combo.set(default_course)
        
        # Tee selection
        ttk.Label(course_card, text="Tee Box:", style="Body.TLabel").pack(anchor='w', pady=(12, 4))
        self.log_tee_var = tk.StringVar()
        self.tee_combo = ttk.Combobox(course_card, textvariable=self.log_tee_var, state='readonly', width=20)
        self.tee_combo.pack(anchor='w')
        
        course_combo.bind('<<ComboboxSelected>>', self._update_log_tee_options)
        self._update_log_tee_options(preferred_tee=pref_tee)
        
        # Holes selection
        ttk.Label(course_card, text="Holes:", style="Body.TLabel").pack(anchor='w', pady=(12, 4))
        self.log_holes_var = tk.StringVar(value="full_18")
        holes_frame = ttk.Frame(course_card)
        holes_frame.pack(anchor='w')
        for text, val in [("18 Holes", "full_18"), ("Front 9", "front_9"), ("Back 9", "back_9")]:
            ttk.Radiobutton(holes_frame, text=text, variable=self.log_holes_var, 
                           value=val).pack(side='left', padx=5)
        
        # Date
        ttk.Label(course_card, text="Date:", style="Body.TLabel").pack(anchor='w', pady=(12, 4))
        self.log_date = DateEntry(course_card, width=15, date_pattern='yyyy-mm-dd')
        self.log_date.pack(anchor='w')
        
        # Round type card
        options_card = self._create_card(scroll_frame)
        options_card.pack(fill='x', pady=8)
        
        ttk.Label(options_card, text="Round Type", style="Subheader.TLabel").pack(anchor='w', pady=(0, 8))
        
        self.log_round_type_var = tk.StringVar(value="solo")
        type_frame = ttk.Frame(options_card)
        type_frame.pack(anchor='w')
        ttk.Radiobutton(type_frame, text="Solo", variable=self.log_round_type_var,
                       value="solo").pack(side='left', padx=5)
        ttk.Radiobutton(type_frame, text="Scramble", variable=self.log_round_type_var,
                       value="scramble").pack(side='left', padx=5)
        
        self.log_serious_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_card, text="Serious round (counts toward handicap)",
                       variable=self.log_serious_var).pack(anchor='w', pady=(8, 0))
        
        # Entry mode card
        entry_card = self._create_card(scroll_frame)
        entry_card.pack(fill='x', pady=8)
        
        ttk.Label(entry_card, text="Entry Mode", style="Subheader.TLabel").pack(anchor='w', pady=(0, 8))
        
        self.log_entry_mode_var = tk.StringVar(value=pref_entry_mode)
        ttk.Radiobutton(entry_card, text="Quick (scores only)", 
                       variable=self.log_entry_mode_var, value="quick").pack(anchor='w')
        ttk.Radiobutton(entry_card, text="Detailed (scores + clubs + stats)", 
                       variable=self.log_entry_mode_var, value="detailed").pack(anchor='w')
        
        # Start button
        btn_card = self._create_card(scroll_frame)
        btn_card.pack(fill='x', pady=8)
        
        ttk.Button(btn_card, text="▶ Start Entering Scores",
                  command=self._proceed_to_score_entry, style="Primary.TButton").pack(fill='x')
    
    def _update_log_tee_options(self, event=None, preferred_tee=None):
        """Update tee box options based on selected course."""
        course_name = self.log_course_var.get()
        course = self.backend.get_course_by_name(course_name)
        
        if course:
            tees = [tb.get("color", "") for tb in course.get("tee_boxes", [])]
            self.tee_combo['values'] = tees
            if tees:
                # Use preferred tee if available
                if preferred_tee and preferred_tee in tees:
                    self.tee_combo.set(preferred_tee)
                else:
                    self.tee_combo.set(tees[0])
    
    def _proceed_to_score_entry(self):
        """Validate setup and proceed to score entry page."""
        course_name = self.log_course_var.get()
        if not course_name:
            messagebox.showerror("Error", "Please select a course")
            return
        
        course = self.backend.get_course_by_name(course_name)
        if not course:
            messagebox.showerror("Error", "Course not found")
            return
        
        tee = self.log_tee_var.get()
        if not tee:
            tees = [tb.get("color", "") for tb in course.get("tee_boxes", [])]
            tee = tees[0] if tees else "White"
        
        # Store round setup data
        self.pending_round = {
            "course": course,
            "tee": tee,
            "holes_choice": self.log_holes_var.get(),
            "round_type": self.log_round_type_var.get(),
            "is_serious": self.log_serious_var.get(),
            "selected_date": self.log_date.get_date(),
            "entry_mode": self.log_entry_mode_var.get()
        }
        
        # Save entry mode preference
        self.backend.set_entry_mode(self.log_entry_mode_var.get())
        
        # Proceed to score entry
        self.show_page("log_round_entry")
    
    # ==================== LOG ROUND ENTRY PAGE ====================
    
    def _show_log_round_entry_page(self):
        """Display Nokia-style score entry page."""
        if not hasattr(self, 'pending_round') or not self.pending_round:
            self.show_page("home")
            return
        
        pr = self.pending_round
        course = pr["course"]
        
        # Determine which holes to score
        all_pars = course["pars"]
        if pr["holes_choice"] == "front_9":
            self.holes_to_score = list(range(9))
        elif pr["holes_choice"] == "back_9":
            self.holes_to_score = list(range(9, min(18, len(all_pars))))
        else:
            self.holes_to_score = list(range(len(all_pars)))
        
        yardages = course.get("yardages", {}).get(pr["tee"], [])
        is_detailed = pr["entry_mode"] == "detailed"
        
        # Initialize score tracking
        self.current_hole_idx = 0
        self.hole_scores = [None] * len(self.holes_to_score)  # Quick mode scores
        self.hole_clubs = [[] for _ in self.holes_to_score]   # Detailed mode clubs
        
        # Club options for detailed mode - load from user's bag (clubs.json)
        user_clubs = self.backend.get_clubs()
        if user_clubs:
            # Sort clubs by distance (longest first) and create abbreviations
            sorted_clubs = sorted(user_clubs, key=lambda c: c.get("distance", 0), reverse=True)
            self.club_options = []
            self.club_full_names = {}
            
            for club in sorted_clubs:
                name = club.get("name", "")
                # Create abbreviation
                abbrev = self._abbreviate_club_name(name)
                self.club_options.append(abbrev)
                self.club_full_names[abbrev] = name
            
            # Always include Putter at the end if not already present
            if "P" not in self.club_options and "Putter" not in [c.get("name") for c in sorted_clubs]:
                self.club_options.append("P")
                self.club_full_names["P"] = "Putter"
        else:
            # Default clubs if none defined
            self.club_options = ["D", "3W", "5W", "H", "3i", "4i", "5i", "6i", 
                                "7i", "8i", "9i", "PW", "GW", "SW", "LW", "P"]
            self.club_full_names = {
                "D": "Driver", "3W": "3 Wood", "5W": "5 Wood", "H": "Hybrid",
                "3i": "3 Iron", "4i": "4 Iron", "5i": "5 Iron", "6i": "6 Iron",
                "7i": "7 Iron", "8i": "8 Iron", "9i": "9 Iron", 
                "PW": "Pitching Wedge", "GW": "Gap Wedge", "SW": "Sand Wedge", 
                "LW": "Lob Wedge", "P": "Putter"
            }
        
        # Main container - no header, custom layout
        main = ttk.Frame(self.content_frame, style="App.TFrame")
        main.pack(fill='both', expand=True)
        
        # === TOP BAR: Hole number left, Course/Club info right ===
        top_bar = ttk.Frame(main, style="Card.TFrame", padding=12)
        top_bar.pack(fill='x')
        
        # Hole number (large, left side)
        self.hole_num_label = ttk.Label(top_bar, text="1", 
                                        font=("Helvetica", 36, "bold"),
                                        foreground=self.COLORS["accent"])
        self.hole_num_label.pack(side='left')
        
        # Course and hole info (right side)
        info_frame = ttk.Frame(top_bar)
        info_frame.pack(side='right', anchor='e')
        
        ttk.Label(info_frame, text=course['name'][:20], 
                 font=("Helvetica", 14, "bold")).pack(anchor='e')
        
        self.hole_info_label = ttk.Label(info_frame, text="Par 4 • 380 yds",
                                         foreground=self.COLORS["text_secondary"])
        self.hole_info_label.pack(anchor='e')
        
        ttk.Label(info_frame, text=f"{pr['tee']} Tees",
                 foreground=self.COLORS["text_secondary"],
                 font=("Helvetica", 10)).pack(anchor='e')
        
        # === MIDDLE: Navigation + Stroke Display ===
        middle_frame = ttk.Frame(main, style="App.TFrame")
        middle_frame.pack(fill='both', expand=True, pady=20)
        
        # Previous hole button (left)
        self.prev_btn = ttk.Button(middle_frame, text="◀", width=4,
                                   command=self._prev_hole)
        self.prev_btn.pack(side='left', padx=20)
        
        # Center area: stroke count + clubs display
        center_frame = ttk.Frame(middle_frame, style="App.TFrame")
        center_frame.pack(side='left', expand=True)
        
        # Stroke count (large number in center)
        self.stroke_var = tk.StringVar(value="0")
        self.stroke_label = ttk.Label(center_frame, textvariable=self.stroke_var,
                                      font=("Helvetica", 72, "bold"),
                                      foreground=self.COLORS["text"])
        self.stroke_label.pack()
        
        # Clubs display (for detailed mode)
        self.clubs_display_var = tk.StringVar(value="")
        self.clubs_display = ttk.Label(center_frame, textvariable=self.clubs_display_var,
                                       font=("Helvetica", 11),
                                       foreground=self.COLORS["text_secondary"],
                                       wraplength=250)
        self.clubs_display.pack(pady=(8, 0))
        
        # Score vs par indicator
        self.score_diff_var = tk.StringVar(value="")
        ttk.Label(center_frame, textvariable=self.score_diff_var,
                 font=("Helvetica", 14), foreground=self.COLORS["accent"]).pack(pady=(4, 0))
        
        # Next hole button (right)
        self.next_btn = ttk.Button(middle_frame, text="▶", width=4,
                                   command=self._next_hole)
        self.next_btn.pack(side='right', padx=20)
        
        # === BOTTOM: Number Pad or Club Grid ===
        pad_frame = ttk.Frame(main, style="Card.TFrame", padding=12)
        pad_frame.pack(fill='x', side='bottom')
        
        if is_detailed:
            # Club grid (4x4)
            self._create_club_grid(pad_frame)
        else:
            # Number pad (0-9 + clear)
            self._create_number_pad(pad_frame)
        
        # Running total at very bottom
        total_frame = ttk.Frame(main, style="App.TFrame")
        total_frame.pack(fill='x', side='bottom', pady=8)
        
        self.running_total_var = tk.StringVar(value="Total: 0 (E)")
        ttk.Label(total_frame, textvariable=self.running_total_var,
                 font=("Helvetica", 14, "bold"),
                 foreground=self.COLORS["accent"]).pack()
        
        # Update display for first hole
        self._update_hole_display()
    
    def _create_number_pad(self, parent):
        """Create Nokia-style number pad for quick mode."""
        # Grid of numbers
        pad = ttk.Frame(parent)
        pad.pack()
        
        # Row 1: 1, 2, 3
        row1 = ttk.Frame(pad)
        row1.pack(pady=4)
        for n in [1, 2, 3]:
            btn = tk.Button(row1, text=str(n), font=("Helvetica", 20, "bold"),
                           width=4, height=2, bg=self.COLORS["card_bg"],
                           command=lambda x=n: self._input_score(x))
            btn.pack(side='left', padx=4)
        
        # Row 2: 4, 5, 6
        row2 = ttk.Frame(pad)
        row2.pack(pady=4)
        for n in [4, 5, 6]:
            btn = tk.Button(row2, text=str(n), font=("Helvetica", 20, "bold"),
                           width=4, height=2, bg=self.COLORS["card_bg"],
                           command=lambda x=n: self._input_score(x))
            btn.pack(side='left', padx=4)
        
        # Row 3: 7, 8, 9
        row3 = ttk.Frame(pad)
        row3.pack(pady=4)
        for n in [7, 8, 9]:
            btn = tk.Button(row3, text=str(n), font=("Helvetica", 20, "bold"),
                           width=4, height=2, bg=self.COLORS["card_bg"],
                           command=lambda x=n: self._input_score(x))
            btn.pack(side='left', padx=4)
        
        # Row 4: Clear, 0, Forfeit (X)
        row4 = ttk.Frame(pad)
        row4.pack(pady=4)
        
        clear_btn = tk.Button(row4, text="C", font=("Helvetica", 20, "bold"),
                             width=4, height=2, bg="#FFCC00",
                             command=self._clear_score)
        clear_btn.pack(side='left', padx=4)
        
        zero_btn = tk.Button(row4, text="0", font=("Helvetica", 20, "bold"),
                            width=4, height=2, bg=self.COLORS["card_bg"],
                            command=lambda: self._input_score(0))
        zero_btn.pack(side='left', padx=4)
        
        forfeit_btn = tk.Button(row4, text="X", font=("Helvetica", 20, "bold"),
                               width=4, height=2, bg=self.COLORS["destructive"], fg="white",
                               command=self._forfeit_hole)
        forfeit_btn.pack(side='left', padx=4)
    
    def _abbreviate_club_name(self, name):
        """Create abbreviation for a club name."""
        name_lower = name.lower()
        
        # Common abbreviations
        if "driver" in name_lower:
            return "D"
        elif "putter" in name_lower:
            return "P"
        elif "hybrid" in name_lower:
            return "H"
        elif "wood" in name_lower:
            # Extract number (e.g., "3 Wood" -> "3W")
            parts = name.split()
            for p in parts:
                if p.isdigit():
                    return f"{p}W"
            return "W"
        elif "iron" in name_lower:
            # Extract number (e.g., "7 Iron" -> "7i")
            parts = name.split()
            for p in parts:
                if p.isdigit():
                    return f"{p}i"
            return "i"
        elif "wedge" in name_lower:
            if "pitch" in name_lower:
                return "PW"
            elif "gap" in name_lower:
                return "GW"
            elif "sand" in name_lower:
                return "SW"
            elif "lob" in name_lower:
                return "LW"
            else:
                # Try to get degree or first letter
                parts = name.split()
                for p in parts:
                    if p.isdigit() or "°" in p:
                        return p.replace("°", "")
                return name[:2].upper()
        else:
            # Default: first 2-3 chars
            return name[:3].upper() if len(name) > 2 else name.upper()
    
    def _create_club_grid(self, parent):
        """Create club selection grid for detailed mode."""
        # Info label
        ttk.Label(parent, text="Tap clubs in order of use:",
                 font=("Helvetica", 11),
                 foreground=self.COLORS["text_secondary"]).pack(pady=(0, 8))
        
        grid = ttk.Frame(parent)
        grid.pack()
        
        # Calculate grid dimensions based on number of clubs
        num_clubs = len(self.club_options)
        cols = 4 if num_clubs <= 16 else 5
        
        # Create grid of clubs
        for i, club in enumerate(self.club_options):
            row = i // cols
            col = i % cols
            
            if not hasattr(self, 'club_grid_frame'):
                self.club_grid_frame = grid
            
            # Color putter differently
            is_putter = club == "P" or "putter" in self.club_full_names.get(club, "").lower()
            bg = "#90EE90" if is_putter else self.COLORS["card_bg"]
            
            btn = tk.Button(grid, text=club, font=("Helvetica", 12, "bold"),
                           width=4, height=2, bg=bg,
                           command=lambda c=club: self._add_club(c))
            btn.grid(row=row, column=col, padx=2, pady=2)
        
        # Undo and Clear buttons
        btn_row = ttk.Frame(parent)
        btn_row.pack(pady=(8, 0))
        
        tk.Button(btn_row, text="↩ Undo", font=("Helvetica", 12),
                 width=8, height=1, bg="#FFCC00",
                 command=self._undo_club).pack(side='left', padx=4)
        
        tk.Button(btn_row, text="Clear All", font=("Helvetica", 12),
                 width=8, height=1, bg=self.COLORS["destructive"], fg="white",
                 command=self._clear_clubs).pack(side='left', padx=4)
    
    def _input_score(self, digit):
        """Input a digit for quick mode score."""
        current = self.hole_scores[self.current_hole_idx]
        if current is None:
            new_score = digit
        else:
            # Append digit (max 2 digits)
            new_score = current * 10 + digit
            if new_score > 20:
                new_score = digit  # Reset if too high
        
        self.hole_scores[self.current_hole_idx] = new_score
        self._update_hole_display()
    
    def _clear_score(self):
        """Clear current hole score."""
        self.hole_scores[self.current_hole_idx] = None
        self._update_hole_display()
    
    def _forfeit_hole(self):
        """Forfeit the current hole (serious round only)."""
        if messagebox.askyesno("Forfeit Hole", 
            "Are you sure you want to forfeit this hole?\n\n"
            "This will record a score of 0 and may affect your handicap."):
            self.hole_scores[self.current_hole_idx] = 0
            self._update_hole_display()
    
    def _add_club(self, club):
        """Add a club to current hole (detailed mode)."""
        self.hole_clubs[self.current_hole_idx].append(club)
        self._update_hole_display()
    
    def _undo_club(self):
        """Remove last club from current hole."""
        if self.hole_clubs[self.current_hole_idx]:
            self.hole_clubs[self.current_hole_idx].pop()
            self._update_hole_display()
    
    def _clear_clubs(self):
        """Clear all clubs from current hole."""
        self.hole_clubs[self.current_hole_idx] = []
        self._update_hole_display()
    
    def _prev_hole(self):
        """Navigate to previous hole."""
        if self.current_hole_idx > 0:
            self.current_hole_idx -= 1
            self._update_hole_display()
    
    def _next_hole(self):
        """Navigate to next hole or finish."""
        if self.current_hole_idx < len(self.holes_to_score) - 1:
            self.current_hole_idx += 1
            self._update_hole_display()
        else:
            # Last hole - check if all filled and go to notes
            self._check_and_finish()
    
    def _check_and_finish(self):
        """Check all holes have data and proceed to notes."""
        pr = self.pending_round
        is_detailed = pr["entry_mode"] == "detailed"
        
        # Check for incomplete holes
        incomplete = []
        for idx, hole_num in enumerate(self.holes_to_score):
            if is_detailed:
                if not self.hole_clubs[idx]:
                    incomplete.append(hole_num + 1)
            else:
                if self.hole_scores[idx] is None:
                    incomplete.append(hole_num + 1)
        
        if incomplete:
            holes_str = ", ".join(map(str, incomplete[:5]))
            if len(incomplete) > 5:
                holes_str += f" (+{len(incomplete) - 5} more)"
            messagebox.showwarning("Incomplete", 
                f"Please enter scores for holes: {holes_str}")
            return
        
        # All complete - show notes page
        self.show_page("log_round_notes")
    
    def _update_hole_display(self):
        """Update all displays for current hole."""
        pr = self.pending_round
        course = pr["course"]
        is_detailed = pr["entry_mode"] == "detailed"
        
        hole_num = self.holes_to_score[self.current_hole_idx]
        par = course["pars"][hole_num]
        yardages = course.get("yardages", {}).get(pr["tee"], [])
        yard = yardages[hole_num] if hole_num < len(yardages) and yardages[hole_num] else "-"
        
        # Update hole number
        self.hole_num_label.configure(text=str(hole_num + 1))
        
        # Update hole info
        self.hole_info_label.configure(text=f"Par {par} • {yard} yds")
        
        # Update stroke count and clubs display
        if is_detailed:
            clubs = self.hole_clubs[self.current_hole_idx]
            score = len(clubs)
            self.stroke_var.set(str(score))
            
            if clubs:
                self.clubs_display_var.set(" → ".join(clubs))
            else:
                self.clubs_display_var.set("Tap clubs below")
        else:
            score = self.hole_scores[self.current_hole_idx]
            if score is not None:
                self.stroke_var.set(str(score))
            else:
                self.stroke_var.set("-")
            self.clubs_display_var.set("")
        
        # Update score diff
        if score is not None and score > 0:
            diff = score - par
            if diff > 0:
                self.score_diff_var.set(f"+{diff}")
            elif diff < 0:
                self.score_diff_var.set(str(diff))
            else:
                self.score_diff_var.set("E")
        else:
            self.score_diff_var.set("")
        
        # Update navigation buttons
        self.prev_btn.configure(state='normal' if self.current_hole_idx > 0 else 'disabled')
        
        # Change next button to "Done" on last hole
        if self.current_hole_idx == len(self.holes_to_score) - 1:
            self.next_btn.configure(text="✓")
        else:
            self.next_btn.configure(text="▶")
        
        # Update running total
        self._update_running_total()
    
    def _update_running_total(self):
        """Update running total display."""
        if not hasattr(self, 'pending_round'):
            return
        
        pr = self.pending_round
        is_detailed = pr["entry_mode"] == "detailed"
        
        total = 0
        holes_done = 0
        
        for idx in range(len(self.holes_to_score)):
            if is_detailed:
                if self.hole_clubs[idx]:
                    total += len(self.hole_clubs[idx])
                    holes_done += 1
            else:
                if self.hole_scores[idx] is not None:
                    total += self.hole_scores[idx]
                    holes_done += 1
        
        par_total = sum(pr["course"]["pars"][i] for i in self.holes_to_score[:holes_done]) if holes_done > 0 else 0
        
        if holes_done > 0:
            diff = total - par_total
            if diff > 0:
                diff_str = f"+{diff}"
            elif diff < 0:
                diff_str = str(diff)
            else:
                diff_str = "E"
            self.running_total_var.set(f"Total: {total} ({diff_str}) • {holes_done}/{len(self.holes_to_score)} holes")
        else:
            self.running_total_var.set(f"0/{len(self.holes_to_score)} holes")
    
    # ==================== LOG ROUND NOTES PAGE ====================
    
    def _show_log_round_notes_page(self):
        """Display notes entry page after scoring."""
        if not hasattr(self, 'pending_round') or not self.pending_round:
            self.show_page("home")
            return
        
        pr = self.pending_round
        course = pr["course"]
        is_detailed = pr["entry_mode"] == "detailed"
        
        self._create_page_header("Round Notes", show_back=True, 
                                back_action=lambda: self.show_page("log_round_entry"))
        
        # Summary card
        summary_card = self._create_card(self.content_frame, padding=16)
        summary_card.pack(fill='x', padx=16, pady=8)
        
        ttk.Label(summary_card, text="Round Summary", style="Subheader.TLabel").pack(anchor='w')
        
        # Calculate total
        if is_detailed:
            total = sum(len(clubs) for clubs in self.hole_clubs)
        else:
            total = sum(s for s in self.hole_scores if s is not None)
        
        par_total = sum(course["pars"][i] for i in self.holes_to_score)
        diff = total - par_total
        diff_str = f"+{diff}" if diff > 0 else str(diff)
        
        ttk.Label(summary_card, text=f"{course['name']}", 
                 font=("Helvetica", 14)).pack(anchor='w', pady=(8, 0))
        ttk.Label(summary_card, text=f"Score: {total} ({diff_str}) • Par {par_total}",
                 font=("Helvetica", 18, "bold"),
                 foreground=self.COLORS["accent"]).pack(anchor='w', pady=4)
        ttk.Label(summary_card, text=f"{len(self.holes_to_score)} holes • {pr['tee']} Tees",
                 foreground=self.COLORS["text_secondary"]).pack(anchor='w')
        
        # Notes entry
        notes_card = self._create_card(self.content_frame, padding=16)
        notes_card.pack(fill='both', expand=True, padx=16, pady=8)
        
        ttk.Label(notes_card, text="Notes (optional)", style="Subheader.TLabel").pack(anchor='w')
        ttk.Label(notes_card, text="Add any notes about this round:",
                 foreground=self.COLORS["text_secondary"]).pack(anchor='w', pady=(4, 8))
        
        self.notes_text = tk.Text(notes_card, height=6, font=("Helvetica", 12),
                                  wrap='word')
        self.notes_text.pack(fill='both', expand=True)
        
        # Save button
        btn_frame = ttk.Frame(self.content_frame, style="App.TFrame")
        btn_frame.pack(fill='x', padx=16, pady=12)
        
        ttk.Button(btn_frame, text="💾 Save Round",
                  command=self._submit_round_from_page, style="Primary.TButton").pack(fill='x')
    
    def _submit_round_from_page(self):
        """Submit the round from notes page."""
        if not hasattr(self, 'pending_round'):
            return
        
        pr = self.pending_round
        course = pr["course"]
        is_detailed = pr["entry_mode"] == "detailed"
        
        # Collect scores
        scores = []
        detailed_stats = []
        
        for idx, hole_num in enumerate(self.holes_to_score):
            par = course["pars"][hole_num]
            
            if is_detailed:
                clubs = self.hole_clubs[idx]
                score = len(clubs)
                scores.append(score)
                
                # Derive stats
                putts = sum(1 for c in clubs if c == "P")
                strokes_to_green = score - putts
                gir = strokes_to_green <= (par - 2)
                fir = None
                if par >= 4 and clubs:
                    fir = clubs[0] in ["D", "3W", "5W", "H"]
                
                detailed_stats.append({
                    "hole": hole_num + 1,
                    "clubs": clubs.copy(),
                    "putts": putts,
                    "strokes_to_green": strokes_to_green,
                    "fir": fir,
                    "gir": gir
                })
            else:
                scores.append(self.hole_scores[idx])
        
        total = sum(scores)
        par = sum(course["pars"][i] for i in self.holes_to_score)
        holes_played = len(self.holes_to_score)
        
        # Get tee box info
        box = next((b for b in course.get("tee_boxes", []) 
                   if b["color"] == pr["tee"]), None)
        tee_rating = box["rating"] if box else 72
        tee_slope = box["slope"] if box else 113
        
        if holes_played == 9:
            tee_rating = tee_rating / 2
        
        # Build full scores array
        full_scores = [None] * len(course["pars"])
        for idx, hole_num in enumerate(self.holes_to_score):
            full_scores[hole_num] = scores[idx]
        
        date_str = pr["selected_date"].strftime("%Y-%m-%d") + " " + datetime.now().strftime("%H:%M")
        
        # Get notes
        notes = self.notes_text.get("1.0", "end-1c").strip()
        
        rd = {
            "course_name": course["name"],
            "tee_color": pr["tee"],
            "scores": full_scores,
            "is_serious": pr["is_serious"],
            "round_type": pr["round_type"],
            "notes": notes,
            "holes_played": holes_played,
            "holes_choice": pr["holes_choice"],
            "total_score": total,
            "par": par,
            "tee_rating": tee_rating,
            "tee_slope": tee_slope,
            "date": date_str,
            "entry_mode": pr["entry_mode"],
            "detailed_stats": detailed_stats
        }
        
        # Calculate target score
        course_handicap, target_score = self.backend.calculate_course_handicap(
            course["name"], pr["tee"], pr["holes_choice"]
        )
        rd["target_score"] = target_score if target_score else par
        
        self.backend.rounds.append(rd)
        save_json(ROUNDS_FILE, self.backend.rounds)
        self.backend.invalidate_stats_cache()
        
        # Clear pending round
        self.pending_round = None
        
        # Show completion message
        diff = total - par
        diff_str = f"+{diff}" if diff > 0 else str(diff)
        messagebox.showinfo("Round Saved", 
            f"Score: {total} ({diff_str})\n"
            f"Course: {course['name']}\n"
            f"Holes: {holes_played}")
        
        # Go to rounds page
        self.show_page("rounds")
    def _go_to_log_round(self):
        """Navigate to log round setup page."""
        self.show_page("log_round_setup")

    def _export_selected_scorecard(self):
        """Export selected scorecard."""
        sel = self.score_tree.focus()
        if not sel:
            return messagebox.showwarning("Warning", "Select a round first")
        rd = self.backend.get_rounds()[int(sel)]
        self._show_export_dialog(rd)
    
    def _delete_selected_round(self):
        """Delete selected round."""
        sel = self.score_tree.focus()
        if not sel:
            return messagebox.showwarning("Warning", "Select a round first")
        if messagebox.askyesno("Confirm Delete", "Delete this round? This cannot be undone."):
            self.backend.delete_round(int(sel))
            self._populate_scorecards_list()
    
    # ==================== COURSES PAGE ====================
    
    def _show_courses_page(self):
        """Display consolidated Courses page (Manage + Add)."""
        self._create_page_header("Courses")
        
        # Add Course button
        btn_frame = ttk.Frame(self.content_frame, style="App.TFrame")
        btn_frame.pack(fill='x', padx=16, pady=(0, 8))
        
        ttk.Button(btn_frame, text="➕ Add New Course",
                  command=lambda: self._open_course_editor()).pack(side='right')
        
        # Hint
        ttk.Label(self.content_frame, text="Tap a course to open its yardbook",
                 foreground=self.COLORS["text_secondary"],
                 font=("Helvetica", 11)).pack(padx=16, anchor='w')
        
        # Courses list
        list_frame = ttk.Frame(self.content_frame, style="App.TFrame")
        list_frame.pack(fill='both', expand=True, padx=16, pady=(4, 8))
        
        cols = ("Club", "Course", "Holes", "Par", "Yardbook")
        self.course_tree = ttk.Treeview(list_frame, columns=cols, show="headings", height=12)
        
        widths = [100, 130, 50, 50, 60]
        for col, w in zip(cols, widths):
            self.course_tree.heading(col, text=col)
            self.course_tree.column(col, width=w, anchor='center' if col != "Course" else 'w')
        
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.course_tree.yview)
        self.course_tree.configure(yscrollcommand=scrollbar.set)
        
        self.course_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # Single click to open yardbook
        self.course_tree.bind("<ButtonRelease-1>", self._on_course_click)
        
        # Action buttons (Edit/Delete only)
        action_frame = ttk.Frame(self.content_frame, style="App.TFrame")
        action_frame.pack(fill='x', padx=16, pady=8)
        
        ttk.Button(action_frame, text="✏️ Edit", command=self._edit_selected_course).pack(side='left', padx=2)
        ttk.Button(action_frame, text="🗑 Delete", command=self._delete_selected_course).pack(side='left', padx=2)
        
        self._populate_courses_list()
    
    def _on_course_click(self, event):
        """Handle single click on course row - opens yardbook."""
        sel = self.course_tree.focus()
        if sel:
            vals = self.course_tree.item(sel)["values"]
            course = self.backend.get_course_by_name(vals[1])
            if course:
                self._open_yardbook_for_course(course)
    
    def _open_yardbook_for_course(self, course):
        """Open yardbook for a course with smart hole selection.
        
        - If no data or partial data: opens to last hole with data + 1 (to add more)
        - If full data: opens to hole 1 (to view)
        """
        if not self.yardbook or not self.yardbook.is_available():
            messagebox.showinfo("Unavailable", 
                "Yardbook requires tkintermapview.\npip install tkintermapview")
            return
        
        # Get yardbook summary to determine which hole to open
        summary = self.yardbook.manager.get_course_yardbook_summary(course["name"])
        total_holes = len(course.get("pars", []))
        holes_complete = summary.get("holes_complete", 0)
        holes_with_data = summary.get("holes_with_data", 0)
        
        if holes_complete >= total_holes:
            # Full data - open to hole 1 for viewing
            start_hole = 1
        elif holes_with_data > 0:
            # Partial data - find first hole without complete data
            # Check each hole to find where to continue
            start_hole = 1
            for h in range(1, total_holes + 1):
                features = self.yardbook.manager.get_hole_features(course["name"], h)
                if features and features.has_data():
                    start_hole = h + 1  # Next hole after last with data
                else:
                    break
            
            # Cap at total holes
            if start_hole > total_holes:
                start_hole = total_holes
        else:
            # No data - start at hole 1
            start_hole = 1
        
        # Launch yardbook
        self.yardbook._launch_yardbook(self.root, course, start_hole)
        
        self._populate_courses_list()
    
    def _populate_courses_list(self):
        """Populate the courses treeview."""
        for row in self.course_tree.get_children():
            self.course_tree.delete(row)
        
        for c in sorted(self.backend.get_courses(), key=lambda x: (x.get("club", ""), x["name"])):
            gb_status = "—"
            if self.yardbook and self.yardbook.is_available():
                summary = self.yardbook.manager.get_course_yardbook_summary(c["name"])
                if summary["holes_with_data"] > 0:
                    gb_status = f"✓ {summary['holes_complete']}/{summary['total_holes']}"
            
            self.course_tree.insert("", "end", values=(
                c.get("club", "")[:12], c["name"][:18], len(c["pars"]), 
                sum(c["pars"]), gb_status
            ))
    
    def _edit_selected_course(self):
        """Edit selected course."""
        sel = self.course_tree.focus()
        if not sel:
            return messagebox.showwarning("Warning", "Select a course first")
        vals = self.course_tree.item(sel)["values"]
        course = self.backend.get_course_by_name(vals[1])
        self._open_course_editor(course)
    
    def _delete_selected_course(self):
        """Delete selected course."""
        sel = self.course_tree.focus()
        if not sel:
            return messagebox.showwarning("Warning", "Select a course first")
        vals = self.course_tree.item(sel)["values"]
        if messagebox.askyesno("Confirm Delete", f"Delete '{vals[1]}'? This cannot be undone."):
            self.backend.delete_course(vals[1])
            self._populate_courses_list()
    
    def _open_course_yardbook(self):
        """Open yardbook for selected course."""
        sel = self.course_tree.focus()
        if not sel:
            return messagebox.showwarning("Warning", "Select a course first")
        vals = self.course_tree.item(sel)["values"]
        course = self.backend.get_course_by_name(vals[1])
        if course and self.yardbook and self.yardbook.is_available():
            self.yardbook._launch_yardbook(self.root, course, 1)
    
    def _open_course_editor(self, course=None):
        """Open course editor as inline page."""
        self.editing_course = course
        self.show_page("course_editor")
    
    def _show_course_editor_page(self):
        """Display inline course editor with yardage support."""
        course = getattr(self, 'editing_course', None)
        
        title = "Edit Course" if course else "Add New Course"
        self._create_page_header(title, show_back=True, 
                                back_action=lambda: self.show_page("courses"))
        
        # Scrollable content
        canvas = tk.Canvas(self.content_frame, bg=self.COLORS["bg"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.content_frame, orient="vertical", command=canvas.yview)
        scroll_frame = ttk.Frame(canvas, style="App.TFrame")
        
        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side='left', fill='both', expand=True, padx=16)
        scrollbar.pack(side='right', fill='y')
        
        # Course info card
        info_card = self._create_card(scroll_frame)
        info_card.pack(fill='x', pady=8)
        
        ttk.Label(info_card, text="Course Information", style="Subheader.TLabel").pack(anchor='w', pady=(0, 10))
        
        # Course Name
        row1 = ttk.Frame(info_card)
        row1.pack(fill='x', pady=4)
        ttk.Label(row1, text="Course Name:", width=15, anchor='e').pack(side='left')
        self.edit_name_var = tk.StringVar(value=course["name"] if course else "")
        ttk.Entry(row1, textvariable=self.edit_name_var, width=25).pack(side='left', padx=8)
        
        # Club Name
        row2 = ttk.Frame(info_card)
        row2.pack(fill='x', pady=4)
        ttk.Label(row2, text="Club Name:", width=15, anchor='e').pack(side='left')
        self.edit_club_var = tk.StringVar(value=course.get("club", "") if course else "")
        ttk.Entry(row2, textvariable=self.edit_club_var, width=25).pack(side='left', padx=8)
        
        # Number of Holes
        row3 = ttk.Frame(info_card)
        row3.pack(fill='x', pady=4)
        ttk.Label(row3, text="Number of Holes:", width=15, anchor='e').pack(side='left')
        self.edit_holes_var = tk.StringVar(value=str(len(course["pars"])) if course else "18")
        ttk.Entry(row3, textvariable=self.edit_holes_var, width=8).pack(side='left', padx=8)
        
        # Pars card
        pars_card = self._create_card(scroll_frame)
        pars_card.pack(fill='x', pady=8)
        
        ttk.Label(pars_card, text="Hole Pars", style="Subheader.TLabel").pack(anchor='w', pady=(0, 10))
        ttk.Label(pars_card, text="Enter pars separated by commas (e.g., 4,4,3,5,4...)", 
                 style="Caption.TLabel").pack(anchor='w')
        
        default_pars = ",".join(map(str, course["pars"])) if course else "4,4,4,3,5,4,4,3,5,4,4,4,3,5,4,4,3,5"
        self.edit_pars_var = tk.StringVar(value=default_pars)
        ttk.Entry(pars_card, textvariable=self.edit_pars_var, width=45).pack(fill='x', pady=8)
        
        # Tee boxes card
        tees_card = self._create_card(scroll_frame)
        tees_card.pack(fill='x', pady=8)
        
        ttk.Label(tees_card, text="Tee Boxes", style="Subheader.TLabel").pack(anchor='w', pady=(0, 10))
        
        self.edit_tee_entries = []
        self.tees_container = ttk.Frame(tees_card)
        self.tees_container.pack(fill='x')
        
        if course:
            for tee in course.get("tee_boxes", []):
                yardages = course.get("yardages", {}).get(tee["color"], [])
                self._add_tee_entry(tee, yardages)
        else:
            self._add_tee_entry({"color": "White", "rating": "72.0", "slope": "113"}, [])
        
        ttk.Button(tees_card, text="➕ Add Tee Box", 
                  command=lambda: self._add_tee_entry()).pack(anchor='w', pady=8)
        
        # Save/Cancel buttons
        btn_card = self._create_card(scroll_frame)
        btn_card.pack(fill='x', pady=8)
        
        btn_row = ttk.Frame(btn_card)
        btn_row.pack(fill='x')
        
        ttk.Button(btn_row, text="💾 Save Course", style="Primary.TButton",
                  command=self._save_course_from_page).pack(side='left', padx=4)
        ttk.Button(btn_row, text="Cancel",
                  command=lambda: self.show_page("courses")).pack(side='left', padx=4)
    
    def _add_tee_entry(self, tee_data=None, yardages=None):
        """Add a tee box entry row with yardage."""
        frame = ttk.Frame(self.tees_container)
        frame.pack(fill='x', pady=6)
        
        # Row 1: Tee info
        row1 = ttk.Frame(frame)
        row1.pack(fill='x')
        
        color_var = tk.StringVar(value=tee_data.get("color", "") if tee_data else "")
        rating_var = tk.StringVar(value=str(tee_data.get("rating", "")) if tee_data else "")
        slope_var = tk.StringVar(value=str(tee_data.get("slope", "")) if tee_data else "")
        
        ttk.Label(row1, text="Color:", width=6).pack(side='left')
        ttk.Entry(row1, textvariable=color_var, width=10).pack(side='left', padx=2)
        
        ttk.Label(row1, text="Rating:").pack(side='left', padx=(8, 0))
        ttk.Entry(row1, textvariable=rating_var, width=6).pack(side='left', padx=2)
        
        ttk.Label(row1, text="Slope:").pack(side='left', padx=(8, 0))
        ttk.Entry(row1, textvariable=slope_var, width=5).pack(side='left', padx=2)
        
        # Row 2: Yardages
        row2 = ttk.Frame(frame)
        row2.pack(fill='x', pady=(4, 0))
        
        ttk.Label(row2, text="Yardages:", width=8).pack(side='left')
        yardage_str = ",".join(map(str, yardages)) if yardages else ""
        yardage_var = tk.StringVar(value=yardage_str)
        ttk.Entry(row2, textvariable=yardage_var, width=40).pack(side='left', padx=2)
        
        # Separator
        ttk.Separator(frame, orient='horizontal').pack(fill='x', pady=(8, 0))
        
        self.edit_tee_entries.append((color_var, rating_var, slope_var, yardage_var, frame))
    
    def _save_course_from_page(self):
        """Save course from inline editor."""
        name = self.edit_name_var.get().strip()
        club = self.edit_club_var.get().strip()
        
        if not name:
            messagebox.showerror("Error", "Course name is required")
            return
        
        try:
            pars = [int(p.strip()) for p in self.edit_pars_var.get().split(",")]
        except:
            messagebox.showerror("Error", "Invalid pars format. Use comma-separated numbers.")
            return
        
        tee_boxes = []
        yardages = {}
        
        for color_var, rating_var, slope_var, yardage_var, _ in self.edit_tee_entries:
            color = color_var.get().strip()
            if color:
                try:
                    rating = float(rating_var.get()) if rating_var.get() else 72.0
                    slope = int(slope_var.get()) if slope_var.get() else 113
                    tee_boxes.append({"color": color, "rating": rating, "slope": slope})
                    
                    # Parse yardages
                    yard_str = yardage_var.get().strip()
                    if yard_str:
                        try:
                            yards = [int(y.strip()) if y.strip() else 0 for y in yard_str.split(",")]
                            yardages[color] = yards
                        except:
                            pass  # Invalid yardage, skip
                except Exception as e:
                    messagebox.showerror("Error", f"Invalid tee box data for {color}: {e}")
                    return
        
        course_data = {
            "name": name,
            "club": club,
            "pars": pars,
            "tee_boxes": tee_boxes,
            "yardages": yardages
        }
        
        editing = getattr(self, 'editing_course', None)
        if editing:
            self.backend.update_course(editing["name"], course_data)
            messagebox.showinfo("Success", "Course updated successfully!")
        else:
            self.backend.add_course(course_data)
            messagebox.showinfo("Success", "Course added successfully!")
        
        self.editing_course = None
        self.show_page("courses")
    
    # ==================== YARDBOOK PAGE ====================
    
    def _show_yardbook_page(self):
        """Display yardbook course selector."""
        self._create_page_header("Yardbook")
        
        if not self.yardbook or not self.yardbook.is_available():
            card = self._create_card(self.content_frame)
            card.pack(fill='x', padx=16, pady=8)
            ttk.Label(card, text="Yardbook Unavailable", style="Subheader.TLabel").pack(anchor='w')
            ttk.Label(card, text="Install tkintermapview to enable:\npip install tkintermapview",
                     style="Caption.TLabel").pack(anchor='w', pady=8)
            return
        
        # Quick launch
        card = self._create_card(self.content_frame)
        card.pack(fill='x', padx=16, pady=8)
        
        ttk.Label(card, text="Select a course to map", style="Subheader.TLabel").pack(anchor='w')
        
        courses = self.backend.get_courses()
        if not courses:
            ttk.Label(card, text="No courses added yet.", style="Caption.TLabel").pack(pady=20)
            return
        
        course_names = sorted([c["name"] for c in courses])
        
        ttk.Label(card, text="Course:", style="Body.TLabel").pack(anchor='w', pady=(12, 4))
        self.yb_course_var = tk.StringVar()
        course_combo = ttk.Combobox(card, textvariable=self.yb_course_var,
                                    values=course_names, state='readonly', width=35)
        course_combo.pack(anchor='w')
        if course_names:
            course_combo.set(course_names[0])
        
        ttk.Label(card, text="Hole:", style="Body.TLabel").pack(anchor='w', pady=(12, 4))
        self.yb_hole_var = tk.IntVar(value=1)
        hole_spin = ttk.Spinbox(card, from_=1, to=18, textvariable=self.yb_hole_var, width=5)
        hole_spin.pack(anchor='w')
        
        ttk.Button(card, text="Open Yardbook", command=self._launch_yardbook_from_page,
                  style="Primary.TButton").pack(fill='x', pady=12)
    
    def _launch_yardbook_from_page(self):
        """Launch yardbook from the yardbook page."""
        course_name = self.yb_course_var.get()
        hole = self.yb_hole_var.get()
        
        course = self.backend.get_course_by_name(course_name)
        if course:
            self.yardbook._launch_yardbook(self.root, course, hole)
    
    # ==================== STATISTICS PAGE ====================
    
    def _show_statistics_page(self):
        """Display statistics page with club distances integrated."""
        self._create_page_header("Statistics", show_back=True,
                                back_action=lambda: self.show_page("home"))
        
        # Notebook for tabs
        notebook = ttk.Notebook(self.content_frame)
        notebook.pack(fill='both', expand=True, padx=16, pady=8)
        
        # Tab 1: Overview
        self._create_stats_overview_tab(notebook)
        
        # Tab 2: Performance
        self._create_stats_performance_tab(notebook)
        
        # Tab 3: Club Distances (MOVED HERE)
        self._create_club_distances_tab(notebook)
        
        # Tab 4: Analysis
        self._create_stats_analysis_tab(notebook)
    
    def _create_stats_overview_tab(self, notebook):
        """Create overview statistics tab."""
        frame = ttk.Frame(notebook, padding=10)
        notebook.add(frame, text="Overview")
        
        stats = self.backend.get_statistics()
        idx = self.backend.calculate_handicap_index()
        
        # Stats grid
        stats_data = [
            ("Handicap Index", f"{idx:.1f}" if idx else "Not established"),
            ("Total Rounds", stats["total_rounds"]),
            ("18-Hole Rounds", stats["rounds_18"]),
            ("9-Hole Rounds", stats["rounds_9"]),
            ("Avg Score (18h)", stats["avg_score_18"] or "N/A"),
            ("Total Holes Played", stats.get("total_holes_played", 0)),
        ]
        
        for i, (label, value) in enumerate(stats_data):
            ttk.Label(frame, text=label + ":", style="Body.TLabel").grid(
                row=i, column=0, sticky='e', padx=5, pady=4)
            ttk.Label(frame, text=str(value), font=("Helvetica", 14, "bold")).grid(
                row=i, column=1, sticky='w', padx=5, pady=4)
        
        # Score differentials
        diffs = self.backend.get_score_differentials()
        if diffs:
            ttk.Label(frame, text="Recent Differentials:", style="Subheader.TLabel").grid(
                row=len(stats_data), column=0, columnspan=2, sticky='w', pady=(16, 8))
            
            cols = ("Diff", "Score", "Course")
            tree = ttk.Treeview(frame, columns=cols, show="headings", height=6)
            for col in cols:
                tree.heading(col, text=col)
            tree.column("Diff", width=60, anchor='center')
            tree.column("Score", width=60, anchor='center')
            tree.column("Course", width=150)
            tree.grid(row=len(stats_data)+1, column=0, columnspan=2, sticky='nsew')
            
            for d in diffs[:8]:
                tree.insert("", "end", values=(d["diff"], d["score"], d["course"][:20]))
    
    def _create_stats_performance_tab(self, notebook):
        """Create performance statistics tab - mobile friendly layout."""
        # Create scrollable frame
        container = ttk.Frame(notebook)
        notebook.add(container, text="Performance")
        
        canvas = tk.Canvas(container, highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        frame = ttk.Frame(canvas, padding=10)
        
        frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        adv_stats = self.backend.get_advanced_statistics()
        
        if adv_stats.get("total_holes_tracked", 0) == 0:
            ttk.Label(frame, text="No detailed stats available yet.",
                     font=("Helvetica", 14)).pack(pady=20)
            ttk.Label(frame, text="Use 'Detailed' entry mode when\nlogging rounds to track stats.",
                     foreground="#8E8E93").pack()
            return
        
        # GIR Card
        gir_card = ttk.LabelFrame(frame, text="Greens in Regulation", padding=12)
        gir_card.pack(fill='x', pady=8)
        
        gir_overall = adv_stats.get('gir_overall')
        if gir_overall:
            ttk.Label(gir_card, text=f"{gir_overall}%",
                     font=("Helvetica", 28, "bold"),
                     foreground="#007AFF").pack(anchor='w')
            ttk.Label(gir_card, text="Overall GIR",
                     foreground="#8E8E93").pack(anchor='w')
        
        # GIR breakdown
        gir_breakdown = ttk.Frame(gir_card)
        gir_breakdown.pack(fill='x', pady=(12, 0))
        
        for i, (label, key) in enumerate([("Par 3", 'gir_par3'), 
                                           ("Par 4", 'gir_par4'), 
                                           ("Par 5", 'gir_par5')]):
            col = ttk.Frame(gir_breakdown)
            col.pack(side='left', expand=True)
            val = adv_stats.get(key)
            ttk.Label(col, text=f"{val}%" if val else "—",
                     font=("Helvetica", 16, "bold")).pack()
            ttk.Label(col, text=label, foreground="#8E8E93",
                     font=("Helvetica", 11)).pack()
        
        # Putting Card
        putt_card = ttk.LabelFrame(frame, text="Putting", padding=12)
        putt_card.pack(fill='x', pady=8)
        
        avg_putts = adv_stats.get('avg_putts_overall')
        if avg_putts:
            ttk.Label(putt_card, text=f"{avg_putts:.1f}",
                     font=("Helvetica", 28, "bold"),
                     foreground="#007AFF").pack(anchor='w')
            ttk.Label(putt_card, text="Avg Putts per Hole",
                     foreground="#8E8E93").pack(anchor='w')
        
        # Putt breakdown
        putt_breakdown = ttk.Frame(putt_card)
        putt_breakdown.pack(fill='x', pady=(12, 0))
        
        for label, key in [("1-Putt", 'one_putt_rate'), ("2-Putt", 'two_putt_rate'), ("3-Putt", 'three_putt_rate')]:
            col = ttk.Frame(putt_breakdown)
            col.pack(side='left', expand=True)
            val = adv_stats.get(key)
            ttk.Label(col, text=f"{val}%" if val else "—",
                     font=("Helvetica", 16, "bold")).pack()
            ttk.Label(col, text=f"{label} Rate", foreground="#8E8E93",
                     font=("Helvetica", 11)).pack()
        
        # Fairways Card (if data exists)
        fir = adv_stats.get('fir_overall')
        if fir:
            fir_card = ttk.LabelFrame(frame, text="Fairways in Regulation", padding=12)
            fir_card.pack(fill='x', pady=8)
            
            ttk.Label(fir_card, text=f"{fir}%",
                     font=("Helvetica", 28, "bold"),
                     foreground="#007AFF").pack(anchor='w')
            ttk.Label(fir_card, text="Fairways Hit (Par 4/5)",
                     foreground="#8E8E93").pack(anchor='w')
    
    def _create_club_distances_tab(self, notebook):
        """Create club distances tab (moved from separate window)."""
        frame = ttk.Frame(notebook, padding=10)
        notebook.add(frame, text="Clubs")
        
        # Add club form
        add_frame = ttk.LabelFrame(frame, text="Add/Update Club", padding=8)
        add_frame.pack(fill='x', pady=(0, 8))
        
        form_grid = ttk.Frame(add_frame)
        form_grid.pack(fill='x')
        
        ttk.Label(form_grid, text="Club:").grid(row=0, column=0, sticky='e', padx=4)
        self.club_name_var = tk.StringVar()
        club_combo = ttk.Combobox(form_grid, textvariable=self.club_name_var, width=12,
                                  values=["Driver", "3 Wood", "5 Wood", "Hybrid", 
                                         "3 Iron", "4 Iron", "5 Iron", "6 Iron", 
                                         "7 Iron", "8 Iron", "9 Iron", 
                                         "PW", "GW", "SW", "LW", "Putter"])
        club_combo.grid(row=0, column=1, padx=4, pady=2)
        
        ttk.Label(form_grid, text="Distance:").grid(row=0, column=2, sticky='e', padx=4)
        self.club_dist_var = tk.StringVar()
        ttk.Entry(form_grid, textvariable=self.club_dist_var, width=6).grid(row=0, column=3, padx=4)
        ttk.Label(form_grid, text="yds").grid(row=0, column=4, sticky='w')
        
        ttk.Button(form_grid, text="Save", command=self._save_club).grid(row=0, column=5, padx=8)
        
        # Clubs list
        list_frame = ttk.Frame(frame)
        list_frame.pack(fill='both', expand=True)
        
        cols = ("Club", "Distance", "Notes")
        self.clubs_tree = ttk.Treeview(list_frame, columns=cols, show="headings", height=10)
        for col in cols:
            self.clubs_tree.heading(col, text=col)
        self.clubs_tree.column("Club", width=100)
        self.clubs_tree.column("Distance", width=80, anchor='center')
        self.clubs_tree.column("Notes", width=120)
        
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.clubs_tree.yview)
        self.clubs_tree.configure(yscrollcommand=scrollbar.set)
        
        self.clubs_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        self.clubs_tree.bind("<Double-1>", self._on_club_select)
        
        ttk.Button(frame, text="Delete Selected", command=self._delete_club).pack(pady=4)
        
        self._populate_clubs_list()
    
    def _populate_clubs_list(self):
        """Populate clubs treeview."""
        for row in self.clubs_tree.get_children():
            self.clubs_tree.delete(row)
        for club in self.backend.get_clubs_sorted_by_distance():
            self.clubs_tree.insert("", "end", values=(
                club["name"], f"{club['distance']} yds", club.get("notes", "")))
    
    def _on_club_select(self, event):
        """Handle club selection for editing."""
        sel = self.clubs_tree.focus()
        if sel:
            vals = self.clubs_tree.item(sel)["values"]
            self.club_name_var.set(vals[0])
            self.club_dist_var.set(str(vals[1]).replace(" yds", ""))
    
    def _save_club(self):
        """Save club distance."""
        name = self.club_name_var.get().strip()
        try:
            distance = int(self.club_dist_var.get())
        except ValueError:
            return messagebox.showerror("Error", "Distance must be a number")
        if not name:
            return messagebox.showerror("Error", "Enter a club name")
        
        club_data = {"name": name, "distance": distance, "notes": ""}
        existing = next((c for c in self.backend.get_clubs() 
                        if c["name"].lower() == name.lower()), None)
        if existing:
            self.backend.update_club(existing["name"], club_data)
        else:
            self.backend.add_club(club_data)
        
        self._populate_clubs_list()
        self.club_name_var.set("")
        self.club_dist_var.set("")
    
    def _delete_club(self):
        """Delete selected club."""
        sel = self.clubs_tree.focus()
        if not sel:
            return messagebox.showwarning("Warning", "Select a club first")
        vals = self.clubs_tree.item(sel)["values"]
        if messagebox.askyesno("Confirm", f"Delete {vals[0]}?"):
            self.backend.delete_club(vals[0])
            self._populate_clubs_list()
    
    def _create_stats_analysis_tab(self, notebook):
        """Create stroke leak analysis tab - mobile friendly layout."""
        # Create scrollable frame
        container = ttk.Frame(notebook)
        notebook.add(container, text="Analysis")
        
        canvas = tk.Canvas(container, highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        frame = ttk.Frame(canvas, padding=10)
        
        frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        insights = self.backend.get_stroke_leak_analysis()
        adv_stats = self.backend.get_advanced_statistics()
        
        if adv_stats.get("total_holes_tracked", 0) == 0:
            # No data card
            no_data_card = ttk.LabelFrame(frame, text="Analysis", padding=16)
            no_data_card.pack(fill='x', pady=8)
            
            ttk.Label(no_data_card, text="📊",
                     font=("Helvetica", 48)).pack(pady=(0, 12))
            ttk.Label(no_data_card, text="No Data Available",
                     font=("Helvetica", 18, "bold")).pack()
            ttk.Label(no_data_card, text="Use 'Detailed' entry mode when\nlogging rounds to track stats.",
                     foreground="#8E8E93", justify='center').pack(pady=8)
            return
        
        if not insights:
            # Great job card
            success_card = ttk.LabelFrame(frame, text="Game Analysis", padding=16)
            success_card.pack(fill='x', pady=8)
            
            ttk.Label(success_card, text="🎉",
                     font=("Helvetica", 48)).pack(pady=(0, 12))
            ttk.Label(success_card, text="Great Job!",
                     font=("Helvetica", 22, "bold"),
                     foreground="#34C759").pack()
            ttk.Label(success_card, text="No significant areas of\nconcern detected in your game.",
                     foreground="#8E8E93", justify='center').pack(pady=8)
            
            # Show summary stats
            summary_card = ttk.LabelFrame(frame, text="Summary", padding=12)
            summary_card.pack(fill='x', pady=8)
            
            ttk.Label(summary_card, text=f"Holes Analyzed: {adv_stats.get('total_holes_tracked', 0)}",
                     font=("Helvetica", 12)).pack(anchor='w', pady=2)
            if adv_stats.get('gir_overall'):
                ttk.Label(summary_card, text=f"GIR: {adv_stats.get('gir_overall')}%",
                         font=("Helvetica", 12)).pack(anchor='w', pady=2)
            if adv_stats.get('avg_putts_overall'):
                ttk.Label(summary_card, text=f"Avg Putts: {adv_stats.get('avg_putts_overall'):.1f}",
                         font=("Helvetica", 12)).pack(anchor='w', pady=2)
            return
        
        # Areas to Focus card
        focus_card = ttk.LabelFrame(frame, text="Areas to Improve", padding=12)
        focus_card.pack(fill='x', pady=8)
        
        ttk.Label(focus_card, text=f"{len(insights)} area{'s' if len(insights) > 1 else ''} identified",
                 foreground="#8E8E93",
                 font=("Helvetica", 11)).pack(anchor='w', pady=(0, 12))
        
        for insight in insights:
            severity = insight.get("severity", "medium")
            
            # Create insight card
            insight_card = ttk.Frame(focus_card, style="Card.TFrame", padding=10)
            insight_card.pack(fill='x', pady=6)
            
            # Icon and severity indicator
            icon_frame = ttk.Frame(insight_card)
            icon_frame.pack(fill='x')
            
            if severity == "high":
                icon = "🔴"
                severity_text = "High Priority"
                color = "#FF3B30"
            else:
                icon = "🟡"
                severity_text = "Medium Priority"
                color = "#FF9500"
            
            ttk.Label(icon_frame, text=icon, font=("Helvetica", 18)).pack(side='left')
            ttk.Label(icon_frame, text=severity_text, 
                     font=("Helvetica", 11, "bold"),
                     foreground=color).pack(side='left', padx=(8, 0))
            
            # Message
            ttk.Label(insight_card, text=insight["message"],
                     wraplength=320, font=("Helvetica", 12)).pack(anchor='w', pady=(8, 0))
            
            # Tip if available
            area = insight.get("area", "")
            tip = self._get_improvement_tip(area)
            if tip:
                ttk.Label(insight_card, text=f"💡 {tip}",
                         wraplength=320, foreground="#8E8E93",
                         font=("Helvetica", 11)).pack(anchor='w', pady=(8, 0))
        
        # Pro tip card
        tip_card = ttk.LabelFrame(frame, text="Pro Tip", padding=12)
        tip_card.pack(fill='x', pady=8)
        
        ttk.Label(tip_card, text="Focus on one area at a time.\nTrack your progress over multiple rounds.",
                 foreground="#8E8E93", font=("Helvetica", 11)).pack(anchor='w')
    
    def _get_improvement_tip(self, area):
        """Get improvement tip for a specific area."""
        tips = {
            "putting": "Practice lag putting to reduce 3-putts",
            "three_putts": "Work on distance control with long putts",
            "gir": "Focus on iron accuracy at the range",
            "fir": "Consider a more consistent tee shot",
            "scrambling": "Practice short game around the green",
        }
        return tips.get(area, "")
    
    # ==================== RULEBOOK PAGE ====================
    
    def _show_rulebook_page(self):
        """Display rulebook page."""
        self._create_page_header("Rules of Golf", show_back=True, 
                                back_action=lambda: self.show_page("home"))
        
        # Open rulebook in window (keeping existing implementation)
        self.open_rulebook()
    
    # ==================== LEGACY METHOD BRIDGES ====================
    
    def open_log_round_page(self):
        """Bridge to new rounds page."""
        self.show_page("rounds")
    
    def open_manage_courses(self):
        """Bridge to new courses page."""
        self.show_page("courses")
    
    def open_yardbook(self):
        """Bridge to yardbook page."""
        if self.yardbook and self.yardbook.is_available():
            self.show_page("yardbook")
        else:
            messagebox.showinfo("Unavailable", 
                "Yardbook requires tkintermapview.\npip install tkintermapview")
    
    def open_club_distances(self):
        """Bridge - now part of statistics."""
        self.show_page("statistics")
    
    def open_scorecards_page(self):
        """Bridge to rounds page."""
        self.show_page("rounds")
    
    def open_statistics(self):
        """Bridge to statistics page."""
        self.show_page("statistics")
    
    def refresh_summary(self):
        """Refresh home page if showing."""
        if self.current_page == "home":
            self.show_page("home")
    
    def _show_export_dialog(self, round_data):
        """Show export options dialog."""
        ExportDialog(self.root, self.backend, round_data)

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
                       font=("Helvetica", 11))
        style.configure("Sidebar.Treeview.Heading", font=("Helvetica", 11, "bold"))
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
        self.total_pages_label = ttk.Label(page_group, text=f" of {total_pages}", font=("Helvetica", 11))
        self.total_pages_label.pack(side='left')
        
        ttk.Separator(toolbar_inner, orient='vertical').pack(side='left', fill='y', padx=12)
        
        # Zoom controls
        zoom_group = ttk.Frame(toolbar_inner)
        zoom_group.pack(side='left')
        
        ttk.Button(zoom_group, text="−", command=self.zoom_out, width=3).pack(side='left', padx=1)
        self.zoom_label = ttk.Label(zoom_group, text="150%", width=5, anchor='center', font=("Helvetica", 10))
        self.zoom_label.pack(side='left', padx=4)
        ttk.Button(zoom_group, text="+", command=self.zoom_in, width=3).pack(side='left', padx=1)
        
        ttk.Separator(toolbar_inner, orient='vertical').pack(side='left', fill='y', padx=12)
        
        # Search (Apple-style search field)
        search_group = ttk.Frame(toolbar_inner)
        search_group.pack(side='left', fill='x', expand=True)
        
        ttk.Label(search_group, text="🔍", font=("Helvetica", 12)).pack(side='left')
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
        ttk.Label(sidebar_header, text="Table of Contents", font=("Helvetica", 13, "bold")).pack(side='left')
        
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
        ttk.Label(status_bar, textvariable=self.status_var, font=("Helvetica", 10), foreground='#666666').pack(side='left', padx=10)

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
                                            font=("Helvetica", 18, "bold"), anchor='center')
            elif line.startswith("━"):
                self.pdf_canvas.create_text(300, y_pos, text=line, fill='#666666', 
                                            font=("Helvetica", 10), anchor='center')
            elif line == "No PDF Loaded":
                self.pdf_canvas.create_text(300, y_pos, text=line, fill='#FF9500', 
                                            font=("Helvetica", 14), anchor='center')
            elif line.startswith("Features"):
                self.pdf_canvas.create_text(300, y_pos, text=line, fill='#AAAAAA', 
                                            font=("Helvetica", 12, "bold"), anchor='center')
            elif line.startswith("•"):
                self.pdf_canvas.create_text(300, y_pos, text=line, fill='#888888', 
                                            font=("Helvetica", 11), anchor='center')
            else:
                self.pdf_canvas.create_text(300, y_pos, text=line, fill='#CCCCCC', 
                                            font=("Helvetica", 12), anchor='center')
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
                  font=("Helvetica", 12, "bold")).pack(anchor='w', pady=(0, 10))
        
        # Results listbox
        list_frame = ttk.Frame(frame)
        list_frame.pack(fill='both', expand=True)
        
        results_list = tk.Listbox(list_frame, height=15, width=60, font=("Helvetica", 11))
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

if __name__ == "__main__":
    root = tk.Tk()
    app = GolfApp(root)
    root.mainloop()