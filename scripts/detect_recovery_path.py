#!/usr/bin/env python3
"""Recovery-path HYPOTHESIS detector over HONG's legacy solc-0.3.6 `--ast-json`.

WHAT THIS IS (and is NOT)
-------------------------
This script reads a legacy solc-0.3.x AST (default out/HONG.ast.json) and, with
ZERO human pointing, surfaces *recovery-path hypotheses* of the shape:

    "an UNCHECKED, balance-inflating state write in one function (the SOURCE)
     unlocks a balance-gated ETH-out in another function (the SINK)"

For HONG this is exactly  mgmtIssueBountyToken (balances[x] += amount, unchecked)
-> refundMyIcoInvestment (balances[msg.sender] > tokensCreated gate, then
msg.sender.send(...)).

HARD INVARIANTS (never violated here):
  * The detector emits a HYPOTHESIS, never a verdict. The Foundry mainnet-fork
    proof (test/HongUnlock.t.sol) is the SOLE oracle that a path is real. The
    heuristic only NOMINATES (source -> sink) candidates for proving.
  * Every hypothesis carries a `required_authority` field (who must sign to
    perform the inflating write) feeding a legal front-runnability gate:
    access-gated => LOW legal tier (owner-signs / no-custody firewall holds);
    `anyone`/front-runnable => HIGH tier (route to SEAL-911, never unilateral).
    Default-safe: an unrecognized gate => `anyone`/HIGH, never silently LOW.

DESIGN (precision on the transfer false-positives, generality elsewhere):
  * Scope is reconstructed ENTIRELY from `src` BYTE-interval containment, never
    parent/child. Legacy 0.3.x nests sibling declarations as descendants and
    root.children collapses to length 1, so parent/child is unusable for scope.
  * State variables (and which are mappings) are discovered at runtime, not
    hardcoded: a VariableDeclaration with a `Mapping` child, declared OUTSIDE
    every ParameterList and Block. The pairing join key is whatever base
    identifier the inflated write resolves to (e.g. 'balances') -- never a literal.
  * The UNCHECKED discriminator (the false-positive killer) flags an inflating
    write ONLY if NO guard in the same function constrains the SAME base var --
    either an IfStatement that byte-encloses the write, OR a PRIOR IfStatement
    whose condition references that base var (the pre-SafeMath early-return
    idiom `if (bal[x]+d < bal[x]) return`), OR a SafeMath-style checked-add call.
    This is what excludes BOTH transfer impls while flagging mgmtIssueBountyToken.
  * ETH-out keys on the universal pre-0.8 egress primitives (.send / .call.value)
    with explicit exclusion of token .transfer (super.transfer) and msg.value
    reads.

Built on the _ast_query plumbing (load/flatten/contains/attr/line_of/node_span/
snippet). Scans are hand-rolled rather than via q.nodes_within because scope here
needs the own-span variant (subtract inner-function spans; see _own_span_test) to
stop a sibling function's statements -- nested as descendants in the legacy AST --
from leaking in. No third-party deps.

Usage:
    python3 scripts/detect_recovery_path.py [ast.json] [src.sol]
Defaults: out/HONG.ast.json, docs/reference/HONG.sol.
"""
import json
import os
import re
import sys

# --- import the shared AST plumbing (works regardless of CWD) -----------------
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
import _ast_query as q  # noqa: E402

# ---------------------------------------------------------------------------
# Tunable, dialect-agnostic vocabularies (structural, not HONG identifiers).
# ---------------------------------------------------------------------------

# Comparison operators that can form a bounds/overflow guard or a balance gate.
_CMP_OPS = {"<", ">", "<=", ">=", "==", "!="}

# Names of checked-arithmetic helpers (SafeMath idiom). Absent in 0.3.x HONG,
# included so the guard discriminator generalizes to later contracts.
_SAFEMATH_NAMES = {"add", "sadd", "safeAdd", "safeadd", "plus", "addmod"}

# Modifier names whose guard shape is a *signer* check (msg.sender vs a fixed/
# stored admin address or role). Used only as a hint; the real classification
# reads the modifier DEFINITION's guard shape so a misleadingly-named modifier
# cannot fool us.
_SIGNER_GATE_HINT = re.compile(
    r"only(owner|admin|management|manager|governor|multisig|curator)", re.I)


# ---------------------------------------------------------------------------
# Small structural helpers (all scope via byte-span containment).
# ---------------------------------------------------------------------------

def _base_name(node):
    """Resolve the base Identifier name of a (possibly nested) IndexAccess /
    MemberAccess / Identifier. balances[_to] -> 'balances';
    votedKickoff[a][b] -> 'votedKickoff'; plain Identifier -> its value."""
    cur = node
    while cur is not None and cur.get("name") in ("IndexAccess", "MemberAccess"):
        kids = cur.get("children") or []
        cur = kids[0] if kids else None
    if cur is not None and cur.get("name") == "Identifier":
        return q.attr(cur, "value")
    return None


def _idents_in(node):
    """Set of all base state-var names referenced anywhere in a subtree.
    Walks raw children (a node's OWN subtree is reliable; it is only *sibling*
    scope that is unreliable in this legacy AST)."""
    out = set()
    stack = [node]
    while stack:
        x = stack.pop()
        if not isinstance(x, dict):
            continue
        nm = x.get("name")
        if nm == "Identifier":
            v = q.attr(x, "value")
            if v:
                out.add(v)
        elif nm == "IndexAccess":
            b = _base_name(x)
            if b:
                out.add(b)
        for c in x.get("children") or []:
            stack.append(c)
    return out


def _body_block_span(fnode, nodes):
    """Byte-span of a function impl's outermost (max-length) body Block. The
    function header (modifiers, params, return list) lives BEFORE this start,
    which lets us cleanly separate modifier identifiers from body guards."""
    fsp = q.node_span(fnode)
    blocks = [q.node_span(b) for b in nodes
              if b.get("name") == "Block" and q.contains(fsp, q.node_span(b))]
    if not blocks:
        return None
    return max(blocks, key=lambda sp: sp[1] - sp[0])


def _own_span_test(fnode, nodes):
    """Return a predicate own(node)->bool: True iff `node` is inside `fnode`'s
    span but NOT inside any INNER function's span. Legacy ASTs nest sibling
    declarations as descendants, so a naive containment scan can leak another
    function's statements; subtracting inner-function spans prevents that."""
    fsp = q.node_span(fnode)
    inner = []
    for f in nodes:
        if f.get("name") not in q.FUNCTION_NAMES:
            continue
        sp = q.node_span(f)
        if sp and sp != fsp and q.contains(fsp, sp):
            inner.append(sp)

    def own(node):
        sp = q.node_span(node)
        if not sp or not q.contains(fsp, sp):
            return False
        for isp in inner:
            if q.contains(isp, sp):
                return False
        return True

    return own


# ---------------------------------------------------------------------------
# Phase 0: discover contract-scope state variables (and which are mappings).
# ---------------------------------------------------------------------------

