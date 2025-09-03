"""
Enhanced Core Design for Recursive Descent Parser
Based on device_tree_parser_spec.md
"""

from typing import Dict, List, Optional, Union, Any
from dataclasses import dataclass, field
from enum import Enum

# ===== Enhanced AST Structure =====

class ValueType(Enum):
    STRING = "string"
    NUMBER = "number"
    BYTE_STREAM = "byte_stream"  
    CELL_LIST = "cell_list"
    BOOLEAN = "boolean"

class ReferenceType(Enum):
    LABEL = "label"      # &label_name
    PATH = "path"        # &{/path/to/node}

@dataclass
class Reference:
    """Reference to another node (&label or &{/path})"""
    kind: ReferenceType
    text: str
    
    def __str__(self):
        if self.kind == ReferenceType.LABEL:
            return f"&{self.text}"
        else:
            return f"&{{{self.text}}}"

@dataclass
class Value:
    """Property value - can be string, number, byte stream, or cell list"""
    type: ValueType
    data: Any  # The actual value
    
    @property
    def is_reference(self) -> bool:
        """Check if this value contains references"""
        if self.type == ValueType.CELL_LIST:
            return any(isinstance(item, Reference) for item in self.data)
        return isinstance(self.data, Reference)

@dataclass
class Property:
    """Device tree property with enhanced type information"""
    name: str
    values: List[Value]
    source_file: str = ""
    line_number: int = 0
    
    @property
    def is_boolean(self) -> bool:
        return len(self.values) == 1 and self.values[0].type == ValueType.BOOLEAN
    
    @property
    def references(self) -> List[Reference]:
        """Get all references in this property"""
        refs = []
        for value in self.values:
            if isinstance(value.data, Reference):
                refs.append(value.data)
            elif value.type == ValueType.CELL_LIST:
                refs.extend([item for item in value.data if isinstance(item, Reference)])
        return refs

class NodeType(Enum):
    NORMAL = "normal"      # Regular node definition
    OVERRIDE = "override"  # Override existing node (&label { ... })

@dataclass  
class NormalNode:
    """Normal node definition: [label:] name[@unit-addr] { ... }"""
    name: str
    label: Optional[str] = None
    unit_addr: Optional[str] = None
    properties: List[Property] = field(default_factory=list)
    children: List['NodeStmt'] = field(default_factory=list)
    source_file: str = ""
    line_number: int = 0
    type: NodeType = NodeType.NORMAL
    
    @property
    def full_name(self) -> str:
        """Get full node name including unit address"""
        if self.unit_addr:
            return f"{self.name}@{self.unit_addr}"
        return self.name

@dataclass
class OverrideNode:  
    """Override node: &reference { ... }"""
    target: Reference
    properties: List[Property] = field(default_factory=list)
    children: List['NodeStmt'] = field(default_factory=list)
    source_file: str = ""
    line_number: int = 0
    type: NodeType = NodeType.OVERRIDE

# Union type for all node statements
NodeStmt = Union[NormalNode, OverrideNode]

# ===== Enhanced Device Tree Structure =====

class DeviceTree:
    """Enhanced device tree structure optimized for recursive parsing"""
    
    def __init__(self):
        self.root: Optional[NodeStmt] = None
        self.label_map: Dict[str, NodeStmt] = {}
        self.source_files: List[str] = []
        self.parse_warnings: List[str] = []
        
    def add_node(self, node: NodeStmt, parent_path: str = "/"):
        """Add node to tree with automatic label mapping"""
        if self.root is None:
            self.root = node
            
        # Register labels
        if isinstance(node, NormalNode) and node.label:
            self.label_map[node.label] = node
            
        # Track source files
        if node.source_file and node.source_file not in self.source_files:
            self.source_files.append(node.source_file)
            
        # Recursively process children
        for child in node.children:
            child_path = f"{parent_path.rstrip('/')}/{child.name if isinstance(child, NormalNode) else 'override'}"
            self.add_node(child, child_path)
    
    def resolve_reference(self, ref: Reference) -> Optional[NodeStmt]:
        """Resolve a reference to actual node"""
        if ref.kind == ReferenceType.LABEL:
            return self.label_map.get(ref.text)
        else:
            # Path-based lookup would need tree traversal
            return self._find_by_path(ref.text)
    
    def _find_by_path(self, path: str) -> Optional[NodeStmt]:
        """Find node by absolute path"""
        # Implementation for path-based node lookup
        # This would traverse the tree structure
        pass
    
    def validate_references(self) -> List[str]:
        """Validate all references in the tree"""
        errors = []
        
        def check_node(node: NodeStmt):
            # Check property references
            for prop in node.properties:
                for ref in prop.references:
                    if not self.resolve_reference(ref):
                        errors.append(f"Unresolved reference {ref} in property {prop.name}")
            
            # Check override node targets
            if isinstance(node, OverrideNode):
                if not self.resolve_reference(node.target):
                    errors.append(f"Unresolved override target {node.target}")
            
            # Recursively check children
            for child in node.children:
                check_node(child)
        
        if self.root:
            check_node(self.root)
            
        return errors

# ===== Token Definitions for New Parser =====

class TokenType(Enum):
    # Identifiers and literals
    IDENT = "IDENT"
    STRING = "STRING" 
    NUMBER = "NUMBER"
    
    # Operators and punctuation
    AMP = "&"           # &
    COLON = ":"         # :
    AT = "@"            # @
    LBRACE = "{"        # {
    RBRACE = "}"        # }
    SEMI = ";"          # ;
    EQUAL = "="         # =
    COMMA = ","         # ,
    LT = "<"            # <
    GT = ">"            # >
    LBRACK = "["        # [
    RBRACK = "]"        # ]
    SLASH = "/"         # /
    
    # Special tokens
    PATH = "PATH"       # For &{/path/to/node}
    COMMENT = "COMMENT"
    NEWLINE = "NEWLINE"
    EOF = "EOF"

@dataclass
class Token:
    """Enhanced token with position information"""
    type: TokenType
    value: str
    line: int
    column: int
    file: str = ""