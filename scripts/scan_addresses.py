#!/usr/bin/env python3
"""Discovery driver: run the recovery engine over an ARBITRARY address list.

Sibling of `scan_forgotteneth.py`, but instead of the curated ForgottenETH
catalog it consumes a CSV of candidate contract addresses (DISCOVERY.md): the
free BigQuery `balances JOIN contracts` export of "contracts holding ETH". For
each address it runs the same Stage 1-2 funnel and emits a triage report:

    scripts/fetch_target.py        (Etherscan V2 verified source + legacy AST;
                                    fail-loud on unverified / multi-file / solc>0.4.26)
  then, on the survivors only (cheap -- most candidates die at fetch):
    scripts/detect_open_refund.py  (the broadened open-refund class -- the vein
                                    that yielded all 4 proven targets)
    scripts/detect_recovery_path.py(the HONG inflate -> balance-gated-exit class)
    + a dormancy signal (Etherscan txlist desc, 1 call / survivor)

It NEVER proves anything -- the Foundry fork-proof stays the SOLE oracle. A
survivor with a CLEAN-LOW open-refund hypothesis is nominated for the by-hand
tail (safety_check -> enumerate_owners -> fork-prove -> package), exactly as the
4 known targets were. Out-of-scope / off-class addresses are recorded with their
precise reason (an honest "nothing here" is a valid discovery outcome).

Cost: fetch_target makes 2 Etherscan calls/addr; the detectors + dormancy run
only on the verified-legacy survivors, so a 10k-row candidate list costs ~20k
free-tier Etherscan calls (well under the 100k/day cap) and trivial Alchemy.

Usage:
    # 1) get candidates (DISCOVERY.md): run the BigQuery query, export CSV.
    # 2) triage them:
    python3 scripts/scan_addresses.py --csv discovery_candidates.csv \
            [--limit N] [--min-eth 1.0] [--only-new] [--report docs/targets/discovery_report.json]
    # 3) survivors -> safety_check.py -> enumerate_owners.py -> fork-prove (by hand).
"""
import argparse
import csv
import json
import os
import subprocess
import sys
import time
import urllib.request

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from fetch_target import env_with_dotenv, es_get  # noqa: E402  (reuse the V2 client)

ROOT = os.path.dirname(_HERE)
TARGETS = os.path.join(ROOT, "docs", "targets")
# Same mirror scan_forgotteneth uses -- so we can tag/subtract the already-known set.
FETH_CATALOG_URL = "https://raw.githubusercontent.com/q84c6tsm95-create/forgotten-eth/HEAD/data/protocols.json"


def load_forgotteneth_addrs():
    """Lowercased set of the ~254 ForgottenETH contract addresses (cached in /tmp).
    Used to tag candidates as already-known so discovery focuses on NEW ones.
    Returns an empty set (with a warning) if the mirror is unreachable -- the
    subtraction is an optimization, never a correctness gate."""
    cache = "/tmp/feth_protocols.json"
    try:
        if not os.path.exists(cache):
            with urllib.request.urlopen(FETH_CATALOG_URL, timeout=30) as r:
                open(cache, "wb").write(r.read())
        cat = json.load(open(cache))
        return {(e.get("contract") or "").lower() for e in cat if e.get("contract")}
    except Exception as e:
        print(f"  (warn: could not load ForgottenETH catalog to subtract known set: {e})")
        return set()


def load_candidates(csv_path):
    """Parse the BigQuery export. Tolerant of column order / header naming:
    finds the first 0x-address column and an 'eth'/'balance' numeric column.
    Returns [{address, eth}] sorted by eth desc. Fail-loud on an empty/garbled file."""
    path = csv_path if os.path.isabs(csv_path) else os.path.join(ROOT, csv_path)
    if not os.path.exists(path):
        raise FileNotFoundError(f"candidate CSV not found: {path}")
    rows = []
    with open(path, newline="") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if header is None:
            raise ValueError(f"{csv_path} is empty")
        # locate columns
        def looks_addr(s):
            s = (s or "").strip()
            return s.startswith("0x") and len(s) == 42
        addr_col, eth_col = None, None
        hdr_l = [(h or "").strip().lower() for h in header]
        for i, h in enumerate(hdr_l):
            if h in ("address", "contract", "addr", "b_address"):
                addr_col = i
            if h in ("eth", "eth_balance", "balance", "balance_eth"):
                eth_col = i
        # header may itself be data (no header row) -> detect & rewind
        data = list(reader)
        if addr_col is None and looks_addr(header[0]):
            data = [header] + data
            addr_col = 0
            eth_col = 1 if len(header) > 1 else None
        if addr_col is None:
            # fall back: first column that looks like an address in row 1
            probe = data[0] if data else header
            for i, c in enumerate(probe):
                if looks_addr(c):
                    addr_col = i
                    break
        if addr_col is None:
            raise ValueError(f"no 0x-address column found in {csv_path} (header={header})")
        for r in data:
            if addr_col >= len(r) or not looks_addr(r[addr_col]):
                continue
            eth = None
            if eth_col is not None and eth_col < len(r):
                try:
                    eth = float(r[eth_col])
                except ValueError:
                    eth = None
            rows.append({"address": r[addr_col].strip().lower(), "eth": eth})
    # dedup, keep max-eth occurrence
    best = {}
    for r in rows:
        a = r["address"]
        if a not in best or (r["eth"] or 0) > (best[a]["eth"] or 0):
            best[a] = r
    out = sorted(best.values(), key=lambda r: -(r["eth"] or 0))
    if not out:
        raise ValueError(f"{csv_path}: parsed 0 candidate addresses")
    return out


