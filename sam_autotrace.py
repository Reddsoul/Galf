"""
SAM Auto-Trace Module for Golf App.
Provides segment-anything-based auto-tracing of golf course features from images.

This module gracefully degrades if SAM dependencies are not available.

Dependencies:
- torch
- segment-anything
- numpy
- PIL (Pillow)
- opencv-python (cv2)
"""

import os
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

# Runtime capability detection
_sam_available = False
_sam_error = None

try:
    import numpy as np
    from PIL import Image
    _numpy_available = True
except ImportError as e:
    _numpy_available = False
    _sam_error = f"NumPy/PIL not available: {e}"

try:
    import cv2
    _cv2_available = True
except ImportError:
    _cv2_available = False
    if not _sam_error:
        _sam_error = "OpenCV (cv2) not available. Install with: pip install opencv-python"

try:
    import torch
    from segment_anything import sam_model_registry, SamPredictor
    _sam_available = True
except ImportError as e:
    if not _sam_error:
        _sam_error = f"SAM dependencies not available: {e}"


# SAM model configuration
SAM_MODEL_TYPE = "vit_h"  # Options: vit_h, vit_l, vit_b
SAM_CHECKPOINT_PATH = "Data/sam_vit_h_4b8939.pth"  # Default location for model weights


@dataclass
class TracedPolygon:
    """Represents a traced polygon from SAM segmentation."""
    vertices: List[Tuple[float, float]]  # List of (x, y) pixel coordinates
    confidence: float
    area: int
    bbox: Tuple[int, int, int, int]  # x, y, width, height


def is_sam_available() -> bool:
    """Check if SAM auto-trace feature is available."""
    return _sam_available and _numpy_available and _cv2_available


def get_sam_unavailable_message() -> str:
    """Get a user-friendly message about missing SAM dependencies."""
    if _sam_available and _numpy_available and _cv2_available:
        return ""
    
    msg = "SAM Auto-Trace requires additional dependencies.\n\n"
    msg += "To enable this feature, install:\n"
    msg += "  pip install torch torchvision\n"
    msg += "  pip install segment-anything\n"
    msg += "  pip install opencv-python\n"
    msg += "  pip install numpy pillow\n\n"
    msg += "Then download the SAM model weights (~2.5GB):\n"
    msg += "  https://github.com/facebookresearch/segment-anything\n\n"
    
    if _sam_error:
        msg += f"Current error: {_sam_error}"
    
    return msg


class SAMTracer:
    """
    SAM-based auto-tracing for golf course features.
    Wraps the Segment Anything Model for use with map tile images.
    """
    
    def __init__(self, checkpoint_path: Optional[str] = None, device: str = "auto"):
        """
        Initialize the SAM tracer.
        
        Args:
            checkpoint_path: Path to SAM model weights file
            device: Device to run on ("auto", "cuda", "cpu")
        """
        if not is_sam_available():
            raise RuntimeError(get_sam_unavailable_message())
        
        self.checkpoint_path = checkpoint_path or SAM_CHECKPOINT_PATH
        
        # Determine device
        if device == "auto":
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device
        
        self.sam = None
        self.predictor = None
        self._image_set = False
        self._current_image = None
    
    def load_model(self) -> bool:
        """
        Load the SAM model.
        
        Returns:
            True if successful, False otherwise
        """
        if not os.path.exists(self.checkpoint_path):
            return False
        
        try:
            self.sam = sam_model_registry[SAM_MODEL_TYPE](checkpoint=self.checkpoint_path)
            self.sam.to(device=self.device)
            self.predictor = SamPredictor(self.sam)
            return True
        except Exception as e:
            print(f"Failed to load SAM model: {e}")
            return False
    
    def is_model_loaded(self) -> bool:
        """Check if the SAM model is loaded."""
        return self.predictor is not None
    
    def set_image(self, image: Any) -> bool:
        """
        Set the image for segmentation.
        
        Args:
            image: PIL Image, numpy array, or path to image file
        
        Returns:
            True if successful
        """
        if not self.is_model_loaded():
            return False
        
        try:
            # Convert to numpy array if needed
            if isinstance(image, str):
                image = np.array(Image.open(image))
            elif hasattr(image, 'convert'):  # PIL Image
                image = np.array(image.convert('RGB'))
            
            self._current_image = image
            self.predictor.set_image(image)
            self._image_set = True
            return True
        except Exception as e:
            print(f"Failed to set image: {e}")
            return False
    
    def segment_point(
        self, 
        point: Tuple[int, int],
        point_label: int = 1
    ) -> Optional[TracedPolygon]:
        """
        Segment a region containing the given point.
        
        Args:
            point: (x, y) pixel coordinates of the point prompt
            point_label: 1 for foreground, 0 for background
        
        Returns:
            TracedPolygon or None if segmentation failed
        """
        if not self._image_set:
            return None
        
        try:
            input_point = np.array([[point[0], point[1]]])
            input_label = np.array([point_label])
            
            masks, scores, _ = self.predictor.predict(
                point_coords=input_point,
                point_labels=input_label,
                multimask_output=True
            )
            
            # Get best mask
            best_idx = np.argmax(scores)
            mask = masks[best_idx]
            score = float(scores[best_idx])
            
            # Convert mask to polygon
            polygon = mask_to_polygon(mask)
            
            if polygon is None:
                return None
            
            return TracedPolygon(
                vertices=polygon,
                confidence=score,
                area=int(np.sum(mask)),
                bbox=get_mask_bbox(mask)
            )
        except Exception as e:
            print(f"Segmentation failed: {e}")
            return None
    
    def segment_box(
        self, 
        box: Tuple[int, int, int, int]
    ) -> Optional[TracedPolygon]:
        """
        Segment a region within the given bounding box.
        
        Args:
            box: (x1, y1, x2, y2) bounding box coordinates
        
        Returns:
            TracedPolygon or None if segmentation failed
        """
        if not self._image_set:
            return None
        
        try:
            input_box = np.array([box])
            
            masks, scores, _ = self.predictor.predict(
                box=input_box,
                multimask_output=True
            )
            
            best_idx = np.argmax(scores)
            mask = masks[best_idx]
            score = float(scores[best_idx])
            
            polygon = mask_to_polygon(mask)
            
            if polygon is None:
                return None
            
            return TracedPolygon(
                vertices=polygon,
                confidence=score,
                area=int(np.sum(mask)),
                bbox=get_mask_bbox(mask)
            )
        except Exception as e:
            print(f"Box segmentation failed: {e}")
            return None
    
    def clear(self):
        """Clear the current image state."""
        self._image_set = False
        self._current_image = None


