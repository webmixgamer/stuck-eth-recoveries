#!/usr/bin/env python3
"""Open-refund recovery-class detector (Lane-A, task #5).

WHAT THIS IS (and is NOT)
-------------------------
A ZERO-pointing detector for the BROADENED recovery class proven on Ahoolee +
jincor: an *intended* per-contributor refund path left permanently OPEN and never
taken. Unlike the HONG inflate->gated-exit class (detect_recovery_path.py) there
is NO bug and NO inflating write -- the rightful contributor simply reclaims their
OWN deposit via the function the authors shipped. That is the cleanest possible
white-hat case, and the structural signature is what makes it LOW legal tier:

    a public/external function whose ETH egress pays `msg.sender`
    an amount that is the caller's OWN per-address ledger entry  ledger[msg.sender]

Because the recipient is the caller and the amount is the caller's own recorded
deposit, the path is NOT front-runnable (a third party can never redirect someone
else's refund) => LOW tier, owner-signs, no-custody firewall holds. This is the
DEFAULT-SAFE gate: a refund that pays a *param*/beneficiary/`owner`, or whose
amount is not the caller's own ledger, is REJECTED (it could be a drain), never
silently classified LOW.

HARD INVARIANTS (never violated here):
  * The detector emits a HYPOTHESIS, never a verdict. A Foundry mainnet-fork test
    that PRANKS a real unclaimed owner and watches refund() pay them is the SOLE
    oracle that the path is live + open (see test/AhooleeRefund.t.sol). "Openness"
    (is the cap flag false / is state==Refunding right now) is a LIVE property the
    fork proves by the refund() call SUCCEEDING; the detector only NOMINATES the
    gates a human/triage should read, it never asserts the contract is open.
  * Idempotence is a safety signal: a refund with NO single-claim mechanism
    (neither zeroing ledger[msg.sender] nor setting a refunded[msg.sender] flag)
    is repeatable => a DRAIN, not a clean refund => `idempotent=False` and the
    record is flagged unsafe (NOT presented as a clean LOW recovery).

DESIGN: reuses detect_recovery_path's AST plumbing wholesale (byte-span scope,
runtime state-var/mapping discovery, is_public, the firewall classifier, the
single-address balance-reader resolver, param_list). Multi-dialect via the same
mechanisms. No third-party deps.

Usage:
    python3 scripts/detect_open_refund.py <ast.json> <src.sol>
Exit 0 always (the detector nominates; it never decides a recovery is real).
"""
import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
import _ast_query as q  # noqa: E402
import detect_recovery_path as d  # noqa: E402

OPEN_REFUND_VERSION = 1


# ---------------------------------------------------------------------------
# Small structural helpers (all scope via byte-span containment, like the
# HONG detector -- sibling declarations nest as descendants in legacy ASTs).
# ---------------------------------------------------------------------------

def _is_msg_sender(node):
    """True iff `node` is the expression `msg.sender` (a MemberAccess member
    'sender' over Identifier 'msg')."""
    if node is None or node.get("name") != "MemberAccess":
        return False
    if q.attr(node, "member_name") != "sender":
        return False
    base = (node.get("children") or [None])[0]
    return base is not None and base.get("name") == "Identifier" \
        and q.attr(base, "value") == "msg"


def _index_key(idx):
    """children[1] (the key expression) of an IndexAccess, else None."""
    kids = idx.get("children") or []
    return kids[1] if len(kids) > 1 else None


def _is_ledger_of_sender(node, mappings):
    """True iff `node` is `M[msg.sender]` for a discovered state mapping M.
    Returns the base var name M (or None)."""
    if node is None or node.get("name") != "IndexAccess":
        return None
    base = d._base_name(node)
    if base not in mappings:
        return None
    return base if _is_msg_sender(_index_key(node)) else None


