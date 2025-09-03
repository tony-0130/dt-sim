"""
parsers/dts_parser.py - DTS syntax parser
Completely independent version, does not depend on any core modules
"""

import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

# ===== Token Definitions =====

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
    """DTS AST Node - used internally by parser"""
    name: str
    labels: List[str]
    properties: Dict[str, PropertyValue]
    children: Dict[str, 'ASTNode']
    line: int = 0
    column: int = 0
    source_file: str = ""
    is_reference: bool = False  # True if this is a &label reference

# ===== Lexical Analyzer =====

class DTSLexer:
    """DTS lexical analyzer"""

    def __init__(self):
        self.text = ""
        self.pos = 0
        self.line = 1
        self.column = 1

    def tokenize(self, text: str, source_file: str) -> List[Token]:
        """Convert DTS text to token list"""
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
        """Get next token"""
        self._skip_whitespace()

        if self.pos >= len(self.text):
            return None
        
        start_line = self.line
        start_column = self.column

        char = self.text[self.pos]

        # Comment processing
        if char == '/' and self._peek() == '*':
            return self._read_block_comment(start_line, start_column)
        elif char == '/' and self._peek() == '/':
            return self._read_line_comment(start_line, start_column)
        
        # DTS version declaration
        if char == '/' and self.text[self.pos:].startswith('/dts-v1/'):
            self.pos += 8
            self.column += 8
            return Token(TokenType.DTS_VERSION, "/dts-v1/", start_line, start_column)

        # Plugin declaration
        if char == '/' and self.text[self.pos:].startswith('/plugin/'):
            self.pos += 8
            self.column += 8
            return Token(TokenType.PLUGIN, "/plugin/", start_line, start_column)

        # String
        if char == '"':
            return self._read_string(start_line, start_column)

        # Number
        if char.isdigit() or (char == '0' and self._peek() in 'xX'):
            return self._read_number(start_line, start_column)

        # Identifier
        if char.isalpha() or char == '_' or char == '-':
            return self._read_identifier(start_line, start_column)
        
        # Single character tokens
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
        
        # Unknown character - skip
        self.pos += 1
        self.column += 1
        return None
    
    def _skip_whitespace(self):
        """Skip whitespace characters"""
        while self.pos < len(self.text) and self.text[self.pos] in ' \t\r\n':
            if self.text[self.pos] == '\n':
                self.line += 1
                self.column = 1
            else:
                self.column += 1
            self.pos += 1

    def _peek(self, offset: int = 1) -> str:
        """Look at next character without consuming it"""
        peek_pos = self.pos + offset
        return self.text[peek_pos] if peek_pos < len(self.text) else ''
    
    def _read_string(self, start_line: int, start_column: int) -> Token:
        """Read string token"""
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
        """Read number"""
        value = ''

        # Handle hexadecimal numbers starting with 0x
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
            # Regular number
            while self.pos < len(self.text) and self.text[self.pos].isdigit():
                value += self.text[self.pos]
                self.pos += 1
                self.column += 1
        
        return Token(TokenType.NUMBER, value, start_line, start_column)
    
    def _read_identifier(self, start_line: int, start_column: int) -> Token:
        """Read identifier"""
        value = ''
        
        while (self.pos < len(self.text) and 
               (self.text[self.pos].isalnum() or 
                self.text[self.pos] in '_-@,.')):
            value += self.text[self.pos]
            self.pos += 1
            self.column += 1
            
        return Token(TokenType.IDENTIFIER, value, start_line, start_column)
    
    def _read_block_comment(self, start_line: int, start_column: int) -> Token:
        """Read block comment /* ... */"""
        value = ''
        self.pos += 2  # Skip /*
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
        """Read line comment // ..."""
        value = ''
        self.pos += 2  # Skip //
        self.column += 2
        
        while self.pos < len(self.text) and self.text[self.pos] != '\n':
            value += self.text[self.pos]
            self.pos += 1
            self.column += 1
            
        return Token(TokenType.COMMENT, value, start_line, start_column)

