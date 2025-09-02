"""
simulators/dtc_simulator.py - DTC 編譯模擬器
"""

import os
import re
from datetime import datetime
from typing import Dict, List, Optional, Set
from pathlib import Path

class DTSNode:
    """設備樹節點 - 內部表示"""
    
    def __init__(self):
        self.name: str = ""
        self.full_path: str = ""
        self.labels: List[str] = []
        self.properties: Dict[str, 'DTSProperty'] = {}
        self.children: Dict[str, 'DTSNode'] = {}
        self.parent: Optional['DTSNode'] = None
        self.phandle: Optional[int] = None
        self.source_file: str = ""
        self.line_number: int = 0
        
    def get_path(self) -> str:
        """獲取節點的完整路徑"""
        if self.parent is None:
            return "/"
        elif self.parent.parent is None:  # parent is root
            return f"/{self.name}"
        else:
            return f"{self.parent.get_path()}/{self.name}"
            
    def find_child_by_path(self, path: str) -> Optional['DTSNode']:
        """根據路徑查找子節點"""
        if not path or path == "/":
            return self
            
        parts = [p for p in path.split("/") if p]
        current = self
        
        for part in parts:
            if part in current.children:
                current = current.children[part]
            else:
                return None
        return current
        
    def add_child(self, child: 'DTSNode'):
        """添加子節點"""
        child.parent = self
        self.children[child.name] = child
        
    def get_all_descendants(self) -> List['DTSNode']:
        """獲取所有後代節點"""
        nodes = []
        for child in self.children.values():
            nodes.append(child)
            nodes.extend(child.get_all_descendants())
        return nodes


class DTSProperty:
    """設備樹屬性"""
    
    def __init__(self):
        self.name: str = ""
        self.value: any = None
        self.type: str = ""  # "string", "number", "array", "phandle", "empty"
        self.raw_value: str = ""
        self.source_file: str = ""
        self.line_number: int = 0
        
    def has_phandle_reference(self) -> bool:
        """檢查是否包含 phandle 引用"""
        if self.type == "phandle":
            return True
        if self.type == "array" and isinstance(self.value, list):
            return any(isinstance(v, str) and v.startswith('&') for v in self.value)
        return False
        
    def get_phandle_references(self) -> List[str]:
        """獲取所有 phandle 引用的標籤"""
        refs = []
        if self.type == "phandle":
            if isinstance(self.value, str) and self.value.startswith('&'):
                refs.append(self.value[1:])
            elif isinstance(self.value, list):
                for v in self.value:
                    if isinstance(v, str) and v.startswith('&'):
                        refs.append(v[1:])
        elif self.type == "array" and isinstance(self.value, list):
            for v in self.value:
                if isinstance(v, str) and v.startswith('&'):
                    refs.append(v[1:])
        return refs


class DeviceTree:
    """設備樹主結構"""
    
    def __init__(self, verbose: bool = False):
        self.root: Optional[DTSNode] = None
        self.phandle_map: Dict[int, DTSNode] = {}  # phandle -> Node
        self.label_map: Dict[str, DTSNode] = {}    # label -> Node
        self.next_phandle: int = 1
        self.source_files: Set[str] = set()
        self.verbose = verbose
        
    def add_node(self, node: DTSNode):
        """添加節點到樹中"""
        if self.root is None:
            self.root = node
            
        # 記錄來源文件
        if node.source_file:
            self.source_files.add(node.source_file)
            
        # 調試：顯示正在處理的節點
        if self.verbose:
            print(f"    Processing node: {node.name} at {node.get_path()}")
            if node.labels:
                print(f"      Labels: {node.labels}")
            print(f"      Properties: {list(node.properties.keys())}")
            
        # 處理標籤 - 確保所有標籤都被正確映射
        for label in node.labels:
            if label:  # 確保標籤不為空
                self.label_map[label] = node
                if self.verbose:
                    print(f"      Mapped label '{label}' to node {node.get_path()}")
            
        # 分配 phandle（如果節點有標籤）
        if node.labels and node.phandle is None:
            node.phandle = self.next_phandle
            self.phandle_map[self.next_phandle] = node
            if self.verbose:
                print(f"      Assigned phandle 0x{self.next_phandle:02x} to node {node.get_path()}")
            self.next_phandle += 1
            
    def find_node_by_path(self, path: str) -> Optional[DTSNode]:
        """根據路徑查找節點"""
        if not self.root:
            return None
        return self.root.find_child_by_path(path)
        
    def find_node_by_label(self, label: str) -> Optional[DTSNode]:
        """根據標籤查找節點"""
        return self.label_map.get(label)
        
    def find_node_by_phandle(self, phandle: int) -> Optional[DTSNode]:
        """根據 phandle 查找節點"""
        return self.phandle_map.get(phandle)
        
    def get_all_nodes(self) -> List[DTSNode]:
        """獲取所有節點"""
        if not self.root:
            return []
        nodes = [self.root]
        nodes.extend(self.root.get_all_descendants())
        return nodes


