"""
parsers/preprocessor.py - DTS Preprocessor

Handle preprocessing directives in DTS files:
- #include "file.dtsi" and #include <file.dtsi>
- #define SYMBOL VALUE
- Basic macro expansion
- Conditional compilation (simple support)
"""

import os
import re
from typing import Dict, List, Set, Optional, Tuple
from pathlib import Path
from utils.error_reporter import ErrorReporter

class PreprocessorError(Exception):
    """Preprocessor error"""
    pass


class Macro:
    """Macro definition"""
    def __init__(self, name: str, value: str, params: List[str] = None, 
                 source_file: str = "", line_number: int = 0):
        self.name = name
        self.value = value
        self.params = params or []  # Function-like macro parameters
        self.source_file = source_file
        self.line_number = line_number
        self.is_function_like = len(self.params) > 0
    
    def expand(self, args: List[str] = None) -> str:
        """Expand macro"""
        if self.is_function_like:
            if not args or len(args) != len(self.params):
                raise PreprocessorError(
                    f"Macro '{self.name}' expects {len(self.params)} arguments, "
                    f"got {len(args) if args else 0}"
                )
            
            # Replace parameters
            result = self.value
            for param, arg in zip(self.params, args):
                result = result.replace(param, arg)
            return result
        else:
            return self.value


