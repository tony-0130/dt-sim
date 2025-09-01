"""
parsers/dts_parser.py - DTS 語法解析器
完全獨立版本，不依賴任何 core 模組
"""

import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

# ===== Token 定義 =====

class TokenType(Enum):
    # Basic Token Types
    LBRACE = '{'
    RBRACE = '}'
    LANGLE = '<'
    RANGLE = '>'
    LPAREN = '('
    RPAREN = ')'
    LBRACKET = '['
    RBRACKET = ']'
    SEMICOLON = ';'
    COMMA = ','
    EQUALS = '='
    AMPERSAND = '&'
    COLON = ':'
    SLASH = '/'

    # Data Types
    IDENTIFIER = 'IDENTIFIER'
    STRING = 'STRING'
    NUMBER = 'NUMBER'

    # Keywords
    DTS_VERSION = '/dts-v1/'
    PLUGIN = '/plugin/'
    DELETE_NODE = '/delete-node/'
    DELETE_PROP = '/delete-property/'

    # Special
    COMMENT = 'COMMENT'
    NEWLINE = 'NEWLINE'
    EOF = 'EOF'

@dataclass
class Token:
    type: TokenType
    value: str
    line: int = 0
    column: int = 0

@dataclass
class PropertyValue:
    """DTS property value"""
    type: str   # 'string', 'number', 'array', 'phandle', 'empty'
    value: Any
    raw: str    # original raw string

@dataclass
class ASTNode:
    """DTS AST Node - 解析器內部使用"""
    name: str
    labels: List[str]
    properties: Dict[str, PropertyValue]
    children: Dict[str, 'ASTNode']
    line: int = 0
    column: int = 0
    source_file: str = ""

# ===== 詞法分析器 =====

