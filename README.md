# Forgotten ETH — recovery proofs

Reproducible **Foundry mainnet-fork proofs** that ETH stuck in old contracts is recoverable
by its **rightful owners** — each contributor calls a normal public refund function that returns
**only their own deposit**. No custody, no intermediary contract, the owner signs; every recovery
is reproducible on Etherscan against the contract's real deployed bytecode.

This is a contribution to **[ForgottenETH](https://forgotteneth.com)** ([repo](https://github.com/q84c6tsm95-create/forgotten-eth)) — the
reference registry for stuck on-chain ETH. Six of the targets below are **net-new** (not previously
on ForgottenETH), found by a discovery sweep beyond its curated set, and contributed to it in
[ForgottenETH PR #15](https://github.com/q84c6tsm95-create/forgotten-eth/pull/15).

> Same ethos as ForgottenETH: **no custody, owner signs, reproducible on Etherscan.** A fork-proof
> is the sole oracle — nothing here is asserted that a `forge test` against live mainnet state can't show.

## Proven targets

10 contracts, ~517 ETH, each with a committed fork-proof + safety audit. **★ = net-new beyond ForgottenETH.**

| Contract | ETH | Owners | Recovery (public, self-paying) | Proof |
|---|---:|---:|---|---|
| ★ [DigiPulse](https://etherscan.io/address/0x9aca6abfe63a5ae0dc6258cefb65207ec990aa4d) | 100.6 | 79 | `refundEther()` | [DigiPulseRefund.t.sol](test/DigiPulseRefund.t.sol) |
| [Ahoolee Token Sale](https://etherscan.io/address/0x575cb87ab3c2329a0248c7d70e0ead8e57f3e3f7) | 191.5 | 106 | `refund()` | [AhooleeRefund.t.sol](test/AhooleeRefund.t.sol) |
| ★ [DirectCrypt Presale](https://etherscan.io/address/0x12d5b7c26dd8dc6e2f71f5bf240d5e76452b2fe5) | 81.9 | 32 | `refund()` | [DirectCryptRefund.t.sol](test/DirectCryptRefund.t.sol) |
| ★ [QCOToken](https://etherscan.io/address/0x3a8a97123bccd826228e5eb4144b48cce169517b) | 31.5 | 56 | `requestRefund()` | [QCOTokenRefund.t.sol](test/QCOTokenRefund.t.sol) |
| ★ [hodlEthereum](https://etherscan.io/address/0x1bb28e79f2482df6bf60efc7a33365703bcf1536) | 22.5 | 11 | `party()` | [HodlEthereumRefund.t.sol](test/HodlEthereumRefund.t.sol) |
| ★ [Blocklancer](https://etherscan.io/address/0x9ea80e204045329ba752d03c395f82a12799f13d) | 21.7 | 28 | `refund()` | [BlocklancerRefund.t.sol](test/BlocklancerRefund.t.sol) |
| ★ [ZTCrowdsale](https://etherscan.io/address/0xaf7aea249098f2c2f50cc11d4000ccf798194373) | 21.2 | 11 | `endCrowdsale()` → `refund()` | [ZTCrowdsaleRefund.t.sol](test/ZTCrowdsaleRefund.t.sol) |
| [Jincor Token ICO](https://etherscan.io/address/0xb3b33f59174f2ef62167770e4c9cabaa3879eb5d) | 19.0 | 48 | `refund()` | [JincorRefund.t.sol](test/JincorRefund.t.sol) |
| [AgroTechFarm](https://etherscan.io/address/0x3fd30f3e1fbf4f3ea6bdf3e3bb11826266708869) | 16.7 | 12 | `refund()` | [AgroTechFarmRefund.t.sol](test/AgroTechFarmRefund.t.sol) |
| [Luckchemy](https://etherscan.io/address/0x18777aec0b231d1a4a9c66b51253088a03affdfc) | 10.8 | 23 | `withdraw()` | [LuckchemyRefund.t.sol](test/LuckchemyRefund.t.sol) |

Each proof pranks a **real unclaimed contributor**, asserts the exact ETH lands with them, that a
second call can't double-claim, that a non-contributor gets nothing, and that **the owner/admin
cannot drain** the funds. The four non-★ contracts are already on ForgottenETH; their proofs are
included for completeness.

The Owners column counts all unclaimed addresses with a refundable ledger entry. The ForgottenETH
contribution ([PR #15](https://github.com/q84c6tsm95-create/forgotten-eth/pull/15)) filters these
further to **self-claimable EOAs** (209 owners, ~261.7 ETH) — excluding contracts and exchange/service
hot wallets (e.g. Bittrex, Poloniex) whose deposits no end user can claim.

## Verify it yourself

```bash
git clone --recurse-submodules https://github.com/webmixgamer/stuck-eth-recoveries
cd stuck-eth-recoveries
cp .env.example .env        # add any mainnet RPC key (Alchemy/Infura free tier is plenty)
forge test --match-path "test/*Refund.t.sol" -vv
# => 31 passed (10 targets). Runs against live mainnet state via fork; no setup beyond an RPC.
```

## How these were found and proven

1. **Discovery** — a free BigQuery `balances⨝contracts` sweep (>10 ETH, pre-2019), minus the
   ForgottenETH set → [`scripts/scan_addresses.py`](scripts/scan_addresses.py) →
   [`scripts/detect_open_refund.py`](scripts/detect_open_refund.py) (AST detector for the
   "pays `msg.sender` their own `ledger[msg.sender]`" signature). Full funnel + dismissed
   false-positives in [`docs/DISCOVERY_RESULTS.md`](docs/DISCOVERY_RESULTS.md).
2. **Safety audit** ([`scripts/safety_check.py`](scripts/safety_check.py), [`docs/targets/SAFETY_*.md`](docs/targets/)) —
   immutable bytecode (no delegatecall/selfdestruct), the only owner ETH-out path is permanently gated shut.
3. **Owner enumeration** ([`scripts/enumerate_owners.py`](scripts/enumerate_owners.py)) — the
   self-claimable EOA contributors and their amounts ([`docs/targets/owners_*.json`](docs/targets/)).
4. **Fork-proof** — the `test/*Refund.t.sol` above. The proof is the only thing that decides "recoverable".

Per-owner recovery packages (the exact tx each owner signs, value 0) are in
[`docs/targets/package_*.md`](docs/targets/); plain-language claim pages in [`claims/`](claims/).

## Legal / ethical

Low-risk by construction: these are **stuck funds returned to their original contributors**, via the
contract's own intended refund path, with the **owner signing their own transaction**. No exploit, no
custody, no front-running (the refund pays only the caller's own deposit) — and the agent that produced
these proofs never holds funds or signs a mainnet transaction.

## Credit

[ForgottenETH](https://forgotteneth.com) and [banteg](https://github.com/banteg) built the reference
for this problem space (157k+ ETH mapped). This repo is an additive contribution in the same spirit.
