# Verified unclaimed-refund claims — QCOToken / Quantum1Net Sale (2018)

**Contract:** [`0x3a8a97123bccd826228e5eb4144b48cce169517b`](https://etherscan.io/address/0x3a8a97123bccd826228e5eb4144b48cce169517b) · **Stuck balance:** 31.4974 ETH · **Unclaimed owners:** 57 · **Recoverable:** 31.4954 ETH · *as of 2026-06-10*

## What this is
The **QCOToken** (Quantum1Net) sale ended in the **Aborted** state, so its on-chain `requestRefund()` is open: each contributor reclaims **their own deposit**. 57 contributors never did — their **31.50 ETH** is the full contract balance. Each can reclaim it today by calling `requestRefund()` from the address that contributed.

## How to claim (read carefully — this is NOT a phishing message)
- You call **one** function on the original contract: `requestRefund()` (calldata `0xd5cef133`), **value 0**, from the SAME address that contributed.
- It sends **your own deposit** back to you. It cannot send your funds anywhere else, and no one else can claim on your behalf (the refund is gated on *your* address).
- **We never ask for your seed phrase, private key, or any payment, and we never need an `approve`.** Anyone telling you otherwise is scamming you.
- You can verify the contract + the exact call on Etherscan before signing.

## Safety attestation
- Code immutability: **the deployed code is the Etherscan-verified Solidity source and contains no `delegatecall`, `callcode`, `selfdestruct` or assembly — it cannot be upgraded or destroyed**.
- The owner cannot take this ETH: the only owner withdrawal path requires the `Operational` state, which is permanently unreachable from `Aborted`. The Aborted state is terminal — no function leaves it — so refunds stay open forever.
- The only ETH that has ever left the contract is contributor refunds.
- The recovery was reproduced on a mainnet fork (the contract's real deployed code).

## Unclaimed owners (addresses are already public on-chain; no identities)
| # | Address | Recoverable ETH |
|---|---|---|
| 1 | `0x0f929995c0c8a00e212df802f57b5f63d7640fe7` | 11.4000 |
| 2 | `0xa2cc3fd7bc2980e0b6362222b75baaec3ba7b973` | 2.6538 |
| 3 | `0x4f1622147432d6280eeb72e2a597bd909efe9b56` | 1.8000 |
| 4 | `0x0e3837631a57b93b31f3d9c371d49c0272355bbb` | 1.0000 |
| 5 | `0x2007035a0ac890636cc223efe34b4647bb73d8c8` | 1.0000 |
| 6 | `0xddd39081d41213020121ca6e8a1b55e5c2722da6` | 1.0000 |
| 7 | `0x702554c2eedce00e2fa3ad77b792e31f4b206d79` | 1.0000 |
| 8 | `0x5fc36a6378e042067fbb0438006885622e40a9de` | 1.0000 |
| 9 | `0xca1d46966a4a89d64602b19e585b34407ab98920` | 1.0000 |
| 10 | `0x011d6ec42109b4718c99180645d468f67f3d841c` | 0.5500 |
| 11 | `0x38a54b444ae72dd0d0e4df553e87905502bad828` | 0.5200 |
| 12 | `0x0e1c23673c21684a88ce0cf2aa2bd5629426776a` | 0.5000 |
| 13 | `0x8c8622ff1fa96b6b174b0eb77aba7c455eefc15a` | 0.5000 |
| 14 | `0xe2d7466c97aac8a96c60ea292b5b99fff100a323` | 0.5000 |
| 15 | `0xc628152dbcb9d6807a598e9ab4fe9133b03ac1c2` | 0.5000 |
| 16 | `0x53866af3d5688ed9bf27b08608404502ed748e71` | 0.4000 |
| 17 | `0xa5ffaf70937ad0b9d85ec491c48fc83302fa85c8` | 0.4000 |
| 18 | `0x50101c76045b6ee9aa40c11c2b917a475a721935` | 0.3997 |
| 19 | `0xfa10d9c5b0961597b8caf449cb78690b2b36e03b` | 0.3580 |
| 20 | `0x8fca937b1b6990398e5e04578734a6d2a9f609cb` | 0.3100 |
| 21 | `0x32bf507e868be6ee718794a066ba2c7333b2836a` | 0.3031 |
| 22 | `0x8cb988b3b5444b5fb0ee19113c465aad9360704c` | 0.2950 |
| 23 | `0x98d8d51f7e2e5462b80096ed32958448d9be500b` | 0.2400 |
| 24 | `0x16e05c253c9bb9efc1748fd3edc181a7e07209a6` | 0.2400 |
| 25 | `0x0354ded5058c5ab4aa42f8260c2cc08904e7ee09` | 0.2160 |
| 26 | `0xd35405bfea25afaf7b7e3f4a3c929546ef26ee78` | 0.2020 |
| 27 | `0x3ae6792adbe6c03d028e2060564698384252e770` | 0.2014 |
| 28 | `0xb7a883569c1d1aafffdbdab06fe9616ce738a227` | 0.2000 |
| 29 | `0xc69dfbc00e53ef13ef712df518ab91f75b905514` | 0.2000 |
| 30 | `0xbba2cb74962001dcb46d794265ae35eac92c5756` | 0.2000 |
| 31 | `0x0652deba59f1685a25d3714e60eaaec7c8ba80ec` | 0.2000 |
| 32 | `0x5e313cdcc988570242144cc228f061bebce5a07a` | 0.2000 |
| 33 | `0x710a5f86f59c4215db3f6a9c8f0213bc5389d939` | 0.2000 |
| 34 | `0x02ac4f727fca7ba22c896b858e109f6323bcb3e9` | 0.1968 |
| 35 | `0x1f38696c7387f572088fc56b2245139d0c2c6eb8` | 0.1600 |
| 36 | `0x213f478b5c2d71f33257464457c67059e6021ed2` | 0.1500 |
| 37 | `0x3567ed0d8f3d9ee2683f6be579c156632945723b` | 0.1500 |
| 38 | `0x0425fc77abd3199de49e141eb109f2243c0930f7` | 0.1500 |
| 39 | `0x4c96b91f3f27137394d5b316e5b0c15dfe6d7da4` | 0.1110 |
| 40 | `0x03089363df31bdaa50313a235a3e8af98b403b0e` | 0.1000 |
| 41 | `0x276ee2ea6974183d02861bea0497862cf7262fd0` | 0.1000 |
| 42 | `0x72c54d2d19848e368893c75186fd8a434bf15eae` | 0.1000 |
| 43 | `0x363d9940ae06b1a4ed2f2028b8e2af647a8b0ecd` | 0.1000 |
| 44 | `0x7895f82357428f38b5738789feea9cf74560eb9b` | 0.0800 |
| 45 | `0x9cd98e067e126b3909c21c419fe61f7b42f14bdc` | 0.0700 |
| 46 | `0x962656db085b3750c9d769622217df8e5d56044a` | 0.0700 |
| 47 | `0x07ba7365f83ca3565780267a2e2c090f6a8525c0` | 0.0500 |
| 48 | `0xa73af3c91a2ed1570a35f9a3edd5ae4fe71e1db9` | 0.0500 |
| 49 | `0xcd79e561d8e535a99c2ec39b2cf816c4328a6bac` | 0.0400 |
| 50 | `0x47b01ddd6ab3bf7b85bbe6d4b8bdf10d9e23580c` | 0.0348 |
| 51 | `0x3b484bd4acf58f0fc97ce911713ffb2aeedcb1d9` | 0.0200 |
| 52 | `0x66982c1abeb45461cb2aeff853f954dbb0d59b57` | 0.0200 |
| 53 | `0xcc93e4678c2d729aafc019d4cb5b33132db3a7d3` | 0.0200 |
| 54 | `0xf91e312983f4faa64db741bc356a2ced9feef60d` | 0.0180 |
| 55 | `0x35677c65e136c6f389b2792b21efb38c2144cd3a` | 0.0100 |
| 56 | `0xb55978845b220a3f98695847be992f27d3606bfd` | 0.0060 |
| 57 | `0x4e31680118f9267689a6cabb49bef79ef8d6032a` | 0.0020 |

## Verify everything yourself
- Fork-proof + tooling (open source): `github.com/webmixgamer/white-hat-recovery-agent` *(make public before publishing this page)*
- Fork-proof test: `test/QCOTokenRefund.t.sol`
- This recovery is **owner-signs / no-custody**: we never hold or move your funds; you sign your own claim.

