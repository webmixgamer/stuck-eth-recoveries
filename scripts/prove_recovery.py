#!/usr/bin/env python3
"""Recovery PROVER (scripts/prove_recovery.py) — stdlib-only generator that turns a
recovery-path HYPOTHESIS (detect_recovery_path.py) + a problem statement
{contract, holder, block} into a Foundry fork-proof test/RecoveryProof.t.sol.

ANTI-CHEAT: problem statement is the legitimate external input; the SOLUTION
(call sequence + magic amount) is derived from hypothesis structure + LIVE
on-chain reads, never a literal. Design = derive-in-EVM: Python resolves NAMES +
target-SELECTION POLICY; all numeric witness derivation is emitted as Solidity
recomputed (unchecked) at fork state. Fork-proof is the SOLE oracle. HONG defaults.
"""
import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEFAULT_CONTRACT = "0x9Fa8fA61A10Ff892E4EBCeB7f4e0FC684C2ce0a9"
DEFAULT_HOLDER = "0x521DABfd2c8b76DEaC89d44222bD3F75f388A2eC"
DEFAULT_BLOCK = 25_195_000
DEFAULT_RPC_ALIAS = "mainnet"

# Must match detect_recovery_path.ABI_SHAPE_VERSION. The prover REFUSES a
# hypothesis whose abi_shape is absent or a different version, so an old detector
# can never silently re-enable the hardcoded ABI shape. [Step 4 / AC-1]
ABI_SHAPE_VERSION = 1

DEFAULT_HYPOTHESIS = {
    "write_function": "mgmtIssueBountyToken",
    "write_operator": "+=",
    "sink_function": "refundMyIcoInvestment",
    "shared_state_var": "balances",
    "gate_snippet": "balances[msg.sender] > tokensCreated",
    "gate_line": 391,
    "sink_modifiers": ["noEther", "notLocked", "onlyTokenHolders"],
    "required_authority": "admin/owner (managementBodyAddress; fixed signer set in constructor)",
    # Explicit authority machine-fields from the detector (the prover reads these,
    # never the human label) + the legal-firewall tier.
    "write_authority_kind": "signer-gated",
    "write_authority_getter": "managementBodyAddress",
    "legal_tier": "LOW",
    "front_runnable": False,
    # AST-derived ABI shape (Step 4). This MUST equal the detector's derived
    # abi_shape for HONG so the default path and the byte-identical independence
    # check (detector JSON vs defaults) stay valid.
    "abi_shape": {
        "version": ABI_SHAPE_VERSION, "encodable": True, "errors": [],
        "write": {
            "name": "mgmtIssueBountyToken",
            "sig": "mgmtIssueBountyToken(address,uint256)",
            "params": [
                {"name": "_recipientAddress", "abi_type": "address", "index": 0, "role": "holder"},
                {"name": "_amount", "abi_type": "uint256", "index": 1, "role": "amount"},
            ],
            "holder_index": 0, "amount_index": 1,
        },
        "sink": {"name": "refundMyIcoInvestment", "sig": "refundMyIcoInvestment()", "arg_count": 0},
        "balance_reader": {"kind": "explicit", "sig": "balanceOf(address)", "reads_var": "balances"},
        "threshold": {"mode": "getter", "sig": "tokensCreated()", "literal": None,
                      "operator": ">", "balance_side": "lhs"},
        "authority": {"mode": "getter", "sig": "managementBodyAddress()"},
        "mapping_addr_keyed": True,
    },
}

def sol_addr(a):
    """Render an address as a checksum-free Solidity literal. cast/RPC return
    lowercase addresses, which solc rejects as 'invalid checksum';
    address(bytes20(hex"...")) sidesteps EIP-55 entirely (and needs no keccak). [CQ-2]"""
    h = a.lower()
    if h.startswith("0x"):
        h = h[2:]
    if len(h) != 40 or any(c not in "0123456789abcdef" for c in h):
        raise SystemExit(f"not a 20-byte hex address: {a!r}")
    return f'address(bytes20(hex"{h}"))'


