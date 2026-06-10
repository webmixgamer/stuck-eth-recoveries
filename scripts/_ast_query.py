#!/usr/bin/env python3
"""AST query plumbing for HONG's legacy solc-0.3.6 `--ast-json` output.

The legacy 0.3.6 AST nests *sibling* declarations as *descendants*, so the
parent/child structure is NOT reliable for reconstructing scope. Instead we
DFS-flatten every node and recover structure purely from the `src` byte-interval
("start:length:fileIndex") via containment. This module is neutral plumbing —
the recovery-path detection logic lives in detect_recovery_path.py.

The AST artifact lives next to the source (docs/reference/), NOT in Foundry's
`out/` dir, which `forge build`/`forge test` wipe. Regenerate it with:
    solc-select use 0.3.6
    solc --ast-json docs/reference/HONG.sol | \
        python3 -c "import sys,json;r=sys.stdin.read();s=r.index('{');\
o,_=json.JSONDecoder().raw_decode(r,s);json.dump(o,open('docs/reference/HONG.ast.json','w'),indent='\t')"

CLI:
    python3 scripts/_ast_query.py types                 # node-type histogram
    python3 scripts/_ast_query.py functions             # all Function nodes + spans
    python3 scripts/_ast_query.py func <name>           # nodes inside each impl of <name>
    python3 scripts/_ast_query.py find <NodeType> [attr=val ...]
"""
import json
import os
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AST_PATH = os.path.join(ROOT, "docs", "reference", "HONG.ast.json")
SRC_PATH = os.path.join(ROOT, "docs", "reference", "HONG.sol")

# Node types that carry structural meaning for recovery-path detection.
STRUCTURAL = {
    "Assignment", "BinaryOperation", "UnaryOperation", "IfStatement",
    "FunctionCall", "IndexAccess", "MemberAccess", "Identifier", "Return",
    "Throw", "Literal", "VariableDeclaration",
}

# The legacy AST node-type name CHANGES across the solc family: 0.3.x emits
# "Function"/"Contract"; 0.4.x emits "FunctionDefinition"/"ContractDefinition".
# Use these sets everywhere instead of a single literal so the walker is
# dialect-agnostic across the whole legacy (0.3.x-0.4.x) range.
FUNCTION_NAMES = {"Function", "FunctionDefinition"}
CONTRACT_NAMES = {"Contract", "ContractDefinition"}


def load(ast_path=AST_PATH, src_path=SRC_PATH):
    """Returns (ast, src) where `src` is the source as RAW BYTES.

    GOTCHA: solc 0.3.6 emits `src` offsets in BYTES, but HONG.sol contains
    multi-byte UTF-8 (818 bytes > chars). Indexing a decoded `str` by those
    offsets drifts (worse the later the offset) and silently maps nodes to the
    wrong function. So all offset math here is on bytes.
    """
    with open(ast_path) as f:
        ast = json.load(f)
    with open(src_path, "rb") as f:
        src = f.read()
    return ast, src


def line_of(src, off):
    """1-based line number of a byte offset (src is bytes)."""
    return src.count(b"\n", 0, off) + 1


def parse_src(s):
    """'start:length:fileIndex' -> (start, length)."""
    a, b, _ = s.split(":")
    return int(a), int(b)


def node_span(n):
    """(start, end) byte interval of a node, or None."""
    s = n.get("src")
    if not s:
        return None
    start, length = parse_src(s)
    return (start, start + length)


def contains(outer, inner):
    """True if `outer` interval contains `inner` (inclusive)."""
    if not outer or not inner:
        return False
    return outer[0] <= inner[0] and inner[1] <= outer[1]


def flatten(ast):
    """DFS over every node; returns the list of raw node dicts in source order."""
    out = []

    def walk(n):
        if isinstance(n, dict):
            out.append(n)
            for c in n.get("children") or []:
                walk(c)
        elif isinstance(n, list):
            for c in n:
                walk(c)

    walk(ast)
    return out


def attr(n, key, default=None):
    return n.get("attributes", {}).get(key, default)


def snippet(src, n, maxlen=140):
    """Decoded, whitespace-normalized source slice for a node (src is bytes)."""
    sp = node_span(n)
    if not sp:
        return ""
    raw = src[sp[0]:sp[1]].decode("utf-8", errors="replace")
    return " ".join(raw.split())[:maxlen]


def function_impls(nodes, src, name=None):
    """Function nodes that have a body (a Block within their span) = real impls,
    not interface stubs. Optionally filter by attribute name."""
    funcs = [n for n in nodes if n.get("name") in FUNCTION_NAMES]
    blocks = [n for n in nodes if n.get("name") == "Block"]
    impls = []
    for f in funcs:
        if name is not None and attr(f, "name") != name:
            continue
        fsp = node_span(f)
        has_body = any(contains(fsp, node_span(b)) for b in blocks)
        impls.append((f, has_body))
    return impls


def nodes_within(nodes, span, types=None):
    """All nodes contained in `span`, optionally filtered to `types`."""
    out = []
    for n in nodes:
        if types and n.get("name") not in types:
            continue
        if contains(span, node_span(n)):
            out.append(n)
    return out


def _fmt(src, n):
    sp = node_span(n)
    lines = f"L{line_of(src, sp[0])}-{line_of(src, sp[1])}" if sp else "?"
    op = attr(n, "operator")
    nm = attr(n, "name")
    tag = []
    if op:
        tag.append(f"op={op!r}")
    if nm:
        tag.append(f"name={nm!r}")
    tagstr = (" " + " ".join(tag)) if tag else ""
    return f"  [{n.get('name')}] {lines}{tagstr} :: {snippet(src, n, 110)}"


def main(argv):
    cmd = argv[0] if argv else "functions"
    ast, src = load()
    nodes = flatten(ast)

    if cmd == "types":
        for k, v in Counter(n.get("name") for n in nodes).most_common():
            print(f"{v:5d}  {k}")
        return

    if cmd == "functions":
        for f, has_body in function_impls(nodes, src):
            sp = node_span(f)
            kind = "impl" if has_body else "stub"
            print(f"[{kind}] {attr(f,'name')!r:32} src={f['src']:>14} "
                  f"L{line_of(src,sp[0])}-{line_of(src,sp[1])}")
        return

    if cmd == "func":
        name = argv[1]
        for f, has_body in function_impls(nodes, src, name):
            if not has_body:
                continue
            sp = node_span(f)
            print(f"=== {name} impl  src={f['src']}  "
                  f"L{line_of(src,sp[0])}-{line_of(src,sp[1])} ===")
            for n in nodes_within(nodes, sp, STRUCTURAL):
                if n is f:
                    continue
                print(_fmt(src, n))
            print()
        return

    if cmd == "find":
        ntype = argv[1]
        filters = dict(a.split("=", 1) for a in argv[2:])
        for n in nodes:
            if n.get("name") != ntype:
                continue
            if any(str(attr(n, k)) != v for k, v in filters.items()):
                continue
            print(_fmt(src, n))
        return

    print(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
