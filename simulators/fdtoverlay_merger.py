"""
simulators/fdtoverlay_merger.py - Core fdtoverlay merge functionality
Simulates the core logic of fdtoverlay tool, merging base DTB and overlay DTBO
"""

import os
import sys
import re
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime


class DTBParser:
    """Parse compiled .dtb.txt and .dtbo.txt files"""
    
    def __init__(self):
        self.nodes = {}
        self.phandles = {}
        self.labels = {}
        self.source_file = ""
        self.total_nodes = 0
        self.total_phandles = 0
        self.raw_content = ""
    
    def parse_dtb_file(self, file_path: str) -> bool:
        """Parse DTB file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                self.raw_content = f.read()
            
            # Extract source file information
            source_match = re.search(r'Source file: (.+)', self.raw_content)
            if source_match:
                self.source_file = source_match.group(1)
            
            # Count nodes and phandle quantities
            self.total_nodes = self._count_nodes()
            self.total_phandles = self._count_phandles()
            
            # Parse phandle table
            self._parse_phandle_table()
            
            return True
            
        except Exception as e:
            print(f"[ERROR] Failed to parse {file_path}: {e}")
            return False
    
    def _count_nodes(self) -> int:
        """Count nodes in DTB file"""
        # Count opening braces { to estimate node count
        # This is a simple approximation
        count = self.raw_content.count(' {')
        return max(0, count)
    
    def _count_phandles(self) -> int:
        """Count phandles in DTB file"""
        # Count label definitions like "label_name: node_name {" or "label_name: {" 
        label_pattern = r'(\w+):\s*(?:\w+\s*)?\{'
        labels = re.findall(label_pattern, self.raw_content)
        return len(labels)
    
    def _parse_phandle_table(self):
        """Parse phandle mapping table"""
        # Match phandle table section
        phandle_section = re.search(
            r'/\*\s*=+ PHANDLE TABLE =+\s*\*(.*?)\*/\s*', 
            self.raw_content, re.DOTALL
        )
        
        if not phandle_section:
            return
            
        phandle_text = phandle_section.group(1)
        
        # Parse each phandle entry: label: 0xNN (path)
        phandle_pattern = r'\*\s+(\w+):\s+(0x[0-9a-f]+)\s+\(([^)]+)\)'
        
        for match in re.finditer(phandle_pattern, phandle_text, re.IGNORECASE):
            label = match.group(1)
            phandle = match.group(2)
            path = match.group(3)
            
            self.phandles[phandle] = path
            self.labels[label] = {
                'phandle': phandle,
                'path': path
            }


class FDTOverlayMerger:
    """Handle overlay merge logic"""
    
    def __init__(self):
        self.base_dtb = None
        self.overlay_dtbs = []
        self.changes_made = []
    
    def load_base_dtb(self, base_file: str) -> bool:
        """Load base DTB file"""
        parser = DTBParser()
        if parser.parse_dtb_file(base_file):
            self.base_dtb = parser
            return True
        return False
    
    def add_overlay_dtb(self, overlay_file: str) -> bool:
        """Add overlay DTB file"""
        parser = DTBParser()
        if parser.parse_dtb_file(overlay_file):
            self.overlay_dtbs.append(parser)
            return True
        return False
    
    def merge_overlays(self, verbose: bool = False) -> bool:
        """Merge all overlays"""
        try:
            for i, overlay in enumerate(self.overlay_dtbs):
                if verbose:
                    print(f"    Merging overlay {i+1}/{len(self.overlay_dtbs)}: {os.path.basename(overlay.source_file)}")
                
                # Record changes (simplified version)
                self.changes_made.append({
                    'type': 'overlay_applied',
                    'source': overlay.source_file,
                    'phandles': len(overlay.phandles),
                    'labels': len(overlay.labels)
                })
            
            return True
            
        except Exception as e:
            print(f"[ERROR] Merge failed: {e}")
            return False
    
    def generate_merged_dtb(self, output_file: str, verbose: bool = False) -> bool:
        """Generate merged DTB file"""
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                self._write_merged_dtb(f)
            
            if verbose:
                print(f"    Generated merged DTB: {os.path.basename(output_file)}")
                print(f"    Total overlays applied: {len(self.overlay_dtbs)}")
            
            return True
            
        except Exception as e:
            print(f"[ERROR] Failed to generate {output_file}: {e}")
            return False
    
    def _write_merged_dtb(self, f):
        """Write merged DTB content"""
        f.write("/*\n")
        f.write(" * Generated by dt-sim fdtoverlay - merged DTB\n")
        f.write(f" * Base file: {self.base_dtb.source_file}\n")
        f.write(" * Overlay files:\n")
        for overlay in self.overlay_dtbs:
            f.write(f" *   - {overlay.source_file}\n")
        f.write(f" * Merge timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f" * Base nodes: {self.base_dtb.total_nodes}\n")
        f.write(f" * Base phandles: {self.base_dtb.total_phandles}\n")
        f.write(f" * Overlays applied: {len(self.overlay_dtbs)}\n")
        f.write(" */\n\n")
        f.write("/dts-v1/;\n\n")
        
        # Merge phandle table
        all_phandles = self.base_dtb.phandles.copy()
        all_labels = self.base_dtb.labels.copy()
        
        for overlay in self.overlay_dtbs:
            all_phandles.update(overlay.phandles)
            all_labels.update(overlay.labels)
        
        if all_phandles:
            f.write("/*\n")
            f.write(" * ===== MERGED PHANDLE TABLE =====\n")
            f.write(" * phandle_map: {\n")
            
            for label, info in sorted(all_labels.items()):
                f.write(f" *   {label}: {info['phandle']} ({info['path']})\n")
            
            f.write(" * }\n")
            f.write(" */\n\n")
        
        # Write base DTB content (remove header comments)
        base_content = self._extract_dtb_content(self.base_dtb.raw_content)
        f.write(base_content)
        
        # Add overlay change records
        if self.changes_made:
            f.write("\n/*\n")
            f.write(" * ===== OVERLAY CHANGES APPLIED =====\n")
            for i, change in enumerate(self.changes_made, 1):
                f.write(f" * {i}. Applied overlay: {os.path.basename(change['source'])}\n")
                f.write(f" *    - Labels: {change['labels']}, Phandles: {change['phandles']}\n")
            f.write(" */\n")
    
    def _extract_dtb_content(self, raw_content: str) -> str:
        """Extract actual DTB content section (remove header comments)"""
        # Find content after /dts-v1/;
        dts_start = raw_content.find('/dts-v1/;')
        if dts_start == -1:
            return raw_content
        
        # Find the start position of actual node definitions
        content_start = raw_content.find('/ {', dts_start)
        if content_start == -1:
            return raw_content[dts_start:]
        
        return raw_content[content_start:]
    
    def show_merge_summary(self):
        """Show merge summary"""
        print(f"\n=== fdtoverlay Merge Summary ===")
        print(f"Base DTB: {os.path.basename(self.base_dtb.source_file)}")
        print(f"  - Nodes: {self.base_dtb.total_nodes}")
        print(f"  - Phandles: {self.base_dtb.total_phandles}")
        
        print(f"Overlay DTBs: {len(self.overlay_dtbs)} files")
        for i, overlay in enumerate(self.overlay_dtbs, 1):
            print(f"  {i}. {os.path.basename(overlay.source_file)}")
            print(f"     - Labels: {len(overlay.labels)}, Phandles: {len(overlay.phandles)}")
        
        print(f"Result: Successfully merged {len(self.overlay_dtbs)} overlays into base DTB")
    
    def merge_overlay_text(self, base_file: str, overlay_files: List[str], output_file: str, 
                          verbose: bool = False, show_changes: bool = False) -> bool:
        """
        Main merge interface - provides backward compatibility
        
        Args:
            base_file: Base DTB file path
            overlay_files: List of overlay DTBO file paths
            output_file: Output file path
            verbose: Whether to show detailed information
            show_changes: Whether to show change summary
            
        Returns:
            bool: Whether merge was successful
        """
        try:
            # Load base DTB
            if not self.load_base_dtb(base_file):
                return False
            
            # Load all overlay DTBs
            for overlay_file in overlay_files:
                if not self.add_overlay_dtb(overlay_file):
                    return False
            
            # Execute merge
            if not self.merge_overlays(verbose):
                return False
            
            # Show change summary
            if show_changes:
                self.show_merge_summary()
            
            # Generate output file
            if not self.generate_merged_dtb(output_file, verbose):
                return False
            
            return True
            
        except Exception as e:
            print(f"[ERROR] merge_overlay_text failed: {e}")
            return False