def derive_target_policy(operator, holder_floor):
    table = {
        ">": {"target_kind": "floor", "rel": "<=", "human": "p <= T"},
        ">=": {"target_kind": "floor", "rel": "<", "human": "p < T"},
        "<": {"target_kind": "threshold", "rel": ">=", "human": "p >= T"},
        "<=": {"target_kind": "threshold+1", "rel": ">", "human": "p > T"},
        "==": {"target_kind": "floor", "rel": "!=", "human": "p != T"},
        "!=": {"target_kind": "point", "rel": "==", "human": "p == T"},
    }
    if operator not in table:
        raise ValueError(f"unsupported gate operator: {operator!r}")
    return table[operator]


_HOLDER_GATE_RE = re.compile(r"only.*(holder|tokenholder|member|whitelist)", re.I)


def derive_holder_floor(sink_modifiers):
    for m in sink_modifiers or []:
        if _HOLDER_GATE_RE.search(m):
            return 1, f"sink holder-gate '{m}' => post-write balance must be >= 1", m
    return 0, "no holder-gate on sink => wrap-to-0 permitted (floor 0)", None


def pass_predicate(op):
    return {">": "p <= T", ">=": "p < T", "<": "p >= T",
            "<=": "p > T", "==": "p != T", "!=": "p == T"}[op]


def band_bounds_solidity(policy):
    rel = policy["rel"]
    return {
        "<=": ("FLOOR", "T", "p in [FLOOR, T]  (gate '>' : pass when p <= T)"),
        "<": ("FLOOR", "T - 1", "p in [FLOOR, T-1]  (gate '>=': pass when p < T)"),
        ">=": ("T", "T", "p == T  (gate '<' : min feasible post-balance is T)"),
        ">": ("T + 1", "T + 1", "p == T+1  (gate '<=': min feasible post-balance is T+1)"),
        "!=": ("FLOOR", "FLOOR", "p == FLOOR  (gate '==': any p != T; we sample the floor)"),
        "==": ("T", "T", "p == T  (gate '!=': the single passing value is T)"),
    }[rel]


