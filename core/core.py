"""
core/ - Device Tree Core Data Structures

This module defines the core data structures used in dt-sim:
- DeviceTree: Main device tree structure
- DTSNode: Device tree node
- DTSProperty: Device tree property
- OverlayStructure: Overlay structure
- Fragment: Overlay fragment
"""

from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
import os
from pathlib import Path


@dataclass
class DTSProperty:
    """Device tree property"""
    name: str = ""
    value: Any = None
    type: str = ""  # "string", "number", "array", "phandle", "empty", "bits_array", "identifier"
    raw_value: str = ""
    source_file: str = ""
    line_number: int = 0
    
    def has_phandle_reference(self) -> bool:
        """Check if contains phandle references"""
        if self.type == "phandle":
            return True
        if self.type == "array" and isinstance(self.value, list):
            return any(isinstance(v, str) and v.startswith('&') for v in self.value)
        return False
        
    def get_phandle_references(self) -> List[str]:
        """Get all phandle reference labels"""
        refs = []
        if self.type == "phandle":
            if isinstance(self.value, str) and self.value.startswith('&'):
                refs.append(self.value[1:])  # 去掉 & 符號
            elif isinstance(self.value, list):
                for v in self.value:
                    if isinstance(v, str) and v.startswith('&'):
                        refs.append(v[1:])
        elif self.type == "array" and isinstance(self.value, list):
            for v in self.value:
                if isinstance(v, str) and v.startswith('&'):
                    refs.append(v[1:])
        return refs
    
    def to_dts_string(self) -> str:
        """Convert property to DTS string format"""
        if self.type == "empty":
            return f"{self.name};"
        elif self.type == "string":
            return f'{self.name} = "{self.value}";'
        elif self.raw_value:
            return f"{self.name} = {self.raw_value};"
        else:
            # fallback
            return f"{self.name} = /* unknown format */;"


class DTSNode:
    """設備樹節點"""
    
    def __init__(self):
        self.name: str = ""
        self.full_path: str = ""
        self.labels: List[str] = []
        self.properties: Dict[str, DTSProperty] = {}
        self.children: Dict[str, 'DTSNode'] = {}
        self.parent: Optional['DTSNode'] = None
        self.phandle: Optional[int] = None
        self.source_file: str = ""
        self.line_number: int = 0
        
    def get_path(self) -> str:
        """獲取節點的完整路徑"""
        if self.parent is None:
            return "/"
        elif self.parent.parent is None:  # parent is root
            return f"/{self.name}"
        else:
            return f"{self.parent.get_path()}/{self.name}"
            
    def find_child_by_path(self, path: str) -> Optional['DTSNode']:
        """根據路徑查找子節點"""
        if not path or path == "/":
            return self
            
        # 處理絕對路徑
        if path.startswith("/"):
            # 找到根節點
            root = self
            while root.parent is not None:
                root = root.parent
            return root.find_child_by_path(path[1:])  # 去掉開頭的 /
            
        parts = [p for p in path.split("/") if p]
        current = self
        
        for part in parts:
            if part in current.children:
                current = current.children[part]
            else:
                return None
        return current
        
    def add_child(self, child: 'DTSNode'):
        """添加子節點"""
        child.parent = self
        self.children[child.name] = child
        
    def get_all_descendants(self) -> List['DTSNode']:
        """獲取所有後代節點"""
        nodes = []
        for child in self.children.values():
            nodes.append(child)
            nodes.extend(child.get_all_descendants())
        return nodes
    
    def get_all_paths(self) -> List[str]:
        """獲取所有可能的節點路徑（用於錯誤提示）"""
        paths = [self.get_path()]
        for child in self.children.values():
            paths.extend(child.get_all_paths())
        return paths
    
    def has_property(self, prop_name: str) -> bool:
        """檢查是否有指定屬性"""
        return prop_name in self.properties
        
    def get_property(self, prop_name: str) -> Optional[DTSProperty]:
        """獲取指定屬性"""
        return self.properties.get(prop_name)
    
    def add_property(self, prop: DTSProperty):
        """添加屬性"""
        self.properties[prop.name] = prop
    
    def to_dts_string(self, indent_level: int = 0) -> str:
        """Convert node to DTS string format"""
        indent = "    " * indent_level
        lines = []
        
        # 節點聲明
        labels_str = ": ".join(self.labels) + ": " if self.labels else ""
        
        if self.name == "/":
            lines.append(f"{labels_str}/ {{")
        else:
            lines.append(f"{indent}{labels_str}{self.name} {{")
            
        # 屬性
        for prop in sorted(self.properties.values(), key=lambda p: p.name):
            prop_line = prop.to_dts_string()
            lines.append(f"{indent}    {prop_line}")
            
        # 子節點
        for child in sorted(self.children.values(), key=lambda c: c.name):
            lines.append("")  # 空行分隔
            child_lines = child.to_dts_string(indent_level + 1).split('\n')
            lines.extend(child_lines)
            
        lines.append(f"{indent}}};")
        
        return '\n'.join(lines)