def discover_state_vars(nodes):
    """A VariableDeclaration is a contract-scope state var iff it is NOT inside
    any ParameterList (so function/modifier params and interface-stub signature
    params are excluded) AND NOT inside any Block (so function locals are
    excluded). We additionally flag mapping-typed ones (a `Mapping` child).
    Returns (state_var_names:set, mapping_names:set). Discovered at runtime; no
    names are assumed.

    NB: the naive 'not inside any *function* span' test leaks params, because
    interface-stub functions have no body and 0.3.x floats their signature
    params (and synthetic msg.sender/msg.value magic decls) outside every
    *bodied* span. ParameterList + Block exclusion is the robust discriminator
    (verified: keeps balances/tokensCreated/managementBodyAddress, drops
    _amount/_to/msg_sender)."""
    param_lists = [q.node_span(p) for p in nodes
                   if p.get("name") == "ParameterList"]
    param_lists = [sp for sp in param_lists if sp]
    blocks = [q.node_span(b) for b in nodes if b.get("name") == "Block"]
    blocks = [sp for sp in blocks if sp]
    state, mappings = set(), set()
    for n in nodes:
        if n.get("name") != "VariableDeclaration":
            continue
        sp = q.node_span(n)
        if not sp:
            continue
        name = q.attr(n, "name")
        if not name:
            continue
        if any(q.contains(pl, sp) for pl in param_lists):
            continue  # a parameter (function/modifier/interface-stub signature)
        if any(q.contains(bl, sp) for bl in blocks):
            continue  # a function local
        state.add(name)
        if any(c.get("name") == "Mapping" for c in (n.get("children") or [])):
            mappings.add(name)
    return state, mappings


def is_public(fnode):
    """Externally callable? Dialect-agnostic: 0.4.x uses a `visibility` string
    ('public'/'external'/'internal'/'private'); 0.3.x uses a `public` bool (and
    functions are public by default when unspecified)."""
    vis = q.attr(fnode, "visibility")
    if vis is not None:
        return vis in ("public", "external")
    pub = q.attr(fnode, "public")
    return True if pub is None else bool(pub)


def owning_contract(fnode, nodes):
    """Innermost Contract whose span contains the function (byte-span)."""
    fsp = q.node_span(fnode)
    cands = []
    for c in nodes:
        if c.get("name") not in q.CONTRACT_NAMES:
            continue
        csp = q.node_span(c)
        if csp and q.contains(csp, fsp):
            cands.append(c)
    if not cands:
        return None
    inner = min(cands, key=lambda c: (q.node_span(c)[1] - q.node_span(c)[0]))
    return q.attr(inner, "name")


def _is_constructor(fnode, nodes):
    """A constructor is not callable post-deployment, so it can never be a live
    recovery source/sink. 0.4.x flags isConstructor=True; 0.3.x / legacy 0.4.x name
    the constructor after the contract. [AST-2]"""
    if q.attr(fnode, "isConstructor") is True:
        return True
    return q.attr(fnode, "name") == owning_contract(fnode, nodes)


# ---------------------------------------------------------------------------
# Phase 1: modifiers + required_authority (the legal gate input).
# ---------------------------------------------------------------------------

def modifiers_of(fnode, nodes, src):
    """Modifier invocation names on a function -- dialect-agnostic.

    0.4.x: each use is a `ModifierInvocation` node within the function span whose
    first child Identifier names the modifier.
    0.3.x: modifiers are NOT a Function attribute and NOT in Function.children --
    they surface as bare Identifier nodes in the header region (before the body
    Block) whose solc type-string starts with 'modifier' (the type filter excludes
    modifier ARGUMENTS like _amount, type 'uint256')."""
    fsp = q.node_span(fnode)
    out = []
    # 0.4.x: ModifierInvocation nodes contained in the function span.
    for n in nodes:
        if n.get("name") != "ModifierInvocation":
            continue
        if not q.contains(fsp, q.node_span(n)):
            continue
        kids = n.get("children") or []
        nm = q.attr(kids[0], "value") if kids else q.attr(n, "name")
        if nm and nm not in out:
            out.append(nm)
    if out:
        return out
    # 0.3.x fallback: header Identifiers typed 'modifier'.
    body = _body_block_span(fnode, nodes)
    hdr_end = body[0] if body else fsp[1]
    for n in nodes:
        if n.get("name") != "Identifier":
            continue
        sp = q.node_span(n)
        if not sp or not (fsp[0] <= sp[0] and sp[1] <= hdr_end):
            continue
        if str(q.attr(n, "type") or "").startswith("modifier"):
            v = q.attr(n, "value")
            if v and v not in out:
                out.append(v)
    return out


def _modifier_definitions(src):
    """Map modifier name -> its guard body text, parsed from source. We resolve
    authority from the guard SHAPE (not the name), so a deceptively-named
    modifier cannot mislabel a finding. Returns {name: body_text}."""
    text = src.decode("utf-8", errors="replace")
    defs = {}
    # `modifier name(args?) { ... }` -- capture up to a balanced close brace.
    for m in re.finditer(r"modifier\s+(\w+)\s*(\([^)]*\))?\s*\{", text):
        name = m.group(1)
        start = m.end() - 1  # at the opening brace
        depth, i = 0, start
        while i < len(text):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        defs[name] = text[start:i + 1]
    return defs


# Abort idioms that make a guard ENFORCING (incl. HONG's `doThrow(...)` helper;
# case-insensitive so doThrow/_revert/etc. match). A signer comparison with NO
# abort in scope is a no-op/log-only guard => NOT a gate (default-safe). [FW-1]
_ABORT_RE = re.compile(r"revert|throw|require|assert", re.I)
_REQUIRE_CALL_RE = re.compile(r"\b(?:require|assert)\s*\(")
_IF_RE = re.compile(r"\bif\s*\(")


def _strip_comments_strings(text):
    """Drop // and /* */ comments and string/char literals so a `public`/`msg.sender`
    token inside a comment or string can never be mistaken for code. [FW-1/AST-1]"""
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    text = re.sub(r"//[^\n]*", " ", text)
    text = re.sub(r'"(?:\\.|[^"\\])*"', " ", text)
    text = re.sub(r"'(?:\\.|[^'\\])*'", " ", text)
    return text


def _matched(s, open_idx, op, cl):
    """Index of the closing `cl` matching the `op` at open_idx (nesting-aware)."""
    depth, i = 0, open_idx
    while i < len(s):
        if s[i] == op:
            depth += 1
        elif s[i] == cl:
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return len(s)


def _paren_close(s, open_idx):
    return _matched(s, open_idx, "(", ")")


def _consume_stmt(s, i):
    """From index i (first non-space of a statement), consume a `{...}` block or a
    single statement up to ';'. Returns (statement_text, next_index)."""
    while i < len(s) and s[i].isspace():
        i += 1
    if i < len(s) and s[i] == "{":
        end = _matched(s, i, "{", "}")
        return s[i:end + 1], end + 1
    end = s.find(";", i)
    if end == -1:
        end = len(s)
    return s[i:end + 1], end + 1


def _then_else(s, after_cond_idx):
    """(then_text, else_text) for an if whose condition closes at after_cond_idx-1."""
    then_text, i = _consume_stmt(s, after_cond_idx)
    j = i
    while j < len(s) and s[j].isspace():
        j += 1
    if s[j:j + 4] == "else" and (j + 4 >= len(s) or not (s[j + 4].isalnum() or s[j + 4] == "_")):
        else_text, _ = _consume_stmt(s, j + 4)
        return then_text, else_text
    return then_text, ""


