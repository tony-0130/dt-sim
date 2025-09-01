"""
core/__init__.py - dt-sim 核心資料結構
"""

from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass

@dataclass
class DTSProperty:
    """設備樹屬性"""
    name: str = ""
    value: Any = None
    type: str = ""
    raw_value: str = ""
    source_file: str = ""
    line_number: int = 0
    
    def has_phandle_reference(self) -> bool:
        if self.type == "phandle":
            return True
        if self.type == "array" and isinstance(self.value, list):
            return any(isinstance(v, str) and v.startswith('&') for v in self.value)
        return False
        
    def get_phandle_references(self) -> List[str]:
        refs = []
        if self.type == "phandle":
            if isinstance(self.value, str) and self.value.startswith('&'):
                refs.append(self.value[1:])
            elif isinstance(self.value, list):
                for v in self.value:
                    if isinstance(v, str) and v.startswith('&'):
                        refs.append(v[1:])
        elif self.type == "array" and isinstance(self.value, list):
            for v in self.value:
                if isinstance(v, str) and v.startswith('&'):
                    refs.append(v[1:])
        return refs

class DTSNode:
    """設備樹節點"""
    
    def __init__(self):
        self.name: str = ""
        self.labels: List[str] = []
        self.properties: Dict[str, DTSProperty] = {}
        self.children: Dict[str, 'DTSNode'] = {}
        self.parent: Optional['DTSNode'] = None
        self.phandle: Optional[int] = None
        self.source_file: str = ""
        self.line_number: int = 0
        
    def get_path(self) -> str:
        if self.parent is None:
            return "/"
        elif self.parent.parent is None:
            return f"/{self.name}"
        else:
            return f"{self.parent.get_path()}/{self.name}"
            
    def find_child_by_path(self, path: str) -> Optional['DTSNode']:
        if not path or path == "/":
            return self
        if path.startswith("/"):
            root = self
            while root.parent is not None:
                root = root.parent
            return root.find_child_by_path(path[1:])
        parts = [p for p in path.split("/") if p]
        current = self
        for part in parts:
            if part in current.children:
                current = current.children[part]
            else:
                return None
        return current
        
    def add_child(self, child: 'DTSNode'):
        child.parent = self
        self.children[child.name] = child
        
    def get_all_descendants(self) -> List['DTSNode']:
        nodes = []
        for child in self.children.values():
            nodes.append(child)
            nodes.extend(child.get_all_descendants())
        return nodes

class DeviceTree:
    """設備樹主結構"""
    
    def __init__(self, verbose: bool = False):
        self.root: Optional[DTSNode] = None
        self.phandle_map: Dict[int, DTSNode] = {}
        self.label_map: Dict[str, DTSNode] = {}
        self.next_phandle: int = 1
        self.source_files: Set[str] = set()
        self.verbose = verbose
        
    def add_node(self, node: DTSNode):
        if self.root is None:
            self.root = node
        if node.source_file:
            self.source_files.add(node.source_file)
        if self.verbose:
            print(f"    Processing node: {node.name} at {node.get_path()}")
        for label in node.labels:
            if label:
                self.label_map[label] = node
                if self.verbose:
                    print(f"      Mapped label '{label}' to node {node.get_path()}")
        if node.labels and node.phandle is None:
            node.phandle = self.next_phandle
            self.phandle_map[self.next_phandle] = node
            if self.verbose:
                print(f"      Assigned phandle 0x{self.next_phandle:02x}")
            self.next_phandle += 1
            
    def find_node_by_path(self, path: str) -> Optional[DTSNode]:
        if not self.root:
            return None
        return self.root.find_child_by_path(path)
        
    def find_node_by_label(self, label: str) -> Optional[DTSNode]:
        return self.label_map.get(label)
        
    def find_node_by_phandle(self, phandle: int) -> Optional[DTSNode]:
        return self.phandle_map.get(phandle)
        
    def get_all_nodes(self) -> List[DTSNode]:
        if not self.root:
            return []
        nodes = [self.root]
        nodes.extend(self.root.get_all_descendants())
        return nodes

__all__ = ['DeviceTree', 'DTSNode', 'DTSProperty']