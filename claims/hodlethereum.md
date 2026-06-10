# Verified unclaimed-refund claims — hodlEthereum Time-Locked Vault (2017)

**Contract:** [`0x1bb28e79f2482df6bf60efc7a33365703bcf1536`](https://etherscan.io/address/0x1bb28e79f2482df6bf60efc7a33365703bcf1536) · **Stuck balance:** 22.5281 ETH · **Unclaimed owners:** 11 · **Recoverable:** 22.5281 ETH · *as of 2026-06-10*

## What this is
**hodlEthereum** (2017) is a time-locked vault: each depositor's ETH was credited to their own address (`hodlers[you] += msg.value`) and became reclaimable after **30 July 2020** via `party()`. 11 depositors never withdrew — their **22.53 ETH** is the full contract balance. Each can reclaim it today by calling `party()` from the address that deposited.

## How to claim (read carefully — this is NOT a phishing message)
- You call **one** function on the original contract: `party()` (calldata `0x354284f2`), **value 0**, from the SAME address that contributed.
- It sends **your own deposit** back to you. It cannot send your funds anywhere else, and no one else can claim on your behalf (the refund is gated on *your* address).
- **We never ask for your seed phrase, private key, or any payment, and we never need an `approve`.** Anyone telling you otherwise is scamming you.
- You can verify the contract + the exact call on Etherscan before signing.

## Safety attestation
- Code immutability: **the contract has **no owner, no admin, no pause and no sweep**; the deployed code is the Etherscan-verified source (solc 0.4.11) with no `selfdestruct`/`delegatecall`/assembly — it is fully immutable**.
- There is no owner or admin at all: ETH can leave only via `party()`, only to the original depositor, only in the amount they deposited.
- The unlock date (30 July 2020) is a hard-coded constant that can never change; the only ETH leaving the contract has been depositors withdrawing their own funds.
- The recovery was reproduced on a mainnet fork (the contract's real deployed code).

## Unclaimed owners (addresses are already public on-chain; no identities)
| # | Address | Recoverable ETH |
|---|---|---|
| 1 | `0xf11cc2152d3e1e44825eb4cc71eac0e9a6f5f2b1` | 20.0000 |
| 2 | `0x25e52afe36b12a136df044e026f7aef22dd93b7a` | 1.0000 |
| 3 | `0x4812505f744b14813d27d641c8af4d74f13c92bf` | 1.0000 |
| 4 | `0xfdb33f8ac7ce72d7d4795dd8610e323b4c122fbb` | 0.3300 |
| 5 | `0x06603aae348bea45a9cc23ade04296301c1d781d` | 0.1000 |
| 6 | `0x8f231e179727784b83351044b272dfb4c4615634` | 0.0400 |
| 7 | `0xcd8e71a93b3cc8417c0dff1ed66d876abba7f9ef` | 0.0300 |
| 8 | `0x7c2c647579f3efcf1ac86751ea7b130712add7a9` | 0.0100 |
| 9 | `0xb9109ab4dcf8ac17f9d7db248dcdb60bd45b77d8` | 0.0100 |
| 10 | `0x8bb5047103cb24da5b5ea9848daa1b9fa2a9bb66` | 0.0081 |
| 11 | `0x16882f55ef843d062ce799805af50cda4240be52` | 0.0000 |

## Verify everything yourself
- Fork-proof + tooling (open source): `github.com/webmixgamer/stuck-eth-recoveries`
- Fork-proof test: `test/HodlEthereumRefund.t.sol`
- This recovery is **owner-signs / no-custody**: we never hold or move your funds; you sign your own claim.

