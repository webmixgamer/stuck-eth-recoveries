# Verified unclaimed-refund claims — Jincor Token ICO (2017)

**Contract:** [`0xB3B33F59174f2eF62167770E4C9cAbaA3879eB5d`](https://etherscan.io/address/0xB3B33F59174f2eF62167770E4C9cAbaA3879eB5d) · **Stuck balance:** 19.0616 ETH · **Unclaimed owners:** 48 · **Recoverable:** 19.0616 ETH · *as of 2026-06-02*

## What this is
This Jincor Token ICO (2017) sale did not reach its soft cap, so its on-chain `refund()` function is **permanently open**. Most contributors already refunded years ago; the addresses below never did. Each can still reclaim **their own deposit** today.

## How to claim (read carefully — this is NOT a phishing message)
- You call **one** function on the original contract: `refund()` (calldata `0x590e1ae3`), **value 0**, from the SAME address that contributed.
- It sends **your own deposit** back to you. It cannot send your funds anywhere else, and no one else can claim on your behalf (the refund is gated on *your* address).
- **We never ask for your seed phrase, private key, or any payment, and we never need an `approve`.** Anyone telling you otherwise is scamming you.
- You can verify the contract + the exact call on Etherscan before signing.

## Safety attestation
- Bytecode audit: **no DELEGATECALL / SELFDESTRUCT (immutable, not upgradeable, not destructible)**.
- The only functions that move ETH are `refund()` (this claim) and an owner `withdraw()` that is **permanently blocked** (requires a soft-cap that can never be reached).
- No ETH has left the contract since 2018; an automated scavenger that tried `drain()/sweep()/destroy()` extracted nothing (those functions don't exist).
- The recovery was reproduced on a mainnet fork (the contract's real deployed code).

## Unclaimed owners (addresses are already public on-chain; no identities)
| # | Address | Recoverable ETH |
|---|---|---|
| 1 | `0x916ddd79b8c8202f22451da16d32b7f96d4b0825` | 2.2000 |
| 2 | `0x02f847950502b743087975989f4cca27a7594315` | 1.4960 |
| 3 | `0x09d95cd9459866c6aa9e40d841456dd909fe8aeb` | 1.4660 |
| 4 | `0x0a3e301f912462feba1a7c1e03260a0ff1cd2729` | 1.3060 |
| 5 | `0x9e8d2c2e57d17a937934bcdbd8d8ed4db8906193` | 0.9860 |
| 6 | `0xcb47d7aa413797a6516e19767e60d86535ef3d4b` | 0.7460 |
| 7 | `0x1667476ebe2cad9ac0bc2f73101dbcd15517c6c7` | 0.6220 |
| 8 | `0xca24a44577b3229bfd07e5249394ee169e5ba090` | 0.5954 |
| 9 | `0x614e2228fe59c6df209093754ee85c1e14af8b27` | 0.4940 |
| 10 | `0x1186c3b7241ed95daaa6ec0a2838f820afe4fc59` | 0.4910 |
| 11 | `0x01cf514d1bfc802572e98b8294bb30e2d8d3462d` | 0.4900 |
| 12 | `0xf87183b8c61fe06671112eb26c5670bb4375146c` | 0.4900 |
| 13 | `0xefd25ac201ec78a1ea6f8d30734a07d77487fa25` | 0.4860 |
| 14 | `0x8d3004bd966006c927cb6ee1bca86120c53b02ef` | 0.4277 |
| 15 | `0x3c2ac7f8390f05d1d8b299220c97ba3a6d74e90a` | 0.3880 |
| 16 | `0xad44f2693ce6f61f954cc967446cbcb67da229ba` | 0.3770 |
| 17 | `0x08ad5bd4aee30d70bac4955c2dc7b8d737524502` | 0.3602 |
| 18 | `0x945c4259eae1b611b4995c3959747860a9c259cf` | 0.2950 |
| 19 | `0xdab5d172df9d2a75b436302e53700910ac160ed6` | 0.2910 |
| 20 | `0x6f768abe524efd4e445f76d7b4a841559925fda5` | 0.2894 |
| 21 | `0xa93742cc229acd275d4fb3eb34d601d1e1237b89` | 0.2860 |
| 22 | `0x6d11d789c8fd011af75ab4e6620b0515c6b4f8f1` | 0.2660 |
| 23 | `0x4781e47a80838218700053de91cc8ae7fc4788bf` | 0.2560 |
| 24 | `0x2ac7836a33c2a643ded8d052c4121e3d5e3e27d2` | 0.2560 |
| 25 | `0x4d35f883c09b8b13079499ee1a37328d430d5780` | 0.2460 |
| 26 | `0x7febdb8c142b2d930682fad79298ce274d2b0f2b` | 0.2431 |
| 27 | `0x8685b27f2688c8639e8c537bb1139edae40886b4` | 0.2210 |
| 28 | `0x39d1767e6e4baabead81cbcd8185079a05cc579c` | 0.2160 |
| 29 | `0x25553d9960b27a3e149a42c8e04f3bca527dc3b8` | 0.2120 |
| 30 | `0x7ce181a1a6ad8f566e7c4b587158895bcddb69dd` | 0.2096 |
| 31 | `0xbbd546d8bf90bf1c05827974f9df94f81d095f70` | 0.1960 |
| 32 | `0xa948e33e6997e695c4ef0665ab70267413fbc84b` | 0.1960 |
| 33 | `0xcce9be82d9fd85371def1f0f4e57f312303f5b8f` | 0.1860 |
| 34 | `0x5ac6994a233fb7fe0de695eab68fa31823f76f13` | 0.1560 |
| 35 | `0x742fa7b453cf1d0677638bc12544397dd9cfb476` | 0.1360 |
| 36 | `0xd5922d17616b8c69e1655a7adf6136ccfff67b89` | 0.1360 |
| 37 | `0x4d3702a764f7005fd4e911509b1ed002b71f94b2` | 0.1260 |
| 38 | `0x4e999438917ae9bbe85f5bab6078b656f5594372` | 0.1260 |
| 39 | `0x3524dc82ae1ab5046e83877d1af8557fb30539cf` | 0.1255 |
| 40 | `0x48cdacb3d6f7104c13ae33933eca3688fb8958d3` | 0.1210 |
| 41 | `0x446b3ae44fa66865fb4afe0981d724377f01a6e7` | 0.1158 |
| 42 | `0xed0226556efcedb012ab9c55ad8b15b02f482a4b` | 0.1110 |
| 43 | `0xd7fe28d46e7d73b95795a202a5681db8999849fc` | 0.1100 |
| 44 | `0xb9b520d26066cc460b711df116501459be3eed61` | 0.1040 |
| 45 | `0x2241e557551bb10b10d6da8e387206e068d80b14` | 0.1040 |
| 46 | `0x3157d48812aff7c24d557bdabee6c81d94dd71bb` | 0.1039 |
| 47 | `0x06953644550ba5b43e7c64cac054aa8f09a06f14` | 0.1000 |
| 48 | `0x4abd2fbcf96fe989f3c8f60d766588b1a0ae427b` | 0.1000 |

## Verify everything yourself
- Fork-proof + tooling (open source): `github.com/webmixgamer/white-hat-recovery-agent` *(make public before publishing this page)*
- Fork-proof test: `test/JincorRefund.t.sol`
- This recovery is **owner-signs / no-custody**: we never hold or move your funds; you sign your own claim.

