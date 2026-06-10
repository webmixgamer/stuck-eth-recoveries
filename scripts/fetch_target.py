#!/usr/bin/env python3
"""Fetch a real mainnet contract's VERIFIED source + compile its legacy AST.

Given a mainnet address, this calls the Etherscan V2 `getsourcecode` endpoint
(free tier; key in .env as ETHERSCAN_API_KEY), writes the verified source, picks
the solc version Etherscan recorded, compiles a legacy `--ast-json`, and writes
both `<NAME>.sol` and `<NAME>.ast.json` into the target dir -- the exact two
inputs `scripts/run_pipeline.py --ast ... --src ...` consumes. Also reports the
contract's live ETH balance (the "is there stuck money here" signal).

SCOPE / FAIL-LOUD (never silently produce a wrong AST):
  * Only the LEGACY AST family the detector understands: solc <= 0.4.26. solc 0.5+
    changed `--ast-json` node names + offset semantics, so >0.4.26 FAILS LOUD.
  * Only SINGLE-FILE verified sources (the dominant legacy case). A multi-file /
    standard-json source FAILS LOUD with a clear reason (flatten it first) rather
    than emit a partial AST -- `--ast-json` over multiple sources concatenates
    per-file ASTs and our `raw_decode` would grab only the first.
  * An UNVERIFIED address (empty SourceCode) FAILS LOUD -- we never guess.

This is data plumbing only: it NOMINATES a target for the detector/prover. The
Foundry fork-proof remains the SOLE oracle that a recovery path is real.

Usage:
    python3 scripts/fetch_target.py 0x<address> [--out-dir docs/targets] [--name NAME]
"""
import argparse
import json
import os
import re
import subprocess
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ETHERSCAN_V2 = "https://api.etherscan.io/v2/api"


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


def es_get(params, key):
    params = dict(params, chainid=1, apikey=key)
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"{ETHERSCAN_V2}?{qs}"
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read().decode())


def parse_single_source(source_code):
    """Return the plain Solidity text iff this is a single-file verified source.
    Raises ValueError (fail loud) on a multi-file / standard-json bundle, whose
    AST our single-`raw_decode` extraction cannot faithfully represent."""
    s = source_code.strip()
    if s.startswith("{"):
        raise ValueError(
            "multi-file / standard-json source (SourceCode begins with '{'); "
            "this tool only handles single-file verified sources -- flatten the "
            "contract first, then point --src/--ast at the flattened file")
    return source_code


def solc_version_of(compiler_version):
    """'v0.4.21+commit.dfe3193c' -> '0.4.21'. Fail loud if unparseable or > 0.4.26."""
    m = re.search(r"v?(\d+)\.(\d+)\.(\d+)", compiler_version or "")
    if not m:
        raise ValueError(f"unrecognized CompilerVersion {compiler_version!r}")
    major, minor, patch = (int(x) for x in m.groups())
    ver = f"{major}.{minor}.{patch}"
    if (major, minor) > (0, 4) or (major, minor) == (0, 4) and patch > 26:
        raise ValueError(
            f"solc {ver} is outside the legacy AST family this detector handles "
            f"(<= 0.4.26). solc 0.5+ changed --ast-json node names/offsets.")
    return ver


def ensure_solc(ver, env):
    """solc-select install (if needed) + use `ver`. Returns the solc command list."""
    listed = subprocess.run(["solc-select", "versions"], capture_output=True,
                            text=True, env=env).stdout
    if ver not in listed:
        print(f"  installing solc {ver} (one-time)...")
        r = subprocess.run(["solc-select", "install", ver], capture_output=True,
                           text=True, env=env)
        if r.returncode != 0:
            raise RuntimeError(f"solc-select install {ver} failed:\n{r.stderr}")
    r = subprocess.run(["solc-select", "use", ver], capture_output=True,
                       text=True, env=env)
    if r.returncode != 0:
        raise RuntimeError(f"solc-select use {ver} failed:\n{r.stderr}")
    return ["solc"]


def compile_ast(sol_path, env):
    """solc --ast-json <file> -> the legacy AST dict (raw_decode from first '{',
    identical to gen_synthetic_asts.sh). Fail loud on non-zero / no JSON."""
    r = subprocess.run(["solc", "--ast-json", sol_path], capture_output=True,
                       text=True, env=env, cwd=ROOT)
    out = r.stdout
    if "{" not in out:
        raise RuntimeError(
            f"solc --ast-json produced no JSON (rc={r.returncode}):\n{r.stderr[:800]}")
    start = out.index("{")
    obj, _ = json.JSONDecoder().raw_decode(out[start:])
    return obj


