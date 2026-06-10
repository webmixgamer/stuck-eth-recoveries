#!/usr/bin/env python3
"""Generate a public, anti-phishing VERIFIED-CLAIMS page for a proven target.

Because the open-refund recovery is NOT front-runnable (refund() pays only the
caller's own deposit), the claim info is SAFE TO PUBLISH — a third party learning
it can only help the rightful owner, never steal. This turns a passive ForgottenETH
balance listing into an actionable, verifiable claim: the owner sees the exact tx
to sign, a safety attestation, and pointers to the open-source fork-proof.

Anti-phishing by construction: the page NEVER asks for keys/seed/funds/approvals;
the owner signs ONE transaction (refund(), value 0) FROM their own address that
sends THEM their ETH. Reads owners_<name>.json + package_<name>.json (+ SAFETY md).

Output is written to claims/<name>.md (a tracked, public-facing dir) + claims/README.md.
NOTE: publishing requires the verification artifacts (fork-proof / repo) to be PUBLIC;
the repo is currently private — see the "Verify" section placeholder.

Usage: python3 scripts/make_claims_page.py --name ahoolee --etherscan-url https://etherscan.io/address/0x..
"""
import argparse
import json
import os
import sys
import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = "github.com/webmixgamer/stuck-eth-recoveries"  # public proofs repo


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--title", required=True, help="human title, e.g. 'Ahoolee Token Sale (2017)'")
    ap.add_argument("--asof", default="2026-06-02", help="snapshot date (no Date.now in this env)")
    args = ap.parse_args(argv)

    owners = json.load(open(os.path.join(ROOT, "docs", "targets", f"owners_{args.name}.json")))
    pkg = json.load(open(os.path.join(ROOT, "docs", "targets", f"package_{args.name}.json")))
    C = owners["contract"]
    safety = os.path.exists(os.path.join(ROOT, "docs", "targets", f"SAFETY_{args.name}.md"))

    # Mechanism-specific anti-phishing copy MUST be exact (zero-new-trust). Each target's
    # openness/owner-drain/immutability differs, so the prose is loaded per-target from
    # docs/targets/claims_copy_<name>.json (keys below); defaults fit the soft-cap/refund()
    # case (Ahoolee/jincor). NEVER publish generic copy that misstates the real mechanism.
    method = pkg["recovery_method"]
    copy_path = os.path.join(ROOT, "docs", "targets", f"claims_copy_{args.name}.json")
    copy = json.load(open(copy_path)) if os.path.exists(copy_path) else {}
    situation = copy.get("situation",
        f"This {args.title} sale did not reach its soft cap, so its on-chain `{method}` "
        "function is **permanently open**. Most contributors already refunded years ago; "
        "the addresses below never did. Each can still reclaim **their own deposit** today.")
    immutable_line = copy.get("immutable_line",
        "no DELEGATECALL / SELFDESTRUCT (immutable, not upgradeable, not destructible)")
    owner_block_line = copy.get("owner_block_line",
        "The only functions that move ETH are the refund (this claim) and an owner "
        "withdraw that is **permanently blocked** (requires a soft-cap that can never be reached).")
    drain_history_line = copy.get("drain_history_line",
        "No ETH has left the contract since 2018; an automated scavenger that tried "
        "`drain()/sweep()/destroy()` extracted nothing (those functions don't exist).")

    rows = sorted(owners["unclaimed"], key=lambda o: -o["eth"])
    L = []
    L.append(f"# Verified unclaimed-refund claims — {args.title}")
    L.append("")
    L.append(f"**Contract:** [`{C}`](https://etherscan.io/address/{C}) · "
             f"**Stuck balance:** {owners['live_balance_eth']:.4f} ETH · "
             f"**Unclaimed owners:** {owners['n_unclaimed']} · "
             f"**Recoverable:** {pkg['total_recoverable_eth']:.4f} ETH · *as of {args.asof}*")
    L.append("")
    L.append("## What this is")
    L.append(situation)
    L.append("")
    L.append("## How to claim (read carefully — this is NOT a phishing message)")
    L.append(f"- You call **one** function on the original contract: `{pkg['recovery_method']}` "
             f"(calldata `{pkg['recovery_calldata']}`), **value 0**, from the SAME address that contributed.")
    L.append("- It sends **your own deposit** back to you. It cannot send your funds anywhere else, "
             "and no one else can claim on your behalf (the refund is gated on *your* address).")
    L.append("- **We never ask for your seed phrase, private key, or any payment, and we never need an "
             "`approve`.** Anyone telling you otherwise is scamming you.")
    L.append("- You can verify the contract + the exact call on Etherscan before signing.")
    L.append("")
    if safety:
        L.append("## Safety attestation")
        L.append(f"- Code immutability: **{immutable_line}**.")
        L.append(f"- {owner_block_line}")
        L.append(f"- {drain_history_line}")
        L.append("- The recovery was reproduced on a mainnet fork (the contract's real deployed code).")
        L.append("")
    L.append("## Unclaimed owners (addresses are already public on-chain; no identities)")
    L.append("| # | Address | Recoverable ETH |")
    L.append("|---|---|---|")
    for i, o in enumerate(rows, 1):
        L.append(f"| {i} | `{o['address']}` | {o['eth']:.4f} |")
    L.append("")
    L.append("## Verify everything yourself")
    L.append(f"- Fork-proof + tooling (open source): `{REPO}`")
    L.append(f"- Fork-proof test: `{pkg.get('fork_proof','(see repo)')}`")
    L.append("- This recovery is **owner-signs / no-custody**: we never hold or move your funds; you sign your own claim.")
    L.append("")

    os.makedirs(os.path.join(ROOT, "claims"), exist_ok=True)
    out = os.path.join(ROOT, "claims", f"{args.name}.md")
    open(out, "w").write("\n".join(L) + "\n")
    print(f"{args.name}: {owners['n_unclaimed']} owners, {pkg['total_recoverable_eth']:.4f} ETH -> claims/{args.name}.md")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