class DTSLexer:
    """DTS 語法詞法分析器"""

    def __init__(self):
        self.text = ""
        self.pos = 0
        self.line = 1
        self.column = 1

    def tokenize(self, text: str, source_file: str) -> List[Token]:
        """將 DTS 文本轉換為 token 列表"""
        self.text = text
        self.pos = 0
        self.line = 1
        self.column = 1
        self.source_file = source_file

        tokens = []

        while self.pos < len(self.text):
            token = self._next_token()
            if token:
                tokens.append(token)
        
        tokens.append(Token(TokenType.EOF, "", self.line, self.column))
        return tokens
    
    def _next_token(self) -> Optional[Token]:
        """獲取下一個 token"""
        self._skip_whitespace()

        if self.pos >= len(self.text):
            return None
        
        start_line = self.line
        start_column = self.column

        char = self.text[self.pos]

        # 註釋處理
        if char == '/' and self._peek() == '*':
            return self._read_block_comment(start_line, start_column)
        elif char == '/' and self._peek() == '/':
            return self._read_line_comment(start_line, start_column)
        
        # DTS 版本聲明
        if char == '/' and self.text[self.pos:].startswith('/dts-v1/'):
            self.pos += 8
            self.column += 8
            return Token(TokenType.DTS_VERSION, "/dts-v1/", start_line, start_column)

        # Plugin 聲明
        if char == '/' and self.text[self.pos:].startswith('/plugin/'):
            self.pos += 8
            self.column += 8
            return Token(TokenType.PLUGIN, "/plugin/", start_line, start_column)

        # 字符串
        if char == '"':
            return self._read_string(start_line, start_column)

        # 數字
        if char.isdigit() or (char == '0' and self._peek() in 'xX'):
            return self._read_number(start_line, start_column)

        # 標識符
        if char.isalpha() or char == '_' or char == '-':
            return self._read_identifier(start_line, start_column)
        
        # 單字符 tokens
        single_chars = {
            '{': TokenType.LBRACE,
            '}': TokenType.RBRACE,
            '<': TokenType.LANGLE,
            '>': TokenType.RANGLE,
            '(': TokenType.LPAREN,
            ')': TokenType.RPAREN,
            '[': TokenType.LBRACKET,
            ']': TokenType.RBRACKET,
            ';': TokenType.SEMICOLON,
            ',': TokenType.COMMA,
            '=': TokenType.EQUALS,
            '&': TokenType.AMPERSAND,
            ':': TokenType.COLON,
            '/': TokenType.SLASH,
        }

        if char in single_chars:
            self.pos += 1
            self.column += 1
            return Token(single_chars[char], char, start_line, start_column)
        
        # 未知字符 - 跳過
        self.pos += 1
        self.column += 1
        return None
    
    def _skip_whitespace(self):
        """跳過空白字符"""
        while self.pos < len(self.text) and self.text[self.pos] in ' \t\r\n':
            if self.text[self.pos] == '\n':
                self.line += 1
                self.column = 1
            else:
                self.column += 1
            self.pos += 1

    def _peek(self, offset: int = 1) -> str:
        """查看下一個字符而不消費它"""
        peek_pos = self.pos + offset
        return self.text[peek_pos] if peek_pos < len(self.text) else ''
    
    def _read_string(self, start_line: int, start_column: int) -> Token:
        """讀取字符串 token"""
        value = ''
        self.pos += 1
        self.column += 1

        while self.pos < len(self.text) and self.text[self.pos] != '"':
            if self.text[self.pos] == '\\':
                self.pos += 1
                self.column += 1
                if self.pos < len(self.text):
                    escape_char = self.text[self.pos]
                    if escape_char == 'n':
                        value += '\n'
                    elif escape_char == 't':
                        value += '\t'
                    elif escape_char == '"':
                        value += '"'
                    elif escape_char == '\\':
                        value += '\\'
                    else:
                        value += escape_char
                    self.pos += 1
                    self.column += 1
            else:
                value += self.text[self.pos]
                self.pos += 1
                self.column += 1
        
        if self.pos < len(self.text):
            self.pos += 1
            self.column += 1

        return Token(TokenType.STRING, value, start_line, start_column)
    
    def _read_number(self, start_line: int, start_column: int) -> Token:
        """讀取數字"""
        value = ''

        # 處理 0x 開頭的十六進制數字
        if (self.text[self.pos] == '0' and
            self.pos + 1 < len(self.text) and
            self.text[self.pos + 1].lower() == 'x'):
            value += self.text[self.pos:self.pos+2]
            self.pos += 2
            self.column += 2

            while (self.pos < len(self.text) and
                   (self.text[self.pos].isdigit() or
                    self.text[self.pos].lower() in 'abcdef')):
                value += self.text[self.pos]
                self.pos += 1
                self.column += 1
        else:
            # 普通數字
            while self.pos < len(self.text) and self.text[self.pos].isdigit():
                value += self.text[self.pos]
                self.pos += 1
                self.column += 1
        
        return Token(TokenType.NUMBER, value, start_line, start_column)
    
    def _read_identifier(self, start_line: int, start_column: int) -> Token:
        """讀取標識符"""
        value = ''
        
        while (self.pos < len(self.text) and 
               (self.text[self.pos].isalnum() or 
                self.text[self.pos] in '_-@,.')):
            value += self.text[self.pos]
            self.pos += 1
            self.column += 1
            
        return Token(TokenType.IDENTIFIER, value, start_line, start_column)
    
    def _read_block_comment(self, start_line: int, start_column: int) -> Token:
        """讀取塊註釋 /* ... */"""
        value = ''
        self.pos += 2  # 跳過 /*
        self.column += 2
        
        while self.pos + 1 < len(self.text):
            if self.text[self.pos] == '*' and self.text[self.pos + 1] == '/':
                self.pos += 2
                self.column += 2
                break
            if self.text[self.pos] == '\n':
                self.line += 1
                self.column = 1
            else:
                self.column += 1
            value += self.text[self.pos]
            self.pos += 1
            
        return Token(TokenType.COMMENT, value, start_line, start_column)
    
    def _read_line_comment(self, start_line: int, start_column: int) -> Token:
        """讀取行註釋 // ..."""
        value = ''
        self.pos += 2  # 跳過 //
        self.column += 2
        
        while self.pos < len(self.text) and self.text[self.pos] != '\n':
            value += self.text[self.pos]
            self.pos += 1
            self.column += 1
            
        return Token(TokenType.COMMENT, value, start_line, start_column)

# ===== 語法分析器 =====

