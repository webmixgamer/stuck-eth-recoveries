#!/usr/bin/env python3
"""Safety gate for a recovery target — is the recovery genuine and trap-free?

Codifies the Ahoolee due-diligence into repeatable, deterministic checks so no
target is ever recommended on the happy path alone. For a contract + its AST it
reports:

  1. BYTECODE opcode audit (eth_getCode): DELEGATECALL/CALLCODE (=> proxy/upgradeable),
     SELFDESTRUCT (=> destructible), CREATE/CREATE2. Absence => code is immutable
     and is exactly what we analyzed.
  2. ETH-OUT SURFACE (from the AST): every function that can move ETH, its authority
     (the detector's firewall classifier), egress primitive, and its modifiers
     (so time-bounds like onlyAfter/onlyBefore are visible). Tells you the ONLY ways
     value can leave + who can trigger them.
  3. DRAIN HISTORY (Etherscan internal txs): when ETH last left, to whom, how much —
     so an active drain or a recent owner-sweep is caught.
  4. (optional) REFUND-ATTEMPT analysis (--refund-sig): scan the contract's full tx
     list for calls to the recovery selector and tally success vs revert, per address
     — the empirical "is the refund actually open / did claimants fail?" check.

Verdict is advisory; it never asserts a recovery is safe by itself — it surfaces
what a human/the fork-proof must still confirm. Read-only.

Usage:
  python3 scripts/safety_check.py --contract 0x.. --ast docs/targets/X.ast.json \
      --src docs/targets/X.sol --name X [--refund-sig 'refund()']
"""
import argparse
import json
import os
import subprocess
import sys
import urllib.request

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import _ast_query as q            # noqa: E402
import detect_recovery_path as d  # noqa: E402
import survey_locks as sl         # noqa: E402

ROOT = os.path.dirname(_HERE)


def env(k):
    v = os.environ.get(k)
    if v:
        return v
    for line in open(os.path.join(ROOT, ".env")):
        line = line.strip()
        if line and not line.startswith("#") and line.split("=", 1)[0] == k:
            return line.split("=", 1)[1]
    return None


def rpc(method, params, url):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=30).read()).get("result")


def opcode_scan(code_hex):
    b = bytes.fromhex(code_hex[2:] if code_hex.startswith("0x") else code_hex)
    danger = {0xf4: "DELEGATECALL", 0xf2: "CALLCODE", 0xff: "SELFDESTRUCT",
              0xf0: "CREATE", 0xf5: "CREATE2"}
    found, i = {}, 0
    while i < len(b):
        op = b[i]
        if 0x60 <= op <= 0x7f:          # PUSH1..32 -> skip immediate data
            i += 1 + (op - 0x5f); continue
        if op in danger:
            found[danger[op]] = found.get(danger[op], 0) + 1
        i += 1
    return found


def eth_out_surface(ast, src):
    nodes = q.flatten(ast)
    mod_defs = d._modifier_definitions(src)
    out = []
    for f, hb in q.function_impls(nodes, src):
        if not hb or d._is_constructor(f, nodes):
            continue
        egress = sl.eth_egress_in(f, nodes, src)
        if not egress:
            continue
        auth = d.classify_authority(f, nodes, src, mod_defs)
        out.append({"fn": q.attr(f, "name"), "public": d.is_public(f),
                    "authority": auth["kind"], "modifiers": auth["modifiers"],
                    "egress": [(k, ln) for k, ln, _ in egress]})
    return out


def drain_history(contract, key):
    url = (f"https://api.etherscan.io/v2/api?chainid=1&module=account&action=txlistinternal"
           f"&address={contract}&startblock=0&endblock=99999999&page=1&offset=50&sort=desc&apikey={key}")
    res = json.loads(urllib.request.urlopen(url, timeout=30).read()).get("result", [])
    outs = [t for t in res if t.get("from", "").lower() == contract.lower()
            and int(t.get("value", "0")) > 0]
    return outs


