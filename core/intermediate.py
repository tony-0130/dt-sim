"""
core/intermediate.py - Intermediate Representation for Device Tree Pipeline

Provides an intermediate representation layer between parsing and generation,
following the user's architectural vision for clean separation of concerns.

This IR layer optimizes the AST for generation while maintaining the original
structure integrity needed for accurate DTB text output.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from core.ast import DeviceTree, NormalNode, OverrideNode, Property, Value, ValueType, Reference


class IRNodeType(Enum):
    """Intermediate representation node types"""
    ROOT = "root"
    NORMAL = "normal"
    MERGED = "merged"  # Result of override merging


@dataclass
class IRProperty:
    """Intermediate representation of a device tree property"""
    name: str
    values: List[Value]
    is_boolean: bool = False
    source_info: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_ast_property(cls, prop: Property) -> 'IRProperty':
        """Convert AST Property to IR Property"""
        is_boolean = (not hasattr(prop, 'values') or not prop.values or
                     (len(prop.values) == 1 and prop.values[0].type == ValueType.BOOLEAN))
        
        return cls(
            name=prop.name,
            values=prop.values if hasattr(prop, 'values') and prop.values else [],
            is_boolean=is_boolean,
            source_info={
                'source_file': getattr(prop, 'source_file', ''),
                'line_number': getattr(prop, 'line_number', 0)
            }
        )


@dataclass
class IRNode:
    """Intermediate representation of a device tree node"""
    name: str
    full_name: str  # name@unit_addr format
    node_type: IRNodeType
    label: Optional[str] = None
    unit_addr: Optional[str] = None
    properties: List[IRProperty] = field(default_factory=list)
    children: List['IRNode'] = field(default_factory=list)
    parent: Optional['IRNode'] = None
    depth: int = 0
    source_info: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Calculate full name and set parent relationships"""
        if self.name == "/":
            self.full_name = "/"
        else:
            self.full_name = f"{self.name}@{self.unit_addr}" if self.unit_addr else self.name
        
        # Set parent relationships
        for child in self.children:
            child.parent = self
            child.depth = self.depth + 1
    
    def add_child(self, child: 'IRNode'):
        """Add child node and set parent relationship"""
        self.children.append(child)
        child.parent = self
        child.depth = self.depth + 1
    
    def add_property(self, prop: IRProperty):
        """Add or replace property"""
        # Remove existing property with same name
        self.properties = [p for p in self.properties if p.name != prop.name]
        self.properties.append(prop)
    
    def find_child_by_name(self, name: str) -> Optional['IRNode']:
        """Find direct child by name"""
        for child in self.children:
            if child.name == name or child.full_name == name:
                return child
        return None
    
    @classmethod
    def from_ast_node(cls, ast_node, parent_depth: int = -1) -> 'IRNode':
        """Convert AST node to IR node"""
        if hasattr(ast_node, 'target'):
            # This shouldn't happen in IR - overrides should be merged
            raise ValueError("Override nodes should not exist in intermediate representation")
        
        name = ast_node.name
        unit_addr = getattr(ast_node, 'unit_addr', None)
        label = getattr(ast_node, 'label', None)
        
        node_type = IRNodeType.ROOT if name == "/" else IRNodeType.NORMAL
        
        ir_node = cls(
            name=name,
            full_name=name,  # Will be set in __post_init__
            node_type=node_type,
            label=label,
            unit_addr=unit_addr,
            depth=parent_depth + 1,
            source_info={
                'source_file': getattr(ast_node, 'source_file', ''),
                'line_number': getattr(ast_node, 'line_number', 0)
            }
        )
        
        # Convert properties
        if hasattr(ast_node, 'properties') and ast_node.properties:
            for prop in ast_node.properties:
                ir_prop = IRProperty.from_ast_property(prop)
                ir_node.properties.append(ir_prop)
        
        # Convert children recursively
        if hasattr(ast_node, 'children') and ast_node.children:
            for child in ast_node.children:
                ir_child = cls.from_ast_node(child, ir_node.depth)
                ir_node.add_child(ir_child)
        
        return ir_node


