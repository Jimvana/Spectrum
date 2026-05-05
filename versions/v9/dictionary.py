"""
Spectrum Algo — Dictionary v9
Colour ↔ Token mapping for the Spectrum encoding system.

Design rules:
  - Each token gets a unique, fixed RGB colour
  - Python keywords: vivid, saturated hues (easy to visually distinguish)
  - Operators & punctuation: mid-range, consistent tone family
  - Digits 0–9: warm amber/orange range
  - Built-in functions: cyan/aqua family (R low, G+B high)
  - Built-in types: magenta/pink family (R+B high, G low)
  - Built-in exceptions: deep crimson/maroon family
  - English control tokens: near-black (R=1, G=0, B=1–5)
  - English text punctuation: (R=1, G=1–2, B=0)
  - English words: sequential RGB starting at (3,0,0) — see english_tokens.py
  - ASCII fallback: uses the character's ordinal value directly
    as (ord, ord, ord) — greyscale — reserved range 0–127
  - Header pixel colour: (0, 0, 0) — pure black — reserved

  New in v8 (placed AFTER ENGLISH_WORDS in TOKEN_TO_RGB so they take
  precedence over any English word with the same spelling):
  - TypeScript keywords: steel-blue family    R=244, B=90
  - SQL DML/DDL keywords: deep-plum family   R=241, B=110
  - SQL aggregate functions: lighter-plum    R=242, B=110
  - Rust keywords: forest-sage family        R=243, B=70

  New in v9:
  - PHP keywords:  warm-sand family          R=245, B=80
  - PHP functions: warm-sand/light family    R=245, B=100

Version: 9  (adds PHP language support.
             Covers Python, HTML, JS, TS, CSS, SQL, Rust, PHP, and English text.)

RLE design:
  - R channel value 253 is reserved as the RLE marker
  - An RLE pixel (253, G, B) following a token pixel means
    "repeat the previous token (G*256 + B) more times"
  - Only emitted for runs of 3+ identical pixels (run of 2 = no saving)
  - Encodes up to 65,535 additional repetitions per marker pixel
  - R=253 never appears in normal token colours; Unicode code points that
    would produce R=253 via fallback encoding (Supplementary Private Use
    Area-B, U+FD0000+) won't appear in real Python source
"""

# ---------------------------------------------------------------------------
# Version tag — encoded in the header pixel's alpha channel (if RGBA),
# or as a dedicated header row in future versions.
# ---------------------------------------------------------------------------
DICT_VERSION = 9

# ---------------------------------------------------------------------------
# Python keywords  →  RGB
# Each keyword gets a colour in a distinct hue band so visual inspection
# of an encoded image gives a rough sense of structure.
# ---------------------------------------------------------------------------
KEYWORDS = {
    # Control flow — blue family
    "if":       (30,  100, 220),
    "elif":     (30,  120, 240),
    "else":     (30,  140, 255),
    "for":      (10,  80,  200),
    "while":    (10,  60,  180),
    "break":    (10,  40,  160),
    "continue": (10,  20,  140),
    "pass":     (10,  10,  120),
    "return":   (50,  160, 255),
    "yield":    (50,  140, 230),

    # Definition — green family
    "def":      (20,  200,  80),
    "class":    (20,  180,  60),
    "lambda":   (20,  160,  40),
    "async":    (40,  220, 100),
    "await":    (40,  200,  80),

    # Imports — teal family
    "import":   (0,   180, 160),
    "from":     (0,   160, 140),
    "as":       (0,   140, 120),

    # Exception handling — red family
    "try":      (220,  40,  40),
    "except":   (200,  30,  30),
    "finally":  (180,  20,  20),
    "raise":    (240,  60,  60),
    "assert":   (210,  50,  50),

    # Boolean / None — purple family
    "True":     (160,  60, 220),
    "False":    (140,  40, 200),
    "None":     (120,  20, 180),
    "and":      (170,  80, 230),
    "or":       (150,  60, 210),
    "not":      (130,  40, 190),
    "in":       (180,  90, 240),
    "is":       (190, 100, 250),

    # Scope — yellow family
    "global":   (220, 200,  10),
    "nonlocal": (200, 180,  10),
    "del":      (180, 160,  10),

    # Context managers
    "with":     (100, 200, 180),

    # Other
    "print":    (80,  180, 255),  # built-in, very common — deserves its own slot
}

# ---------------------------------------------------------------------------
# Built-in functions  →  RGB  (cyan/aqua family: low R, high G+B)
# Spread across G (100–255) and B (180–255) to avoid collisions.
# ---------------------------------------------------------------------------
BUILTINS_FUNCS = {
    "abs":          (0,  100, 200),
    "aiter":        (0,  102, 202),
    "all":          (0,  104, 204),
    "anext":        (0,  106, 206),
    "any":          (0,  108, 208),
    "ascii":        (0,  110, 210),
    "bin":          (0,  112, 212),
    "breakpoint":   (0,  114, 214),
    "callable":     (0,  116, 216),
    "chr":          (0,  118, 218),
    "compile":      (0,  120, 220),
    "copyright":    (0,  122, 222),
    "credits":      (0,  124, 224),
    "delattr":      (0,  126, 226),
    "dir":          (0,  128, 228),
    "divmod":       (0,  130, 230),
    "enumerate":    (0,  132, 232),
    "eval":         (0,  134, 234),
    "exec":         (0,  136, 236),
    "exit":         (0,  138, 238),
    "filter":       (0,  140, 240),
    "format":       (0,  142, 242),
    "getattr":      (0,  144, 244),
    "globals":      (0,  146, 246),
    "hasattr":      (0,  148, 248),
    "hash":         (0,  150, 250),
    "help":         (0,  152, 252),
    "hex":          (0,  154, 254),
    "id":           (2,  100, 200),
    "input":        (2,  104, 204),
    "isinstance":   (2,  108, 208),
    "issubclass":   (2,  112, 212),
    "iter":         (2,  116, 216),
    "len":          (2,  120, 220),
    "license":      (2,  124, 224),
    "locals":       (2,  128, 228),
    "map":          (2,  132, 232),
    "max":          (2,  136, 236),
    "memoryview":   (2,  140, 240),
    "min":          (2,  144, 244),
    "next":         (2,  148, 248),
    "oct":          (2,  152, 252),
    "open":         (2,  156, 254),
    "ord":          (4,  100, 200),
    "pow":          (4,  104, 204),
    "property":     (4,  108, 208),
    "quit":         (4,  112, 212),
    "range":        (4,  116, 216),
    "repr":         (4,  120, 220),
    "reversed":     (4,  124, 224),
    "round":        (4,  128, 228),
    "setattr":      (4,  132, 232),
    "slice":        (4,  136, 236),
    "sorted":       (4,  140, 240),
    "staticmethod": (4,  144, 244),
    "sum":          (4,  148, 248),
    "super":        (4,  152, 252),
    "vars":         (4,  156, 254),
    "zip":          (6,  100, 200),
}

