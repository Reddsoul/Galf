"""
UI Layout Utilities for the Golf App.
Provides consistent window auto-sizing and layout helpers.
"""

import tkinter as tk
from tkinter import ttk
from typing import Tuple, Optional


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
    """
    Auto-size a Toplevel window to fit its content within reasonable bounds.
    
    Args:
        win: The Toplevel window to resize
        pad: (width_padding, height_padding) to add around content
        min_size: (min_width, min_height) minimum window size
        max_ratio: Maximum ratio of screen size (0.0 - 1.0)
        center: Whether to center the window on screen
    
    Usage:
        win = tk.Toplevel(parent)
        # ... add all widgets ...
        autosize_toplevel(win)
    """
    # Force geometry calculations
    win.update_idletasks()
    
    # Get requested size from content
    req_width = win.winfo_reqwidth()
    req_height = win.winfo_reqheight()
    
    # Add padding
    width = req_width + pad[0]
    height = req_height + pad[1]
    
    # Get screen size
    screen_w, screen_h = get_screen_size(win)
    
    # Calculate max dimensions
    max_width = int(screen_w * max_ratio)
    max_height = int(screen_h * max_ratio)
    
    # Clamp to bounds
    width = max(min_size[0], min(width, max_width))
    height = max(min_size[1], min(height, max_height))
    
    # Calculate position for centering
    if center:
        x = (screen_w - width) // 2
        y = (screen_h - height) // 2
        win.geometry(f"{width}x{height}+{x}+{y}")
    else:
        win.geometry(f"{width}x{height}")
    
    # Set minimum size to prevent tiny windows
    win.minsize(min_size[0], min_size[1])


def autosize_root(
    root: tk.Tk,
    pad: Tuple[int, int] = (40, 40),
    min_size: Tuple[int, int] = (400, 500),
    max_ratio: float = 0.85,
    center: bool = True
) -> None:
    """
    Auto-size the root window to fit its content.
    Similar to autosize_toplevel but with defaults suited for main windows.
    """
    autosize_toplevel(root, pad, min_size, max_ratio, center)


def configure_dialog(
    win: tk.Toplevel,
    parent: tk.Misc,
    title: str,
    modal: bool = True,
    min_size: Optional[Tuple[int, int]] = None
) -> None:
    """
    Configure a dialog window with standard settings.
    
    Args:
        win: The Toplevel to configure
        parent: Parent window
        title: Window title
        modal: If True, make the dialog modal (grab focus)
        min_size: Optional minimum size
    """
    win.title(title)
    win.transient(parent)
    
    if modal:
        win.grab_set()
    
    if min_size:
        win.minsize(min_size[0], min_size[1])
    
    # Center relative to parent
    win.update_idletasks()
    
    # Get parent geometry
    parent_x = parent.winfo_rootx()
    parent_y = parent.winfo_rooty()
    parent_w = parent.winfo_width()
    parent_h = parent.winfo_height()
    
    # Get dialog size
    win_w = win.winfo_reqwidth()
    win_h = win.winfo_reqheight()
    
    # Calculate centered position
    x = parent_x + (parent_w - win_w) // 2
    y = parent_y + (parent_h - win_h) // 2
    
    # Ensure on screen
    screen_w, screen_h = get_screen_size(win)
    x = max(0, min(x, screen_w - win_w))
    y = max(0, min(y, screen_h - win_h))
    
    win.geometry(f"+{x}+{y}")