class DeviceTree:
    """設備樹主結構"""
    
    def __init__(self, verbose: bool = False):
        self.root: Optional[DTSNode] = None
        self.phandle_map: Dict[int, DTSNode] = {}  # phandle -> Node
        self.label_map: Dict[str, DTSNode] = {}    # label -> Node
        self.next_phandle: int = 1
        self.source_files: Set[str] = set()
        self.verbose = verbose
        
    def add_node(self, node: DTSNode):
        """添加節點到樹中"""
        if self.root is None:
            self.root = node
            
        # 記錄來源文件
        if node.source_file:
            self.source_files.add(node.source_file)
            
        # 調試：顯示正在處理的節點
        if self.verbose:
            print(f"    Processing node: {node.name} at {node.get_path()}")
            if node.labels:
                print(f"      Labels: {node.labels}")
            print(f"      Properties: {list(node.properties.keys())}")
            
        # 處理標籤 - 確保所有標籤都被正確映射
        for label in node.labels:
            if label:  # 確保標籤不為空
                self.label_map[label] = node
                if self.verbose:
                    print(f"      Mapped label '{label}' to node {node.get_path()}")
            
        # Assign phandle (if node has labels)
        if node.labels and node.phandle is None:
            node.phandle = self.next_phandle
            self.phandle_map[self.next_phandle] = node
            if self.verbose:
                print(f"      Assigned phandle 0x{self.next_phandle:02x} to node {node.get_path()}")
            self.next_phandle += 1
            
    def find_node_by_path(self, path: str) -> Optional[DTSNode]:
        """根據路徑查找節點"""
        if not self.root:
            return None
        return self.root.find_child_by_path(path)
        
    def find_node_by_label(self, label: str) -> Optional[DTSNode]:
        """根據標籤查找節點"""
        return self.label_map.get(label)
        
    def find_node_by_phandle(self, phandle: int) -> Optional[DTSNode]:
        """Find node by phandle"""
        return self.phandle_map.get(phandle)
        
    def get_all_nodes(self) -> List[DTSNode]:
        """獲取所有節點"""
        if not self.root:
            return []
        nodes = [self.root]
        nodes.extend(self.root.get_all_descendants())
        return nodes
    
    def get_all_paths(self) -> List[str]:
        """獲取所有節點路徑（用於錯誤提示和建議）"""
        if not self.root:
            return []
        return self.root.get_all_paths()
    
    def validate_phandle_references(self) -> List[str]:
        """Validate all phandle references, return error list"""
        errors = []
        
        for node in self.get_all_nodes():
            for prop in node.properties.values():
                if prop.has_phandle_reference():
                    refs = prop.get_phandle_references()
                    for ref_label in refs:
                        if not self.find_node_by_label(ref_label):
                            errors.append(
                                f"Unresolved phandle reference: &{ref_label} "
                                f"in {node.get_path()}:{prop.name} "
                                f"({prop.source_file}:{prop.line_number})"
                            )
        return errors
    
    def get_statistics(self) -> Dict[str, Any]:
        """獲取設備樹統計信息"""
        all_nodes = self.get_all_nodes()
        total_properties = sum(len(node.properties) for node in all_nodes)
        
        return {
            "total_nodes": len(all_nodes),
            "total_properties": total_properties,
            "total_phandles": len(self.phandle_map),
            "total_labels": len(self.label_map),
            "source_files": list(self.source_files)
        }


@dataclass
class Fragment:
    """Overlay Fragment"""
    target_path: str = ""
    target_label: str = ""  # If using &label syntax
    target_phandle: Optional[int] = None
    overlay_node: Optional[DTSNode] = None
    source_file: str = ""
    line_number: int = 0
    
    def get_target_reference(self) -> str:
        """獲取目標引用的字符串表示"""
        if self.target_label:
            return f"&{self.target_label}"
        elif self.target_path:
            return self.target_path
        elif self.target_phandle:
            return f"phandle:{self.target_phandle}"
        else:
            return "unknown"
    
    def validate_target(self, base_tree: DeviceTree) -> Optional[str]:
        """Validate target exists in base tree, return error message or None"""
        if self.target_label:
            target_node = base_tree.find_node_by_label(self.target_label)
            if not target_node:
                return f"Target label '{self.target_label}' not found"
        elif self.target_path:
            target_node = base_tree.find_node_by_path(self.target_path)
            if not target_node:
                return f"Target path '{self.target_path}' not found"
        elif self.target_phandle:
            target_node = base_tree.find_node_by_phandle(self.target_phandle)
            if not target_node:
                return f"Target phandle {self.target_phandle} not found"
        else:
            return "No target specified"
            
        return None  # 驗證通過


