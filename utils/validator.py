"""
utils/validator.py - Device Tree Validator
Comprehensive validation for DTS/DTB files and overlays
"""

import re
from typing import List, Dict, Set, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum


class ValidationLevel(Enum):
    INFO = "info"
    WARNING = "warning"  
    ERROR = "error"


@dataclass
class ValidationResult:
    level: ValidationLevel
    message: str
    location: str = ""
    line: Optional[int] = None
    column: Optional[int] = None
    
    def __str__(self):
        location_info = f" at {self.location}" if self.location else ""
        line_info = f":line {self.line}" if self.line else ""
        return f"[{self.level.value.upper()}]{location_info}{line_info}: {self.message}"


class DeviceTreeValidator:
    """Comprehensive Device Tree Validator"""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.results: List[ValidationResult] = []
        
        # Standard DT properties that should be present
        self.required_root_properties = {
            '#address-cells', '#size-cells'
        }
        
        # Properties that typically have specific value formats
        self.property_formats = {
            'compatible': r'^[a-zA-Z0-9_-]+([,][a-zA-Z0-9_-]+)?$',  # vendor,device or just device
            'status': r'^(okay|disabled|fail|fail-sss)$',
            'phandle': r'^\d+$',
            'reg': r'^<.*>$',  # Should be in angle brackets
        }
        
        # Node name patterns
        self.node_name_pattern = r'^[a-zA-Z0-9_-]+(@[0-9a-fA-F,]+)?$'
        
    def validate_dtb_file(self, dtb_file_path: str) -> List[ValidationResult]:
        """
        Validate a compiled DTB text file
        
        Args:
            dtb_file_path: Path to the .dtb.txt file
            
        Returns:
            List of validation results
        """
        self.results = []
        
        try:
            with open(dtb_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            self.results.append(ValidationResult(
                ValidationLevel.ERROR,
                f"Failed to read DTB file: {e}",
                dtb_file_path
            ))
            return self.results
            
        if self.verbose:
            print(f"Validating DTB file: {dtb_file_path}")
            
        # Parse the DTB content
        parsed_data = self._parse_dtb_content(content)
        
        # Run all validation checks
        self._validate_structure(parsed_data, dtb_file_path)
        self._validate_syntax(parsed_data, dtb_file_path)
        self._validate_references(parsed_data, dtb_file_path)
        self._validate_properties(parsed_data, dtb_file_path)
        self._validate_node_names(parsed_data, dtb_file_path)
        
        return self.results
    
    def validate_overlay_application(self, original_dtb: str, final_dtb: str, 
                                   expected_changes: Dict[str, Dict[str, Any]]) -> List[ValidationResult]:
        """
        Validate that overlay/reference changes were applied correctly
        
        Args:
            original_dtb: Path to original DTB before overlay
            final_dtb: Path to final DTB after overlay  
            expected_changes: Dict of {node_path: {property: expected_value}}
            
        Returns:
            List of validation results
        """
        self.results = []
        
        try:
            with open(final_dtb, 'r', encoding='utf-8') as f:
                final_content = f.read()
        except Exception as e:
            self.results.append(ValidationResult(
                ValidationLevel.ERROR,
                f"Failed to read final DTB: {e}",
                final_dtb
            ))
            return self.results
            
        parsed_final = self._parse_dtb_content(final_content)
        
        # Check each expected change
        for node_path, expected_props in expected_changes.items():
            node_data = self._find_node_in_parsed_data(parsed_final, node_path)
            
            if not node_data:
                self.results.append(ValidationResult(
                    ValidationLevel.ERROR,
                    f"Expected node not found: {node_path}",
                    final_dtb
                ))
                continue
                
            for prop_name, expected_value in expected_props.items():
                actual_value = self._get_property_value(node_data, prop_name)
                
                if actual_value is None:
                    self.results.append(ValidationResult(
                        ValidationLevel.ERROR,
                        f"Expected property '{prop_name}' not found in {node_path}",
                        final_dtb
                    ))
                elif not self._values_match(actual_value, expected_value):
                    self.results.append(ValidationResult(
                        ValidationLevel.ERROR,
                        f"Property '{prop_name}' in {node_path}: expected '{expected_value}', got '{actual_value}'",
                        final_dtb
                    ))
                else:
                    self.results.append(ValidationResult(
                        ValidationLevel.INFO,
                        f"OK Property '{prop_name}' in {node_path} correctly set to '{actual_value}'",
                        final_dtb
                    ))
                    
        return self.results
    
    def _parse_dtb_content(self, content: str) -> Dict[str, Any]:
        """Parse DTB text content into structured data"""
        lines = content.split('\n')
        data = {
            'nodes': {},
            'phandle_table': {},
            'root_properties': {},
            'dts_version': None,
            'source_file': None,
        }
        
        current_node_path = ""
        current_node = None
        in_phandle_table = False
        
        for i, line in enumerate(lines, 1):
            line = line.strip()
            
            # Skip comments and empty lines
            if not line or line.startswith('/*') or line.startswith('*'):
                # Extract source file info
                if 'Source file:' in line:
                    data['source_file'] = line.split('Source file:')[1].strip().rstrip('*/')
                # Extract phandle table info  
                elif 'phandle_map:' in line or in_phandle_table:
                    in_phandle_table = True
                    if ':' in line and '0x' in line:
                        # Parse phandle entry: label: 0x01 (/path)
                        match = re.search(r'(\w+):\s*0x([0-9a-fA-F]+)\s*\(([^)]+)\)', line)
                        if match:
                            label, phandle, path = match.groups()
                            data['phandle_table'][label] = {
                                'phandle': int(phandle, 16),
                                'path': path
                            }
                    elif '}' in line:
                        in_phandle_table = False
                continue
                
            # DTS version
            if line.startswith('/dts-v1/'):
                data['dts_version'] = line
                continue
                
            # Node definitions
            if '{' in line and not '=' in line:
                # Extract node name and path
                node_line = line.replace('{', '').strip()
                
                # Handle labels (gpio: gpio@12380000)
                if ':' in node_line:
                    label_part, node_name = node_line.split(':', 1)
                    label = label_part.strip()
                    node_name = node_name.strip()
                else:
                    label = None
                    node_name = node_line
                
                # Build node path
                if node_name == '/':
                    current_node_path = '/'
                else:
                    if current_node_path == '/':
                        current_node_path = f'/{node_name}'
                    else:
                        current_node_path = f'{current_node_path}/{node_name}'
                
                current_node = {
                    'name': node_name,
                    'path': current_node_path,
                    'label': label,
                    'properties': {},
                    'children': [],
                    'line': i
                }
                data['nodes'][current_node_path] = current_node
                continue
                
            # Property definitions
            if '=' in line and current_node:
                prop_line = line.rstrip(';').strip()
                if '=' in prop_line:
                    prop_name, prop_value = prop_line.split('=', 1)
                    prop_name = prop_name.strip()
                    prop_value = prop_value.strip()
                    
                    # Remove source comments
                    if '/*' in prop_value:
                        prop_value = prop_value.split('/*')[0].strip()
                    
                    # Remove trailing semicolons and quotes
                    prop_value = prop_value.rstrip(';').strip()
                    if prop_value.endswith('";'):
                        prop_value = prop_value[:-2]
                    elif prop_value.endswith('"'):
                        prop_value = prop_value[:-1]
                    if prop_value.startswith('"'):
                        prop_value = prop_value[1:]
                    
                    current_node['properties'][prop_name] = {
                        'value': prop_value,
                        'line': i
                    }
                    
                    # If this is root node, also add to root_properties
                    if current_node_path == '/':
                        data['root_properties'][prop_name] = prop_value
                continue
                
            # Node closing
            if line == '};':
                # Move up one level in the path
                if current_node_path and current_node_path != '/':
                    current_node_path = '/'.join(current_node_path.split('/')[:-1])
                    if not current_node_path:
                        current_node_path = '/'
                        current_node = data['nodes'].get('/')
                    else:
                        current_node = data['nodes'].get(current_node_path)
                else:
                    current_node = None
                    current_node_path = ""
                    
        return data
    
    def _validate_structure(self, data: Dict[str, Any], file_path: str):
        """Validate basic DTB structure"""
        
        # Check DTS version
        if not data.get('dts_version'):
            self.results.append(ValidationResult(
                ValidationLevel.ERROR,
                "Missing /dts-v1/ declaration",
                file_path
            ))
            
        # Check root node exists
        if '/' not in data['nodes']:
            self.results.append(ValidationResult(
                ValidationLevel.ERROR,
                "Missing root node '/'",
                file_path
            ))
            return
            
        # Check root node has required properties
        root_props = data['root_properties']
        for required_prop in self.required_root_properties:
            if required_prop not in root_props:
                self.results.append(ValidationResult(
                    ValidationLevel.WARNING,
                    f"Root node missing recommended property: {required_prop}",
                    file_path
                ))
                
        if self.verbose:
            self.results.append(ValidationResult(
                ValidationLevel.INFO,
                f"OK Found {len(data['nodes'])} nodes in device tree",
                file_path
            ))
    
    def _validate_syntax(self, data: Dict[str, Any], file_path: str):
        """Validate DTS syntax"""
        
        for path, node in data['nodes'].items():
            # Validate node names
            if not re.match(self.node_name_pattern, node['name']) and node['name'] != '/':
                self.results.append(ValidationResult(
                    ValidationLevel.WARNING,
                    f"Node name '{node['name']}' doesn't follow standard naming convention",
                    file_path,
                    node.get('line')
                ))
                
    def _validate_references(self, data: Dict[str, Any], file_path: str):
        """Validate phandle references and labels"""
        
        phandle_table = data.get('phandle_table', {})
        found_references = set()
        
        # Find all phandle references in properties
        for path, node in data['nodes'].items():
            for prop_name, prop_data in node['properties'].items():
                prop_value = prop_data['value']
                
                # Look for phandle references (&label)
                refs = re.findall(r'&\s*(\w+)', prop_value)
                for ref in refs:
                    found_references.add(ref)
                    
                    if ref not in phandle_table:
                        self.results.append(ValidationResult(
                            ValidationLevel.WARNING,
                            f"Unresolved phandle reference: &{ref} in {path}:{prop_name}",
                            file_path,
                            prop_data.get('line')
                        ))
                    else:
                        if self.verbose:
                            self.results.append(ValidationResult(
                                ValidationLevel.INFO,
                                f"OK Phandle reference &{ref} resolves to {phandle_table[ref]['path']}",
                                file_path
                            ))
                            
        # Check for unused phandles
        for label in phandle_table:
            if label not in found_references:
                self.results.append(ValidationResult(
                    ValidationLevel.INFO,
                    f"Phandle '{label}' defined but not referenced",
                    file_path
                ))
                
    def _validate_properties(self, data: Dict[str, Any], file_path: str):
        """Validate property values and formats"""
        
        for path, node in data['nodes'].items():
            for prop_name, prop_data in node['properties'].items():
                prop_value = prop_data['value'].strip('"')
                
                # Check specific property formats
                if prop_name in self.property_formats:
                    pattern = self.property_formats[prop_name]
                    if not re.match(pattern, prop_value):
                        self.results.append(ValidationResult(
                            ValidationLevel.WARNING,
                            f"Property '{prop_name}' value '{prop_value}' doesn't match expected format",
                            file_path,
                            prop_data.get('line')
                        ))
                        
                # Check for empty values
                if not prop_value:
                    self.results.append(ValidationResult(
                        ValidationLevel.WARNING,
                        f"Property '{prop_name}' has empty value",
                        file_path,
                        prop_data.get('line')
                    ))
                    
    def _validate_node_names(self, data: Dict[str, Any], file_path: str):
        """Validate node naming conventions"""
        
        for path, node in data['nodes'].items():
            name = node['name']
            
            # Skip root node
            if name == '/':
                continue
                
            # Check for proper addressing
            if '@' in name:
                name_part, address_part = name.split('@', 1)
                
                # Check if node has reg property when it has an address
                if 'reg' not in node['properties']:
                    self.results.append(ValidationResult(
                        ValidationLevel.WARNING,
                        f"Node '{name}' has address but no 'reg' property",
                        file_path,
                        node.get('line')
                    ))
                    
            # Check for duplicate node names at the same level
            # This would require more complex parent-child tracking
                    
    def _find_node_in_parsed_data(self, data: Dict[str, Any], node_path: str) -> Optional[Dict[str, Any]]:
        """Find a node by path in parsed data"""
        return data['nodes'].get(node_path)
    
    def _get_property_value(self, node_data: Dict[str, Any], prop_name: str) -> Optional[str]:
        """Get property value from node data"""
        prop_data = node_data['properties'].get(prop_name)
        if prop_data:
            return prop_data['value'].strip('"')
        return None
    
    def _values_match(self, actual: str, expected: Any) -> bool:
        """Check if actual value matches expected value"""
        # Handle string comparisons
        if isinstance(expected, str):
            return actual == expected
        
        # Handle numeric comparisons
        if isinstance(expected, (int, float)):
            try:
                # Try to extract numeric value from angle brackets
                if '<' in actual and '>' in actual:
                    # Look for hex values (0x50) or decimal values (80)
                    hex_matches = re.findall(r'0x([0-9a-fA-F]+)', actual)
                    if hex_matches:
                        return int(hex_matches[0], 16) == expected
                    
                    # Look for decimal values
                    dec_matches = re.findall(r'(\d+)', actual)
                    if dec_matches:
                        return int(dec_matches[0]) == expected
                        
                return int(actual) == expected
            except ValueError:
                pass
                
        return str(actual) == str(expected)
    
    def print_results(self, show_info: bool = True):
        """Print validation results in a formatted way"""
        
        if not self.results:
            print("✓ No validation issues found")
            return
            
        error_count = sum(1 for r in self.results if r.level == ValidationLevel.ERROR)
        warning_count = sum(1 for r in self.results if r.level == ValidationLevel.WARNING)  
        info_count = sum(1 for r in self.results if r.level == ValidationLevel.INFO)
        
        print(f"\n=== VALIDATION RESULTS ===")
        print(f"Errors: {error_count}, Warnings: {warning_count}, Info: {info_count}")
        print()
        
        # Print errors first
        for result in self.results:
            if result.level == ValidationLevel.ERROR:
                print(f"[ERROR] {result}")
                
        # Print warnings  
        for result in self.results:
            if result.level == ValidationLevel.WARNING:
                print(f"[WARN]  {result}")
                
        # Print info if requested
        if show_info:
            for result in self.results:
                if result.level == ValidationLevel.INFO:
                    print(f"[INFO]  {result}")


def create_validation_test_cases():
    """Create test cases for validating node reference functionality"""
    return {
        # Expected changes from the node reference test
        '/gpio@12380000': {
            'status': 'disabled',
            'pinctrl-names': 'default',
            # Note: pinctrl-0 has a phandle reference, so we'll check format instead
        },
        '/uart@12340000': {
            'status': 'disabled',
            'current-speed': 115200,
        },
        '/i2c@12360000': {
            'clock-frequency': 100000,
            'status': 'okay',  # Should remain okay
        },
        '/i2c@12360000/eeprom@50': {
            'compatible': 'atmel,24c02',
            'reg': 0x50,
            'pagesize': 8,
        },
        '/i2c@12360000/rtc@68': {
            'compatible': 'dallas,ds3231', 
            'reg': 0x68,
        }
    }


if __name__ == "__main__":
    import os
    
    # Example usage
    validator = DeviceTreeValidator(verbose=True)
    
    # Test basic validation
    dtb_file = "output/node_references_complete.dtb.txt"
    if os.path.exists(dtb_file):
        results = validator.validate_dtb_file(dtb_file)
        validator.print_results()
        
        # Test overlay validation
        expected_changes = create_validation_test_cases()
        overlay_results = validator.validate_overlay_application(
            "output/node_references_fixed.dtb.txt",  # original (without refs)  
            "output/node_references_complete.dtb.txt",  # final (with refs)
            expected_changes
        )
        
        print("\n=== OVERLAY VALIDATION ===")
        for result in overlay_results:
            if result.level == ValidationLevel.ERROR:
                print(f"[ERROR] {result}")
            elif result.level == ValidationLevel.WARNING:
                print(f"[WARN]  {result}")
            else:
                print(f"[OK]    {result}")
    else:
        print(f"DTB file not found: {dtb_file}")
        print("Please run the node references test first:")
        print("python dt-sim.py dtc test_node_references.dts -o output/node_references_complete.dtb.txt -v")