def refund_attempts(contract, selector, key):
    """Scan the contract's full tx list for calls to `selector`; tally per-address
    success/revert. selector = 4-byte hex like '0x590e1ae3'."""
    cache = f"/tmp/safety_tx_{contract.lower()}.json"
    if not os.path.exists(cache):
        url = (f"https://api.etherscan.io/v2/api?chainid=1&module=account&action=txlist"
               f"&address={contract}&startblock=0&endblock=99999999&sort=asc&apikey={key}")
        urllib.request.urlretrieve(url, cache)
    txs = json.load(open(cache)).get("result", [])
    ok, fail = {}, {}
    for t in txs:
        if t.get("to", "").lower() == contract.lower() and (t.get("input") or "").startswith(selector):
            a = t["from"].lower()
            (fail if t.get("isError") == "1" else ok)[a] = (fail if t.get("isError") == "1" else ok).get(a, 0) + 1
    return ok, fail


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--contract", required=True)
    ap.add_argument("--ast", required=True)
    ap.add_argument("--src", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--refund-sig", help="recovery method to audit attempts for, e.g. 'refund()'")
    args = ap.parse_args(argv)

    url = env("ALCHEMY_RPC_URL")
    key = env("ETHERSCAN_API_KEY")
    C = args.contract
    ast, srcb = q.load(os.path.join(ROOT, args.ast), os.path.join(ROOT, args.src))

    code = rpc("eth_getCode", [C, "latest"], url)
    ops = opcode_scan(code)
    surface = eth_out_surface(ast, srcb)
    outs = drain_history(C, key)
    bal = int(rpc("eth_getBalance", [C, "latest"], url), 16)

    lines = [f"# Safety check — {args.name}  ({C})", "",
             f"Live balance: **{bal/1e18:.4f} ETH**  |  bytecode {len(code)//2-1} bytes", "",
             "## 1. Bytecode opcode audit",
             f"- Dangerous opcodes: **{ops or 'NONE'}**",
             f"  - upgradeable (DELEGATECALL/CALLCODE): **{'YES — REVIEW' if ('DELEGATECALL' in ops or 'CALLCODE' in ops) else 'no'}**",
             f"  - self-destructible (SELFDESTRUCT): **{'YES — REVIEW' if 'SELFDESTRUCT' in ops else 'no'}**",
             "", "## 2. ETH-out surface (the ONLY ways value can leave)"]
    for s in surface:
        lines.append(f"- `{s['fn']}()` — auth=**{s['authority']}**, "
                     f"{'public' if s['public'] else 'internal'}, modifiers={s['modifiers']}, "
                     f"egress={s['egress']}")
    lines += ["", "## 3. Drain history (ETH out of contract)"]
    if outs:
        last = outs[0]
        lines.append(f"- Last ETH-out: block {last['blockNumber']} (ts {last['timeStamp']}), "
                     f"{int(last['value'])/1e18:.4f} ETH to {last['to']}")
        lines.append(f"- Recent outflows shown: {len(outs)} (newest first)")
    else:
        lines.append("- No ETH has ever left via internal calls.")

    if args.refund_sig:
        sel = subprocess.run(["cast", "sig", args.refund_sig], capture_output=True, text=True).stdout.strip()
        ok, fail = refund_attempts(C, sel, key)
        lines += ["", f"## 4. Recovery-attempt analysis (`{args.refund_sig}` = {sel})",
                  f"- Addresses that called it and **SUCCEEDED**: {len(ok)}",
                  f"- Addresses that called it and **REVERTED**: {len(fail)}"]
        if fail:
            lines.append(f"  - reverted callers (investigate): {list(fail)[:20]}")
        else:
            lines.append("  - **No failed attempts** — nobody who tried was blocked.")
        # stash for the caller to cross-ref with unclaimed
        json.dump({"ok": ok, "fail": fail},
                  open(os.path.join(ROOT, "docs", "targets", f"attempts_{args.name}.json"), "w"), indent=2)

    report = "\n".join(lines) + "\n"
    open(os.path.join(ROOT, "docs", "targets", f"SAFETY_{args.name}.md"), "w").write(report)
    print(report)
    print(f"-> docs/targets/SAFETY_{args.name}.md")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