# ---------------------------------------------------------------------------
# Built-in types  →  RGB  (magenta/pink family: high R+B, low G)
# ---------------------------------------------------------------------------
BUILTINS_TYPES = {
    "bool":         (200,  40, 200),
    "bytearray":    (202,  40, 202),
    "bytes":        (204,  40, 204),
    "classmethod":  (206,  40, 206),
    "complex":      (208,  40, 208),
    "dict":         (210,  40, 210),
    "float":        (212,  40, 212),
    "frozenset":    (214,  40, 214),
    "int":          (216,  40, 216),
    "list":         (218,  40, 218),
    "object":       (220,  40, 220),
    "set":          (222,  40, 222),
    "str":          (224,  40, 224),
    "tuple":        (226,  40, 226),
    "type":         (228,  40, 228),
}

# ---------------------------------------------------------------------------
# Operators and punctuation  →  RGB
# Mid-tone grey-green family to distinguish from keywords
# ---------------------------------------------------------------------------
SYMBOLS = {
    # Arithmetic
    "+":   (160, 200, 160),
    "-":   (150, 190, 150),
    "*":   (140, 180, 140),
    "/":   (130, 170, 130),
    "//":  (120, 160, 120),
    "%":   (110, 150, 110),
    "**":  (100, 140, 100),

    # Comparison
    "==":  (200, 160, 100),
    "!=":  (210, 150,  90),
    "<":   (190, 170, 110),
    ">":   (180, 160, 100),
    "<=":  (170, 150,  90),
    ">=":  (160, 140,  80),

    # Assignment
    "=":   (240, 200,  80),
    "+=":  (230, 190,  70),
    "-=":  (220, 180,  60),
    "*=":  (210, 170,  50),
    "/=":  (200, 160,  40),

    # Logical / bitwise
    "&":   (80,  140, 200),
    "|":   (70,  130, 190),
    "^":   (60,  120, 180),
    "~":   (50,  110, 170),
    "<<":  (40,  100, 160),
    ">>":  (30,   90, 150),

    # Punctuation / structure
    "(":   (220, 220, 220),
    ")":   (210, 210, 210),
    "[":   (200, 200, 240),
    "]":   (190, 190, 230),
    "{":   (240, 200, 200),
    "}":   (230, 190, 190),
    ":":   (180, 180, 180),
    ",":   (170, 170, 170),
    ".":   (160, 160, 160),
    ";":   (150, 150, 150),
    "@":   (255, 160,  80),   # decorator
    "#":   (120, 120, 120),   # comment marker
    "->":  (255, 200, 100),   # return annotation
    "...": (200, 200, 255),   # ellipsis

    # Quotes — these mark string delimiters in the token stream
    '"':   (255, 220, 180),
    "'":   (255, 210, 170),
    '"""': (255, 200, 160),
    "'''": (255, 190, 150),
}

# ---------------------------------------------------------------------------
# Digit characters  →  RGB  (warm amber range)
# ---------------------------------------------------------------------------
DIGITS = {
    "0": (255, 200,  50),
    "1": (255, 190,  45),
    "2": (255, 180,  40),
    "3": (255, 170,  35),
    "4": (255, 160,  30),
    "5": (255, 150,  25),
    "6": (255, 140,  20),
    "7": (255, 130,  15),
    "8": (255, 120,  10),
    "9": (255, 110,   5),
}

# ---------------------------------------------------------------------------
# Whitespace tokens  →  RGB
# ---------------------------------------------------------------------------
WHITESPACE = {
    " ":  (8, 8, 8),     # space — near black (distinct from pure black header)
    "\t": (16, 8, 8),    # tab
    "\n": (8, 16, 8),    # newline
    "\r": (8, 8, 16),    # carriage return
}

# ---------------------------------------------------------------------------
# Special / meta tokens
# ---------------------------------------------------------------------------
SPECIAL = {
    "__HEADER__": (0,   0,   0),   # reserved — header pixel
    "__PAD__":    (1,   1,   1),   # padding pixel to fill last row
}

# ---------------------------------------------------------------------------
# Core universal identifiers  →  RGB  (lime-gold family: high G, low B)
# self/cls/args/kwargs are the most common Python identifiers by far.
# ---------------------------------------------------------------------------
CORE_IDENTIFIERS = {
    "self":    (210, 255,   0),
    "cls":     (210, 245,   5),
    "args":    (210, 235,  10),
    "kwargs":  (210, 225,  15),
    "result":  (215, 255,   0),
    "value":   (215, 245,   5),
    "name":    (215, 235,  10),
    "data":    (215, 225,  15),
    "key":     (220, 255,   0),
    "obj":     (220, 245,   5),
    "func":    (220, 235,  10),
    "text":    (220, 225,  15),
    "node":    (225, 255,   0),
    "msg":     (225, 245,   5),
    "path":    (225, 235,  10),
    "url":     (225, 225,  15),
    "mode":    (230, 255,   0),
    "error":   (230, 245,   5),
    "index":   (230, 235,  10),
    "size":    (230, 225,  15),
    "count":   (235, 255,   0),
    "buf":     (235, 245,   5),
    "tmp":     (235, 235,  10),
    "flag":    (235, 225,  15),
}

# ---------------------------------------------------------------------------
# Dunder attributes / magic methods  →  RGB  (burnt-orange family)
# ---------------------------------------------------------------------------
DUNDERS = {
    "__init__":    (220,  90, 10),
    "__name__":    (220,  95, 15),
    "__main__":    (220, 100, 20),
    "__str__":     (220, 105, 25),
    "__repr__":    (220, 110, 30),
    "__len__":     (220, 115, 35),
    "__dict__":    (225,  90, 10),
    "__doc__":     (225,  95, 15),
    "__all__":     (225, 100, 20),
    "__file__":    (225, 105, 25),
    "__class__":   (225, 110, 30),
    "__module__":  (225, 115, 35),
    "__slots__":   (230,  90, 10),
    "__call__":    (230,  95, 15),
    "__new__":     (230, 100, 20),
    "__get__":     (230, 105, 25),
    "__set__":     (230, 110, 30),
    "__del__":     (230, 115, 35),
    "__bases__":   (235,  90, 10),
    "__mro__":     (235,  95, 15),
    "__iter__":    (235, 100, 20),
    "__next__":    (235, 105, 25),
    "__enter__":   (235, 110, 30),
    "__exit__":    (235, 115, 35),
}

