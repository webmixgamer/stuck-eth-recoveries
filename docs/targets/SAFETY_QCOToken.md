# Safety check — QCOToken  (0x3a8a97123bccd826228e5eb4144b48cce169517b)

Live balance: **31.4974 ETH**  |  bytecode 6863 bytes

## 1. Bytecode opcode audit
- Dangerous opcodes: **{'CALLCODE': 1, 'CREATE2': 2}**
  - upgradeable (DELEGATECALL/CALLCODE): **YES — REVIEW**
  - self-destructible (SELFDESTRUCT): **no**

## 2. ETH-out surface (the ONLY ways value can leave)
- `requestRefund()` — auth=**anyone**, public, modifiers=['requireState'], egress=[('transfer', 768)]
- `requestPayout()` — auth=**signer-gated**, public, modifiers=['onlyWithdraw', 'requireState'], egress=[('transfer', 777)]
- `rescueToken()` — auth=**signer-gated**, public, modifiers=['onlyTokenAssignmentControl'], egress=[('transfer', 785)]

## 3. Drain history (ETH out of contract)
- Last ETH-out: block 19770455 (ts 1714508231), 1.0000 ETH to 0x1a68d3c3ed0acaa4073407e7e553c472b17af669
- Recent outflows shown: 14 (newest first)

## 4. Recovery-attempt analysis (`requestRefund()` = 0xd5cef133)
- Addresses that called it and **SUCCEEDED**: 14
- Addresses that called it and **REVERTED**: 3
  - reverted callers (investigate): ['0x32173ceba79e39e6083f14303a373008a98216e5', '0x7d4982adf03def50fb60cccc3e79340f18f86c51', '0xa9c49630d09ea63114725a7f5cedd4b1f3ec7314']