# ===== Syntax Analyzer =====

class DTSParser:
    """DTS syntax analyzer"""

    def __init__(self, verbose: bool = False):
        self.tokens = []
        self.pos = 0
        self.source_file = ""
        self.verbose = verbose

    def parse(self, text: str, source_file: str = "", verbose: bool = False) -> ASTNode:
        """Parse DTS syntax and return AST"""
        lexer = DTSLexer()
        self.tokens = lexer.tokenize(text, source_file)
        self.pos = 0
        self.source_file = source_file
        self.verbose = verbose or self.verbose
        
        if self.verbose:
            print(f"  Parsing {len(self.tokens)} tokens from {source_file}")
            
        return self._parse_root()
    
    def _current_token(self) -> Token:
        """Get current token"""
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return self.tokens[-1]  # EOF token
    
    def _advance(self):
        """Advance to next token"""
        if self.pos < len(self.tokens) - 1:
            self.pos += 1

    def _match(self, token_type: TokenType) -> bool:
        """Check if current token matches given type"""
        return self._current_token().type == token_type
    
    def _consume(self, token_type: TokenType) -> Token:
        """Consume current token, throw error if type doesn't match"""
        token = self._current_token()
        if token.type != token_type:
            # Enhanced error message with more context
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
        """Skip comments"""
        while self._match(TokenType.COMMENT):
            self._advance()

    def _parse_root(self) -> ASTNode:
        """Parse root node - fixed version"""
        self._skip_comments()

        # Skip DTS version declaration
        if self._match(TokenType.DTS_VERSION):
            self._advance()
            if self._match(TokenType.SEMICOLON):
                self._advance()
        
        # Skip plugin declaration
        if self._match(TokenType.PLUGIN):
            self._advance()
            if self._match(TokenType.SEMICOLON):
                self._advance()

        self._skip_comments()
        
        # ✅ Fix: Handle top-level label definitions that may appear after preprocessing
        saved_labels = []
        while self._match(TokenType.IDENTIFIER):
            # Check if this is a label definition (identifier : )
            if (self.pos + 1 < len(self.tokens) and 
                self.tokens[self.pos + 1].type == TokenType.COLON):
                
                label_name = self._consume(TokenType.IDENTIFIER).value
                self._consume(TokenType.COLON)
                saved_labels.append(label_name)
                
                if self.verbose:
                    print(f"  Found top-level label: {label_name}")
                
                self._skip_comments()
                
                # If label is followed directly by node definition, break out of loop
                if self._match(TokenType.SLASH) or self._match(TokenType.IDENTIFIER):
                    break
            else:
                # Not a label definition, break out of loop
                break

        self._skip_comments()

        # Parse root node or handle overlay syntax
        if self._match(TokenType.SLASH):
            root_node = self._parse_node()
        elif self._match(TokenType.AMPERSAND):
            # Handle overlay file &{/} or &label syntax
            root_node = self._parse_node()
            # Add saved top-level labels to root node
            root_node.labels.extend(saved_labels)
            
            # Check if there's more top-level content (like &references)
            self._skip_comments()
            if not self._match(TokenType.EOF):
                if self.verbose:
                    current = self._current_token()
                    print(f"  Found additional top-level content after root: {current.type.name} '{current.value}'")
                
                # Create virtual root node to contain all content
                virtual_root = ASTNode(
                    name="/",
                    labels=root_node.labels,
                    properties=root_node.properties,
                    children=root_node.children,
                    line=root_node.line,
                    column=root_node.column,
                    source_file=root_node.source_file
                )
                
                # Parse remaining top-level content
                while not self._match(TokenType.EOF):
                    self._skip_comments()
                    if self._match(TokenType.EOF):
                        break
                    
                    if self.verbose:
                        current = self._current_token()
                        print(f"    Parsing additional content: {current.type.name} '{current.value}'")
                        
                    try:
                        child_node = self._parse_node()
                        virtual_root.children[child_node.name] = child_node
                        if self.verbose:
                            ref_info = " (reference)" if child_node.is_reference else ""
                            print(f"    Added top-level node: {child_node.name}{ref_info}")
                    except Exception as e:
                        if self.verbose:
                            print(f"  Warning: Failed to parse additional content: {e}")
                        if not self._match(TokenType.EOF):
                            self._advance()
                            
                return virtual_root
            else:
                return root_node
            
        elif self._match(TokenType.IDENTIFIER):
            # ✅ Fix: Create virtual root node to contain top-level content
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
            
            # Parse all top-level content and add to virtual root node
            while not self._match(TokenType.EOF):
                self._skip_comments()
                if self._match(TokenType.EOF):
                    break
                
                if self.verbose:
                    current = self._current_token()
                    print(f"    Parsing top-level content: {current.type.name} '{current.value}'")
                    
                try:
                    child_node = self._parse_node()
                    virtual_root.children[child_node.name] = child_node
                    if self.verbose:
                        ref_info = " (reference)" if child_node.is_reference else ""
                        print(f"    Added top-level node: {child_node.name}{ref_info}")
                except Exception as e:
                    if self.verbose:
                        print(f"  Warning: Failed to parse top-level content: {e}")
                    # Skip problematic token
                    if not self._match(TokenType.EOF):
                        self._advance()
                        
            return virtual_root
            
        else:
            # ✅ Improved error message
            current = self._current_token()
            
            if current.type == TokenType.EOF:
                raise SyntaxError(f"Empty file or no root node found in {self.source_file}")
            
            # Display context information
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
        """Parse node"""
        self._skip_comments()
        
        labels = []
        
        
        # Parse labels (can be IDENTIFIER or NUMBER)
        while True:
            if self._match(TokenType.IDENTIFIER) or self._match(TokenType.NUMBER):
                # Check if this is a label (followed by :)
                if (self.pos + 1 < len(self.tokens) and 
                    self.tokens[self.pos + 1].type == TokenType.COLON):
                    if self._match(TokenType.IDENTIFIER):
                        label = self._consume(TokenType.IDENTIFIER).value
                    else:
                        label = self._consume(TokenType.NUMBER).value
                    self._consume(TokenType.COLON)
                    labels.append(label)
                else:
                    break
            else:
                break
                
        # Parse node name
        name_token = self._current_token()
        is_reference = False
        
        if self._match(TokenType.SLASH):
            self._advance()
            name = "/"  # Root node
        elif self._match(TokenType.AMPERSAND):
            # Handle node reference &label or &{/}
            self._advance()  # consume &
            if self._match(TokenType.IDENTIFIER):
                name = self._consume(TokenType.IDENTIFIER).value
                is_reference = True
            elif self._match(TokenType.LBRACE):
                # Handle &{/} syntax
                self._advance()  # consume {
                if self._match(TokenType.SLASH):
                    self._advance()  # consume /
                    self._consume(TokenType.RBRACE)  # consume }
                    name = "/"  # Root node reference
                    is_reference = True
                else:
                    raise SyntaxError(f"Expected '/' after '&{{' at line {name_token.line}")
            else:
                raise SyntaxError(f"Expected label name or '{{/' after & at line {name_token.line}")
        elif self._match(TokenType.IDENTIFIER):
            name = self._consume(TokenType.IDENTIFIER).value
        elif self._match(TokenType.NUMBER):
            # DTS allows numeric node names (e.g., "0: cpu@0")
            name = self._consume(TokenType.NUMBER).value
        else:
            raise SyntaxError(f"Expected node name at line {name_token.line}")
            
        node = ASTNode(
            name=name,
            labels=labels,
            properties={},
            children={},
            line=name_token.line,
            column=name_token.column,
            source_file=self.source_file,
            is_reference=is_reference
        )
        
        self._consume(TokenType.LBRACE)
        
        # Parse node content
        while not self._match(TokenType.RBRACE):
            self._skip_comments()
            
            if self._match(TokenType.RBRACE):
                break
                
            # Check if this is a child node or property
            saved_pos = self.pos
            
            # Skip possible labels (can be IDENTIFIER or NUMBER)
            while ((self._match(TokenType.IDENTIFIER) or self._match(TokenType.NUMBER)) and 
                   self.pos + 1 < len(self.tokens) and
                   self.tokens[self.pos + 1].type == TokenType.COLON):
                self._advance()  # label
                self._advance()  # :
                
            # Check if this is a node (has {) or property (has = or ;)
            if self._match(TokenType.IDENTIFIER) or self._match(TokenType.SLASH) or self._match(TokenType.NUMBER):
                # Scan forward to find { or = or ;
                temp_pos = self.pos
                found_brace = False
                found_equals = False
                found_semicolon = False
                
                # Skip current identifier
                if self._match(TokenType.IDENTIFIER):
                    temp_pos += 1
                elif self._match(TokenType.SLASH):
                    temp_pos += 1
                
                # Continue scanning
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
                    
                # Based on found token, decide if this is a node or property
                if found_brace:
                    # Has brace = this is a child node
                    # Reset position to start, let _parse_node handle labels
                    self.pos = saved_pos
                    child = self._parse_node()
                    node.children[child.name] = child
                elif found_equals or found_semicolon:
                    # Has equals or semicolon = this is a property
                    self.pos = saved_pos
                    prop_name, prop_value = self._parse_property()
                    node.properties[prop_name] = prop_value
                else:
                    # Default to treating as property
                    self.pos = saved_pos
                    prop_name, prop_value = self._parse_property()
                    node.properties[prop_name] = prop_value
            else:
                # Not identifier or slash, treat as property
                self.pos = saved_pos
                prop_name, prop_value = self._parse_property()
                node.properties[prop_name] = prop_value
                
        self._consume(TokenType.RBRACE)
        
        # Optional semicolon
        if self._match(TokenType.SEMICOLON):
            self._advance()
            
        return node
        
    def _parse_property(self) -> Tuple[str, PropertyValue]:
        """Parse property"""
        self._skip_comments()
        
        # Property name
        if not self._match(TokenType.IDENTIFIER):
            token = self._current_token()
            raise SyntaxError(f"Expected property name at line {token.line}")
            
        prop_name = self._consume(TokenType.IDENTIFIER).value
        
        # Check if this is just a declaration (no value)
        if self._match(TokenType.SEMICOLON):
            self._advance()
            return prop_name, PropertyValue(
                type="empty",
                value=None,
                raw=""
            )
            
        self._consume(TokenType.EQUALS)
        
        # Parse property value
        prop_value = self._parse_property_value()
        
        self._consume(TokenType.SEMICOLON)
        
        return prop_name, prop_value
        
    def _parse_property_value(self) -> PropertyValue:
        """Parse property value"""
        self._skip_comments()
        
        if self._match(TokenType.STRING):
            # String value - may be single string or comma-separated string array
            strings = []
            raw_parts = []
            
            # First string
            token = self._consume(TokenType.STRING)
            strings.append(token.value)
            raw_parts.append(f'"{token.value}"')
            
            # Check for more comma-separated strings
            while self._match(TokenType.COMMA):
                self._advance()  # consume comma
                raw_parts.append(", ")
                self._skip_comments()
                
                if self._match(TokenType.STRING):
                    token = self._consume(TokenType.STRING)
                    strings.append(token.value)
                    raw_parts.append(f'"{token.value}"')
                else:
                    raise SyntaxError(f"Expected string after comma at line {self._current_token().line}")
            
            # If only one string, return single string; otherwise return string array
            if len(strings) == 1:
                return PropertyValue(
                    type="string",
                    value=strings[0],
                    raw=raw_parts[0]
                )
            else:
                return PropertyValue(
                    type="string_array",
                    value=strings,
                    raw="".join(raw_parts)
                )
            
        elif self._match(TokenType.LANGLE):
            # Array value <...>
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
                        # Convert number
                        if token.value.startswith('0x'):
                            value = int(token.value, 16)
                        else:
                            value = int(token.value)
                        values.append(value)
                        raw_parts.append(token.value)
                        
                    elif self._match(TokenType.AMPERSAND):
                        # phandle reference &label
                        self._advance()  # consume &
                        if self._match(TokenType.IDENTIFIER):
                            label = self._consume(TokenType.IDENTIFIER).value
                            values.append(f"&{label}")
                            raw_parts.extend(["&", label])
                        elif self._match(TokenType.NUMBER):
                            # Handle numeric phandle references like &0, &1 etc.
                            label = self._consume(TokenType.NUMBER).value
                            values.append(f"&{label}")
                            raw_parts.extend(["&", label])
                        else:
                            raise SyntaxError("Expected label after &")
                    
                    elif self._match(TokenType.SLASH):
                        # Handle /bits/ syntax
                        self._advance()  # consume /
                        if self._match(TokenType.IDENTIFIER) and self._current_token().value == "bits":
                            self._advance()  # consume "bits"
                            self._consume(TokenType.SLASH)  # consume /
                            # Next should be bit width number
                            if self._match(TokenType.NUMBER):
                                bits = self._consume(TokenType.NUMBER).value
                                raw_parts.append(f"/bits/{bits}")
                            else:
                                raise SyntaxError("Expected bit width after /bits/")
                        else:
                            raise SyntaxError("Unexpected / in property value")
                            
                    # Handle commas within array
                    if self._match(TokenType.COMMA):
                        self._advance()
                        raw_parts.append(",")
                        
                self._consume(TokenType.RANGLE)
                raw_parts.append(">")
                
                # Add values from this <...> group to overall values
                all_values.extend(values)
                all_raw_parts.extend(raw_parts)
                
                # Check for more <...> groups (separated by commas)
                if self._match(TokenType.COMMA):
                    self._advance()  # consume comma between <...> groups
                    all_raw_parts.append(",")
                    self._skip_comments()
                    
                    # If next is not <, break out of loop
                    if not self._match(TokenType.LANGLE):
                        break
                else:
                    # No comma, end parsing
                    break
            
            # Determine if this is a phandle reference
            has_phandle = any(isinstance(v, str) and v.startswith('&') for v in all_values)
            
            return PropertyValue(
                type="phandle" if has_phandle else "array",
                value=all_values,
                raw=" ".join(all_raw_parts)
            )
        
        elif self._match(TokenType.AMPERSAND):
            # Handle standalone phandle reference &label
            self._advance()  # consume &
            if self._match(TokenType.IDENTIFIER):
                label = self._consume(TokenType.IDENTIFIER).value
                return PropertyValue(
                    type="phandle",
                    value=f"&{label}",
                    raw=f"&{label}"
                )
            elif self._match(TokenType.NUMBER):
                # Handle numeric phandle references like &0, &1 etc.
                label = self._consume(TokenType.NUMBER).value
                return PropertyValue(
                    type="phandle",
                    value=f"&{label}",
                    raw=f"&{label}"
                )
            else:
                raise SyntaxError("Expected label after &")
                
        elif self._match(TokenType.IDENTIFIER):
            # Handle bare identifier
            token = self._consume(TokenType.IDENTIFIER)
            return PropertyValue(
                type="identifier",
                value=token.value,
                raw=token.value
            )
            
        else:
            token = self._current_token()
            raise SyntaxError(f"Unexpected token {token.type.name} at line {token.line}, value: '{token.value}'")

# Export main classes
__all__ = ['DTSParser', 'DTSLexer', 'ASTNode', 'PropertyValue', 'Token', 'TokenType']
