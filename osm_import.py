"""
OSM Import Module for Golf App.
Fetches golf course features from OpenStreetMap using Overpass API.

Imports golf-related polygons:
- golf=fairway
- golf=green (putting_green)
- golf=bunker (sand trap)
- golf=tee (tee box)
- natural=water (water hazards)
- golf=water_hazard
- landuse=grass (rough areas near golf courses)
"""

import json
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

# Runtime capability detection for requests
def _check_requests():
    """Check if requests library is available."""
    try:
        import requests
        return True, requests
    except ImportError:
        return False, None

_requests_available, requests = _check_requests()

# Overpass API endpoint
OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Golf-related OSM tags we're interested in
# Each tag is a (key, value) tuple
GOLF_TAGS = {
    "fairway": {"tags": [("golf", "fairway")], "polygon_type": "fairway"},
    "green": {"tags": [("golf", "green"), ("golf", "putting_green")], "polygon_type": "green"},
    "bunker": {"tags": [("golf", "bunker"), ("golf", "sand_trap")], "polygon_type": "bunker"},
    "tee": {"tags": [("golf", "tee")], "polygon_type": "tee"},
    "water": {"tags": [("natural", "water"), ("golf", "water_hazard"), ("water", "pond"), ("water", "lake")], "polygon_type": "water"},
    "rough": {"tags": [("golf", "rough"), ("landuse", "grass")], "polygon_type": "native"},
}


@dataclass
class OSMPolygon:
    """Represents a polygon from OSM data."""
    osm_id: int
    feature_type: str  # fairway, green, bunker, water, etc.
    vertices: List[Dict[str, float]]  # List of {lat, lon}
    name: Optional[str] = None
    tags: Dict[str, str] = None


def is_osm_available() -> bool:
    """Check if OSM import feature is available."""
    return _requests_available


def build_overpass_query(
    center_lat: float,
    center_lon: float,
    radius_meters: int = 500,
    feature_types: Optional[List[str]] = None
) -> str:
    """
    Build an Overpass QL query for golf features around a center point.
    
    Args:
        center_lat: Center latitude
        center_lon: Center longitude
        radius_meters: Search radius in meters (default 500m for a hole)
        feature_types: List of feature types to fetch (default: all)
    
    Returns:
        Overpass QL query string
    """
    if feature_types is None:
        feature_types = list(GOLF_TAGS.keys())
    
    # Build tag filters
    tag_filters = []
    for ftype in feature_types:
        if ftype in GOLF_TAGS:
            for key, value in GOLF_TAGS[ftype]["tags"]:
                tag_filters.append(f'way["{key}"="{value}"](around:{radius_meters},{center_lat},{center_lon});')
                tag_filters.append(f'relation["{key}"="{value}"](around:{radius_meters},{center_lat},{center_lon});')
    
    # Also search for generic golf=* tags
    tag_filters.append(f'way["golf"](around:{radius_meters},{center_lat},{center_lon});')
    
    query = f"""
    [out:json][timeout:30];
    (
        {chr(10).join(tag_filters)}
    );
    out body;
    >;
    out skel qt;
    """
    
    return query


def build_bbox_query(
    min_lat: float,
    min_lon: float,
    max_lat: float,
    max_lon: float,
    feature_types: Optional[List[str]] = None
) -> str:
    """
    Build an Overpass QL query for golf features within a bounding box.
    
    Args:
        min_lat, min_lon: Southwest corner
        max_lat, max_lon: Northeast corner
        feature_types: List of feature types to fetch
    
    Returns:
        Overpass QL query string
    """
    if feature_types is None:
        feature_types = list(GOLF_TAGS.keys())
    
    bbox = f"{min_lat},{min_lon},{max_lat},{max_lon}"
    
    tag_filters = []
    for ftype in feature_types:
        if ftype in GOLF_TAGS:
            for key, value in GOLF_TAGS[ftype]["tags"]:
                tag_filters.append(f'way["{key}"="{value}"]({bbox});')
                tag_filters.append(f'relation["{key}"="{value}"]({bbox});')
    
    # Generic golf tag
    tag_filters.append(f'way["golf"]({bbox});')
    
    query = f"""
    [out:json][timeout:30];
    (
        {chr(10).join(tag_filters)}
    );
    out body;
    >;
    out skel qt;
    """
    
    return query