def _eth_sends_to_sender(fnode, nodes, src):
    """Every ETH egress in the function's own span whose RECIPIENT is msg.sender.
    Returns list of {kind, amount_node, line, snippet}. Covers the universal
    pre-0.8 primitives plus addr.transfer(x) (an ETH send in 0.4.x):
        msg.sender.send(x) / msg.sender.transfer(x) / msg.sender.call.value(x)()
    The recipient is the base of the .send/.transfer/.call MemberAccess; we keep
    only those whose base is msg.sender (token .transfer over super/this is thereby
    excluded, as is any pay-to-beneficiary egress)."""
    own = d._own_span_test(fnode, nodes)
    out = []
    for n in nodes:
        if n.get("name") != "FunctionCall" or not own(n):
            continue
        callee = (n.get("children") or [None])[0]
        if callee is None or callee.get("name") != "MemberAccess":
            continue
        member = q.attr(callee, "member_name")
        args = (n.get("children") or [])[1:]
        sp = q.node_span(callee)
        line = q.line_of(src, sp[0]) if sp else None
        if member in ("send", "transfer"):
            recipient = (callee.get("children") or [None])[0]
            if not _is_msg_sender(recipient):
                continue
            amount = args[0] if args else None
            out.append({"kind": member, "amount_node": amount, "line": line,
                        "snippet": q.snippet(src, n, 80)})
        elif member == "value":
            # call.value(x)(...): base of this MemberAccess is a 'call' MemberAccess
            # whose own base is the recipient.
            call_ma = (callee.get("children") or [None])[0]
            if call_ma is None or call_ma.get("name") != "MemberAccess" \
                    or q.attr(call_ma, "member_name") != "call":
                continue
            recipient = (call_ma.get("children") or [None])[0]
            if not _is_msg_sender(recipient):
                continue
            amount = args[0] if args else None
            out.append({"kind": "call.value", "amount_node": amount, "line": line,
                        "snippet": q.snippet(src, n, 80)})
    return out


def _local_ledger_bindings(fnode, nodes, src, mappings):
    """{local_name: ledger_var} for own-span statements that bind a local to
    `ledger[msg.sender]` -- both `uint v = ledger[msg.sender];` (a
    VariableDeclaration[Statement] with an IndexAccess initializer) and
    `v = ledger[msg.sender];` (an Assignment). Lets the amount-resolution follow
    one hop of data-flow from a local back to the caller's ledger entry."""
    own = d._own_span_test(fnode, nodes)
    out = {}
    # Assignments: lhs Identifier <- rhs ledger[msg.sender]
    for a in nodes:
        if a.get("name") != "Assignment" or not own(a):
            continue
        if q.attr(a, "operator") != "=":
            continue
        kids = a.get("children") or []
        if len(kids) < 2:
            continue
        lhs, rhs = kids[0], kids[1]
        if lhs.get("name") != "Identifier":
            continue
        led = _is_ledger_of_sender(rhs, mappings)
        if led:
            out[q.attr(lhs, "value")] = led
    # Variable declarations with an initializer: name <- ledger[msg.sender].
    # 0.4.x: VariableDeclarationStatement [VariableDeclaration, <init>]; the init
    # is the IndexAccess. We pair a VariableDeclaration with an IndexAccess that
    # is its sibling initializer (immediately following, same statement span).
    for vds in nodes:
        if vds.get("name") not in ("VariableDeclarationStatement", "VariableDefinitionStatement"):
            continue
        if not own(vds):
            continue
        decl = None
        init = None
        for c in vds.get("children") or []:
            if c.get("name") == "VariableDeclaration" and decl is None:
                decl = c
            elif c.get("name") == "IndexAccess" and init is None:
                init = c
        if decl is not None and init is not None:
            led = _is_ledger_of_sender(init, mappings)
            if led:
                out[q.attr(decl, "name")] = led
    return out


def _resolve_amount_ledger(amount_node, bindings, mappings):
    """Ledger var M iff the send amount is the caller's OWN ledger entry --
    directly `M[msg.sender]` or a local bound to it. None otherwise (=> the egress
    is not a self-refund and the function is rejected, default-safe)."""
    if amount_node is None:
        return None
    led = _is_ledger_of_sender(amount_node, mappings)
    if led:
        return led
    if amount_node.get("name") == "Identifier":
        return bindings.get(q.attr(amount_node, "value"))
    return None


