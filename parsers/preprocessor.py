"""
parsers/preprocessor.py - DTS 預處理器

處理 DTS 文件中的預處理指令：
- #include "file.dtsi" 和 #include <file.dtsi>
- #define SYMBOL VALUE
- 基本的宏展開
- 條件編譯（簡單支持）
"""

import os
import re
from typing import Dict, List, Set, Optional, Tuple
from pathlib import Path
from utils.error_reporter import ErrorReporter

class PreprocessorError(Exception):
    """預處理器錯誤"""
    pass


class Macro:
    """宏定義"""
    def __init__(self, name: str, value: str, params: List[str] = None, 
                 source_file: str = "", line_number: int = 0):
        self.name = name
        self.value = value
        self.params = params or []  # 函數式宏的參數
        self.source_file = source_file
        self.line_number = line_number
        self.is_function_like = len(self.params) > 0
    
    def expand(self, args: List[str] = None) -> str:
        """展開宏"""
        if self.is_function_like:
            if not args or len(args) != len(self.params):
                raise PreprocessorError(
                    f"Macro '{self.name}' expects {len(self.params)} arguments, "
                    f"got {len(args) if args else 0}"
                )
            
            # 替換參數
            result = self.value
            for param, arg in zip(self.params, args):
                result = result.replace(param, arg)
            return result
        else:
            return self.value


