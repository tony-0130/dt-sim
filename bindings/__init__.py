"""
Bindings management for dt-sim

This module provides platform-specific and common device tree bindings.
It supports loading constants and macros based on platform detection or explicit specification.
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

class BindingManager:
    """Manages device tree bindings for multiple platforms"""
    
    def __init__(self, bindings_dir: str = None):
        if bindings_dir is None:
            bindings_dir = Path(__file__).parent
        self.bindings_dir = Path(bindings_dir)
        self.common_dir = self.bindings_dir / "common"
        self.platforms_dir = self.bindings_dir / "platforms"
        
        # Loaded bindings cache
        self._constants_cache = {}
        self._macros_cache = {}
        
    def load_common_bindings(self) -> Tuple[Dict[str, str], Dict[str, Tuple[List[str], str]]]:
        """Load all common bindings"""
        constants = {}
        macros = {}
        
        # Load all JSON files in common directory
        for json_file in self.common_dir.glob("*.json"):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Load constants
                if 'constants' in data:
                    constants.update(data['constants'])
                
                # Load macros
                if 'macros' in data:
                    for name, macro_def in data['macros'].items():
                        params = macro_def.get('params', [])
                        definition = macro_def.get('definition', '')
                        macros[name] = (params, definition)
                        
            except Exception as e:
                print(f"Warning: Failed to load common binding {json_file}: {e}")
        
        return constants, macros
    
    def load_platform_bindings(self, platform: str) -> Tuple[Dict[str, str], Dict[str, Tuple[List[str], str]]]:
        """Load platform-specific bindings"""
        platform_file = self.platforms_dir / f"{platform}.json"
        
        if not platform_file.exists():
            print(f"Warning: Platform bindings not found: {platform}")
            return {}, {}
        
        try:
            with open(platform_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            constants = {}
            macros = {}
            
            # Load included common bindings first
            if 'includes' in data:
                for include in data['includes']:
                    include_constants, include_macros = self._load_include(include)
                    constants.update(include_constants)
                    macros.update(include_macros)
            
            # Load platform-specific constants (can override common ones)
            if 'constants' in data:
                constants.update(data['constants'])
            
            # Load platform-specific macros
            if 'macros' in data:
                for name, macro_def in data['macros'].items():
                    params = macro_def.get('params', [])
                    definition = macro_def.get('definition', '')
                    macros[name] = (params, definition)
            
            return constants, macros
            
        except Exception as e:
            print(f"Error: Failed to load platform binding {platform}: {e}")
            return {}, {}
    
    def _load_include(self, include_path: str) -> Tuple[Dict[str, str], Dict[str, Tuple[List[str], str]]]:
        """Load included binding file"""
        include_file = self.bindings_dir / f"{include_path}.json"
        
        constants = {}
        macros = {}
        
        try:
            with open(include_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if 'constants' in data:
                constants.update(data['constants'])
            
            if 'macros' in data:
                for name, macro_def in data['macros'].items():
                    params = macro_def.get('params', [])
                    definition = macro_def.get('definition', '')
                    macros[name] = (params, definition)
                    
        except Exception as e:
            print(f"Warning: Failed to load include {include_path}: {e}")
        
        return constants, macros
    
    def detect_platform(self, content: str) -> Optional[str]:
        """Auto-detect platform from DTS content"""
        # Look for compatible strings in all platform files
        for platform_file in self.platforms_dir.glob("*.json"):
            try:
                with open(platform_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                if 'compatible_strings' in data:
                    for compat_str in data['compatible_strings']:
                        if compat_str in content:
                            platform_name = platform_file.stem
                            return platform_name
                            
            except Exception:
                continue
        
        return None
    
    def get_all_platforms(self) -> List[str]:
        """Get list of all available platforms"""
        return [f.stem for f in self.platforms_dir.glob("*.json")]
    
    def load_bindings(self, platform: str = None, auto_detect: bool = True, content: str = "") -> Tuple[Dict[str, str], Dict[str, Tuple[List[str], str]]]:
        """Load bindings for specified platform or auto-detect"""
        
        # Auto-detect platform if requested and content provided
        if auto_detect and content and not platform:
            detected = self.detect_platform(content)
            if detected:
                platform = detected
                print(f"Auto-detected platform: {platform}")
        
        if platform:
            # Load platform-specific bindings (includes common ones)
            return self.load_platform_bindings(platform)
        else:
            # Load only common bindings
            return self.load_common_bindings()

__all__ = ['BindingManager']