class Preprocessor:
    """DTS 預處理器 - 簡化版本"""
    
    def __init__(self):
        self.included_files: Set[str] = set()
        self.include_paths: List[str] = []
        self.file_cache: Dict[str, str] = {}  # Cache for file contents
        
    def add_include_path(self, path: str):
        """添加 include 搜索路徑"""
        self.include_paths.append(path)
        
    def process_includes(self, file_path: str, base_dir: str = None) -> str:
        """處理文件中的所有 #include 指令並合併根節點"""
        if base_dir is None:
            base_dir = os.path.dirname(os.path.abspath(file_path))
            
        abs_path = os.path.abspath(file_path)
        
        # 防止循環引用
        if abs_path in self.included_files:
            return ""
        self.included_files.add(abs_path)
        
        print(f"    Processing file: {os.path.basename(file_path)}")
        
        # Check cache first
        if abs_path in self.file_cache:
            content = self.file_cache[abs_path]
        else:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                self.file_cache[abs_path] = content
            except FileNotFoundError:
                raise FileNotFoundError(f"Include file not found: {file_path}")
            
        # 處理 #include 指令，添加詳細的源文件註解
        result_lines = []
        current_file = os.path.basename(file_path)
        
        for line_num, line in enumerate(content.split('\n'), 1):
            stripped = line.strip()
            
            if stripped.startswith('#include'):
                # 解析 include 路徑
                include_file = self._parse_include_line(stripped)
                if include_file:
                    include_path = self._resolve_include_path(include_file, base_dir)
                    if include_path:
                        print(f"      Including: {include_file} -> {os.path.basename(include_path)}")
                        # 添加來源註解
                        result_lines.append(f"/* === Content from {os.path.basename(include_path)} === */")
                        # 遞迴處理 include
                        included_content = self.process_includes(include_path, os.path.dirname(include_path))
                        result_lines.append(included_content)
                        result_lines.append(f"/* === End of {os.path.basename(include_path)} === */")
                    else:
                        raise FileNotFoundError(f"Cannot resolve include: {include_file}")
                else:
                    # 添加當前文件的行註解
                    result_lines.append(f"/* === Line from {current_file}:{line_num} === */")
                    result_lines.append(line)
            else:
                # 為非空行添加源文件信息
                if stripped:
                    result_lines.append(f"/* === Line from {current_file}:{line_num} === */")
                result_lines.append(line)
                
        # 合併內容並處理多個根節點
        raw_content = '\n'.join(result_lines)
        merged_content = self._merge_multiple_root_nodes(raw_content)
        
        # 建構源文件映射（傳遞給模擬器）
        self._build_source_mapping(raw_content)
        
        print(f"    Processed {os.path.basename(file_path)}: {len(merged_content)} characters")
        return merged_content
        
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
            return local_path
            
        # 然後在 include 路徑中查找
        for include_dir in self.include_paths:
            full_path = os.path.join(include_dir, include_file)
            if os.path.exists(full_path):
                return full_path
                
        return None
    
    def _merge_multiple_root_nodes(self, content: str) -> str:
        """
        合併包含多個根節點的 DTS 內容
        
        Args:
            content: 可能包含多個根節點的 DTS 內容
            
        Returns:
            合併後的單一根節點 DTS 內容
        """
        lines = content.split('\n')
        result_lines = []
        dts_version = ""
        root_content_parts = []
        non_root_content = []  # 收集 &references 等非根節點內容
        current_source_file = "unknown"
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # 保留 DTS 版本聲明
            if line.startswith('/dts-v1/') and not dts_version:
                dts_version = line
                i += 1
                continue
                
            # 檢查源文件註解
            if line.startswith('/* === Content from '):
                current_source_file = line.split('Content from ')[1].split(' ===')[0]
                i += 1
                continue
                
            # 跳過結束註解
            if line.startswith('/* === End of '):
                i += 1
                continue
                
            # 跳過其他註解和空行
            if line.startswith('/*') or line.startswith('//') or not line:
                i += 1
                continue
                
            # 找到根節點定義
            if line == '/ {' or line.startswith('/ {'):
                # 收集根節點內容
                root_content = []
                root_content.append(f"    /* Content from {current_source_file} */")
                brace_count = 1
                i += 1
                
                while i < len(lines) and brace_count > 0:
                    current_line = lines[i]
                    if '{' in current_line:
                        brace_count += current_line.count('{')
                    if '}' in current_line:
                        brace_count -= current_line.count('}')
                    
                    if brace_count > 0:  # 不包括最後的 };
                        root_content.append(current_line)
                    i += 1
                
                root_content_parts.extend(root_content)
            else:
                # 這是非根節點內容（如 &references），保留它
                non_root_content.append(lines[i])  # 保留原行（不是 stripped）
                i += 1
        
        # 重新組合：先是根節點，然後是非根節點內容
        if dts_version:
            result_lines.append(dts_version)
            result_lines.append("")
        
        result_lines.append("/ {")
        result_lines.extend(root_content_parts)
        result_lines.append("};")
        
        # 添加非根節點內容（如 &references）
        if non_root_content:
            result_lines.append("")  # 空行分隔
            result_lines.extend(non_root_content)
        
        return '\n'.join(result_lines)
    
    def _build_source_mapping(self, content: str):
        """建構源文件映射表 - 優化版本"""
        if not content:
            self.source_mapping = {}
            return
            
        lines = content.split('\n')
        current_source_file = None
        
        # 存儲在預處理器中，供外部訪問
        self.source_mapping = {}
        
        # 優化：使用批量處理
        for i, line in enumerate(lines):
            line_number = i + 1
            stripped = line.strip()
            
            # 檢測源文件註解 - 支援多種格式
            if stripped.startswith('/* === Content from '):
                try:
                    current_source_file = stripped[20:stripped.index(' ===')]
                except ValueError:
                    continue
                continue
            elif stripped.startswith('/* Content from '):
                try:
                    current_source_file = stripped[16:stripped.rindex(' */')]
                except ValueError:
                    continue
                continue
            elif stripped.startswith('/* === Line from '):
                try:
                    # 解析格式: /* === Line from filename:line === */
                    # Find the content between "Line from " and " ==="
                    start_idx = stripped.find('Line from ') + 10
                    end_idx = stripped.rfind(' ===')
                    line_info = stripped[start_idx:end_idx]
                    
                    if ':' in line_info:
                        file_part, line_part = line_info.rsplit(':', 1)
                        current_source_file = file_part
                        # 存儲帶有原始行號的映射
                        self.source_mapping[line_number] = f"{file_part}:{line_part}"
                        continue
                    else:
                        current_source_file = line_info
                except (ValueError, IndexError):
                    continue
                continue
                
            # 記錄節點和屬性的源文件 - 優化條件檢查
            if current_source_file and stripped and ('{' in stripped or '=' in stripped):
                self.source_mapping[line_number] = current_source_file


