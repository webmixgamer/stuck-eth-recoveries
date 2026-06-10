#!/usr/bin/env python3
"""Enumerate the unclaimed rightful owners of an open-refund target (steps 1 + 3).

For a proven open-refund contract, this produces the definitive list of addresses
that can still reclaim funds, each with amount + EOA/contract flag, and the total
recoverable. Uses HTTP JSON-RPC BATCHING (one round-trip per ~200 items) to keep
Alchemy usage minimal. Read-only; never sends a transaction.

Method:
  1. contributors  = unique senders of value>0, isError=0 txs to the contract
                     (Etherscan txlist; cached on disk).
  2. ledger[addr]  = the per-address deposit getter (e.g. saleBalanceOf/deposited),
                     batched eth_call.
  3. unclaimed     = ledger>0 AND (for "flag" ledgers that are NOT zeroed on refund)
                     NOT in the Refunded event-log set; for "zeroed" ledgers,
                     ledger>0 alone suffices.
  4. receiver-safe = eth_getCode(addr) empty => EOA (refund via .send/.transfer with
                     2300 gas succeeds). A contract owner is flagged NOT-simple-
                     recoverable (its fallback would need >2300 gas / a receive()).

Usage:
  python3 scripts/enumerate_owners.py --contract 0x.. --ledger 'saleBalanceOf(address)' \
      --refunded-by-logs --name ahoolee
  python3 scripts/enumerate_owners.py --contract 0x.. --ledger 'deposited(address)' \
      --zeroed-on-refund --name jincor
"""
import argparse
import json
import os
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def env(k):
    v = os.environ.get(k)
    if v:
        return v
    for line in open(os.path.join(ROOT, ".env")):
        line = line.strip()
        if line and not line.startswith("#") and line.split("=", 1)[0] == k:
            return line.split("=", 1)[1]
    return None


def keccak_selector(sig):
    # 4-byte selector via eth-utils-free keccak: use pysha3 if available, else cast.
    import subprocess
    return subprocess.run(["cast", "sig", sig], capture_output=True, text=True).stdout.strip()


def rpc_batch(url, reqs, chunk=200):
    """Send JSON-RPC requests in batched HTTP POSTs. reqs = list of (method, params).
    Returns list of results in order."""
    out = [None] * len(reqs)
    for start in range(0, len(reqs), chunk):
        batch = []
        for i, (m, p) in enumerate(reqs[start:start + chunk]):
            batch.append({"jsonrpc": "2.0", "id": start + i, "method": m, "params": p})
        data = json.dumps(batch).encode()
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        resp = json.loads(urllib.request.urlopen(req, timeout=60).read())
        for item in resp:
            out[item["id"]] = item.get("result")
    return out


def etherscan_txlist(contract, key):
    cache = f"/tmp/owners_tx_{contract.lower()}.json"
    if not os.path.exists(cache):
        url = (f"https://api.etherscan.io/v2/api?chainid=1&module=account&action=txlist"
               f"&address={contract}&startblock=0&endblock=99999999&sort=asc&apikey={key}")
        urllib.request.urlretrieve(url, cache)
    return json.load(open(cache))["result"]


