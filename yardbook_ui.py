"""
yardbook View - Interactive map-based yardage book feature.
Uses tkintermapview for satellite imagery and custom overlays.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional, Dict, List, Tuple, Callable

# Runtime capability detection for tkintermapview
def _check_map_available():
    """Check if tkintermapview is available at runtime."""
    try:
        import tkintermapview
        return True, tkintermapview
    except ImportError:
        return False, None

_map_available, tkintermapview = _check_map_available()

# Import from consolidated Backend module
from Backend import (
    # OSM functions
    is_osm_available, import_osm_features, get_osm_feature_stats,
    # SAM functions
    is_sam_available, get_sam_unavailable_message,
    # Geospatial functions
    generate_distance_ring, midpoint, calculate_hole_distances,
    validate_yardage_difference, haversine_distance, bearing, destination_point,
    # Data classes and manager
    yardbookManager, GeoPoint, Target, Hazard, Polygon,
    DISTANCE_RING_PRESETS, POLYGON_STYLES, MARKER_STYLES
)


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
    MODE_SAM_TRACE = "sam_trace"  # SAM auto-trace mode
    
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
        
        # Map objects tracking (for cleanup)
        self.map_markers: Dict[str, any] = {}
        self.map_paths: List[any] = []
        self.map_polygons: Dict[str, any] = {}
        self.distance_rings: List[any] = []
        self.aim_lines: List[any] = []
        self.distance_labels: Dict[str, any] = {}  # For on-map distance labels
        
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
        """Create the main yardbook window."""
        self.window = tk.Toplevel(self.parent)
        self.window.title(f"yardbook - {self.course_name} - Hole {self.hole_num}")
        self.window.geometry("1200x800")
        self.window.minsize(900, 600)
        
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
        """Create the top toolbar."""
        toolbar = ttk.Frame(self.main_frame, padding=5)
        toolbar.grid(row=0, column=0, columnspan=2, sticky='ew')
        
        # Hole navigation
        ttk.Button(toolbar, text="◀ Prev", command=self._prev_hole, width=8).pack(side='left', padx=2)
        
        self.hole_label = ttk.Label(
            toolbar, 
            text=f"Hole {self.hole_num} - Par {self.hole_par}",
            font=("Helvetica", 14, "bold")
        )
        self.hole_label.pack(side='left', padx=10)
        
        ttk.Button(toolbar, text="Next ▶", command=self._next_hole, width=8).pack(side='left', padx=2)
        
        # Spacer
        ttk.Label(toolbar, text="  |  ").pack(side='left', padx=5)
        
        # Mode buttons
        self.mode_var = tk.StringVar(value=self.MODE_PAN)
        
        modes = [
            ("Pan", self.MODE_PAN, "🖐"),
            ("Tee", self.MODE_TEE, "T"),
            ("Green Front", self.MODE_GREEN_FRONT, "F"),
            ("Green Back", self.MODE_GREEN_BACK, "B"),
            ("Target", self.MODE_TARGET, "◎"),
            ("Hazard", self.MODE_HAZARD, "⚠"),
            ("Polygon", self.MODE_POLYGON, "▢"),
            ("Move", self.MODE_MOVE, "✥"),      # New: move mode
            ("Delete", self.MODE_DELETE, "🗑"),  # New: delete mode
        ]
        
        for label, mode, icon in modes:
            btn = ttk.Radiobutton(
                toolbar, 
                text=f"{icon} {label}",
                variable=self.mode_var,
                value=mode,
                command=lambda m=mode: self._set_mode(m)
            )
            btn.pack(side='left', padx=3)
        
        # Right side - action buttons
        ttk.Button(toolbar, text="📊 Greenbook View", command=self._show_greenbook_view).pack(side='right', padx=5)
        ttk.Button(toolbar, text="💾 Save", command=self._save_features).pack(side='right', padx=5)
        ttk.Button(toolbar, text="🗑 Clear All", command=self._clear_all).pack(side='right', padx=5)
    
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
        """Create the right sidebar with info and controls."""
        sidebar = ttk.Frame(self.main_frame, width=300)
        sidebar.grid(row=1, column=1, sticky='ns', padx=5, pady=5)
        sidebar.grid_propagate(False)
        
        # Hole Info Section
        info_frame = ttk.LabelFrame(sidebar, text="Hole Info", padding=10)
        info_frame.pack(fill='x', pady=(0, 10))
        
        ttk.Label(info_frame, text=f"Par: {self.hole_par}", font=("Helvetica", 11)).pack(anchor='w')
        
        if self.hole_yardage:
            ttk.Label(info_frame, text=f"Scorecard: {self.hole_yardage} yds", font=("Helvetica", 11)).pack(anchor='w')
        
        # Distances Section
        dist_frame = ttk.LabelFrame(sidebar, text="📏 Distances", padding=10)
        dist_frame.pack(fill='x', pady=(0, 10))
        
        self.dist_labels = {}
        dist_items = [
            ("tee_to_front", "Tee → Front:"),
            ("tee_to_back", "Tee → Back:"),
            ("tee_to_center", "Tee → Center:"),
            ("green_depth", "Green Depth:"),
        ]
        
        for key, label_text in dist_items:
            row = ttk.Frame(dist_frame)
            row.pack(fill='x', pady=1)
            ttk.Label(row, text=label_text, width=14).pack(side='left')
            lbl = ttk.Label(row, text="--", font=("Helvetica", 10, "bold"))
            lbl.pack(side='left')
            self.dist_labels[key] = lbl
        
        # Targets list
        ttk.Label(dist_frame, text="Targets:", font=("Helvetica", 10, "bold")).pack(anchor='w', pady=(10, 2))
        self.targets_listbox = tk.Listbox(dist_frame, height=4, font=("Helvetica", 9))
        self.targets_listbox.pack(fill='x')
        self.targets_listbox.bind('<Double-1>', self._edit_target)
        self.targets_listbox.bind('<Delete>', self._delete_target)
        
        # Toggle Controls Section
        toggle_frame = ttk.LabelFrame(sidebar, text="Display", padding=10)
        toggle_frame.pack(fill='x', pady=(0, 10))
        
        ttk.Checkbutton(
            toggle_frame, text="Distance Rings",
            variable=self.show_distance_rings,
            command=self._toggle_distance_rings
        ).pack(anchor='w')
        
        ttk.Checkbutton(
            toggle_frame, text="Aim Lines",
            variable=self.show_aim_lines,
            command=self._toggle_aim_lines
        ).pack(anchor='w')
        
        ttk.Checkbutton(
            toggle_frame, text="Overlays",
            variable=self.show_polygons,
            command=self._toggle_polygons
        ).pack(anchor='w')
        
        # Polygon Type Selection (when in polygon mode)
        self.polygon_frame = ttk.LabelFrame(sidebar, text="Polygon Type", padding=10)
        self.polygon_frame.pack(fill='x', pady=(0, 10))
        
        self.polygon_type_var = tk.StringVar(value="fairway")
        for ptype, style in POLYGON_STYLES.items():
            ttk.Radiobutton(
                self.polygon_frame,
                text=style["label"],
                variable=self.polygon_type_var,
                value=ptype,
                command=lambda: self._set_polygon_type(self.polygon_type_var.get())
            ).pack(anchor='w')
        
        ttk.Button(
            self.polygon_frame, 
            text="Finish Polygon",
            command=self._finish_polygon
        ).pack(pady=5)
        
        ttk.Button(
            self.polygon_frame,
            text="Cancel",
            command=self._cancel_polygon
        ).pack()
        
        self.polygon_frame.pack_forget()  # Hidden by default
        
        # Auto-trace section (OSM and SAM)
        auto_frame = ttk.LabelFrame(sidebar, text="Auto Features", padding=10)
        auto_frame.pack(fill='x', pady=(0, 10))
        
        ttk.Button(
            auto_frame,
            text="🌍 Import from OSM",
            command=self._import_osm_features
        ).pack(fill='x', pady=2)
        
        ttk.Button(
            auto_frame,
            text="✨ Auto-Trace (SAM)",
            command=self._start_sam_autotrace
        ).pack(fill='x', pady=2)
        
        ttk.Label(
            auto_frame,
            text="Import course features from\nOpenStreetMap or auto-trace\nfrom satellite imagery",
            font=("Helvetica", 8),
            foreground="gray"
        ).pack(pady=(5, 0))
        
        # Hazard Type Selection
        self.hazard_frame = ttk.LabelFrame(sidebar, text="Hazard Type", padding=10)
        self.hazard_frame.pack(fill='x', pady=(0, 10))
        
        self.hazard_type_var = tk.StringVar(value="water")
        for htype in ["water", "bunker", "ob", "native"]:
            ttk.Radiobutton(
                self.hazard_frame,
                text=htype.title(),
                variable=self.hazard_type_var,
                value=htype
            ).pack(anchor='w')
        
        self.hazard_frame.pack_forget()  # Hidden by default
        
        # Distance Rings Config - Now uses player's clubs
        self.rings_frame = ttk.LabelFrame(sidebar, text="Distance Rings (Your Clubs)", padding=10)
        self.rings_frame.pack(fill='x', pady=(0, 10))
        
        # Create scrollable frame for club rings if many clubs
        self._create_club_rings_ui()
        
        # Status bar
        self.status_label = ttk.Label(
            sidebar, 
            text="Ready. Select a mode to place markers.",
            font=("Helvetica", 9),
            foreground="gray"
        )
        self.status_label.pack(side='bottom', pady=10)
    
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
        
        if self.current_mode == self.MODE_PAN:
            return  # Let map handle panning
        
        elif self.current_mode == self.MODE_DELETE:
            self._handle_delete_click(lat, lon)
        
        elif self.current_mode == self.MODE_MOVE:
            # Move mode click is handled by marker drag
            self._handle_move_click(lat, lon)
        
        elif self.current_mode == self.MODE_SAM_TRACE:
            # Handle SAM auto-trace click
            self._handle_sam_trace_click(coords)
            return  # Don't update aim lines during trace
        
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
        
        # Update on-map distances
        if self.show_on_map_distances.get():
            self._render_on_map_distances()
    
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
        """Finish drawing the current polygon."""
        if len(self.temp_polygon_vertices) < 3:
            messagebox.showwarning("Warning", "Polygon needs at least 3 vertices.")
            return
        
        ptype = self.polygon_type_var.get()
        
        # Save polygon
        self.features.polygons[ptype] = Polygon()
        for lat, lon in self.temp_polygon_vertices:
            self.features.polygons[ptype].add_vertex(lat, lon)
        
        # Clear temp markers
        self._clear_temp_polygon_markers()
        
        # Render the final polygon
        self._render_polygon(ptype)
        
        self.temp_polygon_vertices = []
        self.unsaved_changes = True
        self._set_status(f"{POLYGON_STYLES[ptype]['label']} polygon saved.")
    
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
        
        # Render polygons first (background)
        for ptype, polygon in self.features.polygons.items():
            if polygon.is_valid():
                self._render_polygon(ptype)
        
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
    
    def _render_polygon(self, ptype: str):
        """Render a polygon overlay."""
        if not self.map_widget:
            return
        
        polygon = self.features.polygons.get(ptype)
        if not polygon or not polygon.is_valid():
            return
        
        # Remove existing polygon of this type
        if ptype in self.map_polygons:
            try:
                self.map_polygons[ptype].delete()
            except:
                pass
        
        style = POLYGON_STYLES.get(ptype, POLYGON_STYLES["fairway"])
        
        # Convert to list of tuples
        coords = [(v["lat"], v["lon"]) for v in polygon.vertices]
        
        # tkintermapview uses set_polygon for filled areas
        try:
            poly = self.map_widget.set_polygon(
                coords,
                fill_color=style["fill_color"],
                outline_color=style["outline_color"],
                border_width=2
            )
            self.map_polygons[ptype] = poly
        except Exception as e:
            print(f"Error rendering polygon: {e}")
    
    def _render_aim_lines(self):
        """Render aim lines from tee to targets and green."""
        if not self.map_widget:
            return
        
        # Clear existing aim lines
        for line in self.aim_lines:
            try:
                line.delete()
            except:
                pass
        self.aim_lines = []
        
        if not self.features.tee.is_set():
            return
        
        tee = (self.features.tee.lat, self.features.tee.lon)
        
        # Line to green center
        if self.features.green_front.is_set() and self.features.green_back.is_set():
            center = midpoint(
                self.features.green_front.lat, self.features.green_front.lon,
                self.features.green_back.lat, self.features.green_back.lon
            )
            line = self.map_widget.set_path(
                [tee, center],
                color="#44FF44",
                width=2
            )
            self.aim_lines.append(line)
        elif self.features.green_front.is_set():
            gf = (self.features.green_front.lat, self.features.green_front.lon)
            line = self.map_widget.set_path(
                [tee, gf],
                color="#44FF44",
                width=2
            )
            self.aim_lines.append(line)
        
        # Lines to targets
        for target in self.features.targets:
            if target.lat is not None:
                t = (target.lat, target.lon)
                line = self.map_widget.set_path(
                    [tee, t],
                    color="#FFFF44",
                    width=1
                )
                self.aim_lines.append(line)
    
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
        """Update the distances panel with current calculations."""
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
        
        # Update targets list
        self.targets_listbox.delete(0, tk.END)
        for target_dist in distances["targets"]:
            text = f"{target_dist['name']}: {target_dist['from_tee']:.0f}y"
            if target_dist['to_green']:
                text += f" → {target_dist['to_green']:.0f}y to green"
            self.targets_listbox.insert(tk.END, text)
        
        # Validate against scorecard yardage
        if self.hole_yardage and distances["tee_to_green_center"]:
            is_valid, diff_pct = validate_yardage_difference(
                distances["tee_to_green_center"],
                self.hole_yardage
            )
            if not is_valid:
                self._set_status(f"⚠️ Map distance differs from scorecard by {diff_pct}%")
    
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
        # Load new hole
        self.hole_num = new_hole
        self.hole_par = self._get_hole_par()
        self.hole_yardage = self._get_hole_yardage()
        
        # Load features
        self.features = self.yardbook_mgr.get_hole_features(self.course_name, new_hole)
        
        # Update UI
        self.hole_label.config(text=f"Hole {self.hole_num} - Par {self.hole_par}")
        self.window.title(f"yardbook - {self.course_name} - Hole {self.hole_num}")
        
        # Clear and re-render map
        self._clear_map_objects()
        self._render_all_features()
        self._update_distances_panel()
        
        # Center map on the new hole
        self._center_on_hole()
        
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
    
    def _center_on_hole(self):
        """
        Center the map on the hole, showing from tee to green.
        
        Improved zoom calculation for better close-up views.
        Note: tkintermapview doesn't support rotation, but we optimize
        the view to show the full hole layout.
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
            
            # Improved zoom calculation - closer views for golf holes
            # Zoom levels: higher = closer
            # Typical hole lengths:
            # - Par 3: 100-220 yards
            # - Par 4: 300-450 yards  
            # - Par 5: 450-600 yards
            if hole_length < 150:
                zoom = 20  # Very short par 3
            elif hole_length < 200:
                zoom = 19  # Short par 3
            elif hole_length < 280:
                zoom = 19  # Long par 3 / very short par 4
            elif hole_length < 350:
                zoom = 18  # Short par 4
            elif hole_length < 430:
                zoom = 18  # Medium par 4
            elif hole_length < 500:
                zoom = 17  # Long par 4 / short par 5
            elif hole_length < 550:
                zoom = 17  # Medium par 5
            else:
                zoom = 16  # Long par 5
            
            self.map_widget.set_position(center_lat, center_lon)
            self.map_widget.set_zoom(zoom)
            
        elif self.features.tee.is_set() and self.features.green_front.is_set():
            # Fall back to tee and green front
            tee_lat, tee_lon = self.features.tee.lat, self.features.tee.lon
            gf_lat, gf_lon = self.features.green_front.lat, self.features.green_front.lon
            
            center_lat, center_lon = midpoint(tee_lat, tee_lon, gf_lat, gf_lon)
            hole_length = haversine_distance(tee_lat, tee_lon, gf_lat, gf_lon)
            
            # Same improved zoom calculation
            if hole_length < 150:
                zoom = 20
            elif hole_length < 200:
                zoom = 19
            elif hole_length < 280:
                zoom = 19
            elif hole_length < 350:
                zoom = 18
            elif hole_length < 430:
                zoom = 18
            elif hole_length < 500:
                zoom = 17
            elif hole_length < 550:
                zoom = 17
            else:
                zoom = 16
            
            self.map_widget.set_position(center_lat, center_lon)
            self.map_widget.set_zoom(zoom)
            
        elif self.features.tee.is_set():
            # Just tee - zoom in close
            self.map_widget.set_position(self.features.tee.lat, self.features.tee.lon)
            self.map_widget.set_zoom(19)  # Closer view
            
        elif self.features.green_front.is_set():
            # Just green - zoom in close
            self.map_widget.set_position(self.features.green_front.lat, self.features.green_front.lon)
            self.map_widget.set_zoom(19)  # Closer view
        else:
            # No data - use course location if available, else default
            # Try to get approximate course location from course data
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
    
    # === OSM Import Methods ===
    
    def _import_osm_features(self):
        """Import golf course features from OpenStreetMap."""
        if not is_osm_available():
            messagebox.showinfo(
                "OSM Import Unavailable",
                "OSM import requires the 'requests' library.\n\n"
                "Install with:\n  pip install requests\n\n"
                "Then restart the application."
            )
            return
        
        # Get center coordinates for the search
        center_lat, center_lon = self._get_map_center()
        if center_lat is None:
            messagebox.showwarning(
                "No Location",
                "Please navigate to the hole location first.\n"
                "Place a tee marker or center the map on the hole."
            )
            return
        
        # Show progress
        self.status_label.config(text="Fetching OSM data...")
        self.window.update()
        
        # Import features
        features, error = import_osm_features(
            center_lat=center_lat,
            center_lon=center_lon,
            radius_meters=500  # Search 500m radius around center
        )
        
        if error:
            self.status_label.config(text="OSM import failed")
            messagebox.showerror("OSM Import Error", error)
            return
        
        # Get stats
        stats = get_osm_feature_stats(features)
        
        if not stats:
            self.status_label.config(text="No features found")
            messagebox.showinfo(
                "No Features Found",
                "No golf features found in OpenStreetMap for this area.\n\n"
                "This course may not be mapped in OSM.\n"
                "You can manually draw polygons or try the SAM auto-trace feature."
            )
            return
        
        # Ask user to confirm import
        stats_text = "\n".join([f"  • {k.title()}: {v}" for k, v in stats.items()])
        if not messagebox.askyesno(
            "Import OSM Features",
            f"Found the following features:\n{stats_text}\n\n"
            "Import these features?\n"
            "(Existing polygons will be replaced)"
        ):
            self.status_label.config(text="Import cancelled")
            return
        
        # Add features to the map
        imported_count = 0
        for feature_type, polygons in features.items():
            if not polygons:
                continue
            
            for poly_data in polygons:
                vertices = poly_data.get("vertices", [])
                if len(vertices) >= 3:
                    # Convert to internal polygon format
                    polygon = Polygon()
                    for v in vertices:
                        polygon.add_vertex(v["lat"], v["lon"])
                    
                    # Add to features (first polygon of each type, or add as new)
                    if feature_type in self.features.polygons:
                        # For simplicity, replace the first polygon of this type
                        self.features.polygons[feature_type] = polygon
                        imported_count += 1
                        break  # Only import first polygon of each type
        
        # Render the imported features
        self._render_all_features()
        self.unsaved_changes = True
        
        self.status_label.config(text=f"Imported {imported_count} features from OSM")
        messagebox.showinfo(
            "Import Complete",
            f"Imported {imported_count} features from OpenStreetMap.\n\n"
            "Don't forget to save your changes!"
        )
    
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
    
    # === SAM Auto-Trace Methods ===
    
    def _start_sam_autotrace(self):
        """Start SAM-assisted auto-tracing mode."""
        # Check if we have a map
        if not self.map_widget:
            messagebox.showwarning(
                "No Map",
                "The map widget is not available.\n"
                "Auto-trace requires a visible map."
            )
            return
        
        # Check SAM availability
        sam_available = is_sam_available()
        
        if sam_available:
            # Full SAM mode
            result = messagebox.askyesno(
                "SAM Auto-Trace",
                "SAM Auto-Trace Mode\n\n"
                "Click inside a feature (fairway, green, bunker, water) "
                "and SAM will automatically trace its boundary.\n\n"
                "After tracing, you can:\n"
                "• Accept the polygon\n"
                "• Adjust vertices manually\n"
                "• Try again with a different click point\n\n"
                "Start SAM tracing mode?"
            )
        else:
            # Offer simpler color-based segmentation
            result = messagebox.askyesno(
                "Auto-Trace (Simple Mode)",
                "SAM is not installed. Using simple color-based tracing instead.\n\n"
                "This mode works best for:\n"
                "• High-contrast features (water, bunkers)\n"
                "• Well-defined boundaries\n\n"
                "For better results, install SAM:\n"
                "  pip install torch segment-anything\n\n"
                "Start simple tracing mode?"
            )
        
        if not result:
            return
        
        # Enter SAM/auto-trace mode
        self.current_mode = self.MODE_SAM_TRACE
        self.mode_var.set(self.MODE_SAM_TRACE)
        
        # Show polygon type selector
        self.polygon_frame.pack(fill='x', pady=(0, 10))
        
        self.status_label.config(
            text="Auto-Trace: Click inside a feature to trace it"
        )
        
        # Store SAM availability for click handler
        self._sam_available_for_trace = sam_available
    
    def _handle_sam_trace_click(self, coords):
        """Handle a click in SAM/auto-trace mode."""
        lat, lon = coords
        
        self.status_label.config(text="Tracing... please wait")
        self.window.update()
        
        try:
            if self._sam_available_for_trace:
                # Use SAM for tracing
                polygon_vertices = self._trace_with_sam(lat, lon)
            else:
                # Use simple color-based tracing
                polygon_vertices = self._trace_with_color(lat, lon)
            
            if polygon_vertices and len(polygon_vertices) >= 3:
                # Show the traced polygon for confirmation
                self._preview_traced_polygon(polygon_vertices)
            else:
                messagebox.showinfo(
                    "Trace Failed",
                    "Could not trace a feature at this location.\n\n"
                    "Try clicking:\n"
                    "• More towards the center of the feature\n"
                    "• On a more distinct area\n"
                    "• With higher zoom level"
                )
                self.status_label.config(text="Auto-Trace: Click inside a feature to trace it")
        
        except Exception as e:
            messagebox.showerror("Trace Error", f"Error during tracing: {str(e)}")
            self.status_label.config(text="Auto-Trace: Click inside a feature to trace it")
    
    def _trace_with_sam(self, lat: float, lon: float) -> Optional[List[Dict]]:
        """Trace a feature using SAM."""
        try:
            from sam_autotrace import get_tracer, pixels_to_geo
            
            tracer = get_tracer()
            if not tracer or not tracer.is_model_loaded():
                messagebox.showwarning(
                    "SAM Not Ready",
                    "SAM model is not loaded.\n\n"
                    "Please ensure the model weights are downloaded to:\n"
                    "Data/sam_vit_h_4b8939.pth"
                )
                return None
            
            # Capture map image
            image_data = self._capture_map_image()
            if image_data is None:
                return None
            
            image, bounds, size = image_data
            
            # Set image in SAM
            if not tracer.set_image(image):
                return None
            
            # Convert geo coords to pixel coords
            from sam_autotrace import geo_to_pixels
            pixel_coords = geo_to_pixels([{"lat": lat, "lon": lon}], bounds, size)
            if not pixel_coords:
                return None
            
            click_x, click_y = pixel_coords[0]
            
            # Run SAM segmentation
            result = tracer.segment_point((click_x, click_y))
            if not result:
                return None
            
            # Convert pixel polygon to geo coords
            geo_vertices = pixels_to_geo(result.vertices, bounds, size)
            
            return geo_vertices
            
        except ImportError:
            return None
        except Exception as e:
            print(f"SAM trace error: {e}")
            return None
    
    def _trace_with_color(self, lat: float, lon: float) -> Optional[List[Dict]]:
        """Trace a feature using simple color-based flood fill."""
        try:
            from PIL import Image, ImageGrab
            import colorsys
            
            # Capture map image
            image_data = self._capture_map_image()
            if image_data is None:
                messagebox.showwarning(
                    "Capture Failed",
                    "Could not capture the map image.\n"
                    "This feature requires the map to be visible on screen."
                )
                return None
            
            image, bounds, size = image_data
            
            # Convert to RGB if needed
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            pixels = image.load()
            width, height = image.size
            
            # Convert geo coords to pixel coords
            min_lat, max_lat, min_lon, max_lon = bounds
            
            # Calculate pixel position
            x = int((lon - min_lon) / (max_lon - min_lon) * width)
            y = int((max_lat - lat) / (max_lat - min_lat) * height)
            
            # Ensure within bounds
            x = max(0, min(x, width - 1))
            y = max(0, min(y, height - 1))
            
            # Get seed color
            seed_color = pixels[x, y]
            
            # Perform flood fill to find connected region
            mask = self._flood_fill_mask(image, x, y, seed_color, tolerance=30)
            
            if mask is None:
                return None
            
            # Convert mask to polygon
            polygon_pixels = self._mask_to_polygon_simple(mask)
            
            if not polygon_pixels or len(polygon_pixels) < 3:
                return None
            
            # Convert pixel coords to geo coords
            geo_vertices = []
            for px, py in polygon_pixels:
                geo_lon = min_lon + (px / width) * (max_lon - min_lon)
                geo_lat = max_lat - (py / height) * (max_lat - min_lat)
                geo_vertices.append({"lat": geo_lat, "lon": geo_lon})
            
            return geo_vertices
            
        except Exception as e:
            print(f"Color trace error: {e}")
            return None
    
    def _capture_map_image(self):
        """Capture the current map view as an image."""
        try:
            from PIL import ImageGrab
            
            # Get map widget screen position
            self.map_widget.update_idletasks()
            x = self.map_widget.winfo_rootx()
            y = self.map_widget.winfo_rooty()
            width = self.map_widget.winfo_width()
            height = self.map_widget.winfo_height()
            
            # Capture screen region
            image = ImageGrab.grab(bbox=(x, y, x + width, y + height))
            
            # Get map bounds
            try:
                pos = self.map_widget.get_position()
                zoom = self.map_widget.zoom
                
                # Approximate bounds based on zoom level
                # At zoom 20, roughly 0.0001 degrees per pixel
                deg_per_pixel = 360 / (256 * (2 ** zoom))
                
                half_w = (width / 2) * deg_per_pixel
                half_h = (height / 2) * deg_per_pixel
                
                center_lat, center_lon = pos
                bounds = (
                    center_lat - half_h,  # min_lat
                    center_lat + half_h,  # max_lat
                    center_lon - half_w,  # min_lon
                    center_lon + half_w   # max_lon
                )
            except Exception as e:
                print(f"Could not get map bounds: {e}")
                return None
            
            return (image, bounds, (width, height))
            
        except Exception as e:
            print(f"Map capture error: {e}")
            return None
    
    def _flood_fill_mask(self, image, start_x, start_y, seed_color, tolerance=30):
        """Create a binary mask using flood fill from a seed point."""
        try:
            import numpy as np
            
            img_array = np.array(image)
            height, width = img_array.shape[:2]
            
            # Create mask
            mask = np.zeros((height, width), dtype=np.uint8)
            
            # Convert seed color to numpy array
            seed = np.array(seed_color, dtype=np.float32)
            
            # Stack for flood fill
            stack = [(start_x, start_y)]
            visited = set()
            
            # Limit iterations to prevent infinite loops
            max_iterations = width * height // 4
            iterations = 0
            
            while stack and iterations < max_iterations:
                x, y = stack.pop()
                iterations += 1
                
                if (x, y) in visited:
                    continue
                if x < 0 or x >= width or y < 0 or y >= height:
                    continue
                
                visited.add((x, y))
                
                # Check color similarity
                pixel_color = np.array(img_array[y, x], dtype=np.float32)
                color_diff = np.sqrt(np.sum((pixel_color - seed) ** 2))
                
                if color_diff <= tolerance:
                    mask[y, x] = 255
                    
                    # Add neighbors
                    stack.extend([
                        (x + 1, y), (x - 1, y),
                        (x, y + 1), (x, y - 1)
                    ])
            
            # Check if we found a reasonable region
            filled_pixels = np.sum(mask > 0)
            total_pixels = width * height
            
            if filled_pixels < 100:  # Too small
                return None
            if filled_pixels > total_pixels * 0.5:  # Too large (probably background)
                return None
            
            return mask
            
        except ImportError:
            # Fallback without numpy - simpler but slower
            return self._flood_fill_mask_simple(image, start_x, start_y, seed_color, tolerance)
        except Exception as e:
            print(f"Flood fill error: {e}")
            return None
    
    def _flood_fill_mask_simple(self, image, start_x, start_y, seed_color, tolerance):
        """Simple flood fill without numpy."""
        width, height = image.size
        pixels = image.load()
        
        mask = [[0] * width for _ in range(height)]
        
        def color_distance(c1, c2):
            return sum((a - b) ** 2 for a, b in zip(c1, c2)) ** 0.5
        
        stack = [(start_x, start_y)]
        visited = set()
        max_iterations = 50000
        iterations = 0
        
        while stack and iterations < max_iterations:
            x, y = stack.pop()
            iterations += 1
            
            if (x, y) in visited:
                continue
            if x < 0 or x >= width or y < 0 or y >= height:
                continue
            
            visited.add((x, y))
            
            pixel_color = pixels[x, y]
            if color_distance(pixel_color, seed_color) <= tolerance:
                mask[y][x] = 255
                stack.extend([
                    (x + 1, y), (x - 1, y),
                    (x, y + 1), (x, y - 1)
                ])
        
        return mask
    
    def _mask_to_polygon_simple(self, mask) -> List[Tuple[int, int]]:
        """Convert a binary mask to a polygon outline."""
        try:
            import numpy as np
            
            if isinstance(mask, list):
                mask = np.array(mask, dtype=np.uint8)
            
            # Find contour using simple edge detection
            height, width = mask.shape
            
            # Find boundary pixels
            boundary = []
            for y in range(1, height - 1):
                for x in range(1, width - 1):
                    if mask[y, x] > 0:
                        # Check if on boundary
                        if (mask[y-1, x] == 0 or mask[y+1, x] == 0 or
                            mask[y, x-1] == 0 or mask[y, x+1] == 0):
                            boundary.append((x, y))
            
            if len(boundary) < 3:
                return []
            
            # Simplify boundary to polygon (take every Nth point)
            step = max(1, len(boundary) // 50)  # Limit to ~50 points
            simplified = boundary[::step]
            
            # Sort points to form a proper polygon (by angle from centroid)
            if simplified:
                cx = sum(p[0] for p in simplified) / len(simplified)
                cy = sum(p[1] for p in simplified) / len(simplified)
                
                import math
                simplified.sort(key=lambda p: math.atan2(p[1] - cy, p[0] - cx))
            
            return simplified
            
        except Exception as e:
            print(f"Mask to polygon error: {e}")
            return []
    
    def _preview_traced_polygon(self, vertices: List[Dict]):
        """Show a preview of the traced polygon and let user confirm."""
        # Create temporary polygon on map
        if not self.map_widget or not vertices:
            return
        
        # Draw preview polygon
        coords = [(v["lat"], v["lon"]) for v in vertices]
        
        try:
            preview_path = self.map_widget.set_polygon(
                coords,
                fill_color="yellow",
                outline_color="orange",
                border_width=3
            )
            self._preview_polygon = preview_path
        except:
            self._preview_polygon = None
        
        # Ask user to confirm
        polygon_type = self.polygon_type_var.get()
        
        result = messagebox.askyesnocancel(
            "Confirm Traced Polygon",
            f"Polygon traced with {len(vertices)} vertices.\n\n"
            f"Save as: {polygon_type.title()}\n\n"
            "Yes = Save this polygon\n"
            "No = Discard and try again\n"
            "Cancel = Exit trace mode"
        )
        
        # Remove preview
        if self._preview_polygon:
            try:
                self._preview_polygon.delete()
            except:
                pass
            self._preview_polygon = None
        
        if result is True:
            # Save the polygon
            polygon = Polygon()
            for v in vertices:
                polygon.add_vertex(v["lat"], v["lon"])
            
            self.features.polygons[polygon_type] = polygon
            self._render_polygon(polygon_type)
            self.unsaved_changes = True
            
            self.status_label.config(text=f"Saved {polygon_type} polygon. Click to trace another or change mode.")
            
        elif result is False:
            # Try again
            self.status_label.config(text="Auto-Trace: Click inside a feature to trace it")
            
        else:
            # Cancel - exit trace mode
            self._set_mode(self.MODE_PAN)
            self.polygon_frame.pack_forget()
    
    def _show_greenbook_view(self):
        """Show a static greenbook-style view with distances drawn on the image."""
        if not self.features.has_data():
            messagebox.showinfo("No Data", "Place tee and green markers first to generate a greenbook view.")
            return
        
        # Create a new window for the greenbook view
        greenbook_win = tk.Toplevel(self.window)
        greenbook_win.title(f"Greenbook - {self.course_name} - Hole {self.hole_num}")
        greenbook_win.geometry("800x600")
        
        # Create canvas
        canvas = tk.Canvas(greenbook_win, bg='#228B22', highlightthickness=0)
        canvas.pack(fill='both', expand=True)
        
        # Calculate distances
        map_features_dict = {
            "tee": self.features.tee.to_dict(),
            "green_front": self.features.green_front.to_dict(),
            "green_back": self.features.green_back.to_dict(),
            "targets": [t.to_dict() for t in self.features.targets],
            "hazards": [h.to_dict() for h in self.features.hazards]
        }
        distances = calculate_hole_distances(map_features_dict)
        
        # Wait for window to be drawn to get dimensions
        greenbook_win.update()
        width = canvas.winfo_width()
        height = canvas.winfo_height()
        
        # Draw the hole representation
        self._draw_greenbook_hole(canvas, width, height, distances)
        
        # Add hole info
        info_text = f"Hole {self.hole_num} • Par {self.hole_par}"
        if distances['tee_to_green_center']:
            info_text += f" • {distances['tee_to_green_center']:.0f} yards"
        canvas.create_text(width/2, 30, text=info_text, fill='white', 
                          font=("Helvetica", 18, "bold"))
        
        # Add navigation buttons
        btn_frame = ttk.Frame(greenbook_win)
        btn_frame.pack(side='bottom', pady=10)
        
        def prev_hole_gb():
            greenbook_win.destroy()
            if self._check_unsaved():
                new_hole = self.hole_num - 1
                if new_hole < 1:
                    new_hole = len(self.course_data.get("pars", []))
                self._switch_hole(new_hole)
                self._show_greenbook_view()
        
        def next_hole_gb():
            greenbook_win.destroy()
            if self._check_unsaved():
                new_hole = self.hole_num + 1
                if new_hole > len(self.course_data.get("pars", [])):
                    new_hole = 1
                self._switch_hole(new_hole)
                self._show_greenbook_view()
        
        ttk.Button(btn_frame, text="◀ Prev Hole", command=prev_hole_gb).pack(side='left', padx=10)
        ttk.Button(btn_frame, text="Next Hole ▶", command=next_hole_gb).pack(side='left', padx=10)
        ttk.Button(btn_frame, text="Close", command=greenbook_win.destroy).pack(side='left', padx=10)
    
    def _draw_greenbook_hole(self, canvas, width: int, height: int, distances: Dict):
        """Draw a schematic representation of the hole on the canvas."""
        margin = 60
        usable_height = height - margin * 2 - 60  # Extra for buttons
        usable_width = width - margin * 2
        
        # Calculate scale - hole runs from bottom (tee) to top (green)
        hole_length = distances.get('tee_to_green_center', 400) or 400
        scale = usable_height / hole_length
        
        # Tee position (bottom center)
        tee_x = width / 2
        tee_y = height - margin - 30
        
        # Green position (top center)
        green_y = margin + 30
        
        # Draw fairway (simple rectangle for now)
        fairway_width = 80
        canvas.create_polygon(
            tee_x - fairway_width/2, tee_y,
            tee_x - fairway_width/2 - 20, green_y + 40,
            tee_x + fairway_width/2 + 20, green_y + 40,
            tee_x + fairway_width/2, tee_y,
            fill='#90EE90', outline='#228B22', width=2
        )
        
        # Draw green (oval)
        green_width = 60
        green_height = 40
        canvas.create_oval(
            tee_x - green_width/2, green_y - green_height/2,
            tee_x + green_width/2, green_y + green_height/2,
            fill='#006400', outline='#004000', width=2
        )
        
        # Draw tee box
        tee_width = 30
        tee_height = 15
        canvas.create_rectangle(
            tee_x - tee_width/2, tee_y - tee_height/2,
            tee_x + tee_width/2, tee_y + tee_height/2,
            fill='#8B4513', outline='#654321', width=2
        )
        
        # Draw distance labels
        # Tee to Green Front
        if distances.get('tee_to_green_front'):
            front_y = green_y + green_height/2 + 5
            canvas.create_text(tee_x + 80, front_y, 
                             text=f"{distances['tee_to_green_front']:.0f}",
                             fill='white', font=("Helvetica", 14, "bold"))
            canvas.create_text(tee_x + 80, front_y + 15,
                             text="FRONT", fill='#aaa', font=("Helvetica", 10))
        
        # Tee to Green Center  
        if distances.get('tee_to_green_center'):
            canvas.create_text(tee_x - 80, green_y,
                             text=f"{distances['tee_to_green_center']:.0f}",
                             fill='yellow', font=("Helvetica", 16, "bold"))
            canvas.create_text(tee_x - 80, green_y + 18,
                             text="CENTER", fill='#aaa', font=("Helvetica", 10))
        
        # Tee to Green Back
        if distances.get('tee_to_green_back'):
            back_y = green_y - green_height/2 - 5
            canvas.create_text(tee_x + 80, back_y,
                             text=f"{distances['tee_to_green_back']:.0f}",
                             fill='white', font=("Helvetica", 14, "bold"))
            canvas.create_text(tee_x + 80, back_y - 15,
                             text="BACK", fill='#aaa', font=("Helvetica", 10))
        
        # Green Depth
        if distances.get('green_depth'):
            canvas.create_text(tee_x, green_y - green_height/2 - 25,
                             text=f"Depth: {distances['green_depth']:.0f}y",
                             fill='#ccc', font=("Helvetica", 11))
        
        # Draw targets
        for i, target in enumerate(distances.get('targets', [])):
            if target.get('from_tee'):
                # Position target on the fairway
                target_y = tee_y - (target['from_tee'] * scale)
                
                # Draw target marker
                canvas.create_oval(
                    tee_x - 8, target_y - 8,
                    tee_x + 8, target_y + 8,
                    fill='yellow', outline='orange', width=2
                )
                
                # Draw distance to tee
                canvas.create_text(tee_x + 50, target_y,
                                 text=f"{target['from_tee']:.0f}y",
                                 fill='yellow', font=("Helvetica", 12, "bold"))
                
                # Draw distance to green
                if target.get('to_green'):
                    canvas.create_text(tee_x - 50, target_y,
                                     text=f"→{target['to_green']:.0f}y",
                                     fill='#90EE90', font=("Helvetica", 11))
        
        # Draw hazards
        for i, hazard in enumerate(distances.get('hazards', [])):
            if hazard.get('from_tee'):
                hazard_y = tee_y - (hazard['from_tee'] * scale)
                
                # Color based on type
                hazard_type = hazard.get('type', 'water')
                if hazard_type == 'water':
                    color = '#1E90FF'
                elif hazard_type == 'bunker':
                    color = '#F4E4C1'
                else:
                    color = '#8B4513'
                
                # Draw hazard marker (offset to side)
                offset = 60 if i % 2 == 0 else -60
                canvas.create_oval(
                    tee_x + offset - 10, hazard_y - 10,
                    tee_x + offset + 10, hazard_y + 10,
                    fill=color, outline='red', width=1
                )
                
                canvas.create_text(tee_x + offset, hazard_y + 20,
                                 text=f"{hazard['from_tee']:.0f}y",
                                 fill='red', font=("Helvetica", 10))


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