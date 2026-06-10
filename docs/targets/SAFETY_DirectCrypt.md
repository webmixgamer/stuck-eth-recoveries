# Safety check — DirectCrypt  (0x12d5b7c26dd8dc6e2f71f5bf240d5e76452b2fe5)

Live balance: **81.8859 ETH**  |  bytecode 7431 bytes

## 1. Bytecode opcode audit
- Dangerous opcodes: **NONE**
  - upgradeable (DELEGATECALL/CALLCODE): **no**
  - self-destructible (SELFDESTRUCT): **no**

## 2. ETH-out surface (the ONLY ways value can leave)
- `refund()` — auth=**anyone**, public, modifiers=['preSaleEnded', 'inNormalState'], egress=[('transfer', 572)]
- `withdraw()` — auth=**signer-gated**, public, modifiers=['onlyOwner'], egress=[('transfer', 581)]

## 3. Drain history (ETH out of contract)
- Last ETH-out: block 11446874 (ts 1607892175), 2.7867 ETH to 0xe1eb804560757206fed56f47cc9fe53e9d2690dc
- Recent outflows shown: 50 (newest first)

## 4. Recovery-attempt analysis (`refund()` = 0x590e1ae3)
- Addresses that called it and **SUCCEEDED**: 54
- Addresses that called it and **REVERTED**: 14
  - reverted callers (investigate): ['0x3b86b3f28acd295a7d8c4833a8180d4fa5cf3763', '0xaef782db3fa1566c0df8fe9496a41f00ef9a7ded', '0xf137ddadc704bf51d11bb94d4730619b5ab6b168', '0x09cae90fe488ce0059c088229ee02e5c7f54e326', '0xed9ed232646d355b37cf871d2fe0f087fff05554', '0x96171a10fd3e03bd6e2d4a974a2b9d91610cf9b8', '0xe4c6581bcc58f694d50bf65520663bc8f6311bb4', '0xba6bf9eae46b014f41f0aa69390d7589fab9ed16', '0x26123982901ebdf281d0ee09760b2fbcc41b08fb', '0xd8efdbdd6337cde1d23033b3bd9c004f8a97ff64', '0x438d82fd8a4b5bc99e0bb3635fb57c9078d22ab5', '0xb43c7a1c6a1103254f1584a679bc8ef905d8c715', '0xa4b24fe110b238d0ec94fde9c5496a853b4c1f92', '0x078cd23b92f7fdf059379eec4a2b37874431c735']
