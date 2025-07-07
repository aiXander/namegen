#!/usr/bin/env python3

"""
Simple launcher script for the Markov Name Generator GUI
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from gui.gui import main
    main()
except ImportError as e:
    print(f"Error importing GUI: {e}")
    print("Make sure you have tkinter installed (usually comes with Python)")
    print("If on Linux, you might need to install python3-tk")
except Exception as e:
    print(f"Error running GUI: {e}")
    sys.exit(1)