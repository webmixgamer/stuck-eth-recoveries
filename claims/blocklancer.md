# Verified unclaimed-refund claims — Blocklancer (LNC) Token Sale (2017)

**Contract:** [`0x9EA80e204045329Ba752D03C395F82A12799f13d`](https://etherscan.io/address/0x9EA80e204045329Ba752D03C395F82A12799f13d) · **Stuck balance:** 21.6614 ETH · **Unclaimed owners:** 28 · **Recoverable:** 21.6614 ETH · *as of 2026-06-10*

## What this is
The **Blocklancer (LNC)** token sale (2017) did not reach its minimum cap, so its on-chain `refund()` is open: each contributor reclaims **their own deposit**. 28 contributors never did — their **21.66 ETH** is the full contract balance. Each can reclaim it today by calling `refund()` from the address that contributed.

## How to claim (read carefully — this is NOT a phishing message)
- You call **one** function on the original contract: `refund()` (calldata `0x590e1ae3`), **value 0**, from the SAME address that contributed.
- It sends **your own deposit** back to you. It cannot send your funds anywhere else, and no one else can claim on your behalf (the refund is gated on *your* address).
- **We never ask for your seed phrase, private key, or any payment, and we never need an `approve`.** Anyone telling you otherwise is scamming you.
- You can verify the contract + the exact call on Etherscan before signing.

## Safety attestation
- Code immutability: **the deployed code is the Etherscan-verified Solidity source and contains no `delegatecall`, `callcode`, `selfdestruct` or assembly — it cannot be upgraded or destroyed**.
- The project (`master`) cannot take this ETH: its only withdrawal path, `finalize()`, reverts for this failed raise (it requires the token cap to be nearly reached) — verified on a mainnet fork. The fact that refunds are open confirms the sale was never finalized.
- The only ETH that has ever left the contract is contributor refunds.
- The recovery was reproduced on a mainnet fork (the contract's real deployed code).

## Unclaimed owners (addresses are already public on-chain; no identities)
| # | Address | Recoverable ETH |
|---|---|---|
| 1 | `0x61e120b9ca6559961982d9bd1b1dbea7485b84d1` | 7.0000 |
| 2 | `0x7f7c64c7b7f5a611e739b4da26659bf741414917` | 2.6950 |
| 3 | `0x32be343b94f860124dc4fee278fdcbd38c102d88` | 2.0850 |
| 4 | `0x33d94224754c122baa1ebaf455d16a9c82f69c98` | 1.3000 |
| 5 | `0xbf022480bda3f6c839cd443397761d5e83f3c02b` | 1.1600 |
| 6 | `0x5baeac0a0417a05733884852aa068b706967e790` | 1.0849 |
| 7 | `0x267be1c1d684f78cb4f6a176c4911b741e4ffdc0` | 1.0000 |
| 8 | `0xd70837a61a322f69ba3742111216a7b97d61d3a7` | 1.0000 |
| 9 | `0x08bea4ccc9c45e506d5bc5e638acaa13fa3e801c` | 0.9400 |
| 10 | `0xfeb063bd508b82043d6b4d5c51e1e42b44f39b33` | 0.5000 |
| 11 | `0x266dccd07a275a6e72b6bc549f7c2ce9e082f13f` | 0.2900 |
| 12 | `0x0764d446d0701a9b52382f8984b9d270d266e02c` | 0.2803 |
| 13 | `0x3afd1483693fe606c0e58f580bd08ae9aba092fd` | 0.2800 |
| 14 | `0x41bacae05437a3fe126933e57002ae3f129aa079` | 0.2500 |
| 15 | `0x0d4266de516944a49c8109a4397d1fcf06fb7ed0` | 0.2344 |
| 16 | `0xe922c94161d45bdd31433b3c7b912ad214d399ce` | 0.2000 |
| 17 | `0x6c1ddafafd55a53f80cb7f4c8c8f9a9f13f61d70` | 0.2000 |
| 18 | `0x30382b132f30c175bee2858353f3a2dd0d074c3a` | 0.2000 |
| 19 | `0x404b688a1d9eb850be2527c5dd341561cfa84e11` | 0.2000 |
| 20 | `0x330c63a5b737b5542be108a74b3fef6272619585` | 0.1800 |
| 21 | `0x7398a2edb928a2e179f62bfb795f292254f6850e` | 0.1500 |
| 22 | `0x7ed1e469fcb3ee19c0366d829e291451be638e59` | 0.1017 |
| 23 | `0x03c6c82a1d6d13b2f92ed63a10b1b791ffaa1e02` | 0.1000 |
| 24 | `0xe59e4aac45862796cb52434967cf72ea46474ff3` | 0.1000 |
| 25 | `0x7a5159617df20008b4dbe06d645a1b0305406794` | 0.0800 |
| 26 | `0x555cbe849bf5e01db195a81ecec1e65329fff643` | 0.0300 |
| 27 | `0x4d8a7cb44d317113c82f25a0174a637a8f012ebb` | 0.0100 |
| 28 | `0xcb12b8a675e652296a8134e70f128521e633b327` | 0.0100 |

## Verify everything yourself
- Fork-proof + tooling (open source): `github.com/webmixgamer/white-hat-recovery-agent` *(make public before publishing this page)*
- Fork-proof test: `test/BlocklancerRefund.t.sol`
- This recovery is **owner-signs / no-custody**: we never hold or move your funds; you sign your own claim.

