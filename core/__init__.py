"""
core/__init__.py - dt-sim Core Data Structures

This module defines the core data structures used in dt-sim:
- DTSProperty: Device tree property
- DTSNode: Device tree node  
- DeviceTree: Main device tree structure
"""

from .core import DTSProperty, DTSNode, DeviceTree

__all__ = ['DeviceTree', 'DTSNode', 'DTSProperty']