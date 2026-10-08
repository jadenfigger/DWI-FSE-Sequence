"""Minimal PPL preprocessor for source-to-event mapping.

This is not the vendor ``cpp.exe``. It implements only the constructs used by the
supplied v18/v19 sources and MR Solutions includes, and it fails loudly on any
other directive. Identifiers are case-insensitive in PPL (the supplied vendor
code mixes ``MR3040_clock``/``MR3040_Clock`` and ``fov_PHASE_off``/
``fov_phase_off``), so identifier tokens are lower-cased after expansion.
Macro names remain case-sensitive (``DELAY`` macro versus ``delay`` builtin).

Behavioural choices that cannot be verified without the vendor compiler are
explicit:

* ``\\\\`` starts a line comment (PPL extension), as do ``//`` and ``/* */``.
* ``a ## b`` joins the two token sequences without creating a new identifier
  token; the right side is then rescanned.  This reproduces the only use in the
  supplied includes (``read_off##POS_INDEX`` -> ``fov_read_off [pos_index]``).
* ``PPLC`` is predefined, which selects the ``ss/ms/us`` constants in
  ``stdfn_15.pph``.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


class PreprocessError(Exception):
    pass


@dataclass
class Tok:
    kind: str          # id, num, str, op
    value: str
    file: str
    line: int

    def __repr__(self):
        return f"{self.value}@{Path(self.file).name}:{self.line}"


_TOKEN_RE = re.compile(
    r"""
    (?P<ws>[ \t\r\f\v]+)
  | (?P<num>0[xX][0-9a-fA-F]+[lL]?|\d+\.\d*(?:[eE][-+]?\d+)?|\d+[eE][-+]?\d+|\d+[lLuU]*)
  | (?P<id>[A-Za-z_][A-Za-z0-9_]*)
  | (?P<str>"(?:[^"\\\n]|\\.)*")
  | (?P<op>\#\#|<<|>>|<=|>=|==|!=|&&|\|\||\+\+|--|[-+*/%<>=!&|^~(){}\[\];,.:\#?])
    """,
    re.VERBOSE,
)


def _strip_comments(text: str) -> str:
    """Remove /* */, // and \\\\ comments outside string literals, keeping newlines."""
    out = []
    i = 0
    n = len(text)
    in_str = False
    while i < n:
        c = text[i]
        if in_str:
            out.append(c)
            if c == "\\" and i + 1 < n and text[i + 1] != "\n":
                out.append(text[i + 1])
                i += 2
                continue
            if c == '"' or c == "\n":
                in_str = False
            i += 1
            continue
        if c == '"':
            in_str = True
            out.append(c)
            i += 1
            continue
        if text.startswith("/*", i):
            j = text.find("*/", i + 2)
            if j < 0:
                raise PreprocessError("Unterminated block comment")
            out.append("\n" * text.count("\n", i, j + 2))
            i = j + 2
            continue
        if text.startswith("//", i) or text.startswith("\\\\", i):
            j = text.find("\n", i)
            i = n if j < 0 else j
            continue
        out.append(c)
        i += 1
    return "".join(out)


def tokenize_line(line: str, file: str, lineno: int):
    toks = []
    pos = 0
    while pos < len(line):
        m = _TOKEN_RE.match(line, pos)
        if not m:
            raise PreprocessError(f"{file}:{lineno}: cannot tokenize {line[pos:pos+20]!r}")
        kind = m.lastgroup
        val = m.group(kind)
        pos = m.end()
        if kind == "ws":
            continue
        toks.append(Tok(kind, val, file, lineno))
    return toks


@dataclass
class Macro:
    name: str
    params: list[str] | None
    body: list[Tok]


class Preprocessor:
    def __init__(self, include_dirs, defines=None, include_map=None):
        self.include_dirs = [Path(p) for p in include_dirs]
        self.macros: dict[str, Macro] = {}
        self.uses: list[tuple[str, str, str]] = []  # (kind, path, alias)
        self.include_map = {k.lower(): Path(v) for k, v in (include_map or {}).items()}
        self.files: list[Path] = []
        for name, value in (defines or {"PPLC": ""}).items():
            self.macros[name] = Macro(name, None, tokenize_line(value, "<cmd>", 0))

    # -- file handling -------------------------------------------------
    def _resolve(self, name: str, current: Path) -> Path:
        key = name.replace("\\", "/").lower()
        if key in self.include_map:
            return self.include_map[key]
        cands = [current.parent / name.replace("\\", "/")]
        cands += [d / Path(name.replace("\\", "/")).name for d in self.include_dirs]
        for c in cands:
            if c.exists():
                return c
            # case-insensitive match on Windows/Posix
            if c.parent.exists():
                for p in c.parent.iterdir():
                    if p.name.lower() == c.name.lower():
                        return p
        raise PreprocessError(f"Include not found: {name}")

    def run(self, path: Path):
        out: list[Tok] = []
        self._process_file(Path(path), out)
        # PPL identifiers are case-insensitive after preprocessing; macros are not
        # (the supplied includes define DELAY() alongside the delay() builtin).
        for t in out:
            if t.kind == "id":
                t.value = t.value.lower()
        return out

    def _process_file(self, path: Path, out: list[Tok]):
        self.files.append(path)
        raw = path.read_text(encoding="latin-1")
        # join directive continuation lines before comment stripping is unsafe for
        # '\\' comments, so first split, then join only '#' logical lines.
        lines = raw.split("\n")
        logical = []  # (lineno, text)
        i = 0
        while i < len(lines):
            line = lines[i]
            start = i + 1
            if line.lstrip().startswith("#"):
                while line.rstrip("\r").endswith("\\") and not line.rstrip("\r").endswith("\\\\") and i + 1 < len(lines):
                    line = line.rstrip("\r")[:-1] + " " + lines[i + 1]
                    i += 1
            logical.append((start, line))
            i += 1
        # comment stripping across the logical stream (block comments may span lines)
        joined = "\n".join(t for _, t in logical)
        stripped = _strip_comments(joined).split("\n")
        assert len(stripped) == len(logical)
        cond_stack: list[tuple[bool, bool]] = []  # (active, any_branch_taken)

        def active():
            return all(a for a, _ in cond_stack)

        pending: list[Tok] = []

        def flush():
            if pending:
                out.extend(self.expand(list(pending)))
                pending.clear()

        for (lineno, _), text in zip(logical, stripped):
            s = text.strip()
            if s.startswith("#"):
                flush()
                m = re.match(r"#\s*(\w+)\s*(.*)$", s)
                if not m:
                    raise PreprocessError(f"{path}:{lineno}: bad directive {s!r}")
                d, rest = m.group(1).lower(), m.group(2)
                if d in ("ifdef", "ifndef"):
                    name = rest.split()[0]
                    val = name in self.macros
                    if d == "ifndef":
                        val = not val
                    cond_stack.append((val, val))
                    continue
                if d == "else":
                    if not cond_stack:
                        raise PreprocessError(f"{path}:{lineno}: #else without #if")
                    a, taken = cond_stack.pop()
                    cond_stack.append((not taken, True))
                    continue
                if d == "endif":
                    if not cond_stack:
                        raise PreprocessError(f"{path}:{lineno}: #endif without #if")
                    cond_stack.pop()
                    continue
                if not active():
                    continue
                if d == "define":
                    self._define(rest, str(path), lineno)
                elif d == "undef":
                    self.macros.pop(rest.split()[0], None)
                elif d == "include":
                    mm = re.match(r'"([^"]+)"', rest)
                    if not mm:
                        raise PreprocessError(f"{path}:{lineno}: bad include")
                    self._process_file(self._resolve(mm.group(1), path), out)
                elif d == "use":
                    mm = re.match(r'(\w+)\s+"([^"]+)"\s+(\w+)', rest)
                    if not mm:
                        raise PreprocessError(f"{path}:{lineno}: bad #use")
                    self.uses.append((mm.group(1).upper(), mm.group(2), mm.group(3).lower()))
                elif d == "error":
                    raise PreprocessError(f"{path}:{lineno}: #error {rest}")
                else:
                    raise PreprocessError(f"{path}:{lineno}: unsupported directive #{d}")
                continue
            if not active():
                continue
            pending.extend(tokenize_line(text, str(path), lineno))
        flush()
        if cond_stack:
            raise PreprocessError(f"{path}: unterminated conditional")

    def _define(self, rest: str, file: str, lineno: int):
        m = re.match(r"([A-Za-z_]\w*)(\(([^)]*)\))?\s*(.*)$", rest, re.S)
        if not m:
            raise PreprocessError(f"{file}:{lineno}: bad #define {rest!r}")
        name = m.group(1)
        params = None
        if m.group(2) is not None and rest[len(m.group(1))] == "(":
            params = [p.strip() for p in m.group(3).split(",") if p.strip()]
            body_txt = m.group(4)
        else:
            body_txt = rest[len(m.group(1)):]
        body = tokenize_line(body_txt, file, lineno)
        self.macros[name] = Macro(name, params, body)

    # -- macro expansion ---------------------------------------------------
    def expand(self, toks: list[Tok], hide=frozenset()) -> list[Tok]:
        out: list[Tok] = []
        i = 0
        while i < len(toks):
            t = toks[i]
            if t.kind == "id" and t.value in self.macros and t.value not in hide:
                mac = self.macros[t.value]
                if mac.params is None:
                    body = [Tok(b.kind, b.value, t.file, t.line) for b in mac.body]
                    body = self._paste(body)
                    out.extend(self.expand(body, hide | {t.value}))
                    i += 1
                    continue
                # function-like: need '('
                if i + 1 < len(toks) and toks[i + 1].value == "(":
                    args, j = self._collect_args(toks, i + 1)
                    if len(mac.params) == 0 and args == [[]]:
                        args = []
                    if len(args) != len(mac.params):
                        raise PreprocessError(f"{t}: macro {mac.name} expects {len(mac.params)} args, got {len(args)}")
                    exp_args = [self.expand(a, hide) for a in args]
                    body = []
                    k = 0
                    mb = mac.body
                    while k < len(mb):
                        b = mb[k]
                        nxt_paste = k + 1 < len(mb) and mb[k + 1].value == "##"
                        prev_paste = k > 0 and mb[k - 1].value == "##"
                        if b.kind == "id" and b.value in mac.params:
                            idx = mac.params.index(b.value)
                            src = args[idx] if (nxt_paste or prev_paste) else exp_args[idx]
                            body.extend(Tok(a.kind, a.value, t.file, t.line) for a in src)
                        else:
                            body.append(Tok(b.kind, b.value, t.file, t.line))
                        k += 1
                    body = self._paste(body)
                    out.extend(self.expand(body, hide | {t.value}))
                    i = j
                    continue
            out.append(t)
            i += 1
        return out

    @staticmethod
    def _paste(body):
        return [b for b in body if b.value != "##"]

    @staticmethod
    def _collect_args(toks, i):
        assert toks[i].value == "("
        depth = 0
        args = [[]]
        j = i
        while j < len(toks):
            v = toks[j].value
            if v == "(":
                depth += 1
                if depth > 1:
                    args[-1].append(toks[j])
            elif v == ")":
                depth -= 1
                if depth == 0:
                    return args, j + 1
                args[-1].append(toks[j])
            elif v == "," and depth == 1:
                args.append([])
            else:
                args[-1].append(toks[j])
            j += 1
        raise PreprocessError(f"{toks[i]}: unterminated macro arguments")


def extract_paramlist(path: Path) -> str:
    text = Path(path).read_text(encoding="latin-1")
    m = re.search(r"/\*\s*PARAMLIST(.*?)\nEND", text, re.S)
    return m.group(1) if m else ""