class DTCSimulator:
    """DTC 編譯模擬器 - 修復版本"""
    
    def __init__(self):
        self.preprocessor = Preprocessor()
        self.verbose = False
        self.source_mapping = {}  # 用於追踪節點和屬性的真實源文件
        
    def add_include_path(self, path: str):
        """添加 include 搜索路徑"""
        self.preprocessor.add_include_path(path)
        
    def compile_to_text_dtb(self, dts_file: str, output_file: str, verbose: bool = False, show_includes: bool = False) -> DeviceTree:
        """
        模擬 dtc 編譯過程，生成文本格式的 DTB
        
        Args:
            dts_file: 輸入的 DTS 文件
            output_file: 輸出的 .dtb.txt 文件
            verbose: 是否顯示詳細信息
            show_includes: 是否顯示 include 處理過程
            
        Returns:
            DeviceTree: 編譯後的設備樹對象
        """
        self.verbose = verbose
        
        if verbose:
            print(f"dt-sim dtc: Compiling {dts_file} → {output_file}")
            
        try:
            # Step 1: 預處理 - 處理 #include 指令
            if verbose:
                print("  Step 1: Processing includes...")
            if show_includes and verbose:
                print("    (Show includes mode enabled)")
            processed_content = self.preprocessor.process_includes(dts_file)
            
            # Step 2: 語法解析
            if verbose:
                print("  Step 2: Parsing DTS syntax...")
            
            # ✅ 修復：使用本地導入避免循環依賴
            try:
                from parsers.dts_parser import DTSParser
                parser = DTSParser(verbose=verbose)
                ast_root = parser.parse(processed_content, dts_file, verbose=verbose)
            except ImportError:
                raise RuntimeError("DTS parser not available. Please ensure parsers/dts_parser.py exists.")
            
            # Step 3: 建構設備樹
            if verbose:
                print("  Step 3: Building device tree structure...")
            device_tree = self._build_device_tree(ast_root)
            
            # Step 4: 解析 phandle 引用
            if verbose:
                print("  Step 4: Resolving phandle references...")
            self._resolve_phandle_references(device_tree)
            
            # Step 5: 驗證設備樹
            if verbose:
                print("  Step 5: Validating device tree...")
            self._validate_device_tree(device_tree)
            
            # Step 6: 生成文本輸出
            if verbose:
                print("  Step 6: Generating text DTB...")
            self._generate_dtb_text(device_tree, output_file, dts_file)
            
            if verbose:
                node_count = len(device_tree.get_all_nodes())
                print(f"Generated {output_file} ({node_count} nodes, {len(device_tree.phandle_map)} phandles)")
                
            return device_tree
            
        except Exception as e:
            print(f"ERROR in dt-sim dtc: {e}")
            raise
            
    def _build_device_tree(self, ast_root) -> DeviceTree:
        """從 AST 建構設備樹"""
        device_tree = DeviceTree(verbose=self.verbose)
        
        # Step 1: 轉換 AST 節點為設備樹節點（跳過引用節點）
        root_node = self._convert_ast_to_node(ast_root)
        device_tree.root = root_node
        device_tree.add_node(root_node)
        
        # Step 2: 遞歸處理所有正常節點（跳過引用節點）
        self._process_all_nodes_from_ast(device_tree, root_node, ast_root)
        
        # Step 3: 處理節點引用和屬性合併
        self._process_node_references(device_tree, ast_root)
        
        if self.verbose:
            print(f"    Built device tree with {len(device_tree.get_all_nodes())} nodes")
            print(f"    Label map: {list(device_tree.label_map.keys())}")
        
        return device_tree
        
    def _convert_ast_to_node(self, ast_node) -> DTSNode:
        """將 AST 節點轉換為設備樹節點"""
        node = DTSNode()
        node.name = ast_node.name
        node.labels = ast_node.labels.copy()
        node.source_file = ast_node.source_file
        node.line_number = ast_node.line
        
        # 轉換屬性
        for prop_name, prop_value in ast_node.properties.items():
            dts_prop = DTSProperty()
            dts_prop.name = prop_name
            dts_prop.type = prop_value.type
            dts_prop.value = prop_value.value
            dts_prop.raw_value = prop_value.raw
            dts_prop.source_file = ast_node.source_file
            dts_prop.line_number = ast_node.line
            
            node.properties[prop_name] = dts_prop
            
        return node
        
    def _process_all_nodes_from_ast(self, device_tree: DeviceTree, parent_node: DTSNode, parent_ast):
        """遞歸處理所有正常節點，建立父子關係（跳過引用節點）"""
        
        # 處理子節點（跳過引用節點）
        for child_name, child_ast in parent_ast.children.items():
            # 跳過引用節點，這些將在後續單獨處理
            if hasattr(child_ast, 'is_reference') and child_ast.is_reference:
                if self.verbose:
                    print(f"    Skipping reference node &{child_ast.name} for later processing")
                continue
                
            child_node = self._convert_ast_to_node(child_ast)
            parent_node.add_child(child_node)
            
            # ✅ 修正：確保所有節點都添加到設備樹中（包括標籤處理）
            device_tree.add_node(child_node)
            
            # 遞歸處理子節點
            self._process_all_nodes_from_ast(device_tree, child_node, child_ast)
    
    def _process_node_references(self, device_tree: DeviceTree, ast_root):
        """處理節點引用（&label語法）並合併屬性"""
        # 收集所有引用節點
        reference_nodes = []
        self._collect_reference_nodes(ast_root, reference_nodes)
        
        if self.verbose and reference_nodes:
            print(f"    Processing {len(reference_nodes)} node references...")
            
        # 處理每個引用節點
        for ref_ast in reference_nodes:
            target_label = ref_ast.name
            target_node = device_tree.find_node_by_label(target_label)
            
            if target_node is None:
                if self.verbose:
                    print(f"    Warning: Cannot find target node with label '{target_label}' for reference")
                continue
            
            if self.verbose:
                print(f"    Merging &{target_label} properties into {target_node.get_path()}")
            
            # 合併屬性（引用節點的屬性會覆蓋目標節點的同名屬性）
            for prop_name, prop_value in ref_ast.properties.items():
                dts_prop = DTSProperty()
                dts_prop.name = prop_name
                dts_prop.type = prop_value.type
                dts_prop.value = prop_value.value
                dts_prop.raw_value = prop_value.raw
                dts_prop.source_file = ref_ast.source_file
                dts_prop.line_number = ref_ast.line
                
                # 覆蓋或添加屬性
                if prop_name in target_node.properties:
                    if self.verbose:
                        print(f"      Overriding {prop_name}: {target_node.properties[prop_name].value} -> {prop_value.value}")
                else:
                    if self.verbose:
                        print(f"      Adding {prop_name}: {prop_value.value}")
                
                target_node.properties[prop_name] = dts_prop
            
            # 遞歸處理引用節點的子節點（添加到目標節點）
            for child_name, child_ast in ref_ast.children.items():
                child_node = self._convert_ast_to_node(child_ast)
                target_node.add_child(child_node)
                device_tree.add_node(child_node)
                
                if self.verbose:
                    print(f"      Adding child node {child_name} to {target_node.get_path()}")
                
                # 遞歸處理子節點的子節點
                self._process_all_nodes_from_ast(device_tree, child_node, child_ast)
    
    def _collect_reference_nodes(self, ast_node, reference_list):
        """遞歸收集所有引用節點"""
        # 檢查當前節點的子節點
        for child_name, child_ast in ast_node.children.items():
            if hasattr(child_ast, 'is_reference') and child_ast.is_reference:
                reference_list.append(child_ast)
            else:
                # 遞歸檢查非引用節點的子節點
                self._collect_reference_nodes(child_ast, reference_list)
            
    def _resolve_phandle_references(self, device_tree: DeviceTree):
        """解析所有 phandle 引用"""
        unresolved_refs = []
        
        for node in device_tree.get_all_nodes():
            for prop in node.properties.values():
                if prop.has_phandle_reference():
                    phandle_refs = prop.get_phandle_references()
                    for ref_label in phandle_refs:
                        target_node = device_tree.find_node_by_label(ref_label)
                        if target_node is None:
                            unresolved_refs.append(f"Unresolved phandle reference: &{ref_label} in {node.get_path()}:{prop.name}")
                            
        if unresolved_refs:
            if self.verbose:
                print("  Warning: Some phandle references could not be resolved:")
                for ref in unresolved_refs[:10]:  # 只顯示前10個
                    print(f"    {ref}")
                if len(unresolved_refs) > 10:
                    print(f"    ... and {len(unresolved_refs) - 10} more")
                print("  Note: This might be normal if labels are defined in other files")
            
    def _validate_device_tree(self, device_tree: DeviceTree):
        """驗證設備樹的基本約束"""
        errors = []
        
        # 檢查根節點存在
        if device_tree.root is None:
            errors.append("No root node found")
            return
            
        if self.verbose:
            print(f"  Validating root node: {device_tree.root.name}")
            print(f"  Root node properties: {list(device_tree.root.properties.keys())}")
            
        # 檢查根節點基本結構
        if device_tree.root.name == "/":
            root_props = device_tree.root.properties
            
            # 暫時放寬驗證，只警告而不拋出錯誤
            if "#address-cells" not in root_props:
                if self.verbose:
                    print("  Warning: Root node missing #address-cells property")
            if "#size-cells" not in root_props:
                if self.verbose:
                    print("  Warning: Root node missing #size-cells property")
                
    def _generate_dtb_text(self, device_tree: DeviceTree, output_file: str, source_file: str):
        """生成文本格式的 DTB"""
        lines = []
        
        # 文件頭部註解
        lines.append("/*")
        lines.append(" * Generated by dt-sim dtc - mimics compiled DTB")
        lines.append(f" * Source file: {source_file}")
        lines.append(f" * Compilation timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f" * Total nodes: {len(device_tree.get_all_nodes())}")
        lines.append(f" * Total phandles: {len(device_tree.phandle_map)}")
        lines.append(" */")
        lines.append("")
        
        # DTS 版本聲明
        lines.append("/dts-v1/;")
        lines.append("")
        
        # Phandle 映射表
        if device_tree.phandle_map:
            lines.append("/*")
            lines.append(" * ===== PHANDLE TABLE =====")
            lines.append(" * phandle_map: {")
            for phandle, node in device_tree.phandle_map.items():
                labels = ", ".join(node.labels) if node.labels else "unlabeled"
                lines.append(f" *   {labels}: 0x{phandle:02x} ({node.get_path()})")
            lines.append(" * }")
            lines.append(" */")
            lines.append("")
            
        # 生成設備樹內容
        if device_tree.root:
            self._generate_node_text(device_tree.root, lines, 0)
            
        # 寫入文件
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
            
    def _generate_node_text(self, node: DTSNode, lines: List[str], indent_level: int):
        """遞歸生成節點的文本表示"""
        indent = "    " * indent_level
        
        # 節點開始註解 - 使用正確的源文件和行號
        actual_source_file = self._extract_actual_source_file(node)
        actual_line_number = self._extract_actual_source_line(node)
        
        if actual_source_file:
            lines.append(f"{indent}/* Source: {os.path.basename(actual_source_file)}:{actual_line_number} */")
        elif node.source_file:
            lines.append(f"{indent}/* Source: {os.path.basename(node.source_file)}:{node.line_number} */")
            
        # 節點聲明
        labels_str = ": ".join(node.labels) + ": " if node.labels else ""
        
        if node.name == "/":
            lines.append(f"{labels_str}/ {{")
        else:
            lines.append(f"{indent}{labels_str}{node.name} {{")
            
        # phandle 註解
        if node.phandle:
            lines.append(f"{indent}    /* phandle: 0x{node.phandle:02x} (auto-assigned) */")
            
        # 屬性
        for prop_name, prop in sorted(node.properties.items()):
            prop_source_info = f"{actual_source_file}:{actual_line_number}" if actual_source_file else None
            self._generate_property_text(prop, lines, indent_level + 1, prop_source_info)
            
        # 子節點
        for child_name, child_node in sorted(node.children.items()):
            lines.append("")  # 空行分隔
            self._generate_node_text(child_node, lines, indent_level + 1)
            
        lines.append(f"{indent}}};")
    
    def _extract_actual_source_file(self, node: DTSNode) -> Optional[str]:
        """從源文件映射中提取實際的源文件信息"""
        # 從預處理器的源文件映射中查找
        if hasattr(self.preprocessor, 'source_mapping'):
            mapping_result = self.preprocessor.source_mapping.get(node.line_number)
            if mapping_result:
                # 如果包含行號信息，只返回文件名部分
                if ':' in mapping_result:
                    return mapping_result.split(':')[0]
                return mapping_result
        return None
    
    def _extract_actual_source_line(self, node: DTSNode) -> Optional[str]:
        """從源文件映射中提取原始行號"""
        if hasattr(self.preprocessor, 'source_mapping'):
            mapping_result = self.preprocessor.source_mapping.get(node.line_number)
            if mapping_result and ':' in mapping_result:
                return mapping_result.split(':', 1)[1]
        return str(node.line_number)
        
    def _generate_property_text(self, prop: DTSProperty, lines: List[str], indent_level: int, prop_source_info: str = None):
        """生成屬性的文本表示"""
        indent = "    " * indent_level
        
        # 屬性來源註解（使用傳入的源信息）
        if prop_source_info:
            source_comment = f" /* {os.path.basename(prop_source_info)} */"
        elif prop.source_file:
            source_comment = f" /* {os.path.basename(prop.source_file)}:{prop.line_number} */"
        else:
            source_comment = ""
            
        if prop.type == "empty":
            lines.append(f"{indent}{prop.name};{source_comment}")
        elif prop.type == "string":
            lines.append(f'{indent}{prop.name} = "{prop.value}";{source_comment}')
        elif prop.type in ["array", "phandle"]:
            if prop.raw_value:
                # 直接使用原始值，不要額外處理
                lines.append(f"{indent}{prop.name} = {prop.raw_value};{source_comment}")
            else:
                # fallback formatting
                if isinstance(prop.value, list):
                    if len(prop.value) == 1:
                        lines.append(f"{indent}{prop.name} = <{prop.value[0]}>;{source_comment}")
                    else:
                        value_str = " ".join(str(v) for v in prop.value)
                        lines.append(f"{indent}{prop.name} = <{value_str}>;{source_comment}")
                else:
                    lines.append(f"{indent}{prop.name} = <{prop.value}>;{source_comment}")
        else:
            # 其他類型的屬性
            lines.append(f"{indent}{prop.name} = {prop.raw_value};{source_comment}")


# 使用範例和測試函數
def test_dtc_simulator():
    """測試 DTC 模擬器的基本功能"""
    
    # 創建測試 DTS 內容
    test_dts_content = '''
/dts-v1/;

/ {
    #address-cells = <2>;
    #size-cells = <2>;
    compatible = "test,board";
    
    cpus {
        #address-cells = <1>;
        #size-cells = <0>;
        
        cpu0: cpu@0 {
            device_type = "cpu";
            compatible = "arm,cortex-a53";
            reg = <0>;
        };
    };
    
    memory@80000000 {
        device_type = "memory";
        reg = <0x0 0x80000000 0x0 0x40000000>;
    };
    
    intc: interrupt-controller {
        compatible = "arm,gic-400";
        #interrupt-cells = <3>;
        interrupt-controller;
    };
};
'''
    
    # 寫入測試檔案
    test_file = "test_input.dts"
    with open(test_file, 'w') as f:
        f.write(test_dts_content)
        
    try:
        # 測試編譯
        simulator = DTCSimulator()
        device_tree = simulator.compile_to_text_dtb(
            test_file, 
            "test_output.dtb.txt", 
            verbose=True
        )
        
        print(f"Successfully compiled! Device tree has {len(device_tree.get_all_nodes())} nodes.")
        print(f"Phandle map: {device_tree.phandle_map}")
        
    finally:
        # 清理測試檔案
        if os.path.exists(test_file):
            os.remove(test_file)


if __name__ == "__main__":
    test_dtc_simulator()