# ---------------------------------------------------------------------------
# Common exception types  →  RGB  (crimson family: R=140–175, G+B near zero)
# ---------------------------------------------------------------------------
EXCEPTIONS = {
    "Exception":           (140,  0,  0),
    "ValueError":          (143,  3,  0),
    "TypeError":           (146,  6,  0),
    "KeyError":            (149,  9,  0),
    "IndexError":          (152, 12,  0),
    "AttributeError":      (155, 15,  0),
    "RuntimeError":        (158, 18,  0),
    "StopIteration":       (161,  0,  3),
    "IOError":             (164,  3,  3),
    "OSError":             (167,  6,  3),
    "ImportError":         (170,  9,  3),
    "NameError":           (173, 12,  3),
    "NotImplementedError": (140, 15,  3),
    "OverflowError":       (143, 18,  3),
    "ZeroDivisionError":   (146,  0,  6),
    "FileNotFoundError":   (149,  3,  6),
    "PermissionError":     (152,  6,  6),
    "TimeoutError":        (155,  9,  6),
    "ConnectionError":     (158, 12,  6),
    "RecursionError":      (161, 15,  6),
    "MemoryError":         (164, 18,  6),
    "SyntaxError":         (167,  0,  9),
    "UnicodeError":        (170,  3,  9),
    "ArithmeticError":     (173,  6,  9),
}

# ---------------------------------------------------------------------------
# Common built-in methods  →  RGB  (deep teal family: R=0–8, G=160–196, B=98–135)
# ---------------------------------------------------------------------------
COMMON_METHODS = {
    "append":     (0,  160,  98),
    "extend":     (0,  163, 101),
    "insert":     (0,  166, 104),
    "remove":     (0,  169, 107),
    "pop":        (0,  172, 110),
    "clear":      (0,  175, 113),
    "sort":       (0,  178, 116),
    "reverse":    (0,  181, 119),
    "get":        (0,  184, 122),
    "update":     (0,  187, 125),
    "keys":       (0,  190, 128),
    "values":     (0,  193, 131),
    "items":      (0,  196, 134),
    "join":       (4,  160,  98),
    "split":      (4,  163, 101),
    "strip":      (4,  166, 104),
    "replace":    (4,  169, 107),
    "startswith": (4,  172, 110),
    "endswith":   (4,  175, 113),
    "encode":     (4,  178, 116),
    "decode":     (4,  181, 119),
    "read":       (4,  184, 122),
    "write":      (4,  187, 125),
    "close":      (4,  190, 128),
    "seek":       (4,  193, 131),
    "flush":      (4,  196, 134),
    "copy":       (8,  160,  98),
    "lower":      (8,  163, 101),
    "upper":      (8,  166, 104),
    "format":     (8,  169, 107),
    "match":      (8,  172, 110),
    "search":     (8,  175, 113),
    "findall":    (8,  178, 116),
    "compile":    (8,  181, 119),  # re.compile specifically
}

# ---------------------------------------------------------------------------
# Common stdlib module names  →  RGB  (periwinkle family: R=78–110, G=98–138)
# ---------------------------------------------------------------------------
STDLIB_MODULES = {
    "os":          ( 78,  98, 198),
    "sys":         ( 81, 101, 201),
    "re":          ( 84, 104, 204),
    "io":          ( 87, 107, 207),
    "math":        ( 90, 110, 210),
    "json":        ( 93, 113, 213),
    "abc":         ( 96, 116, 216),
    "ast":         ( 99, 119, 219),
    "copy":        (102, 122, 222),
    "time":        (105, 125, 225),
    "functools":   ( 78, 128, 198),
    "itertools":   ( 81, 131, 201),
    "collections": ( 84, 134, 204),
    "pathlib":     ( 87, 137, 207),
    "typing":      ( 90, 138, 210),
    "logging":     ( 93, 128, 213),
    "threading":   ( 96, 131, 216),
    "subprocess":  ( 99, 134, 219),
    "datetime":    (102, 137, 222),
    "unittest":    (105, 138, 225),
}

# ---------------------------------------------------------------------------
# HTML tag names  →  RGB  (coral family: R=248, G=100–220, B=80)
# Covers the most common HTML5 element names.
# Single-char tags (a, p) omitted — 1-char tokens save nothing in .spec format.
# ---------------------------------------------------------------------------
HTML_TAGS = {
    "html":    (248, 100, 80),
    "head":    (248, 103, 80),
    "body":    (248, 106, 80),
    "div":     (248, 109, 80),
    "span":    (248, 112, 80),
    "ul":      (248, 115, 80),
    "ol":      (248, 118, 80),
    "li":      (248, 121, 80),
    "table":   (248, 124, 80),
    "tr":      (248, 127, 80),
    "td":      (248, 130, 80),
    "th":      (248, 133, 80),
    "form":    (248, 136, 80),
    "input":   (248, 139, 80),
    "button":  (248, 142, 80),
    "script":  (248, 145, 80),
    "style":   (248, 148, 80),
    "link":    (248, 151, 80),
    "meta":    (248, 154, 80),
    "title":   (248, 157, 80),
    "header":  (248, 160, 80),
    "footer":  (248, 163, 80),
    "nav":     (248, 166, 80),
    "section": (248, 169, 80),
    "article": (248, 172, 80),
    "main":    (248, 175, 80),
    "h1":      (248, 178, 80),
    "h2":      (248, 181, 80),
    "h3":      (248, 184, 80),
    "h4":      (248, 187, 80),
    "h5":      (248, 190, 80),
    "h6":      (248, 193, 80),
    "br":      (248, 196, 80),
    "hr":      (248, 199, 80),
    "strong":  (248, 202, 80),
    "em":      (248, 205, 80),
    "code":    (248, 208, 80),
    "pre":     (248, 211, 80),
    "img":     (248, 214, 80),
    "iframe":  (248, 217, 80),
    "canvas":  (248, 220, 80),
    "video":   (248, 223, 80),
    "audio":   (248, 226, 80),
}

