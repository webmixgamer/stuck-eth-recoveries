#!/usr/bin/env python3
"""One-command recovery pipeline: detector -> prover -> (optional) fork-proof.

Given a target's legacy AST + source and a problem statement {contract, holder,
block}, this runs the DETECTOR (scripts/detect_recovery_path.py) to produce the
rank-1 recovery HYPOTHESIS, feeds it to the PROVER (scripts/prove_recovery.py) to
generate a Foundry fork-proof, and — with --run — executes that proof (the SOLE
oracle). No per-contract code: the same command works on HONG (0.3.6) and on the
synthetic StuckVault (0.4.26).

Examples:
    # HONG (defaults baked into the prover; detector reads the bundled AST):
    python3 scripts/run_pipeline.py --run
    # A new target:
    python3 scripts/run_pipeline.py \\
        --ast docs/synthetic/StuckVault.ast.json --src docs/synthetic/StuckVault.sol \\
        --contract 0x... --holder 0x... --block <n> --rpc-alias local \\
        --out test/RecoveryProofSynthetic.t.sol --test-contract StuckVaultRecoveryProof --run
"""
import argparse
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DETECTOR = os.path.join(ROOT, "scripts", "detect_recovery_path.py")
PROVER = os.path.join(ROOT, "scripts", "prove_recovery.py")


def sh(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT, **kw)


def env_with_dotenv():
    env = dict(os.environ)
    envfile = os.path.join(ROOT, ".env")
    if os.path.exists(envfile):
        for line in open(envfile):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env.setdefault(k.strip(), v.strip())
    return env


def main(argv):
    ap = argparse.ArgumentParser(description="detector -> prover -> fork-proof pipeline")
    ap.add_argument("--ast", help="target legacy AST json (default: the bundled HONG AST)")
    ap.add_argument("--src", help="target source (default: the bundled HONG source)")
    ap.add_argument("--contract")
    ap.add_argument("--holder")
    ap.add_argument("--block", type=int)
    ap.add_argument("--rpc-alias", default="mainnet")
    ap.add_argument("--out", default=os.path.join(ROOT, "test", "RecoveryProof.t.sol"))
    ap.add_argument("--test-contract", default="RecoveryProofTest")
    ap.add_argument("--allow-high-tier", action="store_true")
    ap.add_argument("--run", action="store_true", help="execute the generated proof with forge (the oracle)")
    args = ap.parse_args(argv)

    # 1. DETECT — produce the rank-1 hypothesis.
    det_cmd = [sys.executable, DETECTOR]
    if args.ast and args.src:
        det_cmd += [args.ast, args.src]
    det = sh(det_cmd)
    if det.returncode != 0:
        print("detector failed:\n", det.stderr, file=sys.stderr)
        return 2
    mj = det.stdout[det.stdout.index("=== MACHINE JSON"):]
    obj = json.loads(mj[mj.index("{"):])
    hyps = obj.get("hypotheses") or []
    if not hyps:
        print("PIPELINE: detector found NO recovery-path hypothesis on this target (fails loud).")
        return 1
    top = hyps[0]
    hyp_path = "/tmp/_pipeline_hyp.json"
    json.dump(top, open(hyp_path, "w"))
    print("=" * 72)
    print("PIPELINE  detector -> prover -> fork-proof")
    print("=" * 72)
    print(f"[1/3] DETECTED rank-1 hypothesis: {top['path']}")
    print(f"      shared var={top['shared_state_var']}  authority={top['write_authority_getter']} "
          f"({top['write_authority_kind']})  tier={top['legal_tier']}  front_runnable={top['front_runnable']}")

    # 2. PROVE — generate the fork-proof (prover enforces the legal-tier firewall).
    pv_cmd = [sys.executable, PROVER, "--hypothesis", hyp_path,
              "--rpc-alias", args.rpc_alias, "--out", args.out, "--test-contract", args.test_contract]
    for flag, val in (("--contract", args.contract), ("--holder", args.holder),
                      ("--block", args.block)):
        if val is not None:
            pv_cmd += [flag, str(val)]
    if args.allow_high_tier:
        pv_cmd.append("--allow-high-tier")
    pv = sh(pv_cmd)
    sys.stdout.write(pv.stdout)
    if pv.returncode != 0:
        print(f"[2/3] PROVER REFUSED / failed (this is the legal firewall doing its job if HIGH-tier):\n{pv.stderr.strip()}")
        return pv.returncode
    print(f"[2/3] GENERATED proof -> {os.path.relpath(args.out, ROOT)} (contract {args.test_contract})")

    # 3. RUN — forge fork-proof is the SOLE oracle.
    if not args.run:
        print("[3/3] skipped (pass --run to execute the fork-proof, the SOLE oracle)")
        return 0
    fr = sh(["forge", "test", "--match-path", os.path.relpath(args.out, ROOT), "-vv"], env=env_with_dotenv())
    out = fr.stdout + fr.stderr
    # Require POSITIVE evidence of executed assertions — not just absence of failures.
    # A run with 0 passed / any skipped is NOT a proof (would let a vacuous/skipped
    # fork-proof read as PASS, undermining "the fork-proof is the SOLE oracle"). [PR-1]
    m = re.search(r"(\d+) passed; (\d+) failed; (\d+) skipped", out)
    if m:
        passed, failed, skipped = (int(x) for x in m.groups())
        ok = passed >= 1 and failed == 0 and skipped == 0
    else:
        ok = False
    tail = "\n".join(l for l in out.splitlines() if "PASS" in l or "FAIL" in l or "recovered" in l.lower() or "Suite result" in l)
    print(f"[3/3] forge fork-proof: {'PASS ✅' if ok else 'FAIL ❌'}")
    print(tail)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
