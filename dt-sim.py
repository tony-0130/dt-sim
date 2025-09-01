#!/usr/bin/env python3
"""
dt-sim.py - Device Tree 模擬工具主程式
"""

import os
import sys
import argparse

# 添加當前目錄到模組搜索路徑
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

def setup_dtc_parser(subparser):
    """設置 dt-sim dtc 子命令"""
    dtc_parser = subparser.add_parser(
        'dtc',
        help='模擬 dtc 編譯 DTS 到文本 DTB',
        description='將 .dts 文件編譯成可讀的 .dtb.txt 文件'
    )
    
    dtc_parser.add_argument('input', help='輸入的 .dts 文件')
    dtc_parser.add_argument('-o', '--output', required=True, help='輸出的 .dtb.txt 文件')
    dtc_parser.add_argument('-v', '--verbose', action='store_true', help='顯示詳細過程')
    dtc_parser.add_argument('--show-includes', action='store_true', help='顯示 include 處理過程')
    dtc_parser.add_argument('--check-only', action='store_true', help='只驗證語法，不生成輸出')
    dtc_parser.add_argument('-I', '--include', action='append', dest='include_paths', 
                           help='添加 include 搜索路徑')
    
    return dtc_parser

def setup_overlay_parser(subparser):
    """設置 dt-sim overlay 子命令"""
    overlay_parser = subparser.add_parser(
        'overlay',
        help='模擬 dtc overlay 編譯',
        description='將 overlay .dts 文件編譯成 .dtbo.txt 文件'
    )
    
    overlay_parser.add_argument('input', help='輸入的 overlay .dts 文件')
    overlay_parser.add_argument('-o', '--output', required=True, help='輸出的 .dtbo.txt 文件')
    overlay_parser.add_argument('-v', '--verbose', action='store_true', help='顯示詳細過程')
    overlay_parser.add_argument('--show-fragments', action='store_true', help='顯示 fragment 結構')
    overlay_parser.add_argument('--validate-targets', action='store_true', help='驗證 fragment targets')
    
    return overlay_parser

def setup_fdtoverlay_parser(subparser):
    """設置 dt-sim fdtoverlay 子命令"""
    fdto_parser = subparser.add_parser(
        'fdtoverlay',
        help='模擬 fdtoverlay 合併',
        description='將 base DTB 和 overlay DTBO 合併成最終 DTB'
    )
    
    fdto_parser.add_argument('base', help='基礎 .dtb.txt 文件')
    fdto_parser.add_argument('overlays', nargs='+', help='一個或多個 .dtbo.txt 文件')
    fdto_parser.add_argument('-o', '--output', required=True, help='輸出的 final .dtb.txt 文件')
    fdto_parser.add_argument('-v', '--verbose', action='store_true', help='顯示詳細過程')
    fdto_parser.add_argument('--show-merge', action='store_true', help='顯示合併過程')
    fdto_parser.add_argument('--show-changes', action='store_true', help='顯示會修改的節點')
    fdto_parser.add_argument('--validate-only', action='store_true', help='只驗證不生成輸出')
    
    return fdto_parser

def main():
    """主函數"""
    parser = argparse.ArgumentParser(
        prog='dt-sim',
        description='Device Tree 模擬工具 - 模擬 dtc 和 fdtoverlay 的行為',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
使用範例:
  # 編譯 DTS 到文本 DTB
  python dt-sim.py dtc base.dts -o base.dtb.txt --verbose
  
  # 編譯 overlay
  python dt-sim.py overlay my_overlay.dts -o my_overlay.dtbo.txt --show-fragments
  
  # 合併 base 和 overlay
  python dt-sim.py fdtoverlay base.dtb.txt overlay.dtbo.txt -o final.dtb.txt --show-changes
        '''
    )
    
    parser.add_argument('--version', action='version', version='dt-sim 1.0.0')
    
    # 創建子命令
    subparsers = parser.add_subparsers(
        title='可用命令',
        description='dt-sim 支援的命令',
        dest='command',
        help='使用 "dt-sim <command> --help" 查看詳細幫助'
    )
    
    # 設置子命令
    dtc_parser = setup_dtc_parser(subparsers)
    overlay_parser = setup_overlay_parser(subparsers)  
    fdto_parser = setup_fdtoverlay_parser(subparsers)
    
    # 解析參數
    args = parser.parse_args()
    
    # 如果沒有指定命令，顯示幫助
    if not args.command:
        parser.print_help()
        return 1
    
    # 執行對應的命令
    try:
        if args.command == 'dtc':
            # ✅ 修復導入
            try:
                from commands.dtc_command import execute
                return execute(args)
            except ImportError as e:
                print(f"❌ 無法導入 dtc_command: {e}")
                print("請確保 commands/dtc_command.py 文件存在")
                return 1
                
        elif args.command == 'overlay':
            try:
                from commands.overlay_command import execute
                return execute(args)
            except ImportError:
                print("❌ overlay 命令尚未實現")
                print("請使用 dtc 命令進行基本的 DTS 編譯")
                return 1
                
        elif args.command == 'fdtoverlay':
            try:
                from commands.fdtoverlay_command import execute  
                return execute(args)
            except ImportError:
                print("❌ fdtoverlay 命令尚未實現")
                print("請使用 dtc 命令進行基本的 DTS 編譯")
                return 1
        else:
            print(f"❌ 未知命令: {args.command}")
            return 1
            
    except KeyboardInterrupt:
        print("\n⚠️  操作被用戶中斷")
        return 130
    except Exception as e:
        print(f"❌ 執行錯誤: {e}")
        if hasattr(args, 'verbose') and args.verbose:
            import traceback
            traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
