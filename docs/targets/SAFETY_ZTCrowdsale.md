# Safety check — ZTCrowdsale  (0xaf7aea249098f2c2f50cc11d4000ccf798194373)

Live balance: **21.1747 ETH**  |  bytecode 3001 bytes

## 1. Bytecode opcode audit
- Dangerous opcodes: **NONE**
  - upgradeable (DELEGATECALL/CALLCODE): **no**
  - self-destructible (SELFDESTRUCT): **no**

## 2. ETH-out surface (the ONLY ways value can leave)
- `withdraw()` — auth=**anyone**, public, modifiers=['atStage'], egress=[('transfer', 209), ('transfer', 210)]
- `refund()` — auth=**anyone**, public, modifiers=['atStage'], egress=[('send', 229)]
- `()` — auth=**anyone**, public, modifiers=['atStage'], egress=[('send', 262), ('send', 267)]

## 3. Drain history (ETH out of contract)
- Last ETH-out: block 4263244 (ts 1505154642), 2.0149 ETH to 0xa2593fea1b725e78822704fda8d66e0c92c1e223
- Recent outflows shown: 8 (newest first)

## 4. Recovery-attempt analysis (`refund()` = 0x590e1ae3)
- Addresses that called it and **SUCCEEDED**: 0
- Addresses that called it and **REVERTED**: 0
  - **No failed attempts** — nobody who tried was blocked.
