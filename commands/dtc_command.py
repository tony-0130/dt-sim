"""
commands/dtc_command.py - dt-sim dtc command implementation
Supports automatic creation of output directory
"""

import os
import sys
from pathlib import Path

def run_validation(dtb_file, input_file, verbose=False, test_overlays=False, show_warnings=True):
    """Run validation on the compiled DTB file"""
    try:
        from utils.validator import DeviceTreeValidator, create_validation_test_cases
        
        if verbose:
            print(f"\n{'='*50}")
            print("VALIDATING DTB OUTPUT")
            print(f"{'='*50}")
        
        validator = DeviceTreeValidator(verbose=verbose)
        
        # Basic validation
        results = validator.validate_dtb_file(dtb_file)
        
        error_count = sum(1 for r in results if r.level.value == 'error')
        warning_count = sum(1 for r in results if r.level.value == 'warning')
        
        # Show results
        if verbose or error_count > 0:
            for result in results:
                if result.level.value == 'error':
                    print(f"[ERROR] {result.message}")
                elif result.level.value == 'warning' and show_warnings:
                    print(f"[WARN]  {result.message}")
                elif result.level.value == 'info' and verbose:
                    print(f"[INFO]  {result.message}")
        
        # Test overlay functionality if requested
        if test_overlays:
            if verbose:
                print(f"\n{'='*50}")
                print("TESTING NODE REFERENCE OVERLAYS")  
                print(f"{'='*50}")
                
            expected_changes = create_validation_test_cases()
            overlay_results = validator.validate_overlay_application(
                dtb_file.replace('_complete', '_fixed'),  # Try to find original
                dtb_file,
                expected_changes
            )
            
            overlay_errors = sum(1 for r in overlay_results if r.level.value == 'error')
            overlay_success = sum(1 for r in overlay_results if r.level.value == 'info')
            
            if verbose:
                print(f"Overlay tests: {overlay_success} passed, {overlay_errors} failed")
                
            for result in overlay_results:
                if result.level.value == 'error':
                    print(f"[FAIL] {result.message}")
                elif verbose and result.level.value == 'info':
                    print(f"[OK]   {result.message}")
            
            if overlay_errors == 0:
                print(f"[OK] All overlay tests PASSED")
            else:
                print(f"[FAIL] Overlay tests FAILED - {overlay_errors} issues found")
                return 1
        
        if error_count == 0:
            print(f"[OK] DTB validation PASSED")
            return 0
        else:
            print(f"[FAIL] DTB validation FAILED - {error_count} errors")
            return 1
            
    except Exception as e:
        print(f"Validation error: {e}")
        return 1

def execute(args):
    """Execute dt-sim dtc command"""
    try:
        from simulators.dtc_simulator import DTCSimulator
        from utils.error_reporter import ErrorReporter
        
        # ✅ Handle output path - ensure it's placed in output directory
        output_file = prepare_output_path(args.output)
        
        if args.verbose:
            print(f"dt-sim dtc: compiling {args.input} → {output_file}")
        
        # Check input file
        if not os.path.exists(args.input):
            ErrorReporter.file_not_found(args.input)
            return 1
            
        # Create simulator
        simulator = DTCSimulator()
        
        # Add include paths
        if hasattr(args, 'include_paths') and args.include_paths:
            for path in args.include_paths:
                simulator.add_include_path(path)
        
        # Add input file directory as include path
        input_dir = os.path.dirname(os.path.abspath(args.input))
        simulator.add_include_path(input_dir)
        
        if hasattr(args, 'check_only') and args.check_only:
            # Only validate syntax
            result = simulator.validate_syntax(args.input, verbose=args.verbose)
            if result:
                print("✅ Syntax validation passed")
                return 0
            else:
                print("❌ Syntax validation failed")
                return 1
        else:
            # Full compilation
            success, device_tree = simulator.compile_to_text_dtb(
                args.input,
                output_file,  # Use processed output path
                verbose=args.verbose,
                platform=getattr(args, 'platform', None)
            )
            
            if success and device_tree:
                if args.verbose:
                    print(f"Compilation completed successfully!")
                    print(f"   Node count: {len(device_tree.get_all_nodes())}")
                    print(f"   Phandle count: {len(device_tree.phandle_map)}")
                    print(f"   Output file: {output_file}")
                else:
                    print(f"Compilation completed: {output_file}")
            else:
                raise Exception("Compilation failed")
            
            # Automatic validation if requested
            if hasattr(args, 'validate') and args.validate:
                validation_result = run_validation(
                    output_file, 
                    args.input,
                    verbose=args.verbose,
                    test_overlays=getattr(args, 'test_overlays', False),
                    show_warnings=not getattr(args, 'no_warnings', False)
                )
                
                if validation_result != 0:
                    print("Note: Compilation succeeded but validation found issues")
                    return validation_result
            
            return 0
            
    except Exception as e:
        ErrorReporter.compilation_failed(args.input, str(e))
        if hasattr(args, 'verbose') and args.verbose:
            import traceback
            traceback.print_exc()
        return 1

def prepare_output_path(output_arg: str) -> str:
    """
    Prepare output path, ensure file is placed in output directory
    
    Args:
        output_arg: User-specified output path
        
    Returns:
        str: Processed output path
    """
    output_path = Path(output_arg)
    
    # If user-specified path is already in output directory, use directly
    if str(output_path).startswith('output' + os.sep) or str(output_path) == 'output':
        final_path = output_path
    else:
        # Otherwise, place file in output directory
        if output_path.is_absolute():
            # If absolute path, take only filename
            filename = output_path.name
        else:
            # If relative path, maintain directory structure but place under output
            filename = str(output_path)
        
        final_path = Path("output") / filename
    
    # Ensure output directory exists
    final_path.parent.mkdir(parents=True, exist_ok=True)
    
    return str(final_path)
