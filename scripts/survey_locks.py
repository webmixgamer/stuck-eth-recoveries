#!/usr/bin/env python3
"""Empirical lock-shape survey over the already-fetched ForgottenETH corpus.

Goal: before broadening the recovery class beyond HONG's `balances[msg.sender]`-
gated refund, SEE what actually gates the ETH-out functions of real stuck-ETH
contracts. For each in-scope target on disk it finds every ETH egress function
and reports: the function name, its authority (via the detector's firewall
classifier), the egress primitive, and the guard expressions (require/if/return
conditions) that precede the send -- i.e. the real "lock". Sorted by stuck ETH.

This is research instrumentation only -- it nominates SHAPES for the design, it
never claims a recovery. Reuses the detector's AST plumbing + classifiers.

Usage: python3 scripts/survey_locks.py [--reports docs/targets/scan_ico_token.json,docs/targets/scan_gambling.json]
"""
import argparse
import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import _ast_query as q          # noqa: E402
import detect_recovery_path as d  # noqa: E402

ROOT = os.path.dirname(_HERE)


def eth_egress_in(fnode, nodes, src):
    """Every ETH egress in a function's own span. Broader than the detector's
    sink finder: includes addr.transfer(x) (an ETH send in 0.4.x) in addition to
    .send / .call.value. Returns list of (kind, line, snippet)."""
    own = d._own_span_test(fnode, nodes)
    out = []
    for n in nodes:
        if n.get("name") != "FunctionCall" or not own(n):
            continue
        callee = (n.get("children") or [None])[0]
        if callee is None or callee.get("name") != "MemberAccess":
            continue
        member = q.attr(callee, "member_name")
        sp = q.node_span(callee)
        line = q.line_of(src, sp[0]) if sp else None
        if member in ("send", "transfer"):
            # exclude token .transfer over super/this; keep address-typed sends.
            base = (callee.get("children") or [None])[0]
            base_txt = q.snippet(src, base, 40) if base is not None else ""
            if member == "transfer" and ("super" in base_txt or base_txt.strip().startswith("token")):
                continue
            out.append((member, line, q.snippet(src, n, 80)))
        elif member == "value":
            base = (callee.get("children") or [None])[0]
            if base is not None and base.get("name") == "MemberAccess" \
                    and q.attr(base, "member_name") == "call":
                out.append(("call.value", line, q.snippet(src, n, 80)))
    return out


def guards_in(fnode, nodes, src):
    """require()/assert() arg snippets + if/return condition snippets in the
    function's own span -- the candidate 'lock' conditions before any send."""
    own = d._own_span_test(fnode, nodes)
    guards = []
    for n in nodes:
        if not own(n):
            continue
        nm = n.get("name")
        if nm == "FunctionCall":
            callee = (n.get("children") or [None])[0]
            cn = q.attr(callee, "value") or q.attr(callee, "member_name") or ""
            if cn in ("require", "assert"):
                kids = n.get("children") or []
                if len(kids) > 1:
                    guards.append(("require", q.snippet(src, kids[1], 70)))
        elif nm == "IfStatement":
            cond = (n.get("children") or [None])[0]
            if cond is not None:
                guards.append(("if", q.snippet(src, cond, 70)))
    return guards


def survey_one(ast_path, sol_path):
    ast, src = q.load(ast_path, sol_path)
    nodes = q.flatten(ast)
    mod_defs = d._modifier_definitions(src)
    funcs = []
    for f, has_body in q.function_impls(nodes, src):
        if not has_body or d._is_constructor(f, nodes):
            continue
        egress = eth_egress_in(f, nodes, src)
        if not egress:
            continue
        auth = d.classify_authority(f, nodes, src, mod_defs)
        funcs.append({
            "function": q.attr(f, "name"),
            "public": d.is_public(f),
            "authority_kind": auth["kind"],
            "modifiers": auth["modifiers"],
            "egress": egress,
            "guards": guards_in(f, nodes, src),
        })
    return funcs


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--reports", default="docs/targets/scan_ico_token.json,docs/targets/scan_gambling.json")
    ap.add_argument("--min-eth", type=float, default=0.0)
    args = ap.parse_args(argv)

    def sanitize(k):
        return "".join(c if c.isalnum() else "_" for c in k)[:40]

    seen, rows = set(), []
    for rp in args.reports.split(","):
        rp = rp.strip()
        if not os.path.exists(os.path.join(ROOT, rp)):
            continue
        for r in json.load(open(os.path.join(ROOT, rp))):
            if not r.get("fetched"):
                continue
            name = sanitize(r.get("key") or r.get("name") or "Target")
            if name in seen:
                continue
            seen.add(name)
            ast = os.path.join(ROOT, "docs", "targets", f"{name}.ast.json")
            sol = os.path.join(ROOT, "docs", "targets", f"{name}.sol")
            if not os.path.exists(ast):
                continue
            wei = r.get("balance_wei") or 0
            eth = wei / 1e18
            if eth < args.min_eth:
                continue
            try:
                funcs = survey_one(ast, sol)
            except Exception as e:
                rows.append((eth, r.get("name"), name, f"[survey error: {e}]"))
                continue
            if funcs:
                rows.append((eth, r.get("name"), name, funcs))

    rows.sort(key=lambda x: -x[0])
    print(f"ETH-out functions across in-scope corpus (>= {args.min_eth} ETH), by stuck ETH:\n")
    for eth, disp, name, funcs in rows:
        print(f"{'='*72}\n{disp}  [{name}]  {eth:.3f} ETH")
        if isinstance(funcs, str):
            print(f"  {funcs}")
            continue
        for fn in funcs:
            vis = "public" if fn["public"] else "internal"
            print(f"  fn {fn['function']}()  [{vis}, auth={fn['authority_kind']}, mods={fn['modifiers']}]")
            for kind, line, snip in fn["egress"]:
                print(f"      EGRESS {kind} @L{line}: {snip}")
            for gk, gs in fn["guards"][:6]:
                print(f"      guard[{gk}]: {gs}")
    print(f"\n{len(rows)} contracts with >=1 ETH-out function.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