class Preprocessor:
    """DTS 預處理器"""
    
    def __init__(self, verbose: bool = False):
        self.included_files: Set[str] = set()
        self.include_paths: List[str] = []
        self.macros: Dict[str, Macro] = {}
        self.verbose = verbose
        
        # 內建宏定義
        self._setup_builtin_macros()
    
    def _setup_builtin_macros(self):
        """設置內建宏定義"""
        # 常用的 DTS 宏定義
        builtins = {
            '__DTS__': '1',
            '__FILE__': '""',  # 在處理時會被替換為實際文件名
            '__LINE__': '0',   # 在處理時會被替換為實際行號
        }
        
        for name, value in builtins.items():
            self.macros[name] = Macro(name, value, source_file="<builtin>")
    
    def add_include_path(self, path: str):
        """添加 include 搜索路徑"""
        abs_path = os.path.abspath(path)
        if abs_path not in self.include_paths:
            self.include_paths.append(abs_path)
            if self.verbose:
                print(f"Added include path: {abs_path}")
    
    def define_macro(self, name: str, value: str = "", params: List[str] = None):
        """定義宏（用於命令行 -D 選項）"""
        self.macros[name] = Macro(name, value, params, source_file="<command-line>")
    
    def process_file(self, file_path: str, base_dir: str = None) -> str:
        """處理文件的所有預處理指令"""
        if base_dir is None:
            base_dir = os.path.dirname(os.path.abspath(file_path))
            
        self.add_include_path(base_dir)  # 添加文件所在目錄
        
        return self.process_includes(file_path, base_dir)
    
    def process_includes(self, file_path: str, base_dir: str = None) -> str:
        """處理文件中的所有 #include 指令"""
        if base_dir is None:
            base_dir = os.path.dirname(os.path.abspath(file_path))
            
        abs_path = os.path.abspath(file_path)
        
        # 防止循環引用
        if abs_path in self.included_files:
            if self.verbose:
                print(f"Skipping already included file: {os.path.basename(file_path)}")
            return ""
        self.included_files.add(abs_path)
        
        if self.verbose:
            print(f"Processing file: {os.path.basename(file_path)}")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except FileNotFoundError:
            raise PreprocessorError(f"File not found: {file_path}")
        except UnicodeDecodeError:
            raise PreprocessorError(f"Cannot decode file (not UTF-8): {file_path}")
        
        # 逐行處理
        result_lines = []
        lines = content.split('\n')
        
        for line_num, line in enumerate(lines, 1):
            processed_line = self._process_line(
                line, file_path, line_num, base_dir, result_lines
            )
            
            if processed_line is not None:
                if isinstance(processed_line, list):
                    result_lines.extend(processed_line)
                else:
                    result_lines.append(processed_line)
        
        final_content = '\n'.join(result_lines)
        
        if self.verbose:
            print(f"Processed {os.path.basename(file_path)}: "
                  f"{len(lines)} lines → {len(result_lines)} lines")
        
        return final_content
    
    def _process_line(self, line: str, current_file: str, line_num: int, 
                     base_dir: str, result_lines: List[str]) -> Optional[str]:
        """處理單行內容"""
        stripped = line.strip()
        
        # 空行和註釋直接保留
        if not stripped or stripped.startswith('//') or stripped.startswith('/*'):
            return line
        
        # 處理 #include 指令
        if stripped.startswith('#include'):
            return self._process_include(stripped, current_file, line_num, base_dir)
        
        # 處理 #define 指令
        elif stripped.startswith('#define'):
            return self._process_define(stripped, current_file, line_num)
        
        # 處理 #undef 指令
        elif stripped.startswith('#undef'):
            return self._process_undef(stripped, current_file, line_num)
        
        # 處理條件編譯（簡單支持）
        elif stripped.startswith('#ifdef'):
            return self._process_ifdef(stripped, current_file, line_num)
        elif stripped.startswith('#ifndef'):
            return self._process_ifndef(stripped, current_file, line_num)
        elif stripped.startswith('#endif'):
            return self._process_endif(stripped, current_file, line_num)
        
        # 其他預處理指令忽略（但保留註釋）
        elif stripped.startswith('#'):
            return f"/* Ignored preprocessor directive: {stripped} */"
        
        # 普通行 - 進行宏展開
        else:
            return self._expand_macros(line)
    
    def _process_include(self, line: str, current_file: str, line_num: int, 
                        base_dir: str) -> List[str]:
        """處理 #include 指令"""
        include_file = self._parse_include_line(line)
        if not include_file:
            ErrorReporter.warning(f"Invalid #include syntax: {line}", 
                                f"{current_file}:{line_num}")
            return [f"/* Invalid include: {line} */"]
        
        include_path = self._resolve_include_path(include_file, base_dir)
        if not include_path:
            ErrorReporter.include_file_not_found(
                include_file, current_file, self.include_paths
            )
            return [f"/* Include not found: {include_file} */"]
        
        if self.verbose:
            print(f"  Including: {include_file} -> {os.path.basename(include_path)}")
        
        # 添加來源註解
        result = [f"/* Include from {include_path} */"]
        
        try:
            # 遞迴處理 include
            included_content = self.process_includes(include_path, os.path.dirname(include_path))
            result.append(included_content)
            result.append(f"/* End of {include_path} */")
            
        except Exception as e:
            ErrorReporter.compilation_failed(include_path, str(e))
            result.append(f"/* Include failed: {e} */")
        
        return result
    
    def _process_define(self, line: str, current_file: str, line_num: int) -> Optional[str]:
        """處理 #define 指令"""
        # 解析 #define 語法
        match = re.match(r'#define\s+(\w+)(?:\((.*?)\))?\s*(.*)', line)
        if not match:
            ErrorReporter.warning(f"Invalid #define syntax: {line}", 
                                f"{current_file}:{line_num}")
            return f"/* Invalid define: {line} */"
        
        macro_name = match.group(1)
        macro_params = match.group(2)
        macro_value = match.group(3).strip()
        
        # 解析參數（如果是函數式宏）
        params = []
        if macro_params:
            params = [p.strip() for p in macro_params.split(',') if p.strip()]
        
        # 創建宏定義
        macro = Macro(macro_name, macro_value, params, current_file, line_num)
        self.macros[macro_name] = macro
        
        if self.verbose:
            param_str = f"({', '.join(params)})" if params else ""
            print(f"  Defined macro: {macro_name}{param_str} = {macro_value}")
        
        return f"/* #define {macro_name} {macro_value} */"
    
    def _process_undef(self, line: str, current_file: str, line_num: int) -> Optional[str]:
        """處理 #undef 指令"""
        match = re.match(r'#undef\s+(\w+)', line)
        if not match:
            ErrorReporter.warning(f"Invalid #undef syntax: {line}", 
                                f"{current_file}:{line_num}")
            return f"/* Invalid undef: {line} */"
        
        macro_name = match.group(1)
        if macro_name in self.macros:
            del self.macros[macro_name]
            if self.verbose:
                print(f"  Undefined macro: {macro_name}")
        
        return f"/* #undef {macro_name} */"
    
    def _process_ifdef(self, line: str, current_file: str, line_num: int) -> Optional[str]:
        """處理 #ifdef 指令（簡單實現）"""
        match = re.match(r'#ifdef\s+(\w+)', line)
        if not match:
            return f"/* Invalid ifdef: {line} */"
        
        macro_name = match.group(1)
        # 簡單實現：總是認為條件為真（在真實實現中需要條件編譯堆棧）
        return f"/* #ifdef {macro_name} (always true in dt-sim) */"
    
    def _process_ifndef(self, line: str, current_file: str, line_num: int) -> Optional[str]:
        """處理 #ifndef 指令（簡單實現）"""
        match = re.match(r'#ifndef\s+(\w+)', line)
        if not match:
            return f"/* Invalid ifndef: {line} */"
        
        macro_name = match.group(1)
        return f"/* #ifndef {macro_name} (always true in dt-sim) */"
    
    def _process_endif(self, line: str, current_file: str, line_num: int) -> Optional[str]:
        """處理 #endif 指令"""
        return f"/* #endif */"
    
    def _expand_macros(self, line: str) -> str:
        """展開行中的宏"""
        result = line
        
        # 簡單的宏展開（不支持函數式宏的複雜情況）
        for macro_name, macro in self.macros.items():
            if not macro.is_function_like:
                # 只替換完整的標識符
                pattern = r'\b' + re.escape(macro_name) + r'\b'
                if re.search(pattern, result):
                    result = re.sub(pattern, macro.value, result)
        
        return result
    
    def _parse_include_line(self, line: str) -> Optional[str]:
        """解析 #include 行，提取文件路徑"""
        # 支援兩種格式: #include "file.dtsi" 和 #include <file.dtsi>
        match = re.match(r'#include\s*[<"](.*?)[>"]', line)
        return match.group(1) if match else None
    
    def _resolve_include_path(self, include_file: str, base_dir: str) -> Optional[str]:
        """解析 include 文件的絕對路徑"""
        # 首先在同一目錄中查找
        local_path = os.path.join(base_dir, include_file)
        if os.path.exists(local_path):
            return os.path.abspath(local_path)
        
        # 然後在 include 路徑中查找
        for include_dir in self.include_paths:
            full_path = os.path.join(include_dir, include_file)
            if os.path.exists(full_path):
                return os.path.abspath(full_path)
        
        return None
    
    def get_statistics(self) -> Dict[str, any]:
        """獲取預處理統計信息"""
        return {
            "included_files": list(self.included_files),
            "include_paths": self.include_paths,
            "defined_macros": list(self.macros.keys()),
            "total_files_processed": len(self.included_files)
        }
    
    def reset(self):
        """重置預處理器狀態（用於處理新文件）"""
        self.included_files.clear()
        # 保留 include_paths 和用戶定義的宏
        
        # 重新設置內建宏
        self._setup_builtin_macros()