def render_test(*, contract, holder, block, rpc_alias, hyp, policy,
                holder_floor, floor_reason, op, authority_sig,
                threshold_mode, threshold_sig, threshold_literal,
                balance_reader_sig, write_sig, sink_sig,
                holder_index, amount_index, n_params,
                private_stamp=False, test_contract="RecoveryProofTest"):
    banner = ("" if not private_stamp else
              "// !! PRIVATE — HIGH-TIER / FRONT-RUNNABLE PATH. Generated under an explicit\n"
              "// !! --allow-high-tier override. Route to SEAL-911 under coordinated disclosure.\n"
              "// !! DO NOT run against a public RPC and DO NOT execute on mainnet.\n")
    c_lit = sol_addr(contract)
    h_lit = sol_addr(holder)
    tk = policy["target_kind"]
    target_expr, target_comment = {
        "floor": ("FLOOR", "min of feasible interval is the holder-gate floor"),
        "threshold": ("T", "min of [T, inf) is the live threshold T"),
        "threshold+1": ("T + 1", "min of [T+1, inf) is T+1"),
        "point": ("T", "the single passing value is T"),
    }[tk]
    rel = policy["rel"]
    blocked_rel = {"<=": "bal0 > T", "<": "bal0 >= T", ">=": "bal0 < T",
                   ">": "bal0 <= T", "!=": "bal0 == T", "==": "bal0 != T"}[rel]
    # Threshold T read live (AST-confirmed public getter) or inlined (numeric literal).
    if threshold_mode == "getter":
        threshold_read = f'uint256 T = _readUint(C, "{threshold_sig}");'
        threshold_label = threshold_sig
    else:  # literal
        threshold_read = f"uint256 T = {threshold_literal};"
        threshold_label = str(threshold_literal)
    # Write-call args in the AST-DERIVED parameter order (a reordered
    # f(uint256,address) places amount before holder); amount is still recomputed
    # in-EVM (target - bal0 mod 2**256), never a literal. encodable=True
    # guarantees every param is exactly holder or amount, so n_params == 2.
    slots = ["" for _ in range(n_params)]
    slots[holder_index] = "HOLDER"
    slots[amount_index] = "amount"
    write_args = ", ".join(slots)
    band_lo, band_hi, band_comment = band_bounds_solidity(policy)
    return f"""// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {{Test, console2}} from "forge-std/Test.sol";
{banner}
/// @title RecoveryProof — GENERATED by scripts/prove_recovery.py (Step 2). DO NOT EDIT.
/// @notice Fork-proof; the SOLE oracle. Only literals are the PROBLEM STATEMENT
///   (contract/holder/block) + resolved NAMES. Authority and the magic amount are
///   DERIVED IN-EVM from live reads:
///     authority = {authority_sig} read live; target = {target_comment}
///     (gate '{op}' + holder-floor {holder_floor}); amount = (target - bal) mod 2**256.
///   Two proofs: test_ProveRecovery (min of band) and testFuzz_AnyTargetInBandUnlocks
///   (ANY target in the live-derived band {band_comment}). No custody/no signing.
contract {test_contract} is Test {{
    address constant C      = {c_lit};
    address constant HOLDER = {h_lit};
    uint256 constant FORK_BLOCK = {block};
    uint256 constant FLOOR = {holder_floor};

    function setUp() public {{ vm.createSelectFork(vm.rpcUrl("{rpc_alias}"), FORK_BLOCK); }}

    function test_ProveRecovery() public {{
        address authority = _readAddr(C, "{authority_sig}");
        {threshold_read}
        uint256 bal0 = _balanceOf(HOLDER);
        console2.log("authority ({authority_sig}):", authority);
        console2.log("threshold ({threshold_label}):", T);
        console2.log("holder balance (pre):", bal0);
        require(authority != address(0), "authority getter returned zero");
        assertTrue({blocked_rel}, "precondition: holder must be blocked at fork state");
        vm.prank(HOLDER);
        (bool blockedExit, ) = C.call{{gas: 500_000}}(abi.encodeWithSignature("{sink_sig}"));
        assertFalse(blockedExit, "bug repro: blocked holder's exit must revert");
        uint256 target = {target_expr};
        assertTrue(target >= FLOOR, "derived target below holder floor");
        _assertTargetInPassingInterval(target, T);
        uint256 recovered = _runRecovery(authority, target);
        console2.log("derived target:", target);
        console2.log("ETH recovered (wei):", recovered);
        console2.log("ETH recovered (ether):", recovered / 1e18);
        assertGt(recovered, 0, "fix: holder must recover ETH");
        assertEq(_balanceOf(HOLDER), 0, "fix: balance zeroed after a successful exit");
    }}

    function testFuzz_AnyTargetInBandUnlocks(uint256 rawTarget) public {{
        address authority = _readAddr(C, "{authority_sig}");
        {threshold_read}
        uint256 bal0 = _balanceOf(HOLDER);
        require(authority != address(0), "authority getter returned zero");
        assertTrue({blocked_rel}, "precondition: holder must be blocked at fork state");
        uint256 lo = {band_lo};
        uint256 hi = {band_hi};
        vm.assume(hi >= lo);
        uint256 target = lo + (rawTarget % (hi - lo + 1));
        _assertTargetInPassingInterval(target, T);
        assertTrue(target >= FLOOR, "fuzz target below holder floor");
        uint256 snap = vm.snapshotState();
        uint256 recovered = _runRecovery(authority, target);
        assertGt(recovered, 0, "fuzz: every in-band target must recover ETH");
        assertEq(_balanceOf(HOLDER), 0, "fuzz: balance zeroed after the exit");
        vm.revertToState(snap);
    }}

    function _runRecovery(address authority, uint256 target) internal returns (uint256) {{
        uint256 bal0 = _balanceOf(HOLDER);
        uint256 amount;
        unchecked {{ amount = target - bal0; }}
        vm.prank(authority);
        (bool writeOk, ) = C.call(abi.encodeWithSignature("{write_sig}", {write_args}));
        assertTrue(writeOk, "recovery: authority's additive write must succeed");
        assertEq(_balanceOf(HOLDER), target, "recovery: write must land balance on the derived target");
        uint256 ethBefore = HOLDER.balance;
        vm.prank(HOLDER);
        (bool exitOk, ) = C.call(abi.encodeWithSignature("{sink_sig}"));
        assertTrue(exitOk, "fix: previously-blocked exit must now succeed");
        return HOLDER.balance - ethBefore;
    }}

    function _assertTargetInPassingInterval(uint256 p, uint256 T) internal pure {{
        bool passes = {pass_predicate(op)};
        assertTrue(passes, "derived target not inside the gate's passing interval");
    }}

    function _balanceOf(address a) internal view returns (uint256) {{
        (bool ok, bytes memory ret) = C.staticcall(abi.encodeWithSignature("{balance_reader_sig}", a));
        require(ok, "balance reader failed");
        return abi.decode(ret, (uint256));
    }}
    function _readUint(address c, string memory sig) internal view returns (uint256) {{
        (bool ok, bytes memory ret) = c.staticcall(abi.encodeWithSignature(sig));
        require(ok, string(abi.encodePacked("read failed: ", sig)));
        return abi.decode(ret, (uint256));
    }}
    function _readAddr(address c, string memory sig) internal view returns (address) {{
        (bool ok, bytes memory ret) = c.staticcall(abi.encodeWithSignature(sig));
        require(ok, string(abi.encodePacked("read failed: ", sig)));
        return abi.decode(ret, (address));
    }}
}}
"""


