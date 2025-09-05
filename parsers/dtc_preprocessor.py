"""
parsers/preprocessor_v2.py - Enhanced DTS Preprocessor v2

Redesigned preprocessor optimized for dts_parser_v2.py recursive descent parser.
Maintains better structural integrity and prevents node/property corruption.

Key improvements:
- Better include processing that preserves node boundaries
- Enhanced macro expansion with context awareness  
- Improved file structure preservation
- Compatible with recursive descent parsing requirements
"""

import os
import re
from typing import Dict, List, Set, Optional, Tuple
from pathlib import Path
from utils.error_reporter import ErrorReporter


class PreprocessorV2Error(Exception):
    """Preprocessor v2 error"""
    pass


class MacroV2:
    """Enhanced macro definition for v2 preprocessor"""
    def __init__(self, name: str, value: str, params: List[str] = None, 
                 source_file: str = "", line_number: int = 0):
        self.name = name
        self.value = value
        self.params = params or []
        self.source_file = source_file
        self.line_number = line_number
        self.is_function_like = len(self.params) > 0
    
    def expand(self, args: List[str] = None) -> str:
        """Expand macro with better context handling"""
        if self.is_function_like:
            if not args or len(args) != len(self.params):
                raise PreprocessorV2Error(
                    f"Macro '{self.name}' expects {len(self.params)} arguments, "
                    f"got {len(args) if args else 0}"
                )
            
            result = self.value
            for param, arg in zip(self.params, args):
                # Use word boundaries to avoid partial replacements
                pattern = r'\b' + re.escape(param) + r'\b'
                result = re.sub(pattern, arg, result)
            return result
        else:
            return self.value


