"""
commands/fdtoverlay_command.py - fdtoverlay command implementation
Simulates fdtoverlay tool, merging base DTB and overlay DTBO into final DTB
"""

import os
import sys

# Import core merge logic
from simulators.fdtoverlay_merger import FDTOverlayMerger

def execute(args) -> int:
    """Execute fdtoverlay command"""
    try:
        if args.verbose:
            print(f"dt-sim fdtoverlay: merging {os.path.basename(args.base)} + {len(args.overlays)} overlays -> {os.path.basename(args.output)}")
        
        # Check input files
        if not os.path.exists(args.base):
            print(f"[ERROR] Base file not found: {args.base}")
            return 1
        
        for overlay_file in args.overlays:
            if not os.path.exists(overlay_file):
                print(f"[ERROR] Overlay file not found: {overlay_file}")
                return 1
        
        # Create output directory
        output_dir = os.path.dirname(args.output)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        # Use core merge logic
        merger = FDTOverlayMerger()
        
        if args.verbose:
            print("  Step 1: Loading base DTB...")
        
        if not merger.load_base_dtb(args.base):
            return 1
        
        if args.verbose:
            print("  Step 2: Loading overlay DTBs...")
        
        for overlay_file in args.overlays:
            if not merger.add_overlay_dtb(overlay_file):
                return 1
        
        if args.verbose:
            print("  Step 3: Merging overlays...")
        
        if not merger.merge_overlays(args.verbose):
            return 1
        
        if args.show_changes:
            merger.show_merge_summary()
        
        if args.validate_only:
            print("[OK] Validation completed successfully")
            return 0
        
        if args.verbose:
            print("  Step 4: Generating merged DTB...")
        
        if not merger.generate_merged_dtb(args.output, args.verbose):
            return 1
        
        if args.show_merge:
            merger.show_merge_summary()
        
        print(f"[OK] Successfully merged DTB: {os.path.basename(args.output)}")
        return 0
        
    except KeyboardInterrupt:
        print("\n[WARN] Operation interrupted by user")
        return 130
    except Exception as e:
        print(f"[ERROR] fdtoverlay execution failed: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1