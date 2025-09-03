#!/usr/bin/env python3
"""
dt-sim.py - Device Tree Simulation Tool Main Program
"""

import os
import sys
import argparse

# Add current directory to module search path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

def setup_dtc_parser(subparser):
    """Setup dt-sim dtc subcommand"""
    dtc_parser = subparser.add_parser(
        'dtc',
        help='Simulate dtc compilation from DTS to text DTB',
        description='Compile .dts files into readable .dtb.txt files'
    )
    
    dtc_parser.add_argument('input', help='Input .dts file')
    dtc_parser.add_argument('-o', '--output', required=True, help='Output .dtb.txt file')
    dtc_parser.add_argument('-v', '--verbose', action='store_true', help='Show detailed process')
    dtc_parser.add_argument('--show-includes', action='store_true', help='Show include processing')
    dtc_parser.add_argument('--check-only', action='store_true', help='Only validate syntax, do not generate output')
    dtc_parser.add_argument('-I', '--include', action='append', dest='include_paths', 
                           help='Add include search path')
    dtc_parser.add_argument('--platform', help='Specify platform (e.g. imx95, rk3588), auto-detect if not specified')
    
    # Validation options
    dtc_parser.add_argument('--validate', action='store_true', 
                           help='Automatically validate DTB output after compilation')
    dtc_parser.add_argument('--test-overlays', action='store_true',
                           help='Test node reference overlay functionality (for test files)')
    dtc_parser.add_argument('--no-warnings', action='store_true',
                           help='Do not show warnings during validation')
    
    return dtc_parser


def setup_fdtoverlay_parser(subparser):
    """Setup dt-sim fdtoverlay subcommand"""
    fdto_parser = subparser.add_parser(
        'fdtoverlay',
        help='Simulate fdtoverlay merge',
        description='Merge base DTB and overlay DTBO into final DTB'
    )
    
    fdto_parser.add_argument('base', help='Base .dtb.txt file')
    fdto_parser.add_argument('overlays', nargs='+', help='One or more .dtbo.txt files')
    fdto_parser.add_argument('-o', '--output', required=True, help='Output final .dtb.txt file')
    fdto_parser.add_argument('-v', '--verbose', action='store_true', help='Show detailed process')
    fdto_parser.add_argument('--show-merge', action='store_true', help='Show merge process')
    fdto_parser.add_argument('--show-changes', action='store_true', help='Show nodes that will be modified')
    fdto_parser.add_argument('--validate-only', action='store_true', help='Only validate, do not generate output')
    
    return fdto_parser

def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        prog='dt-sim',
        description='Device Tree Simulation Tool - Simulates dtc and fdtoverlay behavior',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Usage examples:
  # Compile DTS to text DTB
  python dt-sim.py dtc base.dts -o base.dtb.txt --verbose
  
  # Merge base and overlay
  python dt-sim.py fdtoverlay base.dtb.txt overlay.dtbo.txt -o final.dtb.txt --show-changes
        '''
    )
    
    parser.add_argument('--version', action='version', version='dt-sim 1.0.0')
    
    # Create subcommands
    subparsers = parser.add_subparsers(
        title='Available commands',
        description='Commands supported by dt-sim',
        dest='command',
        help='Use "dt-sim <command> --help" for detailed help'
    )
    
    # Setup subcommands
    dtc_parser = setup_dtc_parser(subparsers)
    fdto_parser = setup_fdtoverlay_parser(subparsers)
    
    # Parse arguments
    args = parser.parse_args()
    
    # If no command specified, show help
    if not args.command:
        parser.print_help()
        return 1
    
    # Execute corresponding command
    try:
        if args.command == 'dtc':
            # ✅ Fixed import
            try:
                from commands.dtc_command import execute
                return execute(args)
            except ImportError as e:
                print(f"[ERROR] Cannot import dtc_command: {e}")
                print("Please ensure commands/dtc_command.py file exists")
                return 1
                
        elif args.command == 'fdtoverlay':
            try:
                from commands.fdtoverlay_command import execute  
                return execute(args)
            except ImportError as e:
                print(f"[ERROR] Cannot import fdtoverlay_command: {e}")
                print("Please ensure commands/fdtoverlay_command.py file exists")
                return 1
        else:
            print(f"[ERROR] Unknown command: {args.command}")
            return 1
            
    except KeyboardInterrupt:
        print("\n[WARN] Operation interrupted by user")
        return 130
    except Exception as e:
        print(f"[ERROR] Execution error: {e}")
        if hasattr(args, 'verbose') and args.verbose:
            import traceback
            traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
