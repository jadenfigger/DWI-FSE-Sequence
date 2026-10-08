"""Recursive-descent parser for the PPL subset used by the v18/v19 sources.

Unsupported syntax raises ``ParseError`` rather than being skipped.  The AST is
made of small tuples so the interpreter stays simple:

statements: ('decl', type, common, [(name, size_expr|None, init)]),
            ('expr', e), ('if', c, s1, s2|None), ('block', [stmts]),
            ('do', body, cond), ('for', count, body), ('goto', label),
            ('label', name), ('return', e|None), ('nop',)
expressions: ('num', value, is_long), ('str', s), ('var', name),
             ('index', name, e), ('member', name, [fields]), ('input', n),
             ('call', name, [args]), ('un', op, e), ('bin', op, a, b),
             ('assign', target, e)
"""
from __future__ import annotations

from .preprocess import Tok


class ParseError(Exception):
    pass


TYPES = {"int", "long", "void", "unsigned", "char", "short"}
BINOPS = [
    ["||"], ["&&"], ["|"], ["^"], ["&"], ["==", "!="], ["<", ">", "<=", ">="],
    ["<<", ">>"], ["+", "-"], ["*", "/", "%"],
]


class Parser:
    def __init__(self, toks: list[Tok]):
        self.t = toks
        self.i = 0

    # helpers --------------------------------------------------------------
    def peek(self, k=0):
        j = self.i + k
        return self.t[j] if j < len(self.t) else Tok("eof", "<eof>", "", 0)

    def next(self):
        tok = self.peek()
        self.i += 1
        return tok

    def accept(self, v):
        if self.peek().value == v:
            self.i += 1
            return True
        return False

    def expect(self, v):
        tok = self.next()
        if tok.value != v:
            raise ParseError(f"expected {v!r} at {tok!r}")
        return tok

    def where(self):
        tok = self.peek()
        return (tok.file, tok.line)

    # program -----------------------------------------------------------------
    def program(self):
        globals_, funcs = [], {}
        while self.peek().kind != "eof":
            if self.peek().value == "main" and self.peek(1).value == "(":
                self.next(); self.expect("("); self.expect(")")
                funcs["main"] = ([], self.block())
                continue
            common = self.accept("common")
            if self.peek().value not in TYPES:
                raise ParseError(f"unexpected top-level token {self.peek()!r}")
            typ = self.type_name()
            name_tok = self.next()
            if self.peek().value == "(":
                params = self.param_list()
                if self.peek().value == "{":
                    funcs[name_tok.value] = (params, self.block())
                else:
                    self.expect(";")
                continue
            self.i -= 1
            globals_.append(self.declaration_rest(typ, common))
        return globals_, funcs

    def type_name(self):
        parts = []
        while self.peek().value in TYPES:
            parts.append(self.next().value)
        if not parts:
            raise ParseError(f"type expected at {self.peek()!r}")
        if "long" in parts:
            return "long"
        if "void" in parts:
            return "void"
        return "int"

    def param_list(self):
        self.expect("(")
        params = []
        while not self.accept(")"):
            if self.peek().value in TYPES:
                typ = self.type_name()
            else:
                typ = "int"
            name = None
            if self.peek().kind == "id":
                name = self.next().value
            params.append((typ, name))
            self.accept(",")
        return params

    def declaration_rest(self, typ, common):
        where = self.where()
        items = []
        while True:
            name = self.next()
            if name.kind != "id":
                raise ParseError(f"declarator expected at {name!r}")
            if self.peek().value == "(":
                # local prototype like `int pr(int offset, int page);`
                self.param_list()
                if not self.accept(","):
                    self.expect(";")
                    return ("nop",)
                continue
            size = None
            if self.accept("["):
                size = self.expr()
                self.expect("]")
            init = None
            if self.accept("="):
                if self.accept("{"):
                    vals = []
                    while not self.accept("}"):
                        vals.append(self.expr())
                        self.accept(",")
                    init = ("list", vals)
                else:
                    init = self.expr()
            items.append((name.value, size, init))
            if self.accept(";"):
                break
            self.expect(",")
        return ("decl", typ, common, items, where)

    def block(self):
        self.expect("{")
        stmts = []
        while not self.accept("}"):
            stmts.append(self.statement())
        return ("block", stmts)

    def statement(self):
        tok = self.peek()
        where = self.where()
        v = tok.value
        if v == "{":
            return self.block()
        if v == ";":
            self.next()
            return ("nop",)
        if v == "common" or (v in TYPES and tok.kind == "id"):
            common = self.accept("common")
            typ = self.type_name()
            return self.declaration_rest(typ, common)
        if v == "if":
            self.next(); self.expect("(")
            c = self.expr(); self.expect(")")
            s1 = self.statement()
            s2 = None
            if self.accept("else"):
                s2 = self.statement()
            return ("if", c, s1, s2, where)
        if v == "do":
            self.next()
            body = self.statement()
            self.expect("until")
            c = self.expr()
            self.expect(";")
            return ("do", body, c, where)
        if v == "for":
            self.next(); self.expect("(")
            c = self.expr(); self.expect(")")
            body = self.statement()
            return ("for", c, body, where)
        if v == "goto":
            self.next()
            lab = self.next().value
            self.expect(";")
            return ("goto", lab, where)
        if v == "return":
            self.next()
            e = None if self.peek().value == ";" else self.expr()
            self.expect(";")
            return ("return", e, where)
        if v == "noop":
            self.next(); self.expect(";")
            return ("expr", ("call", "__noop", []), where)
        if tok.kind == "id" and self.peek(1).value == ":":
            self.next(); self.next()
            return ("label", v, where)
        e = self.expr()
        self.expect(";")
        return ("expr", e, where)

    # expressions ----------------------------------------------------------
    def expr(self):
        left = self.binary(0)
        if self.peek().value == "=":
            self.next()
            right = self.expr()
            if left[0] not in ("var", "index"):
                raise ParseError(f"bad assignment target near {self.peek()!r}")
            return ("assign", left, right)
        return left

    def binary(self, level):
        if level == len(BINOPS):
            return self.unary()
        left = self.binary(level + 1)
        while self.peek().value in BINOPS[level] and self.peek().kind == "op":
            op = self.next().value
            right = self.binary(level + 1)
            left = ("bin", op, left, right)
        return left

    def unary(self):
        v = self.peek().value
        if self.peek().kind == "op" and v in ("-", "!", "~", "+"):
            self.next()
            return ("un", v, self.unary())
        return self.postfix()

    def postfix(self):
        tok = self.next()
        if tok.kind == "num":
            s = tok.value
            is_long = s[-1] in "lL"
            s2 = s.rstrip("lLuU")
            if s2.lower().startswith("0x"):
                val = int(s2, 16)
            elif "." in s2 or "e" in s2.lower():
                raise ParseError(f"floating literal not supported: {tok!r}")
            else:
                val = int(s2)
            if not is_long and not -32768 <= val <= 32767 and not s2.lower().startswith("0x"):
                is_long = True  # C: unsuffixed decimal that does not fit int is long
            return ("num", val, is_long)
        if tok.kind == "str":
            return ("str", bytes(tok.value[1:-1], "latin-1").decode("unicode_escape"))
        if tok.value == "(":
            e = self.expr()
            self.expect(")")
            return e
        if tok.kind != "id":
            raise ParseError(f"unexpected token {tok!r}")
        name = tok.value
        if name == "input" and self.peek().value == "#":
            self.next()
            n = self.next()
            return ("input", int(n.value))
        if self.peek().value == "(":
            self.next()
            args = []
            while not self.accept(")"):
                args.append(self.expr())
                self.accept(",")
            return ("call", name, args)
        if self.peek().value == "[":
            self.next()
            idx = self.expr()
            self.expect("]")
            return ("index", name, idx)
        if self.peek().value == ".":
            fields = []
            while self.accept("."):
                f = self.next()
                fields.append(f.value[1:-1] if f.kind == "str" else f.value)
            return ("member", name, fields)
        return ("var", name)