# ---------------------------------------------------------------------------
# HTML attribute names  →  RGB  (light coral: R=246, G=100–176, B=140)
# Covers the most common HTML5 attribute names not already in the dictionary.
# ('class', 'type', 'name', 'value', 'id', 'style', 'method', 'action',
#  'target', 'width', 'height', 'required', 'title' already covered elsewhere)
# ---------------------------------------------------------------------------
HTML_ATTRS = {
    "href":         (246, 100, 140),
    "src":          (246, 104, 140),
    "alt":          (246, 108, 140),
    "placeholder":  (246, 112, 140),
    "rel":          (246, 116, 140),
    "disabled":     (246, 120, 140),
    "checked":      (246, 124, 140),
    "defer":        (246, 128, 140),
    "charset":      (246, 132, 140),
    "onclick":      (246, 136, 140),
    "onchange":     (246, 140, 140),
    "onsubmit":     (246, 144, 140),
    "onload":       (246, 148, 140),
    "tabindex":     (246, 152, 140),
    "download":     (246, 156, 140),
    "hidden":       (246, 160, 140),
    "multiple":     (246, 164, 140),
    "autocomplete": (246, 168, 140),
    "colspan":      (246, 172, 140),
    "rowspan":      (246, 176, 140),
}

# ---------------------------------------------------------------------------
# JavaScript keywords  →  RGB  (warm amber: R=252, G=50–130, B=50–70)
# JS-only keywords not already in the Python dictionary.
# ('import', 'from', 'as', 'class', 'extends' covered by Python keywords or
#  built-ins; 'super', 'async', 'await', 'yield', 'return', 'break',
#  'continue', 'for', 'while', 'if', 'else', 'try', 'delete' already there)
# ---------------------------------------------------------------------------
JS_KEYWORDS = {
    "var":        (252,  50, 50),
    "let":        (252,  56, 52),
    "const":      (252,  62, 54),
    "function":   (252,  68, 56),
    "this":       (252,  74, 58),
    "new":        (252,  80, 60),
    "typeof":     (252,  86, 62),
    "instanceof": (252,  92, 64),
    "switch":     (252,  98, 66),
    "case":       (252, 104, 68),
    "void":       (252, 110, 50),
    "debugger":   (252, 116, 52),
    "do":         (252, 122, 54),
    "of":         (252, 128, 56),
    "export":     (252, 134, 58),
    "null":       (252, 140, 60),
    "undefined":  (252, 146, 62),
    "NaN":        (252, 152, 64),
    "Infinity":   (252, 158, 66),
}

# ---------------------------------------------------------------------------
# JavaScript operators not in Python dictionary  →  RGB  (R=251)
# ---------------------------------------------------------------------------
JS_OPERATORS = {
    "===":  (251, 100, 50),
    "!==":  (251, 112, 52),
    "=>":   (251, 124, 54),
    "++":   (251, 136, 56),
    "--":   (251, 148, 58),
    "?.":   (251, 160, 60),
    "??":   (251, 172, 62),
}

# ---------------------------------------------------------------------------
# JavaScript built-in identifiers  →  RGB  (R=249, G=80–172, B=40)
# Covers the most frequently appearing JS global objects and common methods.
# ---------------------------------------------------------------------------
JS_IDENTIFIERS = {
    "console":           (249,  80, 40),
    "document":          (249,  84, 40),
    "window":            (249,  88, 40),
    "JSON":              (249,  92, 40),
    "Object":            (249,  96, 40),
    "Array":             (249, 100, 40),
    "Math":              (249, 104, 40),
    "Number":            (249, 108, 40),
    "String":            (249, 112, 40),
    "Boolean":           (249, 116, 40),
    "Promise":           (249, 120, 40),
    "fetch":             (249, 124, 40),
    "setTimeout":        (249, 128, 40),
    "setInterval":       (249, 132, 40),
    "clearTimeout":      (249, 136, 40),
    "clearInterval":     (249, 140, 40),
    "addEventListener":  (249, 144, 40),
    "querySelector":     (249, 148, 40),
    "getElementById":    (249, 152, 40),
    "callback":          (249, 156, 40),
    "resolve":           (249, 160, 40),
    "reject":            (249, 164, 40),
    "prototype":         (249, 168, 40),
    "module":            (249, 172, 40),
}

# ---------------------------------------------------------------------------
# CSS at-rule keywords  →  RGB  (indigo-violet family: R=247, B=200, G steps)
# At-rules are stored as full strings including the '@' prefix so the tokenizer
# can emit them as single tokens (e.g. "@media", "@keyframes").
# ---------------------------------------------------------------------------
CSS_AT_RULES = {
    "@media":      (247,  50, 200),
    "@import":     (247,  62, 200),
    "@keyframes":  (247,  74, 200),
    "@font-face":  (247,  86, 200),
    "@supports":   (247,  98, 200),
    "@charset":    (247, 110, 200),
    "@layer":      (247, 122, 200),
    "@container":  (247, 134, 200),
    "@page":       (247, 146, 200),
    "@namespace":  (247, 158, 200),
}

# ---------------------------------------------------------------------------
# CSS property names  →  RGB  (fresh lime family: R=112, B=60, G=200–239)
# Hyphenated properties stored as single tokens for maximum compression.
# ---------------------------------------------------------------------------
CSS_PROPERTIES = {
    # Layout & positioning
    "display":          (112, 200, 60),
    "position":         (112, 201, 60),
    "top":              (112, 202, 60),
    "right":            (112, 203, 60),
    "bottom":           (112, 204, 60),
    "left":             (112, 205, 60),
    "width":            (112, 206, 60),
    "height":           (112, 207, 60),
    "max-width":        (112, 208, 60),
    "min-width":        (112, 209, 60),
    "max-height":       (112, 210, 60),
    "min-height":       (112, 211, 60),
    "overflow":         (112, 212, 60),
    "z-index":          (112, 213, 60),
    # Box model
    "margin":           (112, 214, 60),
    "margin-top":       (112, 215, 60),
    "margin-right":     (112, 216, 60),
    "margin-bottom":    (112, 217, 60),
    "margin-left":      (112, 218, 60),
    "padding":          (112, 219, 60),
    "padding-top":      (112, 220, 60),
    "padding-right":    (112, 221, 60),
    "padding-bottom":   (112, 222, 60),
    "padding-left":     (112, 223, 60),
    "border":           (112, 224, 60),
    "border-radius":    (112, 225, 60),
    # Typography
    "color":            (112, 226, 60),
    "font-size":        (112, 227, 60),
    "font-weight":      (112, 228, 60),
    "font-family":      (112, 229, 60),
    "line-height":      (112, 230, 60),
    "text-align":       (112, 231, 60),
    "text-decoration":  (112, 232, 60),
    # Background
    "background":       (112, 233, 60),
    "background-color": (112, 234, 60),
    "background-image": (112, 235, 60),
    # Visuals & animation
    "opacity":          (112, 236, 60),
    "transform":        (112, 237, 60),
    "transition":       (112, 238, 60),
    "cursor":           (112, 239, 60),
}