class ScrollableFrame(ttk.Frame):
    """
    A frame that supports scrolling when content exceeds bounds.
    Works with autosize - window grows until max, then scrolls.
    """
    
    def __init__(self, parent, max_height: int = 500, **kwargs):
        """
        Create a scrollable frame.
        
        Args:
            parent: Parent widget
            max_height: Maximum height before scrolling kicks in
        """
        super().__init__(parent, **kwargs)
        
        self.max_height = max_height
        
        # Create canvas and scrollbar
        self.canvas = tk.Canvas(self, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        
        # Create inner frame for content
        self.inner_frame = ttk.Frame(self.canvas)
        
        # Configure canvas scrolling
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        # Create window in canvas
        self.canvas_window = self.canvas.create_window(
            (0, 0), 
            window=self.inner_frame, 
            anchor="nw"
        )
        
        # Pack widgets
        self.scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        
        # Bind events
        self.inner_frame.bind("<Configure>", self._on_frame_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        
        # Bind mousewheel
        self.canvas.bind("<Enter>", self._bind_mousewheel)
        self.canvas.bind("<Leave>", self._unbind_mousewheel)
    
    def _on_frame_configure(self, event):
        """Update scroll region when inner frame size changes."""
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        
        # Adjust canvas height based on content
        content_height = self.inner_frame.winfo_reqheight()
        if content_height <= self.max_height:
            self.canvas.configure(height=content_height)
            self.scrollbar.pack_forget()
        else:
            self.canvas.configure(height=self.max_height)
            self.scrollbar.pack(side="right", fill="y")
    
    def _on_canvas_configure(self, event):
        """Make inner frame fill canvas width."""
        self.canvas.itemconfig(self.canvas_window, width=event.width)
    
    def _bind_mousewheel(self, event):
        """Bind mousewheel when mouse enters."""
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind_all("<Button-4>", self._on_mousewheel_linux)
        self.canvas.bind_all("<Button-5>", self._on_mousewheel_linux)
    
    def _unbind_mousewheel(self, event):
        """Unbind mousewheel when mouse leaves."""
        self.canvas.unbind_all("<MouseWheel>")
        self.canvas.unbind_all("<Button-4>")
        self.canvas.unbind_all("<Button-5>")
    
    def _on_mousewheel(self, event):
        """Handle mousewheel on Windows/Mac."""
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
    
    def _on_mousewheel_linux(self, event):
        """Handle mousewheel on Linux."""
        if event.num == 4:
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self.canvas.yview_scroll(1, "units")


class CollapsibleSection(ttk.Frame):
    """
    A collapsible section widget with toggle button.
    Used for rulebook chapters and other expandable content.
    """
    
    def __init__(
        self, 
        parent, 
        title: str, 
        expanded: bool = False,
        header_style: str = "Header.TLabel",
        **kwargs
    ):
        """
        Create a collapsible section.
        
        Args:
            parent: Parent widget
            title: Section title text
            expanded: Initial state (expanded or collapsed)
            header_style: ttk style for the header label
        """
        super().__init__(parent, **kwargs)
        
        self.title = title
        self._expanded = expanded
        
        # Header frame with toggle button
        self.header_frame = ttk.Frame(self)
        self.header_frame.pack(fill="x")
        
        # Toggle button
        self.toggle_var = tk.StringVar(value="▼" if expanded else "▶")
        self.toggle_btn = ttk.Button(
            self.header_frame,
            textvariable=self.toggle_var,
            width=3,
            command=self.toggle
        )
        self.toggle_btn.pack(side="left", padx=(0, 5))
        
        # Title label (also clickable)
        self.title_label = ttk.Label(
            self.header_frame,
            text=title,
            style=header_style,
            cursor="hand2"
        )
        self.title_label.pack(side="left", fill="x", expand=True)
        self.title_label.bind("<Button-1>", lambda e: self.toggle())
        
        # Content frame
        self.content_frame = ttk.Frame(self)
        if expanded:
            self.content_frame.pack(fill="both", expand=True, pady=(5, 0))
    
    @property
    def content(self) -> ttk.Frame:
        """Get the content frame for adding widgets."""
        return self.content_frame
    
    @property
    def is_expanded(self) -> bool:
        """Check if section is expanded."""
        return self._expanded
    
    def toggle(self):
        """Toggle between expanded and collapsed states."""
        self._expanded = not self._expanded
        
        if self._expanded:
            self.toggle_var.set("▼")
            self.content_frame.pack(fill="both", expand=True, pady=(5, 0))
        else:
            self.toggle_var.set("▶")
            self.content_frame.pack_forget()
    
    def expand(self):
        """Expand the section."""
        if not self._expanded:
            self.toggle()
    
    def collapse(self):
        """Collapse the section."""
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
    """
    Create a label + entry widget pair in a grid.
    
    Returns:
        The Entry widget
    """
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
    """
    Create a row of buttons.
    
    Args:
        parent: Parent frame
        buttons: List of (text, command) tuples
        pack_side: Which side to pack buttons
        padx, pady: Padding
    
    Returns:
        The button frame
    """
    btn_frame = ttk.Frame(parent)
    btn_frame.pack(fill="x", pady=pady)
    
    for text, command in buttons:
        ttk.Button(btn_frame, text=text, command=command).pack(
            side=pack_side, padx=padx
        )
    
    return btn_frame