class PreprocessorV2:
    """Enhanced DTS Preprocessor v2 - Optimized for recursive descent parser"""
    
    def __init__(self, verbose: bool = False):
        self.included_files: Set[str] = set()
        self.include_paths: List[str] = []
        self.macros: Dict[str, MacroV2] = {}
        self.verbose = verbose
        self.current_file = ""
        self.current_line = 0
        
        # Enhanced built-in macro definitions
        self._setup_builtin_macros()
    
    def _setup_builtin_macros(self):
        """Setup enhanced built-in macro definitions"""
        basic_builtins = {
            '__DTS__': '1',
            '__FILE__': '""',
            '__LINE__': '0',
            # Common device tree macros
            'DT_CPP_CONCAT': '#define DT_CPP_CONCAT(a, b) a ## b',
            'DT_STRINGIFY': '#define DT_STRINGIFY(s) #s',
        }
        
        for name, value in basic_builtins.items():
            self.macros[name] = MacroV2(name, value)
    
    def add_include_path(self, path: str):
        """Add include search path"""
        abs_path = os.path.abspath(path)
        if abs_path not in self.include_paths:
            self.include_paths.append(abs_path)
    
    def load_platform_bindings(self, platform: str = None, auto_detect: bool = True, content: str = ""):
        """Load platform-specific bindings with enhanced detection"""
        if self.verbose:
            if platform:
                print(f"Auto-detected platform: {platform}")
            print("  Loading common bindings")
        
        # Load common bindings
        common_bindings_path = os.path.join("bindings", "common.dtsi")
        if os.path.exists(common_bindings_path):
            self._load_bindings_file(common_bindings_path)
        
        # Platform-specific bindings
        if platform and auto_detect:
            platform_path = os.path.join("bindings", f"{platform}.dtsi")
            if os.path.exists(platform_path):
                self._load_bindings_file(platform_path)
        
        # Auto-detect platform from content if not specified
        if auto_detect and not platform:
            detected_platform = self._detect_platform(content)
            if detected_platform:
                platform_path = os.path.join("bindings", f"{detected_platform}.dtsi")
                if os.path.exists(platform_path):
                    self._load_bindings_file(platform_path)
    
    def _detect_platform(self, content: str) -> Optional[str]:
        """Enhanced platform detection"""
        platform_patterns = {
            'imx95': [r'imx95', r'fsl,imx95'],
            'imx8': [r'imx8', r'fsl,imx8'],
            'rpi': [r'raspberry', r'broadcom'],
        }
        
        content_lower = content.lower()
        for platform, patterns in platform_patterns.items():
            if any(re.search(pattern, content_lower) for pattern in patterns):
                return platform
        
        return None
    
    def _load_bindings_file(self, bindings_path: str):
        """Load macro definitions from bindings file"""
        try:
            with open(bindings_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Process #define statements
            define_pattern = r'#define\s+(\w+)\s+(.+)'
            defines_found = 0
            macros_found = 0
            
            for match in re.finditer(define_pattern, content, re.MULTILINE):
                name = match.group(1)
                value = match.group(2).strip()
                
                # Check if it's a function-like macro
                if '(' in name:
                    # Function-like macro: #define FUNC(x,y) (x + y)
                    func_match = re.match(r'(\w+)\(([^)]*)\)', name)
                    if func_match:
                        func_name = func_match.group(1)
                        params = [p.strip() for p in func_match.group(2).split(',') if p.strip()]
                        self.macros[func_name] = MacroV2(func_name, value, params, bindings_path, 0)
                        macros_found += 1
                else:
                    # Simple define
                    self.macros[name] = MacroV2(name, value, [], bindings_path, 0)
                    defines_found += 1
            
            if self.verbose:
                print(f"  Loaded {defines_found} constants, {macros_found} macros")
                
        except FileNotFoundError:
            if self.verbose:
                print(f"  Bindings file not found: {bindings_path}")
        except Exception as e:
            if self.verbose:
                print(f"  Error loading bindings: {e}")
    
    def process_file(self, file_path: str, base_dir: str = None, platform: str = None) -> str:
        """Process all preprocessing directives in file with enhanced structure preservation"""
        if base_dir is None:
            base_dir = os.path.dirname(os.path.abspath(file_path))
            
        self.add_include_path(base_dir)
        
        # Load platform bindings
        if self.verbose:
            print("  Loading platform-specific bindings...")
        
        # Read file for platform detection
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                initial_content = f.read()
        except:
            initial_content = ""
        
        self.load_platform_bindings(platform=platform, auto_detect=True, content=initial_content)
        
        # Process with enhanced structure preservation
        return self._process_file_enhanced(file_path, base_dir)
    
    def _process_file_enhanced(self, file_path: str, base_dir: str) -> str:
        """Enhanced file processing that preserves device tree structure"""
        abs_path = os.path.abspath(file_path)
        
        # Prevent circular includes
        if abs_path in self.included_files:
            if self.verbose:
                print(f"Skipping already included file: {os.path.basename(file_path)}")
            return ""
        
        self.included_files.add(abs_path)
        self.current_file = file_path
        
        if self.verbose:
            print(f"Processing file: {os.path.basename(file_path)}")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except FileNotFoundError:
            raise PreprocessorV2Error(f"File not found: {file_path}")
        except UnicodeDecodeError:
            raise PreprocessorV2Error(f"Cannot decode file (not UTF-8): {file_path}")
        
        # Enhanced line-by-line processing with better context awareness
        result_lines = []
        lines = content.split('\n')
        in_node = False
        node_depth = 0
        
        for line_num, line in enumerate(lines, 1):
            self.current_line = line_num
            
            # Track node depth for better structure preservation
            stripped = line.strip()
            if stripped.endswith('{'):
                if self._is_node_start(stripped):
                    in_node = True
                node_depth += stripped.count('{')
            
            node_depth -= stripped.count('}')
            if node_depth <= 0:
                in_node = False
                node_depth = 0
            
            # Process line with enhanced context
            processed_line = self._process_line_enhanced(
                line, file_path, line_num, base_dir, result_lines, in_node, node_depth
            )
            
            if processed_line is not None:
                if isinstance(processed_line, list):
                    result_lines.extend(processed_line)
                else:
                    result_lines.append(processed_line)
        
        final_content = '\n'.join(result_lines)
        
        if self.verbose:
            print(f"Processed {os.path.basename(file_path)}: "
                  f"{len(lines)} lines → {len(result_lines)} lines")
        
        return final_content
    
    def _is_node_start(self, line: str) -> bool:
        """Check if line starts a device tree node"""
        # Simple heuristic: contains node name patterns
        node_patterns = [
            r'^\s*\w+\s*{',  # simple_node {
            r'^\s*\w+:\s*\w+.*{',  # label: node_name@addr {
            r'^\s*/.*{',  # root node / {
            r'^\s*&\w+\s*{',  # override node &label {
        ]
        
        return any(re.match(pattern, line) for pattern in node_patterns)
    
    def _process_line_enhanced(self, line: str, current_file: str, line_num: int, 
                             base_dir: str, result_lines: List[str], 
                             in_node: bool, node_depth: int) -> Optional[str]:
        """Enhanced line processing with better context awareness"""
        original_line = line
        stripped = line.strip()
        
        # Handle preprocessor directives
        if stripped.startswith('#'):
            return self._handle_preprocessor_directive(
                line, current_file, line_num, base_dir, result_lines
            )
        
        # Skip empty lines and comments (but preserve them for structure)
        if not stripped or stripped.startswith('//') or stripped.startswith('/*'):
            return line
        
        # Enhanced macro expansion with context awareness
        expanded_line = self._expand_macros_enhanced(line, in_node, node_depth)
        
        return expanded_line
    
    def _handle_preprocessor_directive(self, line: str, current_file: str, line_num: int,
                                     base_dir: str, result_lines: List[str]) -> Optional[str]:
        """Handle preprocessor directives with enhanced include processing"""
        stripped = line.strip()
        
        # Handle #include
        include_match = re.match(r'#include\s*[<"]([^>"]+)[>"]', stripped)
        if include_match:
            include_file = include_match.group(1)
            
            # Find include file
            include_path = self._find_include_file(include_file, base_dir)
            if not include_path:
                raise PreprocessorV2Error(f"Include file not found: {include_file}")
            
            if self.verbose:
                print(f"  Including: {include_file} -> {os.path.basename(include_path)}")
            
            # Process included file with structure preservation
            included_content = self._process_file_enhanced(include_path, os.path.dirname(include_path))
            
            # Return as list of lines to maintain structure
            if included_content:
                return included_content.split('\n')
            else:
                return None
        
        # Handle #define
        define_match = re.match(r'#define\s+(\w+)(?:\(([^)]*)\))?\s*(.*)', stripped)
        if define_match:
            name = define_match.group(1)
            params_str = define_match.group(2)
            value = define_match.group(3) if define_match.group(3) else ""
            
            params = []
            if params_str:
                params = [p.strip() for p in params_str.split(',') if p.strip()]
            
            self.macros[name] = MacroV2(name, value, params, current_file, line_num)
            
            if self.verbose:
                if params:
                    print(f"  Defined macro: {name}({', '.join(params)}) = {value}")
                else:
                    print(f"  Defined constant: {name} = {value}")
            
            return None  # Remove the #define line from output
        
        # Handle other directives (pass through)
        return line
    
    def _find_include_file(self, filename: str, base_dir: str) -> Optional[str]:
        """Find include file in search paths with enhanced search"""
        # Try relative to current file first
        candidate = os.path.join(base_dir, filename)
        if os.path.exists(candidate):
            return candidate
        
        # Try all include paths
        for include_path in self.include_paths:
            candidate = os.path.join(include_path, filename)
            if os.path.exists(candidate):
                return candidate
        
        return None
    
    def _expand_macros_enhanced(self, line: str, in_node: bool, node_depth: int) -> str:
        """Enhanced macro expansion with better context awareness"""
        result = line
        
        # Sort macros by name length (longest first) to avoid partial replacements
        sorted_macros = sorted(self.macros.items(), key=lambda x: len(x[0]), reverse=True)
        
        for name, macro in sorted_macros:
            if macro.is_function_like:
                # Function-like macro expansion
                pattern = rf'\b{re.escape(name)}\s*\('
                matches = list(re.finditer(pattern, result))
                
                for match in reversed(matches):  # Process from end to avoid position shifts
                    start = match.start()
                    # Find matching closing parenthesis
                    paren_count = 0
                    pos = match.end() - 1  # Start at the opening paren
                    
                    for i in range(pos, len(result)):
                        if result[i] == '(':
                            paren_count += 1
                        elif result[i] == ')':
                            paren_count -= 1
                            if paren_count == 0:
                                end = i + 1
                                break
                    else:
                        continue  # No matching closing paren
                    
                    # Extract arguments
                    args_str = result[match.end():end-1]
                    args = self._parse_macro_args(args_str)
                    
                    try:
                        expanded = macro.expand(args)
                        result = result[:start] + expanded + result[end:]
                    except PreprocessorV2Error:
                        continue  # Skip invalid expansions
            else:
                # Simple macro expansion with word boundaries
                pattern = r'\b' + re.escape(name) + r'\b'
                result = re.sub(pattern, macro.value, result)
        
        return result
    
    def _parse_macro_args(self, args_str: str) -> List[str]:
        """Parse macro function arguments with proper comma handling"""
        if not args_str.strip():
            return []
        
        args = []
        current_arg = ""
        paren_count = 0
        
        for char in args_str:
            if char == ',' and paren_count == 0:
                args.append(current_arg.strip())
                current_arg = ""
            else:
                if char == '(':
                    paren_count += 1
                elif char == ')':
                    paren_count -= 1
                current_arg += char
        
        if current_arg.strip():
            args.append(current_arg.strip())
        
        return args