# ---------------------------------------------------------------------------
# CSS value keywords  →  RGB  (dusty mauve family: R=195, B=150, G=100–138)
# Common keyword values that appear in CSS declarations.
# ---------------------------------------------------------------------------
CSS_VALUE_KEYWORDS = {
    "none":         (195, 100, 150),
    "auto":         (195, 102, 150),
    "block":        (195, 104, 150),
    "inline":       (195, 106, 150),
    "inline-block": (195, 108, 150),
    "flex":         (195, 110, 150),
    "grid":         (195, 112, 150),
    "absolute":     (195, 114, 150),
    "relative":     (195, 116, 150),
    "fixed":        (195, 118, 150),
    "sticky":       (195, 120, 150),
    "bold":         (195, 122, 150),
    "normal":       (195, 124, 150),
    "inherit":      (195, 126, 150),
    "initial":      (195, 128, 150),
    "unset":        (195, 130, 150),
    "center":       (195, 132, 150),
    "visible":      (195, 134, 150),
    "pointer":      (195, 136, 150),
    "solid":        (195, 138, 150),
}

# ---------------------------------------------------------------------------
# TypeScript keywords  →  RGB  (steel-blue family: R=244, B=90, G steps by 8)
# Only tokens NOT already in the dictionary (Python/JS/CSS/HTML cover many).
# 'enum' is listed here and shared with Rust (it only needs one colour entry).
# Placed AFTER ENGLISH_WORDS in TOKEN_TO_RGB so programming use takes priority
# over any English-word entry with the same spelling.
# ---------------------------------------------------------------------------
TS_KEYWORDS = {
    "interface":  (244,  50, 90),
    "enum":       (244,  58, 90),   # shared with Rust — defined here once
    "namespace":  (244,  66, 90),
    "declare":    (244,  74, 90),
    "readonly":   (244,  82, 90),
    "abstract":   (244,  90, 90),
    "implements": (244,  98, 90),
    "keyof":      (244, 106, 90),
    "infer":      (244, 114, 90),
    "never":      (244, 122, 90),
    "unknown":    (244, 130, 90),
    "override":   (244, 138, 90),
    "satisfies":  (244, 146, 90),
    "asserts":    (244, 154, 90),
    "accessor":   (244, 162, 90),
    "using":      (244, 170, 90),
}

# ---------------------------------------------------------------------------
# SQL DML / DDL keywords  →  RGB  (deep-plum family: R=241, B=110, G steps by 4)
# Stored as UPPERCASE — SQL tokenizer emits uppercase for keyword tokens so
# that dict hits are maximised regardless of how the source was written.
# ---------------------------------------------------------------------------
SQL_KEYWORDS = {
    # Core query
    "SELECT":      (241,  50, 110),
    "FROM":        (241,  54, 110),
    "WHERE":       (241,  58, 110),
    "JOIN":        (241,  62, 110),
    "LEFT":        (241,  66, 110),
    "RIGHT":       (241,  70, 110),
    "INNER":       (241,  74, 110),
    "OUTER":       (241,  78, 110),
    "CROSS":       (241,  82, 110),
    "ON":          (241,  86, 110),
    "GROUP":       (241,  90, 110),
    "ORDER":       (241,  94, 110),
    "BY":          (241,  98, 110),
    "HAVING":      (241, 102, 110),
    # DML
    "INSERT":      (241, 106, 110),
    "INTO":        (241, 110, 110),
    "VALUES":      (241, 114, 110),
    "UPDATE":      (241, 118, 110),
    "SET":         (241, 122, 110),
    "DELETE":      (241, 126, 110),
    # DDL
    "CREATE":      (241, 130, 110),
    "TABLE":       (241, 134, 110),
    "DROP":        (241, 138, 110),
    "ALTER":       (241, 142, 110),
    "ADD":         (241, 146, 110),
    "COLUMN":      (241, 150, 110),
    "INDEX":       (241, 154, 110),
    "PRIMARY":     (241, 158, 110),
    "KEY":         (241, 162, 110),
    "FOREIGN":     (241, 166, 110),
    "REFERENCES":  (241, 170, 110),
    "UNIQUE":      (241, 174, 110),
    # Logical / filter
    "NOT":         (241, 178, 110),
    "NULL":        (241, 182, 110),
    "AND":         (241, 186, 110),
    "OR":          (241, 190, 110),
    "AS":          (241, 194, 110),
    "DISTINCT":    (241, 198, 110),
    "LIMIT":       (241, 202, 110),
    "OFFSET":      (241, 206, 110),
    "UNION":       (241, 210, 110),
    "ALL":         (241, 214, 110),
    "EXISTS":      (241, 218, 110),
    "IN":          (241, 222, 110),
    "LIKE":        (241, 226, 110),
    "BETWEEN":     (241, 230, 110),
    "IS":          (241, 234, 110),
    # CASE expression
    "CASE":        (241, 238, 110),
    "WHEN":        (241, 242, 110),
    "THEN":        (241, 246, 110),
    "ELSE":        (241, 250, 110),
    "END":         (241, 254, 110),
    # Extended DDL / TCL
    "WITH":        (241,  50, 114),
    "RETURNING":   (241,  54, 114),
    "DEFAULT":     (241,  58, 114),
    "CONSTRAINT":  (241,  62, 114),
    "TRUNCATE":    (241,  66, 114),
    "DATABASE":    (241,  70, 114),
    "SCHEMA":      (241,  74, 114),
    "VIEW":        (241,  78, 114),
    "TRIGGER":     (241,  82, 114),
    "PROCEDURE":   (241,  86, 114),
    "EXEC":        (241,  90, 114),
    "BEGIN":       (241,  94, 114),
    "COMMIT":      (241,  98, 114),
    "ROLLBACK":    (241, 102, 114),
    "TRANSACTION": (241, 106, 114),
    "GRANT":       (241, 110, 114),
    "REVOKE":      (241, 114, 114),
}

