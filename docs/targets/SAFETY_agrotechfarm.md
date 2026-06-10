# Safety check — agrotechfarm  (0x3fD30f3E1fbF4F3Ea6BDf3E3bb11826266708869)

Live balance: **16.6917 ETH**  |  bytecode 7675 bytes

## 1. Bytecode opcode audit
- Dangerous opcodes: **NONE**
  - upgradeable (DELEGATECALL/CALLCODE): **no**
  - self-destructible (SELFDESTRUCT): **no**

## 2. ETH-out surface (the ONLY ways value can leave)
- `closeRefunds()` — auth=**signer-gated**, public, modifiers=['onlyOwner'], egress=[('transfer', 597)]
- `refund()` — auth=**anyone**, public, modifiers=[], egress=[('transfer', 612)]
- `createTokens()` — auth=**anyone**, public, modifiers=['saleIsOn'], egress=[('transfer', 621)]

## 3. Drain history (ETH out of contract)
- Last ETH-out: block 19018297 (ts 1705394195), 0.0120 ETH to 0x9c1e5c3bdf1933cd7427959e6a6c72c0894a31f8
- Recent outflows shown: 12 (newest first)

## 4. Recovery-attempt analysis (`refund()` = 0x590e1ae3)
- Addresses that called it and **SUCCEEDED**: 15
- Addresses that called it and **REVERTED**: 0
  - **No failed attempts** — nobody who tried was blocked.
