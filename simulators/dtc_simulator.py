"""
simulators/dtc_simulator.py - DTC Compilation Simulator
"""

import os
import re
from datetime import datetime
from typing import Dict, List, Optional, Set
from pathlib import Path

# Import core classes instead of redefining them
from core import DTSNode, DTSProperty, DeviceTree


class Preprocessor:
    """DTS Preprocessor - Simplified version"""
    
    def __init__(self):
        self.included_files: Set[str] = set()
        self.include_paths: List[str] = []
        self.file_cache: Dict[str, str] = {}  # Cache for file contents
        
    def add_include_path(self, path: str):
        """Add include search path"""
        self.include_paths.append(path)
        
    def process_includes(self, file_path: str, base_dir: str = None) -> str:
        """Process all #include directives in file and merge root nodes"""
        if base_dir is None:
            base_dir = os.path.dirname(os.path.abspath(file_path))
            
        abs_path = os.path.abspath(file_path)
        
        # Prevent circular references
        if abs_path in self.included_files:
            return ""
        self.included_files.add(abs_path)
        
        print(f"    Processing file: {os.path.basename(file_path)}")
        
        # Check cache first
        if abs_path in self.file_cache:
            content = self.file_cache[abs_path]
        else:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                self.file_cache[abs_path] = content
            except FileNotFoundError:
                raise FileNotFoundError(f"Include file not found: {file_path}")
            
        # Process #include directives, add detailed source file annotations
        result_lines = []
        current_file = os.path.basename(file_path)
        
        for line_num, line in enumerate(content.split('\n'), 1):
            stripped = line.strip()
            
            if stripped.startswith('#include'):
                # Parse include path
                include_file = self._parse_include_line(stripped)
                if include_file:
                    include_path = self._resolve_include_path(include_file, base_dir)
                    if include_path:
                        print(f"      Including: {include_file} -> {os.path.basename(include_path)}")
                        # Add source annotation
                        result_lines.append(f"/* Include from {include_path} */")
                        
                        try:
                            # Recursively process include, no longer merge root nodes
                            included_content = self.process_includes(include_path, os.path.dirname(include_path))
                            result_lines.append(included_content)
                            result_lines.append(f"/* End of {include_path} */")
                            
                        except Exception as e:
                            result_lines.append(f"/* Include failed: {e} */")
                    else:
                        result_lines.append(f"/* Include not found: {include_file} */")
                else:
                    result_lines.append(f"/* Invalid include: {stripped} */")
            else:
                # Regular line, add source file annotation (for important lines)
                if any(keyword in stripped for keyword in ['compatible', '/dts-v1/', '/ {']):
                    result_lines.append(f"{line} /* {current_file}:{line_num} */")
                else:
                    result_lines.append(line)
        
        # Statistics information
        result_content = '\n'.join(result_lines)
        print(f"    Processed {current_file}: {len(content)} characters")
        
        return result_content
    
    def _parse_include_line(self, line: str) -> Optional[str]:
        """Parse #include line, extract file path"""
        # Support two formats: #include "file.dtsi" and #include <file.dtsi>
        match = re.match(r'#include\s*[<"](.*?)[>"]', line)
        return match.group(1) if match else None
    
    def _resolve_include_path(self, include_file: str, base_dir: str) -> Optional[str]:
        """Resolve absolute path of include file"""
        # First search in the same directory
        local_path = os.path.join(base_dir, include_file)
        if os.path.exists(local_path):
            return os.path.abspath(local_path)
        
        # Then search in include paths
        for include_dir in self.include_paths:
            full_path = os.path.join(include_dir, include_file)
            if os.path.exists(full_path):
                return os.path.abspath(full_path)
        
        return None