def _idempotence(fnode, nodes, src, ledger_var, mappings):
    """How a second refund() is prevented. Returns
    {idempotent, zeroed_on_refund, refunded_flag, enumerate_mode}.

      * zeroed_on_refund : own-span has `ledger[msg.sender] = 0` => unclaimed iff
                           ledger>0  (enumerate_mode='zeroed-on-refund').
      * refunded_flag    : a DIFFERENT mapping F (not the ledger) that is BOTH
                           read in a msg.sender-keyed guard AND written
                           `F[msg.sender] = <truthy>` => unclaimed iff
                           ledger>0 AND not in the Refunded log
                           (enumerate_mode='refunded-by-logs').
      * neither          : refund is REPEATABLE => a drain => idempotent=False
                           (flagged unsafe; never a clean LOW recovery)."""
    own = d._own_span_test(fnode, nodes)
    zeroed = False
    written_sender_maps = set()
    for a in nodes:
        if a.get("name") != "Assignment" or not own(a):
            continue
        kids = a.get("children") or []
        if not kids:
            continue
        lhs = kids[0]
        led = _is_ledger_of_sender(lhs, mappings)
        if led == ledger_var:
            rhs = kids[1] if len(kids) > 1 else None
            if rhs is not None and rhs.get("name") == "Literal" \
                    and str(q.attr(rhs, "value")) == "0":
                zeroed = True
        else:
            m = _is_ledger_of_sender(lhs, mappings)  # any other M[msg.sender] write
            if m and m != ledger_var:
                written_sender_maps.add(m)
    # a refunded-style flag: a written msg.sender-keyed mapping also read in a guard.
    guard_read_maps = set()
    for n in nodes:
        if n.get("name") == "IndexAccess" and own(n):
            b = _is_ledger_of_sender(n, mappings)
            if b and b != ledger_var:
                guard_read_maps.add(b)
    refunded_flag = None
    for m in written_sender_maps:
        if m in guard_read_maps:
            refunded_flag = m
            break
    if zeroed:
        return {"idempotent": True, "zeroed_on_refund": True,
                "refunded_flag": None, "enumerate_mode": "zeroed-on-refund"}
    if refunded_flag:
        return {"idempotent": True, "zeroed_on_refund": False,
                "refunded_flag": refunded_flag, "enumerate_mode": "refunded-by-logs"}
    return {"idempotent": False, "zeroed_on_refund": False,
            "refunded_flag": None, "enumerate_mode": None}


def _openness_gates(fnode, nodes, src, ledger_var, refunded_flag, bindings,
                    mappings, state_decls):
    """The require()/assert() conditions in the refund's own span that are the
    'is this refund open?' preconditions -- i.e. NOT the eligibility guards that
    just identify a rightful, unclaimed caller, and NOT the egress wrapper.

    An eligibility/owner guard (skipped) references ONLY the caller's ledger, the
    refunded flag, or a local bound to the ledger (ledger[sender]>0, !refunded[
    sender], require(amount>0) where amount==ledger[sender]). `msg` is always
    present inside `[msg.sender]`, so it is stripped before this comparison. The
    egress wrapper `require(msg.sender.send(x))` is skipped structurally (it
    contains an ETH send to msg.sender). Everything else is an openness gate.

    Each kept gate is reported with its live-readability:
      reader_sig != None  => a public getter/state var the prover can read live
                             (a bool flag like softCapReached, a function like
                             softCapReached()/hasEnded(), or a state enum state()).
      reader_sig == None  => time/derived/complex; the fork-proof (refund()
                             succeeding) remains the real openness oracle.

    The detector NEVER asserts which value means 'open' -- it surfaces the gate;
    the fork test encodes the precondition and the refund() call proves it live."""
    own = d._own_span_test(fnode, nodes)
    eligibility = {ledger_var} | ({refunded_flag} if refunded_flag else set()) \
        | set(bindings) | {"msg"}
    gates = []
    for n in nodes:
        if n.get("name") != "FunctionCall" or not own(n):
            continue
        callee = (n.get("children") or [None])[0]
        nm = (q.attr(callee, "value") or q.attr(callee, "member_name") or "") if callee else ""
        if nm not in ("require", "assert"):
            continue
        kids = n.get("children") or []
        cond = kids[1] if len(kids) > 1 else None
        if cond is None:
            continue
        # egress-wrapper guard, e.g. require(msg.sender.send(refund)): skip.
        if _eth_sends_to_sender_in(cond, src):
            continue
        meaningful = d._idents_in(cond) - eligibility
        if not meaningful:
            continue  # pure eligibility/owner guard, not an openness gate
        gsp = q.node_span(n)
        gates.append({
            "snippet": q.snippet(src, cond, 90),
            "line": q.line_of(src, gsp[0]) if gsp else None,
            **_gate_reader(cond, nodes, src, state_decls),
        })
    return gates