def _sender_principal(expr, op):
    """Identifier P compared to msg.sender with the EXACT op ('=='/'!=') in
    `expr`, in either order, allowing an `address(...)` cast. None otherwise.
    Only identity ops gate a signer; <,>,<=,>= are not identity gates."""
    o = re.escape(op)
    m = (re.search(r"msg\.sender\s*" + o + r"\s*(?:address\s*\(\s*)?([A-Za-z_]\w*)", expr)
         or re.search(r"(?:address\s*\(\s*)?([A-Za-z_]\w*)\s*" + o + r"\s*msg\.sender", expr))
    if m and m.group(1) != "msg":
        return m.group(1)
    return None


def _enforcing_signer_principal(body):
    """Principal P iff the (comment/string-stripped) modifier `body` is an
    ENFORCING signer gate that RESTRICTS the caller to exactly P; else None
    (=> default-safe 'anyone'/HIGH). Recognizes ONLY the polarity-correct idioms:

        require/assert(msg.sender == P)              passes iff sender == P
        if (msg.sender != P) <abort>                 reverts for everyone but P

    REJECTS (=> None): inverted polarity (require !=, `if (sender == P) revert`),
    no-op / log-only bodies with no abort, and bodies with no identity comparison.
    The guard RESTRICTS-to-P iff it ABORTS exactly when sender != P, in either
    encoding: `if (sender != P) {abort}` (then-abort) OR `if (sender == P) {pass}
    else {abort}` (else-abort). This is the FW-1/FW-2 fix: classification is now
    polarity- and enforcement-aware, not a bare substring match."""
    # require/assert(msg.sender == P [...]) -- pass-set restricts to P
    for m in _REQUIRE_CALL_RE.finditer(body):
        arg = body[m.end():_paren_close(body, m.end() - 1)]
        p = _sender_principal(arg, "==")
        if p:
            return p
    # if (...) <then> [else <else>] -- restricts to P iff it aborts when sender != P
    for m in _IF_RE.finditer(body):
        cond_end = _paren_close(body, m.end() - 1)
        cond = body[m.end():cond_end]
        then_t, else_t = _then_else(body, cond_end + 1)
        then_abort = bool(_ABORT_RE.search(then_t))
        else_abort = bool(_ABORT_RE.search(else_t))
        if then_abort:                       # if (sender != P) abort
            p = _sender_principal(cond, "!=")
            if p:
                return p
        if else_abort:                       # if (sender == P) pass else abort
            p = _sender_principal(cond, "==")
            if p:
                return p
    return None


def classify_authority(fnode, nodes, src, mod_defs):
    """Derive required_authority for a single function from its modifiers'
    guard SHAPES.

    Returns dict: {principal, modifiers, access_gated, kind}
      kind in {'signer-gated','holder-gated','anyone'}.

    SHAPE rules (structural, name-agnostic):
      * signer gate  : the modifier body compares `msg.sender` against something
                       that is NOT a balanceOf(...) call -> a fixed/stored admin
                       address or role  => ACCESS-GATED (LOW tier).
      * holder gate  : the modifier body checks balanceOf(msg.sender) / a balance
                       mapping of msg.sender  => restricted to a token-holder
                       CLASS (not arbitrary, but not a single signer).
      * value/state  : noEther/hasEther/notLocked/... (msg.value or a bare state
                       flag) -> NOT a signer gate; ignored for authority.
    Default-safe: no signer gate found => kind='anyone' (front-runnable, HIGH)."""
    mods = modifiers_of(fnode, nodes, src)
    principal = None
    kind = "anyone"
    for name in mods:
        body = _strip_comments_strings(mod_defs.get(name, ""))
        if "msg.sender" not in body:
            continue  # value/state guard (noEther, notLocked, ...): not an authority gate
        # CLASS / HOLDER gate: msg.sender used as a balanceOf() argument OR as a
        # mapping KEY (balances[msg.sender], isWhitelisted[msg.sender], ...). Anyone
        # who JOINS the class (acquires tokens / gets whitelisted) passes -- this is a
        # restricted CLASS, not a single privileged signer (cf. the Eisenberg/Mango
        # buy-then-act scenario). Never a 'fixed signer set'.
        if "balanceOf" in body or re.search(r"\[\s*msg\.sender\s*\]", body):
            if kind == "anyone":
                kind = "holder-gated"
                principal = principal or "any token holder"
            continue
        # SIGNER gate: ONLY when an ENFORCING, polarity-correct guard restricts the
        # caller to a single principal -- require(sender==P) or if(sender!=P){abort}.
        # A msg.sender comparison that does NOT revert (no-op / log-only) or that
        # reverts with the WRONG polarity (inverted gate => permissionless) is NOT a
        # signer gate and stays DEFAULT-SAFE 'anyone' (=> HIGH / front-runnable),
        # never silently signer-gated/LOW. Hard legal-firewall invariant. [FW-1/FW-2]
        p = _enforcing_signer_principal(body)
        if p:
            principal = p
            kind = "signer-gated"
        # else: DEFAULT-SAFE -- unrecognized / non-enforcing / inverted gate => 'anyone'.
    access_gated = kind == "signer-gated"
    return {
        "principal": principal,
        "modifiers": mods,
        "access_gated": access_gated,
        "kind": kind,
    }


def authority_string(auth):
    """Human/JSON-friendly required_authority label from a classify_authority()
    result. (The end-to-end path authority is computed by join_authority.)"""
    if auth["kind"] == "signer-gated":
        p = auth["principal"]
        return f"admin/owner ({p}; fixed signer set in constructor)" if p \
            else "admin/owner (fixed signer)"
    if auth["kind"] == "holder-gated":
        return "any token holder (restricted class)"
    return "anyone (front-runnable)"


def join_authority(src_auth, sink_auth):
    """End-to-end legal classification of a (write -> sink) recovery path.
    Returns (authority_string, legal_tier, front_runnable).

    LABEL (for reporting) names the MORE-privileged endpoint -- executing the
    recovery requires the inflating write, so the admin lever is what a human
    reads first.

    TIER / FRONT-RUNNABILITY (the legal gate) take the WEAKEST-LINK reading: an
    'anyone'-callable leg ANYWHERE on the path makes the path front-runnable and
    HIGH tier (route to SEAL-911), regardless of how privileged the OTHER leg is.
    A privileged source must NEVER mask an ungated sink down to LOW -- that is the
    hard default-safe invariant (header lines 22-24). [FP-4]"""
    order = {"signer-gated": 2, "holder-gated": 1, "anyone": 0}
    dominant = src_auth if order[src_auth["kind"]] >= order[sink_auth["kind"]] \
        else sink_auth
    label = authority_string(dominant)
    # Weakest link: any ungated leg => front-runnable => HIGH.
    if src_auth["kind"] == "anyone" or sink_auth["kind"] == "anyone":
        return label, "HIGH", True
    # No ungated leg: both ends are access-restricted (signer and/or holder class)
    # => owner-/class-signs path holds => LOW, not front-runnable.
    return label, "LOW", False


# ---------------------------------------------------------------------------
# Phase 2: SOURCE detection -- unchecked balance-inflating writes.
# ---------------------------------------------------------------------------

def _is_inflating_shape(assign):
    """SHAPE test: `x += d`  OR  `x = x + d` / `x = x * k` (RHS re-reads the
    LHS base). The strict self-reference for '=' rejects re-initializations
    like `balances[x] = 0` and snapshot copies `voted[x] = balances[x]`."""
    op = q.attr(assign, "operator")
    if op == "+=":
        return True
    if op == "=":
        kids = assign.get("children") or []
        if len(kids) < 2:
            return False
        lhs, rhs = kids[0], kids[1]
        lhs_base = _base_name(lhs)
        if not lhs_base:
            return False
        for n in q.flatten(rhs):
            if n.get("name") == "BinaryOperation" and q.attr(n, "operator") in ("+", "*"):
                if lhs_base in _idents_in(n):
                    return True
    return False


