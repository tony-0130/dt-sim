# Device Tree Parsing Specification


## Grammar (Simplified EBNF)

```ebnf
file         := { preproc | node | property }

preproc      := "#include" string
              | "#define" identifier value
              | "#ifdef" identifier { node | property } "#endif"

node         := [label ":"] [reference] node_name [ "@" address ] "{" { property | node } "};"

property     := prop_name [ "=" value_list ] ";"

label        := [A-Za-z_][A-Za-z0-9_.-]*

reference    := "&" ( label | "/" | "/{" "}" )

node_name    := [A-Za-z0-9._-]+

prop_name    := [A-Za-z0-9,._#-]+

address      := hex_number | decimal_number

value_list   := value { "," value }

value        := string
              | "<" cell_list ">"
              | "&" label
              | "&{/}"
              | number

cell_list    := number { number }

number       := decimal_number | hex_number

```

---

## Pseudo Code

```pseudo
function parse_dts(file):
    tokens = tokenize(file)   # convert input file into token stream
    context = new ParseContext()

    while not tokens.end():
        token = tokens.peek()

        if token.type == PREPROCESSOR:
            if token.value starts with "#include":
                # Call preprocessor.py to process this include
            else if token.value starts with "#define":
                # Call preprocessor.py to process this define
            tokens.consume()
            continue

        else if token.type == IDENTIFIER or token.type == REFERENCE:
            parse_node_or_property(tokens, context)

        else:
            error("Unexpected token: " + token)

    return context.root


function parse_node_or_property(tokens, context):
    # Possible forms:
    # 1. label: node_name @address { ... };
    # 2. node_name @address { ... };
    # 3. prop_name = value;
    # 4. prop_name;   (empty property)
    # 5. &reference { ... };

    label = None
    reference = None

    if tokens.lookahead(1) == ":":
        label = tokens.consume_identifier()
        tokens.consume(":")   # consume colon

    if tokens.peek() == "&":
        reference = tokens.consume_reference()

    name = tokens.consume_identifier_or_node_name()

    address = None
    if tokens.peek() == "@":
        tokens.consume("@")
        address = tokens.consume_number()

    if tokens.peek() == "{":
        # This is a node
        tokens.consume("{")
        node = new Node(label, reference, name, address)

        while tokens.peek() != "}":
            parse_node_or_property(tokens, node)

        tokens.consume("}")
        tokens.consume(";")
        context.add_node(node)

    else if tokens.peek() == "=":
        # This is a property with value
        prop_name = (label ? label + ":" : "") + name
        tokens.consume("=")
        values = parse_value_list(tokens)
        tokens.consume(";")
        context.add_property(prop_name, values)

    else if tokens.peek() == ";":
        # This is an empty property
        prop_name = (label ? label + ":" : "") + name
        tokens.consume(";")
        context.add_property(prop_name, None)

    else:
        error("Unexpected token in node/property: " + tokens.peek())


function parse_value_list(tokens):
    values = []
    while True:
        if tokens.peek() == "<":
            tokens.consume("<")
            cells = []
            while tokens.peek() != ">":
                if tokens.peek() == "&":
                    cells.append(tokens.consume_reference())
                else:
                    cells.append(tokens.consume_number())
            tokens.consume(">")
            values.append(cells)

        else if tokens.peek() == STRING:
            values.append(tokens.consume_string())

        else if tokens.peek() == "&":
            values.append(tokens.consume_reference())

        else:
            values.append(tokens.consume_number())

        if tokens.peek() == ",":
            tokens.consume(",")
            continue
        else:
            break

    return values

```