@dataclass
class IntermediateRepresentation:
    """Complete intermediate representation of a device tree"""
    root: Optional[IRNode] = None
    labels_map: Dict[str, IRNode] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Build label mapping after construction"""
        if self.root:
            self._build_labels_map(self.root)
    
    def _build_labels_map(self, node: IRNode):
        """Recursively build label to node mapping"""
        if node.label:
            self.labels_map[node.label] = node
        
        for child in node.children:
            self._build_labels_map(child)
    
    def find_node_by_label(self, label: str) -> Optional[IRNode]:
        """Find node by label"""
        return self.labels_map.get(label)
    
    def find_node_by_path(self, path: str) -> Optional[IRNode]:
        """Find node by absolute path"""
        if not path.startswith('/'):
            return None
        
        if path == '/':
            return self.root
        
        # Split path and traverse
        parts = [p for p in path.split('/') if p]
        current = self.root
        
        for part in parts:
            if current is None:
                return None
            current = current.find_child_by_name(part)
        
        return current
    
    def get_node_count(self) -> int:
        """Get total number of nodes"""
        if not self.root:
            return 0
        return self._count_nodes(self.root)
    
    def _count_nodes(self, node: IRNode) -> int:
        """Recursively count nodes"""
        count = 1
        for child in node.children:
            count += self._count_nodes(child)
        return count


class IRBuilder:
    """Builder for creating intermediate representation from AST"""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
    
    def build_from_ast(self, device_tree: DeviceTree) -> IntermediateRepresentation:
        """Build IR from parsed AST with override merging"""
        if self.verbose:
            print("Building intermediate representation from AST")
        
        ir = IntermediateRepresentation()
        
        if not device_tree.root:
            return ir
        
        # First, convert AST to IR without overrides
        ir.root = IRNode.from_ast_node(device_tree.root)
        
        # Apply override nodes if they exist
        if hasattr(device_tree, 'override_nodes') and device_tree.override_nodes:
            if self.verbose:
                print(f"Applying {len(device_tree.override_nodes)} override nodes")
            
            for override in device_tree.override_nodes:
                self._apply_override_to_ir(ir, override)
        
        # Rebuild labels map after merging
        ir._build_labels_map(ir.root)
        
        # Set metadata
        ir.metadata = {
            'node_count': ir.get_node_count(),
            'label_count': len(ir.labels_map),
            'has_overrides': hasattr(device_tree, 'override_nodes') and bool(device_tree.override_nodes)
        }
        
        if self.verbose:
            print(f"Built IR with {ir.metadata['node_count']} nodes, {ir.metadata['label_count']} labels")
        
        return ir
    
    def _apply_override_to_ir(self, ir: IntermediateRepresentation, override_node: OverrideNode):
        """Apply an override node to the IR"""
        if not hasattr(override_node, 'target'):
            return
        
        # Find target node
        target = None
        if hasattr(override_node.target, 'kind') and hasattr(override_node.target, 'text'):
            if override_node.target.kind.name == 'LABEL':
                target = ir.find_node_by_label(override_node.target.text)
            elif override_node.target.kind.name == 'PATH':
                target = ir.find_node_by_path(override_node.target.text)
        else:
            # Fallback: try string representation
            target_str = str(override_node.target)
            if target_str.startswith('&'):
                label_name = target_str[1:]  # Remove &
                target = ir.find_node_by_label(label_name)
        
        if not target:
            if self.verbose:
                print(f"Warning: Override target not found: {override_node.target}")
            return
        
        # Mark as merged node
        target.node_type = IRNodeType.MERGED
        
        # Merge properties
        if hasattr(override_node, 'properties') and override_node.properties:
            for override_prop in override_node.properties:
                ir_prop = IRProperty.from_ast_property(override_prop)
                target.add_property(ir_prop)
        
        # Merge children
        if hasattr(override_node, 'children') and override_node.children:
            for override_child in override_node.children:
                ir_child = IRNode.from_ast_node(override_child, target.depth)
                target.add_child(ir_child)
        
        if self.verbose:
            print(f"Applied override to node: {target.full_name}")


# ===== Utility Functions =====

def optimize_ir_for_generation(ir: IntermediateRepresentation) -> IntermediateRepresentation:
    """Optimize IR for efficient text generation"""
    # Future optimizations can be added here:
    # - Property sorting for consistent output
    # - Node reordering for better readability
    # - Duplicate detection and removal
    # - Memory optimization for large trees
    
    return ir


def validate_ir(ir: IntermediateRepresentation) -> List[str]:
    """Validate IR structure and return list of issues"""
    issues = []
    
    if not ir.root:
        issues.append("No root node found")
        return issues
    
    if ir.root.name != "/":
        issues.append(f"Root node name should be '/', got '{ir.root.name}'")
    
    # Check for circular references (shouldn't happen but good to verify)
    visited = set()
    
    def check_node(node: IRNode, path: str):
        node_id = id(node)
        if node_id in visited:
            issues.append(f"Circular reference detected at {path}")
            return
        
        visited.add(node_id)
        
        for child in node.children:
            check_node(child, f"{path}/{child.name}")
    
    check_node(ir.root, "")
    
    return issues