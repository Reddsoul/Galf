"""
yardbook Data Model and Persistence.
Extends the existing course JSON structure with map_features for each hole.
"""

import json
import os
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class GeoPoint:
    """A geographic point with latitude and longitude."""
    lat: Optional[float] = None
    lon: Optional[float] = None
    
    def is_set(self) -> bool:
        return self.lat is not None and self.lon is not None
    
    def to_dict(self) -> Dict:
        return {"lat": self.lat, "lon": self.lon}
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'GeoPoint':
        if not data:
            return cls()
        return cls(lat=data.get("lat"), lon=data.get("lon"))


@dataclass 
class Target:
    """A target point on the hole (layup, landing zone, etc.)."""
    name: str = "Target"
    lat: Optional[float] = None
    lon: Optional[float] = None
    
    def to_dict(self) -> Dict:
        return {"name": self.name, "lat": self.lat, "lon": self.lon}
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Target':
        return cls(
            name=data.get("name", "Target"),
            lat=data.get("lat"),
            lon=data.get("lon")
        )


@dataclass
class Hazard:
    """A hazard point (water, bunker, OB, etc.)."""
    hazard_type: str = "water"  # water, bunker, ob, native
    lat: Optional[float] = None
    lon: Optional[float] = None
    
    def to_dict(self) -> Dict:
        return {"type": self.hazard_type, "lat": self.lat, "lon": self.lon}
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Hazard':
        return cls(
            hazard_type=data.get("type", "water"),
            lat=data.get("lat"),
            lon=data.get("lon")
        )


@dataclass
class Polygon:
    """A polygon overlay (fairway, green, water, bunker)."""
    vertices: List[Dict] = field(default_factory=list)  # List of {lat, lon}
    
    def add_vertex(self, lat: float, lon: float):
        self.vertices.append({"lat": lat, "lon": lon})
    
    def remove_last_vertex(self):
        if self.vertices:
            self.vertices.pop()
    
    def clear(self):
        self.vertices = []
    
    def is_valid(self) -> bool:
        return len(self.vertices) >= 3
    
    def to_list(self) -> List[Dict]:
        return self.vertices
    
    @classmethod
    def from_list(cls, data: List) -> 'Polygon':
        poly = cls()
        if data:
            poly.vertices = data
        return poly


