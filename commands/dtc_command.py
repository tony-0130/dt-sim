"""
commands/dtc_command.py - Clean thin wrapper for dt-sim dtc command

Implements the user's vision for thin command wrapper that delegates
to the clean pipeline dtc_simulator for all actual processing.

Clean architecture: dt-sim → dtc_command → dtc_simulator → pipeline components
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
    """Execute dt-sim dtc command - Thin wrapper around clean pipeline simulator"""
    try:
        from simulators.dtc_simulator import DTCSimulator
        
        # ✅ Handle output path - auto-generate if not specified
        if args.output:
            output_file = prepare_output_path(args.output)
        else:
            # Auto-generate output filename
            input_path = Path(args.input)
            auto_output = input_path.stem + ".dtb.txt"
            output_file = prepare_output_path(auto_output)
        
        # Check input file
        if not os.path.exists(args.input):
            print(f"[ERROR] Input file not found: {args.input}")
            return 1
            
        # Create clean pipeline simulator
        simulator = DTCSimulator(verbose=args.verbose)
        
        # Add include paths from args
        if hasattr(args, 'include_paths') and args.include_paths:
            for path in args.include_paths:
                simulator.add_include_path(path)
        
        # Add input file directory as include path
        input_dir = os.path.dirname(os.path.abspath(args.input))
        simulator.add_include_path(input_dir)
        
        # Run clean pipeline compilation
        success, intermediate_rep = simulator.compile_dts(
            args.input,
            output_file,
            platform=getattr(args, 'platform', None),
            validate=getattr(args, 'validate', False),
            no_warnings=getattr(args, 'no_warnings', False)
        )
        
        if not success:
            return 1
        
        # Automatic validation if requested (additional validation beyond pipeline)
        if hasattr(args, 'validate') and args.validate and hasattr(args, 'test_overlays'):
            validation_result = run_validation(
                output_file, 
                args.input,
                verbose=args.verbose,
                test_overlays=getattr(args, 'test_overlays', False),
                show_warnings=not getattr(args, 'no_warnings', False)
            )
            
            if validation_result != 0:
                print("Note: Compilation succeeded but additional validation found issues")
                return validation_result
        
        return 0
            
    except Exception as e:
        print(f"[ERROR] Compilation failed: {args.input}")
        print(f"   Error: {str(e)}")
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

