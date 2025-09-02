"""
commands/dtc_command.py - dt-sim dtc 命令實現
支持自動創建 output 目錄
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
    """執行 dt-sim dtc 命令"""
    try:
        from simulators.dtc_simulator import DTCSimulator
        from utils.error_reporter import ErrorReporter
        
        # ✅ 處理輸出路徑 - 確保放在 output 目錄下
        output_file = prepare_output_path(args.output)
        
        if args.verbose:
            print(f"dt-sim dtc: 編譯 {args.input} → {output_file}")
        
        # 檢查輸入文件
        if not os.path.exists(args.input):
            ErrorReporter.file_not_found(args.input)
            return 1
            
        # 創建模擬器
        simulator = DTCSimulator()
        
        # 添加 include 路徑
        if hasattr(args, 'include_paths') and args.include_paths:
            for path in args.include_paths:
                simulator.add_include_path(path)
        
        # 添加輸入文件所在目錄為 include 路徑
        input_dir = os.path.dirname(os.path.abspath(args.input))
        simulator.add_include_path(input_dir)
        
        if hasattr(args, 'check_only') and args.check_only:
            # 只驗證語法
            result = simulator.validate_syntax(args.input, verbose=args.verbose)
            if result:
                print("✅ 語法驗證通過")
                return 0
            else:
                print("❌ 語法驗證失敗")
                return 1
        else:
            # 完整編譯
            device_tree = simulator.compile_to_text_dtb(
                args.input,
                output_file,  # 使用處理後的輸出路徑
                verbose=args.verbose
            )
            
            if args.verbose:
                print(f"Compilation completed successfully!")
                print(f"   Node count: {len(device_tree.get_all_nodes())}")
                print(f"   Phandle count: {len(device_tree.phandle_map)}")
                print(f"   Output file: {output_file}")
            else:
                print(f"Compilation completed: {output_file}")
            
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
    準備輸出路徑，確保文件放在 output 目錄下
    
    Args:
        output_arg: 用戶指定的輸出路徑
        
    Returns:
        str: 處理後的輸出路徑
    """
    output_path = Path(output_arg)
    
    # 如果用戶指定的路徑已經在 output 目錄下，直接使用
    if str(output_path).startswith('output' + os.sep) or str(output_path) == 'output':
        final_path = output_path
    else:
        # 否則，將文件放到 output 目錄下
        if output_path.is_absolute():
            # 如果是絕對路徑，只取文件名
            filename = output_path.name
        else:
            # 如果是相對路徑，保持目錄結構但放在 output 下
            filename = str(output_path)
        
        final_path = Path("output") / filename
    
    # 確保 output 目錄存在
    final_path.parent.mkdir(parents=True, exist_ok=True)
    
    return str(final_path)