def _rhs_is_safemath(assign):
    """SafeMath escape hatch: RHS is a checked-add call (add/safeAdd/plus...)."""
    kids = assign.get("children") or []
    if len(kids) < 2:
        return False
    for n in q.flatten(kids[1]):
        if n.get("name") == "FunctionCall":
            callee = (n.get("children") or [None])[0]
            if callee is None:
                continue
            nm = (q.attr(callee, "member_name")
                  or q.attr(callee, "value") or "")
            if nm in _SAFEMATH_NAMES:
                return True
    return False


def find_inflating_writes(fnode, nodes, src, mappings):
    """Unchecked balance-inflating writes inside one function impl.

    Returns a list of dicts. A write is UNCHECKED iff NO guard constrains its
    base var, where a guard is: (a) an IfStatement that byte-ENCLOSES the write,
    OR (b) a PRIOR IfStatement (lower start line, same body) whose CONDITION
    references the same base var, OR (c) a SafeMath checked-add RHS, OR (d) a
    PRIOR require()/assert() call whose argument references the same base var.

    Branch (b) is the 0.3.x precision linchpin: Token.transfer's overflow guard
    L85 `if (bal[_to]+_amount < bal[_to]) return false` is an early-return that
    PRECEDES the L88 write, so lexical enclosure alone (a) would miss it and
    false-positive. (b) catches it because L85's condition references base
    'balances'. mgmtIssueBountyToken L439 has neither => UNCHECKED => flagged.
    Branch (d) is the 0.4.x analogue: the idiomatic overflow guard there is
    `require(bal[to]+amt >= bal[to]);` -- a FunctionCall (not an IfStatement), so
    (a)/(b) miss it; without (d) a require-guarded admin top-up would be wrongly
    flagged 'unchecked' and (for a '<' top-up gate) the fork-proof would PASS on a
    non-buggy contract -- a false 'proven recovery'. [MD-2]"""
    own = _own_span_test(fnode, nodes)
    body = _body_block_span(fnode, nodes)
    if not body:
        return []
    ifs = [n for n in nodes if n.get("name") == "IfStatement" and own(n)]
    # (d) require()/assert() guard calls + the base vars their argument references.
    req_guards = []
    for n in nodes:
        if n.get("name") != "FunctionCall" or not own(n):
            continue
        callee = (n.get("children") or [None])[0]
        if callee is None:
            continue
        nm = q.attr(callee, "value") or q.attr(callee, "member_name") or ""
        if nm in ("require", "assert"):
            kids = n.get("children") or []
            cond = kids[1] if len(kids) > 1 else None  # [0]=callee, [1]=first arg
            req_guards.append((q.node_span(n), _idents_in(cond) if cond is not None else set()))
    results = []
    for a in nodes:
        if a.get("name") != "Assignment" or not own(a):
            continue
        kids = a.get("children") or []
        if not kids:
            continue
        lhs = kids[0]
        # TARGET: LHS must be an IndexAccess on a discovered state MAPPING.
        if lhs.get("name") != "IndexAccess":
            continue
        base = _base_name(lhs)
        if base not in mappings:
            continue
        if not _is_inflating_shape(a):
            continue
        if _rhs_is_safemath(a):
            continue
        a_sp = q.node_span(a)
        a_line = q.line_of(src, a_sp[0])
        guard = None
        # (a) ENCLOSING IfStatement whose condition references the same base var.
        #     Condition-aware (mirrors branch (b)): an UNRELATED enclosing `if`
        #     (e.g. `if (active) { balances[x] += d; }`, condition unrelated to the
        #     mapping) must NOT count as an overflow/bounds guard. [CORR-1]
        for g in ifs:
            g_sp = q.node_span(g)
            if q.contains(g_sp, a_sp) and g_sp != a_sp:
                cond = (g.get("children") or [None])[0]
                if cond is not None and base in _idents_in(cond):
                    guard = g
                    break
        # (b) prior IfStatement whose condition references the same base var
        if guard is None:
            for g in ifs:
                g_sp = q.node_span(g)
                if q.line_of(src, g_sp[0]) <= a_line:
                    cond = (g.get("children") or [None])[0]
                    if cond is not None and base in _idents_in(cond):
                        guard = g
                        break
        # (d) prior require()/assert() whose argument references the same base var
        if guard is None:
            for gsp, idents in req_guards:
                if gsp and q.line_of(src, gsp[0]) <= a_line and base in idents:
                    guard = ("require/assert", gsp)
                    break
        if guard is not None:
            continue  # CHECKED: do not flag
        results.append({
            "function": q.attr(fnode, "name"),
            "contract": owning_contract(fnode, nodes),
            "line": a_line,
            "operator": q.attr(a, "operator"),
            "snippet": q.snippet(src, a, 90),
            "base_var": base,
            "span": a_sp,
            "assignment": a,  # the Assignment node, for ABI-shape data-flow roles
        })
    return results


# ---------------------------------------------------------------------------
# Phase 3: SINK detection -- balance-gated ETH-out.
# ---------------------------------------------------------------------------

def _is_eth_send(call, src):
    """True iff a FunctionCall is a real low-level ETH egress:
       addr.send(x)            -> MemberAccess member_name=='send'
       addr.call.value(x)(...) -> member_name=='value' over a 'call' MemberAccess
    EXCLUDES token .transfer (super.transfer / ERC-20) and bare msg.value reads.
    Returns (kind:str|None, line, snippet)."""
    callee = (call.get("children") or [None])[0]
    if callee is None or callee.get("name") != "MemberAccess":
        return (None, None, None)
    member = q.attr(callee, "member_name")
    sp = q.node_span(callee)
    line = q.line_of(src, sp[0]) if sp else None
    if member == "send":
        return ("send", line, q.snippet(src, call, 90))
    if member == "value":
        # call.value(x) pattern: the base of this MemberAccess is itself a
        # MemberAccess with member_name 'call'.
        base = (callee.get("children") or [None])[0]
        if base is not None and base.get("name") == "MemberAccess" \
                and q.attr(base, "member_name") == "call":
            return ("call.value", line, q.snippet(src, call, 90))
    # .transfer over 'super'/token base and bare msg.value are NOT ETH-out.
    return (None, None, None)