def sanitize(key):
    return "".join(c if c.isalnum() else "_" for c in key)[:40]


def fetch(addr, name):
    """Run fetch_target.py. Returns (ok, sol, ast, balance_wei, reason)."""
    r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "fetch_target.py"),
                        addr, "--name", name], capture_output=True, text=True, cwd=ROOT)
    out = r.stdout + r.stderr
    wei = None
    for line in out.splitlines():
        if "live ETH balance:" in line:
            try:
                wei = int(line.split("(")[1].split(" wei")[0])
            except Exception:
                pass
    sol = os.path.join("docs", "targets", f"{name}.sol")
    ast = os.path.join("docs", "targets", f"{name}.ast.json")
    if r.returncode == 0 and os.path.exists(os.path.join(ROOT, ast)):
        return True, sol, ast, wei, None
    reason = next((l.strip() for l in out.splitlines() if "FAIL LOUD" in l or "ERROR" in l),
                  out.strip().splitlines()[-1] if out.strip() else "unknown")
    return False, None, None, wei, reason


def _machine_json(stdout):
    """Extract the '=== MACHINE JSON ===' object both detectors emit."""
    mj = stdout[stdout.index("=== MACHINE JSON"):]
    return json.loads(mj[mj.index("{"):])


def detect_open(ast, sol):
    """Run the open-refund detector. Returns (n_open, primary_or_None, error_or_None)."""
    r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "detect_open_refund.py"),
                        ast, sol], capture_output=True, text=True, cwd=ROOT)
    if r.returncode != 0:
        return 0, None, (r.stderr.strip().splitlines()[-1] if r.stderr.strip() else "detector error")
    try:
        obj = _machine_json(r.stdout)
    except Exception as e:
        return 0, None, f"parse error: {e}"
    refs = obj.get("open_refunds") or []
    return len(refs), (refs[0] if refs else None), None


def detect_hong(ast, sol):
    """Run the HONG-class detector. Returns (n_hyps, top_or_None, error_or_None)."""
    r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "detect_recovery_path.py"),
                        ast, sol], capture_output=True, text=True, cwd=ROOT)
    if r.returncode != 0:
        return 0, None, (r.stderr.strip().splitlines()[-1] if r.stderr.strip() else "detector error")
    try:
        obj = _machine_json(r.stdout)
    except Exception as e:
        return 0, None, f"parse error: {e}"
    hyps = obj.get("hypotheses") or []
    return len(hyps), (hyps[0] if hyps else None), None


