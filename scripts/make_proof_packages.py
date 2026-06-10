#!/usr/bin/env python3
"""Generate a ProofPackage per open-refund target (step 4). LOCAL ONLY — no RPC.

For each enumerated unclaimed owner this emits the EXACT transaction they (and only
they) sign to recover their own funds: {to: contract, data: refund() calldata,
value: 0, gas}. The agent NEVER signs or sends — this is the hand-off artifact the
rightful owner executes (no-custody invariant). Inputs: docs/targets/owners_<name>.json
(from enumerate_owners.py). Outputs: a machine JSON + a human-readable markdown.

Usage: python3 scripts/make_proof_packages.py --name ahoolee --proof test/AhooleeRefund.t.sol \
           --method 'refund()'
"""
import argparse
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--method", default="refund()", help="zero-arg recovery method the owner calls")
    ap.add_argument("--proof", required=True, help="path to the forge fork-proof test (evidence)")
    ap.add_argument("--gas", type=int, default=120000)
    args = ap.parse_args(argv)

    owners_path = os.path.join(ROOT, "docs", "targets", f"owners_{args.name}.json")
    rep = json.load(open(owners_path))
    contract = rep["contract"]
    calldata = subprocess.run(["cast", "sig", args.method], capture_output=True, text=True).stdout.strip()

    packages = []
    for o in rep["unclaimed"]:
        if not o["eoa"]:
            continue  # contract owners: refund .send/.transfer (2300 gas) may revert — exclude
        packages.append({
            "rightful_owner": o["address"],
            "recoverable_eth": o["eth"],
            "recoverable_wei": o["wei"],
            "transaction_to_sign": {
                "from": o["address"], "to": contract, "value": "0",
                "data": calldata, "gas": args.gas,
            },
        })

    out = {
        "target": rep["name"], "contract": contract,
        "recovery_method": args.method, "recovery_calldata": calldata,
        "fork_proof": args.proof, "snapshot_block": rep["block"],
        "live_balance_eth": rep["live_balance_eth"],
        "total_recoverable_eth": sum(p["recoverable_eth"] for p in packages),
        "n_owners": len(packages),
        "no_custody_note": ("The agent never signs or sends. Each owner signs the single "
                            "transaction above from their OWN address; refund() returns only "
                            "that caller's deposit (verified not front-runnable). LOW legal tier."),
        "packages": packages,
    }
    pj = os.path.join(ROOT, "docs", "targets", f"package_{args.name}.json")
    json.dump(out, open(pj, "w"), indent=2)

    # human-readable markdown
    md = [f"# ProofPackage — {rep['name']}  ({contract})", "",
          f"- **Recovery:** each rightful owner calls `{args.method}` from their own address.",
          f"- **Calldata:** `{calldata}`  (to: `{contract}`, value: 0, gas: ~{args.gas})",
          f"- **Fork-proof (evidence):** `{args.proof}` (snapshot block {rep['block']})",
          f"- **Live contract balance:** {rep['live_balance_eth']:.4f} ETH",
          f"- **Recoverable to {len(packages)} EOA owners:** {out['total_recoverable_eth']:.4f} ETH",
          "- **No custody:** the agent produces this path; the owner signs. refund() pays only the caller's own deposit (not front-runnable, LOW tier).",
          "", "| # | Rightful owner | Recoverable ETH |", "|---|---|---|"]
    for i, p in enumerate(sorted(packages, key=lambda x: -x["recoverable_eth"]), 1):
        md.append(f"| {i} | `{p['rightful_owner']}` | {p['recoverable_eth']:.4f} |")
    mp = os.path.join(ROOT, "docs", "targets", f"package_{args.name}.md")
    open(mp, "w").write("\n".join(md) + "\n")

    print(f"{rep['name']}: {len(packages)} owner packages, "
          f"{out['total_recoverable_eth']:.4f} ETH recoverable")
    print(f"  -> docs/targets/package_{args.name}.json")
    print(f"  -> docs/targets/package_{args.name}.md")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