def _eth_sends_to_sender_in(node, src):
    """True iff the subtree contains an ETH send/transfer/call.value to msg.sender
    (used to skip a `require(msg.sender.send(x))` egress wrapper)."""
    for n in q.flatten(node):
        if n.get("name") != "FunctionCall":
            continue
        callee = (n.get("children") or [None])[0]
        if callee is None or callee.get("name") != "MemberAccess":
            continue
        member = q.attr(callee, "member_name")
        if member in ("send", "transfer") and _is_msg_sender(
                (callee.get("children") or [None])[0]):
            return True
        if member == "value":
            cm = (callee.get("children") or [None])[0]
            if cm is not None and cm.get("name") == "MemberAccess" \
                    and q.attr(cm, "member_name") == "call" \
                    and _is_msg_sender((cm.get("children") or [None])[0]):
                return True
    return False


def _gate_reader(cond, nodes, src, state_decls):
    """Classify a gate condition's live-readability. Returns
    {reader_sig, reader_kind, references}. Recognizes:
      * public bool/uint scalar state var  -> auto-getter `name()`
      * public state enum compared to a member -> `state()` (uint8)
      * a same-contract public view function call -> that call's sig
    Default: reader_sig=None (informational; fork-proof is the oracle)."""
    refs = sorted(d._idents_in(cond))
    # a function call in the condition (e.g. softCapReached(), hasEnded())?
    for n in q.flatten(cond):
        if n.get("name") == "FunctionCall":
            callee = (n.get("children") or [None])[0]
            fn = q.attr(callee, "value") if callee else None
            if fn and _is_public_view_fn(fn, nodes, src):
                return {"reader_sig": f"{fn}()", "reader_kind": "view-fn",
                        "references": refs}
    # a public scalar state var (bool flag, uint) read directly?
    for name in refs:
        vd = state_decls.get(name)
        if vd is None or d._state_var_is_mapping(vd):
            continue
        if not d.state_var_public(vd, src, nodes):
            continue
        t = d.abi_canon(d.state_var_scalar_type(vd, src, nodes))
        if t in ("bool",) or d._is_uint(t):
            return {"reader_sig": f"{name}()", "reader_kind": "state-var",
                    "references": refs}
        # an enum-typed state var (non-elementary => abi_canon None) read as state.
        return {"reader_sig": f"{name}()", "reader_kind": "state-enum",
                "references": refs}
    return {"reader_sig": None, "reader_kind": "derived/time/complex",
            "references": refs}


def _is_public_view_fn(name, nodes, src):
    """True iff `name` is a same-contract public/external function with no
    Assignment in its body (a live, side-effect-free reader the prover can call)."""
    for f, hb in q.function_impls(nodes, src):
        if not hb or q.attr(f, "name") != name or not d.is_public(f):
            continue
        own = d._own_span_test(f, nodes)
        if any(n.get("name") == "Assignment" and own(n) for n in nodes):
            return False
        return True
    return False


def _contract_node_of(fnode, nodes):
    """Innermost Contract NODE whose byte-span contains the function."""
    fsp = q.node_span(fnode)
    cands = [c for c in nodes if c.get("name") in q.CONTRACT_NAMES
             and q.node_span(c) and q.contains(q.node_span(c), fsp)]
    if not cands:
        return None
    return min(cands, key=lambda c: (q.node_span(c)[1] - q.node_span(c)[0]))