def find_gated_eth_out(fnode, nodes, src, state_vars, mappings):
    """If a function impl has at least one ETH egress AND at least one
    balance-comparison gate over a state mapping keyed by msg.sender (with the
    gate preceding the send in source order), return a sink record; else None.

    All scans are bounded to this function's own span minus inner functions, so
    sinks/gates from sibling functions never leak in."""
    own = _own_span_test(fnode, nodes)

    # --- ETH egress sinks ---
    sinks = []
    for n in nodes:
        if n.get("name") != "FunctionCall" or not own(n):
            continue
        kind, line, snip = _is_eth_send(n, src)
        if kind:
            sinks.append({"kind": kind, "line": line, "snippet": snip,
                          "start": q.node_span(n)[0]})
    if not sinks:
        return None

    # --- balance-comparison gates over a state mapping keyed by msg.sender ---
    gates, gatevars, touched = [], set(), set()
    for n in nodes:
        if n.get("name") == "IndexAccess" and own(n):
            b = _base_name(n)
            if b in state_vars:
                touched.add(b)
    for n in nodes:
        if n.get("name") != "BinaryOperation" or not own(n):
            continue
        if q.attr(n, "operator") not in _CMP_OPS:
            continue
        kids = n.get("children") or []
        for operand in kids:
            if operand.get("name") != "IndexAccess":
                continue
            base = _base_name(operand)
            if base not in mappings:
                continue
            # index keyed by a caller-controlled key (msg.sender)?
            keyed_by_sender = any(
                m.get("name") == "MemberAccess"
                and q.attr(m, "member_name") == "sender"
                for m in q.flatten(operand))
            if not keyed_by_sender:
                continue
            gsp = q.node_span(n)
            gates.append({"line": q.line_of(src, gsp[0]),
                          "snippet": q.snippet(src, n, 70),
                          "operator": q.attr(n, "operator"),
                          "base_var": base, "start": gsp[0],
                          "node": n})  # the BinaryOperation, for ABI threshold orientation
            gatevars.add(base)
    if not gates:
        return None

    # ORDER: require some gate to precede some send (conservative reachability
    # proxy; the fork-proof is the real reachability oracle).
    first_send = min(s["start"] for s in sinks)
    ordered_gates = [g for g in gates if g["start"] <= first_send]
    if not ordered_gates:
        return None

    sink_sorted = sorted(sinks, key=lambda s: s["start"])
    gate_sorted = sorted(ordered_gates, key=lambda g: g["start"])
    # Index gates by their base var so the pairing can report the gate on the
    # SHARED variable (e.g. the balances gate), not merely the earliest gate.
    gates_by_var = {}
    for g in gate_sorted:
        gates_by_var.setdefault(g["base_var"], g)
    return {
        "function": q.attr(fnode, "name"),
        "contract": owning_contract(fnode, nodes),
        "eth_out": sink_sorted[0],
        "gate": gate_sorted[0],          # earliest gate on the path (fallback)
        "gates_by_var": gates_by_var,    # gate keyed by its base state var
        "gatevars": gatevars,
        "touched": touched,
    }


# ---------------------------------------------------------------------------
# Phase 3.5: ABI-shape derivation (Step 4 -- close AC-1). Derive the recovery
# ABI from the AST so the prover never ASSUMES (address,uint256) / balanceOf /
# zero-arg getters. Every sub-field that cannot be determined records an error
# and forces encodable=False (the prover then fails loud). All scope via
# byte-span containment; multi-dialect (0.3.x 'type' absent -> ElementaryTypeName
# / source-text; 0.4.x 'type'/'visibility' attrs present).
# ---------------------------------------------------------------------------

ABI_SHAPE_VERSION = 1


def abi_canon(sol_type):
    """CLOSED canonicalization: elementary Solidity type -> its ABI form, or None
    if NOT an ABI-encodable elementary type (struct/array/contract/enum/mapping/
    unknown alias). Returning None (never a raw pass-through) is what prevents a
    WRONG abi.encodeWithSignature selector from a type the prover can't encode."""
    if not sol_type:
        return None
    t = sol_type.strip()
    if t == "uint":
        return "uint256"
    if t == "int":
        return "int256"
    if t == "byte":
        return "bytes1"
    if t in ("address", "bool", "string", "bytes"):
        return t
    m = re.fullmatch(r"(uint|int)(\d+)", t)
    if m:
        n = int(m.group(2))
        return t if (8 <= n <= 256 and n % 8 == 0) else None
    m = re.fullmatch(r"bytes(\d+)", t)
    if m:
        n = int(m.group(1))
        return t if 1 <= n <= 32 else None
    return None


def _is_uint(canon):
    return bool(canon and re.fullmatch(r"uint\d+", canon))


def _elementary_type_in(span, nodes):
    """Type name of the FIRST ElementaryTypeName (by byte-span) inside `span`.
    Used for 0.3.x where VariableDeclaration carries no `type` attr. Byte-span
    containment (not .children) keeps a sibling decl -- nested as a descendant in
    the legacy AST -- from leaking in."""
    if not span:
        return None
    ets = [e for e in nodes if e.get("name") == "ElementaryTypeName"
           and q.contains(span, q.node_span(e))]
    if not ets:
        return None
    ets.sort(key=lambda e: q.node_span(e)[0])
    return q.attr(ets[0], "name") or q.attr(ets[0], "value")


def header_param_list_span(fnode, nodes):
    """Byte-span of a function's HEADER (argument) ParameterList = the FIRST
    ParameterList, in source order, whose span ends at/before the body Block
    start. Arguments precede the return list in source, so the first such PL is
    always the arg list; a zero-arg function still has an empty `()` PL (verified
    in BOTH dialects). Returns the span, or None if no PL precedes the body."""
    fsp = q.node_span(fnode)
    body = _body_block_span(fnode, nodes)
    pls = sorted(q.node_span(p) for p in nodes
                 if p.get("name") == "ParameterList"
                 and q.node_span(p) and q.contains(fsp, q.node_span(p)))
    if not pls:
        return None
    if body:
        for sp in pls:
            if sp[1] <= body[0]:
                return sp
    return pls[0]


def param_list(fnode, nodes, src):
    """Ordered external-ABI parameters of a function, by declaration order:
    [{name, abi_type, raw_type, index}]. abi_type is canonicalized (None if a
    param's type is unresolvable/non-elementary). Returns None if the header
    ParameterList cannot be isolated."""
    sp = header_param_list_span(fnode, nodes)
    if sp is None:
        return None
    vds = [v for v in nodes if v.get("name") == "VariableDeclaration"
           and q.contains(sp, q.node_span(v))]
    vds.sort(key=lambda v: q.node_span(v)[0])
    out = []
    for i, vd in enumerate(vds):
        raw = q.attr(vd, "type") or _elementary_type_in(q.node_span(vd), nodes)
        out.append({"name": q.attr(vd, "name"), "abi_type": abi_canon(raw),
                    "raw_type": raw, "index": i})
    return out


def state_var_decls(nodes):
    """{name: VariableDeclaration node} for contract-scope state vars (same
    ParameterList/Block exclusion as discover_state_vars). First decl wins."""
    pls = [sp for sp in (q.node_span(p) for p in nodes
                         if p.get("name") == "ParameterList") if sp]
    blks = [sp for sp in (q.node_span(b) for b in nodes
                          if b.get("name") == "Block") if sp]
    out = {}
    for n in nodes:
        if n.get("name") != "VariableDeclaration":
            continue
        name = q.attr(n, "name")
        sp = q.node_span(n)
        if not name or not sp:
            continue
        if any(q.contains(pl, sp) for pl in pls):
            continue
        if any(q.contains(bl, sp) for bl in blks):
            continue
        out.setdefault(name, n)
    return out


def state_var_public(vd, src, nodes):
    """Externally readable via an auto-getter? 0.4.x: `visibility` attr == public.
    0.3.x (no attr): scan the declaration's OWN byte-span for a `public` keyword
    (anchored so a sibling can't bleed in). INDETERMINATE -> NON-public (fail
    loud, never optimistic) -- the firewall-adjacent default-safe choice."""
    vis = q.attr(vd, "visibility")
    if vis is not None:
        return vis == "public"
    sp = q.node_span(vd)
    if not sp:
        return False
    # 0.3.x: scan the declaration's OWN span, but FIRST strip comments + string
    # literals so a `public` token inside `uint x /*public*/` or a string
    # initializer cannot false-positive an internal var to public. [AST-1]
    text = _strip_comments_strings(src[sp[0]:sp[1]].decode("utf-8", "replace"))
    return bool(re.search(r"\bpublic\b", text))