def load_hypothesis(path):
    with open(path) as f:
        obj = json.load(f)
    if isinstance(obj, dict) and "hypotheses" in obj:
        hs = obj["hypotheses"]
        return next((h for h in hs if h.get("rank") == 1), hs[0])
    return obj


def derive(hyp, contract, holder, block, rpc_alias, allow_high_tier=False):
    # LEGAL FIREWALL (CLAUDE.md invariant #2): a HIGH-tier / front-runnable path is
    # NEVER proven unilaterally -- route to SEAL-911. Default-safe = REFUSE. [GEN-2/INV-LEGAL-1]
    tier = str(hyp.get("legal_tier") or "").upper()
    front_runnable = bool(hyp.get("front_runnable"))
    private_stamp = False
    if tier == "HIGH" or front_runnable:
        if not allow_high_tier:
            raise SystemExit(
                f"REFUSED: hypothesis is HIGH-tier / front-runnable "
                f"(legal_tier={hyp.get('legal_tier')!r}, front_runnable={front_runnable}). "
                f"Per CLAUDE.md invariant #2, a HIGH-tier path is never proven unilaterally -- route to "
                f"SEAL-911 under coordinated disclosure. Re-run with --allow-high-tier ONLY with explicit "
                f"SEAL/owner authorization (the generated test is then stamped PRIVATE).")
        private_stamp = True  # authorized override: stamp the test PRIVATE

    # Operator capability gate -- placed AFTER the legal firewall so a HIGH-tier
    # x=x+d path reports the SEAL-911 reason before this one. [PE-3]
    if hyp.get("write_operator", "+=") not in ("+=",):
        raise SystemExit("unsupported write_operator; this prover handles the unchecked additive (+=) class.")

    # ABI-SHAPE GATE (Step 4 / AC-1): the prover consumes the detector's
    # AST-derived ABI shape and NEVER falls back to a hardcoded
    # (address,uint256)/balanceOf/zero-arg-getter shape. A non-encodable target
    # FAILS LOUD here -- it never produces a mis-encoded test that still passes.
    # Placed AFTER the legal firewall so ABI widening can't create a LOW-tier path.
    abi = hyp.get("abi_shape")
    if not isinstance(abi, dict) or abi.get("version") != ABI_SHAPE_VERSION:
        raise SystemExit(
            f"REFUSED: hypothesis has no abi_shape v{ABI_SHAPE_VERSION} "
            f"(got version={(abi.get('version') if isinstance(abi, dict) else None)!r}). "
            f"Refusing to fall back to the hardcoded (address,uint256)/balanceOf/zero-arg-getter shape.")
    if not abi.get("encodable"):
        raise SystemExit("REFUSED: target ABI shape is not encodable by this prover: "
                         + "; ".join(abi.get("errors") or ["(no reason given)"]))
    # An encodable shape from the real detector always carries these blocks; a
    # corrupt/hand-edited --hypothesis must FAIL LOUD with a named reason, not an
    # uncaught KeyError. [RB-1]
    for k in ("write", "sink", "balance_reader", "threshold", "authority"):
        if not isinstance(abi.get(k), dict):
            raise SystemExit(f"REFUSED: abi_shape marked encodable but missing required block {k!r}")
    for blk, sub in (("balance_reader", "sig"), ("sink", "sig"), ("write", "sig"),
                     ("write", "holder_index"), ("write", "amount_index"), ("write", "params")):
        if abi[blk].get(sub) is None:
            raise SystemExit(f"REFUSED: abi_shape marked encodable but {blk}.{sub} is missing")

    # Authority must still be a single signer (defense-in-depth with the firewall);
    # the live getter now comes from the AST-derived abi_shape, not a scraped label.
    if hyp.get("write_authority_kind") != "signer-gated":
        raise SystemExit(
            f"REFUSED: write authority is not a single signer "
            f"(write_authority_kind={hyp.get('write_authority_kind')!r}). This prover only generates a "
            f"unilateral 'owner-signs' PoC for a signer-gated recovery lever; holder-gated / "
            f"permissionless paths are out of scope and must go through the legal gate.")
    authority = abi["authority"]
    if authority.get("mode") != "getter" or not authority.get("sig"):
        raise SystemExit("REFUSED: write authority is not a live-readable public address getter "
                         f"(authority={authority!r}).")

    threshold = abi["threshold"]
    op = threshold.get("operator")
    if not op:
        raise SystemExit("REFUSED: gate operator could not be derived from the AST.")
    holder_floor, floor_reason, _g = derive_holder_floor(hyp.get("sink_modifiers"))
    policy = derive_target_policy(op, holder_floor)
    write = abi["write"]

    return dict(contract=contract, holder=holder, block=block, rpc_alias=rpc_alias,
                hyp=hyp, policy=policy, holder_floor=holder_floor, floor_reason=floor_reason,
                op=op, authority_sig=authority["sig"],
                threshold_mode=threshold["mode"], threshold_sig=threshold.get("sig"),
                threshold_literal=threshold.get("literal"),
                balance_reader_sig=abi["balance_reader"]["sig"],
                write_sig=write["sig"], sink_sig=abi["sink"]["sig"],
                holder_index=write["holder_index"], amount_index=write["amount_index"],
                n_params=len(write["params"]), private_stamp=private_stamp)