def fetch_osm_data(query: str) -> Optional[Dict]:
    """
    Execute an Overpass query and return the results.
    
    Args:
        query: Overpass QL query string
    
    Returns:
        JSON response dict or None if failed
    """
    if not _requests_available:
        return None
    
    try:
        response = requests.post(
            OVERPASS_URL,
            data={"data": query},
            timeout=60
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"OSM fetch error: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"OSM JSON parse error: {e}")
        return None


def parse_osm_response(data: Dict) -> List[OSMPolygon]:
    """
    Parse Overpass API response into OSMPolygon objects.
    
    Args:
        data: Raw JSON response from Overpass API
    
    Returns:
        List of OSMPolygon objects
    """
    if not data or "elements" not in data:
        return []
    
    elements = data["elements"]
    
    # Build node lookup
    nodes = {}
    for elem in elements:
        if elem.get("type") == "node":
            nodes[elem["id"]] = (elem["lat"], elem["lon"])
    
    # Process ways into polygons
    polygons = []
    
    for elem in elements:
        if elem.get("type") != "way":
            continue
        
        # Get nodes for this way
        node_refs = elem.get("nodes", [])
        if len(node_refs) < 3:
            continue
        
        # Build vertices
        vertices = []
        for node_id in node_refs:
            if node_id in nodes:
                lat, lon = nodes[node_id]
                vertices.append({"lat": lat, "lon": lon})
        
        if len(vertices) < 3:
            continue
        
        # Determine feature type from tags
        tags = elem.get("tags", {})
        feature_type = determine_feature_type(tags)
        
        if feature_type:
            polygon = OSMPolygon(
                osm_id=elem["id"],
                feature_type=feature_type,
                vertices=vertices,
                name=tags.get("name"),
                tags=tags
            )
            polygons.append(polygon)
    
    return polygons


def determine_feature_type(tags: Dict[str, str]) -> Optional[str]:
    """
    Determine the golf feature type from OSM tags.
    
    Args:
        tags: OSM tag dictionary
    
    Returns:
        Feature type string or None if not a recognized golf feature
    """
    golf_tag = tags.get("golf", "")
    natural_tag = tags.get("natural", "")
    water_tag = tags.get("water", "")
    
    # Direct golf tags
    if golf_tag == "fairway":
        return "fairway"
    elif golf_tag in ("green", "putting_green"):
        return "green"
    elif golf_tag in ("bunker", "sand_trap"):
        return "bunker"
    elif golf_tag == "tee":
        return "tee"
    elif golf_tag == "water_hazard":
        return "water"
    elif golf_tag == "rough":
        return "native"
    
    # Water features
    if natural_tag == "water" or water_tag in ("pond", "lake"):
        return "water"
    
    return None


def convert_to_internal_format(polygons: List[OSMPolygon]) -> Dict[str, List[Dict]]:
    """
    Convert OSMPolygon objects to the internal yardbook polygon format.
    
    Args:
        polygons: List of OSMPolygon objects
    
    Returns:
        Dict mapping polygon type to list of vertex lists
    """
    result = {
        "fairway": [],
        "green": [],
        "bunker": [],
        "water": [],
        "native": [],
        "tee": []
    }
    
    for poly in polygons:
        ptype = poly.feature_type
        if ptype in result:
            result[ptype].append({
                "osm_id": poly.osm_id,
                "vertices": poly.vertices,
                "name": poly.name
            })
    
    return result


def import_osm_features(
    center_lat: float,
    center_lon: float,
    radius_meters: int = 500,
    feature_types: Optional[List[str]] = None
) -> Tuple[Dict[str, List[Dict]], Optional[str]]:
    """
    Import golf course features from OSM for a given location.
    
    This is the main entry point for OSM import.
    
    Args:
        center_lat: Latitude of the hole/area center
        center_lon: Longitude of the hole/area center
        radius_meters: Search radius (default 500m)
        feature_types: List of feature types to import (default: all)
    
    Returns:
        Tuple of (features_dict, error_message)
        features_dict: Dict mapping polygon type to list of polygon data
        error_message: Error string if failed, None if successful
    """
    if not is_osm_available():
        return {}, "OSM import requires the 'requests' library.\nInstall with: pip install requests"
    
    # Build and execute query
    query = build_overpass_query(center_lat, center_lon, radius_meters, feature_types)
    data = fetch_osm_data(query)
    
    if data is None:
        return {}, "Failed to fetch data from OpenStreetMap.\nPlease check your internet connection."
    
    # Parse response
    polygons = parse_osm_response(data)
    
    if not polygons:
        return {}, "No golf features found in this area.\nTry increasing the search radius or use manual polygon drawing."
    
    # Convert to internal format
    features = convert_to_internal_format(polygons)
    
    return features, None


def import_osm_features_bbox(
    min_lat: float,
    min_lon: float,
    max_lat: float,
    max_lon: float,
    feature_types: Optional[List[str]] = None
) -> Tuple[Dict[str, List[Dict]], Optional[str]]:
    """
    Import golf course features from OSM for a bounding box.
    
    Args:
        min_lat, min_lon: Southwest corner
        max_lat, max_lon: Northeast corner
        feature_types: List of feature types to import
    
    Returns:
        Tuple of (features_dict, error_message)
    """
    if not is_osm_available():
        return {}, "OSM import requires the 'requests' library.\nInstall with: pip install requests"
    
    query = build_bbox_query(min_lat, min_lon, max_lat, max_lon, feature_types)
    data = fetch_osm_data(query)
    
    if data is None:
        return {}, "Failed to fetch data from OpenStreetMap."
    
    polygons = parse_osm_response(data)
    
    if not polygons:
        return {}, "No golf features found in this area."
    
    return convert_to_internal_format(polygons), None


def simplify_polygon(vertices: List[Dict], tolerance: float = 0.00001) -> List[Dict]:
    """
    Simplify a polygon using the Ramer-Douglas-Peucker algorithm.
    
    Args:
        vertices: List of {lat, lon} dicts
        tolerance: Distance tolerance in degrees (smaller = more detail)
    
    Returns:
        Simplified list of vertices
    """
    if len(vertices) <= 3:
        return vertices
    
    def point_line_distance(point, line_start, line_end):
        """Calculate perpendicular distance from point to line."""
        if line_start == line_end:
            return ((point['lat'] - line_start['lat'])**2 + 
                    (point['lon'] - line_start['lon'])**2)**0.5
        
        # Line vector
        dx = line_end['lon'] - line_start['lon']
        dy = line_end['lat'] - line_start['lat']
        
        # Normalized projection
        t = max(0, min(1, 
            ((point['lon'] - line_start['lon']) * dx + 
             (point['lat'] - line_start['lat']) * dy) / 
            (dx * dx + dy * dy)))
        
        # Closest point on line
        proj_lon = line_start['lon'] + t * dx
        proj_lat = line_start['lat'] + t * dy
        
        return ((point['lat'] - proj_lat)**2 + (point['lon'] - proj_lon)**2)**0.5
    
    def rdp(points, start, end, tolerance):
        """Recursive Douglas-Peucker."""
        if end - start < 2:
            return []
        
        max_dist = 0
        max_idx = start
        
        for i in range(start + 1, end):
            dist = point_line_distance(points[i], points[start], points[end])
            if dist > max_dist:
                max_dist = dist
                max_idx = i
        
        if max_dist > tolerance:
            left = rdp(points, start, max_idx, tolerance)
            right = rdp(points, max_idx, end, tolerance)
            return left + [max_idx] + right
        
        return []
    
    # Run RDP algorithm
    keep_indices = [0] + rdp(vertices, 0, len(vertices) - 1, tolerance) + [len(vertices) - 1]
    keep_indices = sorted(set(keep_indices))
    
    return [vertices[i] for i in keep_indices]


def get_osm_feature_stats(features: Dict[str, List[Dict]]) -> Dict[str, int]:
    """
    Get statistics about imported OSM features.
    
    Args:
        features: Features dict from import_osm_features
    
    Returns:
        Dict with counts per feature type
    """
    return {ftype: len(polys) for ftype, polys in features.items() if polys}