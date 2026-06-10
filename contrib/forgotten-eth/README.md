# ForgottenETH contribution — staged, NOT yet submitted

Prepared artifacts to contribute our 6 fork-verified failed-ICO refund vaults to
[forgotten-eth](https://github.com/q84c6tsm95-create/forgotten-eth). Review before submitting.

## What's here
- `balances/<key>_eth_balances.json` (6) — per-holder claimable amounts in ForgottenETH's exact
  schema (EOA-only, reconciled to the live balance). Copy into their `data/balances/`.
- `protocols_entries.json` — the 6 entries to merge into their `data/protocols.json`.
- `PR_DESCRIPTION.md` — forensic-grade PR body (follows their `docs/templates/banteg-forensic-report.md`).
- `CHANGELOG_row.md` — the changelog line to add.

## How a PR is assembled (verified against their merged PRs #2/#10/#12)
1. Fork their repo; for each protocol: add `data/balances/<key>_eth_balances.json` + an entry in
   `data/protocols.json`.
2. Add the CHANGELOG row (+ optional README count bump).
3. **Do NOT touch** `data/index_shards/`, `data/table_meta/`, `data/total.json`,
   `data/protocol_info.json` — the maintainer's pipeline regenerates those (PR #12 skipped them).
4. Open the PR with `PR_DESCRIPTION.md` as the body.

## Totals
209 self-claimable EOA owners · ~261.7 ETH · all 6 absent from the current 259-entry registry.
(Exchange/service hot wallets — Bittrex, Poloniex + 4 service-scale addresses — excluded as not self-claimable.)

| key | name | owners | ETH | recovery |
|---|---|---:|---:|---|
| digipulse_token_sale | DigiPulse (DGT) Token Sale | 75 | 87.24 | `refundEther()` |
| directcrypt_presale | DirectCrypt Token Presale | 32 | 81.89 | `refund()` |
| qcotoken_ico | QCOToken (Quantum1Net) Sale | 56 | 31.50 | `requestRefund()` |
| hodl_ethereum | hodlEthereum | 11 | 22.53 | `party()` |
| blocklancer_ico | Blocklancer (LNC) Token Sale | 24 | 17.39 | `refund()` |
| ztcrowdsale | ZTCrowdsale (ZeroTraffic) | 11 | 21.17 | `endCrowdsale()`→`refund()` (multi_step) |

Regenerate from our proven data: `python3 scripts/make_feth_contribution.py`
