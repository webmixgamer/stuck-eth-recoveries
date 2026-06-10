# Safety check — jincor  (0xB3B33F59174f2eF62167770E4C9cAbaA3879eB5d)

Live balance: **19.0616 ETH**  |  bytecode 7952 bytes

## 1. Bytecode opcode audit
- Dangerous opcodes: **NONE**
  - upgradeable (DELEGATECALL/CALLCODE): **no**
  - self-destructible (SELFDESTRUCT): **no**

## 2. ETH-out surface (the ONLY ways value can leave)
- `refund()` — auth=**anyone**, public, modifiers=['icoEnded'], egress=[('transfer', 538)]
- `withdraw()` — auth=**signer-gated**, public, modifiers=['onlyOwner'], egress=[('transfer', 546)]

## 3. Drain history (ETH out of contract)
- Last ETH-out: block 6182763 (ts 1534788396), 0.2461 ETH to 0x2894541793e55c4cd949d9c6ff93316457996394
- Recent outflows shown: 13 (newest first)

## 4. Recovery-attempt analysis (`refund()` = 0x590e1ae3)
- Addresses that called it and **SUCCEEDED**: 12
- Addresses that called it and **REVERTED**: 48
  - reverted callers (investigate): ['0x06953644550ba5b43e7c64cac054aa8f09a06f14', '0xfb86df0f2cfde39f55bb5262a37a46320e04922a', '0x07ffad50741cb4dc0486426f58ae9b71c1bf9b33', '0x97becdbb4acdd989f89c5d238a230d7aee303c83', '0xf60af2ec733c50c8d5229408410d30b7f99f5fe9', '0xbbfebb65dd40f5513ed5d056a861836254e78792', '0x91517be92c26de475f80bc1fd3e23e70d2c36522', '0x2302c53ca59e3b72f9d16fe1e900acb5c6a73985', '0xf144006ca0d135775ebbea36616b0ae731435810', '0x009db089bfe6ebff40935efd6e316e545d45f7df', '0x47b4df97ba1448123bb41c8d62d2841bc5283824', '0xa4ee0e08d280b1b2adfb0c942e70bfb22152446a', '0xca5843f5d0f6e6aa7de98e9f23ce00486d0b3a34', '0x248d0aa689f90c5579ac7090cc7001fd18b1cc1a', '0x8d3004bd966006c927cb6ee1bca86120c53b02ef', '0xa006502f2d0feb7259a5a3dfcafe1ee5a4e3d40c', '0x47296eb3bb46031a63763f20dda23165a0a4fb46', '0x81e8946596d8fb22f08074cf652624678018a30b', '0x83260a576fd5fd8d8e7e724450a0185fc7119597', '0x684c850421afb8f443ca4b480ea1b96357c288f7']