def _state_var_is_mapping(vd):
    return any(c.get("name") == "Mapping" for c in (vd.get("children") or []))


def state_var_scalar_type(vd, src, nodes):
    """Raw scalar type of a (non-mapping) state var. 0.4.x: `type` attr;
    0.3.x: contained ElementaryTypeName, else the leading source-text token."""
    t = q.attr(vd, "type")
    if t:
        return t
    et = _elementary_type_in(q.node_span(vd), nodes)
    if et:
        return et
    sp = q.node_span(vd)
    if sp:
        m = re.match(r"([A-Za-z_]\w*)", src[sp[0]:sp[1]].decode("utf-8", "replace").strip())
        if m:
            return m.group(1)
    return None


def mapping_kv(vd, src):
    """(key_type, value_type) of a mapping VariableDeclaration. Reads the `type`
    attr (0.4.x) else the declaration source text (0.3.x) -- NEVER the Mapping
    node's .children, which leak sibling decls in the legacy AST (verified: HONG
    balances' Mapping.children = ['address','uint256','allowed'])."""
    t = q.attr(vd, "type")
    if not t:
        sp = q.node_span(vd)
        t = src[sp[0]:sp[1]].decode("utf-8", "replace") if sp else ""
    m = re.search(r"mapping\s*\(\s*([A-Za-z0-9_]+)\s*=>\s*(.+)\)", t.strip())
    if not m:
        return (None, None)
    return (m.group(1).strip(), m.group(2).strip())


def resolve_balance_reader(shared_var, nodes, src, state_decls):
    """A live, single-address-arg getter returning shared_var[holder] at fork
    state. {kind:'explicit'|'mapping-getter'|None, sig, reads_var}. kind=None
    (fail loud) if neither a conforming explicit getter nor a public
    address->uint mapping auto-getter exists -- without it the prover can compute
    neither the amount nor the post-balance assertion."""
    for f in (fn for fn, hb in q.function_impls(nodes, src) if hb):
        if not is_public(f):
            continue
        params = param_list(f, nodes, src)
        if not params or len(params) != 1 or params[0]["abi_type"] != "address":
            continue
        own = _own_span_test(f, nodes)
        # read-only STRUCTURALLY (no Assignment in body) -- not via a keyword scan
        # that could match an interface stub line.
        if any(n.get("name") == "Assignment" and own(n) for n in nodes):
            continue
        rets = [r for r in nodes if r.get("name") == "Return" and own(r)]
        if len(rets) != 1:
            continue
        rk = rets[0].get("children") or []
        val = rk[0] if rk else None
        if val is None or val.get("name") != "IndexAccess" or _base_name(val) != shared_var:
            continue
        ik = val.get("children") or []
        idx = ik[1] if len(ik) > 1 else None
        if idx is None or idx.get("name") != "Identifier" \
                or q.attr(idx, "value") != params[0]["name"]:
            continue
        return {"kind": "explicit", "sig": f"{q.attr(f,'name')}(address)",
                "reads_var": shared_var}
    vd = state_decls.get(shared_var)
    if vd is not None and _state_var_is_mapping(vd) and state_var_public(vd, src, nodes):
        k, v = mapping_kv(vd, src)
        if abi_canon(k) == "address" and _is_uint(abi_canon(v)):
            return {"kind": "mapping-getter", "sig": f"{shared_var}(address)",
                    "reads_var": shared_var}
    return {"kind": None, "sig": None, "reads_var": shared_var}


def _derive_threshold(gate_node, shared_var, nodes, src, state_decls, errors):
    """How the prover reads the gate threshold T live + the gate operator
    NORMALIZED so the holder balance is the subject (so derive_target_policy
    stays correct regardless of which side the balance is written on)."""
    out = {"mode": None, "sig": None, "literal": None,
           "operator": None, "balance_side": None}
    if gate_node is None:
        errors.append("gate node unavailable for threshold derivation")
        return out
    kids = gate_node.get("children") or []
    if len(kids) != 2:
        errors.append("gate is not a binary comparison")
        return out
    op = q.attr(gate_node, "operator")
    lhs, rhs = kids[0], kids[1]

    def is_balance(o):
        return o.get("name") == "IndexAccess" and _base_name(o) == shared_var

    if is_balance(lhs) and not is_balance(rhs):
        out["balance_side"], thr = "lhs", rhs
    elif is_balance(rhs) and not is_balance(lhs):
        out["balance_side"], thr = "rhs", lhs
    else:
        errors.append("could not orient gate: neither/both operands are the shared-mapping balance")
        return out
    swap = {"<": ">", ">": "<", "<=": ">=", ">=": "<=", "==": "==", "!=": "!="}
    out["operator"] = op if out["balance_side"] == "lhs" else swap.get(op, op)
    if thr.get("name") == "Literal":
        # A subdenominated literal (`1 ether`, `100 finney`, `1 days`) has value='1'
        # but a scaled true value -- resolve it from the AST 'type' (= 'int_const N')
        # so the prover never emits the unscaled '1'. Fail loud if unresolvable. [PE-1]
        sub = q.attr(thr, "subdenomination")
        if sub:
            m = re.search(r"int_const\s+(-?\d+)", str(q.attr(thr, "type") or ""))
            if m:
                out["mode"], out["literal"] = "literal", m.group(1)
            else:
                errors.append(f"gate threshold literal uses an unresolved subdenomination {sub!r}")
            return out
        out["mode"], out["literal"] = "literal", str(q.attr(thr, "value"))
        return out
    if thr.get("name") == "Identifier":
        tname = q.attr(thr, "value")
        vd = state_decls.get(tname)
        if vd is None:
            errors.append(f"gate threshold {tname!r} is not a discovered state var")
            return out
        if _state_var_is_mapping(vd) or not _is_uint(abi_canon(state_var_scalar_type(vd, src, nodes))):
            errors.append(f"gate threshold {tname!r} is not a scalar uint state var")
            return out
        if not state_var_public(vd, src, nodes):
            errors.append(f"gate threshold {tname!r} is not public (no live getter)")
            return out
        out["mode"], out["sig"] = "getter", f"{tname}()"
        return out
    errors.append("gate threshold operand is a complex expression (not a literal or state-var getter)")
    return out