class Preprocessor:
    """DTS Preprocessor"""
    
    def __init__(self, verbose: bool = False):
        self.included_files: Set[str] = set()
        self.include_paths: List[str] = []
        self.macros: Dict[str, Macro] = {}
        self.verbose = verbose
        
        # Built-in macro definitions
        self._setup_builtin_macros()
    
    def _setup_builtin_macros(self):
        """Setup built-in macro definitions"""
        # Basic DTS macros
        basic_builtins = {
            '__DTS__': '1',
            '__FILE__': '""',  # Will be replaced with actual filename during processing
            '__LINE__': '0',   # Will be replaced with actual line number during processing
        }
        
        # Add basic macros
        for name, value in basic_builtins.items():
            self.macros[name] = Macro(name, value, source_file="<builtin>")
    
    def load_platform_bindings(self, platform: str = None, auto_detect: bool = True, content: str = ""):
        """Load platform-specific bindings"""
        try:
            from bindings import BindingManager
            
            binding_manager = BindingManager()
            constants, macros = binding_manager.load_bindings(platform, auto_detect, content)
            
            if self.verbose:
                if platform:
                    print(f"  Loading bindings for platform: {platform}")
                else:
                    print("  Loading common bindings")
                print(f"  Loaded {len(constants)} constants, {len(macros)} macros")
            
            # Add constants as macros
            for name, value in constants.items():
                self.macros[name] = Macro(name, value, source_file="<platform-binding>")
            
            # Add function-like macros
            for name, (params, definition) in macros.items():
                self.macros[name] = Macro(name, definition, params, source_file="<platform-binding>")
                
        except Exception as e:
            if self.verbose:
                print(f"  Warning: Failed to load platform bindings: {e}")
                print("  Continuing with basic macros only")
    
    def add_include_path(self, path: str):
        """Add include search path"""
        abs_path = os.path.abspath(path)
        if abs_path not in self.include_paths:
            self.include_paths.append(abs_path)
            if self.verbose:
                print(f"Added include path: {abs_path}")
    
    def define_macro(self, name: str, value: str = "", params: List[str] = None):
        """Define macro (for command line -D option)"""
        self.macros[name] = Macro(name, value, params, source_file="<command-line>")
    
    def process_file(self, file_path: str, base_dir: str = None, platform: str = None) -> str:
        """Process all preprocessing directives in file"""
        if base_dir is None:
            base_dir = os.path.dirname(os.path.abspath(file_path))
            
        self.add_include_path(base_dir)  # Add file directory
        
        # Load platform bindings before processing
        if self.verbose:
            print("  Loading platform-specific bindings...")
        
        # Read file content for platform detection
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                initial_content = f.read()
        except:
            initial_content = ""
        
        self.load_platform_bindings(platform=platform, auto_detect=True, content=initial_content)
        
        return self.process_includes(file_path, base_dir)
    
    def process_includes(self, file_path: str, base_dir: str = None) -> str:
        """Process all #include directives in file"""
        if base_dir is None:
            base_dir = os.path.dirname(os.path.abspath(file_path))
            
        abs_path = os.path.abspath(file_path)
        
        # Prevent circular references
        if abs_path in self.included_files:
            if self.verbose:
                print(f"Skipping already included file: {os.path.basename(file_path)}")
            return ""
        self.included_files.add(abs_path)
        
        if self.verbose:
            print(f"Processing file: {os.path.basename(file_path)}")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except FileNotFoundError:
            raise PreprocessorError(f"File not found: {file_path}")
        except UnicodeDecodeError:
            raise PreprocessorError(f"Cannot decode file (not UTF-8): {file_path}")
        
        # Process line by line
        result_lines = []
        lines = content.split('\n')
        
        for line_num, line in enumerate(lines, 1):
            processed_line = self._process_line(
                line, file_path, line_num, base_dir, result_lines
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
    
    def _process_line(self, line: str, current_file: str, line_num: int, 
                     base_dir: str, result_lines: List[str]) -> Optional[str]:
        """Process single line content"""
        stripped = line.strip()
        
        # Preserve empty lines and comments directly
        if not stripped or stripped.startswith('//') or stripped.startswith('/*'):
            return line
        
        # Process #include directive
        if stripped.startswith('#include'):
            return self._process_include(stripped, current_file, line_num, base_dir)
        
        # Process #define directive
        elif stripped.startswith('#define'):
            return self._process_define(stripped, current_file, line_num)
        
        # Process #undef directive
        elif stripped.startswith('#undef'):
            return self._process_undef(stripped, current_file, line_num)
        
        # Process conditional compilation (simple support)
        elif stripped.startswith('#ifdef'):
            return self._process_ifdef(stripped, current_file, line_num)
        elif stripped.startswith('#ifndef'):
            return self._process_ifndef(stripped, current_file, line_num)
        elif stripped.startswith('#endif'):
            return self._process_endif(stripped, current_file, line_num)
        
        # Check if it's a real C preprocessor directive vs DTS property
        elif stripped.startswith('#'):
            # Common C preprocessor directives
            c_directives = ['#if', '#ifdef', '#ifndef', '#else', '#elif', '#endif', 
                          '#error', '#warning', '#pragma', '#line']
            
            # Check if it's a C preprocessor directive
            is_c_directive = any(stripped.startswith(directive) for directive in c_directives)
            
            if is_c_directive:
                return f"/* Ignored C preprocessor directive: {stripped} */"
            else:
                # This might be a DTS property (like #address-cells, #cooling-cells etc.), keep as is
                return self._expand_macros(line)
        
        # Regular line - perform macro expansion
        else:
            return self._expand_macros(line)
    
    def _process_include(self, line: str, current_file: str, line_num: int, 
                        base_dir: str) -> List[str]:
        """Process #include directive"""
        include_file = self._parse_include_line(line)
        if not include_file:
            ErrorReporter.warning(f"Invalid #include syntax: {line}", 
                                f"{current_file}:{line_num}")
            return [f"/* Invalid include: {line} */"]
        
        # Skip .h header files (C kernel headers) - only process .dtsi files
        if include_file.endswith('.h'):
            if self.verbose:
                print(f"  Skipping C header file: {include_file}")
            return [f"/* Skipped C header: {include_file} */"]
        
        include_path = self._resolve_include_path(include_file, base_dir)
        if not include_path:
            # For .h files that we can't find, just skip silently
            if include_file.endswith('.h'):
                return [f"/* Skipped missing C header: {include_file} */"]
            
            ErrorReporter.include_file_not_found(
                include_file, current_file, self.include_paths
            )
            return [f"/* Include not found: {include_file} */"]
        
        if self.verbose:
            print(f"  Including: {include_file} -> {os.path.basename(include_path)}")
        
        # Add source annotation
        result = [f"/* Include from {include_path} */"]
        
        try:
            # Recursively process include
            included_content = self.process_includes(include_path, os.path.dirname(include_path))
            result.append(included_content)
            result.append(f"/* End of {include_path} */")
            
        except Exception as e:
            ErrorReporter.compilation_failed(include_path, str(e))
            result.append(f"/* Include failed: {e} */")
        
        return result
    
    def _process_define(self, line: str, current_file: str, line_num: int) -> Optional[str]:
        """Process #define directive"""
        # Parse #define syntax
        match = re.match(r'#define\s+(\w+)(?:\((.*?)\))?\s*(.*)', line)
        if not match:
            ErrorReporter.warning(f"Invalid #define syntax: {line}", 
                                f"{current_file}:{line_num}")
            return f"/* Invalid define: {line} */"
        
        macro_name = match.group(1)
        macro_params = match.group(2)
        macro_value = match.group(3).strip()
        
        # Parse parameters (if function-like macro)
        params = []
        if macro_params:
            params = [p.strip() for p in macro_params.split(',') if p.strip()]
        
        # Create macro definition
        macro = Macro(macro_name, macro_value, params, current_file, line_num)
        self.macros[macro_name] = macro
        
        if self.verbose:
            param_str = f"({', '.join(params)})" if params else ""
            print(f"  Defined macro: {macro_name}{param_str} = {macro_value}")
        
        return f"/* #define {macro_name} {macro_value} */"
    
    def _process_undef(self, line: str, current_file: str, line_num: int) -> Optional[str]:
        """Process #undef directive"""
        match = re.match(r'#undef\s+(\w+)', line)
        if not match:
            ErrorReporter.warning(f"Invalid #undef syntax: {line}", 
                                f"{current_file}:{line_num}")
            return f"/* Invalid undef: {line} */"
        
        macro_name = match.group(1)
        if macro_name in self.macros:
            del self.macros[macro_name]
            if self.verbose:
                print(f"  Undefined macro: {macro_name}")
        
        return f"/* #undef {macro_name} */"
    
    def _process_ifdef(self, line: str, current_file: str, line_num: int) -> Optional[str]:
        """Process #ifdef directive (simple implementation)"""
        match = re.match(r'#ifdef\s+(\w+)', line)
        if not match:
            return f"/* Invalid ifdef: {line} */"
        
        macro_name = match.group(1)
        # Simple implementation: always consider condition as true (real implementation would need conditional compilation stack)
        return f"/* #ifdef {macro_name} (always true in dt-sim) */"
    
    def _process_ifndef(self, line: str, current_file: str, line_num: int) -> Optional[str]:
        """Process #ifndef directive (simple implementation)"""
        match = re.match(r'#ifndef\s+(\w+)', line)
        if not match:
            return f"/* Invalid ifndef: {line} */"
        
        macro_name = match.group(1)
        return f"/* #ifndef {macro_name} (always true in dt-sim) */"
    
    def _process_endif(self, line: str, current_file: str, line_num: int) -> Optional[str]:
        """Process #endif directive"""
        return f"/* #endif */"
    
    def _expand_macros(self, line: str) -> str:
        """Expand macros in line"""
        result = line
        
        # First process function-like macros
        for macro_name, macro in self.macros.items():
            if macro.is_function_like:
                # Match function-like macro calls: MACRO_NAME(arg1, arg2, ...)
                pattern = r'\b' + re.escape(macro_name) + r'\s*\(([^)]*)\)'
                matches = list(re.finditer(pattern, result))
                
                # Replace from back to front, avoiding position offset issues
                for match in reversed(matches):
                    args_str = match.group(1).strip()
                    if args_str:
                        args = [arg.strip() for arg in args_str.split(',')]
                    else:
                        args = []
                    
                    try:
                        expanded = macro.expand(args)
                        result = result[:match.start()] + expanded + result[match.end():]
                    except PreprocessorError as e:
                        # Keep original call, add comment
                        original = match.group(0)
                        result = result[:match.start()] + f"{original} /* ERROR: {e} */" + result[match.end():]
        
        # Then process simple macros
        for macro_name, macro in self.macros.items():
            if not macro.is_function_like:
                # Only replace complete identifiers
                pattern = r'\b' + re.escape(macro_name) + r'\b'
                if re.search(pattern, result):
                    result = re.sub(pattern, macro.value, result)
        
        # Handle undefined constants - replace identifiers that look like constants with 0
        # This handles constants like IMX95_CLK_*, IMX95_PAD_*, IMX95_PERF_* etc.
        undefined_const_pattern = r'\b[A-Z][A-Z0-9_]{4,}\b'
        undefined_matches = re.findall(undefined_const_pattern, result)
        
        for match in set(undefined_matches):  # Use set to avoid duplicates
            # Skip known macros
            if match not in self.macros:
                # Replace undefined constants with 0 (don't add comments to avoid parsing issues)
                pattern = r'\b' + re.escape(match) + r'\b'
                result = re.sub(pattern, '0', result)
        
        return result
    
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
    
    def get_statistics(self) -> Dict[str, any]:
        """Get preprocessing statistics"""
        return {
            "included_files": list(self.included_files),
            "include_paths": self.include_paths,
            "defined_macros": list(self.macros.keys()),
            "total_files_processed": len(self.included_files)
        }
    
    def reset(self):
        """Reset preprocessor state (for processing new files)"""
        self.included_files.clear()
        # Keep include_paths and user-defined macros
        
        # Re-setup built-in macros
        self._setup_builtin_macros()


# Helper functions for testing

def create_test_files():
    """Create test DTS files"""
    
    # Create test directory
    test_dir = Path("test_preprocessor")
    test_dir.mkdir(exist_ok=True)
    
    # common.dtsi
    common_dtsi = """
/* Common definitions */
#define UART_CLOCK_FREQ 50000000
#define I2C_CLOCK_FREQ  100000
#define SPI_CLOCK_FREQ  25000000

/* Common memory regions */
memory: memory@80000000 {
    device_type = "memory";
    reg = <0x80000000 0x40000000>;
};

/* Common interrupt controller */
intc: interrupt-controller {
    compatible = "arm,gic-400";
    #interrupt-cells = <3>;
    interrupt-controller;
    reg = <0x1000000 0x1000>;
};
"""
    
    # board.dtsi
    board_dtsi = """
#include "common.dtsi"

/* Board specific definitions */
#define GPIO_BASE 0x12000000
#define UART_BASE 0x12340000

/ {
    model = "Test Board";
    compatible = "test,board";
    
    cpus {
        #address-cells = <1>;
        #size-cells = <0>;
        
        cpu@0 {
            device_type = "cpu";
            compatible = "arm,cortex-a53";
            reg = <0>;
            clock-frequency = <UART_CLOCK_FREQ>;
        };
    };
};
"""
    
    # main.dts
    main_dts = """
/dts-v1/;

#include "board.dtsi"

/ {
    uart0: uart@UART_BASE {
        compatible = "ns16550a";
        reg = <UART_BASE 0x100>;
        interrupts = <&intc 0 4 1>;
        clock-frequency = <UART_CLOCK_FREQ>;
    };
    
    i2c0: i2c@12370000 {
        compatible = "simple-i2c";
        reg = <0x12370000 0x100>;
        clock-frequency = <I2C_CLOCK_FREQ>;
    };
};
"""
    
    # Write files
    with open(test_dir / "common.dtsi", 'w') as f:
        f.write(common_dtsi)
    
    with open(test_dir / "board.dtsi", 'w') as f:
        f.write(board_dtsi)
    
    with open(test_dir / "main.dts", 'w') as f:
        f.write(main_dts)
    
    return test_dir


def test_preprocessor():
    """Test preprocessor functionality"""
    print("=== Test DTS Preprocessor ===")
    
    # Create test files
    test_dir = create_test_files()
    
    try:
        # Create preprocessor
        preprocessor = Preprocessor(verbose=True)
        
        # Process main file
        main_file = test_dir / "main.dts"
        result = preprocessor.process_file(str(main_file))
        
        print("\n=== Preprocessing Results ===")
        print(result)
        
        # Display statistics
        stats = preprocessor.get_statistics()
        print(f"\n=== Statistics ===")
        print(f"Files processed: {stats['total_files_processed']}")
        print(f"Include paths: {stats['include_paths']}")
        print(f"Defined macros: {stats['defined_macros']}")
        
        print("\n✅ Preprocessor test completed")
        
    except Exception as e:
        print(f"❌ Preprocessor test failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Cleanup test files
        import shutil
        if test_dir.exists():
            shutil.rmtree(test_dir)


if __name__ == "__main__":
    test_preprocessor()