def _ledger_reader_scoped(ledger_var, refund_fnode, nodes, src):
    """A live ledger reader CALLABLE ON THE TARGET (refund's own) contract.

    CRITICAL: the reader sig is invoked on the target address by enumerate_owners
    and the fork-proof, so it must belong to the SAME contract as refund(). A
    same-named getter in a sibling contract (e.g. an ERC20 token's
    `balanceOf`->token `balances`, distinct from a crowdsale's deposit `balances`)
    would read the wrong storage / not exist on the target. We therefore:
      1) look for an explicit public single-address getter returning
         ledger[param] WITHIN refund()'s contract (Ahoolee saleBalanceOf,
         luckchemy depositOf);
      2) else fall back to the public mapping auto-getter `ledger(address)`,
         requiring the ledger var to be declared public IN THIS contract.
    Returns {sig, kind} (sig=None if neither is live-readable on the target)."""
    csp = q.node_span(_contract_node_of(refund_fnode, nodes))
    in_contract = (lambda n: csp and q.contains(csp, q.node_span(n)))

    # 1) explicit getter declared inside this contract
    for f, hb in q.function_impls(nodes, src):
        if not hb or not d.is_public(f) or not in_contract(f):
            continue
        params = d.param_list(f, nodes, src)
        if not params or len(params) != 1 or params[0]["abi_type"] != "address":
            continue
        own = d._own_span_test(f, nodes)
        if any(n.get("name") == "Assignment" and own(n) for n in nodes):
            continue
        rets = [r for r in nodes if r.get("name") == "Return" and own(r)]
        if len(rets) != 1:
            continue
        val = (rets[0].get("children") or [None])[0]
        if val is None or val.get("name") != "IndexAccess" \
                or d._base_name(val) != ledger_var:
            continue
        ik = val.get("children") or []
        idx = ik[1] if len(ik) > 1 else None
        if idx is None or idx.get("name") != "Identifier" \
                or q.attr(idx, "value") != params[0]["name"]:
            continue
        return {"sig": f"{q.attr(f, 'name')}(address)", "kind": "explicit"}

    # 2) public mapping auto-getter, ledger var declared public in THIS contract
    for n in nodes:
        if n.get("name") != "VariableDeclaration" or not in_contract(n):
            continue
        if q.attr(n, "name") != ledger_var or not d._state_var_is_mapping(n):
            continue
        if not d.state_var_public(n, src, nodes):
            continue
        k, v = d.mapping_kv(n, src)
        if d.abi_canon(k) == "address" and d._is_uint(d.abi_canon(v)):
            return {"sig": f"{ledger_var}(address)", "kind": "mapping-getter"}
    return {"sig": None, "kind": None}


# ---------------------------------------------------------------------------
# Top-level detection.
# ---------------------------------------------------------------------------

def detect_open_refund(ast, src):
    nodes = q.flatten(ast)
    state_vars, mappings = d.discover_state_vars(nodes)
    state_decls = d.state_var_decls(nodes)

    impls = [f for (f, hb) in q.function_impls(nodes, src)
             if hb and not d._is_constructor(f, nodes)]

    findings = []
    for f in impls:
        if not d.is_public(f):
            continue  # an open-refund must be externally callable by the owner
        sends = _eth_sends_to_sender(f, nodes, src)
        if not sends:
            continue
        bindings = _local_ledger_bindings(f, nodes, src, mappings)
        # Resolve each msg.sender-paying egress to the caller's own ledger entry.
        ledger_var = None
        matched_send = None
        for s in sends:
            led = _resolve_amount_ledger(s["amount_node"], bindings, mappings)
            if led:
                ledger_var, matched_send = led, s
                break
        if ledger_var is None:
            continue  # pays msg.sender but NOT from the caller's own ledger -> reject

        # zero-arg ABI shape (a self-refund takes no caller-supplied args)
        params = d.param_list(f, nodes, src)
        arg_count = len(params) if params is not None else None

        idem = _idempotence(f, nodes, src, ledger_var, mappings)
        gates = _openness_gates(f, nodes, src, ledger_var, idem["refunded_flag"],
                                bindings, mappings, state_decls)
        getter = _ledger_reader_scoped(ledger_var, f, nodes, src)
        auth = d.classify_authority(f, nodes, src, d._modifier_definitions(src))

        fname = q.attr(f, "name")
        # Legal classification: recipient == msg.sender AND amount ==
        # ledger[msg.sender] => self-paying => NOT front-runnable => LOW. This is
        # the whole point of the class. Idempotence must hold or it is a drain.
        clean = idem["idempotent"] and arg_count == 0 and getter["sig"] is not None
        findings.append({
            "kind": "open-refund-hypothesis",
            "contract": d.owning_contract(f, nodes),
            "refund_function": fname,
            "refund_sig": f"{fname}()" if arg_count == 0 else None,
            "arg_count": arg_count,
            "recipient": "msg.sender",
            "amount_source": f"{ledger_var}[msg.sender]",
            "egress_kind": matched_send["kind"],
            "egress_line": matched_send["line"],
            "egress_snippet": matched_send["snippet"],
            "ledger": {
                "var": ledger_var,
                "reader_sig": getter["sig"],
                "reader_kind": getter["kind"],
                "zeroed_on_refund": idem["zeroed_on_refund"],
                "refunded_flag": idem["refunded_flag"],
            },
            "enumerate_mode": idem["enumerate_mode"],
            "idempotent": idem["idempotent"],
            "openness_gates": gates,
            "required_authority": "the rightful contributor (msg.sender) signs",
            "write_modifiers": auth["modifiers"],
            "legal_tier": "LOW" if clean else "REVIEW",
            "front_runnable": False,
            "clean": clean,
            "verdict": ("HYPOTHESIS -- not a verdict. A Foundry fork-proof that "
                        "pranks a real unclaimed owner and watches refund() pay "
                        "them is the SOLE oracle (openness is proven by the call "
                        "succeeding)."),
            "safety_note": (None if idem["idempotent"] else
                            "NOT idempotent: refund has no single-claim guard "
                            "(no ledger zeroing, no refunded flag) => REPEATABLE "
                            "=> a DRAIN, not a clean refund. Flagged unsafe."),
            "next_action": (
                f"1) safety_check.py (mandatory); 2) enumerate_owners.py "
                f"--ledger '{getter['sig']}' --{idem['enumerate_mode']} ; "
                f"3) fork-prove a real unclaimed owner reclaiming via {fname}()."
                if clean else
                f"REVIEW: {fname} pays msg.sender from {ledger_var}[msg.sender] but "
                f"is not a clean LOW refund (see safety_note / arg_count / reader)."),
        })

    # Confidence ranking: clean self-refunds first, then by openness-gate count
    # (a gate we can read live is stronger triage than an opaque one).
    findings.sort(key=lambda h: (h["clean"], sum(
        1 for g in h["openness_gates"] if g["reader_sig"])), reverse=True)
    for i, h in enumerate(findings, 1):
        h["rank"] = i
    summary = {
        "state_mappings": sorted(mappings),
        "n_open_refunds": len(findings),
        "open_refunds": [f"{h['refund_function']}<-{h['ledger']['var']}[msg.sender]"
                         for h in findings],
    }
    return findings, summary