def mask_to_polygon(
    mask: 'np.ndarray', 
    simplify_tolerance: float = 2.0
) -> Optional[List[Tuple[float, float]]]:
    """
    Convert a binary mask to a polygon outline.
    
    Args:
        mask: Binary mask array (H, W) where True = foreground
        simplify_tolerance: Tolerance for polygon simplification (higher = fewer points)
    
    Returns:
        List of (x, y) vertices or None if conversion failed
    """
    if not _cv2_available:
        return None
    
    try:
        # Ensure mask is uint8
        mask_uint8 = (mask.astype(np.uint8) * 255)
        
        # Find contours
        contours, _ = cv2.findContours(
            mask_uint8, 
            cv2.RETR_EXTERNAL, 
            cv2.CHAIN_APPROX_SIMPLE
        )
        
        if not contours:
            return None
        
        # Get largest contour
        largest = max(contours, key=cv2.contourArea)
        
        # Simplify using Douglas-Peucker
        epsilon = simplify_tolerance
        simplified = cv2.approxPolyDP(largest, epsilon, True)
        
        # Convert to list of (x, y) tuples
        vertices = [(float(pt[0][0]), float(pt[0][1])) for pt in simplified]
        
        if len(vertices) < 3:
            return None
        
        return vertices
    except Exception as e:
        print(f"Mask to polygon conversion failed: {e}")
        return None


def get_mask_bbox(mask: 'np.ndarray') -> Tuple[int, int, int, int]:
    """
    Get bounding box of a mask.
    
    Returns:
        (x, y, width, height)
    """
    rows = np.any(mask, axis=1)
    cols = np.any(mask, axis=0)
    
    if not np.any(rows) or not np.any(cols):
        return (0, 0, 0, 0)
    
    y_min, y_max = np.where(rows)[0][[0, -1]]
    x_min, x_max = np.where(cols)[0][[0, -1]]
    
    return (int(x_min), int(y_min), int(x_max - x_min), int(y_max - y_min))


def pixels_to_geo(
    pixel_coords: List[Tuple[float, float]],
    image_bounds: Tuple[float, float, float, float],
    image_size: Tuple[int, int]
) -> List[Dict[str, float]]:
    """
    Convert pixel coordinates to geographic coordinates.
    
    Args:
        pixel_coords: List of (x, y) pixel coordinates
        image_bounds: (min_lat, max_lat, min_lon, max_lon) of the image extent
        image_size: (width, height) of the image in pixels
    
    Returns:
        List of {lat, lon} dicts
    """
    min_lat, max_lat, min_lon, max_lon = image_bounds
    width, height = image_size
    
    lat_range = max_lat - min_lat
    lon_range = max_lon - min_lon
    
    geo_coords = []
    for x, y in pixel_coords:
        # Convert pixel to normalized (0-1)
        norm_x = x / width
        norm_y = y / height
        
        # Convert to geographic
        lon = min_lon + (norm_x * lon_range)
        lat = max_lat - (norm_y * lat_range)  # Y is inverted
        
        geo_coords.append({"lat": lat, "lon": lon})
    
    return geo_coords


