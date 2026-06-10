# Safety check — ahoolee  (0x575cb87ab3C2329A0248C7d70e0ead8E57f3e3F7)

Live balance: **191.5095 ETH**  |  bytecode 4049 bytes

## 1. Bytecode opcode audit
- Dangerous opcodes: **NONE**
  - upgradeable (DELEGATECALL/CALLCODE): **no**
  - self-destructible (SELFDESTRUCT): **no**

## 2. ETH-out surface (the ONLY ways value can leave)
- `withdraw()` — auth=**signer-gated**, public, modifiers=['onlyOwner'], egress=[('send', 418)]
- `refund()` — auth=**anyone**, public, modifiers=['onlyAfter'], egress=[('send', 428)]

## 3. Drain history (ETH out of contract)
- Last ETH-out: block 5772426 (ts 1528753316), 0.5000 ETH to 0xba49bbf6c9fc9a18008bd3abd08c699b0b5ceac6
- Recent outflows shown: 50 (newest first)

## 4. Recovery-attempt analysis (`refund()` = 0x590e1ae3)
- Addresses that called it and **SUCCEEDED**: 223
- Addresses that called it and **REVERTED**: 56
  - reverted callers (investigate): ['0x7d42ad985d43ad37f92ad720d9078d4dd549571f', '0x9873cf7b34fd8878aa40340920861aaae61e5237', '0x1bf546e7e42ebc76c270f84dc9f5f3e2e8e7276d', '0xef5e920c3178d6eabffd250b2f096912a3292f86', '0x4396005dbc7c3ef36f379f124196631477744fc1', '0xf7b56294b0ccd758666ffa830fc1136bf37fcf7d', '0x1da3531bed37f7de3baeaf35ed84fa58eb6b786b', '0xaa37234afba94d0cc94cee7058b89fd17525791e', '0x314612aa97cb3e8eb47c84be5847dbce9ce9b1d6', '0xbdb0209459d712baf9ed2115981300013cac9adb', '0xa7f1f4d8346fe8e3c89eb8dac5b3d46d29845739', '0xabb3613d01388a8d3c79b86fde98a50ae685b1c4', '0x8a898202616ba5f31ed5d37c1e7618b67169f9bb', '0xb9e50ced0ccf03079ffdba5fac16f05f4a9423f5', '0x8cc1c0b82f2de2b14ee5e0e2a811bffdb5e15b26', '0xa6697904c21ed0cc3df5480725f1ec857e0e9b88', '0x2ee8aca17be155e90a59e0ba796ced24052de270', '0xcfd0f8dcfaf2be2650e6e83ba6e1b77f3dadf05a', '0x55d4deb9198118354f9edb1a0d0efd754a3b765b', '0x692ea0f4b1badb064144cb11c8de8f248fbf7c5d']
