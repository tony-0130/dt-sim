"""
utils/error_reporter.py - 錯誤報告器
提供詳細、有用的錯誤報告功能
"""

import os
import sys
from typing import List, Dict, Any, Optional
from pathlib import Path
import difflib


class ErrorReporter:
    """錯誤報告器 - dt-sim 的核心價值"""
    
    @staticmethod
    def file_not_found(file_path: str):
        """報告文件找不到錯誤"""
        print(f"[ERROR] 文件不存在: {file_path}")
        
        # 嘗試找到相似的文件名
        directory = os.path.dirname(file_path) or "."
        filename = os.path.basename(file_path)
        
        if os.path.exists(directory):
            try:
                files = os.listdir(directory)
                similar_files = difflib.get_close_matches(filename, files, n=3, cutoff=0.6)
                
                if similar_files:
                    print("   可能的相似文件:")
                    for similar_file in similar_files:
                        full_path = os.path.join(directory, similar_file)
                        print(f"     - {full_path}")
            except PermissionError:
                pass
        else:
            print(f"   目錄也不存在: {directory}")
    
    @staticmethod
    def compilation_failed(input_file: str, error_message: str):
        """報告編譯失敗錯誤"""
        print(f"[ERROR] Compilation failed: {input_file}")
        print(f"   Error: {error_message}")
        
        # 嘗試從錯誤信息中提取行號
        if "line" in error_message:
            try:
                import re
                line_match = re.search(r'line (\d+)', error_message)
                if line_match:
                    line_number = int(line_match.group(1))
                    ErrorReporter.show_source_context(input_file, line_number)
            except:
                pass
    
    @staticmethod
    def show_source_context(file_path: str, line_number: int, context_lines: int = 3):
        """顯示源文件上下文"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            print(f"\n[LOCATION] 錯誤位置 ({os.path.basename(file_path)}:{line_number}):")
            print("   " + "─" * 50)
            
            start = max(0, line_number - context_lines - 1)
            end = min(len(lines), line_number + context_lines)
            
            for i in range(start, end):
                line_num = i + 1
                prefix = ">>>" if line_num == line_number else "   "
                print(f"{prefix} {line_num:3d}: {lines[i].rstrip()}")
                
            print("   " + "─" * 50)
            
        except Exception as e:
            print(f"   無法顯示源文件上下文: {e}")
    
    @staticmethod
    def overlay_target_not_found(target_path: str, available_paths: List[str], 
                                source_location: str = ""):
        """報告 overlay target 找不到錯誤"""
        print(f"[ERROR] Overlay target 不存在: '{target_path}'")
        
        if source_location:
            print(f"   位置: {source_location}")
        
        # 提供可用的路徑列表
        if available_paths:
            print("   [INFO] 可用的節點路徑:")
            
            # 按層級分組顯示
            path_groups = ErrorReporter._group_paths_by_level(available_paths)
            
            for level, paths in sorted(path_groups.items()):
                if level <= 2:  # 只顯示前3層
                    level_name = "根節點" if level == 0 else f"第{level}層"
                    print(f"     {level_name}:")
                    for path in sorted(paths)[:10]:  # 最多顯示10個
                        print(f"       - {path}")
                    if len(paths) > 10:
                        print(f"       ... 還有 {len(paths) - 10} 個")
        
        # 建議相似的路徑
        similar_paths = difflib.get_close_matches(target_path, available_paths, n=3, cutoff=0.4)
        if similar_paths:
            print("   [SUGGEST] 建議的相似路徑:")
            for similar_path in similar_paths:
                print(f"     - {similar_path}")
        
        # 提供常見的修正建議
        print("   [FIX] 常見修正方法:")
        print("     1. 檢查節點名稱拼寫")
        print("     2. 確認節點是否在正確的父節點下")
        print("     3. 檢查 base DTB 是否包含該節點")
        if "@" in target_path:
            base_name = target_path.split("@")[0]
            matching_nodes = [p for p in available_paths if base_name in p]
            if matching_nodes:
                print(f"     4. 可能的正確地址: {', '.join(matching_nodes[:3])}")
    
    @staticmethod
    def _group_paths_by_level(paths: List[str]) -> Dict[int, List[str]]:
        """按路徑層級分組"""
        groups = {}
        for path in paths:
            level = path.count('/') - 1 if path.startswith('/') else path.count('/')
            if level not in groups:
                groups[level] = []
            groups[level].append(path)
        return groups
    
    @staticmethod
    def phandle_reference_not_found(reference: str, available_labels: List[str], 
                                   node_path: str, property_name: str, 
                                   source_location: str = ""):
        """報告 phandle 引用找不到錯誤"""
        print(f"[ERROR] Phandle 引用不存在: '&{reference}'")
        print(f"   節點: {node_path}")
        print(f"   屬性: {property_name}")
        
        if source_location:
            print(f"   位置: {source_location}")
        
        # 顯示可用的 labels
        if available_labels:
            print("   [INFO] 可用的 labels:")
            for label in sorted(available_labels)[:15]:
                print(f"     - &{label}")
            if len(available_labels) > 15:
                print(f"     ... 還有 {len(available_labels) - 15} 個")
        
        # 建議相似的 labels
        similar_labels = difflib.get_close_matches(reference, available_labels, n=3, cutoff=0.6)
        if similar_labels:
            print("   [SUGGEST] 建議的相似 labels:")
            for similar_label in similar_labels:
                print(f"     - &{similar_label}")
    
    @staticmethod
    def merge_validation_failed(errors: List[str]):
        """報告合併驗證失敗"""
        print(f"[ERROR] Overlay 合併驗證失敗 ({len(errors)} 個錯誤):")
        
        for i, error in enumerate(errors, 1):
            print(f"   {i}. {error}")
        
        print("\n[SUGGEST] 解決建議:")
        print("   1. 確認 overlay 的 target 路徑正確")
        print("   2. 檢查 base DTB 包含所有需要的節點")
        print("   3. 驗證 overlay 語法無誤")
        print("   4. 使用 --show-changes 查看詳細信息")
    
    @staticmethod
    def merge_failed(base_file: str, overlay_files: List[str], error_message: str):
        """報告合併失敗錯誤"""
        print(f"[ERROR] Overlay 合併失敗:")
        print(f"   Base: {base_file}")
        print(f"   Overlays: {', '.join(overlay_files)}")
        print(f"   錯誤: {error_message}")
    
    @staticmethod
    def parsing_failed(file_path: str, line_number: int, column: int, 
                      token_info: str = "", context_tokens: List[str] = None):
        """報告解析失敗錯誤"""
        print(f"[ERROR] 語法解析失敗: {os.path.basename(file_path)}")
        print(f"   位置: 第 {line_number} 行, 第 {column} 列")
        
        if token_info:
            print(f"   Token: {token_info}")
        
        # 顯示源文件上下文
        ErrorReporter.show_source_context(file_path, line_number)
        
        # 顯示 token 上下文
        if context_tokens:
            print("   [DEBUG] Token 上下文:")
            for token_str in context_tokens[:10]:
                print(f"     {token_str}")
    
    @staticmethod
    def include_file_not_found(include_file: str, current_file: str, 
                              include_paths: List[str]):
        """報告 include 文件找不到錯誤"""
        print(f"[ERROR] Include 文件不存在: {include_file}")
        print(f"   被包含於: {current_file}")
        
        # 顯示搜索路徑
        print("   [INFO] 搜索路徑:")
        for path in include_paths:
            full_path = os.path.join(path, include_file)
            exists = "[OK]" if os.path.exists(full_path) else "[FAIL]"
            print(f"     {exists} {full_path}")
        
        # 嘗試找到相似的文件
        for search_path in include_paths:
            if os.path.exists(search_path):
                try:
                    files = [f for f in os.listdir(search_path) 
                            if f.endswith(('.dts', '.dtsi'))]
                    similar_files = difflib.get_close_matches(
                        include_file, files, n=3, cutoff=0.6)
                    
                    if similar_files:
                        print(f"   [SUGGEST] 在 {search_path} 中找到相似文件:")
                        for similar_file in similar_files:
                            print(f"     - {similar_file}")
                        break
                except PermissionError:
                    continue
    
    @staticmethod
    def warning(message: str, source_location: str = ""):
        """顯示警告信息"""
        print(f"[WARN] {message}")
        if source_location:
            print(f"   位置: {source_location}")
    
    @staticmethod
    def info(message: str):
        """顯示信息"""
        print(f"[INFO] {message}")
    
    @staticmethod
    def success(message: str):
        """顯示成功信息"""
        print(f"[OK] {message}")
    
    @staticmethod
    def debug(message: str):
        """顯示調試信息"""
        if os.getenv('DT_SIM_DEBUG') or '--verbose' in sys.argv:
            print(f"[DEBUG] {message}")


# 演示錯誤報告功能
if __name__ == "__main__":
    print("=== dt-sim 錯誤報告演示 ===\n")
    
    # 文件不存在
    ErrorReporter.file_not_found("/path/to/nonexistent.dts")
    print()
    
    # Overlay target 不存在
    available_paths = [
        "/", "/soc", "/soc/uart@12350000", "/soc/uart@12360000", 
        "/soc/i2c@12370000", "/memory@80000000"
    ]
    ErrorReporter.overlay_target_not_found(
        "/soc/uart@12340000", 
        available_paths,
        "overlay.dts:15"
    )
    print()
    
    # Phandle 引用不存在
    available_labels = ["uart0", "uart1", "i2c0", "intc", "clk"]
    ErrorReporter.phandle_reference_not_found(
        "uart2", available_labels, "/soc/device", "interrupts",
        "base.dts:42"
    )