def geo_to_pixels(
    geo_coords: List[Dict[str, float]],
    image_bounds: Tuple[float, float, float, float],
    image_size: Tuple[int, int]
) -> List[Tuple[int, int]]:
    """
    Convert geographic coordinates to pixel coordinates.
    
    Args:
        geo_coords: List of {lat, lon} dicts
        image_bounds: (min_lat, max_lat, min_lon, max_lon)
        image_size: (width, height)
    
    Returns:
        List of (x, y) pixel coordinate tuples
    """
    min_lat, max_lat, min_lon, max_lon = image_bounds
    width, height = image_size
    
    lat_range = max_lat - min_lat
    lon_range = max_lon - min_lon
    
    pixel_coords = []
    for coord in geo_coords:
        lat, lon = coord["lat"], coord["lon"]
        
        norm_x = (lon - min_lon) / lon_range
        norm_y = (max_lat - lat) / lat_range
        
        x = int(norm_x * width)
        y = int(norm_y * height)
        
        pixel_coords.append((x, y))
    
    return pixel_coords


def simplify_polygon_rdp(
    vertices: List[Tuple[float, float]], 
    tolerance: float = 1.0
) -> List[Tuple[float, float]]:
    """
    Simplify polygon using Ramer-Douglas-Peucker algorithm.
    
    Pure Python implementation for when cv2 is not available.
    
    Args:
        vertices: List of (x, y) coordinates
        tolerance: Distance tolerance
    
    Returns:
        Simplified list of vertices
    """
    if len(vertices) <= 3:
        return vertices
    
    def perpendicular_distance(point, line_start, line_end):
        """Calculate perpendicular distance from point to line."""
        dx = line_end[0] - line_start[0]
        dy = line_end[1] - line_start[1]
        
        if dx == 0 and dy == 0:
            return ((point[0] - line_start[0])**2 + (point[1] - line_start[1])**2)**0.5
        
        t = max(0, min(1, 
            ((point[0] - line_start[0]) * dx + (point[1] - line_start[1]) * dy) / 
            (dx * dx + dy * dy)))
        
        proj_x = line_start[0] + t * dx
        proj_y = line_start[1] + t * dy
        
        return ((point[0] - proj_x)**2 + (point[1] - proj_y)**2)**0.5
    
    def rdp_recursive(points, start, end):
        if end - start < 2:
            return []
        
        max_dist = 0
        max_idx = start
        
        for i in range(start + 1, end):
            dist = perpendicular_distance(points[i], points[start], points[end])
            if dist > max_dist:
                max_dist = dist
                max_idx = i
        
        if max_dist > tolerance:
            left = rdp_recursive(points, start, max_idx)
            right = rdp_recursive(points, max_idx, end)
            return left + [max_idx] + right
        
        return []
    
    keep_indices = [0] + rdp_recursive(vertices, 0, len(vertices) - 1) + [len(vertices) - 1]
    keep_indices = sorted(set(keep_indices))
    
    return [vertices[i] for i in keep_indices]


def extract_map_tile_image(
    map_widget: Any,
    bounds: Optional[Tuple[float, float, float, float]] = None
) -> Optional[Tuple[Any, Tuple[float, float, float, float], Tuple[int, int]]]:
    """
    Extract the current visible map tile as an image.
    
    This function attempts to capture the map widget's current display.
    
    Args:
        map_widget: The tkintermapview TkinterMapView widget
        bounds: Optional explicit bounds (min_lat, max_lat, min_lon, max_lon)
    
    Returns:
        Tuple of (PIL Image, bounds, size) or None if extraction failed
    
    Note: This requires access to the map widget's internal state.
    """
    try:
        from PIL import ImageGrab
        
        # Get widget position on screen
        x = map_widget.winfo_rootx()
        y = map_widget.winfo_rooty()
        width = map_widget.winfo_width()
        height = map_widget.winfo_height()
        
        # Capture screen region
        image = ImageGrab.grab(bbox=(x, y, x + width, y + height))
        
        # Get map bounds
        if bounds is None:
            # Try to get bounds from map widget
            try:
                # Get current view bounds
                pos = map_widget.get_position()  # center lat, lon
                zoom = map_widget.zoom
                
                # Approximate bounds based on zoom level
                # This is a rough calculation - actual bounds depend on tile provider
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
            except:
                return None
        
        return (image, bounds, (width, height))
    except Exception as e:
        print(f"Map tile extraction failed: {e}")
        return None


# Singleton tracer instance (lazily initialized)
_global_tracer = None


def get_tracer(checkpoint_path: Optional[str] = None) -> Optional[SAMTracer]:
    """
    Get or create the global SAM tracer instance.
    
    Args:
        checkpoint_path: Optional path to SAM model weights
    
    Returns:
        SAMTracer instance or None if SAM is not available
    """
    global _global_tracer
    
    if not is_sam_available():
        return None
    
    if _global_tracer is None:
        _global_tracer = SAMTracer(checkpoint_path)
        if not _global_tracer.load_model():
            _global_tracer = None
    
    return _global_tracer