def derive_abi_shape(*, source_fnode, write_assignment, sink_fnode, gate_node,
                     auth, shared_var, nodes, src, state_decls):
    """Build the abi_shape block for one (write -> sink) hypothesis. Records an
    error (=> encodable=False) for every sub-field the prover cannot encode."""
    errors = []

    # --- write params + data-flow roles (holder = mapping KEY param; amount =
    #     the non-holder param flowing into the additive delta) ---
    write_name = q.attr(source_fnode, "name")
    wparams = param_list(source_fnode, nodes, src)
    holder_index = amount_index = None
    params_out = []
    if wparams is None:
        errors.append("write function header ParameterList could not be isolated")
    else:
        kids = (write_assignment.get("children") or []) if write_assignment else []
        lhs = kids[0] if kids else None
        key_name = None
        if lhs is not None and lhs.get("name") == "IndexAccess":
            ik = lhs.get("children") or []
            keyn = ik[1] if len(ik) > 1 else None
            if keyn is not None and keyn.get("name") == "Identifier":
                key_name = q.attr(keyn, "value")
        rhs = kids[1] if len(kids) > 1 else None
        rhs_idents = _idents_in(rhs) if rhs is not None else set()
        if key_name is None:
            errors.append("inflated-write key is msg.sender/constant/complex, not a passable holder param")
        else:
            m = [p["index"] for p in wparams if p["name"] == key_name]
            if len(m) == 1:
                holder_index = m[0]
            else:
                errors.append(f"holder param ambiguous/absent (key {key_name!r} matches {len(m)} params)")
        amt = [p["index"] for p in wparams
               if p["name"] in rhs_idents and p["index"] != holder_index]
        if len(amt) == 1:
            amount_index = amt[0]
        else:
            errors.append(f"amount param ambiguous/absent (delta references {len(amt)} non-holder params)")
        for p in wparams:
            role = ("holder" if p["index"] == holder_index else
                    "amount" if p["index"] == amount_index else "other")
            params_out.append({"name": p["name"], "abi_type": p["abi_type"],
                               "index": p["index"], "role": role})
            if p["abi_type"] is None:
                errors.append(f"write param {p['name']!r} type {p['raw_type']!r} is not ABI-encodable")
            elif role == "other":
                errors.append(f"write param {p['name']!r} ({p['abi_type']}) is neither holder nor amount and cannot be synthesized")
        # FP-1: the prover models post-balance = bal0 + amount via a single
        # write(holder, amount). For the unchecked-additive (+=) class the RHS
        # delta must therefore be a BARE reference to the amount param -- any extra
        # term (the holder, a cast, a second var, a multiplier) would land the
        # balance OFF the derived target. Reject at the gate, not at forge.
        if amount_index is not None and q.attr(write_assignment, "operator") == "+=":
            amt_name = next((p["name"] for p in wparams if p["index"] == amount_index), None)
            if not (rhs is not None and rhs.get("name") == "Identifier"
                    and q.attr(rhs, "value") == amt_name):
                errors.append(f"write delta is not a bare additive of {amt_name!r} "
                              f"(prover models post-balance = bal0 + amount)")
    write_sig = None
    if wparams is not None and all(p["abi_type"] for p in wparams):
        write_sig = f"{write_name}(" + ",".join(p["abi_type"] for p in wparams) + ")"
    write = {"name": write_name, "sig": write_sig, "params": params_out,
             "holder_index": holder_index, "amount_index": amount_index}

    # --- sink (zero-arg only) ---
    sink_name = q.attr(sink_fnode, "name")
    sparams = param_list(sink_fnode, nodes, src)
    if sparams is None:
        arg_count, sink_sig = None, None
        errors.append("sink function header ParameterList could not be isolated")
    else:
        arg_count, sink_sig = len(sparams), f"{sink_name}()"
        if arg_count != 0:
            errors.append(f"sink {sink_name} takes {arg_count} arg(s); this prover only proves zero-arg sinks")
    sink = {"name": sink_name, "sig": sink_sig, "arg_count": arg_count}

    # --- balance reader ---
    balance_reader = resolve_balance_reader(shared_var, nodes, src, state_decls)
    if balance_reader["kind"] is None:
        errors.append(f"no live balance reader for state var {shared_var!r} "
                      f"(no public single-address getter and not a public address->uint mapping)")

    # --- threshold ---
    threshold = _derive_threshold(gate_node, shared_var, nodes, src, state_decls, errors)

    # --- authority (only signer-gated; TIGHTENS the firewall, never loosens) ---
    authority = {"mode": None, "sig": None}
    if auth.get("kind") == "signer-gated":
        principal = auth.get("principal")
        vd = state_decls.get(principal) if principal else None
        if (vd is not None and state_var_public(vd, src, nodes)
                and not _state_var_is_mapping(vd)
                and abi_canon(state_var_scalar_type(vd, src, nodes)) == "address"):
            authority = {"mode": "getter", "sig": f"{principal}()"}
        else:
            errors.append(f"write authority {principal!r} is not a live-readable public scalar address getter")

    # --- shared mapping is address-keyed ---
    vd = state_decls.get(shared_var)
    mapping_addr_keyed = False
    if vd is not None:
        k, v = mapping_kv(vd, src)
        mapping_addr_keyed = (abi_canon(k) == "address" and _is_uint(abi_canon(v)))
    if not mapping_addr_keyed:
        errors.append(f"shared mapping {shared_var!r} is not address-keyed mapping(address=>uint)")

    return {"version": ABI_SHAPE_VERSION, "encodable": not errors, "errors": errors,
            "write": write, "sink": sink, "balance_reader": balance_reader,
            "threshold": threshold, "authority": authority,
            "mapping_addr_keyed": mapping_addr_keyed}


# ---------------------------------------------------------------------------
# Phase 4: pair, rank, emit.
# ---------------------------------------------------------------------------