# ---------------------------------------------------------------------------
# SQL aggregate / scalar functions  →  RGB  (lighter-plum: R=242, B=110)
# ---------------------------------------------------------------------------
SQL_FUNCTIONS = {
    "COUNT":       (242,  50, 110),
    "SUM":         (242,  54, 110),
    "AVG":         (242,  58, 110),
    "MAX":         (242,  62, 110),
    "MIN":         (242,  66, 110),
    "COALESCE":    (242,  70, 110),
    "NULLIF":      (242,  74, 110),
    "IFNULL":      (242,  78, 110),
    "ISNULL":      (242,  82, 110),
    "CAST":        (242,  86, 110),
    "CONVERT":     (242,  90, 110),
    "CONCAT":      (242,  94, 110),
    "NOW":         (242,  98, 110),
    "CURDATE":     (242, 102, 110),
    "DATE":        (242, 106, 110),
    "YEAR":        (242, 110, 110),
    "MONTH":       (242, 114, 110),
    "DAY":         (242, 118, 110),
    "HOUR":        (242, 122, 110),
    "MINUTE":      (242, 126, 110),
    "SECOND":      (242, 130, 110),
    "FLOOR":       (242, 134, 110),
    "CEILING":     (242, 138, 110),
    "CEIL":        (242, 142, 110),
    "ROUND":       (242, 146, 110),
    "ABS":         (242, 150, 110),
    "LENGTH":      (242, 154, 110),
    "UPPER":       (242, 158, 110),
    "LOWER":       (242, 162, 110),
    "TRIM":        (242, 166, 110),
    "SUBSTRING":   (242, 170, 110),
    "SUBSTR":      (242, 174, 110),
    "REPLACE":     (242, 178, 110),
    "ROW_NUMBER":  (242, 182, 110),
    "RANK":        (242, 186, 110),
    "DENSE_RANK":  (242, 190, 110),
    "LAG":         (242, 194, 110),
    "LEAD":        (242, 198, 110),
    "EXTRACT":     (242, 202, 110),
    "DATEDIFF":    (242, 206, 110),
    "DATEADD":     (242, 210, 110),
    "NVL":         (242, 214, 110),
    "IIF":         (242, 218, 110),
}

# ---------------------------------------------------------------------------
# PHP keywords  →  RGB  (warm-sand family: R=245, B=80, G steps by 8)
# Covers PHP-specific keywords not already in the dictionary.
# Many PHP keywords are shared with Python/JS (class, function, if, else,
# while, for, switch, case, break, continue, return, abstract, interface,
# use, new, null, true, false, static, final, namespace, trait, fn, match)
# and are already handled by those language's existing colour entries.
# Placed AFTER ENGLISH_WORDS so PHP keywords win over same-spelling English words.
# ---------------------------------------------------------------------------
PHP_KEYWORDS = {
    # PHP-specific control flow
    "echo":         (245,  50, 80),
    "elseif":       (245,  58, 80),
    "foreach":      (245,  66, 80),
    "endif":        (245,  74, 80),
    "endfor":       (245,  82, 80),
    "endforeach":   (245,  90, 80),
    "endwhile":     (245,  98, 80),
    "endswitch":    (245, 106, 80),
    # PHP include / require
    "require":      (245, 114, 80),
    "include":      (245, 122, 80),
    "require_once": (245, 130, 80),
    "include_once": (245, 138, 80),
    # PHP type system (PHP 8+)
    "iterable":     (245, 146, 80),
    "mixed":        (245, 154, 80),
    "array":        (245, 162, 80),
    "parent":       (245, 170, 80),
    # PHP language constructs
    "isset":        (245, 178, 80),
    "unset":        (245, 186, 80),
    "empty":        (245, 194, 80),
    "list":         (245, 202, 80),
    # PHP 8 nullsafe operator (2-char token)
    "?->":          (245, 210, 80),
    # PHP debugging constructs
    "print_r":      (245, 218, 80),
    "var_dump":     (245, 226, 80),
    "var_export":   (245, 234, 80),
}

# ---------------------------------------------------------------------------
# PHP built-in functions  →  RGB  (warm-sand/light family: R=245, B=100)
# Common PHP functions not already in the dictionary.
# ---------------------------------------------------------------------------
PHP_FUNCTIONS = {
    # String functions
    "strlen":            (245,  50, 100),
    "strpos":            (245,  58, 100),
    "strrpos":           (245,  66, 100),
    "substr":            (245,  74, 100),
    "str_replace":       (245,  82, 100),
    "str_contains":      (245,  90, 100),
    "str_starts_with":   (245,  98, 100),
    "str_ends_with":     (245, 106, 100),
    "implode":           (245, 114, 100),
    "explode":           (245, 122, 100),
    "str_split":         (245, 130, 100),
    "sprintf":           (245, 138, 100),
    "htmlspecialchars":  (245, 146, 100),
    "htmlentities":      (245, 154, 100),
    "nl2br":             (245, 162, 100),
    "preg_match":        (245, 170, 100),
    "preg_replace":      (245, 178, 100),
    "preg_split":        (245, 186, 100),
    # Array functions
    "in_array":          (245, 194, 100),
    "array_map":         (245, 202, 100),
    "array_filter":      (245, 210, 100),
    "array_keys":        (245, 218, 100),
    "array_values":      (245, 226, 100),
    "array_push":        (245, 234, 100),
    "array_pop":         (245, 242, 100),
    "array_merge":       (245,  50, 104),
    "array_slice":       (245,  58, 104),
    "array_splice":      (245,  66, 104),
    "array_unique":      (245,  74, 104),
    "array_search":      (245,  82, 104),
    "array_reverse":     (245,  90, 104),
    "array_shift":       (245,  98, 104),
    "array_unshift":     (245, 106, 104),
    "array_combine":     (245, 114, 104),
    "array_flip":        (245, 122, 104),
    "array_chunk":       (245, 130, 104),
    # JSON
    "json_encode":       (245, 138, 104),
    "json_decode":       (245, 146, 104),
    # Date / time
    "date":              (245, 154, 104),
    "time":              (245, 162, 104),
    "mktime":            (245, 170, 104),
    "strtotime":         (245, 178, 104),
    # Math
    "intval":            (245, 186, 104),
    "floatval":          (245, 194, 104),
    "strval":            (245, 202, 104),
    "boolval":           (245, 210, 104),
    "number_format":     (245, 218, 104),
    # File / path
    "file_get_contents": (245, 226, 104),
    "file_put_contents": (245, 234, 104),
    "file_exists":       (245, 242, 104),
    "basename":          (245,  50, 108),
    "dirname":           (245,  58, 108),
    "pathinfo":          (245,  66, 108),
}

