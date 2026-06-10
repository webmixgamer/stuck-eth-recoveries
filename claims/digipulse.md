# Verified unclaimed-refund claims — DigiPulse (DGT) Token Sale (2017)

**Contract:** [`0x9AcA6aBFe63A5ae0Dc6258cefB65207eC990Aa4D`](https://etherscan.io/address/0x9AcA6aBFe63A5ae0Dc6258cefB65207eC990Aa4D) · **Stuck balance:** 100.5835 ETH · **Unclaimed owners:** 79 · **Recoverable:** 97.0835 ETH · *as of 2026-06-10*

## What this is
The **DigiPulse (DGT)** token sale ran in August 2017 and raised roughly 1,920 ETH against an 8,000 ETH minimum. When `finalise()` was called the balance was below that minimum, so the contract permanently set `icoFailed = true`, which opens refunds. 590 addresses contributed; most have already reclaimed their ETH, but the 79 addresses below never called the refund — their **97.08 ETH** is still sitting in the contract. Each can reclaim **their own deposit** today by calling `refundEther()` from the address that contributed.

## How to claim (read carefully — this is NOT a phishing message)
- You call **one** function on the original contract: `refundEther()` (calldata `0x560ed6a1`), **value 0**, from the SAME address that contributed.
- It sends **your own deposit** back to you. It cannot send your funds anywhere else, and no one else can claim on your behalf (the refund is gated on *your* address).
- **We never ask for your seed phrase, private key, or any payment, and we never need an `approve`.** Anyone telling you otherwise is scamming you.
- You can verify the contract + the exact call on Etherscan before signing.

## Safety attestation
- Code immutability: **the deployed code is the Etherscan-verified Solidity source (compiler 0.4.13) and contains no `delegatecall`, `callcode`, `selfdestruct` or assembly — it cannot be upgraded or destroyed**.
- The only function that could send ETH to the project owner, `withdrawFundsToOwner()`, is **permanently blocked**: it requires `icoFulfilled == true`, which is false and can never become true (the contract already latched `icoFailed`, and `finalise()` refuses to run again). The owner cannot take these funds — confirmed on a mainnet fork.
- The refund switch (`icoFailed`) is one-way — no function can turn it back off — and the contribution window closed in 2017, so the refund cannot be re-closed. The only ETH that has ever left the contract is contributor refunds.
- The recovery was reproduced on a mainnet fork (the contract's real deployed code).

## Unclaimed owners (addresses are already public on-chain; no identities)
| # | Address | Recoverable ETH |
|---|---|---|
| 1 | `0xc4a03dba02a43490fb94ca3c019d5bb0fe006711` | 10.0000 |
| 2 | `0xfbb1b73c4f0bda4f67dca266ce6ef42f520fbb98` | 5.5158 |
| 3 | `0x7b4eaf72539e2f54dd160d54185fe1d0533734f3` | 5.0000 |
| 4 | `0xf506540f35bac10fe0078909f0c0eeb403406364` | 5.0000 |
| 5 | `0xf3153f952260b1a8ab9e6e537203b2b691575b2e` | 5.0000 |
| 6 | `0x32be343b94f860124dc4fee278fdcbd38c102d88` | 3.4437 |
| 7 | `0xcf2819e383723f823f072dacca109436ae3ce7e0` | 3.0800 |
| 8 | `0xcab96a30333a46b766a348e939335b03df59afb5` | 3.0000 |
| 9 | `0x754485ed993165c804a32df01b35019d22580acd` | 3.0000 |
| 10 | `0x915e9effab855cf9b5940f0a83a252b0b85d13be` | 3.0000 |
| 11 | `0x6616c5c49b31cdad9e79db383341c59143b738e8` | 3.0000 |
| 12 | `0x67fb29be6404a1e467168aa1e524fb798fd41fa2` | 3.0000 |
| 13 | `0x173e96f898fe63e08326bda7a3948646ebb366df` | 3.0000 |
| 14 | `0x0cfe248ddd32add7b3efbc1b540185b99aa2140a` | 2.3885 |
| 15 | `0x6c023c08d7d47d06a9cb6aa84d76b1a3c2e7948b` | 2.0000 |
| 16 | `0xb43944494daee5c08a84ad768b0942b4773ebb31` | 2.0000 |
| 17 | `0x4f605ad0b71ed4b19f2c369b11d49ac72881cb93` | 2.0000 |
| 18 | `0xd6a3a11548f82cdafd8bff454023ad65298821ca` | 2.0000 |
| 19 | `0x1521aea7fc112fd79ccbb8ff590ef0044798b060` | 2.0000 |
| 20 | `0xc1f4efd3efe48ddc18834d06f8a0e1697dc1cdf2` | 2.0000 |
| 21 | `0x27014067f656db071740f3205f56b0a13a39aa99` | 2.0000 |
| 22 | `0x46e56e4c807257caa443895aa43113beb96f7c80` | 1.5000 |
| 23 | `0xe3133ecabe6ae18f7ffd384e35aa3394282086b1` | 1.5000 |
| 24 | `0x72727667ea73e5b0a1612d7d685b205c78ae4748` | 1.2000 |
| 25 | `0x5c2e90c6a7abf1adc50efe38c518d394bbdf3c42` | 1.0000 |
| 26 | `0xdf48f1586f07dc4f6d02192cad51e8d56401864e` | 1.0000 |
| 27 | `0xa402d0d37555670d60e4e51bd242e7cc3ef1b07f` | 1.0000 |
| 28 | `0x47b7420abe764b96e039380635b96eb97c60d0e1` | 1.0000 |
| 29 | `0x7e643653c95586cced5a53bcb46f62f0b6a29d6c` | 1.0000 |
| 30 | `0x14128502fd9848090812dbef5857e8d6034158ce` | 1.0000 |
| 31 | `0x212f2e6caac9553307ccd871f0d09ac7318bce84` | 1.0000 |
| 32 | `0x03b9457f4b3e38d63e2e3ca2643c67db42736c2a` | 1.0000 |
| 33 | `0x3074b30349574ff342b7dac4de924ef1408733c9` | 1.0000 |
| 34 | `0x5cb501bb7badba627d05366700b7f7bf2bca982a` | 0.9700 |
| 35 | `0xa96e7f906c33ae139c89b81352de57226c3cf8c5` | 0.9180 |
| 36 | `0x7ed1e469fcb3ee19c0366d829e291451be638e59` | 0.8617 |
| 37 | `0x62121c02fcf1449b1a06419b534571e0f94bea31` | 0.7500 |
| 38 | `0xb7e17d6397a1279366908f32c0e963c9eac191f1` | 0.7000 |
| 39 | `0xe94336e44faad2ac683bc889e35d8de48080295c` | 0.6000 |
| 40 | `0x4f01424d91728377532292e2079dba97bba490d5` | 0.5000 |
| 41 | `0x6046d7759ebcc6abc7623fa2394c7668b549b501` | 0.5000 |
| 42 | `0xe9415f47799275cbbf920a5db4d585bc832a0c78` | 0.5000 |
| 43 | `0x243b456e2302b2835220d53b47dcf248f54f97a1` | 0.5000 |
| 44 | `0x45708caffcf9cf3c2f864b8f3af4775b4f041eda` | 0.4835 |
| 45 | `0xd9f54bdfdc73e743299036db59c40c7e04538c3c` | 0.4000 |
| 46 | `0x611ce71cb0535db63fea8d7aea648352b42bc832` | 0.4000 |
| 47 | `0x6165398be703bfdb015f2e94cec864875b2997ea` | 0.3600 |
| 48 | `0x61676a8f3c78d8dfaa42096935ffd6685f6b9dfc` | 0.3400 |
| 49 | `0x3d78643ecfc36aee85074d5781245a183bd791b5` | 0.3000 |
| 50 | `0xecffa1e18ef74ce967e6493b8b7d5ce6bcfb46fa` | 0.2786 |
| 51 | `0x48ae7ea7038973e4dd8316cb37ffd01a8b3b9828` | 0.2715 |
| 52 | `0x2f55e36764003aac8c03806503e8f9a9063a6699` | 0.2500 |
| 53 | `0xf89e92d073db46b5beb9be5463378cde924a567d` | 0.2213 |
| 54 | `0x81a60c1ac4a1f75ec5cb727a768f67b5641b095b` | 0.2109 |
| 55 | `0xb74ac951bac064d4755b62743c55cb10733402db` | 0.2085 |
| 56 | `0x1812cba5cc0f7a4723ad5c7df044102049868ea0` | 0.2000 |
| 57 | `0x6b0edc2d00c2dfe9b95bddf25888058b6417614c` | 0.2000 |
| 58 | `0xbdf7363dc5face995a152a2f7355ac4182dd836d` | 0.2000 |
| 59 | `0x272cd7502e1d902bf1aa129983bf49425cb09e20` | 0.1943 |
| 60 | `0xcc8298078000d44e1bd98740e1528474a8a00b19` | 0.1537 |
| 61 | `0xd4fae84d8619afb31adc2c77dc031f8f41b48af4` | 0.1500 |
| 62 | `0x80009cd3ac6446bfb1a7eeb876a2dbb5283c92a4` | 0.1070 |
| 63 | `0x2be8a55bef89a7685d94e27a64402526df5e89e0` | 0.1000 |
| 64 | `0x73da5c235a4fb1a74cbc0148272db53828c0cda3` | 0.1000 |
| 65 | `0xfc62cdc5afd5512102e6b2c572549c5759734d1c` | 0.0952 |
| 66 | `0x44d2fd6d3908dadef2f90dc6e9cd878753df2b8d` | 0.0900 |
| 67 | `0xdea8605f24b3f5840ab4932c79e63723daa53009` | 0.0882 |
| 68 | `0x9fef4d2d76b36cc72310dbe08c200205da9c61b3` | 0.0480 |
| 69 | `0x70b58d9266460ef5d8f90654de25e09227249abf` | 0.0440 |
| 70 | `0x36b0fd7efe0b121feae1f97938deeff468b792b4` | 0.0335 |
| 71 | `0xfba2ce6ea29efc03614a20f7ab8cbeb01c62faad` | 0.0300 |
| 72 | `0xd24400ae8bfebb18ca49be86258a3c749cf46853` | 0.0200 |
| 73 | `0x5c792fa12df665146f4fb6d4b61fcc82eb8757e7` | 0.0165 |
| 74 | `0x84f76b82f12c7c8bcaf40158bd33aefd173e9782` | 0.0150 |
| 75 | `0xc183f8134fb0d93cc48cf32001007231386b36fb` | 0.0110 |
| 76 | `0xe0ddd355c17200ed3f4835c07dffbe36822cd0a6` | 0.0100 |
| 77 | `0x5fb28453b5ea250ada0b42cc2cda1fa298e5f797` | 0.0100 |
| 78 | `0x52a4d65de46fa9126f108d21da6a54e649d990b7` | 0.0100 |
| 79 | `0xe1ae08fd0e212be0d7da0e748fce6b313c8f2e7a` | 0.0050 |

## Verify everything yourself
- Fork-proof + tooling (open source): `github.com/webmixgamer/stuck-eth-recoveries`
- Fork-proof test: `test/DigiPulseRefund.t.sol`
- This recovery is **owner-signs / no-custody**: we never hold or move your funds; you sign your own claim.