def main(argv):
    ap = argparse.ArgumentParser(description="Generate a fork-proof from a recovery hypothesis.")
    ap.add_argument("--hypothesis")
    ap.add_argument("--contract", default=DEFAULT_CONTRACT)
    ap.add_argument("--holder", default=DEFAULT_HOLDER)
    ap.add_argument("--block", type=int, default=DEFAULT_BLOCK)
    ap.add_argument("--rpc-alias", default=DEFAULT_RPC_ALIAS)
    ap.add_argument("--allow-high-tier", action="store_true",
                    help="override the legal-firewall refusal for a HIGH-tier/front-runnable path "
                         "(SEAL-911-coordinated, authorized use only; stamps the test PRIVATE)")
    ap.add_argument("--test-contract", default="RecoveryProofTest",
                    help="name of the generated Foundry test contract (set a distinct name to avoid "
                         "collisions when proving multiple targets)")
    ap.add_argument("-o", "--out", default=os.path.join(ROOT, "test", "RecoveryProof.t.sol"))
    args = ap.parse_args(argv)
    hyp = load_hypothesis(args.hypothesis) if args.hypothesis else dict(DEFAULT_HYPOTHESIS)
    kw = derive(hyp, args.contract, args.holder, args.block, args.rpc_alias,
                allow_high_tier=args.allow_high_tier)
    if kw.get("private_stamp"):
        print("WARNING: HIGH-tier / front-runnable path generated under --allow-high-tier. "
              "Route to SEAL-911; the test is stamped PRIVATE — do not run on a public RPC.",
              file=sys.stderr)
    kw["test_contract"] = args.test_contract
    code = render_test(**kw)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as f:
        f.write(code)
    lo, hi, _ = band_bounds_solidity(kw["policy"])
    thr = kw["threshold_sig"] if kw["threshold_mode"] == "getter" else f"literal {kw['threshold_literal']}"
    print("RECOVERY PROVER — generated", os.path.relpath(args.out, ROOT))
    print("GIVEN problem statement:", args.contract, args.holder, args.block)
    print("DERIVED: write", kw["write_sig"],
          "(holder@%d, amount@%d)" % (kw["holder_index"], kw["amount_index"]),
          "; authority", kw["authority_sig"], "live; threshold", thr,
          "; gate '" + kw["op"] + "' =>", kw["policy"]["human"] + "; floor", kw["holder_floor"],
          "; balance reader", kw["balance_reader_sig"],
          "; fuzz band [" + lo + ", " + hi + "]; amount=(target-bal0) mod 2**256 in-EVM (NO literal)")
    print(f"Run the SOLE oracle: forge test --match-contract {args.test_contract} -vvv")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))