class DTSParser:
    """DTS 語法分析器"""

    def __init__(self, verbose: bool = False):
        self.tokens = []
        self.pos = 0
        self.source_file = ""
        self.verbose = verbose

    def parse(self, text: str, source_file: str = "", verbose: bool = False) -> ASTNode:
        """解析 DTS 語法，返回 AST"""
        lexer = DTSLexer()
        self.tokens = lexer.tokenize(text, source_file)
        self.pos = 0
        self.source_file = source_file
        self.verbose = verbose or self.verbose
        
        if self.verbose:
            print(f"  Parsing {len(self.tokens)} tokens from {source_file}")
            
        return self._parse_root()
    
    def _current_token(self) -> Token:
        """獲取當前 token"""
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return self.tokens[-1]  # EOF token
    
    def _advance(self):
        """前進到下一個 token"""
        if self.pos < len(self.tokens) - 1:
            self.pos += 1

    def _match(self, token_type: TokenType) -> bool:
        """檢查當前 token 是否匹配給定類型"""
        return self._current_token().type == token_type
    
    def _consume(self, token_type: TokenType) -> Token:
        """消費當前 token，如果類型不匹配則拋出錯誤"""
        token = self._current_token()
        if token.type != token_type:
            # 增強錯誤信息，顯示更多上下文
            context_tokens = []
            for i in range(max(0, self.pos-3), min(len(self.tokens), self.pos+4)):
                marker = " <-- HERE" if i == self.pos else ""
                t = self.tokens[i]
                context_tokens.append(f"  {i}: {t.type.name} '{t.value}' (line {t.line}){marker}")
            
            error_msg = f"Expected token {token_type.name}, got {token.type.name} at line {token.line}, column {token.column}\n"
            error_msg += "Token context:\n" + "\n".join(context_tokens)
            raise SyntaxError(error_msg)
        self._advance()
        return token
    
    def _skip_comments(self):
        """跳過註釋"""
        while self._match(TokenType.COMMENT):
            self._advance()

    def _parse_root(self) -> ASTNode:
        """解析根節點 - 修復版本"""
        self._skip_comments()

        # 跳過 DTS 版本聲明
        if self._match(TokenType.DTS_VERSION):
            self._advance()
            if self._match(TokenType.SEMICOLON):
                self._advance()
        
        # 跳過 plugin 聲明
        if self._match(TokenType.PLUGIN):
            self._advance()
            if self._match(TokenType.SEMICOLON):
                self._advance()

        self._skip_comments()
        
        # ✅ 修復：處理預處理後可能出現的頂層標籤定義
        saved_labels = []
        while self._match(TokenType.IDENTIFIER):
            # 檢查是否是標籤定義（identifier : ）
            if (self.pos + 1 < len(self.tokens) and 
                self.tokens[self.pos + 1].type == TokenType.COLON):
                
                label_name = self._consume(TokenType.IDENTIFIER).value
                self._consume(TokenType.COLON)
                saved_labels.append(label_name)
                
                if self.verbose:
                    print(f"  Found top-level label: {label_name}")
                
                self._skip_comments()
                
                # 如果標籤後面直接跟著節點定義，跳出循環
                if self._match(TokenType.SLASH) or self._match(TokenType.IDENTIFIER):
                    break
            else:
                # 不是標籤定義，跳出循環
                break

        self._skip_comments()

        # 解析根節點
        if self._match(TokenType.SLASH):
            root_node = self._parse_node()
            # 將保存的頂層標籤添加到根節點
            root_node.labels.extend(saved_labels)
            return root_node
            
        elif self._match(TokenType.IDENTIFIER):
            # ✅ 修復：創建虛擬根節點來包含頂層內容
            if self.verbose:
                print("  Creating virtual root node for top-level content")
                
            virtual_root = ASTNode(
                name="/",
                labels=saved_labels,
                properties={},
                children={},
                line=self._current_token().line,
                column=self._current_token().column,
                source_file=self.source_file
            )
            
            # 解析所有頂層內容並加入到虛擬根節點
            while not self._match(TokenType.EOF):
                self._skip_comments()
                if self._match(TokenType.EOF):
                    break
                    
                try:
                    child_node = self._parse_node()
                    virtual_root.children[child_node.name] = child_node
                except Exception as e:
                    if self.verbose:
                        print(f"  Warning: Failed to parse top-level content: {e}")
                    # 跳過有問題的 token
                    if not self._match(TokenType.EOF):
                        self._advance()
                        
            return virtual_root
            
        else:
            # ✅ 改進的錯誤信息
            current = self._current_token()
            
            if current.type == TokenType.EOF:
                raise SyntaxError(f"Empty file or no root node found in {self.source_file}")
            
            # 顯示上下文信息
            context_info = []
            start_idx = max(0, self.pos - 3)
            end_idx = min(len(self.tokens), self.pos + 3)
            
            for i in range(start_idx, end_idx):
                token = self.tokens[i]
                marker = " <-- HERE" if i == self.pos else ""
                context_info.append(f"  {i}: {token.type.name} '{token.value}' (line {token.line}){marker}")
            
            error_msg = f"""Expected root node starting with '/' or valid content, got {current.type.name} '{current.value}' at line {current.line}

File: {self.source_file}
Context:
{chr(10).join(context_info)}

Suggestions:
- Check if file starts with /dts-v1/; and has root node / {{ ... }}
- Verify include files contain valid node definitions
- Check for unbalanced braces or missing semicolons"""

            raise SyntaxError(error_msg)
        
    def _parse_node(self) -> ASTNode:
        """解析節點"""
        self._skip_comments()
        
        labels = []
        
        # 解析標籤
        while True:
            if self._match(TokenType.IDENTIFIER):
                # 檢查是否是 label (後面跟 :)
                if (self.pos + 1 < len(self.tokens) and 
                    self.tokens[self.pos + 1].type == TokenType.COLON):
                    label = self._consume(TokenType.IDENTIFIER).value
                    self._consume(TokenType.COLON)
                    labels.append(label)
                else:
                    break
            else:
                break
                
        # 解析節點名稱
        name_token = self._current_token()
        if self._match(TokenType.SLASH):
            self._advance()
            name = "/"  # 根節點
        elif self._match(TokenType.IDENTIFIER):
            name = self._consume(TokenType.IDENTIFIER).value
        else:
            raise SyntaxError(f"Expected node name at line {name_token.line}")
            
        node = ASTNode(
            name=name,
            labels=labels,
            properties={},
            children={},
            line=name_token.line,
            column=name_token.column,
            source_file=self.source_file
        )
        
        self._consume(TokenType.LBRACE)
        
        # 解析節點內容
        while not self._match(TokenType.RBRACE):
            self._skip_comments()
            
            if self._match(TokenType.RBRACE):
                break
                
            # 檢查是否是子節點還是屬性
            saved_pos = self.pos
            
            # 跳過可能的 labels
            while (self._match(TokenType.IDENTIFIER) and 
                   self.pos + 1 < len(self.tokens) and
                   self.tokens[self.pos + 1].type == TokenType.COLON):
                self._advance()  # label
                self._advance()  # :
                
            # 檢查是否是節點（有 {）或屬性（有 = 或 ;）
            if self._match(TokenType.IDENTIFIER) or self._match(TokenType.SLASH):
                # 向前掃描找到 { 或 = 或 ;
                temp_pos = self.pos
                found_brace = False
                found_equals = False
                found_semicolon = False
                
                # 跳過當前標識符
                if self._match(TokenType.IDENTIFIER):
                    temp_pos += 1
                elif self._match(TokenType.SLASH):
                    temp_pos += 1
                
                # 繼續掃描
                while temp_pos < len(self.tokens):
                    token_type = self.tokens[temp_pos].type
                    if token_type == TokenType.LBRACE:
                        found_brace = True
                        break
                    elif token_type == TokenType.EQUALS:
                        found_equals = True
                        break
                    elif token_type == TokenType.SEMICOLON:
                        found_semicolon = True
                        break
                    elif token_type == TokenType.RBRACE:
                        break
                    temp_pos += 1
                    
                # 基於找到的 token 來決定這是節點還是屬性
                if found_brace:
                    # 有大括號 = 這是子節點
                    child = self._parse_node()
                    node.children[child.name] = child
                elif found_equals or found_semicolon:
                    # 有等號或分號 = 這是屬性
                    self.pos = saved_pos
                    prop_name, prop_value = self._parse_property()
                    node.properties[prop_name] = prop_value
                else:
                    # 默認當作屬性處理
                    self.pos = saved_pos
                    prop_name, prop_value = self._parse_property()
                    node.properties[prop_name] = prop_value
            else:
                # 不是標識符或斜槓，當作屬性處理
                self.pos = saved_pos
                prop_name, prop_value = self._parse_property()
                node.properties[prop_name] = prop_value
                
        self._consume(TokenType.RBRACE)
        
        # 可選的分號
        if self._match(TokenType.SEMICOLON):
            self._advance()
            
        return node
        
    def _parse_property(self) -> Tuple[str, PropertyValue]:
        """解析屬性"""
        self._skip_comments()
        
        # 屬性名稱
        if not self._match(TokenType.IDENTIFIER):
            token = self._current_token()
            raise SyntaxError(f"Expected property name at line {token.line}")
            
        prop_name = self._consume(TokenType.IDENTIFIER).value
        
        # 檢查是否只是聲明（沒有值）
        if self._match(TokenType.SEMICOLON):
            self._advance()
            return prop_name, PropertyValue(
                type="empty",
                value=None,
                raw=""
            )
            
        self._consume(TokenType.EQUALS)
        
        # 解析屬性值
        prop_value = self._parse_property_value()
        
        self._consume(TokenType.SEMICOLON)
        
        return prop_name, prop_value
        
    def _parse_property_value(self) -> PropertyValue:
        """解析屬性值"""
        self._skip_comments()
        
        if self._match(TokenType.STRING):
            # 字符串值
            token = self._consume(TokenType.STRING)
            return PropertyValue(
                type="string",
                value=token.value,
                raw=f'"{token.value}"'
            )
            
        elif self._match(TokenType.LANGLE):
            # 數組值 <...>
            all_values = []
            all_raw_parts = []
            
            while self._match(TokenType.LANGLE):
                self._advance()  # consume <
                values = []
                raw_parts = ["<"]
                
                while not self._match(TokenType.RANGLE):
                    self._skip_comments()
                    
                    if self._match(TokenType.NUMBER):
                        token = self._consume(TokenType.NUMBER)
                        # 轉換數字
                        if token.value.startswith('0x'):
                            value = int(token.value, 16)
                        else:
                            value = int(token.value)
                        values.append(value)
                        raw_parts.append(token.value)
                        
                    elif self._match(TokenType.AMPERSAND):
                        # phandle 引用 &label
                        self._advance()  # consume &
                        if self._match(TokenType.IDENTIFIER):
                            label = self._consume(TokenType.IDENTIFIER).value
                            values.append(f"&{label}")
                            raw_parts.extend(["&", label])
                        else:
                            raise SyntaxError("Expected label after &")
                    
                    elif self._match(TokenType.SLASH):
                        # 處理 /bits/ 語法
                        self._advance()  # consume /
                        if self._match(TokenType.IDENTIFIER) and self._current_token().value == "bits":
                            self._advance()  # consume "bits"
                            self._consume(TokenType.SLASH)  # consume /
                            # 接下來應該是位寬數字
                            if self._match(TokenType.NUMBER):
                                bits = self._consume(TokenType.NUMBER).value
                                raw_parts.append(f"/bits/{bits}")
                            else:
                                raise SyntaxError("Expected bit width after /bits/")
                        else:
                            raise SyntaxError("Unexpected / in property value")
                            
                    # 處理數組內的逗號
                    if self._match(TokenType.COMMA):
                        self._advance()
                        raw_parts.append(",")
                        
                self._consume(TokenType.RANGLE)
                raw_parts.append(">")
                
                # 將這個 <...> 組的值添加到總體值中
                all_values.extend(values)
                all_raw_parts.extend(raw_parts)
                
                # 檢查是否有更多的 <...> 組（用逗號分隔）
                if self._match(TokenType.COMMA):
                    self._advance()  # consume comma between <...> groups
                    all_raw_parts.append(",")
                    self._skip_comments()
                    
                    # 如果後面不是 <，則跳出循環
                    if not self._match(TokenType.LANGLE):
                        break
                else:
                    # 沒有逗號，結束解析
                    break
            
            # 判斷是否為 phandle 引用
            has_phandle = any(isinstance(v, str) and v.startswith('&') for v in all_values)
            
            return PropertyValue(
                type="phandle" if has_phandle else "array",
                value=all_values,
                raw=" ".join(all_raw_parts)
            )
        
        elif self._match(TokenType.AMPERSAND):
            # 處理單獨的 phandle 引用 &label
            self._advance()  # consume &
            if self._match(TokenType.IDENTIFIER):
                label = self._consume(TokenType.IDENTIFIER).value
                return PropertyValue(
                    type="phandle",
                    value=f"&{label}",
                    raw=f"&{label}"
                )
            else:
                raise SyntaxError("Expected label after &")
                
        elif self._match(TokenType.IDENTIFIER):
            # 處理裸露的標識符
            token = self._consume(TokenType.IDENTIFIER)
            return PropertyValue(
                type="identifier",
                value=token.value,
                raw=token.value
            )
            
        else:
            token = self._current_token()
            raise SyntaxError(f"Unexpected token {token.type.name} at line {token.line}, value: '{token.value}'")

# 導出主要類別
__all__ = ['DTSParser', 'DTSLexer', 'ASTNode', 'PropertyValue', 'Token', 'TokenType']