@dataclass
class HoleMapFeatures:
    """All map features for a single hole."""
    tee: GeoPoint = field(default_factory=GeoPoint)
    green_front: GeoPoint = field(default_factory=GeoPoint)
    green_back: GeoPoint = field(default_factory=GeoPoint)
    targets: List[Target] = field(default_factory=list)
    hazards: List[Hazard] = field(default_factory=list)
    polygons: Dict[str, Polygon] = field(default_factory=dict)
    slope_arrows: List[Dict] = field(default_factory=list)  # Future: green slope indicators
    notes: str = ""
    last_modified: str = ""
    
    def __post_init__(self):
        # Ensure polygons dict has default keys
        default_polygon_types = ["fairway", "green", "water", "bunker", "native"]
        for ptype in default_polygon_types:
            if ptype not in self.polygons:
                self.polygons[ptype] = Polygon()
    
    def to_dict(self) -> Dict:
        return {
            "tee": self.tee.to_dict(),
            "green_front": self.green_front.to_dict(),
            "green_back": self.green_back.to_dict(),
            "targets": [t.to_dict() for t in self.targets],
            "hazards": [h.to_dict() for h in self.hazards],
            "polygons": {k: v.to_list() for k, v in self.polygons.items() if v.is_valid()},
            "slope_arrows": self.slope_arrows,
            "notes": self.notes,
            "last_modified": self.last_modified
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'HoleMapFeatures':
        if not data:
            return cls()
        
        features = cls(
            tee=GeoPoint.from_dict(data.get("tee", {})),
            green_front=GeoPoint.from_dict(data.get("green_front", {})),
            green_back=GeoPoint.from_dict(data.get("green_back", {})),
            notes=data.get("notes", ""),
            last_modified=data.get("last_modified", "")
        )
        
        # Parse targets
        for t_data in data.get("targets", []):
            features.targets.append(Target.from_dict(t_data))
        
        # Parse hazards
        for h_data in data.get("hazards", []):
            features.hazards.append(Hazard.from_dict(h_data))
        
        # Parse polygons
        for ptype, vertices in data.get("polygons", {}).items():
            features.polygons[ptype] = Polygon.from_list(vertices)
        
        # Parse slope arrows
        features.slope_arrows = data.get("slope_arrows", [])
        
        return features
    
    def clear_all(self):
        """Reset all map features."""
        self.tee = GeoPoint()
        self.green_front = GeoPoint()
        self.green_back = GeoPoint()
        self.targets = []
        self.hazards = []
        for poly in self.polygons.values():
            poly.clear()
        self.slope_arrows = []
        self.notes = ""
    
    def has_data(self) -> bool:
        """Check if any map features have been set."""
        if self.tee.is_set() or self.green_front.is_set() or self.green_back.is_set():
            return True
        if self.targets or self.hazards:
            return True
        for poly in self.polygons.values():
            if poly.is_valid():
                return True
        return False


class yardbookManager:
    """
    Manages yardbook data for courses.
    Integrates with existing course JSON structure.
    """
    
    def __init__(self, courses_file: str):
        self.courses_file = courses_file
        self._cache: Dict[str, Dict[int, HoleMapFeatures]] = {}  # course_name -> {hole_num -> features}
    
    def _load_courses(self) -> List[Dict]:
        """Load courses from JSON file."""
        if not os.path.exists(self.courses_file):
            return []
        with open(self.courses_file, 'r') as f:
            return json.load(f)
    
    def _save_courses(self, courses: List[Dict]):
        """Save courses to JSON file."""
        with open(self.courses_file, 'w') as f:
            json.dump(courses, f, indent=2)
    
    def get_hole_features(self, course_name: str, hole_num: int) -> HoleMapFeatures:
        """
        Get map features for a specific hole.
        
        Args:
            course_name: Name of the course
            hole_num: Hole number (1-18)
        
        Returns:
            HoleMapFeatures instance (empty if none exist)
        """
        # Check cache first
        cache_key = course_name
        if cache_key in self._cache and hole_num in self._cache[cache_key]:
            return self._cache[cache_key][hole_num]
        
        # Load from file
        courses = self._load_courses()
        for course in courses:
            if course.get("name") == course_name:
                holes_data = course.get("holes", {})
                hole_key = str(hole_num)
                
                if hole_key in holes_data:
                    hole_data = holes_data[hole_key]
                    map_features_data = hole_data.get("map_features", {})
                    features = HoleMapFeatures.from_dict(map_features_data)
                else:
                    features = HoleMapFeatures()
                
                # Cache it
                if cache_key not in self._cache:
                    self._cache[cache_key] = {}
                self._cache[cache_key][hole_num] = features
                
                return features
        
        return HoleMapFeatures()
    
    def save_hole_features(self, course_name: str, hole_num: int, features: HoleMapFeatures):
        """
        Save map features for a specific hole.
        
        Args:
            course_name: Name of the course
            hole_num: Hole number (1-18)
            features: HoleMapFeatures to save
        """
        features.last_modified = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        courses = self._load_courses()
        
        for course in courses:
            if course.get("name") == course_name:
                # Ensure holes dict exists
                if "holes" not in course:
                    course["holes"] = {}
                
                hole_key = str(hole_num)
                
                # Ensure hole entry exists
                if hole_key not in course["holes"]:
                    course["holes"][hole_key] = {}
                
                # Get existing par if not set
                pars = course.get("pars", [])
                if hole_num <= len(pars):
                    course["holes"][hole_key]["par"] = pars[hole_num - 1]
                
                # Save map features
                course["holes"][hole_key]["map_features"] = features.to_dict()
                
                break
        
        self._save_courses(courses)
        
        # Update cache
        cache_key = course_name
        if cache_key not in self._cache:
            self._cache[cache_key] = {}
        self._cache[cache_key][hole_num] = features
    
    def clear_hole_features(self, course_name: str, hole_num: int):
        """Clear all map features for a hole."""
        features = HoleMapFeatures()
        self.save_hole_features(course_name, hole_num, features)
    
    def get_course_yardbook_summary(self, course_name: str) -> Dict:
        """
        Get summary of yardbook data for a course.
        
        Returns:
            Dict with counts of holes with data, completion status, etc.
        """
        courses = self._load_courses()
        
        for course in courses:
            if course.get("name") == course_name:
                num_holes = len(course.get("pars", []))
                holes_with_data = 0
                holes_complete = 0  # Has tee and green at minimum
                
                holes_data = course.get("holes", {})
                
                for h in range(1, num_holes + 1):
                    hole_key = str(h)
                    if hole_key in holes_data:
                        map_features = holes_data[hole_key].get("map_features", {})
                        if map_features:
                            features = HoleMapFeatures.from_dict(map_features)
                            if features.has_data():
                                holes_with_data += 1
                                if features.tee.is_set() and features.green_front.is_set():
                                    holes_complete += 1
                
                return {
                    "total_holes": num_holes,
                    "holes_with_data": holes_with_data,
                    "holes_complete": holes_complete,
                    "completion_percent": round((holes_complete / num_holes) * 100, 1) if num_holes > 0 else 0
                }
        
        return {"total_holes": 0, "holes_with_data": 0, "holes_complete": 0, "completion_percent": 0}
    
    def invalidate_cache(self, course_name: Optional[str] = None):
        """Clear cached data."""
        if course_name:
            self._cache.pop(course_name, None)
        else:
            self._cache.clear()


# Distance ring presets for the UI
DISTANCE_RING_PRESETS = {
    "driver": {"distance": 250, "color": "#FF6B6B", "label": "Driver"},
    "3_wood": {"distance": 225, "color": "#4ECDC4", "label": "3 Wood"},
    "5_wood": {"distance": 200, "color": "#45B7D1", "label": "5 Wood"},
    "hybrid": {"distance": 180, "color": "#96CEB4", "label": "Hybrid"},
    "5_iron": {"distance": 160, "color": "#FFEAA7", "label": "5 Iron"},
    "7_iron": {"distance": 140, "color": "#DDA0DD", "label": "7 Iron"},
    "9_iron": {"distance": 120, "color": "#98D8C8", "label": "9 Iron"},
    "pw": {"distance": 100, "color": "#F7DC6F", "label": "PW"},
}

# Polygon style presets
POLYGON_STYLES = {
    "fairway": {
        "fill_color": "#90EE90",  # Light green
        "outline_color": "#228B22",
        "fill_opacity": 0.3,
        "label": "Fairway"
    },
    "green": {
        "fill_color": "#006400",  # Dark green
        "outline_color": "#004000",
        "fill_opacity": 0.5,
        "label": "Green"
    },
    "water": {
        "fill_color": "#1E90FF",  # Dodger blue
        "outline_color": "#0000CD",
        "fill_opacity": 0.4,
        "label": "Water"
    },
    "bunker": {
        "fill_color": "#F4E4C1",  # Sand color
        "outline_color": "#C4A961",
        "fill_opacity": 0.5,
        "label": "Bunker"
    },
    "native": {
        "fill_color": "#8B4513",  # Saddle brown
        "outline_color": "#654321",
        "fill_opacity": 0.3,
        "label": "Native/Waste"
    }
}

# Marker style presets
MARKER_STYLES = {
    "tee": {"color": "#FF4444", "label": "T", "size": 12},
    "green_front": {"color": "#44FF44", "label": "F", "size": 10},
    "green_back": {"color": "#44FF44", "label": "B", "size": 10},
    "target": {"color": "#FFFF44", "label": "●", "size": 10},
    "hazard_water": {"color": "#4444FF", "label": "W", "size": 10},
    "hazard_bunker": {"color": "#F4E4C1", "label": "S", "size": 10},
    "hazard_ob": {"color": "#FFFFFF", "label": "OB", "size": 10},
}