# Safety check — luckchemy  (0x18777Aec0B231D1a4A9C66B51253088a03affDFc)

Live balance: **10.7676 ETH**  |  bytecode 5531 bytes

## 1. Bytecode opcode audit
- Dangerous opcodes: **NONE**
  - upgradeable (DELEGATECALL/CALLCODE): **no**
  - self-destructible (SELFDESTRUCT): **no**

## 2. ETH-out surface (the ONLY ways value can leave)
- `processPrivatePurchase()` — auth=**anyone**, internal, modifiers=[], egress=[('transfer', 251)]
- `processPublicPurchase()` — auth=**anyone**, internal, modifiers=[], egress=[('transfer', 288)]
- `forwardFunds()` — auth=**signer-gated**, public, modifiers=['onlyOwner'], egress=[('transfer', 392), ('transfer', 393), ('transfer', 394)]
- `refund()` — auth=**anyone**, public, modifiers=[], egress=[('transfer', 408)]

## 3. Drain history (ETH out of contract)
- Last ETH-out: block 6360844 (ts 1537365436), 1.0000 ETH to 0xa491600e2dfeb1fc199f556d92fac5bf0e780bbb
- Recent outflows shown: 27 (newest first)

## 4. Recovery-attempt analysis (`refund()` = 0x590e1ae3)
- Addresses that called it and **SUCCEEDED**: 27
- Addresses that called it and **REVERTED**: 7
  - reverted callers (investigate): ['0x932aa206eb50ae9e65b723bf977d90a8c83d0c59', '0x3bf42a6833b5ef3cfcf7458ed73b6ac0f6c4e3d5', '0x55d3b2f3a5595750e7eab20ec6d90b50e496b661', '0x8b474bddbd0be5702b0d6956819b5a70d972a727', '0xb92c52c80b79ab093bca1f58632bfb72fed10ede', '0x13e2eee81a6da28dba1a3bf8a0343c93ab2e75ef', '0xa491600e2dfeb1fc199f556d92fac5bf0e780bbb']
