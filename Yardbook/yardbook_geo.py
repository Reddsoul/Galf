"""
Geodesic distance calculations for the Golf yardbook feature.
Uses the Haversine formula for accurate yardage calculations.
All distances returned in yards.
"""

import math
from typing import Tuple, List, Dict


# Constants
EARTH_RADIUS_METERS = 6_371_000  # Mean Earth radius in meters
METERS_TO_YARDS = 1.09361


def haversine_distance(
    lat1: float, lon1: float, 
    lat2: float, lon2: float
) -> float:
    """
    Calculate the great-circle distance between two points on Earth.
    
    Args:
        lat1, lon1: Latitude and longitude of point 1 (decimal degrees)
        lat2, lon2: Latitude and longitude of point 2 (decimal degrees)
    
    Returns:
        Distance in yards
    """
    # Convert to radians
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    
    # Haversine formula
    a = (math.sin(delta_lat / 2) ** 2 + 
         math.cos(lat1_rad) * math.cos(lat2_rad) * 
         math.sin(delta_lon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    distance_meters = EARTH_RADIUS_METERS * c
    return round(distance_meters * METERS_TO_YARDS, 1)


def bearing(
    lat1: float, lon1: float,
    lat2: float, lon2: float
) -> float:
    """
    Calculate the initial bearing from point 1 to point 2.
    
    Args:
        lat1, lon1: Starting point coordinates (decimal degrees)
        lat2, lon2: Ending point coordinates (decimal degrees)
    
    Returns:
        Bearing in degrees (0-360, where 0/360 is North)
    """
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lon = math.radians(lon2 - lon1)
    
    x = math.sin(delta_lon) * math.cos(lat2_rad)
    y = (math.cos(lat1_rad) * math.sin(lat2_rad) - 
         math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(delta_lon))
    
    bearing_rad = math.atan2(x, y)
    bearing_deg = math.degrees(bearing_rad)
    
    # Normalize to 0-360
    return (bearing_deg + 360) % 360


def destination_point(
    lat: float, lon: float,
    bearing_deg: float, distance_yards: float
) -> Tuple[float, float]:
    """
    Calculate the destination point given start point, bearing, and distance.
    
    Args:
        lat, lon: Starting point coordinates (decimal degrees)
        bearing_deg: Bearing in degrees (0-360)
        distance_yards: Distance in yards
    
    Returns:
        Tuple of (latitude, longitude) of destination point
    """
    distance_meters = distance_yards / METERS_TO_YARDS
    angular_distance = distance_meters / EARTH_RADIUS_METERS
    
    lat_rad = math.radians(lat)
    lon_rad = math.radians(lon)
    bearing_rad = math.radians(bearing_deg)
    
    dest_lat_rad = math.asin(
        math.sin(lat_rad) * math.cos(angular_distance) +
        math.cos(lat_rad) * math.sin(angular_distance) * math.cos(bearing_rad)
    )
    
    dest_lon_rad = lon_rad + math.atan2(
        math.sin(bearing_rad) * math.sin(angular_distance) * math.cos(lat_rad),
        math.cos(angular_distance) - math.sin(lat_rad) * math.sin(dest_lat_rad)
    )
    
    return (math.degrees(dest_lat_rad), math.degrees(dest_lon_rad))


def generate_distance_ring(
    center_lat: float, center_lon: float,
    distance_yards: float,
    num_points: int = 72
) -> List[Tuple[float, float]]:
    """
    Generate points forming a circle at a given distance from center.
    Used for distance rings/arcs on the map.
    
    Args:
        center_lat, center_lon: Center point coordinates
        distance_yards: Radius of the ring in yards
        num_points: Number of points to generate (higher = smoother circle)
    
    Returns:
        List of (lat, lon) tuples forming the circle
    """
    points = []
    for i in range(num_points + 1):  # +1 to close the circle
        angle = (360.0 / num_points) * i
        point = destination_point(center_lat, center_lon, angle, distance_yards)
        points.append(point)
    return points


def generate_arc(
    center_lat: float, center_lon: float,
    distance_yards: float,
    start_bearing: float,
    end_bearing: float,
    num_points: int = 36
) -> List[Tuple[float, float]]:
    """
    Generate an arc segment (partial circle) at a given distance.
    
    Args:
        center_lat, center_lon: Center point coordinates
        distance_yards: Radius in yards
        start_bearing: Starting angle in degrees (0-360)
        end_bearing: Ending angle in degrees (0-360)
        num_points: Number of points in the arc
    
    Returns:
        List of (lat, lon) tuples forming the arc
    """
    points = []
    
    # Handle wrap-around (e.g., 350 to 10 degrees)
    if end_bearing < start_bearing:
        end_bearing += 360
    
    angle_step = (end_bearing - start_bearing) / num_points
    
    for i in range(num_points + 1):
        angle = (start_bearing + angle_step * i) % 360
        point = destination_point(center_lat, center_lon, angle, distance_yards)
        points.append(point)
    
    return points


def midpoint(
    lat1: float, lon1: float,
    lat2: float, lon2: float
) -> Tuple[float, float]:
    """
    Calculate the midpoint between two coordinates.
    
    Returns:
        Tuple of (latitude, longitude) of midpoint
    """
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    lon1_rad = math.radians(lon1)
    delta_lon = math.radians(lon2 - lon1)
    
    bx = math.cos(lat2_rad) * math.cos(delta_lon)
    by = math.cos(lat2_rad) * math.sin(delta_lon)
    
    mid_lat = math.atan2(
        math.sin(lat1_rad) + math.sin(lat2_rad),
        math.sqrt((math.cos(lat1_rad) + bx) ** 2 + by ** 2)
    )
    mid_lon = lon1_rad + math.atan2(by, math.cos(lat1_rad) + bx)
    
    return (math.degrees(mid_lat), math.degrees(mid_lon))


def polygon_centroid(vertices: List[Tuple[float, float]]) -> Tuple[float, float]:
    """
    Calculate the centroid of a polygon.
    Simple average method - accurate enough for small golf course polygons.
    
    Args:
        vertices: List of (lat, lon) tuples
    
    Returns:
        Tuple of (latitude, longitude) of centroid
    """
    if not vertices:
        return (0.0, 0.0)
    
    avg_lat = sum(v[0] for v in vertices) / len(vertices)
    avg_lon = sum(v[1] for v in vertices) / len(vertices)
    return (avg_lat, avg_lon)


def calculate_hole_distances(map_features: Dict) -> Dict:
    """
    Calculate all relevant distances for a hole from its map features.
    
    Args:
        map_features: Dictionary containing tee, green_front, green_back,
                     targets, and hazards data
    
    Returns:
        Dictionary with all calculated distances
    """
    distances = {
        "tee_to_green_front": None,
        "tee_to_green_back": None,
        "tee_to_green_center": None,
        "green_depth": None,
        "targets": [],
        "hazards": []
    }
    
    tee = map_features.get("tee")
    green_front = map_features.get("green_front")
    green_back = map_features.get("green_back")
    
    if not tee:
        return distances
    
    tee_lat, tee_lon = tee.get("lat"), tee.get("lon")
    if tee_lat is None or tee_lon is None:
        return distances
    
    # Tee to Green distances
    if green_front and green_front.get("lat") is not None:
        gf_lat, gf_lon = green_front["lat"], green_front["lon"]
        distances["tee_to_green_front"] = haversine_distance(
            tee_lat, tee_lon, gf_lat, gf_lon
        )
        
        if green_back and green_back.get("lat") is not None:
            gb_lat, gb_lon = green_back["lat"], green_back["lon"]
            distances["tee_to_green_back"] = haversine_distance(
                tee_lat, tee_lon, gb_lat, gb_lon
            )
            distances["green_depth"] = haversine_distance(
                gf_lat, gf_lon, gb_lat, gb_lon
            )
            
            # Green center
            center = midpoint(gf_lat, gf_lon, gb_lat, gb_lon)
            distances["tee_to_green_center"] = haversine_distance(
                tee_lat, tee_lon, center[0], center[1]
            )
    
    # Target distances
    for target in map_features.get("targets", []):
        if target.get("lat") is not None:
            t_lat, t_lon = target["lat"], target["lon"]
            dist_from_tee = haversine_distance(tee_lat, tee_lon, t_lat, t_lon)
            
            # Distance remaining to green (if green front is set)
            dist_to_green = None
            if green_front and green_front.get("lat") is not None:
                dist_to_green = haversine_distance(
                    t_lat, t_lon, 
                    green_front["lat"], green_front["lon"]
                )
            
            distances["targets"].append({
                "name": target.get("name", "Target"),
                "from_tee": dist_from_tee,
                "to_green": dist_to_green
            })
    
    # Hazard distances
    for hazard in map_features.get("hazards", []):
        if hazard.get("lat") is not None:
            h_lat, h_lon = hazard["lat"], hazard["lon"]
            dist_from_tee = haversine_distance(tee_lat, tee_lon, h_lat, h_lon)
            
            distances["hazards"].append({
                "type": hazard.get("type", "hazard"),
                "from_tee": dist_from_tee
            })
    
    return distances


def validate_yardage_difference(
    map_distance: float,
    scorecard_yardage: int,
    tolerance_percent: float = 10.0
) -> Tuple[bool, float]:
    """
    Check if the map-calculated distance differs significantly from scorecard.
    
    Args:
        map_distance: Distance calculated from map coordinates (yards)
        scorecard_yardage: Official scorecard yardage
        tolerance_percent: Acceptable difference percentage
    
    Returns:
        Tuple of (is_within_tolerance, percent_difference)
    """
    if scorecard_yardage == 0:
        return (True, 0.0)
    
    diff = abs(map_distance - scorecard_yardage)
    percent_diff = (diff / scorecard_yardage) * 100
    
    return (percent_diff <= tolerance_percent, round(percent_diff, 1))


# Polygon area calculation (for info display)
def polygon_area_sqyards(vertices: List[Tuple[float, float]]) -> float:
    """
    Calculate approximate area of a polygon in square yards.
    Uses the shoelace formula with geodesic adjustments.
    
    Args:
        vertices: List of (lat, lon) tuples
    
    Returns:
        Area in square yards (approximate)
    """
    if len(vertices) < 3:
        return 0.0
    
    # Convert to a local Cartesian coordinate system centered on centroid
    centroid = polygon_centroid(vertices)
    
    # Convert each vertex to yards from centroid
    local_coords = []
    for v in vertices:
        # X distance (east-west)
        x = haversine_distance(centroid[0], centroid[1], centroid[0], v[1])
        if v[1] < centroid[1]:
            x = -x
        
        # Y distance (north-south)
        y = haversine_distance(centroid[0], centroid[1], v[0], centroid[1])
        if v[0] < centroid[0]:
            y = -y
        
        local_coords.append((x, y))
    
    # Shoelace formula
    n = len(local_coords)
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += local_coords[i][0] * local_coords[j][1]
        area -= local_coords[j][0] * local_coords[i][1]
    
    return abs(area) / 2.0