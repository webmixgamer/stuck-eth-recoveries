# Add 6 fork-verified failed-ICO refund vaults (~276 ETH, 217 addresses)

Six 2016–2018 contracts where stuck ETH is recoverable by each original contributor calling a **normal public refund function that returns only their own deposit** — the same class as the existing OpenZeppelin RefundableCrowdsale entries (Vuepay, GavCoin, …). None are on the current registry. Every one is reproduced on a mainnet fork and safety-audited; this PR adds the `protocols.json` entries + `data/balances/*` files.

> First, thank you — ForgottenETH is the reference for this problem space, and the no-custody / reproducible-on-Etherscan ethos is exactly right. These six are my contribution to it.

## Scope

For each contract: is the ETH recoverable **today** by the original depositor with no admin/authority action, no custody, and no front-running risk? Verified against real mainnet bytecode on a Foundry fork at block 25,270,000.

## Executive summary

- **What the evidence supports:** each contract exposes a self-paying refund (`refund()`/`refundEther()`/`requestRefund()`/`party()`) that pays `msg.sender` exactly their own recorded deposit and zeroes it (CEI). A real, unclaimed contributor reclaiming their funds is fork-proven for all six; the only owner/admin ETH-out path is gated permanently shut (proven by a reverting call), so none is owner-drainable.
- **Strongest evidence:** committed Foundry tests that prank a real unclaimed address and assert exact ETH movement + idempotence + owner-can't-drain (31 tests, all green). Per-owner amounts reconcile to the live contract balance.
- **Practical impact:** 217 self-claimable EOAs, ~275.8 ETH, invisible to portfolio trackers.
- **What it does NOT prove:** that the owners are reachable or will act; that *every* historical contributor is included (lists are the currently-unclaimed, EOA-only set); legitimacy beyond extractability (mitigated — each payout is the caller's own deposit).
- **Evidence still required:** independent re-verification on your pipeline; holder-list filtering to your standard (I excluded contracts/non-EOAs; you may also drop exchange-deposit addresses).

## Deployed surface

| Protocol | Contract | Live ETH | Recovery (public, self-paying) | Owner-drain status |
|---|---|---:|---|---|
| DigiPulse (DGT) | [0x9aca…aa4d](https://etherscan.io/address/0x9aca6abfe63a5ae0dc6258cefb65207ec990aa4d) | 100.58 | `refundEther()` ← `ethBalanceOf` | `withdrawFundsToOwner` needs `icoFulfilled` (false forever) — reverts |
| DirectCrypt | [0x12d5…2fe5](https://etherscan.io/address/0x12d5b7c26dd8dc6e2f71f5bf240d5e76452b2fe5) | 81.89 | `refund()` ← `deposited` | `withdraw` needs softCap (never); owner can `halt()` (reversible pause, not a drain) |
| QCOToken | [0x3a8a…517b](https://etherscan.io/address/0x3a8a97123bccd826228e5eb4144b48cce169517b) | 31.50 | `requestRefund()` ← `ethPossibleRefunds` | drain needs `Operational`, unreachable from terminal `Aborted` |
| hodlEthereum | [0x1bb2…1536](https://etherscan.io/address/0x1bb28e79f2482df6bf60efc7a33365703bcf1536) | 22.53 | `party()` ← `hodlers` | **no owner/admin at all** — fully immutable |
| Blocklancer (LNC) | [0x9ea8…f13d](https://etherscan.io/address/0x9ea80e204045329ba752d03c395f82a12799f13d) | 21.66 | `refund()` ← `balancesEther` | `master.finalize()` reverts for the failed raise — proven |
| ZTCrowdsale | [0xaf7a…4373](https://etherscan.io/address/0xaf7aea249098f2c2f50cc11d4000ccf798194373) | 21.17 | `endCrowdsale()` then `refund()` ← `balances` | `withdraw` needs `raised≥min` (never) |

## Method

1. **Discovery** — BigQuery `balances⨝contracts` (>10 ETH, created < 2019-07), minus the ForgottenETH set → 937 candidates → 359 verified-legacy → 18 with a self-paying-refund AST signature.
2. **Adversarial triage** — each read in full; classified stuck vs live vs false-positive. (Dismissed: CryptoPunks 3,230 ETH = live marketplace float; SingularDTVFund 435 ETH = detector matched a sibling contract in a flattened source, selector absent on-chain; ZiberCrowdsale = self-destructed, `cast code`=0x.)
3. **Fork-proof** — per target, a Foundry test pranks a real unclaimed contributor, asserts exact ETH out, idempotence (2nd call reverts/no-ops), a non-contributor reverts, and the owner-drain path reverts.
4. **Safety audit** — bytecode is immutable (no delegatecall/selfdestruct in the verified source), the only ETH-out paths are the refund + an owner path that is permanently gated shut.

## Per-target claim boundaries

- **ZTCrowdsale** is **multi_step** (`multi_step:true`): the stage is still `InProgress`, so the one-time, **permissionless** `endCrowdsale()` (now past `end`, no owner gate) must run before refunds open. Per-owner amounts read from private storage (slot 23); the ~7 ETH of pre-ICO deposits that were auto-forwarded to the beneficiary are correctly excluded, and the 11 entitlements reconcile to the balance.
- **DirectCrypt**: the owner can `halt()` to pause refunds (a reversible griefing lever, **not** a drain); refunds are confirmed open at this snapshot.
- **DigiPulse**: `total_eth_in_balances` (97.08) is < contract balance (100.58); the ~3.5 ETH surplus has no ledger entry and is not claimable via `refundEther()`.
- **hodlEthereum** is a distinct contract from the existing `just_hodl_it` entry (different address). Suggested category `other`.

## Reproduction

Foundry fork-proofs + safety audits are public and self-contained: **https://github.com/webmixgamer/stuck-eth-recoveries**

```bash
forge test --match-path "test/*Refund.t.sol"   # 31 passed (the six above + 4 already-listed)
```
Each test is one file (`DigiPulseRefund.t.sol`, `DirectCryptRefund.t.sol`, …) and reads live mainnet state via fork.

## Notes for integration

- I left `index_shards/`, `table_meta/`, `total.json` for your pipeline to regenerate (per #12).
- Balances are EOA-only and `balance_source:"token"` (precomputed, like the other ICO entries); 4 of the 6 also have a live public getter if you prefer `"eth"` for the multicall CLI.
- Happy to split this into per-contract PRs or adjust keys/categories to your conventions.

## References
- Discovery + triage + per-owner enumeration methodology and raw data: https://github.com/webmixgamer/stuck-eth-recoveries
