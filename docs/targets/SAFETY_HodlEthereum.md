# Safety check — HodlEthereum  (0x1bb28e79f2482df6bf60efc7a33365703bcf1536)

Live balance: **22.5281 ETH**  |  bytecode 761 bytes

## 1. Bytecode opcode audit
- Dangerous opcodes: **{'SELFDESTRUCT': 1}**
  - upgradeable (DELEGATECALL/CALLCODE): **no**
  - self-destructible (SELFDESTRUCT): **YES — REVIEW**

## 2. ETH-out surface (the ONLY ways value can leave)
- `party()` — auth=**anyone**, public, modifiers=[], egress=[('transfer', 20)]

## 3. Drain history (ETH out of contract)
- Last ETH-out: block 22790632 (ts 1750965239), 0.0560 ETH to 0x03f584b8bc3e91d5ef27c9697959b8a6e36a8f4d
- Recent outflows shown: 26 (newest first)

## 4. Recovery-attempt analysis (`party()` = 0x354284f2)
- Addresses that called it and **SUCCEEDED**: 26
- Addresses that called it and **REVERTED**: 4
  - reverted callers (investigate): ['0x7b5f9141e26e581862205ec32f2aca8878bc708c', '0xd02e4dfb47555722c26724ff05597ef74830c54c', '0xf0a65df2c868db73c7e8aaa5fb87c51d371cc8d7', '0xd2e38c0a867df4b28e7a7b33391dad536984590e']