def refunded_set(contract, key):
    """Addresses present in the Refunded(address,uint256) event log."""
    import subprocess
    sig = subprocess.run(["cast", "keccak", "Refunded(address,uint256)"],
                         capture_output=True, text=True).stdout.strip()
    url = (f"https://api.etherscan.io/v2/api?chainid=1&module=logs&action=getLogs"
           f"&address={contract}&topic0={sig}&fromBlock=0&toBlock=latest&apikey={key}")
    cache = f"/tmp/owners_refunds_{contract.lower()}.json"
    if not os.path.exists(cache):
        urllib.request.urlretrieve(url, cache)
    logs = json.load(open(cache)).get("result", [])
    return {("0x" + l["topics"][1][-40:]).lower() for l in logs if l.get("topics")}


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--contract", required=True)
    ap.add_argument("--ledger", required=True, help="getter sig, e.g. 'saleBalanceOf(address)'")
    ap.add_argument("--name", required=True)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--refunded-by-logs", action="store_true",
                   help="ledger NOT zeroed on refund; unclaimed = ledger>0 AND not in Refunded logs")
    g.add_argument("--zeroed-on-refund", action="store_true",
                   help="ledger zeroed on refund; unclaimed = ledger>0")
    ap.add_argument("--block", default="latest")
    args = ap.parse_args(argv)

    rpc = env("ALCHEMY_RPC_URL")
    ek = env("ETHERSCAN_API_KEY")
    C = args.contract.lower()
    sel = keccak_selector(args.ledger)

    # 1. contributors
    txs = etherscan_txlist(C, ek)
    contrib = {}
    for t in txs:
        if t.get("to", "").lower() == C and int(t.get("value", "0")) > 0 and t.get("isError") == "0":
            contrib[t["from"].lower()] = contrib.get(t["from"].lower(), 0) + int(t["value"])
    addrs = list(contrib)

    # 2. ledger reads (batched eth_call)
    def call_for(a):
        data = sel + a[2:].rjust(64, "0")
        return ("eth_call", [{"to": C, "data": data}, args.block])
    ledger_raw = rpc_batch(rpc, [call_for(a) for a in addrs])
    ledger = {a: int(r, 16) if r and r != "0x" else 0 for a, r in zip(addrs, ledger_raw)}

    # 3. unclaimed
    if args.refunded_by_logs:
        rf = refunded_set(C, ek)
        unclaimed = [a for a in addrs if ledger[a] > 0 and a not in rf]
    else:
        unclaimed = [a for a in addrs if ledger[a] > 0]

    # 4. receiver-safety: getCode (batched) for unclaimed
    code_raw = rpc_batch(rpc, [("eth_getCode", [a, args.block]) for a in unclaimed])
    is_eoa = {a: (c in (None, "0x", "0x0")) for a, c in zip(unclaimed, code_raw)}

    # contract live balance
    bal = int(rpc_batch(rpc, [("eth_getBalance", [C, args.block])])[0], 16)

    rows = sorted(((a, ledger[a], is_eoa[a]) for a in unclaimed), key=lambda x: -x[1])
    total = sum(v for _, v, _ in rows)
    eoa_total = sum(v for _, v, e in rows if e)
    contract_owners = [(a, v) for a, v, e in rows if not e]

    report = {
        "contract": args.contract, "name": args.name, "block": args.block,
        "live_balance_wei": bal, "live_balance_eth": bal / 1e18,
        "n_contributors": len(addrs), "n_unclaimed": len(rows),
        "total_unclaimed_wei": total, "total_unclaimed_eth": total / 1e18,
        "eoa_recoverable_eth": eoa_total / 1e18,
        "n_contract_owners": len(contract_owners),
        "unclaimed": [{"address": a, "wei": v, "eth": v / 1e18, "eoa": e} for a, v, e in rows],
    }
    out = os.path.join(ROOT, "docs", "targets", f"owners_{args.name}.json")
    json.dump(report, open(out, "w"), indent=2)

    print(f"=== {args.name}  {args.contract} @ block {args.block} ===")
    print(f"live balance:        {bal/1e18:.4f} ETH")
    print(f"contributors:        {len(addrs)}")
    print(f"UNCLAIMED owners:    {len(rows)}  totaling {total/1e18:.4f} ETH")
    print(f"  EOA-recoverable:   {eoa_total/1e18:.4f} ETH ({sum(1 for _,_,e in rows if e)} addrs)")
    if contract_owners:
        print(f"  CONTRACT owners (refund .send/.transfer may fail): {len(contract_owners)} "
              f"holding {sum(v for _,v in contract_owners)/1e18:.4f} ETH")
        for a, v in contract_owners[:5]:
            print(f"     {a}  {v/1e18:.4f} ETH")
    print(f"reconcile: unclaimed {total/1e18:.3f} vs balance {bal/1e18:.3f} ETH "
          f"({'covered' if bal>=total else 'SHORTFALL'})")
    print(f"top 8 EOA owners:")
    for a, v, e in [r for r in rows if r[2]][:8]:
        print(f"  {a}  {v/1e18:.4f} ETH")
    print(f"\nreport -> docs/targets/owners_{args.name}.json")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