def main(argv):
    ap = argparse.ArgumentParser(description="fetch verified source + legacy AST for a mainnet address")
    ap.add_argument("address")
    ap.add_argument("--out-dir", default=os.path.join("docs", "targets"))
    ap.add_argument("--name", help="override output basename (default: Etherscan ContractName)")
    args = ap.parse_args(argv)

    env = env_with_dotenv()
    key = env.get("ETHERSCAN_API_KEY")
    if not key:
        print("ERROR: ETHERSCAN_API_KEY not set (.env)", file=sys.stderr)
        return 2
    addr = args.address.strip()
    if not re.fullmatch(r"0x[0-9a-fA-F]{40}", addr):
        print(f"ERROR: {addr!r} is not a 20-byte hex address", file=sys.stderr)
        return 2

    print(f"[1/4] Etherscan getsourcecode {addr} ...")
    src_resp = es_get({"module": "contract", "action": "getsourcecode", "address": addr}, key)
    if src_resp.get("status") != "1" or not src_resp.get("result"):
        print(f"  FAIL LOUD: Etherscan error: {src_resp.get('result') or src_resp}", file=sys.stderr)
        return 1
    info = src_resp["result"][0]
    source_code = info.get("SourceCode") or ""
    cname = info.get("ContractName") or ""
    compiler = info.get("CompilerVersion") or ""
    if not source_code.strip():
        print(f"  FAIL LOUD: {addr} has NO verified source on Etherscan (not a candidate).", file=sys.stderr)
        return 1
    print(f"      ContractName={cname}  CompilerVersion={compiler}")

    bal_resp = es_get({"module": "account", "action": "balance", "address": addr, "tag": "latest"}, key)
    wei = int(bal_resp.get("result", "0")) if str(bal_resp.get("result", "")).isdigit() else 0
    print(f"[2/4] live ETH balance: {wei/1e18:.6f} ETH ({wei} wei)")

    try:
        text = parse_single_source(source_code)
        ver = solc_version_of(compiler)
    except ValueError as e:
        print(f"  FAIL LOUD: {e}", file=sys.stderr)
        return 1

    name = args.name or (cname if re.fullmatch(r"\w+", cname or "") else "Target")
    out_dir = os.path.join(ROOT, args.out_dir)
    os.makedirs(out_dir, exist_ok=True)
    sol_path = os.path.join(out_dir, f"{name}.sol")
    ast_path = os.path.join(out_dir, f"{name}.ast.json")
    # Prepend a provenance header (comment) so the on-disk source is traceable.
    header = (f"// SPDX-Recovery-Provenance: fetched from Etherscan (verified)\n"
              f"// address: {addr}\n// contract: {cname}\n// compiler: {compiler}\n"
              f"// live balance at fetch: {wei} wei ({wei/1e18:.6f} ETH)\n")
    with open(sol_path, "w") as f:
        f.write(header + text)

    print(f"[3/4] compiling legacy AST with solc {ver} ...")
    try:
        ensure_solc(ver, env)
        ast = compile_ast(os.path.relpath(sol_path, ROOT), env)
    except (RuntimeError, ValueError) as e:
        print(f"  FAIL LOUD: {e}", file=sys.stderr)
        return 1
    with open(ast_path, "w") as f:
        json.dump(ast, f, indent="\t")

    rel_ast = os.path.relpath(ast_path, ROOT)
    rel_sol = os.path.relpath(sol_path, ROOT)
    print(f"[4/4] wrote:\n      {rel_sol}\n      {rel_ast}")
    print("\nNext (detect-only):")
    print(f"  python3 scripts/detect_recovery_path.py {rel_ast} {rel_sol}")
    print("Then (prove on a mainnet fork, the SOLE oracle):")
    print(f"  python3 scripts/run_pipeline.py --ast {rel_ast} --src {rel_sol} \\")
    print(f"      --contract {addr} --holder 0x<owner> --block <n> --rpc-alias mainnet \\")
    print(f"      --out test/{name}Recovery.t.sol --test-contract {name}Recovery --run")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