class OverlayStructure:
    """Overlay structure"""
    
    def __init__(self):
        self.fragments: List[Fragment] = []
        self.source_file: str = ""
        self.metadata: Dict[str, Any] = {}
        
    def add_fragment(self, fragment: Fragment):
        """Add fragment"""
        self.fragments.append(fragment)
        
    def validate_against_base(self, base_tree: DeviceTree) -> List[str]:
        """Validate all fragments against base tree, return error list"""
        errors = []
        
        for i, fragment in enumerate(self.fragments):
            error = fragment.validate_target(base_tree)
            if error:
                location = f"{fragment.source_file}:{fragment.line_number}" if fragment.source_file else f"fragment[{i}]"
                errors.append(f"{location}: {error}")
                
        return errors
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get overlay statistics"""
        return {
            "total_fragments": len(self.fragments),
            "source_file": self.source_file,
            "metadata": self.metadata
        }


# 工具函數

def suggest_similar_path(target_path: str, available_paths: List[str], max_suggestions: int = 3) -> List[str]:
    """建議相似的路徑（用於錯誤提示）"""
    import difflib
    
    # Use difflib to find most similar path
    matches = difflib.get_close_matches(target_path, available_paths, n=max_suggestions, cutoff=0.3)
    return matches


def parse_node_address(node_name: str) -> tuple:
    """解析節點名中的地址部分
    例如: "uart@12340000" -> ("uart", "12340000")
    """
    if '@' in node_name:
        parts = node_name.split('@', 1)
        return (parts[0], parts[1])
    else:
        return (node_name, None)


def format_property_value_for_display(prop: DTSProperty, max_length: int = 50) -> str:
    """格式化屬性值用於顯示（截斷過長的值）"""
    if prop.type == "empty":
        return ""
    elif prop.type == "string":
        if len(prop.value) > max_length:
            return f'"{prop.value[:max_length-3]}..."'
        return f'"{prop.value}"'
    elif prop.raw_value:
        if len(prop.raw_value) > max_length:
            return f"{prop.raw_value[:max_length-3]}..."
        return prop.raw_value
    else:
        return str(prop.value)


# 常用的節點類型檢查函數

def is_root_node(node: DTSNode) -> bool:
    """檢查是否為根節點"""
    return node.name == "/" and node.parent is None


def is_memory_node(node: DTSNode) -> bool:
    """Check if is memory node"""
    device_type = node.get_property("device_type")
    return device_type and device_type.value == "memory"


def is_cpu_node(node: DTSNode) -> bool:
    """Check if is CPU node"""
    device_type = node.get_property("device_type")
    return device_type and device_type.value == "cpu"


def has_compatible_property(node: DTSNode, compatible_string: str) -> bool:
    """Check if node has specified compatible property"""
    compatible = node.get_property("compatible")
    if not compatible:
        return False
    
    if compatible.type == "string":
        return compatible.value == compatible_string
    elif compatible.type == "array":
        return compatible_string in compatible.value
    
    return False


# 用於調試和測試的輔助函數

def print_device_tree_summary(tree: DeviceTree, max_depth: int = 3):
    """打印設備樹摘要（用於調試）"""
    print("=== Device Tree Summary ===")
    stats = tree.get_statistics()
    print(f"總節點數: {stats['total_nodes']}")
    print(f"總屬性數: {stats['total_properties']}")
    print(f"Phandle 數: {stats['total_phandles']}")
    print(f"Label 數: {stats['total_labels']}")
    print(f"來源文件: {', '.join(stats['source_files'])}")
    
    if tree.root:
        print("\n節點結構:")
        _print_node_tree(tree.root, 0, max_depth)
        
    if tree.label_map:
        print(f"\nLabel 映射:")
        for label, node in sorted(tree.label_map.items()):
            phandle_str = f" (phandle: 0x{node.phandle:02x})" if node.phandle else ""
            print(f"  {label}: {node.get_path()}{phandle_str}")


def _print_node_tree(node: DTSNode, depth: int, max_depth: int):
    """遞迴打印節點樹（輔助函數）"""
    if depth > max_depth:
        return
        
    indent = "  " * depth
    labels_str = f" [{', '.join(node.labels)}]" if node.labels else ""
    prop_count = len(node.properties)
    child_count = len(node.children)
    
    print(f"{indent}{node.name}{labels_str} ({prop_count} props, {child_count} children)")
    
    # 顯示重要屬性
    important_props = ["compatible", "device_type", "reg", "status"]
    for prop_name in important_props:
        if prop_name in node.properties:
            prop = node.properties[prop_name]
            value_str = format_property_value_for_display(prop, 30)
            print(f"{indent}  {prop_name} = {value_str}")
    
    # 遞迴顯示子節點
    for child in sorted(node.children.values(), key=lambda n: n.name):
        _print_node_tree(child, depth + 1, max_depth)


def validate_device_tree_structure(tree: DeviceTree) -> List[str]:
    """驗證設備樹基本結構，返回警告列表"""
    warnings = []
    
    if not tree.root:
        warnings.append("No root node found")
        return warnings
    
    root = tree.root
    
    # 檢查根節點基本屬性
    if not root.has_property("#address-cells"):
        warnings.append("Root node missing #address-cells property")
    
    if not root.has_property("#size-cells"):
        warnings.append("Root node missing #size-cells property")
    
    if not root.has_property("compatible"):
        warnings.append("Root node missing compatible property")
    
    # Check if has memory node
    has_memory = any(is_memory_node(node) for node in tree.get_all_nodes())
    if not has_memory:
        warnings.append("No memory node found")
    
    # Check phandle references
    phandle_errors = tree.validate_phandle_references()
    warnings.extend(phandle_errors)
    
    return warnings
