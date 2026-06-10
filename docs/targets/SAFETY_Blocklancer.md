# Safety check — Blocklancer  (0x9ea80e204045329ba752d03c395f82a12799f13d)

Live balance: **21.6614 ETH**  |  bytecode 3969 bytes

## 1. Bytecode opcode audit
- Dangerous opcodes: **{'CALLCODE': 1, 'CREATE2': 2}**
  - upgradeable (DELEGATECALL/CALLCODE): **YES — REVIEW**
  - self-destructible (SELFDESTRUCT): **no**

## 2. ETH-out surface (the ONLY ways value can leave)
- `finalize()` — auth=**anyone**, public, modifiers=[], egress=[('send', 307)]
- `refund()` — auth=**anyone**, public, modifiers=[], egress=[('send', 334)]

## 3. Drain history (ETH out of contract)
- Last ETH-out: block 20666916 (ts 1725328703), 0.0050 ETH to 0x80ad7165f29f97896a0b5758193879de34fd9712
- Recent outflows shown: 49 (newest first)

## 4. Recovery-attempt analysis (`refund()` = 0x590e1ae3)
- Addresses that called it and **SUCCEEDED**: 69
- Addresses that called it and **REVERTED**: 15
  - reverted callers (investigate): ['0x6ad0f0f578115b6fafa73df45e9f1e9056b84459', '0xcc8ab06eb5a14855fc8b90abcb6be2f34ee5cea1', '0xa1beac79dda14bce1ee698fdee47e2f7f2fd1f0d', '0x20abf65634219512c6c98a64614c43220ca2085b', '0x11f9ad6eb7e9e98349b8397c836c0e3e88455b0a', '0x771a2137708ca7e07e7b7c55e5ea666e88d7c0c8', '0x94ef531595ffe510f8dc92e0e07a987f57784338', '0x07004b458b56fb152c06ad81fe1be30c8a8b2ea1', '0xf6ac7c81ca099e34421b7eff7c9e80c8f56b74ae', '0xabedb3d632fddccd4e95957be4ee0daffbe6acdd', '0x32fd1e3d71d2290c8df0e009c394f2082e91df74', '0xe727ea5340256a5236287ee3074eea34d8483457', '0x6cd5b9b60d2bcf81af8e6ef5d750dc9a8f18bf45', '0xfc28b52160639167fa59f30232bd8d43fab681e6', '0xcdba57a9741fb99eba5e71d96c29327ce5258103']