# ---------------------------------------------------------------------------
# Rust keywords  →  RGB  (forest-sage family: R=243, B=70, G steps by 8)
# 'enum' is intentionally omitted here — it's defined in TS_KEYWORDS and
# the two languages share the colour (244, 58, 90).
# '::' is the Rust path-separator operator, stored as a 2-char token.
# Placed AFTER ENGLISH_WORDS in TOKEN_TO_RGB so Rust keywords win over any
# same-spelling English word (e.g. 'pub', 'trait', 'crate', 'where').
# ---------------------------------------------------------------------------
RUST_KEYWORDS = {
    "fn":       (243,  50, 70),
    "mut":      (243,  58, 70),
    "impl":     (243,  66, 70),
    "trait":    (243,  74, 70),
    "struct":   (243,  82, 70),
    "mod":      (243,  90, 70),
    "pub":      (243,  98, 70),
    "crate":    (243, 106, 70),
    "extern":   (243, 114, 70),
    "unsafe":   (243, 122, 70),
    "move":     (243, 130, 70),
    "ref":      (243, 138, 70),
    "dyn":      (243, 146, 70),
    "loop":     (243, 154, 70),
    "Self":     (243, 162, 70),
    "use":      (243, 170, 70),
    "where":    (243, 178, 70),
    "::":       (243, 186, 70),   # path separator  e.g. std::vec::Vec
    "box":      (243, 194, 70),
    "become":   (243, 202, 70),   # reserved future keyword
}

# ---------------------------------------------------------------------------
# English text — control tokens  →  RGB  (near-black, R=1, G=0, B=1–5)
# These are emitted by the text tokenizer to control capitalisation and
# word-spelling.  They are interpreted by the text decoder as state changes,
# never concatenated directly to the output string.
#
#   CTRL:CAP_FIRST   — capitalise the first letter of the next word token
#   CTRL:CAP_ALL     — capitalise the entire next word token (ALL CAPS)
#   CTRL:BEGIN_WORD  — start of a letter-by-letter word (unknown to dictionary)
#   CTRL:END_WORD    — end of a letter-by-letter word
#   CTRL:NUM_SEP     — explicit spacer between two adjacent number groups
# ---------------------------------------------------------------------------
ENGLISH_CONTROL = {
    "CTRL:CAP_FIRST":  (1, 0, 1),
    "CTRL:CAP_ALL":    (1, 0, 2),
    "CTRL:BEGIN_WORD": (1, 0, 3),
    "CTRL:END_WORD":   (1, 0, 4),
    "CTRL:NUM_SEP":    (1, 0, 5),
}

# ---------------------------------------------------------------------------
# English text — additional punctuation  →  RGB
# '!' and '?' are not covered by the code-oriented SYMBOLS dict.
# All other English punctuation (, . ; : ' " - ( ) ...) is already in SYMBOLS.
# ---------------------------------------------------------------------------
TEXT_PUNCTUATION = {
    "!": (1, 1, 0),
    "?": (1, 2, 0),
}

# ---------------------------------------------------------------------------
# English words — imported from auto-generated english_tokens.py
# Run generate_english_dict.py to regenerate after wordlist changes.
# ---------------------------------------------------------------------------
try:
    from english_tokens import ENGLISH_WORDS
except ImportError:
    ENGLISH_WORDS: dict[str, tuple[int, int, int]] = {}

# ---------------------------------------------------------------------------
# Run-Length Encoding (RLE) support
# R=253 is reserved as the RLE marker channel value.
# An RLE pixel encodes how many ADDITIONAL times to repeat the previous token.
# ---------------------------------------------------------------------------
RLE_MARKER_R = 253  # reserved R value — never used by any real token colour


def make_rle_pixel(count: int) -> tuple[int, int, int]:
    """
    Create an RLE marker pixel encoding `count` additional repetitions.
    count must be in range 1–65535.
    e.g. make_rle_pixel(99) means "repeat the previous token 99 more times"
    """
    count = min(max(count, 1), 65535)
    return (RLE_MARKER_R, (count >> 8) & 0xFF, count & 0xFF)


def is_rle_pixel(rgb: tuple[int, int, int]) -> bool:
    """Return True if this pixel is an RLE marker (not a real token)."""
    return rgb[0] == RLE_MARKER_R


def rle_pixel_count(rgb: tuple[int, int, int]) -> int:
    """Decode the additional-repeat count from an RLE marker pixel."""
    _, g, b = rgb
    return (g << 8) | b


# ---------------------------------------------------------------------------
# Master lookup: token (str) → RGB tuple
# ---------------------------------------------------------------------------
TOKEN_TO_RGB: dict[str, tuple[int, int, int]] = {
    **KEYWORDS,
    **SYMBOLS,
    **DIGITS,
    **WHITESPACE,
    **BUILTINS_FUNCS,
    **BUILTINS_TYPES,
    **CORE_IDENTIFIERS,
    **DUNDERS,
    **EXCEPTIONS,
    **COMMON_METHODS,
    **STDLIB_MODULES,
    **HTML_TAGS,
    **HTML_ATTRS,
    **JS_KEYWORDS,
    **JS_OPERATORS,
    **JS_IDENTIFIERS,
    **CSS_AT_RULES,
    **CSS_PROPERTIES,
    **CSS_VALUE_KEYWORDS,
    **SPECIAL,
    # v7 additions — English plain-text support
    **ENGLISH_CONTROL,
    **TEXT_PUNCTUATION,
    **ENGLISH_WORDS,
    # v8 additions — new language support (placed AFTER ENGLISH_WORDS so that
    # programming-language keywords take precedence over same-spelling English
    # words for encoding and RAG discrimination purposes)
    **TS_KEYWORDS,
    **SQL_KEYWORDS,
    **SQL_FUNCTIONS,
    **RUST_KEYWORDS,
    # v9 additions
    **PHP_KEYWORDS,
    **PHP_FUNCTIONS,
}

# ---------------------------------------------------------------------------
# Reverse lookup: RGB tuple → token (str)
# Built at import time from TOKEN_TO_RGB.
# ---------------------------------------------------------------------------
RGB_TO_TOKEN: dict[tuple[int, int, int], str] = {
    v: k for k, v in TOKEN_TO_RGB.items()
}

# ---------------------------------------------------------------------------
# Fallback encoding for characters NOT in the dictionary.
# Encodes a single character using its Unicode code point split across RGB.
# Supports code points 0–16,777,215 (covers all of Unicode plane 0–15).
#
# Encoding:  (R, G, B) = ((cp >> 16) & 0xFF, (cp >> 8) & 0xFF, cp & 0xFF)
# The range (0,0,0)–(0,0,127) is reserved for ASCII fallback chars 0–127.
# We shift single-byte ASCII into a clearly distinct band to avoid collisions
# with WHITESPACE and SPECIAL tokens.
# ---------------------------------------------------------------------------

