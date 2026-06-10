# Safety check — DigiPulse  (0x9aca6abfe63a5ae0dc6258cefb65207ec990aa4d)

Live balance: **100.5835 ETH**  |  bytecode 2287 bytes

## 1. Bytecode opcode audit
- Dangerous opcodes: **{'CALLCODE': 1, 'CREATE2': 2}**
  - upgradeable (DELEGATECALL/CALLCODE): **YES — REVIEW**
  - self-destructible (SELFDESTRUCT): **no**

## 2. ETH-out surface (the ONLY ways value can leave)
- `refundEther()` — auth=**anyone**, public, modifiers=[], egress=[('transfer', 132)]
- `withdrawFundsToOwner()` — auth=**anyone**, public, modifiers=[], egress=[('transfer', 162)]

## 3. Drain history (ETH out of contract)
- Last ETH-out: block 20666223 (ts 1725320351), 0.0500 ETH to 0x414cc62dc5c2081eca297928b469cdddc5c8f398
- Recent outflows shown: 49 (newest first)

## 4. Recovery-attempt analysis (`refundEther()` = 0x560ed6a1)
- Addresses that called it and **SUCCEEDED**: 515
- Addresses that called it and **REVERTED**: 89
  - reverted callers (investigate): ['0xb2b4b27d1b56b23ba16b253ec03a4f8ad5a1ce2b', '0x69631ec2cf6bceb2e6cd2fad6c9fe910d1b683dd', '0x8922559ca2feb7fa09d6b73a66d18aee2d86b5cd', '0x6177e07693861fb48735958f91cd944b7c0b9460', '0x31b3d6a94be2870ec578686be0a0d612fc3cc4aa', '0xd1d41cb6c7152923b3ed6ad8663e5f6b3175a443', '0xbb6a783707f9fff6eb5d97d7053ef06151f0b125', '0xb3a76920addab32264c9a182b12d7dc590501a8a', '0xe74391e83f4c813a9e34aafd97930ea1de2c5cd5', '0xe150501659b6dd0a6c014fd040bead874efb8642', '0xa3796bd75d35a824a21f968ad3bd610927f824ed', '0x02f8bf877823cab3246501cd8db8dc14c5cad109', '0xf946367a01b42d99e2c37b56322dc74e09300b5c', '0x39885eb552a3a814fe2c79781b9bc915843c1bd3', '0x1c4f5e82dac438c7f8cf47b4f237faed93b43b16', '0x244de0468620cb10c0a240a0a8cdb07478588385', '0xa2154cdc419da40b532ada5d2d737492412da808', '0x0e140ffc4a27d3f79513b70aae7e8e8e02f938e6', '0x01e5d52447d74fa40a21666f0240937b8e2265d1', '0x7b708930b5f7bb88ae1739c972be5698c2640f4a']