class DTCSimulator:
    """DTC Compiler Simulator - Stateless version"""
    
    def __init__(self, include_paths: List[str] = None):
        self.include_paths = include_paths or []
        
    def add_include_path(self, path: str):
        """Add include search path"""
        if path not in self.include_paths:
            self.include_paths.append(path)
            
    def compile_to_text_dtb(self, dts_file: str, output_file: str, 
                           verbose: bool = False, validate: bool = False,
                           test_overlays: bool = False, no_warnings: bool = False,
                           platform: str = None) -> tuple:
        """Compile DTS file to text DTB"""
        
        try:
            if verbose:
                print(f"dt-sim dtc: Compiling {os.path.basename(dts_file)} → {os.path.basename(output_file)}")
                print(f"dt-sim dtc: Compiling {os.path.basename(dts_file)} → {os.path.basename(output_file)}")
                
            if verbose:
                print("  Step 1: Processing includes...")
            
            # 1. Preprocess includes
            from parsers.preprocessor import Preprocessor as MainPreprocessor
            preprocessor = MainPreprocessor(verbose=verbose)
            
            # Add include paths
            base_dir = os.path.dirname(os.path.abspath(dts_file))
            preprocessor.add_include_path(base_dir)
            for path in self.include_paths:
                preprocessor.add_include_path(path)
            
            processed_content = preprocessor.process_file(dts_file, base_dir, platform=platform)
            
            if verbose:
                print("  Step 2: Parsing DTS syntax...")
            
            # 2. Parse syntax
            from parsers.dts_parser import DTSParser, DTSLexer
            
            lexer = DTSLexer()
            tokens = lexer.tokenize(processed_content, dts_file)
            
            print(f"  Parsing {len(tokens)} tokens from {os.path.basename(dts_file)}")
            
            parser = DTSParser(verbose=verbose)
            ast_root = parser.parse(processed_content, dts_file)
            
            if verbose:
                print("  Step 3: Building device tree structure...")
            
            # 3. Build device tree structure
            device_tree = DeviceTree(verbose=verbose)
            self._build_device_tree_from_ast(device_tree, ast_root)
            
            if verbose:
                print(f"    Built device tree with {len(device_tree.get_all_nodes())} nodes")
                print(f"    Label map: {list(device_tree.label_map.keys())}")
            
            if verbose:
                print("  Step 4: Resolving phandle references...")
                
            # 4. Resolve phandle references
            self._resolve_phandle_references(device_tree)
            
            if verbose:
                print("  Step 5: Validating device tree...")
                
            # 5. Validate device tree (if enabled)
            if validate:
                from utils.validator import DeviceTreeValidator
                validator = DeviceTreeValidator(verbose=verbose)
                validation_errors = validator.validate_device_tree(device_tree)
                
                if validation_errors and not no_warnings:
                    print(f"  Found {len(validation_errors)} validation issues")
                    for error in validation_errors:
                        print(f"    {error}")
                        
            if verbose:
                print("  Step 6: Generating text DTB...")
            
            # 6. Generate text DTB
            self._generate_text_dtb(device_tree, output_file, 
                                  source_file=dts_file, verbose=verbose)
            
            if verbose:
                phandle_count = len(device_tree.phandle_map)
                node_count = len(device_tree.get_all_nodes())
                print(f"Generated {os.path.basename(output_file)} ({node_count} nodes, {phandle_count} phandles)")
                
            print("Compilation completed successfully!")
            print(f"   Node count: {len(device_tree.get_all_nodes())}")
            print(f"   Phandle count: {len(device_tree.phandle_map)}")
            print(f"   Output file: {os.path.basename(output_file)}")
            
            return True, device_tree
            
        except Exception as e:
            print(f"ERROR in dt-sim dtc: {e}")
            return False, None
    
    def _build_device_tree_from_ast(self, device_tree: DeviceTree, ast_root):
        """Build device tree structure from AST"""
        # Recursively process AST nodes
        self._process_node_from_ast(device_tree, None, ast_root)
    
    def _process_node_from_ast(self, device_tree: DeviceTree, parent_node: Optional[DTSNode], ast_node):
        """Process individual node from AST node"""
        # Create device tree node
        node = DTSNode()
        node.name = ast_node.name
        node.labels = ast_node.labels[:]
        node.source_file = ast_node.source_file
        node.line_number = ast_node.line
        
        # Process properties
        for prop_name, prop_ast in ast_node.properties.items():
            prop = DTSProperty()
            prop.name = prop_name
            prop.type = prop_ast.type
            prop.value = prop_ast.value
            prop.raw_value = prop_ast.raw
            prop.source_file = ast_node.source_file
            prop.line_number = ast_node.line
            
            node.add_property(prop)
        
        # Add to parent node or device tree
        if parent_node:
            parent_node.add_child(node)
        else:
            device_tree.root = node
            
        # Add to device tree for tracking
        device_tree.add_node(node)
        
        # Recursively process child nodes
        for child_name, child_ast in ast_node.children.items():
            self._process_node_from_ast(device_tree, node, child_ast)
    
    def _process_all_nodes_from_ast(self, device_tree: DeviceTree, parent_node: DTSNode, parent_ast):
        """Process all AST nodes, including reference nodes"""
        for child_name, child_ast in parent_ast.children.items():
            self._process_node_from_ast(device_tree, parent_node, child_ast)
    
    def _resolve_phandle_references(self, device_tree: DeviceTree):
        """Resolve phandle references"""
        unresolved_refs = []
        
        for node in device_tree.get_all_nodes():
            for prop in node.properties.values():
                if prop.has_phandle_reference():
                    refs = prop.get_phandle_references()
                    for ref in refs:
                        target_node = device_tree.find_node_by_label(ref)
                        if not target_node:
                            unresolved_refs.append(f"&{ref} in {node.get_path()}:{prop.name}")
        
        if unresolved_refs:
            print("  Warning: Some phandle references could not be resolved:")
            for ref in unresolved_refs:
                print(f"    Unresolved phandle reference: {ref}")
            print("  Note: This might be normal if labels are defined in other files")
    
    def _generate_text_dtb(self, device_tree: DeviceTree, output_file: str,
                          source_file: str, verbose: bool = False):
        """Generate text format DTB file"""
        
        # Ensure output directory exists
        output_dir = os.path.dirname(output_file)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        # Use text generator
        from utils.text_generator import TextGenerator
        generator = TextGenerator()
        generator.generate_dtb_text(device_tree, output_file, source_file)