"""
commands/dtc_command.py - dt-sim dtc 命令實現
支持自動創建 output 目錄
"""

import os
import sys
from pathlib import Path

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