def build_hypotheses(ast, src):
    nodes = q.flatten(ast)
    state_vars, mappings = discover_state_vars(nodes)
    state_decls = state_var_decls(nodes)
    mod_defs = _modifier_definitions(src)

    # Constructors are excluded: they cannot be invoked on a deployed instance, so
    # a constructor's unchecked mapping write is never a callable recovery lever. [AST-2]
    impls = [f for (f, has_body) in q.function_impls(nodes, src)
             if has_body and not _is_constructor(f, nodes)]

    # Collect SOURCES and SINKS over every impl independently (both transfer
    # impls are evaluated separately, attributed by innermost contract).
    sources, sinks = [], []
    for f in impls:
        for w in find_inflating_writes(f, nodes, src, mappings):
            w["_fnode"] = f
            w["auth"] = classify_authority(f, nodes, src, mod_defs)
            sources.append(w)
        sk = find_gated_eth_out(f, nodes, src, state_vars, mappings)
        if sk:
            sk["_fnode"] = f
            sk["auth"] = classify_authority(f, nodes, src, mod_defs)
            sinks.append(sk)

    # PAIR on a shared state mapping. Join key = the inflated base var; STRONG
    # when that var is itself the SINK's gate var (inflating it opens the exit).
    hyps = []
    for s in sources:
        for k in sinks:
            if s["function"] == k["function"]:
                continue
            if s["base_var"] not in k["touched"]:
                continue
            strong = s["base_var"] in k["gatevars"]
            # Report the gate on the SHARED variable when the sink gates on it
            # (the inflated var IS the lock); else fall back to the earliest gate.
            gate = k["gates_by_var"].get(s["base_var"], k["gate"])
            auth_label, tier, front_run = join_authority(s["auth"], k["auth"])
            # ABI shape derived from the AST (Step 4): the prover consumes this
            # instead of assuming (address,uint256)/balanceOf/zero-arg getters,
            # and FAILS LOUD when encodable is False.
            abi_shape = derive_abi_shape(
                source_fnode=s["_fnode"], write_assignment=s.get("assignment"),
                sink_fnode=k["_fnode"], gate_node=gate.get("node"),
                auth=s["auth"], shared_var=s["base_var"],
                nodes=nodes, src=src, state_decls=state_decls)
            # Confidence ranking: STRONG > weak; signer-gated source (a real
            # admin recovery lever) > anyone/holder source; externally callable
            # source > internal. createTokenProxy (internal, anyone) is thereby
            # ranked BELOW mgmtIssueBountyToken (signer-gated) and never
            # presented as THE recovery path.
            src_public = is_public(s["_fnode"])
            src_order = {"signer-gated": 2, "holder-gated": 1, "anyone": 0}[
                s["auth"]["kind"]]
            score = (10 if strong else 0) + 3 * src_order + (1 if src_public else 0)
            hyps.append({
                "path": f"{s['function']} -> {k['function']}",
                "strength": "strong" if strong else "weak",
                "shared_state_var": s["base_var"],
                "write_function": s["function"],
                "write_contract": s["contract"],
                "write_line": s["line"],
                "write_snippet": s["snippet"],
                "write_operator": s["operator"],
                "sink_function": k["function"],
                "sink_contract": k["contract"],
                "sink_line": k["eth_out"]["line"],
                "sink_snippet": k["eth_out"]["snippet"],
                "sink_kind": k["eth_out"]["kind"],
                "gate_line": gate["line"],
                "gate_snippet": gate["snippet"],
                "required_authority": auth_label,
                # Explicit machine fields for the prover (so it never parses the
                # human label): the SOURCE write's authority kind + the getter to
                # read the signer live. Getter is null unless signer-gated. [CORR-1]
                "write_authority_kind": s["auth"]["kind"],
                "write_authority_getter": (s["auth"]["principal"]
                                           if s["auth"]["kind"] == "signer-gated" else None),
                "write_modifiers": s["auth"]["modifiers"],
                "sink_modifiers": k["auth"]["modifiers"],
                "legal_tier": tier,
                "front_runnable": front_run,
                "source_visibility": "public" if src_public else "internal/private",
                "abi_shape": abi_shape,
                "_score": score,
                "verdict": ("HYPOTHESIS -- not a verdict; the Foundry fork-proof "
                            "test/HongUnlock.t.sol is the SOLE oracle"),
                "rationale": (
                    f"Unchecked inflating write `{s['snippet']}` (op "
                    f"{s['operator']}, L{s['line']}, no guard references base "
                    f"'{s['base_var']}') in {s['function']} can set the shared "
                    f"mapping '{s['base_var']}' that {k['function']} "
                    f"{'GATES on' if strong else 'reads'} at L{gate['line']} "
                    f"(`{gate['snippet']}`) before the ETH egress "
                    f"`{k['eth_out']['snippet']}` at L{k['eth_out']['line']}. "
                    f"Inflating the balance lets a caller pass the gate and reach "
                    f"the {k['eth_out']['kind']}. Authority to perform the write: "
                    f"{authority_string(s['auth'])}."),
                "next_action": (
                    f"Hand (inflate {s['function']}, exit {k['function']}) to "
                    f"test/HongUnlock.t.sol for fork-proof confirmation; do not "
                    f"assert as confirmed."),
            })

    hyps.sort(key=lambda h: h["_score"], reverse=True)
    for i, h in enumerate(hyps, 1):
        h["rank"] = i
        if i > 1:
            h["downrank_reason"] = (
                "lower confidence than the top hypothesis: weaker pairing and/or "
                "source is not a signer-gated, externally-callable admin lever "
                "(e.g. internal visibility / 'anyone' authority). Surfaced for "
                "completeness, NOT presented as the primary recovery path.")
    return hyps, {
        "state_vars": sorted(state_vars),
        "mappings": sorted(mappings),
        "n_sources": len(sources),
        "n_sinks": len(sinks),
        "sources": [f"{s['function']}@{s['line']}({s['base_var']})" for s in sources],
        "sinks": [f"{k['function']}@{k['eth_out']['line']}" for k in sinks],
    }


# ---------------------------------------------------------------------------
# CLI / reporting.
# ---------------------------------------------------------------------------

def _print_human(hyps, summary):
    print("=" * 78)
    print("WHITE-HAT RECOVERY-PATH DETECTOR  (HYPOTHESIS generator -- not a verdict)")
    print("The Foundry fork-proof test/HongUnlock.t.sol is the SOLE oracle.")
    print("=" * 78)
    print(f"State mappings discovered: {', '.join(summary['mappings'])}")
    print(f"Unchecked inflating writes: {summary['sources'] or 'none'}")
    print(f"Gated ETH-out sinks       : {summary['sinks'] or 'none'}")
    print(f"Recovery-path hypotheses  : {len(hyps)}")
    print("-" * 78)
    if not hyps:
        print("No (inflate -> gated-exit) recovery path found.")
        return
    for h in hyps:
        flag = ">>> PRIMARY" if h["rank"] == 1 else f"    #{h['rank']}"
        print(f"{flag}  [{h['strength'].upper()}]  {h['path']}")
        print(f"        shared state var : {h['shared_state_var']}")
        print(f"        inflating write  : L{h['write_line']} {h['write_snippet']}"
              f"  ({h['write_function']}, {h['source_visibility']},"
              f" modifiers={h['write_modifiers']})")
        print(f"        balance gate     : L{h['gate_line']} {h['gate_snippet']}")
        print(f"        ETH-out sink     : L{h['sink_line']} {h['sink_snippet']}"
              f"  (kind={h['sink_kind']})")
        print(f"        required_authority: {h['required_authority']}")
        print(f"        legal_tier       : {h['legal_tier']}"
              f"   front_runnable={h['front_runnable']}")
        if h["rank"] > 1:
            print(f"        downranked       : {h['downrank_reason']}")
        print(f"        verdict          : {h['verdict']}")
        print("-" * 78)


def _machine(h):
    """The required machine JSON object for one hypothesis (drops internals)."""
    return {
        "kind": "recovery-path-hypothesis",
        "rank": h["rank"],
        "strength": h["strength"],
        "confidence": "primary" if h["rank"] == 1 else "secondary",
        "path": h["path"],
        "shared_state_var": h["shared_state_var"],
        "write_function": h["write_function"],
        "write_contract": h["write_contract"],
        "write_line": h["write_line"],
        "write_snippet": h["write_snippet"],
        "write_operator": h["write_operator"],
        "sink_function": h["sink_function"],
        "sink_contract": h["sink_contract"],
        "sink_line": h["sink_line"],
        "sink_snippet": h["sink_snippet"],
        "sink_kind": h["sink_kind"],
        "gate_line": h["gate_line"],
        "gate_snippet": h["gate_snippet"],
        "required_authority": h["required_authority"],
        "write_authority_kind": h["write_authority_kind"],
        "write_authority_getter": h["write_authority_getter"],
        "write_modifiers": h["write_modifiers"],
        "sink_modifiers": h["sink_modifiers"],
        "legal_tier": h["legal_tier"],
        "front_runnable": h["front_runnable"],
        "source_visibility": h["source_visibility"],
        "abi_shape": h["abi_shape"],
        "verdict": h["verdict"],
        "rationale": h["rationale"],
        "next_action": h["next_action"],
        **({"downrank_reason": h["downrank_reason"]} if "downrank_reason" in h else {}),
    }


def main(argv):
    ast_path = argv[0] if len(argv) >= 1 else q.AST_PATH
    src_path = argv[1] if len(argv) >= 2 else q.SRC_PATH
    ast, src = q.load(ast_path, src_path)
    hyps, summary = build_hypotheses(ast, src)

    _print_human(hyps, summary)
    print("\n=== MACHINE JSON (one object per hypothesis) ===")
    print(json.dumps({
        "target": {"ast_file": ast_path, "src_file": src_path, "solc": "0.3.x"},
        "summary": summary,
        "hypotheses": [_machine(h) for h in hyps],
    }, indent=2))
    # Exit 0 always: the detector NOMINATES; it never decides a vuln is real.
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))