# 用於測試的輔助函數

def create_test_files():
    """創建測試用的 DTS 文件"""
    
    # 創建測試目錄
    test_dir = Path("test_preprocessor")
    test_dir.mkdir(exist_ok=True)
    
    # common.dtsi
    common_dtsi = """
/* Common definitions */
#define UART_CLOCK_FREQ 50000000
#define I2C_CLOCK_FREQ  100000
#define SPI_CLOCK_FREQ  25000000

/* Common memory regions */
memory: memory@80000000 {
    device_type = "memory";
    reg = <0x80000000 0x40000000>;
};

/* Common interrupt controller */
intc: interrupt-controller {
    compatible = "arm,gic-400";
    #interrupt-cells = <3>;
    interrupt-controller;
    reg = <0x1000000 0x1000>;
};
"""
    
    # board.dtsi
    board_dtsi = """
#include "common.dtsi"

/* Board specific definitions */
#define GPIO_BASE 0x12000000
#define UART_BASE 0x12340000

/ {
    model = "Test Board";
    compatible = "test,board";
    
    cpus {
        #address-cells = <1>;
        #size-cells = <0>;
        
        cpu@0 {
            device_type = "cpu";
            compatible = "arm,cortex-a53";
            reg = <0>;
            clock-frequency = <UART_CLOCK_FREQ>;
        };
    };
};
"""
    
    # main.dts
    main_dts = """
/dts-v1/;

#include "board.dtsi"

/ {
    uart0: uart@UART_BASE {
        compatible = "ns16550a";
        reg = <UART_BASE 0x100>;
        interrupts = <&intc 0 4 1>;
        clock-frequency = <UART_CLOCK_FREQ>;
    };
    
    i2c0: i2c@12370000 {
        compatible = "simple-i2c";
        reg = <0x12370000 0x100>;
        clock-frequency = <I2C_CLOCK_FREQ>;
    };
};
"""
    
    # 寫入文件
    with open(test_dir / "common.dtsi", 'w') as f:
        f.write(common_dtsi)
    
    with open(test_dir / "board.dtsi", 'w') as f:
        f.write(board_dtsi)
    
    with open(test_dir / "main.dts", 'w') as f:
        f.write(main_dts)
    
    return test_dir


def test_preprocessor():
    """測試預處理器功能"""
    print("=== 測試 DTS 預處理器 ===")
    
    # 創建測試文件
    test_dir = create_test_files()
    
    try:
        # 創建預處理器
        preprocessor = Preprocessor(verbose=True)
        
        # 處理主文件
        main_file = test_dir / "main.dts"
        result = preprocessor.process_file(str(main_file))
        
        print("\n=== 預處理結果 ===")
        print(result)
        
        # 顯示統計信息
        stats = preprocessor.get_statistics()
        print(f"\n=== 統計信息 ===")
        print(f"處理文件數: {stats['total_files_processed']}")
        print(f"包含路徑: {stats['include_paths']}")
        print(f"定義的宏: {stats['defined_macros']}")
        
        print("\n✅ 預處理器測試完成")
        
    except Exception as e:
        print(f"❌ 預處理器測試失敗: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # 清理測試文件
        import shutil
        if test_dir.exists():
            shutil.rmtree(test_dir)


if __name__ == "__main__":
    test_preprocessor()
