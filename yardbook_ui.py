"""
yardbook View - Interactive map-based yardage book feature.
Uses tkintermapview for satellite imagery and custom overlays.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional, Dict, List, Tuple, Callable

import tkintermapview

from yardbook_geo import (
    generate_distance_ring,
    midpoint,
    calculate_hole_distances,
    validate_yardage_difference,
)
from yardbook_data import (
    yardbookManager,
    GeoPoint,
    Target,
    Hazard,
    Polygon,
    DISTANCE_RING_PRESETS,
    POLYGON_STYLES,
    MARKER_STYLES
)

MAP_AVAILABLE = True


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
    
    def __init__(
        self, 
        parent: tk.Tk,
        course_data: Dict,
        hole_num: int,
        courses_file: str,
        on_save_callback: Optional[Callable] = None
    ):
        """
        Initialize the yardbook view.
        
        Args:
            parent: Parent Tkinter window
            course_data: Full course dictionary from backend
            hole_num: Which hole to display (1-18)
            courses_file: Path to courses.json
            on_save_callback: Optional callback when data is saved
        """
        self.parent = parent
        self.course_data = course_data
        self.course_name = course_data.get("name", "Unknown")
        self.hole_num = hole_num
        self.courses_file = courses_file
        self.on_save_callback = on_save_callback
        
        # Data management
        self.yardbook_mgr = yardbookManager(courses_file)
        self.features = self.yardbook_mgr.get_hole_features(self.course_name, hole_num)
        
        # UI state
        self.current_mode = self.MODE_PAN
        self.current_polygon_type = "fairway"
        self.current_hazard_type = "water"
        self.temp_polygon_vertices: List[Tuple[float, float]] = []
        self.unsaved_changes = False
        
        # Map objects tracking (for cleanup)
        self.map_markers: Dict[str, any] = {}
        self.map_paths: List[any] = []
        self.map_polygons: Dict[str, any] = {}
        self.distance_rings: List[any] = []
        self.aim_lines: List[any] = []
        
        # Toggle states
        self.show_distance_rings = tk.BooleanVar(value=False)
        self.show_aim_lines = tk.BooleanVar(value=True)
        self.show_polygons = tk.BooleanVar(value=True)
        self.show_distances = tk.BooleanVar(value=True)
        
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
        
        # Center map on course or existing data
        self._initial_map_position()
    
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
        ttk.Button(toolbar, text="💾 Save", command=self._save_features).pack(side='right', padx=5)
        ttk.Button(toolbar, text="🗑 Clear All", command=self._clear_all).pack(side='right', padx=5)
    
    def _create_map(self):
        """Create the map widget."""
        map_frame = ttk.Frame(self.main_frame)
        map_frame.grid(row=1, column=0, sticky='nsew', padx=5, pady=5)
        
        if not MAP_AVAILABLE:
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
        # Note: For production, consider using MapBox or other tile providers
        self.map_widget.set_tile_server(
            "https://mt0.google.com/vt/lyrs=s&hl=en&x={x}&y={y}&z={z}&s=Ga",
            max_zoom=20
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
        
        # Distance Rings Config
        self.rings_frame = ttk.LabelFrame(sidebar, text="Distance Rings", padding=10)
        self.rings_frame.pack(fill='x', pady=(0, 10))
        
        self.ring_vars = {}
        for preset_key, preset in DISTANCE_RING_PRESETS.items():
            var = tk.BooleanVar(value=False)
            self.ring_vars[preset_key] = var
            cb = ttk.Checkbutton(
                self.rings_frame,
                text=f"{preset['label']} ({preset['distance']}y)",
                variable=var,
                command=self._update_distance_rings
            )
            cb.pack(anchor='w')
        
        # Status bar
        self.status_label = ttk.Label(
            sidebar, 
            text="Ready. Select a mode to place markers.",
            font=("Helvetica", 9),
            foreground="gray"
        )
        self.status_label.pack(side='bottom', pady=10)
    
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
        
        for preset_key, var in self.ring_vars.items():
            if var.get():
                preset = DISTANCE_RING_PRESETS[preset_key]
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
        # Save current hole's view position (optional)
        
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
        
        # Reset state
        self.unsaved_changes = False
        self.temp_polygon_vertices = []
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
    
    def _initial_map_position(self):
        """Set initial map position."""
        if not self.map_widget:
            return
        
        # If we have tee data, center on that
        if self.features.tee.is_set():
            self.map_widget.set_position(self.features.tee.lat, self.features.tee.lon)
            self.map_widget.set_zoom(18)
        else:
            # Try to get approximate location from course name (would need geocoding)
            # For now, default to a reasonable position
            # In production, you'd want to geocode the course address
            self.map_widget.set_position(40.0, -74.0)  # Default to generic location
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


def open_yardbook(
    parent: tk.Tk,
    course_data: Dict,
    hole_num: int,
    courses_file: str,
    on_save_callback: Optional[Callable] = None
) -> yardbookView:
    """
    Convenience function to open the yardbook view.
    
    Args:
        parent: Parent Tkinter window
        course_data: Course dictionary from backend
        hole_num: Hole number to display
        courses_file: Path to courses.json
        on_save_callback: Optional callback when data is saved
    
    Returns:
        yardbookView instance
    """
    return yardbookView(
        parent=parent,
        course_data=course_data,
        hole_num=hole_num,
        courses_file=courses_file,
        on_save_callback=on_save_callback
    )