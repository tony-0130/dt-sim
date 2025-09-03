"""
core/__init__.py - dt-sim Core Data Structures

This module defines the core data structures used in dt-sim:
- DTSProperty: Device tree property
- DTSNode: Device tree node  
- DeviceTree: Main device tree structure

V2 Enhanced structures (for new parser):
- NormalNode, OverrideNode: Enhanced node types
- Property, Value: Enhanced property types  
- DeviceTree: Enhanced device tree structure
"""

from .core import DTSProperty, DTSNode, DeviceTree

# V2 enhanced structures available but not exported by default
# Import from core.core_v2 if needed

__all__ = ['DeviceTree', 'DTSNode', 'DTSProperty']