# ---------------------------------------------------------------------------
# CLI / reporting.
# ---------------------------------------------------------------------------

def _print_human(findings, summary):
    print("=" * 78)
    print("OPEN-REFUND DETECTOR  (HYPOTHESIS generator -- not a verdict)")
    print("The Foundry fork-proof (prank a real unclaimed owner) is the SOLE oracle.")
    print("=" * 78)
    print(f"State mappings discovered : {', '.join(summary['state_mappings']) or 'none'}")
    print(f"Open-refund candidates    : {summary['n_open_refunds']}")
    print("-" * 78)
    if not findings:
        print("No self-paying (pay msg.sender from ledger[msg.sender]) refund found.")
        return
    for h in findings:
        flag = ">>> PRIMARY" if h["rank"] == 1 else f"    #{h['rank']}"
        tag = "CLEAN-LOW" if h["clean"] else "REVIEW"
        print(f"{flag}  [{tag}]  {h['refund_function']}()  pays msg.sender "
              f"<- {h['amount_source']}")
        print(f"        egress      : L{h['egress_line']} {h['egress_snippet']}  ({h['egress_kind']})")
        print(f"        ledger      : {h['ledger']['var']}  reader={h['ledger']['reader_sig']} "
              f"({h['ledger']['reader_kind']})  zeroed={h['ledger']['zeroed_on_refund']} "
              f"refunded_flag={h['ledger']['refunded_flag']}")
        print(f"        idempotent  : {h['idempotent']}  enumerate_mode={h['enumerate_mode']}")
        print(f"        openness    : " + (", ".join(
            f"[{g['reader_sig'] or g['reader_kind']}] {g['snippet']}"
            for g in h["openness_gates"]) or "none found"))
        print(f"        authority   : {h['required_authority']}   tier={h['legal_tier']}"
              f"  front_runnable={h['front_runnable']}")
        if h["safety_note"]:
            print(f"        !! SAFETY   : {h['safety_note']}")
        print(f"        next        : {h['next_action']}")
        print("-" * 78)


def main(argv):
    if len(argv) < 2:
        print("usage: detect_open_refund.py <ast.json> <src.sol>", file=sys.stderr)
        return 2
    ast_path, src_path = argv[0], argv[1]
    ast, src = q.load(ast_path, src_path)
    findings, summary = detect_open_refund(ast, src)
    _print_human(findings, summary)
    print("\n=== MACHINE JSON ===")
    print(json.dumps({
        "version": OPEN_REFUND_VERSION,
        "target": {"ast_file": ast_path, "src_file": src_path},
        "summary": summary,
        "open_refunds": findings,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
