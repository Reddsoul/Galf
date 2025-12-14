"""
Golf Tracker Application - Main Entry Point
"""

import tkinter as tk
from Frontend.Frontend import GolfApp


if __name__ == "__main__":
    root = tk.Tk()
    app = GolfApp(root)
    root.mainloop()