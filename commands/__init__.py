"""
dt-sim commands module - Command Processing
"""

# Import all command handlers
from .dtc_command import execute as execute_dtc

# If there are other commands, they can be added here
# from .overlay_command import execute as execute_overlay
# from .fdtoverlay_command import execute as execute_fdtoverlay

__all__ = ['execute_dtc']