FALLBACK_MARKER = 0  # R channel value that signals "this is a fallback pixel"

def char_to_fallback_rgb(char: str) -> tuple[int, int, int]:
    """Encode a single character as a fallback RGB pixel."""
    cp = ord(char)
    r = (cp >> 16) & 0xFF
    g = (cp >> 8)  & 0xFF
    b =  cp        & 0xFF
    return (r, g, b)


def fallback_rgb_to_char(rgb: tuple[int, int, int]) -> str:
    """Decode a fallback RGB pixel back to a character."""
    r, g, b = rgb
    cp = (r << 16) | (g << 8) | b
    return chr(cp)


def is_fallback_rgb(rgb: tuple[int, int, int]) -> bool:
    """
    Heuristic: an RGB value is treated as a fallback-encoded character
    if it doesn't appear in RGB_TO_TOKEN.
    The encoder marks fallback pixels explicitly in the pixel stream,
    so the decoder doesn't need to guess — but this helper is useful
    for debugging and validation.
    """
    return rgb not in RGB_TO_TOKEN


# ---------------------------------------------------------------------------
# Convenience helpers
# ---------------------------------------------------------------------------

def token_to_rgb(token: str) -> tuple[int, int, int]:
    """Return the RGB colour for a known token, or raise KeyError."""
    return TOKEN_TO_RGB[token]


def rgb_to_token(rgb: tuple[int, int, int]) -> str | None:
    """Return the token for a known RGB colour, or None if not in dictionary."""
    return RGB_TO_TOKEN.get(rgb)


def all_tokens() -> list[str]:
    """Return all tokens in the dictionary (excluding meta tokens)."""
    return [k for k in TOKEN_TO_RGB if not k.startswith("__")]


# ---------------------------------------------------------------------------
# Stable token ↔ ID mappings for the .spec binary format
#
# IDs are assigned in TOKEN_TO_RGB insertion order (deterministic in Python
# 3.7+). The two meta-tokens (__HEADER__, __PAD__) are excluded.
#
# Reserved IDs (above the dictionary range):
#   SPEC_ID_ASCII_BASE  = len(SPEC_TOKENS)          — ASCII fallback chars 0–127
#   SPEC_ID_RLE         = 0xFFFD (65533)             — RLE marker
#   SPEC_ID_UNICODE     = 0xFFFE (65534)             — Unicode fallback (>127)
#   0xFFFF              = reserved / unused
# ---------------------------------------------------------------------------
SPEC_TOKENS: list[str] = [tok for tok in TOKEN_TO_RGB if not tok.startswith("__")]
TOKEN_TO_SPEC_ID: dict[str, int] = {tok: i for i, tok in enumerate(SPEC_TOKENS)}
SPEC_ID_TO_TOKEN: dict[int, str] = {i: tok for i, tok in enumerate(SPEC_TOKENS)}

SPEC_ID_ASCII_BASE: int = len(SPEC_TOKENS)        # ASCII chars start here
SPEC_ID_RLE:        int = 0xFFFFFFFD             # followed by uint32 repeat count
SPEC_ID_UNICODE:    int = 0xFFFFFFFE             # followed by uint32 code point
# NOTE: v7 body format uses uint32 LE tokens (upgraded from uint16 in v6)
# to accommodate the 234K+ English word dictionary. v6 .spec files should
# be re-encoded with v7 if English text support is needed.


if __name__ == "__main__":
    print(f"Spectrum Algo Dictionary v{DICT_VERSION}")
    print(f"Total tokens: {len(TOKEN_TO_RGB):,}")
    print(f"  Keywords:          {len(KEYWORDS)}")
    print(f"  Symbols:           {len(SYMBOLS)}")
    print(f"  Digits:            {len(DIGITS)}")
    print(f"  Whitespace:        {len(WHITESPACE)}")
    print(f"  Built-in funcs:    {len(BUILTINS_FUNCS)}")
    print(f"  Built-in types:    {len(BUILTINS_TYPES)}")
    print(f"  Core identifiers:  {len(CORE_IDENTIFIERS)}")
    print(f"  Dunders:           {len(DUNDERS)}")
    print(f"  Exceptions:        {len(EXCEPTIONS)}")
    print(f"  Common methods:    {len(COMMON_METHODS)}")
    print(f"  Stdlib modules:    {len(STDLIB_MODULES)}")
    print(f"  HTML tags:         {len(HTML_TAGS)}")
    print(f"  HTML attributes:   {len(HTML_ATTRS)}")
    print(f"  JS keywords:       {len(JS_KEYWORDS)}")
    print(f"  JS operators:      {len(JS_OPERATORS)}")
    print(f"  JS identifiers:    {len(JS_IDENTIFIERS)}")
    print(f"  CSS at-rules:      {len(CSS_AT_RULES)}")
    print(f"  CSS properties:    {len(CSS_PROPERTIES)}")
    print(f"  CSS values:        {len(CSS_VALUE_KEYWORDS)}")
    print(f"  Special:           {len(SPECIAL)}")
    print(f"  English control:   {len(ENGLISH_CONTROL)}")
    print(f"  Text punctuation:  {len(TEXT_PUNCTUATION)}")
    print(f"  English words:     {len(ENGLISH_WORDS):,}")
    print(f"  --- v8 ---")
    print(f"  TS keywords:       {len(TS_KEYWORDS)}")
    print(f"  SQL keywords:      {len(SQL_KEYWORDS)}")
    print(f"  SQL functions:     {len(SQL_FUNCTIONS)}")
    print(f"  Rust keywords:     {len(RUST_KEYWORDS)}")
    print(f"  --- v9 ---")
    print(f"  PHP keywords:      {len(PHP_KEYWORDS)}")
    print(f"  PHP functions:     {len(PHP_FUNCTIONS)}")
    print(f"\n  RGB space used:    {len(TOKEN_TO_RGB):,} / 16,777,216 "
          f"({100*len(TOKEN_TO_RGB)/16_777_216:.2f}%)")
    print()
    # Sanity check: no duplicate RGB values
    all_rgb = list(TOKEN_TO_RGB.values())
    unique_rgb = set(all_rgb)
    if len(all_rgb) != len(unique_rgb):
        dupes = [rgb for rgb in unique_rgb if all_rgb.count(rgb) > 1]
        print(f"WARNING: {len(all_rgb) - len(unique_rgb)} duplicate RGB value(s) found!")
        for d in dupes:
            tokens = [t for t, c in TOKEN_TO_RGB.items() if c == d]
            print(f"  {d} → {tokens}")
    else:
        print("✓ All RGB values are unique — no collisions.")