def last_activity(addr, key):
    """Most-recent tx timestamp via Etherscan txlist desc (1 call). Returns
    (last_ts_or_None, n_txs_seen). A live, busy contract is not 'stuck'."""
    try:
        resp = es_get({"module": "account", "action": "txlist", "address": addr,
                       "startblock": 0, "endblock": 99999999, "page": 1, "offset": 1,
                       "sort": "desc"}, key)
    except Exception:
        return None, None
    res = resp.get("result")
    if not isinstance(res, list) or not res:
        return None, 0
    try:
        return int(res[0].get("timeStamp")), len(res)
    except Exception:
        return None, None


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", required=True, help="BigQuery candidate export (address[,eth])")
    ap.add_argument("--limit", type=int, help="only the top-N by ETH")
    ap.add_argument("--min-eth", type=float, default=1.0, help="skip candidates below this ETH")
    ap.add_argument("--only-new", action="store_true",
                    help="skip addresses already on the ForgottenETH curated list")
    ap.add_argument("--report", default=os.path.join("docs", "targets", "discovery_report.json"))
    ap.add_argument("--dormant-days", type=int, default=365,
                    help="a survivor whose last tx is older than this is flagged DORMANT")
    args = ap.parse_args(argv)

    env = env_with_dotenv()
    key = env.get("ETHERSCAN_API_KEY")
    if not key:
        print("ERROR: ETHERSCAN_API_KEY not set (.env)", file=sys.stderr)
        return 2

    cands = load_candidates(args.csv)
    feth = load_forgotteneth_addrs()
    if args.only_new:
        before = len(cands)
        cands = [c for c in cands if c["address"] not in feth]
        print(f"--only-new: dropped {before - len(cands)} already on ForgottenETH "
              f"({len(cands)} new candidates remain)")
    cands = [c for c in cands if (c["eth"] is None or c["eth"] >= args.min_eth)]
    if args.limit:
        cands = cands[:args.limit]

    print(f"Discovery triage: {len(cands)} candidates (min_eth={args.min_eth}) "
          f"through fetch -> detect ...\n")
    rows, survivors, hits = [], [], []
    used_names = set()
    for i, c in enumerate(cands, 1):
        addr = c["address"]
        # unique on-disk basename per address (avoid collisions across candidates)
        name = sanitize(f"disc_{addr[2:10]}")
        n = name
        while n in used_names:
            n = f"{name}_{len(used_names)}"
        name = n
        used_names.add(name)
        known = addr in feth
        eth_hint = f"{c['eth']:.3f}ETH" if c["eth"] is not None else "?"
        label = f"[{i}/{len(cands)}] {addr} ({eth_hint}{', FETH' if known else ''})"

        ok, sol, ast, wei, reason = fetch(addr, name)
        eth = wei / 1e18 if wei else (c["eth"] or 0)
        base = {"address": addr, "name": name, "eth_csv": c["eth"], "balance_wei": wei,
                "known_forgotteneth": known}
        if not ok:
            print(f"{label}\n    SKIP: {(reason or '')[:90]}")
            rows.append({**base, "fetched": False, "reason": reason})
            time.sleep(0.22)
            continue

        n_open, top_open, oerr = detect_open(ast, sol)
        n_hong, top_hong, herr = detect_hong(ast, sol)
        ts, ntx = last_activity(addr, key)
        # Dormancy is a ranking SIGNAL, not a hard drop: our 4 proven targets still
        # receive sporadic refund() calls yet remain stuck for the unclaimed, so a
        # clean self-refund is worth proving regardless of recent activity.
        days_dormant = round((time.time() - ts) / 86400.0, 1) if ts is not None else None

        row = {**base, "fetched": True, "sol": sol, "ast": ast,
               "n_open_refunds": n_open, "n_hong_hyps": n_hong,
               "last_tx_ts": ts, "days_dormant": days_dormant, "n_recent_tx": ntx,
               "open_error": oerr, "hong_error": herr}
        clean_low = bool(top_open and top_open.get("clean") and top_open.get("legal_tier") == "LOW")
        if top_open:
            row["open_primary"] = {
                "refund_function": top_open.get("refund_function"),
                "clean": top_open.get("clean"),
                "legal_tier": top_open.get("legal_tier"),
                "idempotent": top_open.get("idempotent"),
                "front_runnable": top_open.get("front_runnable"),
                "amount_source": top_open.get("amount_source"),
            }
        if top_hong:
            row["hong_primary"] = {
                "path": top_hong.get("path"), "legal_tier": top_hong.get("legal_tier"),
                "encodable": top_hong.get("abi_shape", {}).get("encodable"),
            }
        row["clean_low_open_refund"] = clean_low
        rows.append(row)
        survivors.append(row)

        if clean_low or n_hong:
            tag = "OPEN-REFUND CLEAN-LOW" if clean_low else f"HONG-class x{n_hong}"
            dorm = f", dormant {days_dormant:.0f}d" if days_dormant is not None else ""
            print(f"{label}\n    *** SURVIVOR ({eth:.3f} ETH{dorm}): {tag} "
                  f"| open={n_open} hong={n_hong}")
            hits.append(row)
        else:
            why = "no self-paying refund / off-class" if not (oerr or herr) else f"{oerr or herr}"
            print(f"{label}\n    fetched ({eth:.3f} ETH); no clean hypothesis ({why})")
        time.sleep(0.22)

    os.makedirs(TARGETS, exist_ok=True)
    report_path = os.path.join(ROOT, args.report)
    json.dump(rows, open(report_path, "w"), indent=2)

    fetched = sum(1 for r in rows if r.get("fetched"))
    print(f"\n{'='*74}\nDISCOVERY SUMMARY: {len(rows)} candidates | {fetched} verified-legacy "
          f"(in-scope) | {len(survivors)} ran detectors | {len(hits)} SURVIVORS")
    for h in sorted(hits, key=lambda r: -(r.get("balance_wei") or 0)):
        eth = (h.get("balance_wei") or 0) / 1e18
        op = h.get("open_primary") or {}
        kind = (f"open-refund {op.get('refund_function')}() clean={op.get('clean')}"
                if h.get("clean_low_open_refund") else f"HONG-class x{h.get('n_hong_hyps')}")
        new = "" if h.get("known_forgotteneth") else "  [NEW]"
        print(f"  SURVIVOR  {h['address']}  {eth:.3f} ETH | {kind}{new}")
    if hits:
        print(f"\nNEXT (by hand, on each SURVIVOR -- the fork-proof is the SOLE oracle):")
        print(f"  1) python3 scripts/safety_check.py --contract <addr> --ast <ast> --src <sol> --name <n>")
        print(f"  2) python3 scripts/enumerate_owners.py ...   3) fork-prove a real unclaimed owner")
    print(f"\nreport -> {args.report}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
