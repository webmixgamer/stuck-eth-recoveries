# DISCOVERY RESULTS — first sweep beyond ForgottenETH (2026-06-09)

Source: free BigQuery `balances⨝contracts` (>10 ETH, created <2019-07) → `docs/discovery_candidates`
(1019 rows). Pipeline: `scan_addresses.py --only-new` → 937 candidates → **359 verified-legacy** →
**18 open-refund/HONG survivors** → adversarial triage workflow (27 agents: classify + independent refute).

Per-target safety audits, owner lists, and recovery packages are in `docs/targets/`.

## Verdict summary
| Contract | Address | ETH | Dormant | Class | Verify | Note |
|---|---|---:|---:|---|---|---|
| DigiPulse | `0x9aca6abfe63a5ae0dc6258cefb65207ec990aa4d` | 100.6 | 91.6d | TRUE_TARGET | held | DigiPulse is a 2017 ICO that raised ~1920 ETH against an 8000 ETH minimum soft cap. finalise() was called once; because … |
| QCOToken | `0x3a8a97123bccd826228e5eb4144b48cce169517b` | 31.5 | 769.7d | TRUE_TARGET | held | The Qravity QCO ICO was ABORTED (live state() == 3 == States.Aborted, fork-confirmed; mintingFinished == false so burnAn… |
| hodlEthereum | `0x1bb28e79f2482df6bf60efc7a33365703bcf1536` | 22.5 | 107.6d | TRUE_TARGET | held | Depositors sent their own ETH to the payable fallback, which credits hodlers[msg.sender] += msg.value (line 13). Withdra… |
| DirectCryptTokenPreSale | `0x12d5b7c26dd8dc6e2f71f5bf240d5e76452b2fe5` | 81.9 | 2003.7d | NEEDS_FORK | held | A 2018-era DRCT token presale that took ETH from whitelisted investors and recorded each contribution in deposited[msg.s… |
| ZiberCrowdsale | `0xf0a924661b0263e5ce12756d07f45b8668c53380` | 37.5 | 107.9d | NEEDS_FORK | REFUTED | This is a failed 2017 ICO. MIN_ICO_GOAL was 5000 ETH and only ~37.5 ETH remains, so the soft cap was missed and the resi… |
| BlocklancerToken | `0x9ea80e204045329ba752d03c395f82a12799f13d` | 21.7 | 644.5d | NEEDS_FORK | held | This is the 2017 Blocklancer (LNC) ICO crowdsale. Contributors sent ETH to the payable fallback (lines 242-279), which r… |
| ZTCrowdsale | `0xaf7aea249098f2c2f50cc11d4000ccf798194373` | 21.2 | 982.1d | NEEDS_FORK | held | A 2017 ZeroTraffic (ZTT) crowdsale that raised only 28.39 ETH against a minAmount soft cap of 20000 ETH (0.14% of minimu… |
| KYCCrowdsale | `0x5de9f32b2665bb2cdc23bfb51b03e2a2985ecc87` | 15.4 | 1706d | NEEDS_FORK | REFUTED | Two refund surfaces exist on the same ~15.44 ETH pool (= part of weiRaised). (1) collectRefund (line 1226) pays msg.send… |
| CrowdSale | `0x0e915b35cc269b2dfc8bbd8e4a88ed4884a53efc` | 11.0 | 92.2d | NEEDS_FORK | REFUTED | This is the canonical OpenZeppelin "Crowdsale" tutorial contract. Contributors send ETH via the payable fallback/shiftSa… |
| PixelSelling | `0x709c7134053510fce03b464982eab6e3d89728a5` | 31.7 | 3006.5d | MURKY | — | Funds are NOT forgotten own-deposit refunds. The 31.72 ETH in balances[] was credited as: (a) creator commissions on eve… |
| EtherTanksCore | `0x336db6c1ead9cc4d5b0a33ac03c057e20640126a` | 27.6 | 314.6d | MURKY | — | NOT cleanly stuck. The 27.56 ETH is the shared game treasury backing the `balances` ledger. That ledger is NOT a record … |
| DRSCoin | `0x6b249a94182219cb1af58a197573dccd9ab94144` | 17.9 | 1008.6d | MURKY | — | NOT a clean stuck-deposit case. The 17.89 ETH is a POOLED dividend reserve: it was injected by whitelisted "game" contra… |
| OneSingleCoin | `0x6103281b7d1f7862d692fda42dc06ece61a40547` | 14.3 | 126.2d | MURKY | — | The 14.35 ETH is NOT forgotten own-deposit principal — it is game winnings. OneSingleCoin is a "one coin to rule them al… |
| CryptoPunksMarket | `0xb47e3cd837ddf8e4c57f05d70ab865de6e193bbb` | 3230.4 | 0.1d | LIVE_CONTRACT | — | NOT stuck. This is the canonical, still-actively-traded CryptoPunks marketplace. The 3230 ETH is live working-capital fl… |
| Marketplace | `0x00685230359bdb9e16704e1d3918b553e9a015e2` | 24.8 | 231.1d | LIVE_CONTRACT | — | NOT stuck. The 24.75 ETH is pending sale proceeds in a functioning NFT marketplace, not abandoned own-deposits. balances… |
| NumberBoard | `0x9249133819102b2ed31680468c8c67f6fe9e7505` | 21.9 | 15.6d | LIVE_CONTRACT | — | NOT stuck. This is a functioning trading dApp (solc 0.4.13, 2017). The 21.92 ETH is the WHOLE contract balance, a live m… |
| SingularDTVFund | `0x0286f920f893513c7ec9fe35ba0a4760229a243e` | 386.5 | 107.8d | FALSE_POSITIVE | — | NOT stuck. The 386.48 ETH is the undistributed reward/dividend pool for SNGX token holders, distributed pro-rata via wit… |
| SingularDTVFund | `0xd4f427e95f8dae7e8e1b6b962259a6f25ef38e5c` | 48.6 | 1442.6d | FALSE_POSITIVE | — | The 48.6 ETH is NOT stuck. The detector flagged withdrawContribution paying contributions[msg.sender], but that function… |

## Confirmed shortlist — 6 targets, 279.3 ETH (survived classify + refute)
- **DigiPulse** `0x9aca6abfe63a5ae0dc6258cefb65207ec990aa4d` — 100.6 ETH [TRUE_TARGET/HIGH] — **PROVEN #5** (`test/DigiPulseRefund.t.sol` 3/3, `SAFETY_DigiPulse.md`)
  - DigiPulse is a 2017 ICO that raised ~1920 ETH against an 8000 ETH minimum soft cap. finalise() was called once; because this.balance was far below 8000 ETH it set icoFailed=true, enabling refunds. Of ~590 depositors, ~243 already pulled refunds (refundEther() called 243x). The remaining 100.58 ETH b
- **QCOToken** `0x3a8a97123bccd826228e5eb4144b48cce169517b` — 31.5 ETH [TRUE_TARGET/HIGH]
  - The Qravity QCO ICO was ABORTED (live state() == 3 == States.Aborted, fork-confirmed; mintingFinished == false so burnAndFinish/Operational never happened). The payable fallback credited each contributor's ETH into ethPossibleRefunds[msg.sender] during the sale; on abort, requestRefund() lets each i
- **hodlEthereum** `0x1bb28e79f2482df6bf60efc7a33365703bcf1536` — 22.5 ETH [TRUE_TARGET/HIGH]
  - Depositors sent their own ETH to the payable fallback, which credits hodlers[msg.sender] += msg.value (line 13). Withdrawal via party() was time-locked until partyTime = 1596067200 = 2020-07-30 UTC. That unlock passed ~6 years ago, but 22.53 ETH remains because some hodlers never called party() to r
- **DirectCryptTokenPreSale** `0x12d5b7c26dd8dc6e2f71f5bf240d5e76452b2fe5` — 81.9 ETH [NEEDS_FORK/HIGH]
  - A 2018-era DRCT token presale that took ETH from whitelisted investors and recorded each contribution in deposited[msg.sender] (doPurchase, line 633). If the soft cap was never reached, the presale failed and each investor can reclaim exactly their own ETH via refund() (line 565). 81.89 ETH remainin
- **BlocklancerToken** `0x9ea80e204045329ba752d03c395f82a12799f13d` — 21.7 ETH [NEEDS_FORK/HIGH]
  - This is the 2017 Blocklancer (LNC) ICO crowdsale. Contributors sent ETH to the payable fallback (lines 242-279), which recorded each sender's own pledge in balancesEther[msg.sender] += msg.value (line 272) and minted LNC into balances[msg.sender]. The contract has a standard soft-cap design: if tota
- **ZTCrowdsale** `0xaf7aea249098f2c2f50cc11d4000ccf798194373` — 21.2 ETH [NEEDS_FORK/HIGH]
  - A 2017 ZeroTraffic (ZTT) crowdsale that raised only 28.39 ETH against a minAmount soft cap of 20000 ETH (0.14% of minimum) — a clearly failed ICO. 15 distinct addresses deposited their own ETH. Pre-ICO deposits (~7.215 ETH) were auto-forwarded to beneficiary/creator and are non-refundable by design;

## Canonicalization status — ALL 6 PROVEN (2026-06-10)
Every confirmed target now has a committed Foundry mainnet-fork proof + mandatory `safety_check`
(all §1 CALLCODE/CREATE2/SELFDESTRUCT flags were the known naive-opcode-count FP — every source has
0 dangerous primitives; CREATE2 is impossible in these 2017–18 contracts). 31/31 refund tests green.

| Target | ETH | Fork-proof | Owners | Package | Claims | Notes |
|---|---:|---|---|---|---|---|
| DigiPulse | 100.6 | `DigiPulseRefund` 3/3 | 79 | ✓ | ✓ | refundEther/icoFailed latch |
| DirectCrypt | 81.9 | `DirectCryptRefund` 3/3 | 32 | ✓ | ✓ | owner can `halt()` (reversible pause, not a drain) |
| QCOToken | 31.5 | `QCOTokenRefund` 2/2 | 57 | ✓ | ✓ | state==Aborted (terminal); requestRefund |
| hodlEthereum | 22.5 | `HodlEthereumRefund` 2/2 | 11 | ✓ | ✓ | no owner/admin at all — fully immutable; `party()` |
| Blocklancer | 21.7 | `BlocklancerRefund` 3/3 | 28 | ✓ | ✓ | private `balancesEther` (owners from txlist, reconciles); master-finalize() drain reverts |
| ZTCrowdsale | 21.2 | `ZTCrowdsaleRefund` 2/2 | 11 | ✓ | (FETH) | **permissionless 2-step** (anyone `endCrowdsale()` then owner `refund()`); **SOLVENT** — private `balances[]` (slot 23) sums to 21.1747 ETH == balance across 11 EOAs (pre-ICO-forwarded deposits correctly excluded) |

**Discovery total: 6 net-new proven targets, ~279 ETH** (DigiPulse + these 5). Combined with the 4
ForgottenETH targets → **10 proven targets, ~517 ETH**.

## Dismissed (correctly — adversarial layer earned its keep)
- **CryptoPunksMarket 3230 ETH** — LIVE NFT marketplace; `withdraw()` pays sellers' `pendingWithdrawals`. Not stuck.
- **SingularDTVFund 386 + 48.6 ETH** — FALSE POSITIVE: detector matched `withdrawContribution` from a SIBLING contract in the flattened source; selector ABSENT on deployed bytecode (a live dividend pool).
- **ZiberCrowdsale 37.5 ETH** — REFUTED: contract SELF-DESTRUCTED (`cast code`=0x); ICO rug-swept. The fork is the sole oracle.
- **KYCCrowdsale / CrowdSale** — REFUTED: refunds owner-gated / owner-drainable, not contributor-openable.
- **Marketplace / NumberBoard** — LIVE (seller proceeds / in-flight auction bids).
- **PixelSelling / EtherTanksCore / DRSCoin / OneSingleCoin** — MURKY (games / dividend token; 'rightful owner' contestable).

## Tool limitations surfaced (resolved, worth hardening)
- `safety_check.py §1` naive linear opcode count → FALSE 'upgradeable: CALLCODE/CREATE2' on legacy data-bearing bytecode (DigiPulse). Tell: CREATE2 can't exist in a 2017 contract. Resolve via verified-source (deployed==solc(src)) + 'no assembly/delegatecall/callcode/selfdestruct in source'.
- `detect_open_refund` on a FLATTENED multi-contract source can match a function from a NON-deployed sibling (SingularDTV). Mitigation: confirm the recovery selector exists on the deployed bytecode before trusting.
