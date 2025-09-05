"""
core/__init__.py - dt-sim Core Data Structures - Clean Architecture

Clean architecture exports:
- AST structures for parsing (from ast.py)
- Intermediate representation (from intermediate.py)

Legacy V1 structures moved to legacy/ folder.
"""

from .ast import (
    DeviceTree, NormalNode, OverrideNode, 
    Property, Value, ValueType, Reference, ReferenceType,
    Token, TokenType, NodeStmt
)

from .intermediate import (
    IntermediateRepresentation, IRNode, IRProperty, IRBuilder,
    validate_ir, optimize_ir_for_generation
)

__all__ = [
    # AST structures
    'DeviceTree', 'NormalNode', 'OverrideNode', 
    'Property', 'Value', 'ValueType', 'Reference', 'ReferenceType',
    'Token', 'TokenType', 'NodeStmt',
    
    # Intermediate representation
    'IntermediateRepresentation', 'IRNode', 'IRProperty', 'IRBuilder',
    'validate_ir', 'optimize_ir_for_generation'
]